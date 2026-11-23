"""Field-level validators. Pure functions.

Flags are named for the PROBLEM they report (raised when the problem occurs), so
`amount_mismatch_transcript` means the model's amount disagrees with the number
words in the transcript.
"""

from __future__ import annotations

from dataclasses import dataclass

from .numbers import is_confusable, parse_amounts
from .payee import PayeeMatch

SEND_MONEY = "send_money"


@dataclass(frozen=True)
class ValidatorResult:
    payee_score: float
    amount_score: float
    intent_score: float
    flags: frozenset[str]


def validate(
    *,
    transcript: str,
    amount_text: str | None,
    amount_value: int | None,
    intent: str | None,
    speech_detected: bool,
    payee_text: str,
    payee_match: PayeeMatch,
    ceiling: int,
    confusable_penalty: float = 0.15,
) -> ValidatorResult:
    flags: set[str] = set()

    if not speech_detected or len(transcript.strip()) < 3:
        flags.add("empty_or_short_transcript")

    # intent
    intent_score = 1.0 if intent == SEND_MONEY else 0.0
    if intent != SEND_MONEY:
        flags.add("intent_not_send_money")

    # amount
    amount_score = 0.0
    if amount_value is not None and amount_value > 0:
        source = amount_text or transcript
        cands = parse_amounts(source, ignore=payee_text) or parse_amounts(
            transcript, ignore=payee_text
        )
        if not cands:
            amount_score = 0.3  # cannot cross-check; soft, not a contradiction
        elif cands[0].value != amount_value:
            flags.add("amount_mismatch_transcript")
        else:
            rivals = [c for c in cands[1:] if c.confidence >= cands[0].confidence - 0.3]
            amount_score = 0.8 if rivals else 1.0
        if is_confusable(amount_value):
            flags.add("amount_in_confusable_pair")
            amount_score = max(0.0, amount_score - confusable_penalty)
        if amount_value > ceiling:
            flags.add("amount_over_ceiling")
            amount_score = 0.0
    if "amount_mismatch_transcript" in flags:
        amount_score = 0.0

    # payee
    payee_score = payee_match.candidates[0].score if payee_match.candidates else 0.0
    if payee_match.ambiguous:
        flags.add("payee_margin_low")
        payee_score = min(payee_score, 0.5)
    if payee_match.n_exact > 1:
        flags.add("payee_alias_ambiguous")

    return ValidatorResult(payee_score, amount_score, intent_score, frozenset(flags))
