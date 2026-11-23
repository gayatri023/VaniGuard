"""Three-tier router. Pure functions, fail-safe.

A: fast path (one tap). B: targeted verify (chips). C: retry / manual.
Tier A is returned ONLY when every field has a valid confidence at or above its
threshold and no hard flag is set. Any error or odd input returns Tier C.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum

FIELDS = ("payee", "amount", "intent")
CHIP_FIELDS = ("payee", "amount")


class Tier(str, Enum):
    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True)
class FieldInput:
    conf: float | None
    candidates: tuple[str, ...] = ()  # display strings for chips, best first


@dataclass(frozen=True)
class RouterInput:
    payee: FieldInput
    amount: FieldInput
    intent: FieldInput
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RouterConfig:
    version: str
    thresholds: Mapping[str, float]
    hard_flags: frozenset[str]
    max_chips: int = 3

    def __post_init__(self) -> None:
        missing = [f for f in FIELDS if f not in self.thresholds]
        if missing:
            raise ValueError(f"missing thresholds for {missing}")
        if any(not (0.0 <= t <= 1.0) for t in self.thresholds.values()):
            raise ValueError("thresholds must be in [0, 1]")
        if self.max_chips < 2:
            raise ValueError("max_chips must be at least 2")


@dataclass(frozen=True)
class RouteDecision:
    tier: Tier
    reasons: tuple[str, ...]
    chips: tuple[str, ...] = ()
    uncertain_fields: tuple[str, ...] = ()


def _valid(conf: float | None) -> bool:
    return conf is not None and math.isfinite(conf) and 0.0 <= conf <= 1.0


def _tier_c(*reasons: str, uncertain: tuple[str, ...] = ()) -> RouteDecision:
    return RouteDecision(Tier.C, tuple(reasons), (), uncertain)


def route(inp: RouterInput, cfg: RouterConfig) -> RouteDecision:
    try:
        return _route(inp, cfg)
    except Exception:  # noqa: BLE001 - fail safe on anything unexpected
        return _tier_c("router_error")


def _route(inp: RouterInput, cfg: RouterConfig) -> RouteDecision:
    fields = {"payee": inp.payee, "amount": inp.amount, "intent": inp.intent}
    bad = tuple(f for f in FIELDS if not _valid(fields[f].conf))
    if bad:
        return _tier_c(*(f"invalid_conf:{f}" for f in bad), uncertain=bad)

    hard = sorted(inp.flags & cfg.hard_flags)
    uncertain = tuple(
        f for f in FIELDS if fields[f].conf is not None and fields[f].conf < cfg.thresholds[f]  # type: ignore[operator]
    )
    if hard:
        return _tier_c(*(f"hard_flag:{h}" for h in hard), uncertain=uncertain)
    if not uncertain:
        return RouteDecision(Tier.A, ("all_fields_confident",))

    if len(uncertain) == 1 and uncertain[0] in CHIP_FIELDS:
        field = uncertain[0]
        chips = tuple(dict.fromkeys(c for c in fields[field].candidates if c))
        if 2 <= len(chips) <= cfg.max_chips:
            return RouteDecision(Tier.B, (f"verify:{field}",), chips, uncertain)
        return _tier_c(f"uncertain:{field}", f"chips:{len(chips)}", uncertain=uncertain)

    return _tier_c(*(f"uncertain:{f}" for f in uncertain), uncertain=uncertain)


HARD_FLAG_SCORE = -2.0  # strictly below any real margin (margins are >= -1)


def margin_score(conf: Mapping[str, float | None], cfg: RouterConfig, flags: Collection[str]) -> float:
    """Command-level score for threshold sweeps and replay.

    min over fields of (confidence - threshold). A hard flag or an invalid confidence gives
    HARD_FLAG_SCORE (never fast path). Tier A  <=>  margin_score >= 0, so sweeping a uniform
    offset delta (fast path iff score >= delta) keeps the per-field asymmetry of the live router.
    """
    if set(flags) & cfg.hard_flags:
        return HARD_FLAG_SCORE
    margins = []
    for f in FIELDS:
        c = conf.get(f)
        if not _valid(c):
            return HARD_FLAG_SCORE
        margins.append(c - cfg.thresholds[f])  # type: ignore[operator]
    return min(margins)
