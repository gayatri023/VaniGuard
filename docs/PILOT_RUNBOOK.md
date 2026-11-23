# Pilot runbook

## T-minus checklist (all must be ticked before the wide link)
- [ ] `docs/PREREG.md` filled in (B, retention) and committed **with** `analysis/prereg.yaml`; commit hash written in the file
- [ ] Gemini model string pinned (`GEMINI_MODEL`), `config/pricing.yaml` filled from the current AI Studio pricing page and its `model` equals `GEMINI_MODEL`
- [ ] Daily and per-session cost caps set; a tiny-cap test done (QA row 20)
- [ ] Card pool reviewed by you, every card: truth payee, truth amount, ceiling
- [ ] Hindi speaker skimmed the number table in `domain/numbers.py` and the Hinglish UI strings
- [ ] Live 10 to 30 clip test run and read (accuracy, latency table, cost per command), including injection clips
- [ ] `docs/QA_MATRIX.md` complete on real phones
- [ ] Consent text final; Google data-use terms for your API tier read and `docs/PRIVACY.md` retention filled in; institutional guidance checked
- [ ] `STUDY_PAUSED` kill switch tested; backup taken and one restore tested
- [ ] Error tracking and an uptime ping on `/healthz` configured; spend alerts at 50% and 80% of the cap
- [ ] Router config frozen: from now on any change needs a version bump and an entry in `docs/DECISIONS.md`

## If you have under two days (compressed schedule)
Collection time cannot be compressed, so protect it: get the link live as early as possible and report the real n. A shorter window means a smaller n and wider intervals, which is a legitimate, honest result.
1. **First 2 hours:** Gemini key and model string, fill `config/pricing.yaml`, review the 41 cards, pick B, commit `PREREG.md` and `analysis/prereg.yaml`, deploy API and web (`docs/DEPLOY.md`).
2. **Next 2 hours:** `python -m vani.livecheck` on 10 to 15 recorded clips (see the file header for the truth.csv format), then the QA rows marked **must** on two real phones.
3. **Pilot:** 5 people, fix only blockers (1 to 2 hours).
4. **Same evening:** send the wide link. Send the reminder the next morning.
5. **Freeze early on the last day** (leave at least 6 hours): `STUDY_PAUSED=1`, export, `make analyze`, then the one-pager and resume bullets from `results.md` only.

## Pilot (5 people), then the wide link
Send the link to 5 people you can talk to. Watch the dashboard live. Fix **only** blocking bugs. Then post to the wider groups.

## Messages (both under 60 words, honest, no pressure)
**Invite** (48 words):
> Hi! I'm testing a voice-payment prototype for a student project. It's a mock: no real money, about 5 minutes, and your voice is deleted right after it's turned into text. You'll say 8 short payment commands in Hindi, English or both. Please open in Chrome or Safari: {LINK}

**Day-2 reminder** (34 words):
> Quick reminder: the 5-minute voice-payment test is still open: {LINK}. Mock payments only, nothing personal collected. Thank you! If it's stuck on the mic, open the link in Chrome or Safari, not inside WhatsApp.

## Participant FAQ
- **Is it real money?** No. Nothing moves; a banner says so on every screen.
- **What do you keep?** The text of what you said, your taps and survey answers. Not your name, number or bank details. Your voice is deleted right after it is turned into text (it is sent to Google's AI service for that step).
- **Can I stop or delete?** Yes, any time. The code on the last screen deletes everything you sent.
- **Why did one screen show something wrong?** Some screens contain deliberate mistakes to test attention (only if probes are enabled). It was part of the test, not your mistake.

## Troubleshooting
- **Mic blocked:** tap the lock or tune icon by the address, allow Microphone, reload. iPhone: Settings, Safari, Microphone.
- **Opened inside WhatsApp or Instagram:** copy the link and open it in Chrome or Safari (the app shows a button).
- **"Cannot reach the server":** check the connection; "Try again" re-sends the same request safely.
- **Stuck on processing:** it stops by itself and offers retry or manual entry.
- **Study paused:** the daily cost cap was reached or you set the kill switch.

## Daily routine
1. Open `/admin` (dashboard): participants, funnel and dropout screen, errors in the last hour, spend against caps, data-health versions (must be exactly one router, prompt and app version).
2. If the funnel shows a cliff at one screen, fix that screen only. Do not touch router config mid-study.
3. Send the Day-2 reminder once.

## Close-out
Freeze the link (`STUDY_PAUSED=1`), export (`python -m vani.export`, and the dashboard CSV), take a backup, record the final n (participants and commands), then `make analyze`. Quote only numbers from `analysis/output/results.md`.
