"""Pre-registered analyses. Every statistic comes from vani.domain.metrics (the same functions the
dashboard uses), every number in results.md is produced here, and all randomness is seeded."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression

from vani.admin import DELTAS
from vani.domain.metrics import auroc, bootstrap_ci, brier, ece, risk_coverage_curve, select_threshold, wilson_interval
from vani.domain.router import RouterConfig, margin_score
from vani.settings import CONFIG_DIR, load_settings

JSON_COLS = ["self_conf", "agreement", "validator_scores", "combined_conf", "validator_flags", "route_reasons", "stage_ms"]
BOOL_COLS = ["is_practice", "is_probe", "correct_payee", "correct_amount", "correct_intent", "correct_all", "final_correct_all"]
SYNTHETIC_MODELS = {"synthetic-sim"}
FIELDS = ("payee", "amount")


def to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return {"True": True, "False": False}.get(v)
    return None if pd.isna(v) else bool(v)


def load(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv)
    for c in JSON_COLS:
        df[c] = df[c].map(lambda s: json.loads(s) if isinstance(s, str) and s else ({} if c != "validator_flags" else []))
    for c in BOOL_COLS:
        df[c] = df[c].map(to_bool)
    df["participant"] = df["session_id"]
    return df


def study_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that count toward accuracy: no practice cards, no seeded-error probes."""
    return df[(df.is_practice == False) & (df.is_probe == False)].reset_index(drop=True)  # noqa: E712


def router_cfg() -> RouterConfig:
    return load_settings({"VANI_DEV": "1"}).router.router


def feature(df: pd.DataFrame, col: str, f: str) -> np.ndarray:
    return np.array([(d or {}).get(f, np.nan) if (d or {}).get(f) is not None else np.nan for d in df[col]], dtype=float)


def add_scores(df: pd.DataFrame, cfg: RouterConfig) -> pd.DataFrame:
    df = df.copy()
    df["margin"] = [margin_score(c or {}, cfg, fl or []) for c, fl in zip(df.combined_conf, df.validator_flags, strict=True)]
    return df


def folds_for(groups: np.ndarray, k: int, seed: int) -> np.ndarray:
    """Deterministic participant-grouped folds: a participant is never in both train and test."""
    uniq = sorted(set(groups.tolist()))
    k = max(2, min(k, len(uniq)))
    perm = np.random.default_rng(seed).permutation(len(uniq))
    fold_of = {uniq[i]: j % k for j, i in enumerate(perm)}
    return np.array([fold_of[g] for g in groups])


def prop(k: int, n: int) -> dict[str, float]:
    lo, hi = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": k / n if n else float("nan"), "lo": lo, "hi": hi}


