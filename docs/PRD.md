# PRD 1: Vani-Guard, confidence-routed Hinglish voice payments

*Condensed from PRD v1.0 by the author. Every number below is a target, a parameter or a placeholder, not a result.*

**One line.** A voice payment flow that decides, per field and per command, whether to proceed with one tap, ask a targeted question, or ask the user to retry, so wrong payments are caught without taxing every correct one.
**Surface.** Mobile-first web app (PWA) with a mock send flow. No real money, no bank or NPCI integration. A "demo, no real money" banner is on every screen.

## 1. Problem
Spoken Indian payment commands mix Hindi and English and use colloquial number words (pachaas = 50, dedh sau = 150, dhai sau = 250, sawa sau = 125). Payees are spoken in many spellings. The costly error is not a failed transcription but a **confidently wrong execution**: Rs 15 read as Rs 50, or one Rahul read as another. Confirming everything taxes every correct command and may train users to tap Confirm without reading; this project measures that effect instead of assuming it.
**Product question:** where is the line between fast and safe, and how do you know?

## 2. Users (hypotheses to test, not facts)
| Persona | Context | Needs |
|---|---|---|
| Hands-busy payer | Student in a noisy hostel, someone carrying bags | Speed; tolerates one tap, resents three |
| Typing-averse payer | Older relative, small shopkeeper | Speaking feels natural; amount shown large and read back clearly |

**Job to be done.** When typing is inconvenient, I want to say who and how much the way I naturally speak, so the money moves correctly without me re-checking every digit.

## 3. Goals and non-goals
Goals: a deployed voice payment flow with per-field confidence and routing; a measured risk-coverage frontier from real users; one defended threshold decision; a documented error taxonomy that drives a v2.
Non-goals: real payments or any NPCI/bank integration, KYC or authentication, production security hardening, speaker identification, languages beyond Hindi-English in the P0 scope.

## 4. Hypotheses and pre-registered decision rules
| ID | Hypothesis | Decision rule |
|---|---|---|
| H1 | A combined confidence signal (model self-report + sample agreement + rule validators) predicts field correctness better than self-report alone | Adopt if AUROC improves by at least 0.03 with a bootstrap CI excluding zero (participant-grouped). Otherwise ship the simpler signal and report that |
| H2 | A routed flow beats always-confirm on taps and time while keeping wrong executions low | Highest fast-path coverage whose Wilson 95% upper bound on wrong-execution rate is at most B. With zero errors the upper bound is about 3.8 / (n + 3.8), so 150 fast-path commands supports B of about 2.5% and 75 supports about 5% |
| H3 | Users confirm a meaningful share of deliberately wrong parses (confirmation blindness) | Report the rate with its interval; above 20%, treat always-confirm as an unsafe baseline |
| H4 | Errors cluster in identifiable conditions | If any condition is at least 10 points below average accuracy, v2 targets it |

## 5. Metrics
North star: **Safe Fast-Path Rate** = commands that took the one-tap path and were fully correct, divided by all commands. Also: wrong-execution rate, escalation precision, accuracy (payee, amount, intent, all), calibration (ECE, Brier, AUROC), taps and time to complete by arm, confirmation-blindness rate, trust and effort (three survey items), guardrails (p50/p95 latency with p95 at most 5 s, cost per command, mic and API failure rate).

## 6. Requirements
See `docs/REQUIREMENTS.md` for the status of VG-1 to VG-15 and where each is implemented and tested.

## 7. Study design
Target 40 participants, floor 25, recruited from peer groups; eight scenario cards each from a pool of about 40, stratified by difficulty; a 5-person pilot before the wide link; thresholds chosen on training folds and reported on held-out folds, always grouped by participant. Limits to state: convenience sample of peers, scripted scenarios, no real money at stake, small n for rare errors.

## 8. Business case (assumption-driven)
Per 1,000 commands: net value = (taps saved x value of a tap) - (wrong fast-path executions x average loss per wrong payment) - (cost per command x 1,000). Rates come from the study; value of a tap and average loss are labelled assumptions on a sensitivity grid. The deliverable is the **break-even loss** at which stricter thresholds win, showing how the product decision depends on stakes.

## 9. Risks and mitigations
Mobile audio formats break uploads (server-side transcode, test on iOS and Android); too few participants (send early, report real n); model nondeterminism (log model string, store all samples); users mistake it for a real payment app (persistent banner, consent text); API cost overrun (per-session and daily caps); privacy (delete audio after transcription, no identifiers, check institutional guidance); bugs in metric code (unit-test every metric against hand-computed examples).

## 10. Realism note
Real UPI ends with PIN authentication. Vani-Guard operates on intent capture before that step, and any write-up should say so.
