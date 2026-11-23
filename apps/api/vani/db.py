"""Database models. Events are append-only by convention: the only DELETE path is the
participant deletion route (enforced by DB role later, see docs/DECISIONS.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)  # naive UTC, consistent on SQLite and Postgres


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    consent_version: Mapped[str] = mapped_column(String(32))
    consent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    language_comfort: Mapped[str] = mapped_column(String(24))
    noise_self_report: Mapped[str] = mapped_column(String(24))
    device_class: Mapped[str | None] = mapped_column(String(24), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(48), nullable=True)
    os: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    deletion_code_hash: Mapped[str] = mapped_column(String(64))
    card_ids: Mapped[list[str]] = mapped_column(JSON)
    arms: Mapped[list[str]] = mapped_column(JSON, default=list)


class CommandRow(Base):
    __tablename__ = "commands"
    cmd_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    client_request_id: Mapped[str] = mapped_column(String(64))
    card_id: Mapped[str] = mapped_column(String(16))
    is_practice: Mapped[bool] = mapped_column(Boolean, default=False)
    seq: Mapped[int] = mapped_column(Integer)
    arm: Mapped[str] = mapped_column(String(16), default="routed")
    is_probe: Mapped[bool] = mapped_column(Boolean, default=False)
    probe_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ui_mode: Mapped[str] = mapped_column(String(16), default="retry")
    shown_payee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shown_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    audio_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript_roman: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_payee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parsed_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_intent: Mapped[str | None] = mapped_column(String(16), nullable=True)
    parsed_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_conf: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agreement: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validator_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    validator_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    combined_conf: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    router_version: Mapped[str] = mapped_column(String(48))
    route_tier: Mapped[str] = mapped_column(String(1))
    route_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    chips: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    app_version: Mapped[str] = mapped_column(String(32))
    stage_ms: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pricing_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    # ground-truth comparisons, computed server-side from card truth only
    correct_payee: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    correct_amount: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    correct_intent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    correct_all: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # what the participant did
    user_action_final: Mapped[str | None] = mapped_column(String(16), nullable=True)
    final_payee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_correct_all: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    chip_field: Mapped[str | None] = mapped_column(String(8), nullable=True)
    taps_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_mic_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_result_to_action_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_complete_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SampleRow(Base):
    __tablename__ = "samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cmd_id: Mapped[str] = mapped_column(String(36), index=True)
    sample_idx: Mapped[int] = mapped_column(Integer)
    temperature: Mapped[float] = mapped_column(Float)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32))


class EventRow(Base):
    __tablename__ = "events"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    cmd_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    app_version: Mapped[str] = mapped_column(String(32))


class SurveyRow(Base):
    __tablename__ = "surveys"
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trust_amount: Mapped[int] = mapped_column(Integer)
    low_effort: Mapped[int] = mapped_column(Integer)
    would_use: Mapped[int] = mapped_column(Integer)
    free_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DeletionRow(Base):
    __tablename__ = "deletions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_hash: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def make_engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kwargs)


class DeleteGateRow(Base):
    """One row. 1 only inside the participant-deletion transaction, which is the single allowed DELETE on events."""

    __tablename__ = "delete_gate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allow: Mapped[int] = mapped_column(Integer, default=0)


def guard_statements(dialect: str) -> list[str]:
    """DDL that makes the events table append-only in the database itself: no UPDATE ever, no DELETE
    unless the deletion route has opened the gate in the same transaction."""
    if dialect == "postgresql":
        func = (
            "CREATE OR REPLACE FUNCTION vani_events_guard() RETURNS trigger AS $$ BEGIN "
            "IF TG_OP = 'UPDATE' THEN RAISE EXCEPTION 'events are append-only'; END IF; "
            "IF TG_OP = 'DELETE' AND COALESCE((SELECT allow FROM delete_gate WHERE id = 1), 0) <> 1 "
            "THEN RAISE EXCEPTION 'events are append-only'; END IF; RETURN OLD; END; $$ LANGUAGE plpgsql"
        )
        trigger = "CREATE TRIGGER events_guard BEFORE UPDATE OR DELETE ON events FOR EACH ROW EXECUTE FUNCTION vani_events_guard()"
        return [func, "DROP TRIGGER IF EXISTS events_guard ON events", trigger]
    no_update = (
        "CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events "
        "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END"
    )
    no_delete = (
        "CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events "
        "WHEN (SELECT allow FROM delete_gate WHERE id = 1) IS NOT 1 "
        "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END"
    )
    return [no_update, no_delete]


def install_guards(engine: Engine) -> None:
    with engine.begin() as conn:
        if conn.execute(text("SELECT COUNT(*) FROM delete_gate")).scalar() == 0:
            conn.execute(text("INSERT INTO delete_gate (id, allow) VALUES (1, 0)"))
        for stmt in guard_statements(engine.dialect.name):
            conn.execute(text(stmt))
