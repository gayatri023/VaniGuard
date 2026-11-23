# Decisions

Format: context, options, choice, reason, date. Items marked **PROPOSED** are defaults I implemented so the pilot can run; they are yours to confirm or change, and a change after data starts needs a router version bump and an entry here.

## D1. Per-field thresholds and why: PROPOSED
- **Context.** A wrong amount or payee is far costlier than a wrong note, so the fast path must be stricter for those fields.
- **Options.** One global threshold; per-field thresholds; per-field thresholds swept together by one offset.
- **Implemented.** Per-field thresholds amount 0.90, payee 0.85, intent 0.80 (`config/router.yaml`, version `v1-placeholder-0`), swept by a single offset δ in analysis (see PREREG).
- **Why.** Keeps the asymmetry and gives one curve to defend. **The numbers themselves are placeholders, not tuned.**

## D2. Two or three samples: PROPOSED (three)
- **Context.** Agreement across samples is one of the confidence signals; each sample costs one more model call.
- **Implemented.** Three parallel samples (temperature 0, 0.7, 0.7); a failed sample counts as disagreement; fewer than two successes routes to retry.
- **Reason.** Three allows a majority and a meaningful agreement score. The cost-versus-AUROC trade-off can be checked after the pilot by recomputing agreement from two samples (the raw samples are stored).

## D3. Verify tier: chips or re-ask: PROPOSED (chips)
- **Implemented.** Two or three large chips for the one uncertain field, plus "Something else". More than three candidates, or fewer than two, goes to retry.
- **Reason.** One tap resolves it; re-asking costs a new recording and more latency.

## D4. Error rate and fast-path coverage required before shipping to real users: OPEN
Your call, and the PRD says to record it. This prototype has no real-money path and no PIN step; any real launch decision needs a much larger, representative sample.

## Engineering decisions (made while building)
- **E1. Fail safe everywhere.** Any error, timeout, missing field or contradiction routes to retry, never the fast path; a defence-in-depth check re-verifies the displayed fields after the router. Property-tested.
- **E2. Confusable amounts are a soft penalty, not a hard flag**, and the rule is narrow (bare amounts under 100, whole hundreds and thousands). Revisit after H4.
- **E3. Probes are shown only in the routed arm, never on the practice card, capped per participant.** Practice and probe rows are tagged and excluded from accuracy.
- **E4. The events table is append-only in the database itself** (triggers), with one documented exception: the participant-deletion transaction.
- **E5. Dashboard and analysis share one set of metric functions**, so a number can never differ between them.
- **E6. Synthetic data is labelled everywhere** (model string, dashboard banner, analysis banner) so it cannot be mistaken for results.
- **E7. No third-party requests from the browser**: fonts and icons are self-hosted; the CSP allows only this origin and the API.
- **E8. A consistent mishearing passes the fast path at the v1 placeholders (found by the live-check tests).** If the model hears and transcribes "50" for a spoken "15", the transcript, the amount and all three samples agree and nothing can contradict it. The confusable-pair penalty lowers the combined amount confidence only to about 0.94, which still clears the 0.90 amount threshold. This is the failure the study measures, not a bug. **Your options (decide before the pilot, version-bump if changed):** (a) keep v1 and measure how often it happens; (b) raise the amount threshold; (c) make any confusable amount (13/30 to 19/90) always go to the chips tier. (c) costs one extra tap on those commands and removes the blind spot for exactly the pairs you worry about most.
