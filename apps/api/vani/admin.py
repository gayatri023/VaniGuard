"""Read-only admin API for the live dashboard (token protected).

Every statistic comes from vani.domain.metrics, the same functions the analysis pipeline uses,
so the dashboard replay and `make analyze` agree to the last decimal."""

from __future__ import annotations

import hmac
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from datetime import timedelta
from statistics import median
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .cards import Card
from .db import CommandRow, EventRow, SessionRow, utcnow
from .domain.metrics import auroc, brier, ece, risk_coverage_curve, wilson_interval
from .domain.router import margin_score
from .export import flat_csv
from .settings import Settings

DELTAS = [round(float(x), 2) for x in np.arange(-0.30, 0.1001, 0.01)]
FUNNEL = ["mic", "task", "processing", "result", "success", "survey", "end"]
SYNTHETIC_MODELS = {"synthetic-sim"}


def clean(x: Any) -> Any:
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def pct(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def prop(k: int, n: int) -> dict[str, Any]:
    lo, hi = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": k / n if n else None, "lo": lo, "hi": hi}


def has_parse(r: CommandRow) -> bool:
    return bool(r.parsed_payee_id) and r.parsed_amount is not None and r.parsed_intent == "send_money"


def study_rows(db: Session) -> list[CommandRow]:
    """Rows that count toward accuracy: no practice cards, no seeded-error probes."""
    return [r for r in db.scalars(select(CommandRow)) if not r.is_practice and not r.is_probe]


def build_admin_router(st: Settings, Db: sessionmaker[Session], cards: dict[str, Card]) -> APIRouter:
    def guard(x_admin_token: str | None = Header(None)) -> None:
        if not st.admin_token:
            raise HTTPException(503, "admin_disabled")
        if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), st.admin_token.encode()):
            raise HTTPException(401, "bad_token")

    r = APIRouter(prefix="/api/admin", dependencies=[Depends(guard)])

    def scores(rows: list[CommandRow]) -> list[float]:
        return [margin_score(row.combined_conf or {}, st.router.router, row.validator_flags or []) for row in rows]

    @r.get("/summary")
    def summary() -> Any:
        with Db() as db:
            sessions = list(db.scalars(select(SessionRow)))
            allc = list(db.scalars(select(CommandRow)))
            rows = [c for c in allc if not c.is_practice and not c.is_probe]
            events = list(db.scalars(select(EventRow).where(EventRow.type.in_(["screen_view", "client_error"]))))
        now = utcnow()
        seen: dict[str, set[str]] = {k: set() for k in FUNNEL}
        last_screen: dict[str, str] = {}
        for e in events:
            if e.type == "screen_view":
                sc = (e.payload or {}).get("screen")
                if sc in seen:
                    seen[sc].add(e.session_id)
                last_screen[e.session_id] = str(sc)
        done = {s.session_id for s in sessions if s.status == "completed"}
        dropouts = Counter(last_screen.get(s.session_id, "consent") for s in sessions if s.session_id not in done)
        errors_1h = sum(1 for c in allc if c.error_code and now - c.created_at < timedelta(hours=1)) + sum(
            1 for e in events if e.type == "client_error" and now - e.ts < timedelta(hours=1))
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        spend = sum(c.cost_usd for c in allc if c.created_at >= today)
        return clean({
            "synthetic": any(c.model in SYNTHETIC_MODELS for c in allc),
            "participants": {"started": len(sessions), "completed": len(done)},
            "commands": {"logged": len(rows), "practice": sum(c.is_practice for c in allc), "probes": sum(c.is_probe for c in allc)},
            "funnel": [{"step": "consent", "sessions": len(sessions)}] + [{"step": k, "sessions": len(seen[k])} for k in FUNNEL],
            "dropout_last_screen": dict(dropouts),
            "tiers": dict(Counter(c.route_tier for c in rows)),
            "modes": dict(Counter(c.ui_mode for c in rows)),
            "arms": dict(Counter(c.arm for c in rows)),
            "errors_last_hour": errors_1h,
            "spend": {"today_usd": spend, "daily_cap_usd": st.daily_cost_cap_usd if st.daily_cost_cap_usd < 1e8 else None,
                      "session_cap_usd": st.session_cost_cap_usd if st.session_cost_cap_usd < 1e8 else None},
            "versions": {"router": st.router.router.version, "prompt": st.prompt_version, "app": st.app_version},
        })

    @r.get("/quality")
    def quality() -> Any:
        with Db() as db:
            rows = study_rows(db)
        n = len(rows)
        out: dict[str, Any] = {"n": n, "fields": {}, "by_tag": {}, "by_difficulty": {}, "latency_ms": {}}
        for f, getter in (("payee", lambda x: x.correct_payee), ("amount", lambda x: x.correct_amount),
                          ("intent", lambda x: x.correct_intent), ("all", lambda x: x.correct_all)):  # fmt: skip
            out["fields"][f] = prop(sum(1 for x in rows if getter(x)), n)
        tag_rows: dict[str, list[CommandRow]] = {}
        diff_rows: dict[str, list[CommandRow]] = {}
        for x in rows:
            c = cards.get(x.card_id)
            if c:
                diff_rows.setdefault(c.difficulty, []).append(x)
                for t in c.condition_tags:
                    tag_rows.setdefault(t, []).append(x)
        overall = out["fields"]["all"]["rate"]
        for name, grp, key in (("by_tag", tag_rows, "tag"), ("by_difficulty", diff_rows, "difficulty")):
            out[name] = {k: {**prop(sum(1 for x in v if x.correct_all), len(v)),
                             "below_average_10pts": bool(overall is not None and len(v) and (sum(1 for x in v if x.correct_all) / len(v)) <= overall - 0.10)}
                         for k, v in sorted(grp.items())}  # fmt: skip
        esc = [x for x in rows if x.route_tier != "A" and has_parse(x)]
        out["escalation_precision"] = prop(sum(1 for x in esc if not x.correct_all), len(esc))
        out["latency_ms"]["total"] = {"p50": pct([x.latency_ms for x in rows], 50), "p95": pct([x.latency_ms for x in rows], 95)}
        for stage in ("transcode", "model", "validate", "route"):
            v = [float(x.stage_ms[stage]) for x in rows if stage in (x.stage_ms or {})]
            out["latency_ms"][stage] = {"p50": pct(v, 50), "p95": pct(v, 95), "n": len(v)}
        return clean(out)

    @r.get("/risk-coverage")
    def risk_coverage() -> Any:
        with Db() as db:
            rows = study_rows(db)
        sc = scores(rows)
        correct = [bool(x.correct_all) for x in rows]
        curve = [asdict(p) for p in risk_coverage_curve(sc, correct, DELTAS)]
        confirm = [x for x in rows if x.arm == "always_confirm" and x.user_action_final in ("paid", "edited", "manual")]
        routed = [x for x in rows if x.arm == "routed" and x.user_action_final in ("paid", "edited", "manual")]

        def arm_stats(g: list[CommandRow]) -> dict[str, Any]:
            taps = [x.taps_count for x in g if x.taps_count is not None]
            tm = [x.time_to_complete_ms for x in g if x.time_to_complete_ms is not None]
            return {"n": len(g), "median_taps": median(taps) if taps else None, "median_time_ms": median(tm) if tm else None,
                    "wrong_final": prop(sum(1 for x in g if x.final_correct_all is False), len(g))}  # fmt: skip
        return clean({"n": len(rows), "deltas": DELTAS, "curve": curve, "live_delta": 0.0,
                      "router_version": st.router.router.version,
                      "arms": {"routed": arm_stats(routed), "always_confirm": arm_stats(confirm)}})

    @r.get("/calibration")
    def calibration() -> Any:
        with Db() as db:
            rows = study_rows(db)
        out: dict[str, Any] = {"n": len(rows), "signals": {}}
        for f, label in (("amount", lambda x: x.correct_amount), ("payee", lambda x: x.correct_payee)):
            for sig, pick in (("self_conf", lambda x, f=f: (x.self_conf or {}).get(f)),
                              ("agreement", lambda x, f=f: (x.agreement or {}).get(f)),
                              ("validator", lambda x, f=f: (x.validator_scores or {}).get(f)),
                              ("combined", lambda x, f=f: (x.combined_conf or {}).get(f))):  # fmt: skip
                pairs = [(float(pick(x)), 1.0 if label(x) else 0.0) for x in rows if pick(x) is not None]
                p = np.array([a for a, _ in pairs]); y = np.array([b for _, b in pairs])
                bins = []
                for b in range(10):
                    m = (np.minimum((p * 10).astype(int), 9) == b) if len(p) else np.array([], dtype=bool)
                    if m.any():
                        bins.append({"bin": b, "n": int(m.sum()), "mean_conf": float(p[m].mean()), "accuracy": float(y[m].mean())})
                out["signals"][f"{f}.{sig}"] = {"n": len(p), "ece": ece(p, y) if len(p) else None,
                                                "brier": brier(p, y) if len(p) else None,
                                                "auroc": auroc(p, y) if len(p) else None, "bins": bins}  # fmt: skip
        return clean(out)

    @r.get("/health")
    def data_health() -> Any:
        with Db() as db:
            allc = list(db.scalars(select(CommandRow)))
            sessions = list(db.scalars(select(SessionRow)))
        rows = [c for c in allc if not c.is_practice and not c.is_probe]
        by_session: dict[str, list[CommandRow]] = {}
        for c in allc:
            by_session.setdefault(c.session_id, []).append(c)
        dup = Counter((c.session_id, c.client_request_id) for c in allc)
        return clean({
            "n_commands": len(rows),
            "missing": {"transcript": sum(1 for c in rows if not c.transcript_roman),
                        "payee": sum(1 for c in rows if not c.parsed_payee_id),
                        "amount": sum(1 for c in rows if c.parsed_amount is None),
                        "no_final_action": sum(1 for c in rows if c.user_action_final is None)},
            "duplicate_requests": sum(1 for v in dup.values() if v > 1),
            "sessions_without_study_commands": sum(1 for s in sessions if not any(not c.is_practice for c in by_session.get(s.session_id, []))),
            "error_codes": dict(Counter(c.error_code for c in rows if c.error_code)),
            "versions_seen": {"model": dict(Counter(c.model for c in rows)), "router": dict(Counter(c.router_version for c in rows)),
                              "prompt": dict(Counter(c.prompt_version for c in rows)), "app": dict(Counter(c.app_version for c in rows))},
        })  # fmt: skip

    @r.get("/export.csv")
    def export_csv() -> Response:
        with Db() as db:
            body = flat_csv(db)
        return Response(body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=commands_flat.csv"})

    _: Callable[..., Any] = guard
    return r
