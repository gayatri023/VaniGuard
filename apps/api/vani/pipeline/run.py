"""One command through the model, validators, confidence and router. Fail-safe: any
doubt, error or missing field ends in Tier C, never Tier A."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from ..domain.confidence import FieldFeatures, agreement_rate
from ..domain.numbers import confusable_partner, parse_amounts
from ..domain.payee import Contact, PayeeMatch, rank_payees
from ..domain.router import FieldInput, RouterInput, Tier, route
from ..domain.validators import validate
from ..settings import Settings, compute_cost
from .clients import ModelCall, ModelClient, ModelInput

TEMPS = (0.0, 0.7, 0.7)  # sample 0 is the displayed parse; 1 and 2 give the agreement signal


@dataclass
class SampleLog:
    idx: int
    temperature: float
    status: str
    raw: dict[str, Any] | None = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class PipelineResult:
    tier: str
    reasons: list[str]
    error_code: str | None = None
    transcript: str | None = None
    payee_id: str | None = None
    payee_name: str | None = None
    amount: int | None = None
    intent: str | None = None
    note: str | None = None
    chips: dict[str, Any] | None = None
    self_conf: dict[str, float] = field(default_factory=dict)
    agreement: dict[str, float] = field(default_factory=dict)
    combined: dict[str, float] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    samples: list[SampleLog] = field(default_factory=list)
    stage_ms: dict[str, int] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


def tier_c(code: str, samples: list[SampleLog] | None = None, stage: dict[str, int] | None = None) -> PipelineResult:
    return PipelineResult("C", [code], error_code=code, samples=samples or [], stage_ms=stage or {})


def _top_id(text: str | None, contacts: list[Contact], delta: float) -> str | None:
    if not text:
        return None
    m = rank_payees(text, contacts, delta)
    return m.candidates[0].payee_id if m.candidates else None


async def run_pipeline(
    client: ModelClient, inp: ModelInput, contacts: list[Contact], ceiling: int,
    st: Settings, timeout_s: float = 8.0,
) -> PipelineResult:  # fmt: skip
    try:
        return await _run(client, inp, contacts, ceiling, st, timeout_s)
    except Exception:  # noqa: BLE001 - fail safe
        return tier_c("pipeline_error")


async def _run(
    client: ModelClient, inp: ModelInput, contacts: list[Contact], ceiling: int,
    st: Settings, timeout_s: float,
) -> PipelineResult:  # fmt: skip
    rs = st.router
    t_model = time.perf_counter()

    async def one(i: int) -> tuple[int, ModelCall | None, str]:
        for attempt in (0, 1):
            try:
                return i, await asyncio.wait_for(client.extract(inp, TEMPS[i], i), timeout_s), "ok"
            except TimeoutError:
                return i, None, "timeout"  # no retry: it would blow the latency budget
            except Exception as exc:  # noqa: BLE001
                if attempt == 1:
                    return i, None, f"error:{type(exc).__name__}"
        return i, None, "error"

    results = await asyncio.gather(*(one(i) for i in range(3)))
    stage = {"model": int((time.perf_counter() - t_model) * 1000)}
    ok = {i: c for i, c, _ in results if c is not None}
    logs = [
        SampleLog(i, TEMPS[i], status, c.output.model_dump() if c else None,
                  c.latency_ms if c else 0, c.tokens_in if c else 0, c.tokens_out if c else 0)
        for i, c, status in results
    ]  # fmt: skip
    if len(ok) < 2:
        return tier_c("model_unavailable", logs, stage)

    out = ok[min(ok)].output  # the displayed parse: lowest-index successful sample
    t_val = time.perf_counter()
    payee_text = out.payee_text or ""
    match: PayeeMatch = rank_payees(payee_text, contacts, rs.payee_ambiguity_delta)
    v = validate(
        transcript=out.transcript_roman, amount_text=out.amount_text, amount_value=out.amount_value,
        intent=out.intent, speech_detected=out.speech_detected, payee_text=payee_text,
        payee_match=match, ceiling=ceiling, confusable_penalty=rs.confusable_penalty,
    )  # fmt: skip

    def slot(fn: Any) -> list[Any]:  # a failed sample counts as disagreement
        return [fn(ok[i].output) if i in ok else None for i in range(3)]

    agree = {
        "payee": agreement_rate(slot(lambda o: _top_id(o.payee_text, contacts, rs.payee_ambiguity_delta))),
        "amount": agreement_rate(slot(lambda o: o.amount_value)),
        "intent": agreement_rate(slot(lambda o: o.intent)),
    }
    sc = out.self_conf
    selfc = {"payee": sc.payee or 0.0, "amount": sc.amount or 0.0, "intent": sc.intent or 0.0}
    scores = {"payee": v.payee_score, "amount": v.amount_score, "intent": v.intent_score}
    conf = {f: rs.combiner.combine(f, FieldFeatures(selfc[f], agree[f], scores[f])) for f in agree}
    stage["validate"] = int((time.perf_counter() - t_val) * 1000)

    # chips: only plausible, distinct candidates
    name_of = {c.payee_id: c.display_name for c in contacts}
    top = match.candidates[0].score if match.candidates else 0.0
    pids = [c.payee_id for c in match.candidates if c.score >= top - 0.25 and c.score > 0]
    pids += [p for p in slot(lambda o: _top_id(o.payee_text, contacts, rs.payee_ambiguity_delta)) if p]
    pids = list(dict.fromkeys(pids))
    vals = [out.amount_value, *slot(lambda o: o.amount_value)]
    vals += [c.value for c in parse_amounts(out.transcript_roman, ignore=payee_text) if c.confidence >= 0.5]
    if out.amount_value:
        vals.append(confusable_partner(out.amount_value))
    vals = list(dict.fromkeys(x for x in vals if x))
    payee_opts = {name_of[p]: p for p in pids}
    amount_opts = {f"\u20b9{x}": x for x in vals}

    t_route = time.perf_counter()
    decision = route(
        RouterInput(
            FieldInput(conf["payee"], tuple(payee_opts)), FieldInput(conf["amount"], tuple(amount_opts)),
            FieldInput(conf["intent"]), v.flags,
        ),
        rs.router,
    )  # fmt: skip
    stage["route"] = int((time.perf_counter() - t_route) * 1000)

    payee_id = match.candidates[0].payee_id if match.candidates and payee_text else None
    tier, reasons = decision.tier, list(decision.reasons)
    if tier is Tier.A and (payee_id is None or out.amount_value is None or out.intent != "send_money"):
        tier, reasons = Tier.C, ["missing_display_field"]  # defence in depth

    chips = None
    if tier is Tier.B:
        f = decision.uncertain_fields[0]
        opts = payee_opts if f == "payee" else amount_opts
        chips = {"field": f, "options": [{"label": k, "value": val} for k, val in opts.items() if k in decision.chips]}

    tin = sum(c.tokens_in for c in ok.values())
    tout = sum(c.tokens_out for c in ok.values())
    audio = sum(c.audio_tokens_in or 0 for c in ok.values()) or None
    cost = compute_cost(st.pricing, tin, tout, audio) if st.pricing and st.backend == "gemini" else 0.0
    return PipelineResult(
        tier.value, reasons,
        error_code="no_speech" if "empty_or_short_transcript" in v.flags else None,
        transcript=out.transcript_roman, payee_id=payee_id, payee_name=name_of.get(payee_id or ""),
        amount=out.amount_value, intent=out.intent, note=out.note, chips=chips,
        self_conf=selfc, agreement=agree, combined=conf, scores=scores, flags=sorted(v.flags), samples=logs,
        stage_ms=stage, tokens_in=tin, tokens_out=tout, cost_usd=cost,
    )  # fmt: skip
