# PRD 1 traceability: requirement to implementation to proof

| ID | Requirement | Pri | Status | Where | Verified by |
|---|---|---|---|---|---|
| VG-1 | Mock send flow, persistent demo banner | P0 | Done | `components/Shell.tsx`, `Results.tsx` | journey test (banner on first screen); 22 accessibility checks |
| VG-2 | Voice capture, 15 s cap, retry, mobile formats | P0 | Code done; **needs real-phone check** | `lib/recorder.ts`, `pipeline/audio.py` | ffmpeg tests for wav, webm/opus, mp4/aac, ogg; QA matrix pending |
| VG-3 | Gemini audio to JSON with self-confidence | P0 | Code done; **needs live API check** | `pipeline/clients.py`, `config/prompts/extract_v1.txt` | offline schema, config and parsing tests; live check pending |
| VG-4 | Three parallel samples, per-field agreement | P0 | Done | `pipeline/run.py`, `domain/confidence.py` | pipeline and API tests |
| VG-5 | Rule validators (number words, payee margin, ceiling) | P0 | Done | `domain/numbers.py`, `payee.py`, `validators.py` | 70+ number cases, payee confusable sets |
| VG-6 | Router with per-field thresholds, three tiers | P0 | Done | `domain/router.py`, `config/router.yaml` | property tests (fail safe; Tier A iff score at least 0) |
| VG-7 | Card engine, 8 of about 40 cards, stratified | P0 | Done (41 cards; **needs your review**) | `cards.py`, `config/cards/` | assignment balance and pool consistency tests |
| VG-8 | Consent, anonymous ids, audio deleted, deletion | P0 | Done; privacy items pending | `Consent.tsx`, `docs/PRIVACY.md` | deletion, no-leftover-audio, append-only tests |
| VG-9 | Append-only event log and CSV export | P0 | Done | `db.py`, `export.py`, migrations | guard and export tests |
| VG-10 | Live dashboard with replay slider | P0 | Done | `/admin`, `vani/admin.py` | 4 dashboard UI tests; replay equals analysis to 4 decimals |
| VG-11 | Per-command arms: routed vs always-confirm | P1 | Done | `cards.assign_arms`, `ConfirmAll` | arm balance, mode and tap tests |
| VG-12 | Seeded-error probes | P1 | Done | `probes.py` | probe correctness, exclusion and cap tests |
| VG-13 | Learned router, grouped CV, calibration | P1 | Offline candidate only (not deployed) | `analysis/pipeline.py`, `router_v2_candidate.yaml` | analysis tests; needs real data |
| VG-14 | Second ASR path as an extra signal | P1 | **Not built** | | |
| VG-15 | Telugu or Tamil mini-set | P2 | **Not built** | | |
