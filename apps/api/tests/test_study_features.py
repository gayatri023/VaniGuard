import logging
import random
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import new_session, send
from vani.app import create_app
from vani.cards import assign_arms
from vani.db import CommandRow, SessionRow
from vani.pipeline.clients import FakeClient
from vani.probes import make_probe
from vani.ratelimit import RateLimiter

ADMIN = {"X-Admin-Token": "dev-admin-token"}


def make(settings, **kw):  # type: ignore[no-untyped-def]
    return TestClient(create_app(replace(settings, **kw), FakeClient(0)))


def session_rows(client, sid):  # type: ignore[no-untyped-def]
    with client.app.state.Db() as db:
        s = db.get(SessionRow, sid)
        return s.card_ids, s.arms


def good(client, card_id):  # type: ignore[no-untyped-def]
    c = client.app.state.cards[card_id]
    names = {"priya": "Priya", "amit": "Amit", "neha": "Neha", "vikram": "Vikram", "sneha": "Sneha", "papa": "Papa",
             "pooja": "Pooja", "sumit": "Sumit", "ankit": "Ankit", "ravi": "Ravi", "sunit": "Sunit",
             "rahul_sharma": "Rahul Sharma", "rahul_sethi": "Rahul Sethi", "rohit_sharma": "Rohit Sharma",
             "ravi_kumar": "Ravi Kumar", "mummy": "Mummy"}  # fmt: skip
    return f"{names[c.truth_payee_id]} ko {c.truth_amount} rupaye bhej do"


# --------------------------------------------------------------------- arms
def test_arms_are_balanced_permuted_blocks_and_deterministic() -> None:
    seen = set()
    for i in range(60):
        arms = assign_arms(random.Random(f"s{i}"), 8, True)
        assert arms[0] == "routed" and len(arms) == 9
        assert arms[1:].count("routed") == 4 and arms[1:].count("always_confirm") == 4
        assert arms[1:5].count("routed") == 2  # every block of 4 is balanced
        seen.add(tuple(arms))
        assert arms == assign_arms(random.Random(f"s{i}"), 8, True)
    assert len(seen) > 5  # genuinely randomised order
    assert set(assign_arms(random.Random(1), 8, False)) == {"routed"}


def test_arms_disabled_means_everyone_routed(c: TestClient) -> None:
    sid, _ = new_session(c)
    assert set(session_rows(c, sid)[1]) == {"routed"}


def test_always_confirm_arm_shows_full_parse_and_never_hides_fields(settings) -> None:  # type: ignore[no-untyped-def]
    cl = make(settings, arms_enabled=True)
    sid, _ = new_session(cl)
    ids, arms = session_rows(cl, sid)
    card = next(cid for cid, a in zip(ids, arms, strict=True) if a == "always_confirm")
    # a samples-disagree command would be Tier B in the routed arm; the baseline just shows the parse
    r = send(cl, sid, card, "Amit ko pandrah rupaye bhej do", {"sample_amounts": [15, 15, 50]}).json()
    assert r["tier"] == "B" and r["mode"] == "confirm_all" and r["chips"] is None
    assert r["fields"]["payee"]["id"] == "amit" and r["fields"]["amount"] == 15
    assert cl.post(f"/api/commands/{r['cmd_id']}/action", json={"action": "pay", "taps_count": 3}).status_code == 200
    with cl.app.state.Db() as db:
        row = db.scalar(select(CommandRow).where(CommandRow.cmd_id == r["cmd_id"]))
        assert row.arm == "always_confirm" and row.ui_mode == "confirm_all" and row.final_amount == 15
    nothing = send(cl, sid, card, "mujhe kuch samajh nahi aaya").json()
    assert nothing["mode"] == "retry" and nothing["fields"] is None
    assert cl.post(f"/api/commands/{nothing['cmd_id']}/action", json={"action": "pay"}).status_code == 409


def test_routed_arm_unchanged_when_arms_enabled(settings) -> None:  # type: ignore[no-untyped-def]
    cl = make(settings, arms_enabled=True)
    sid, _ = new_session(cl)
    ids, arms = session_rows(cl, sid)
    card = next(cid for cid, a in zip(ids, arms, strict=True) if a == "routed" and cid != "p0")
    r = send(cl, sid, card, "Priya ko bees rupaye bhej do").json()
    assert r["mode"] == "fast" and r["tier"] == "A"


