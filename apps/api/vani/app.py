"""FastAPI app. Ground truth and confidence numbers never leave the server (confidences only in dev)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import secrets
import time
import uuid
from datetime import timedelta
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from .admin import build_admin_router
from .cards import (
    CONFIG_DIR_CARDS,
    assign_arms,
    assign_cards,
    load_cards,
    load_contacts,
    load_groups,
)
from .db import (
    Base,
    CommandRow,
    DeleteGateRow,
    DeletionRow,
    EventRow,
    SampleRow,
    SessionRow,
    SurveyRow,
    install_guards,
    make_engine,
    utcnow,
)  # fmt: skip
from .pipeline.audio import ALLOWED_MIME, MAX_UPLOAD_BYTES, AudioError, base_mime, to_wav16k
from .pipeline.clients import DevInput, FakeClient, GeminiClient, ModelClient, ModelInput
from .pipeline.run import PipelineResult, run_pipeline, tier_c
from .probes import make_probe
from .ratelimit import RateLimiter
from .settings import Settings, load_settings

TOTAL_CARDS = 8
DONE_ACTIONS = ("paid", "edited", "manual", "abandoned")
CLIENT_EVENTS = {
    "screen_view", "mic_granted", "mic_denied", "mic_unsupported", "inapp_browser", "offline",
    "client_error", "recording_started", "processing_slow", "processing_timeout",
}  # fmt: skip


class SessionIn(BaseModel):
    consent_version: str = Field(max_length=32)
    language_comfort: Literal["hindi_dominant", "english_dominant", "balanced"]
    noise_self_report: Literal["quiet", "some", "noisy"]
    device_class: str | None = Field(None, max_length=24)
    browser: str | None = Field(None, max_length=48)
    os: str | None = Field(None, max_length=48)


class ActionIn(BaseModel):
    action: Literal["pay", "retry", "manual", "edit", "abandon"]
    chip_field: Literal["payee", "amount"] | None = None
    chip_value: str | int | None = None
    final_payee_id: str | None = None
    final_amount: int | None = Field(None, gt=0, lt=10_000_000)
    taps_count: int = Field(0, ge=0, le=200)
    time_to_mic_ms: int | None = Field(None, ge=0)
    time_result_to_action_ms: int | None = Field(None, ge=0)
    time_to_complete_ms: int | None = Field(None, ge=0)


class SurveyIn(BaseModel):
    trust_amount: int = Field(ge=1, le=5)
    low_effort: int = Field(ge=1, le=5)
    would_use: int = Field(ge=1, le=5)
    free_text: str | None = Field(None, max_length=500)


class DeleteIn(BaseModel):
    deletion_code: str = Field(max_length=32)


class EventIn(BaseModel):
    session_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def build_client(st: Settings) -> ModelClient:
    if st.backend == "gemini":
        assert st.gemini_api_key and st.gemini_model
        return GeminiClient(
            st.gemini_api_key, st.gemini_model, st.prompt_text, thinking_budget=st.gemini_thinking_budget
        )
    return FakeClient(delay_s=0.6)


def create_app(settings: Settings | None = None, model_client: ModelClient | None = None) -> FastAPI:
    st = settings or load_settings()
    client = model_client or build_client(st)
    engine = make_engine(st.database_url)
    Base.metadata.create_all(engine)
    install_guards(engine)  # events become append-only at the database level
    Db = sessionmaker(engine, expire_on_commit=False)
    contacts = load_contacts(CONFIG_DIR_CARDS / "contacts.yaml")
    cards = {c.card_id: c for c in load_cards(CONFIG_DIR_CARDS / "pool.yaml", contacts)}
    card_list = list(cards.values())
    groups = load_groups(CONFIG_DIR_CARDS / "contacts.yaml")
    ip_limit, sess_limit = RateLimiter(st.rate_per_ip_per_min), RateLimiter(st.rate_per_session_per_min)
    consent_version = "v2-probes" if st.probes_enabled else "v2"

    app = FastAPI(title="Vani-Guard API", docs_url="/docs" if st.dev else None, redoc_url=None,
                  openapi_url="/openapi.json" if st.dev else None)  # fmt: skip
    app.add_middleware(
        CORSMiddleware, allow_origins=list(st.allowed_origins), allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )  # fmt: skip
    app.state.settings, app.state.Db, app.state.cards = st, Db, cards

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return resp

    def client_ip(request: Request) -> str:
        if st.trust_proxy and (fwd := request.headers.get("x-forwarded-for")):
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def log(db: Session, type_: str, session_id: str, cmd_id: str | None = None, /, **payload: Any) -> None:
        db.add(EventRow(session_id=session_id, cmd_id=cmd_id, type=type_, payload=payload, app_version=st.app_version))

    def get_session(db: Session, session_id: str) -> SessionRow:
        row = db.get(SessionRow, session_id)
        if row is None:
            raise HTTPException(404, "unknown_session")
        return row

    # ------------------------------------------------------------------ system
    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True, "version": st.app_version, "backend": st.backend, "model": client.name,
                "study_paused": st.study_paused}  # fmt: skip

    @app.get("/readyz")
    def readyz() -> dict[str, bool]:
        with Db() as db:
            db.execute(text("SELECT 1"))
        return {"ready": True}

    @app.get("/api/config")
    def public_config() -> dict[str, Any]:
        return {"probes_enabled": st.probes_enabled, "consent_version": consent_version, "total_cards": TOTAL_CARDS}

    @app.get("/api/contacts")
    def list_contacts() -> list[dict[str, str]]:
        return [{"payee_id": c.payee_id, "display_name": c.display_name} for c in contacts]

    # ---------------------------------------------------------------- sessions
    @app.post("/api/sessions")
    def create_session(body: SessionIn) -> dict[str, Any]:
        if st.study_paused:
            raise HTTPException(503, "study_paused")
        sid, code = str(uuid.uuid4()), secrets.token_hex(4).upper()
        with Db() as db:
            served = dict(db.execute(select(CommandRow.card_id, func.count()).group_by(CommandRow.card_id)).all())
            ids = assign_cards(card_list, served, random.Random(sid))
            arms = assign_arms(random.Random(sid + "arms"), TOTAL_CARDS, st.arms_enabled)
            db.add(SessionRow(session_id=sid, consent_version=body.consent_version,
                              language_comfort=body.language_comfort, noise_self_report=body.noise_self_report,
                              device_class=body.device_class, browser=body.browser, os=body.os,
                              deletion_code_hash=_sha(code), card_ids=ids, arms=arms))  # fmt: skip
            log(db, "session_created", sid, consent_version=body.consent_version)
            db.commit()
        return {"session_id": sid, "deletion_code": code, "total_cards": TOTAL_CARDS}

    @app.get("/api/sessions/{session_id}/next-card")
    def next_card(session_id: str) -> dict[str, Any]:
        with Db() as db:
            s = get_session(db, session_id)
            done = set(db.scalars(select(CommandRow.card_id).where(
                CommandRow.session_id == session_id, CommandRow.user_action_final.in_(DONE_ACTIONS))))  # fmt: skip
            for i, cid in enumerate(s.card_ids):
                if cid not in done:
                    c = cards[cid]  # only the task text is sent; truth_* never leaves the server
                    return {"done": False, "card": {"card_id": c.card_id, "scenario_text": c.scenario_text,
                                                    "practice": c.practice},
                            "index": i, "total": TOTAL_CARDS}  # fmt: skip
        return {"done": True, "card": None, "index": TOTAL_CARDS, "total": TOTAL_CARDS}

    # ---------------------------------------------------------------- commands
    @app.post("/api/commands")
    async def post_command(
        request: Request,
        session_id: str = Form(...), card_id: str = Form(...), client_request_id: str = Form(..., max_length=64),
        client_audio_mime: str = Form(""), audio_ms: int = Form(0),
        audio: UploadFile | None = File(None),
        dev_transcript: str | None = Form(None), dev_overrides: str | None = Form(None),
    ) -> Any:  # fmt: skip
        if st.study_paused:
            return JSONResponse({"error": "study_paused"}, status_code=503)
        if not ip_limit.allow(client_ip(request)) or not sess_limit.allow(session_id):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        t0 = time.perf_counter()
        with Db() as db:
            s = get_session(db, session_id)
            if card_id not in s.card_ids:
                raise HTTPException(403, "card_not_assigned")
            prior = db.scalar(select(CommandRow).where(CommandRow.session_id == session_id,
                                                       CommandRow.client_request_id == client_request_id))  # fmt: skip
            if prior is not None:
                return prior.response_json  # idempotent resubmission
            arm = s.arms[s.card_ids.index(card_id)] if st.arms_enabled and s.arms else "routed"
            n_cmds = db.scalar(select(func.count()).select_from(CommandRow).where(CommandRow.session_id == session_id)) or 0
            n_probes = db.scalar(select(func.count()).select_from(CommandRow).where(
                CommandRow.session_id == session_id, CommandRow.is_probe.is_(True))) or 0  # fmt: skip
            spent_s = db.scalar(select(func.coalesce(func.sum(CommandRow.cost_usd), 0.0)).where(
                CommandRow.session_id == session_id)) or 0.0  # fmt: skip
            midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            spent_d = db.scalar(select(func.coalesce(func.sum(CommandRow.cost_usd), 0.0)).where(
                CommandRow.created_at >= midnight)) or 0.0  # fmt: skip
        if n_cmds >= st.max_commands_per_session:
            return JSONResponse({"error": "session_limit"}, status_code=429)
        if spent_s >= st.session_cost_cap_usd or spent_d >= st.daily_cost_cap_usd:
            return JSONResponse({"error": "study_paused"}, status_code=503)

        card = cards[card_id]
        stage: dict[str, int] = {}
        inp = ModelInput()
        pre: PipelineResult | None = None
        if audio is not None:
            if base_mime(audio.content_type or client_audio_mime) not in ALLOWED_MIME:
                raise HTTPException(415, "unsupported_audio_type")
            data = await audio.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "audio_too_large")
            t = time.perf_counter()
            try:
                inp.wav = await to_wav16k(data)
            except AudioError as e:
                pre = tier_c(e.code)
            stage["transcode"] = int((time.perf_counter() - t) * 1000)
            del data
        elif st.dev and dev_transcript:
            try:
                ov = json.loads(dev_overrides) if dev_overrides else {}
                inp.dev = DevInput(transcript=dev_transcript[:300], **ov)
            except (TypeError, ValueError) as exc:
                raise HTTPException(400, "bad_dev_overrides") from exc
        else:
            raise HTTPException(400, "audio_required")

        if pre is None:
            try:  # hard server-side deadline so the participant never waits more than ~10 s
                pre = await asyncio.wait_for(run_pipeline(client, inp, contacts, card.ceiling_amount, st), 10)
            except TimeoutError:
                pre = tier_c("pipeline_timeout")
        res = pre
        res.stage_ms = {**stage, **res.stage_ms}
        latency = int((time.perf_counter() - t0) * 1000)
        cmd_id = str(uuid.uuid4())

        # ---- what the participant sees: UI mode, probe, shown values
        has_parse = bool(res.payee_id) and res.amount is not None and res.intent == "send_money" and bool(res.transcript)
        if arm == "always_confirm":
            mode = "confirm_all" if has_parse else "retry"
        else:
            mode = {"A": "fast", "B": "verify", "C": "retry"}[res.tier]
        shown_payee = res.payee_id if mode in ("fast", "confirm_all") else None
        shown_amount = res.amount if mode in ("fast", "confirm_all") else None
        is_probe, probe_type = False, None
        if (mode == "fast" and st.probes_enabled and not card.practice and n_probes < st.max_probes_per_session
                and shown_payee and shown_amount is not None):  # fmt: skip
            rnd = random.Random(cmd_id)
            if rnd.random() < st.probe_rate:
                probe_type, shown_payee, shown_amount = make_probe(shown_payee, shown_amount, groups, rnd)
                is_probe = True
        name_of = {c.payee_id: c.display_name for c in contacts}

        fields = None
        if mode in ("fast", "confirm_all"):
            fields = {"payee": {"id": shown_payee, "name": name_of[shown_payee or ""]}, "amount": shown_amount, "note": res.note}
        elif mode == "verify" and res.chips:
            unsure = res.chips["field"]
            fields = {
                "payee": None if unsure == "payee" or not res.payee_id else {"id": res.payee_id, "name": res.payee_name},
                "amount": None if unsure == "amount" else res.amount,
                "note": res.note,
            }  # fmt: skip
        chips = res.chips if mode == "verify" else None
        view: dict[str, Any] = {"cmd_id": cmd_id, "tier": res.tier, "mode": mode, "fields": fields, "chips": chips,
                                "latency_ms": latency}  # fmt: skip
        if st.dev:  # debug numbers only exist in dev
            view["debug"] = {"reasons": res.reasons, "flags": res.flags, "combined": res.combined, "arm": arm,
                             "agreement": res.agreement, "error_code": res.error_code, "probe": probe_type}  # fmt: skip

        with Db() as db:
            db.add(CommandRow(
                cmd_id=cmd_id, session_id=session_id, client_request_id=client_request_id, card_id=card_id,
                is_practice=card.practice, seq=n_cmds + 1, arm=arm, is_probe=is_probe, probe_type=probe_type,
                ui_mode=mode, shown_payee_id=shown_payee, shown_amount=shown_amount, audio_ms=audio_ms or None,
                transcript_roman=res.transcript, parsed_payee_id=res.payee_id, parsed_amount=res.amount,
                parsed_intent=res.intent, parsed_note=res.note, self_conf=res.self_conf, agreement=res.agreement,
                validator_flags=res.flags, validator_scores=res.scores, combined_conf=res.combined,
                router_version=st.router.router.version, route_tier=res.tier, route_reasons=res.reasons, chips=res.chips,
                model=client.name, prompt_version=st.prompt_version, app_version=st.app_version, stage_ms=res.stage_ms,
                latency_ms=latency, tokens_in=res.tokens_in, tokens_out=res.tokens_out, cost_usd=res.cost_usd,
                pricing_version=st.pricing.version if st.pricing else None, error_code=res.error_code,
                correct_payee=res.payee_id == card.truth_payee_id, correct_amount=res.amount == card.truth_amount,
                correct_intent=res.intent == card.truth_intent,
                correct_all=(res.payee_id == card.truth_payee_id and res.amount == card.truth_amount
                             and res.intent == card.truth_intent),
                response_json=view,
            ))  # fmt: skip
            for sm in res.samples:
                db.add(SampleRow(cmd_id=cmd_id, sample_idx=sm.idx, temperature=sm.temperature, raw_json=sm.raw,
                                 latency_ms=sm.latency_ms, tokens_in=sm.tokens_in, tokens_out=sm.tokens_out,
                                 status=sm.status))  # fmt: skip
            log(db, "command_routed", session_id, cmd_id, tier=res.tier, mode=mode, error_code=res.error_code,
                latency_ms=latency)
            db.commit()
        return view

    @app.post("/api/commands/{cmd_id}/action")
    def post_action(cmd_id: str, body: ActionIn) -> dict[str, bool]:
        with Db() as db:
            row = db.get(CommandRow, cmd_id)
            if row is None:
                raise HTTPException(404, "unknown_command")
            if row.user_action_final is not None:
                raise HTTPException(409, "already_actioned")
            card = cards[row.card_id]
            payee, amount, final = None, None, None
            if body.action == "pay":
                if row.ui_mode in ("fast", "confirm_all"):
                    payee, amount = row.shown_payee_id, row.shown_amount  # a probe is paid as shown (wrong on purpose)
                elif row.ui_mode == "verify":
                    payee, amount = row.parsed_payee_id, row.parsed_amount
                    opts = {o["value"] for o in (row.chips or {}).get("options", [])}
                    want = body.chip_value if body.chip_field == "payee" else (
                        int(body.chip_value) if body.chip_value is not None and body.chip_field == "amount" else None)
                    if row.chips is None or body.chip_field != row.chips["field"] or want not in opts:
                        raise HTTPException(409, "chip_required")
                    payee, amount = (want, amount) if body.chip_field == "payee" else (payee, want)
                else:
                    raise HTTPException(409, "cannot_pay_tier_c")
                final = "paid"
            elif body.action in ("manual", "edit"):
                if not body.final_payee_id or body.final_amount is None or body.final_payee_id not in {c.payee_id for c in contacts}:
                    raise HTTPException(422, "final_values_required")
                payee, amount = body.final_payee_id, body.final_amount
                final = "manual" if body.action == "manual" else "edited"
            elif body.action == "retry":
                final = "retried"
            else:
                final = "abandoned"
            row.user_action_final, row.final_payee_id, row.final_amount = final, payee, amount
            row.final_correct_all = (payee == card.truth_payee_id and amount == card.truth_amount) if payee else None
            row.chip_field = body.chip_field if body.action == "pay" else None
            row.taps_count, row.time_to_mic_ms = body.taps_count, body.time_to_mic_ms
            row.time_result_to_action_ms, row.time_to_complete_ms = body.time_result_to_action_ms, body.time_to_complete_ms
            log(db, "action", row.session_id, cmd_id, action=body.action, taps=body.taps_count)
            db.commit()
        return {"ok": True}  # correctness is never revealed to the participant

    # -------------------------------------------------- survey, events, deletion
    @app.post("/api/sessions/{session_id}/survey")
    def survey(session_id: str, body: SurveyIn) -> dict[str, bool]:
        with Db() as db:
            s = get_session(db, session_id)
            if db.get(SurveyRow, session_id) is not None:
                raise HTTPException(409, "already_submitted")
            db.add(SurveyRow(session_id=session_id, trust_amount=body.trust_amount, low_effort=body.low_effort,
                             would_use=body.would_use, free_text=body.free_text))  # fmt: skip
            s.status = "completed"
            log(db, "survey_submitted", session_id)
            db.commit()
        return {"ok": True}

    @app.post("/api/events")
    def client_event(body: EventIn) -> dict[str, bool]:
        if body.type not in CLIENT_EVENTS or len(json.dumps(body.payload)) > 500:
            raise HTTPException(422, "bad_event")
        with Db() as db:
            get_session(db, body.session_id)
            log(db, body.type, body.session_id, None, **body.payload)
            db.commit()
        return {"ok": True}

    @app.post("/api/sessions/{session_id}/delete")
    def delete_session(session_id: str, body: DeleteIn) -> dict[str, bool]:
        with Db() as db:
            s = get_session(db, session_id)
            if not hmac.compare_digest(s.deletion_code_hash, _sha(body.deletion_code.strip().upper())):
                raise HTTPException(403, "bad_deletion_code")
            db.execute(update(DeleteGateRow).where(DeleteGateRow.id == 1).values(allow=1))  # open the gate, same transaction
            cmd_ids = list(db.scalars(select(CommandRow.cmd_id).where(CommandRow.session_id == session_id)))
            if cmd_ids:
                db.execute(delete(SampleRow).where(SampleRow.cmd_id.in_(cmd_ids)))
            for model in (CommandRow, EventRow, SurveyRow):  # the one allowed exception to append-only
                db.execute(delete(model).where(model.session_id == session_id))
            db.execute(delete(SessionRow).where(SessionRow.session_id == session_id))
            db.add(DeletionRow(session_hash=_sha(session_id)))
            db.execute(update(DeleteGateRow).where(DeleteGateRow.id == 1).values(allow=0))
            db.commit()
        return {"deleted": True}

    app.include_router(build_admin_router(st, Db, cards))
    _ = timedelta  # reserved for the 24 h abandonment sweep
    return app
