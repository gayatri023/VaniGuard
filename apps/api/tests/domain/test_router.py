import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vani.domain.router import FieldInput, RouterConfig, RouterInput, Tier, margin_score, route

HARD = frozenset({"amount_over_ceiling", "amount_mismatch_transcript",
                  "intent_not_send_money", "empty_or_short_transcript"})  # fmt: skip
CFG = RouterConfig("test", {"amount": 0.90, "payee": 0.85, "intent": 0.80}, HARD)


def inp(p: float | None, a: float | None, i: float | None, flags: frozenset[str] = frozenset(),
        pc: tuple[str, ...] = (), ac: tuple[str, ...] = ()) -> RouterInput:  # fmt: skip
    return RouterInput(FieldInput(p, pc), FieldInput(a, ac), FieldInput(i), flags)


def test_tier_a_when_everything_confident() -> None:
    assert route(inp(0.95, 0.95, 0.95), CFG).tier is Tier.A


def test_threshold_is_inclusive() -> None:
    assert route(inp(0.85, 0.90, 0.80), CFG).tier is Tier.A
    assert route(inp(0.85, 0.8999, 0.80), CFG).tier is not Tier.A


def test_tier_b_amount_chips() -> None:
    d = route(inp(0.95, 0.6, 0.95, ac=("₹15", "₹50")), CFG)
    assert d.tier is Tier.B and d.chips == ("₹15", "₹50") and d.uncertain_fields == ("amount",)


def test_tier_b_payee_chips_dedupe() -> None:
    d = route(inp(0.5, 0.95, 0.95, pc=("Rahul Sharma", "Rahul Sethi", "Rahul Sharma")), CFG)
    assert d.tier is Tier.B and d.chips == ("Rahul Sharma", "Rahul Sethi")


def test_tier_c_when_chips_missing_or_too_many() -> None:
    assert route(inp(0.95, 0.6, 0.95, ac=("₹15",)), CFG).tier is Tier.C
    assert route(inp(0.95, 0.6, 0.95, ac=("1", "2", "3", "4")), CFG).tier is Tier.C


def test_tier_c_two_uncertain_or_intent_uncertain() -> None:
    assert route(inp(0.5, 0.5, 0.95, pc=("a", "b"), ac=("1", "2")), CFG).tier is Tier.C
    assert route(inp(0.95, 0.95, 0.5), CFG).tier is Tier.C


def test_hard_flag_beats_everything() -> None:
    d = route(inp(0.99, 0.99, 0.99, frozenset({"amount_over_ceiling"})), CFG)
    assert d.tier is Tier.C
    d = route(inp(0.99, 0.5, 0.99, frozenset({"amount_over_ceiling"}), ac=("1", "2")), CFG)
    assert d.tier is Tier.C


def test_missing_nan_or_out_of_range_confidence_is_tier_c() -> None:
    for bad in (None, math.nan, math.inf, -0.1, 1.1):
        assert route(inp(bad, 0.95, 0.95), CFG).tier is Tier.C
        assert route(inp(0.95, bad, 0.95), CFG).tier is Tier.C
        assert route(inp(0.95, 0.95, bad), CFG).tier is Tier.C


def test_exception_fails_safe() -> None:
    assert route(None, CFG).tier is Tier.C  # type: ignore[arg-type]


conf = st.one_of(st.none(), st.floats(allow_nan=True, allow_infinity=True), st.floats(0, 1))
flags = st.frozensets(st.sampled_from(sorted(HARD) + ["amount_in_confusable_pair", "payee_margin_low"]))
cands = st.lists(st.sampled_from(["a", "b", "c", "d", ""]), max_size=5).map(tuple)


@given(conf, conf, conf, flags, cands, cands)
def test_property_tier_a_never_with_hard_flag_or_bad_input(p, a, i, fl, pc, ac) -> None:  # type: ignore[no-untyped-def]
    d = route(inp(p, a, i, fl, pc, ac), CFG)
    if d.tier is Tier.A:
        assert not (fl & HARD)
        for c, t in ((p, 0.85), (a, 0.90), (i, 0.80)):
            assert c is not None and math.isfinite(c) and t <= c <= 1.0
    if d.tier is Tier.B:
        assert 2 <= len(d.chips) <= 3 and len(d.uncertain_fields) == 1


def test_margin_score_matches_router_exactly() -> None:
    thr = {"payee": 0.85, "amount": 0.90, "intent": 0.80}
    assert margin_score({"payee": 0.95, "amount": 0.92, "intent": 0.9}, CFG, set()) == pytest.approx(0.02)
    assert margin_score({"payee": 0.95, "amount": 0.92, "intent": 0.9}, CFG, {"amount_over_ceiling"}) < -1
    assert margin_score({"payee": None, "amount": 0.92, "intent": 0.9}, CFG, set()) < -1
    assert thr["amount"] == CFG.thresholds["amount"]


@given(conf, conf, conf, flags)
def test_property_tier_a_iff_margin_nonnegative(p, a, i, fl) -> None:  # type: ignore[no-untyped-def]
    d = route(inp(p, a, i, fl), CFG)
    m = margin_score({"payee": p, "amount": a, "intent": i}, CFG, fl)
    assert (d.tier is Tier.A) == (m >= 0)
