# One-page memo (fill from `analysis/output/results.md`; quote only numbers that file produced)

**Problem.** A voice payment can fail in a way that is worse than a failed transcript: a confidently wrong execution. Where is the line between fast and safe, and how do we know?

**Users and pilot.** [who exactly: e.g. university peers], n = [participants] participants, [commands] scored commands, [dates]. A mock payment flow, no real money.

**Method.** Per-field confidence from three signals (model self-report, agreement across three samples, rule validators), routed to one tap, a targeted question, or retry. Decision rules were fixed before data (see `docs/PREREG.md`, commit [hash]).

**Results (with intervals).**
- H1: combined vs self-report AUROC difference [value], 95% CI [lo, hi]. Rule applied: [adopt / simpler signal].
- H2: chosen offset [value] covers [x%] of commands; held-out wrong-execution rate [k of n = y%], Wilson 95% [lo, hi]; B was [B].
- H3: [k of n] seeded wrong parses were paid as shown ([rate], Wilson 95% [lo, hi]). Rule applied: [unsafe baseline / not].
- H4: conditions 10+ points below average: [list or none].
- Routed vs always-confirm: median taps [a vs b], median time [a vs b] seconds (bootstrap CIs in results.md).

**Decision.** [the threshold you would defend, and the break-even stakes from the business grid, labelled as assumptions].

**Limits (state plainly).** Convenience sample of peers; scripted scenarios; no real money at stake; small n for rare errors; v1 weights and thresholds were placeholders; real UPI ends in PIN authentication, which this prototype does not model; "associated with" wording where there was no randomisation.

**Next step.** [the v2 change aimed at the worst condition, with the held-out improvement from the exploratory section].

**Rehearse:** why that threshold and not a stricter one? What result would have proved you wrong? What does it cost per user, and what changes at a million users? Who were your users and what can't the data tell you? What did you decide not to build, and why?
