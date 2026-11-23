from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from tests.conftest import new_session, send
from vani.db import Base, install_guards

API = Path(__file__).resolve().parents[1]


def alembic_cfg() -> Config:
    cfg = Config(str(API / "alembic.ini"))
    cfg.set_main_option("script_location", str(API / "migrations"))
    return cfg


def test_events_cannot_be_updated_or_deleted_directly(c: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    sid, _ = new_session(c)
    send(c, sid, "p0", "Priya ko bees rupaye bhej do")
    eng = app.state.Db.kw["bind"]
    with eng.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("UPDATE events SET type = 'tampered'"))
    with eng.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("DELETE FROM events"))
    with eng.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM events")).scalar() >= 2  # untouched
        conn.execute(text("INSERT INTO events (ts, session_id, type, payload, app_version) VALUES (CURRENT_TIMESTAMP, 'x', 'ok', '{}', 'v')"))  # INSERT still fine


def test_deletion_route_is_the_only_delete_and_closes_the_gate(c: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    sid, code = new_session(c)
    send(c, sid, "p0", "Priya ko bees rupaye bhej do")
    assert c.post(f"/api/sessions/{sid}/delete", json={"deletion_code": code}).status_code == 200
    eng = app.state.Db.kw["bind"]
    with eng.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM events WHERE session_id = :s"), {"s": sid}).scalar() == 0
        assert conn.execute(text("SELECT allow FROM delete_gate WHERE id = 1")).scalar() == 0
    other, _ = new_session(c)  # another participant's events must still be protected
    with eng.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("DELETE FROM events WHERE session_id = :s"), {"s": other})  # gate is shut again


def test_a_wrong_deletion_code_leaves_everything_in_place(c: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    sid, _ = new_session(c)
    send(c, sid, "p0", "Priya ko bees rupaye bhej do")
    assert c.post(f"/api/sessions/{sid}/delete", json={"deletion_code": "NOPE"}).status_code == 403
    with app.state.Db.kw["bind"].begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM events WHERE session_id = :s"), {"s": sid}).scalar() >= 2
        assert conn.execute(text("SELECT allow FROM delete_gate WHERE id = 1")).scalar() == 0


def test_migrations_build_exactly_the_model_schema(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    url = f"sqlite:///{tmp_path}/m.db"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(alembic_cfg(), "head")
    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        assert {c["name"] for c in insp.get_columns(name)} == {c.name for c in table.columns}, name
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO events (ts, session_id, type, payload, app_version) VALUES (CURRENT_TIMESTAMP, 's', 't', '{}', 'v')"))
    with eng.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("UPDATE events SET type = 'x'"))  # guards came from migration 0002
    with eng.begin() as conn:
        assert conn.execute(text("SELECT allow FROM delete_gate WHERE id = 1")).scalar() == 0
    command.downgrade(alembic_cfg(), "0001")
    with eng.begin() as conn:  # guards removed by the downgrade; no trigger, so UPDATE is allowed again
        conn.execute(text("UPDATE events SET type = 'x'"))


def test_install_guards_is_idempotent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    eng = create_engine(f"sqlite:///{tmp_path}/g.db")
    Base.metadata.create_all(eng)
    install_guards(eng)
    install_guards(eng)
    with eng.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM delete_gate")).scalar() == 1
