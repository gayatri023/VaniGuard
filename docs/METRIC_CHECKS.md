# Metric verification

Every metric function is checked against an example worked out by hand, independent of the code. The test that matches each is named.

| Metric | Hand-computed example | Test (`apps/api/tests/domain/test_metrics.py` unless noted) |
|---|---|---|
| Wilson, zero errors | upper = z^2 / (n + z^2). n=150: 3.8416 / 153.8416 = 0.02497. n=75: 3.8416 / 78.8416 = 0.04873 | `test_wilson_zero_errors_matches_closed_form`, `test_wilson_prd_vectors` |
| Wilson, all wrong; symmetry | lower for n of n = n / (n + z^2); interval of (k, n) mirrors (n-k, n) | `test_wilson_all_wrong_and_symmetry_and_empty` |
| ECE | ten items at confidence 0.9, eight correct: gap 0.1, ECE = 0.1. Two bins each off by 0.2: ECE = 0.2 | `test_ece_hand_computed` |
| ECE, calibrated data | perfectly calibrated synthetic data is near 0 | `test_ece_calibrated_synthetic_is_near_zero` |
| Brier | predictions [1, 0] against outcomes [1, 1]: (0 + 1) / 2 = 0.5 | `test_brier_hand_computed` |
| AUROC | scores [0.1, 0.4, 0.35, 0.8], labels [0, 0, 1, 1]: of 4 positive-negative pairs, 3 ranked correctly = 0.75; separable = 1; reversed = 0; all ties = 0.5 | `test_auroc_cases` |
| Grouped bootstrap | resamples whole participants, never rows; same seed gives the same interval | `test_bootstrap_is_grouped_and_reproducible` |
| Risk-coverage | confidence [0.95, 0.90, 0.80, 0.60], correct [1, 1, 0, 1]. At 0.85: 2 fast, 0 wrong, coverage 0.5. At 0.70: 3 fast, 1 wrong = 1/3, safe fast-path rate 2/4 | `test_risk_coverage_hand_computed` |
| H2 selection rule | 80 certain and right, 40 at 0.9 with 2 wrong, 80 at 0.5 with 40 wrong. Upper bound at 0.95: 0/80 = 0.0458; at 0.85: 2/120 = 0.0587. B = 5% picks 0.95 (coverage 0.4); B = 6% picks 0.85 (coverage 0.6); B = 0 picks nothing | `test_select_threshold_follows_h2_rule` |
| Offset score equals the live router | Tier A if and only if the score is at least 0, over random inputs | `test_property_tier_a_iff_margin_nonnegative` (`tests/domain/test_router.py`) |
| Dashboard replay equals analysis | the 41-point curve from the admin API equals the analysis table to 4 decimals | `test_dashboard_replay_equals_analysis_to_four_decimals` (`tests/test_analysis.py`) |
| Dashboard numbers equal the database | 7 hand-built commands, 5 correct: accuracy 5/7, fast path 5 of 7, 0 wrong | `test_dashboard_numbers_match_the_database` (`tests/test_study_features.py`) |
| Reproducibility | two analysis runs produce byte-identical files | `test_analysis_is_reproducible_and_flags_synthetic` (`tests/test_analysis.py`) |
