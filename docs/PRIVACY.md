# Privacy notes

These are the things the system does, written so you can check them against your institution's guidance. They are **not** legal compliance claims.
Before the link goes out: confirm with your university whether peer data collection needs ethics review or approval, and finalise the retention rule.

## Purpose
Measure how well a Hinglish voice-payment prototype understands spoken commands and how participants respond to it. Mock payments only; no real money.

## What is collected
Short voice clips (see "Audio"), the transcript text, parsed payee and amount, taps and timings, a 3-question survey (optional free text), coarse device info (mobile or desktop, browser family, OS family), self-reported language comfort and noise level, and an anonymous random session id.

## What is not collected
Names, phone numbers, email, bank details, contacts, location, advertising ids, IP addresses (rate limiting keeps salted hashes in memory only, which vanish on restart).

## Audio
Audio is transcoded in memory and in a temporary directory that is deleted on every code path (tested). It is never written to the database or the logs. **The clip is sent to Google's Gemini API for transcription**, which the consent screen says in plain words. **Not yet verified:** Google's data-use terms for the API tier you use (for example, whether prompts may be retained or used for model improvement on free versus paid tiers). Read the current terms for your tier and tell participants accurately.

## Retention
Raw rows: ______ (decide, e.g. delete N days after the analysis is submitted). Backups follow the same rule. Aggregate results contain no row-level data.

## Deletion
Each participant gets an 8-character code at the end. With it they can delete every row of theirs (commands, samples, events, survey, session); only a hash of the session id is kept as proof a deletion happened. The route and the database guard around it are tested. Participants should save the code; there is no other way to find a session because there is no identity to look up.

## Access
You (the researcher) via the admin dashboard (token-protected, read-only) and the database. Anyone else needs your explicit decision; share only aggregate results.

## Consent version history
- `v1`: early development build (no arms, no probes). Not used for data collection.
- `v2`: arms enabled, probes off.
- `v2-probes`: arms and probes on; the consent screen discloses that some screens may contain deliberate mistakes, and the debrief explains them. The server decides which version is shown, so consent wording always matches what actually runs.

## Children
The consent text is written for adults. Recruit adults only and say so in the invite.