# ---------------------------------------------------------------------------- H1
def h1(df: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """AUROC for predicting field correctness: self-confidence alone vs the combined signal."""
    out: dict[str, Any] = {"fields": {}}
    s_all, c_all, y_all, g_all = [], [], [], []
    for f in FIELDS:
        s, c = feature(df, "self_conf", f), feature(df, "combined_conf", f)
        y = df[f"correct_{f}"].astype(float).to_numpy()
        keep = ~np.isnan(s) & ~np.isnan(c) & ~np.isnan(y)
        s, c, y, g = s[keep], c[keep], y[keep], df.participant.to_numpy()[keep]
        out["fields"][f] = {"n": int(keep.sum()), "auroc_self": auroc(s, y), "auroc_combined": auroc(c, y)}
        s_all.append(s); c_all.append(c); y_all.append(y); g_all.append(g)
    s, c, y, g = map(np.concatenate, (s_all, c_all, y_all, g_all))
    stat: Callable[[np.ndarray], float] = lambda i: auroc(c[i], y[i]) - auroc(s[i], y[i])  # noqa: E731
    d, lo, hi = bootstrap_ci(stat, g, cfg["n_boot"], seed=cfg["seed"])
    out["pooled"] = {"n": len(y), "auroc_self": auroc(s, y), "auroc_combined": auroc(c, y), "diff": d, "lo": lo, "hi": hi}
    adopt = bool(d >= cfg["h1_min_delta_auroc"] and lo > 0)
    out["adopt_combined"] = adopt
    out["rule"] = f"adopt the combined signal if the AUROC difference is at least {cfg['h1_min_delta_auroc']} and its bootstrap 95% CI excludes zero"
    return out


# ---------------------------------------------------------------------------- H2
def curve_table(df: pd.DataFrame) -> pd.DataFrame:
    """Risk-coverage over the offset grid. Identical to the dashboard replay by construction."""
    pts = risk_coverage_curve(df.margin.to_numpy(), df.correct_all.astype(bool).to_numpy(), DELTAS)
    return pd.DataFrame([p.__dict__ for p in pts])


def h2(df: pd.DataFrame, cfg: dict[str, Any], b: float) -> dict[str, Any]:
    scores, correct, groups = df.margin.to_numpy(), df.correct_all.astype(bool).to_numpy(), df.participant.to_numpy()
    full = risk_coverage_curve(scores, correct, DELTAS)
    pick = select_threshold(full, b)
    fold = folds_for(groups, cfg["folds"], cfg["seed"])
    n_fast = n_wrong = n_test = 0
    chosen: list[float | None] = []
    for f in sorted(set(fold.tolist())):
        tr, te = fold != f, fold == f
        p = select_threshold(risk_coverage_curve(scores[tr], correct[tr], DELTAS), b)
        chosen.append(p.threshold if p else None)
        n_test += int(te.sum())
        if p:
            fast = scores[te] >= p.threshold
            n_fast += int(fast.sum())
            n_wrong += int((fast & ~correct[te]).sum())
    held = prop(n_wrong, n_fast)
    return {"b": b, "final": pick.__dict__ if pick else None, "held_out": {**held, "coverage": n_fast / n_test if n_test else float("nan"), "n_test": n_test},
            "fold_thresholds": chosen, "folds": len(chosen), "curve": curve_table(df)}


# ---------------------------------------------------------------------------- H3, H4, arms
def h3(df_all: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    p = df_all[(df_all.is_probe == True) & (df_all.is_practice == False)]  # noqa: E712
    blind = prop(int((p.user_action_final == "paid").sum()), len(p))
    by_type = {t: prop(int((g.user_action_final == "paid").sum()), len(g)) for t, g in p.groupby("probe_type")}
    return {"overall": blind, "by_type": by_type, "unsafe": bool(len(p) and blind["rate"] > cfg["h3_unsafe_rate"])}


def card_tags() -> dict[str, tuple[str, list[str]]]:
    pool = yaml.safe_load((CONFIG_DIR / "cards" / "pool.yaml").read_text())
    return {c["card_id"]: (c["difficulty"], list(c["condition_tags"])) for c in pool}


def h4(df: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    tags = card_tags()
    overall = float(df.correct_all.astype(float).mean()) if len(df) else float("nan")
    rows: dict[str, list[bool]] = {}
    for cid, ok in zip(df.card_id, df.correct_all, strict=True):
        for t in tags.get(cid, ("", []))[1]:
            rows.setdefault(t, []).append(bool(ok))
    table = []
    for t, v in sorted(rows.items()):
        p = prop(sum(v), len(v))
        table.append({"condition": t, **p, "gap_points": (p["rate"] - overall) * 100, "flag": bool((p["rate"] - overall) * 100 <= -cfg["h4_gap_points"])})
    return {"overall": overall, "table": pd.DataFrame(table)}


def arms(df: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any] | None:
    done = df[df.user_action_final.isin(["paid", "edited", "manual"])]
    if done.arm.nunique() < 2:
        return None
    out: dict[str, Any] = {"arms": {}}
    for a, g in done.groupby("arm"):
        out["arms"][a] = {"n": len(g), "median_taps": float(g.taps_count.median()), "median_time_s": float(g.time_to_complete_ms.median()) / 1000,
                          "wrong_at_payment": prop(int((g.final_correct_all == False).sum()), len(g))}  # noqa: E712
    r, c = done[done.arm == "routed"], done[done.arm == "always_confirm"]
    for name, col, scale in (("taps", "taps_count", 1.0), ("time_s", "time_to_complete_ms", 1000.0)):
        rv, cv, gr, gc = r[col].to_numpy(float) / scale, c[col].to_numpy(float) / scale, r.participant.to_numpy(), c.participant.to_numpy()
        vals = np.concatenate([rv, cv]); groups = np.concatenate([gr, gc]); is_c = np.concatenate([np.zeros(len(rv), bool), np.ones(len(cv), bool)])

        def stat(i: np.ndarray, vals: np.ndarray = vals, is_c: np.ndarray = is_c) -> float:
            a, b = vals[i][is_c[i]], vals[i][~is_c[i]]
            return float(np.median(a) - np.median(b)) if len(a) and len(b) else float("nan")
        d, lo, hi = bootstrap_ci(stat, groups, cfg["n_boot"], seed=cfg["seed"])
        out[f"diff_{name}"] = {"diff": d, "lo": lo, "hi": hi}
    return out


# ------------------------------------------------------------------- calibration
def calibration(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for f in FIELDS:
        y = df[f"correct_{f}"].astype(float).to_numpy()
        for sig, col in (("self_conf", "self_conf"), ("agreement", "agreement"), ("validator", "validator_scores"), ("combined", "combined_conf")):
            x = feature(df, col, f)
            k = ~np.isnan(x) & ~np.isnan(y)
            rows.append({"field": f, "signal": sig, "n": int(k.sum()), "ece": ece(x[k], y[k]) if k.any() else np.nan,
                         "brier": brier(x[k], y[k]) if k.any() else np.nan, "auroc": auroc(x[k], y[k]) if k.any() else np.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- v2 router
def v2_router(df: pd.DataFrame, cfg: dict[str, Any], b: float) -> dict[str, Any]:
    """Per-field logistic regression on the three signals, participant-grouped out-of-fold, vs the v1 weighted sum."""
    fold_all = folds_for(df.participant.to_numpy(), cfg["folds"], cfg["seed"])
    res: dict[str, Any] = {"fields": {}, "candidate": {}}
    oof_v2: dict[str, np.ndarray] = {}
    for f in FIELDS:
        X = np.column_stack([feature(df, "self_conf", f), feature(df, "agreement", f), feature(df, "validator_scores", f)])
        y = df[f"correct_{f}"].astype(float).to_numpy()
        ok = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        if ok.sum() < 40 or len(set(y[ok])) < 2:
            res["fields"][f] = {"skipped": f"only {int(ok.sum())} usable rows or a single outcome class"}
            continue
        p = np.full(len(y), np.nan)
        for k in sorted(set(fold_all.tolist())):
            tr, te = ok & (fold_all != k), ok & (fold_all == k)
            if len(set(y[tr])) < 2 or not te.any():
                continue
            p[te] = LogisticRegression(max_iter=1000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        v1 = feature(df, "combined_conf", f)
        k2 = ok & ~np.isnan(p)
        res["fields"][f] = {"n": int(k2.sum()),
                            "v1": {"auroc": auroc(v1[k2], y[k2]), "ece": ece(v1[k2], y[k2]), "brier": brier(v1[k2], y[k2])},
                            "v2": {"auroc": auroc(p[k2], y[k2]), "ece": ece(p[k2], y[k2]), "brier": brier(p[k2], y[k2])}}
        oof_v2[f] = p
        m = LogisticRegression(max_iter=1000).fit(X[ok], y[ok])
        res["candidate"][f] = {"features": ["self_conf", "agreement", "validator_score"], "coef": [float(c) for c in m.coef_[0]], "intercept": float(m.intercept_[0])}
    if len(oof_v2) == 2:
        thr = np.round(np.arange(0.5, 1.0, 0.01), 2)
        both = ~np.isnan(oof_v2["payee"]) & ~np.isnan(oof_v2["amount"])
        correct = df.correct_all.astype(bool).to_numpy()[both]
        s1 = np.minimum(feature(df, "combined_conf", "payee"), feature(df, "combined_conf", "amount"))[both]
        s2 = np.minimum(oof_v2["payee"], oof_v2["amount"])[both]
        res["coverage_at_b"] = {"n": int(both.sum()), "b": b}
        for name, s in (("v1", s1), ("v2", s2)):
            pk = select_threshold(risk_coverage_curve(s, correct, thr), b)
            res["coverage_at_b"][name] = {"threshold": pk.threshold, "coverage": pk.coverage, "n_fast": pk.n_fast, "wilson_hi": pk.wilson_hi} if pk else None
        res["curves"] = {"v1": risk_coverage_curve(s1, correct, thr), "v2": risk_coverage_curve(s2, correct, thr)}
    return res


# --------------------------------------------------------------- business model
def business(df: pd.DataFrame, cfg: dict[str, Any], rc: pd.DataFrame) -> dict[str, Any]:
    """Net value per 1,000 commands = taps saved x value of a tap - wrong fast-path executions x average loss - model cost.
    All money inputs are labelled assumptions; rates come from the study."""
    b = cfg["business"]
    nonfast = df[df.route_tier != "A"]
    taps_nonfast = float(nonfast.taps_count.mean()) if len(nonfast) and nonfast.taps_count.notna().any() else 3.0
    cost_usd = float(df.cost_usd.mean()) if len(df) else 0.0
    cost_inr = cost_usd * b["usd_inr"]
    cells = []
    for v in b["value_per_tap_inr"]:
        for loss in b["avg_loss_per_wrong_payment_inr"]:
            net = rc.coverage * (taps_nonfast - 1) * v * 1000 - (rc.n_wrong / rc.n_total) * loss * 1000 - cost_inr * 1000
            best = int(np.argmax(net.to_numpy()))
            cells.append({"value_per_tap_inr": v, "loss_inr": loss, "best_offset": float(rc.threshold.iloc[best]), "net_inr_per_1000": float(net.iloc[best])})
    live = rc[rc.threshold == 0.0].iloc[0]
    strict = rc[rc.threshold == 0.05].iloc[0]
    d_cov, d_wrong = live.coverage - strict.coverage, live.n_wrong / live.n_total - strict.n_wrong / strict.n_total
    be = {v: (d_cov * (taps_nonfast - 1) * v / d_wrong if d_wrong > 0 and d_cov >= 0 else None) for v in b["value_per_tap_inr"]}
    return {"taps_nonfast": taps_nonfast, "cost_usd_per_command": cost_usd, "grid": pd.DataFrame(cells), "breakeven_loss": be, "live": live.to_dict(), "strict": strict.to_dict()}