# ------------------------------------------------------------------- probes
def test_make_probe_always_changes_exactly_one_field() -> None:
    groups = {"priya": "pp", "pooja": "pp", "neha": "other", "rahul_sharma": "rahul", "rahul_sethi": "rahul"}
    kinds = set()
    for i in range(200):
        for payee, amount in (("priya", 15), ("neha", 150), ("rahul_sharma", 50), ("priya", 2500), ("neha", 1)):
            kind, p2, a2 = make_probe(payee, amount, groups, random.Random(i))
            kinds.add(kind)
            assert (p2, a2) != (payee, amount) and a2 > 0
            assert (p2 != payee) != (a2 != amount)  # exactly one field differs
            if kind == "payee":
                assert groups[p2] == groups[payee]  # a plausible sibling, never a random stranger
    assert kinds == {"amount", "payee"}
    assert make_probe("priya", 15, groups, random.Random(3)) == make_probe("priya", 15, groups, random.Random(3))


def test_probe_is_shown_wrong_paid_as_wrong_and_excluded_from_accuracy(settings) -> None:  # type: ignore[no-untyped-def]
    cl = make(settings, probes_enabled=True, probe_rate=1.0)
    sid, _ = new_session(cl)
    ids, _ = session_rows(cl, sid)
    practice = send(cl, sid, ids[0], good(cl, ids[0])).json()
    assert practice["mode"] == "fast"
    with cl.app.state.Db() as db:
        assert db.scalar(select(CommandRow.is_probe).where(CommandRow.cmd_id == practice["cmd_id"])) is False  # never on practice
    r = send(cl, sid, ids[1], good(cl, ids[1])).json()
    assert r["tier"] == "A" and r["mode"] == "fast"
    truth = cl.app.state.cards[ids[1]]
    shown = (r["fields"]["payee"]["id"], r["fields"]["amount"])
    assert shown != (truth.truth_payee_id, truth.truth_amount)  # looks like a normal Tier A card, but is wrong
    assert cl.post(f"/api/commands/{r['cmd_id']}/action", json={"action": "pay", "taps_count": 1}).status_code == 200
    with cl.app.state.Db() as db:
        row = db.scalar(select(CommandRow).where(CommandRow.cmd_id == r["cmd_id"]))
        assert row.is_probe and row.probe_type in ("amount", "payee") and row.final_correct_all is False
        assert row.correct_all is True  # the model itself was right; only the display was seeded
    q = cl.get("/api/admin/quality", headers=ADMIN).json()
    assert q["n"] == 0  # practice + probe excluded from accuracy
    s = cl.get("/api/admin/summary", headers=ADMIN).json()
    assert s["commands"]["probes"] == 1 and s["commands"]["practice"] == 1


def test_probe_cap_per_session(settings) -> None:  # type: ignore[no-untyped-def]
    cl = make(settings, probes_enabled=True, probe_rate=1.0, max_probes_per_session=2)
    sid, _ = new_session(cl)
    ids, _ = session_rows(cl, sid)
    flags = [send(cl, sid, cid, good(cl, cid)).json() for cid in ids[1:5]]
    with cl.app.state.Db() as db:
        probes = [db.scalar(select(CommandRow.is_probe).where(CommandRow.cmd_id == f["cmd_id"])) for f in flags]
    assert probes == [True, True, False, False]


def test_config_endpoint(settings, c: TestClient) -> None:  # type: ignore[no-untyped-def]
    assert c.get("/api/config").json() == {"probes_enabled": False, "consent_version": "v2", "total_cards": 8}
    assert make(settings, probes_enabled=True).get("/api/config").json()["consent_version"] == "v2-probes"


# -------------------------------------------------- security and hygiene
def test_rate_limiter_unit() -> None:
    rl = RateLimiter(3, 60)
    assert [rl.allow("a", t) for t in (0, 1, 2, 3)] == [True, True, True, False]
    assert rl.allow("b", 3) and rl.allow("a", 61)  # other keys independent; window slides


