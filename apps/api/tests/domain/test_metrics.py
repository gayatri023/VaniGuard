import math

import numpy as np
import pytest

from vani.domain.metrics import (
    auroc,
    bootstrap_ci,
    brier,
    ece,
    replay_threshold,
    risk_coverage_curve,
    select_threshold,
    wilson_interval,
)  # fmt: skip

Z2 = 1.96**2


def test_wilson_zero_errors_matches_closed_form() -> None:
    for n in (25, 75, 150, 300):
        lo, hi = wilson_interval(0, n)
        assert lo == 0.0
        assert hi == pytest.approx(Z2 / (n + Z2), abs=1e-9)


def test_wilson_prd_vectors() -> None:
    assert wilson_interval(0, 150)[1] == pytest.approx(0.025, abs=5e-4)
    assert wilson_interval(0, 75)[1] == pytest.approx(0.049, abs=5e-4)


def test_wilson_all_wrong_and_symmetry_and_empty() -> None:
    assert wilson_interval(50, 50)[0] == pytest.approx(50 / (50 + Z2), abs=1e-9)
    lo, hi = wilson_interval(7, 40)
    lo2, hi2 = wilson_interval(33, 40)
    assert (lo, hi) == pytest.approx((1 - hi2, 1 - lo2))
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_ece_hand_computed() -> None:
    # ten items at confidence 0.9, eight correct: |0.8 - 0.9| = 0.1
    assert ece([0.9] * 10, [1] * 8 + [0] * 2) == pytest.approx(0.1)
    # two bins: (0.2 conf, 0/2 right) gap 0.2 ; (0.8 conf, 2/2 right) gap 0.2 -> 0.2
    assert ece([0.2, 0.2, 0.8, 0.8], [0, 0, 1, 1]) == pytest.approx(0.2)
    # confidence 1.0 lands in the last bin, perfect
    assert ece([1.0, 1.0], [1, 1]) == pytest.approx(0.0)


def test_ece_calibrated_synthetic_is_near_zero() -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 50_000)
    y = (rng.uniform(0, 1, p.size) < p).astype(int)
    assert ece(p, y) < 0.01


def test_brier_hand_computed() -> None:
    assert brier([1.0, 0.0], [1, 1]) == pytest.approx(0.5)
    assert brier([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_auroc_cases() -> None:
    assert auroc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert auroc([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0
    assert auroc([0.5, 0.5, 0.5, 0.5], [0, 1, 0, 1]) == 0.5
    assert auroc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.75)
    assert math.isnan(auroc([0.1, 0.2], [1, 1]))


def test_bootstrap_is_grouped_and_reproducible() -> None:
    groups = np.repeat(np.arange(10), 5)
    vals = np.where(groups < 5, 0.0, 1.0)

    def stat(idx: np.ndarray) -> float:
        return float(vals[idx].mean())

    a = bootstrap_ci(stat, groups, n_boot=500, seed=3)
    b = bootstrap_ci(stat, groups, n_boot=500, seed=3)
    assert a == b and a[0] == 0.5 and a[1] < 0.5 < a[2]

    seen: list[set[int]] = []

    def spy(idx: np.ndarray) -> float:
        seen.append(set(np.unique(idx).tolist()))
        return 0.0

    bootstrap_ci(spy, groups, n_boot=20, seed=0)
    for s in seen[1:]:  # every resample is a union of whole participants
        assert all({g * 5 + k for k in range(5)} <= s for g in {i // 5 for i in s})


def test_risk_coverage_hand_computed() -> None:
    conf = [0.95, 0.90, 0.80, 0.60]
    ok = [1, 1, 0, 1]
    hi, lo = risk_coverage_curve(conf, ok, [0.85, 0.70])
    assert (hi.n_fast, hi.coverage, hi.n_wrong, hi.wrong_rate, hi.safe_fast_rate) == (2, 0.5, 0, 0.0, 0.5)
    assert (lo.n_fast, lo.n_wrong, lo.safe_fast_rate) == (3, 1, 0.5)
    assert lo.wrong_rate == pytest.approx(1 / 3)
    assert not hi.reliable  # n_fast < 30


def test_replay_matches_direct_curve() -> None:
    data = {"conf": [0.9, 0.7, 0.95], "correct": [1, 0, 1]}
    assert replay_threshold(data, [0.5, 0.8]) == risk_coverage_curve(data["conf"], data["correct"], [0.5, 0.8])


def test_select_threshold_follows_h2_rule() -> None:
    # 80 certain+right, 40 at 0.9 (2 wrong), 80 at 0.5 (half wrong)
    conf = [0.99] * 80 + [0.9] * 40 + [0.5] * 80
    ok = [1] * 80 + [1] * 38 + [0] * 2 + [1] * 40 + [0] * 40
    pts = risk_coverage_curve(conf, ok, [0.95, 0.85, 0.4])
    # hand check: 0/80 -> upper 3.8416/83.8416 = 0.0458 ; 2/120 -> upper ~0.0587
    assert pts[0].wilson_hi == pytest.approx(0.0458, abs=5e-4)
    assert pts[1].wilson_hi == pytest.approx(0.0587, abs=5e-4)
    pick = select_threshold(pts, 0.05)
    assert pick is not None and pick.threshold == 0.95 and pick.coverage == 0.4
    pick = select_threshold(pts, 0.06)
    assert pick is not None and pick.threshold == 0.85 and pick.coverage == 0.6
    assert select_threshold(pts, 0.0) is None  # unreachable bound -> nothing qualifies


def test_wilson_interval_always_contains_the_point_estimate() -> None:
    # regression: k = 0 once produced a lower bound of 1e-17 above the estimate, which crashed an error-bar plot
    for n in range(1, 121):
        for k in range(n + 1):
            lo, hi = wilson_interval(k, n)
            assert 0.0 <= lo <= k / n <= hi <= 1.0, (k, n, lo, hi)
