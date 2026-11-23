# Device QA matrix (complete before the public link goes out)

Mark each cell PASS / FAIL with a one-line note. Anything FAIL on a row marked **must** blocks the link. Use the real deployed URL, not localhost.

| # | Scenario | must | Result | Notes |
|---|---|---|---|---|
| 1 | Android Chrome, mid-range phone: full journey, 9 cards, survey, deletion code | must | | |
| 2 | Low-end Android (2 GB RAM or older): recording, waveform smooth enough, no crash | must | | |
| 3 | iPhone Safari: mic permission, audio format (mp4/aac) reaches the model, full journey | must | | |
| 4 | Link opened from inside WhatsApp (in-app browser): the "open in Chrome or Safari" guidance appears and the copy-link button works | must | | |
| 5 | Mic permission denied, then allowed after following the on-screen steps | must | | |
| 6 | Bluetooth headset as the microphone | | | |
| 7 | Throttled 3G (devtools or a weak connection): processing screen, "taking longer" after 5 s, hard stop and retry | must | | |
| 8 | Airplane mode mid-session: offline bar appears, retry works after reconnecting, no duplicate payment rows | must | | |
| 9 | Reload mid-session: resumes at the mic check and continues the same cards | must | | |
| 10 | Background noise (TV or music on): the noise card behaves, results look plausible | | | |
| 11 | Dark mode on the phone: every screen legible | | | |
| 12 | Hinglish toggle on every screen | | | |
| 13 | Both arms seen: a 1-tap card and a 3-tap confirm card appear within one session | must | | |
| 14 | A probe seen (may need several sessions): looks identical to a normal fast-path card, debrief mentions it | | | |
| 15 | Delete my data from the end screen with the code; dashboard counts drop | must | | |
| 16 | Wrong deletion code is rejected | | | |
| 17 | Kill switch: set `STUDY_PAUSED=1`, new sessions and commands show the paused screen; set it back | must | | |
| 18 | `/dev/states` returns 404 in production | must | | |
| 19 | Dashboard at `/admin`: wrong token rejected, right token loads, slider moves, CSV downloads | must | | |
| 20 | Spend alert or cap: a deliberately tiny daily cap pauses the study cleanly (then restore the real cap) | must | | |

Also run the live model check (10 to 30 consented clips) and the live prompt-injection clips before the link goes out; see `docs/DEPLOY.md`.
