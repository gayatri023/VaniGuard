"""Evaluation metrics. Pure numpy, no I/O. Every function is unit-tested."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

MIN_RELIABLE_N = 30


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # float error can leave the bounds a hair on the wrong side of p (e.g. lower = 1e-17 when k = 0); the interval always contains p
    return (min(max(0.0, centre - half), p), max(min(1.0, centre + half), p))


def brier(probs: ArrayLike, labels: ArrayLike) -> float:
    p = np.asarray(probs, dtype=float)
    y = np.asarray(labels, dtype=float)
    return float(np.mean((p - y) ** 2))


def ece(probs: ArrayLike, labels: ArrayLike, bins: int = 10) -> float:
    p = np.asarray(probs, dtype=float)
    y = np.asarray(labels, dtype=float)
    if p.size == 0:
        return float("nan")
    idx = np.minimum((p * bins).astype(int), bins - 1)  # p == 1.0 goes in the last bin
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.sum() / p.size * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(total)


def _rankdata(a: NDArray[np.float64]) -> NDArray[np.float64]:
    order = np.argsort(a, kind="mergesort")
    s = a[order]
    ranks = np.empty(len(a), dtype=float)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def auroc(scores: ArrayLike, labels: ArrayLike) -> float:
    """P(score of a correct item > score of a wrong item); ties count half."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=float) > 0.5
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    r = _rankdata(s)
    return float((r[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def bootstrap_ci(
    stat: Callable[[NDArray[np.intp]], float],
    groups: ArrayLike,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Participant-grouped bootstrap. `stat` receives row indices into the data.

    Whole groups are resampled with replacement so one person's rows stay together.
    Returns (point estimate, lo, hi). NaN resamples are dropped.
    """
    g = np.asarray(groups)
    uniq = np.unique(g)
    members = {u: np.flatnonzero(g == u) for u in uniq}
    point = stat(np.arange(len(g)))
    rng = np.random.default_rng(seed)
    vals: list[float] = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        v = stat(np.concatenate([members[u] for u in pick]))
        if math.isfinite(v):
            vals.append(v)
    if not vals:
        return (point, float("nan"), float("nan"))
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (point, float(lo), float(hi))


@dataclass(frozen=True)
class RCPoint:
    threshold: float
    n_total: int
    n_fast: int
    coverage: float  # fast / total
    n_wrong: int
    wrong_rate: float  # wrong fast / fast (nan if no fast)
    wilson_lo: float
    wilson_hi: float
    safe_fast_rate: float  # (fast and correct) / total  -- the north-star metric
    reliable: bool  # n_fast >= MIN_RELIABLE_N


def risk_coverage_curve(
    conf: ArrayLike, correct: ArrayLike, thresholds: Sequence[float]
) -> list[RCPoint]:
    c = np.asarray(conf, dtype=float)
    ok = np.asarray(correct, dtype=float) > 0.5
    n = len(c)
    out: list[RCPoint] = []
    for t in thresholds:
        fast = c >= t
        n_fast = int(fast.sum())
        n_wrong = int((fast & ~ok).sum())
        lo, hi = wilson_interval(n_wrong, n_fast)
        out.append(
            RCPoint(
                threshold=float(t),
                n_total=n,
                n_fast=n_fast,
                coverage=n_fast / n if n else float("nan"),
                n_wrong=n_wrong,
                wrong_rate=n_wrong / n_fast if n_fast else float("nan"),
                wilson_lo=lo,
                wilson_hi=hi,
                safe_fast_rate=int((fast & ok).sum()) / n if n else float("nan"),
                reliable=n_fast >= MIN_RELIABLE_N,
            )
        )
    return out


def replay_threshold(data: Mapping[str, Any], thresholds: Sequence[float]) -> list[RCPoint]:
    """Replay logged confidences at new thresholds (no model calls). `data` needs
    'conf' and 'correct' columns; a pandas DataFrame works."""
    return risk_coverage_curve(data["conf"], data["correct"], thresholds)


def select_threshold(points: Sequence[RCPoint], b_max: float) -> RCPoint | None:
    """H2 rule: highest fast-path coverage whose Wilson upper bound <= b_max.

    Ties on coverage go to the higher (safer) threshold. None if no point qualifies.
    """
    ok = [p for p in points if p.n_fast > 0 and p.wilson_hi <= b_max]
    if not ok:
        return None
    return max(ok, key=lambda p: (p.coverage, p.threshold))
