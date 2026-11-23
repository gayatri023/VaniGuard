# Architecture

## Components
- **Participant app** (`apps/web`, Next.js 16 PWA): records audio with `MediaRecorder` (Chrome webm/opus, iOS mp4/aac), shows the card the server chose, and sends taps and timings with the final action. It holds no ground truth and no confidence numbers.
- **API** (`apps/api`, FastAPI): validates and transcodes audio (ffmpeg), runs three Gemini calls in parallel, then validators, confidence and the router; persists everything; serves the read-only admin API.
- **Domain** (`apps/api/vani/domain`): pure, typed functions with no I/O: number parsing, payee matching, validators, confidence, router, metrics. This is the code that decides whether results are valid.
- **Database**: SQLite in development, Postgres in production; Alembic migrations; the `events` table is append-only via triggers.
- **Dashboard** (`/admin`) and **analysis** (`analysis/`): both use the same metric functions.

## Request lifecycle (`POST /api/commands`)
1. Rate-limit (per IP and per session), pause and cost-cap checks, idempotency lookup by `client_request_id`.
2. Validate MIME and size; transcode to 16 kHz mono WAV in a temp directory that is always removed.
3. Three parallel model calls (temperature 0, 0.7, 0.7) with a JSON schema; per-call timeout 8 s; one retry on non-timeout errors.
4. Agreement across samples, validators against contacts and the card ceiling, per-field confidence, router decision.
5. Decide what the participant sees (fast, verify, confirm-all, retry), apply a probe if due, persist command, samples, timings, cost and events in one transaction, respond without confidence numbers or ground truth.

Latency budget: target p95 of 5 s from stop-speaking to result; model-stage deadline 10 s; browser hard stop 12 s.

## Failure modes: every one fails safe
| Situation | What happens |
|---|---|
| Fewer than 2 of 3 model calls succeed | Retry screen, code `model_unavailable` |
| A model call times out (8 s) | Counted as failed, not retried (retrying would break the latency budget) |
| Whole model stage exceeds 10 s | Retry screen, code `pipeline_timeout` |
| Malformed or schema-violating model JSON | That sample counts as failed |
| No intelligible speech or a near-empty transcript | Hard flag, retry screen, code `no_speech` |
| Audio cannot be transcoded, is too long or too short | Retry screen with the error code stored |
| Unsupported audio type or upload over 3 MB | HTTP 415 / 413 |
| Amount contradicts the number words in the transcript | Hard flag, retry screen |
| Amount above the card's ceiling | Hard flag, retry screen |
| Intent is not "send money" | Hard flag, retry screen |
| A confidence is missing, NaN or outside 0 to 1 | Retry screen |
| Unexpected exception in the router or pipeline | Retry screen (`router_error`, `pipeline_error`) |
| Router says fast path but a displayed field is missing | Forced to retry (`missing_display_field`) |
| Daily or session cost cap reached; `STUDY_PAUSED` set | HTTP 503, "study paused" screen |
| Browser cannot reach the server | "Cannot reach the server" screen; retry re-sends the same request id, which is idempotent |
| UPDATE on events, or DELETE outside the participant-deletion transaction | Rejected by the database |

## Data model (see `docs/DATA_CARD.md` for every column)
`sessions` (anonymous id, consent version, arms and card list), `commands` (parse, per-field confidences, flags, route, what was shown, what the user did, ground-truth comparisons, timings, cost), `samples` (raw model JSON), `events` (append-only funnel and system events), `surveys`, `deletions` (hash only), `delete_gate` (internal).

## Design principles
Fail safe over fast; thresholds, weights, prices and model strings live in config, never inline; every row carries model, prompt, router and app versions; ground truth comes from scenario cards, never the model; audio is never persisted; one source of truth for metrics.