def test_session_rate_limit_returns_429(settings) -> None:  # type: ignore[no-untyped-def]
    cl = make(settings, rate_per_session_per_min=3)
    sid, _ = new_session(cl)
    codes = [send(cl, sid, "p0", "Priya ko bees rupaye bhej do").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_security_headers(c: TestClient) -> None:
    h = c.get("/healthz").headers
    assert h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and "max-age" in h["strict-transport-security"]


def test_admin_requires_the_token(c: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    for path in ("summary", "quality", "risk-coverage", "calibration", "health", "export.csv"):
        assert c.get(f"/api/admin/{path}").status_code == 401
        assert c.get(f"/api/admin/{path}", headers={"X-Admin-Token": "nope"}).status_code == 401
        assert c.get(f"/api/admin/{path}", headers=ADMIN).status_code == 200
    assert c.get("/api/admin/summary?token=dev-admin-token").status_code == 401  # never accepted in the URL
    assert make(settings, admin_token=None).get("/api/admin/summary", headers=ADMIN).status_code == 503


def test_logs_never_contain_transcripts(c: TestClient, caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.DEBUG)
    sid, _ = new_session(c)
    send(c, sid, "p0", "Priya ko zebra-quartz-7391 rupaye bhej do")
    assert "zebra-quartz-7391" not in caplog.text


# ---------------------------------------------- dashboard numbers vs database
def test_dashboard_numbers_match_the_database(c: TestClient) -> None:
    sid, _ = new_session(c)
    ids, _ = session_rows(c, sid)
    cmds = []
    for cid in ids[1:8]:
        wrong = len(cmds) in (2, 5)  # two commands are misread by the model
        ov = {"amount_value": c.app.state.cards[cid].truth_amount + 7} if wrong else None
        cmds.append(send(c, sid, cid, good(c, cid), ov).json())
    assert [x["tier"] for x in cmds] == ["A", "A", "C", "A", "A", "C", "A"]

    q = c.get("/api/admin/quality", headers=ADMIN).json()
    assert q["n"] == 7 and q["fields"]["all"]["k"] == 5 and q["fields"]["all"]["n"] == 7
    assert q["fields"]["all"]["lo"] < 5 / 7 < q["fields"]["all"]["hi"]
    rc = c.get("/api/admin/risk-coverage", headers=ADMIN).json()
    live = next(p for p in rc["curve"] if p["threshold"] == 0.0)
    assert (live["n_fast"], live["n_wrong"], live["n_total"]) == (5, 0, 7)  # slider at 0 == the live router
    assert live["safe_fast_rate"] == pytest.approx(5 / 7) and live["reliable"] is False
    stricter = next(p for p in rc["curve"] if p["threshold"] == 0.1)
    assert stricter["n_fast"] <= live["n_fast"]
    cal = c.get("/api/admin/calibration", headers=ADMIN).json()
    assert cal["signals"]["amount.combined"]["n"] == 7  # misreads are Tier C via a hard flag but still carry confidences
    assert c.get("/api/admin/export.csv", headers=ADMIN).text.splitlines()[0].count("ui_mode") == 1
    h = c.get("/api/admin/health", headers=ADMIN).json()
    assert h["duplicate_requests"] == 0 and h["versions_seen"]["model"] == {"dev-simulator": 7}


def test_cors_only_allows_listed_origins(c: TestClient) -> None:
    ok = c.options("/api/sessions", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    bad = c.options("/api/sessions", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers


def test_rate_limiter_stores_hashed_keys_only() -> None:
    rl = RateLimiter(5, 60)
    rl.allow("203.0.113.77")
    assert all("203.0.113" not in k for k in rl._hits)  # raw IPs are never held, only salted hashes


def test_session_command_limit_returns_429(settings) -> None:  # type: ignore[no-untyped-def]
    cl = make(settings, max_commands_per_session=2)
    sid, _ = new_session(cl)
    codes = [send(cl, sid, "p0", "Priya ko bees rupaye bhej do") for _ in range(3)]
    assert [r.status_code for r in codes] == [200, 200, 429] and codes[2].json()["error"] == "session_limit"
