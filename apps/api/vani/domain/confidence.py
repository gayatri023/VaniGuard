"""Per-field confidence combination. Pure functions.

`Combiner` is the seam: v1 is a weighted sum with placeholder weights from
config/router.yaml; v2 can swap in a learned model without touching the router.
Anything missing or non-finite counts as 0.0 (fail safe).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FieldFeatures:
    self_conf: float | None
    agreement: float | None
    validator_score: float | None


def _clean(x: float | None) -> float:
    if x is None or not math.isfinite(x):
        return 0.0
    return min(1.0, max(0.0, x))


def agreement_rate(values: Sequence[Hashable | None]) -> float:
    """Share of samples that match the plurality value. None never agrees.

    Fewer than two samples cannot show agreement, so returns 0.0.
    """
    n = len(values)
    if n < 2:
        return 0.0
    counts = Counter(v for v in values if v is not None)
    return max(counts.values()) / n if counts else 0.0


class Combiner(Protocol):
    def combine(self, field: str, f: FieldFeatures) -> float: ...


@dataclass(frozen=True)
class WeightedSumCombiner:
    w_self: float
    w_agreement: float
    w_validator: float

    def __post_init__(self) -> None:
        if min(self.w_self, self.w_agreement, self.w_validator) < 0 or self.total() <= 0:
            raise ValueError("weights must be non-negative and not all zero")

    def total(self) -> float:
        return self.w_self + self.w_agreement + self.w_validator

    def combine(self, field: str, f: FieldFeatures) -> float:
        s = (
            self.w_self * _clean(f.self_conf)
            + self.w_agreement * _clean(f.agreement)
            + self.w_validator * _clean(f.validator_score)
        )
        return s / self.total()
