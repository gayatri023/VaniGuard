# Deploy guide

Accounts you need: Google AI Studio (API key), Neon or Supabase (Postgres), Render (API), Vercel (web). All have free tiers; check each one's current limits yourself.

## 1. Database
Create a Postgres database. Use the connection string in SQLAlchemy form: `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`.

## 2. API on Render
1. New Blueprint from this repo (`render.yaml`), or a Docker web service from the root `Dockerfile`.
2. Set the secret env vars (see table). The app **refuses to start** with a clear message if anything is missing or if `config/pricing.yaml` still has null values.
3. The container runs `alembic upgrade head` before serving. Check `https://<api>/healthz` and `/readyz`.

| Variable | Value |
|---|---|
| `VANI_DEV` | `0` (never 1 in production) |
| `VANI_MODEL_BACKEND` | `gemini` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | your key; the exact model string from AI Studio |
| `DATABASE_URL` | the Postgres URL above |
| `ADMIN_TOKEN` | a long random string (at least 16 characters) |
| `ALLOWED_ORIGINS` | your web origin, e.g. `https://vani-guard.vercel.app` |
| `DAILY_COST_CAP_USD`, `SESSION_COST_CAP_USD` | caps you choose |
| `ARMS_ENABLED`, `PROBES_ENABLED` | `1` for the full study |
| `TRUST_PROXY` | `1` behind Render's proxy |
| `STUDY_PAUSED` | `0` (set `1` for the kill switch) |

Fill `config/pricing.yaml` (version, model, prices) from the current pricing page and commit it before deploying.

## 3. Web on Vercel
Import the repo with root directory `apps/web`. Environment: `NEXT_PUBLIC_API_URL` = the API URL, `NEXT_PUBLIC_DEV` = `0`. Deploy. Open `/dev/states`: it must return 404.

## 4. Verify live
Record 10 to 30 consented clips (include hard cases, noise, and two or three prompt-injection clips), write a `truth.csv`, and run `cd apps/api && python -m vani.livecheck path/to/clips` with the live env set. It prints accuracy, tier mix, **wrong fast-path commands**, latency p50/p95 per stage (budget: p95 under 5 s) and cost per command. Then QA matrix on real phones. HTTPS is required for the microphone on phones.

## 5. Observability and backups
- Uptime ping every 5 minutes on `/healthz` (any free monitor).
- Error tracking: add a free Sentry-style service on both apps if you want one; none is wired in by default, so no third party sees data unless you add it (and then disclose it).
- Spend alerts: set 50% and 80% budget alerts in the Google Cloud billing console for the key's project.
- Backups: a daily `pg_dump` (or the provider's snapshots), and **test one restore** before launch. Restore is not tested here.

## 6. Kill switch and rollback
Set `STUDY_PAUSED=1` and restart: new sessions and commands show the paused screen. To roll back code, redeploy the previous image; migrations are additive.
