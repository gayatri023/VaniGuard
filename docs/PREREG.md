# Pre-registration: Vani-Guard pilot

**Commit this file, and `analysis/prereg.yaml`, BEFORE the participant link goes out (the pilot with 5 people counts as data).**
The git commit timestamp is the proof. After data collection starts, changes go in "Amendments" with a date and a reason.

- Committed at (UTC): ______  ·  Commit hash: ______
- Router version in force: ______  ·  Model string (pinned): ______  ·  Prompt version: ______  ·  App version: ______

## Choices that are yours (fill in now, before data)

| Item | Value | Note |
|---|---|---|
| **B**: max acceptable wrong-execution rate (Wilson 95% upper bound) | ____ % | Copy as a fraction into `analysis/prereg.yaml` (`b_max`). See the table below |
| Target / floor participants | 40 / 25 | PRD defaults |
| Folds | participant-grouped, k = 5 | `analysis/prereg.yaml` |
| Bootstrap | 2,000 resamples, participant-grouped, seed 0 | `analysis/prereg.yaml` |
| Retention rule for raw data | ______ | Decide, then write it in `docs/PRIVACY.md` |

Best-case Wilson upper bound with **zero** wrong fast-path commands, 3.8416 / (n + 3.8416):

| fast-path n | 50 | 75 | 100 | 150 | 200 |
|---|---|---|---|---|---|
| upper bound | 7.1% | 4.9% | 3.7% | 2.5% | 1.9% |

If B is below what your fast-path n can reach, the H2 rule can select nothing. Choose B with that in mind. (On the synthetic demo data, B = 5% selects nothing for exactly this reason.)

## What "threshold" means in this study

The live router has three per-field thresholds (amount, payee, intent; asymmetric on purpose, `config/router.yaml`). To sweep a single threshold
without losing that asymmetry, each command gets one score: **min over fields of (confidence minus that field's threshold)**, and any hard flag
(amount over the card ceiling, amount contradicting the transcript, intent not send-money, empty transcript) scores below everything.
A command takes the fast path iff its score is at least the offset **δ**. δ = 0 is exactly the live router (tested). The grid is δ from -0.30 to +0.10 in steps of 0.01 (41 points).
The same function produces the dashboard slider and the analysis, so they agree to the last decimal (tested).

## Hypotheses and decision rules (from PRD 1)

- **H1**: the combined signal predicts field correctness better than self-report alone. Adopt the combined signal if the AUROC difference is at least 0.03 **and** its participant-grouped bootstrap 95% CI excludes zero. Otherwise ship the simpler signal and report that. Fields: payee and amount, pooled.
- **H2**: routing beats always-confirm on taps and time while keeping wrong executions low. Choose the δ with the highest fast-path coverage whose Wilson 95% upper bound on the wrong-execution rate is at most B (ties go to the stricter δ). Thresholds are chosen on training folds; the wrong-execution rate is reported on held-out folds, pooled, with a Wilson interval.
- **H3**: users confirm a meaningful share of deliberately wrong parses (confirmation blindness). Report probes paid as shown ÷ probes, with a Wilson interval. If above 20%, call always-confirm an unsafe baseline.
- **H4**: errors cluster in identifiable conditions. If any condition's accuracy is at least 10 points below the overall accuracy, v2 targets it.

## Design facts the analysis relies on

- Eight scored cards per participant (2 easy, 3 medium, 3 hard) plus one practice card; least-served-first, no repeats.
- Arms: randomised per card, permuted blocks of 4 (2 routed, 2 always-confirm), seeded by session id, logged per command.
- Probes: about 12% of fast-path cards on non-practice cards in the routed arm, at most 2 per participant (`PROBE_RATE`, `MAX_PROBES_PER_SESSION`); disclosed in the consent text and debrief.
- Excluded from accuracy metrics: practice cards, seeded-error probes, and the researcher's own stress set (reported separately).
- Correctness comes from scenario-card ground truth only, never from the model.
- Always report n. Proportions get Wilson intervals; everything else gets bootstrap intervals. "Associated with" wording wherever there is no randomisation.
- Anything not listed here is exploratory and labelled as such (the v2 router and the business model are exploratory).

## Amendments
(none)
