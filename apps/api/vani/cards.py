"""Scenario cards and contacts. Ground truth stays on the server."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from .domain.payee import Contact

CONFIG_DIR_CARDS = Path(__file__).resolve().parents[3] / "config" / "cards"
QUOTAS = {"easy": 2, "medium": 3, "hard": 3}  # 8 main cards per participant


@dataclass(frozen=True)
class Card:
    card_id: str
    difficulty: str
    condition_tags: tuple[str, ...]
    scenario_text: str
    truth_payee_id: str
    truth_amount: int
    truth_intent: str
    truth_note: str
    ceiling_amount: int
    practice: bool = False


def load_contacts(path: Path) -> list[Contact]:
    return [
        Contact(c["payee_id"], c["display_name"], tuple(c.get("aliases") or ()), c.get("devanagari_name"))
        for c in yaml.safe_load(path.read_text())
    ]


def load_cards(path: Path, contacts: list[Contact]) -> list[Card]:
    ids = {c.payee_id for c in contacts}
    cards = []
    for c in yaml.safe_load(path.read_text()):
        if c["truth_payee_id"] not in ids:
            raise ValueError(f"card {c['card_id']}: unknown payee {c['truth_payee_id']}")
        cards.append(
            Card(
                c["card_id"], c["difficulty"], tuple(c["condition_tags"]), c["scenario_text"],
                c["truth_payee_id"], int(c["truth_amount"]), c.get("truth_intent", "send_money"),
                str(c.get("truth_note", "")), int(c["ceiling_amount"]), bool(c.get("practice", False)),
            )
        )  # fmt: skip
    return cards


def assign_cards(cards: list[Card], served: Mapping[str, int], rng: random.Random) -> list[str]:
    """Practice card first, then 8 main cards: 2 easy, 3 medium, 3 hard, least-served first,
    no repeats, shuffled so difficulty does not track position."""
    practice = [c.card_id for c in cards if c.practice]
    chosen: list[str] = []
    for diff, k in QUOTAS.items():
        pool = [c for c in cards if c.difficulty == diff and not c.practice]
        if len(pool) < k:
            raise ValueError(f"pool has only {len(pool)} '{diff}' cards, need {k}")
        pool.sort(key=lambda c: (served.get(c.card_id, 0), rng.random()))
        chosen += [c.card_id for c in pool[:k]]
    rng.shuffle(chosen)
    return practice[:1] + chosen


def load_groups(path: Path) -> dict[str, str]:
    return {c["payee_id"]: c.get("group_tag", "other") for c in yaml.safe_load(path.read_text())}


def assign_arms(rng: random.Random, n_main: int = 8, enabled: bool = True) -> list[str]:
    """Arm per card, aligned with assign_cards (practice first, always routed).
    Permuted blocks of 4 (2 routed + 2 always_confirm) so every participant is balanced."""
    if not enabled:
        return ["routed"] * (n_main + 1)
    arms: list[str] = []
    while len(arms) < n_main:
        block = ["routed", "routed", "always_confirm", "always_confirm"]
        rng.shuffle(block)
        arms += block
    return ["routed", *arms[:n_main]]
