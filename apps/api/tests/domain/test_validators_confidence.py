import math
from pathlib import Path

import pytest

from vani.config import load_settings
from vani.domain.confidence import FieldFeatures, WeightedSumCombiner, agreement_rate
from vani.domain.payee import Contact, rank_payees
from vani.domain.validators import validate

CONTACTS = [Contact("rahul_sharma", "Rahul Sharma"), Contact("rahul_sethi", "Rahul Sethi"),
            Contact("priya", "Priya")]  # fmt: skip


def run(transcript: str, amount_text: str | None, amount: int | None, payee: str = "Priya",
        intent: str = "send_money", ceiling: int = 500, speech: bool = True):  # type: ignore[no-untyped-def]  # fmt: skip
    return validate(transcript=transcript, amount_text=amount_text, amount_value=amount,
                    intent=intent, speech_detected=speech, payee_text=payee,
                    payee_match=rank_payees(payee, CONTACTS), ceiling=ceiling)  # fmt: skip


def test_clean_command_has_no_flags_and_full_scores() -> None:
    r = run("Priya ko dedh sau rupaye bhej do", "dedh sau", 150)
    assert r.flags == frozenset() and r.amount_score == 1.0 and r.intent_score == 1.0
    assert r.payee_score > 0.9


def test_model_amount_contradicting_transcript_is_flagged() -> None:
    r = run("Priya ko pandrah rupaye bhej do", "pandrah", 50)
    assert "amount_mismatch_transcript" in r.flags and r.amount_score == 0.0


def test_confusable_amount_is_soft_penalty_not_hard_flag() -> None:
    r = run("Priya ko pandrah rupaye bhej do", "pandrah", 15)
    assert "amount_in_confusable_pair" in r.flags
    assert r.amount_score == pytest.approx(0.85)


def test_over_ceiling_intent_and_empty_flags() -> None:
    assert "amount_over_ceiling" in run("Priya ko pachaas hazaar", "pachaas hazaar", 50000).flags
    assert "intent_not_send_money" in run("Priya ko pachaas", "pachaas", 50, intent="other").flags
    assert "empty_or_short_transcript" in run("", None, None, speech=False).flags


def test_ambiguous_payee_caps_payee_score() -> None:
    r = run("Rahul ko pachaas rupaye", "pachaas", 50, payee="Rahul")
    assert "payee_margin_low" in r.flags and r.payee_score <= 0.5


def test_missing_amount_scores_zero() -> None:
    assert run("Priya ko kuch bhej do", None, None).amount_score == 0.0


def test_agreement_rate() -> None:
    assert agreement_rate([50, 50, 50]) == 1.0
    assert agreement_rate([50, 50, 15]) == pytest.approx(2 / 3)
    assert agreement_rate([50, None, 15]) == pytest.approx(1 / 3)
    assert agreement_rate([None, None, None]) == 0.0
    assert agreement_rate([50]) == 0.0 and agreement_rate([]) == 0.0


def test_weighted_sum_and_fail_safe() -> None:
    c = WeightedSumCombiner(0.3, 0.4, 0.3)
    assert c.combine("amount", FieldFeatures(1.0, 1.0, 1.0)) == pytest.approx(1.0)
    assert c.combine("amount", FieldFeatures(0.5, 1.0, 0.0)) == pytest.approx(0.55)
    assert c.combine("amount", FieldFeatures(None, math.nan, None)) == 0.0
    assert c.combine("amount", FieldFeatures(9.0, 9.0, 9.0)) == pytest.approx(1.0)  # clamped
    with pytest.raises(ValueError):
        WeightedSumCombiner(0, 0, 0)


def test_repo_config_loads() -> None:
    s = load_settings(Path(__file__).parents[4] / "config" / "router.yaml")
    assert s.router.thresholds["amount"] == 0.90 and "amount_over_ceiling" in s.router.hard_flags
    assert s.router.version.startswith("v1")
