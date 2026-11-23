"""Seeded-error probes (H3): a deliberately wrong amount or payee shown in the fast-path card."""

from __future__ import annotations

import random
from collections.abc import Mapping

from .domain.numbers import confusable_partner


def make_probe(
    payee_id: str, amount: int, groups: Mapping[str, str], rng: random.Random
) -> tuple[str, str, int]:
    """Return (probe_type, shown_payee_id, shown_amount) with exactly one field made wrong."""
    siblings = sorted(p for p, g in groups.items() if g == groups.get(payee_id) and p != payee_id and g != "other")
    kinds = ["amount"] + (["payee"] if siblings else [])
    kind = rng.choice(kinds)
    if kind == "payee":
        return "payee", rng.choice(siblings), amount
    alt = confusable_partner(amount)
    if alt is None or alt == amount:
        alt = amount * 10 if amount < 1000 else amount // 10
    return "amount", payee_id, max(1, alt)
