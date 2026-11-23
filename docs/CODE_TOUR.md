# Code tour

## Run
```
pip install -e "apps/api[dev]"            # Python 3.11+, plus ffmpeg on PATH
make dev-api                              # API :8000, dev simulator on (VANI_DEV=1), no key needed
cd apps/web && cp .env.example .env.local && npm install && cd ../.. && make dev-web   # http://localhost:3000
```
Pages: `/` participant app · `/admin` dashboard (dev token `dev-admin-token`) · `/dev/states` every screen with fixture data (dev only). The dev simulator panel on the task screen lets you trigger each tier without a microphone. Phones need HTTPS for the microphone, so test them on a deploy or a tunnel.

## Test
```
make check                 # ruff + mypy strict + eslint + tsc + API tests
make test-web              # boots three dev APIs (plain, arms+probes, synthetic), runs all UI tests
make demo-analysis         # synthetic participants -> CSV -> analysis/output (results.md, figures/, tables/)
```

## Read in this order
1. `config/router.yaml`: every threshold, weight, hard flag (v1 placeholders).
2. `apps/api/vani/domain/`: `numbers.py` (spoken amounts), `payee.py`, `validators.py`, `confidence.py`, `router.py` (Tier A/B/C and the offset score), `metrics.py`. Pure functions; the heart of the product.
3. `apps/api/vani/pipeline/run.py`: three samples → validators → router. Then `app.py` (all routes, arms, probes, modes), `db.py` (tables and append-only guards), `admin.py` (dashboard API).
4. `apps/web/components/Study.tsx`: the whole participant flow; screens in `Consent`, `MicSetup`, `Task`, `Results`, `Finish`; design system in `ui.tsx` + `app/globals.css` + generated `theme.generated.css`.
5. `apps/web/components/admin/`: dashboard and charts. `analysis/pipeline.py` + `run.py`: the pre-registered analyses.

## Map
```
config/        router.yaml · pricing.yaml (fill in) · prompts/extract_v1.txt · cards/ (16 contacts, 41 cards)
apps/api/vani/ domain/ · pipeline/ · app.py · admin.py · db.py · cards.py · probes.py · ratelimit.py · settings.py · simulate.py · export.py
apps/api/      migrations/ (Alembic) · tests/
apps/web/      app/ (/, /admin, /dev/states) · components/ · lib/ · scripts/ (gen-theme, gen-icons) · tests/
analysis/      prereg.yaml · pipeline.py · run.py
docs/          see README
```
Regenerate the theme from one seed colour: `cd apps/web && npm run theme` (Google's Material Color Utilities). Icons: `npm run icons` (Material Symbols).
