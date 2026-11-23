# Assumptions (append-only)

**2026-11-18**
1. **Flag names describe the problem.** `amount_mismatch_transcript` is raised when the model's amount disagrees with the transcript's number words (the PRD lists the names without polarity).
2. **"do" is often a verb.** In "bhej do / de do / kar do" the token is "give", not 2. `parse_amounts` returns every candidate with a confidence; a lone "do" after a send-verb scores 0.15, and payee tokens can be passed as `ignore` so "Rahul Das" does not yield 10.
3. **Confusable amounts are a soft penalty, not a hard flag.** Narrow rule: bare amounts under 100 (15 ↔ 50) and whole hundreds/thousands (1500 ↔ 5000). 150 and 250 are deliberately not flagged. Penalty is 0.15 off the amount validator score. Revisit after H4.
4. **Hindi 11 to 99 spellings are a starter table.** Variants are absorbed by collapsing repeated letters (aa/a, ee/e). Unrecognised words yield no amount, which routes to Tier C. Have a Hindi speaker skim `_HI_1_99` and extend it from pilot transcripts.
5. **All weights, thresholds and the payee score blend are placeholders**, not tuned. Router v1 values live in `config/router.yaml`.
6. **Tier B needs 2 to 3 distinct candidates.** Zero, one, or more than three goes to Tier C.
7. **Audio goes to Google's API for transcription.** Consent text must say so (the PRD only says audio is deleted right after transcription). Check the Gemini API data-use terms for the tier you use before writing the privacy text. I have not verified them.

**2026-11-19** (walking skeleton: API + interface)
8. **Vertical slice before hardening.** The API and the participant app were built end to end before Prompt 2's Alembic migrations and DB-role permissions. Tables are created with `create_all`; the events table is append-only by convention (the only DELETE is the participant deletion route). Do both properly before the wide link goes out if time allows.
9. **Practice card** is flagged `is_practice` on its command row and must be excluded from all accuracy metrics.
10. **Timeouts.** Server deadline for the whole model stage is 10 s (then Tier C, `pipeline_timeout`); per-call timeout is 8 s, no retry on timeout. The browser hard-stops at 12 s and shows a "cannot reach the server" screen whose retry re-sends the same request id (idempotent).
11. **Tap counting** (feeds H2): from the moment a result is shown, each button press counts (Pay, chip, Edit, Enter manually, contact pick) and typing an amount counts once. Pinned by a test: Tier A = 1, Tier B = 2, Tier C then manual = 4.
12. **The dev simulator is for UI QA only.** The API refuses to start with `VANI_MODEL_BACKEND=fake` unless `VANI_DEV=1`, and the simulator panel needs `NEXT_PUBLIC_DEV=1` at build time. Never deploy either to participants.
13. **GeminiClient is not yet tested against the live API.** The schema conversion, config, response parsing and usage extraction are tested offline against the installed google-genai SDK. Run the 10-clip live check (Prompt 4) with your key before the pilot. Thinking config is only sent if `GEMINI_THINKING_BUDGET` is set.
14. **Probe wording is gated.** The consent and debrief mention deliberate errors only when `NEXT_PUBLIC_PROBES=1`, because probes (Prompt 6) are not built yet; saying so now would be false.
15. **Card pool is a 17-card starter.** Every card's truth and ceiling must be reviewed by you before the pilot; wrong truth silently corrupts every metric.
16. **Mic needs HTTPS.** Phones only allow the microphone on https:// pages (localhost is exempt), so phone testing needs a deploy or a tunnel.

17. **Easy cards avoid confusable amounts.** The PRD's example card 1 ("Rahul Sharma Rs 50 for chai, easy_clear") uses 50, which the confusable table pairs with 15, so it was not actually "easy" for this system. Cards e1 and e6 now use Rs 100. Revert if you prefer the PRD's literal example, but then tag it `confusable_amount`.
18. **Card pool is 41 cards (12 easy, 15 medium, 13 hard, plus practice).** Every card's truth and ceiling still needs your review.
