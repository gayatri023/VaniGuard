"""Config loading (I/O lives here, not in domain/)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .domain.confidence import WeightedSumCombiner
from .domain.router import RouterConfig


@dataclass(frozen=True)
class Settings:
    router: RouterConfig
    combiner: WeightedSumCombiner
    payee_ambiguity_delta: float
    confusable_penalty: float


def load_settings(path: str | Path) -> Settings:
    raw = yaml.safe_load(Path(path).read_text())
    w = raw["weights"]
    return Settings(
        router=RouterConfig(
            version=str(raw["router_version"]),
            thresholds={k: float(v) for k, v in raw["thresholds"].items()},
            hard_flags=frozenset(raw["hard_flags"]),
            max_chips=int(raw["max_chips"]),
        ),
        combiner=WeightedSumCombiner(
            float(w["self_conf"]), float(w["agreement"]), float(w["validator"])
        ),
        payee_ambiguity_delta=float(raw["payee_ambiguity_delta"]),
        confusable_penalty=float(raw["confusable_penalty"]),
    )
