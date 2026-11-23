"""make analyze: raw CSV export -> results.md, figures/, tables/ (no manual steps, fixed seeds).

    python analysis/run.py [--csv data/export/commands_flat.csv] [--out analysis/output]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 110, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
TEAL, AMBER, GREY = "#00696b", "#b26a00", "#6f7979"


def pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.{d}f}%"


def num(x: float | None, d: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def md_table(df: pd.DataFrame, fmt: dict[str, str] | None = None) -> str:
    fmt = fmt or {}
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(fmt[c].format(v) if c in fmt and not (isinstance(v, float) and np.isnan(v)) else ("n/a" if isinstance(v, float) and np.isnan(v) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_rc(rc: pd.DataFrame, h2: dict, n: int, path: Path) -> None:
    d = rc[(rc.n_fast > 0)].sort_values("coverage")
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.fill_between(d.coverage, d.wilson_lo, d.wilson_hi, color=TEAL, alpha=0.15, label="95% Wilson band")
    ax.plot(d.coverage, d.wrong_rate, color=TEAL, lw=2)
    ax.scatter(d.coverage[d.reliable], d.wrong_rate[d.reliable], color=TEAL, s=14, zorder=3)
    ax.scatter(d.coverage[~d.reliable], d.wrong_rate[~d.reliable], facecolors="none", edgecolors=TEAL, s=14, zorder=3, label="n_fast < 30 (unreliable)")
    ax.axhline(h2["b"], color="crimson", ls="--", lw=1.2, label=f"B = {pct(h2['b'])}")
    if h2["final"]:
        ax.scatter([h2["final"]["coverage"]], [h2["final"]["wrong_rate"]], marker="*", s=180, color=AMBER, zorder=4, label=f"chosen offset {h2['final']['threshold']:.2f}")
    ho = h2["held_out"]
    if ho["n"]:
        ax.errorbar([ho["coverage"]], [ho["rate"]], yerr=[[max(0.0, ho["rate"] - ho["lo"])], [max(0.0, ho["hi"] - ho["rate"])]], fmt="D", color="black", capsize=4, label="held-out folds (95% Wilson)")
    ax.scatter([0], [0], marker="s", color=GREY, label="always-confirm baseline")
    ax.set(xlabel="Fast-path coverage (share of all commands)", ylabel="Wrong-execution rate", title=f"Risk-coverage curve (n = {n} commands)", xlim=(-0.02, 1.02), ylim=(-0.005, max(0.1, float(d.wilson_hi.max()) * 1.05)))
    ax.legend(fontsize=8, frameon=False)
    save(fig, path)


def fig_h4(t: pd.DataFrame, overall: float, n: int, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 0.5 * max(3, len(t)) + 1))
    y = np.arange(len(t))
    ax.barh(y, t.rate, color=[AMBER if f else TEAL for f in t.flag], alpha=0.85)
    ax.errorbar(t.rate, y, xerr=[np.clip(t.rate - t.lo, 0, None), np.clip(t.hi - t.rate, 0, None)], fmt="none", ecolor="black", capsize=3)
    ax.axvline(overall, color="black", ls="--", lw=1, label=f"overall {pct(overall)}")
    ax.set_yticks(y, [f"{c}  (n={k})" for c, k in zip(t.condition, t.n, strict=True)])
    ax.set(xlabel="Accuracy, all three fields correct", xlim=(0, 1), title=f"Accuracy by condition (n = {n} commands; amber = 10+ points below average)")
    ax.legend(frameon=False, fontsize=8)
    save(fig, path)


def fig_reliability(df: pd.DataFrame, n: int, path: Path) -> None:
    sigs = [("self_conf", "self_conf"), ("agreement", "agreement"), ("validator", "validator_scores"), ("combined", "combined_conf")]
    fig, axes = plt.subplots(2, 4, figsize=(12, 6))
    for r, f in enumerate(P.FIELDS):
        y = df[f"correct_{f}"].astype(float).to_numpy()
        for c, (name, col) in enumerate(sigs):
            ax, x = axes[r][c], P.feature(df, col, f)
            k = ~np.isnan(x) & ~np.isnan(y)
            b = np.minimum((x[k] * 10).astype(int), 9)
            for i in range(10):
                m = b == i
                if m.any():
                    ax.scatter(x[k][m].mean(), y[k][m].mean(), s=20 + 160 * m.sum() / k.sum(), color=TEAL, alpha=0.6)
            ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1)
            ax.set(xlim=(0, 1), ylim=(0, 1.02), title=f"{f}.{name} (n={int(k.sum())})")
    fig.suptitle(f"Reliability diagrams (dot size = n in bin; n = {n} commands)")
    save(fig, path)


def fig_v2(v2: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for name, col in (("v1", GREY), ("v2", TEAL)):
        pts = [p for p in v2["curves"][name] if p.n_fast > 0]
        ax.plot([p.coverage for p in pts], [p.wrong_rate for p in pts], color=col, lw=2, label=f"{name} (out-of-fold for v2)")
    ax.set(xlabel="Fast-path coverage", ylabel="Wrong-execution rate", title=f"v1 weighted sum vs v2 logistic regression (n = {v2['coverage_at_b']['n']})")
    ax.legend(frameon=False)
    save(fig, path)


def fig_business(grid: pd.DataFrame, path: Path) -> None:
    pv = grid.pivot(index="loss_inr", columns="value_per_tap_inr", values="best_offset")
    fig, ax = plt.subplots(figsize=(6.2, 4))
    im = ax.imshow(pv.to_numpy(), aspect="auto", cmap="viridis", origin="lower")
    ax.set_xticks(range(len(pv.columns)), [str(c) for c in pv.columns])
    ax.set_yticks(range(len(pv.index)), [str(i) for i in pv.index])
    for i in range(pv.shape[0]):
        for j in range(pv.shape[1]):
            ax.text(j, i, f"{pv.iloc[i, j]:.2f}", ha="center", va="center", color="white", fontsize=8)
    ax.set(xlabel="Assumed value of one tap (INR)", ylabel="Assumed loss per wrong payment (INR)", title="Best threshold offset by stakes (assumptions, not findings)")
    fig.colorbar(im, label="offset (higher = stricter)")
    save(fig, path)


def main(csv: Path, out: Path) -> Path:
    cfg = yaml.safe_load((Path(__file__).parent / "prereg.yaml").read_text())
    b_unset = cfg["b_max"] is None
    b = 0.05 if b_unset else float(cfg["b_max"])
    out, (tdir, fdir) = out, (out / "tables", out / "figures")
    tdir.mkdir(parents=True, exist_ok=True); fdir.mkdir(parents=True, exist_ok=True)

    df_all = P.load(csv)
    synthetic = bool(df_all.model.isin(P.SYNTHETIC_MODELS).any())
    df = P.add_scores(P.study_rows(df_all), P.router_cfg())
    n = len(df)
    if n < 20:
        raise SystemExit(f"only {n} study commands in {csv}; nothing meaningful to analyse yet")

    r1, r2, r3, r4, ar, cal, v2 = P.h1(df, cfg), P.h2(df, cfg, b), P.h3(df_all, cfg), P.h4(df, cfg), P.arms(df, cfg), P.calibration(df), P.v2_router(df, cfg, b)
    rc = r2["curve"]
    biz = P.business(df, cfg, rc)

    rc.to_csv(tdir / "risk_coverage.csv", index=False)
    r4["table"].to_csv(tdir / "h4_conditions.csv", index=False)
    cal.to_csv(tdir / "calibration.csv", index=False)
    biz["grid"].to_csv(tdir / "business_grid.csv", index=False)
    fig_rc(rc, r2, n, fdir / "risk_coverage.png"); fig_h4(r4["table"], r4["overall"], n, fdir / "h4_conditions.png")
    fig_reliability(df, n, fdir / "reliability.png"); fig_business(biz["grid"], fdir / "business_breakeven.png")
    if "curves" in v2:
        fig_v2(v2, fdir / "router_v2_vs_v1.png")
    if v2["candidate"]:
        (out / "router_v2_candidate.yaml").write_text(yaml.safe_dump({
            "router_version": "v2-lr-candidate", "status": "CANDIDATE: not deployed; v1 is untouched. Re-choose thresholds with the H2 rule before use.",
            "fitted_on_rows": n, "models": v2["candidate"]}, sort_keys=False))

    versions = {c: sorted(df[c].dropna().unique().tolist()) for c in ("router_version", "prompt_version", "app_version", "model")}
    L: list[str] = ["# Results (auto-generated by `analysis/run.py`; do not edit by hand)", ""]
    if synthetic:
        L += ["> **SYNTHETIC DATA. NOT RESULTS.** These rows come from the simulator (model = synthetic-sim). Do not quote any number below.", ""]
    if b_unset:
        L += ["> **PREREG INCOMPLETE.** `analysis/prereg.yaml` has no `b_max`; this run used a placeholder B. Set B in `docs/PREREG.md`, copy it here, commit, then re-run.", ""]
    if any(len(v) > 1 for k, v in versions.items() if k != "model"):
        L += [f"> **Mixed versions in the data: {versions}.** Do not pool across router or prompt versions without justification.", ""]
    L += [f"Input: `{csv.name}` (sha256 {hashlib.sha256(csv.read_bytes()).hexdigest()[:12]}). Versions: {versions}.", ""]
    tiers = df.route_tier.value_counts().sort_index()
    L += ["## Data", "",
          f"- Participants with study commands: **{df.participant.nunique()}**; study commands: **{n}** (practice cards: {int(df_all.is_practice.sum())}, seeded-error probes: {int(df_all.is_probe.sum())}, both excluded from accuracy).",
          "- Router tiers: " + ", ".join(f"{k} {v}" for k, v in tiers.items()) + ". Arms: " + ", ".join(f"{k} {v}" for k, v in df.arm.value_counts().sort_index().items()) + ".",
          f"- Accuracy, all three fields correct: **{pct(r4['overall'])}** (payee {pct(df.correct_payee.astype(float).mean())}, amount {pct(df.correct_amount.astype(float).mean())}, intent {pct(df.correct_intent.astype(float).mean())}).", ""]

    p = r1["pooled"]
    L += ["## H1: does the combined signal predict correctness better than self-report?", "", f"Rule: {r1['rule']}.", "",
          md_table(pd.DataFrame([{"field": f, "n": v["n"], "AUROC self": v["auroc_self"], "AUROC combined": v["auroc_combined"]} for f, v in r1["fields"].items()]), {"AUROC self": "{:.3f}", "AUROC combined": "{:.3f}"}), "",
          f"Pooled (n = {p['n']}): self {num(p['auroc_self'])}, combined {num(p['auroc_combined'])}, difference **{num(p['diff'])}** (participant-grouped bootstrap 95% CI {num(p['lo'])} to {num(p['hi'])}).", "",
          f"**Decision: {'adopt the combined signal' if r1['adopt_combined'] else 'ship the simpler signal and report that'}.**", ""]

    fin, ho = r2["final"], r2["held_out"]
    L += ["## H2: how much of the traffic can take the fast path while wrong executions stay low?", "",
          f"Rule: pick the offset with the highest fast-path coverage whose Wilson 95% upper bound on the wrong-execution rate is at most B = **{pct(b)}**; thresholds are chosen on training folds and reported on held-out folds ({r2['folds']} participant-grouped folds).", "",
          (f"Final threshold on all data: offset **{fin['threshold']:.2f}** (0 = router v1), coverage **{pct(fin['coverage'])}**, {fin['n_wrong']} wrong of {fin['n_fast']} fast-path commands, 95% upper bound {pct(fin['wilson_hi'])}." if fin else "No threshold meets the bound with this data, so no fast path would be justified."), "",
          f"Held-out (pooled over folds): **{ho['k']} wrong of {ho['n']}** fast-path commands = {pct(ho['rate'])} (Wilson 95% {pct(ho['lo'])} to {pct(ho['hi'])}); held-out coverage {pct(ho['coverage'])} of {ho['n_test']} commands. Offsets chosen per fold: {r2['fold_thresholds']}.", "",
          "![risk-coverage](figures/risk_coverage.png)", ""]

    h3r = r3["overall"]
    L += ["## H3: do users confirm deliberately wrong parses (confirmation blindness)?", "",
          (f"**{h3r['k']} of {h3r['n']}** seeded probes were paid as shown = {pct(h3r['rate'])} (Wilson 95% {pct(h3r['lo'])} to {pct(h3r['hi'])})." if h3r["n"] else "No seeded-error probes in this data."), "",
          ("Rule: if this exceeds the unsafe rate, treat always-confirm as an unsafe baseline in the write-up. **Result: exceeds it.**" if r3["unsafe"] else "Rule: if this exceeds the unsafe rate, treat always-confirm as an unsafe baseline. **Result: does not exceed it (or no probes).**"), ""]
    for t, v in r3["by_type"].items():
        L.append(f"- {t} probes: {v['k']}/{v['n']} ({pct(v['rate'])})")
    L.append("")

    t4 = r4["table"].copy()
    L += ["## H4: do errors cluster in identifiable conditions?", "", md_table(t4[["condition", "n", "rate", "lo", "hi", "gap_points", "flag"]], {"rate": "{:.3f}", "lo": "{:.3f}", "hi": "{:.3f}", "gap_points": "{:+.1f}"}), "",
          "Flagged conditions (10 or more points below average): " + (", ".join(t4[t4.flag].condition) or "none") + ".", "", "![h4](figures/h4_conditions.png)", ""]

    L += ["## Routed versus always-confirm", ""]
    if ar:
        L += [md_table(pd.DataFrame([{"arm": a, "n": v["n"], "median taps": v["median_taps"], "median time (s)": v["median_time_s"], "wrong at payment": f"{v['wrong_at_payment']['k']}/{v['wrong_at_payment']['n']} ({pct(v['wrong_at_payment']['rate'])})"} for a, v in ar["arms"].items()]), {"median taps": "{:.1f}", "median time (s)": "{:.1f}"}), "",
              f"Always-confirm minus routed, median taps: {num(ar['diff_taps']['diff'], 2)} (bootstrap 95% CI {num(ar['diff_taps']['lo'], 2)} to {num(ar['diff_taps']['hi'], 2)}); median time (s): {num(ar['diff_time_s']['diff'], 2)} ({num(ar['diff_time_s']['lo'], 2)} to {num(ar['diff_time_s']['hi'], 2)}).", ""]
    else:
        L += ["Only one arm present; arms were not randomised in this data.", ""]

    L += ["## Calibration", "", md_table(cal, {"ece": "{:.3f}", "brier": "{:.3f}", "auroc": "{:.3f}"}), "", "Validator scores are not probabilities, so read their AUROC rather than ECE.", "", "![reliability](figures/reliability.png)", ""]

    L += ["## Exploratory (not pre-registered)", "", "### Router v2 candidate: logistic regression per field", ""]
    fv = {f: v for f, v in v2["fields"].items() if "v1" in v}
    if fv:
        L += [md_table(pd.DataFrame([{"field": f, "n": v["n"], "AUROC v1": v["v1"]["auroc"], "AUROC v2": v["v2"]["auroc"], "ECE v1": v["v1"]["ece"], "ECE v2": v["v2"]["ece"], "Brier v1": v["v1"]["brier"], "Brier v2": v["v2"]["brier"]} for f, v in fv.items()]), {c: "{:.3f}" for c in ("AUROC v1", "AUROC v2", "ECE v1", "ECE v2", "Brier v1", "Brier v2")}), "",
              "v2 numbers are out-of-fold (participant-grouped). A candidate `router_v2_candidate.yaml` was written; v1 was not overwritten."]
        if "coverage_at_b" in v2:
            c = v2["coverage_at_b"]
            L += ["", f"Coverage at B = {pct(c['b'])} (threshold chosen on the same out-of-fold scores, so optimistic): v1 {pct(c['v1']['coverage']) if c['v1'] else 'none qualifies'}, v2 {pct(c['v2']['coverage']) if c['v2'] else 'none qualifies'} (n = {c['n']}).", "", "![v2](figures/router_v2_vs_v1.png)"]
    else:
        L += ["Not enough usable rows or outcome variety to fit v2."]
    L += ["", "### Business break-even (assumptions, not findings)", "",
          f"Measured: mean taps for commands that left the fast path {num(biz['taps_nonfast'], 2)}; mean model cost per command ${num(biz['cost_usd_per_command'], 4)}. Money inputs are labelled assumptions in `analysis/prereg.yaml` and are varied on the grid.", "",
          "Loss per wrong payment (INR) above which the stricter offset 0.05 beats the live router, by assumed value of a tap (INR): " + "; ".join(f"{k}: {('%.0f' % v) if v is not None else 'never (no extra safety gained)'}" for k, v in biz["breakeven_loss"].items()) + ".", "",
          "![breakeven](figures/business_breakeven.png)", "",
          "## Limitations", "", "Convenience sample of peers; scripted scenarios; no real money at stake; small sample for the rarest errors; the router thresholds and weights are v1 placeholders; real UPI ends in PIN authentication, which this prototype does not model."]
    (out / "results.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return out / "results.md"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=ROOT / "data" / "export" / "commands_flat.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "analysis" / "output")
    a = ap.parse_args()
    print(main(a.csv, a.out))
