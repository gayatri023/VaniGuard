#!/usr/bin/env bash
# Builds a clean, reviewable git history (26 logical commits) from the finished working tree, under YOUR identity.
# Run once, from the repo root, in a directory that has no .git yet:
#   git config user.name "Your Name" && git config user.email "you@example.com"
#   bash scripts/build-history.sh
# Commits use the current time (nothing is back-dated). This script excludes itself from the history.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d .git ] && git rev-parse HEAD >/dev/null 2>&1; then
  echo "A git history already exists here. To rebuild it: rm -rf .git, then run this script again." >&2; exit 1
fi
[ -d .git ] || git init -q -b main
name="$(git config user.name || true)"; email="$(git config user.email || true)"
if [ -z "$name" ] || [ -z "$email" ]; then
  echo "Set your identity first:  git config user.name \"Your Name\" && git config user.email \"you@example.com\"" >&2; exit 1
fi
mkdir -p .git/info && grep -qx "scripts/build-history.sh" .git/info/exclude 2>/dev/null || echo "scripts/build-history.sh" >> .git/info/exclude

stage() { local p; for p in "$@"; do [ -e "$p" ] || { echo "missing path: $p" >&2; exit 1; }; git add -- "$p"; done; }
commit() { git commit -q -F -; echo "  $(git log -1 --format='%h  %s')"; }
API=apps/api; V=apps/api/vani; T=apps/api/tests; W=apps/web

# 1 ---------------------------------------------------------------------------------------------
stage .gitignore .editorconfig .env.example Makefile Dockerfile .dockerignore render.yaml .github $API/pyproject.toml data/.gitkeep
commit <<'MSG'
chore: scaffold monorepo tooling, CI, container and deploy config

Python 3.12 API package metadata with ruff, mypy and pytest; Makefile
targets for setup, checks and tests; an env template that documents every
variable; a GitHub Actions workflow (lint, types, tests, secret scan,
dependency audits); a Dockerfile with ffmpeg that runs migrations on boot;
a Render blueprint.

Audio files and local data directories are gitignored so recordings and
exports can never be committed by accident.
MSG

# 2 ---------------------------------------------------------------------------------------------
stage $V/__init__.py $V/domain/__init__.py $V/domain/numbers.py $T/domain/test_numbers.py
commit <<'MSG'
feat(domain): parse spoken Hindi, Hinglish and English amounts

Handles the Indian number system, including the colloquial multipliers
dedh, dhai, sawa, saade and paune, in Roman and Devanagari script, plus
digits and rupee words. Spelling variants are absorbed by normalisation
with a collision guard, so an ambiguous word yields no candidate rather
than a guess.

Every candidate carries a confidence. "do" after a send-verb ("bhej do")
is a verb, not the number two, and scores low. The confusable pairs that
noisy audio swaps (13/30 through 19/90) are exposed for the validators.

Anything unparseable returns no amount, which later routes to retry.
Tests: 70+ spoken-amount cases, collision checks, confusable rules.
MSG

# 3 ---------------------------------------------------------------------------------------------
stage $V/domain/payee.py $T/domain/test_payee.py
commit <<'MSG'
feat(domain): rank payees with Hinglish name normalisation

Normalises Roman and Devanagari names (aa/a, ee/i, v/w, sh/s, doubled
consonants, honorifics such as ji and bhai) and scores contacts with
RapidFuzz blended with a consonant-skeleton key. Returns the top three,
the top-1 versus top-2 margin, and an ambiguity flag so a bare "Rahul"
between two Rahuls is never treated as certain.

Tests cover the confusable sets (Rahul Sharma/Sethi, Rohit Sharma,
Priya/Pooja, Amit/Ankit, Sumit/Sunit, Ravi/Ravi Kumar).
MSG

# 4 ---------------------------------------------------------------------------------------------
stage $V/domain/router.py $T/domain/test_router.py
commit <<'MSG'
feat(domain): three-tier router that fails safe

Tier A (one tap) is returned only when payee, amount and intent each meet
their threshold and no hard flag is set. Tier B (targeted verify) needs
exactly one uncertain payee or amount and two or three distinct
candidates. Everything else, including missing, NaN or out-of-range
confidence and any unexpected exception, is Tier C.

Adds margin_score: one command-level number, the minimum of confidence
minus threshold over the fields, with hard flags scoring below everything.
Tier A is exactly "score >= 0", which lets thresholds be replayed against
logged data with a single offset.

Tests include property tests: never Tier A with a hard flag or bad input,
and Tier A if and only if the score is non-negative.
MSG

# 5 ---------------------------------------------------------------------------------------------
stage $V/domain/validators.py $V/domain/confidence.py $V/config.py config/router.yaml $T/domain/test_validators_confidence.py
commit <<'MSG'
feat(domain): field validators, confidence combination and config loader

Validators cross-check the model's output against the transcript, the
contact list and the scenario ceiling, raising named flags (amount
mismatch, amount over ceiling, intent not send-money, empty transcript,
low payee margin). Confusable amounts are a soft penalty, not a hard flag.

Confidence combines self-report, agreement across samples and validator
score behind a small interface so a learned model can replace the v1
weighted sum without touching the router. Missing inputs count as zero.

config/router.yaml holds every threshold, weight and hard flag. All values
are v1 placeholders, not tuned.
MSG

# 6 ---------------------------------------------------------------------------------------------
stage $V/domain/metrics.py $T/domain/test_metrics.py
commit <<'MSG'
feat(domain): evaluation metrics with hand-verified tests

Wilson interval, ECE, Brier, AUROC (ties handled), participant-grouped
bootstrap, the risk-coverage curve and the pre-registered threshold
selection rule (highest coverage whose Wilson upper bound is within B).

Each metric is tested against an example worked out by hand: Wilson with
zero errors against its closed form, ECE and Brier on small fixed cases,
AUROC on the textbook example (0.75), and the selection rule on a case
where the answer is known.
MSG

# 7 ---------------------------------------------------------------------------------------------
stage $V/demo.py $T/test_demo.py
commit <<'MSG'
feat(cli): command-line demo of the decision chain

python -m vani.demo "Priya ko dedh sau rupaye bhej do" runs parse,
validate, combine and route on a transcript and prints every step, so the
logic can be explored without a model, network or database.

Chips never include low-confidence candidates (the "do" verb parsed as 2
was leaking into chips); covered by a regression test.
MSG

# 8 ---------------------------------------------------------------------------------------------
stage $V/settings.py $V/cards.py $V/db.py config/pricing.yaml config/prompts config/cards
commit <<'MSG'
feat(api): settings, scenario cards and database models

Settings come from the environment and fail at startup with a clear
message: live mode refuses to start without a key, a pinned model string,
cost caps, an admin token and filled-in pricing. The dev simulator is only
allowed with VANI_DEV=1.

Scenario cards (41, stratified easy/medium/hard) and 16 contacts with
deliberately confusable pairs live in config; ground truth stays on the
server. Arms are assigned in permuted blocks of four. The database models
cover sessions, commands, samples, events, surveys and deletions, and the
events table is guarded by triggers: no UPDATE ever, DELETE only inside
the participant-deletion transaction.

pricing.yaml is intentionally empty until copied from the pricing page.
MSG

# 9 ---------------------------------------------------------------------------------------------
stage $V/pipeline $T/test_settings_gemini.py
commit <<'MSG'
feat(pipeline): audio intake, model clients and three-sample runs

Audio is transcoded with ffmpeg to 16 kHz mono WAV inside a temporary
directory that is removed on every code path; it is never written to the
database or logs. Three model calls run in parallel (temperature 0, 0.7,
0.7) with a JSON schema; per-call timeout 8 s, one retry on non-timeout
errors, and fewer than two successes routes to retry.

The Gemini client is built against the installed SDK and tested offline
(schema conversion, config, parsing, usage). It has not yet run against
the live API. A dev simulator lets the whole app run without a key.
MSG

# 10 --------------------------------------------------------------------------------------------
stage $V/probes.py $V/ratelimit.py
commit <<'MSG'
feat(api): seeded-error probes and in-memory rate limiter

Probes make exactly one field of a fast-path card deliberately wrong (a
confusable amount or a same-group payee) to measure confirmation
blindness. The rate limiter is a sliding window keyed by salted hashes
that live only in memory, so no IP address is ever stored.
MSG

# 11 --------------------------------------------------------------------------------------------
stage $V/export.py $V/admin.py
commit <<'MSG'
feat(api): CSV export and token-protected read-only admin API

One CSV per table plus a joined commands_flat file (without the deletion
hash). The admin API (summary, quality, risk-coverage replay, calibration,
data health, CSV download) requires a header token compared in constant
time and computes every statistic with the same metric functions the
analysis pipeline uses.
MSG

# 12 --------------------------------------------------------------------------------------------
stage $V/app.py $T/conftest.py $T/test_api.py $T/test_study_features.py
commit <<'MSG'
feat(api): participant study API with arms, probes and deletion

Sessions, next-card, commands, actions, survey, client events and
participant deletion with a code. Each command is idempotent by request
id, rate-limited, cost-capped and pause-able. The participant sees one of
four modes (one tap, chips, three-tap read-back for the always-confirm
arm, retry); ground truth and confidence numbers never leave the server.

Tests: full journeys, every failure mode failing safe, real audio formats
through ffmpeg with no leftover temp files, arms balance, probes (shown
wrong, paid as wrong, excluded from accuracy, capped), caps, rate limits,
CORS, admin auth, log hygiene, and dashboard numbers matching the DB.
MSG

# 13 --------------------------------------------------------------------------------------------
stage $API/alembic.ini $API/migrations $T/test_migrations_guards.py
commit <<'MSG'
feat(db): Alembic migrations with the append-only events guard

Initial schema plus a second revision that installs the events guard
(SQLite and Postgres variants). Tests prove direct UPDATE and DELETE on
events fail, the deletion route is the only DELETE and re-closes the gate,
and a database built from migrations matches the models exactly.

The Postgres variant is written but has only been exercised on SQLite.
MSG

# 14 --------------------------------------------------------------------------------------------
stage $V/simulate.py $V/livecheck.py $T/test_livecheck.py
commit <<'MSG'
feat(sim): synthetic participants and a live-check tool for real clips

The simulator drives the real API with a noisy model stand-in and scripted
participants to exercise the dashboard and analysis. Everything it writes
is labelled model=synthetic-sim and every report prints a SYNTHETIC banner.
Its error rates are invented simulation parameters, not findings.

livecheck runs recorded clips through the real pipeline and prints
accuracy, tier mix, wrong fast-path commands, latency per stage and cost.
Its test surfaced a real blind spot: a consistent mishearing contradicts
nothing checkable and takes the fast path (recorded as decision E8).
MSG

# 15 --------------------------------------------------------------------------------------------
stage analysis $T/test_analysis.py
commit <<'MSG'
feat(analysis): pre-registered analysis pipeline

Raw CSV to results.md, figures and tables with no manual steps and fixed
seeds: H1 (AUROC difference with grouped bootstrap), H2 (grouped
cross-validated threshold selection, held-out Wilson interval), H3
(confirmation blindness), H4 (conditions 10+ points below average), the
routed versus always-confirm comparison, calibration, an exploratory v2
logistic-regression router candidate and a labelled business break-even.

Tests: the dashboard replay curve equals the analysis to four decimals,
two runs are byte-identical, folds never split a participant, practice and
probe rows never count toward accuracy, tiny datasets are refused.
MSG

# 16 --------------------------------------------------------------------------------------------
stage $W/package.json $W/package-lock.json $W/tsconfig.json $W/eslint.config.mjs $W/next.config.ts $W/.gitignore $W/.env.example $W/README.md \
      $W/public $W/scripts $W/app/globals.css $W/app/theme.generated.css $W/app/layout.tsx $W/components/PwaRegister.tsx $W/components/icons.ts
commit <<'MSG'
feat(web): scaffold Next.js PWA with a generated Material 3 theme

The whole palette, light and dark, is generated from one seed colour with
Google's open-source Material Color Utilities; icons are extracted from
Material Symbols; fonts (Roboto Flex, Noto Sans Devanagari) are
self-hosted, so the browser makes no third-party requests.

Production headers: strict CSP, HSTS, no-sniff, frame denial, microphone
permission limited to this origin. A minimal service worker makes the app
installable and deliberately caches nothing.
MSG

# 17 --------------------------------------------------------------------------------------------
stage $W/lib/api.ts $W/lib/types.ts $W/lib/i18n.ts $W/lib/format.ts $W/lib/store.ts $W/lib/recorder.ts $W/lib/device.ts
commit <<'MSG'
feat(web): API client, i18n, formatting and voice recorder

Typed API client; English and Hinglish strings in one file; Indian digit
grouping and amounts in words; browser-only state (saved session,
language, online status) read through useSyncExternalStore so server and
phone never disagree; a MediaRecorder hook with a live level meter that
stops after 1.5 s of silence following speech or at 15 s.
MSG

# 18 --------------------------------------------------------------------------------------------
stage $W/components/ui.tsx $W/components/Shell.tsx
commit <<'MSG'
feat(web): Material 3 UI primitives and app shell

Buttons, cards, chips, notices, progress and amount display built on the
generated tokens with state layers, the Material type scale and
reduced-motion support. The shell shows the "Demo. No real money moves."
banner on every screen, an offline bar, and the language toggle.
MSG

# 19 --------------------------------------------------------------------------------------------
stage $W/components/Consent.tsx $W/components/MicSetup.tsx $W/components/Task.tsx $W/components/Results.tsx \
      $W/components/Finish.tsx $W/components/Study.tsx $W/app/page.tsx
commit <<'MSG'
feat(web): participant screens and study flow

Consent, microphone check (including in-app-browser guidance), task card
with live waveform and countdown ring, processing with a slow-state and
cancel, the four result cards, manual entry, success, survey, and an end
screen with the deletion code. The flow controller captures taps and
timings, resumes an interrupted session, and handles offline, paused and
rate-limited states. Consent wording about probes comes from the server,
so it always matches what actually runs.
MSG

# 20 --------------------------------------------------------------------------------------------
stage $W/lib/adminApi.ts $W/components/admin $W/app/admin
commit <<'MSG'
feat(web): admin dashboard with threshold replay

Live status and funnel, quality with Wilson intervals, a risk-coverage
chart with a replay slider (no model calls), the pre-registered H2 rule
preview, routed versus always-confirm, calibration and data health. A
SYNTHETIC banner appears whenever simulator rows exist. The token is kept
in the tab only and is never put in a URL.
MSG

# 21 --------------------------------------------------------------------------------------------
stage $W/components/StatesGallery.tsx $W/app/dev
commit <<'MSG'
feat(web): /dev/states gallery for visual QA

Every screen and state rendered with fixture data in one scroll, for
checking light and dark themes by eye. Returns 404 unless
NEXT_PUBLIC_DEV=1, so it never exists in a production build.
MSG

# 22 --------------------------------------------------------------------------------------------
stage $W/tests $W/vitest.config.mts scripts/test-web.sh
commit <<'MSG'
test(web): journey, arms, dashboard and accessibility suites

The UI tests drive the real React app against real dev API servers (one
command boots three): complete participant journeys with tap-count
assertions, the always-confirm arm and probe disclosure, dashboard numbers
matching the API with the replay slider moving them, and 22 axe-core
checks over every screen with a negative control proving the harness
catches violations. Colour contrast needs a real browser and is not
covered here.
MSG

# 23 --------------------------------------------------------------------------------------------
stage docs/PRD.md docs/REQUIREMENTS.md docs/ARCHITECTURE.md docs/DECISIONS.md docs/ASSUMPTIONS.md docs/DATA_CARD.md docs/METRIC_CHECKS.md
commit <<'MSG'
docs: product requirements, architecture, decisions and data card

PRD with traceability from each requirement to its implementation and
proof; architecture with the request lifecycle and a table of failure
modes that all fail safe; decisions and assumptions with the open ones
marked; a data card generated from the models; and the hand-computed
examples behind every metric.
MSG

# 24 --------------------------------------------------------------------------------------------
stage docs/PRIVACY.md docs/SECURITY.md docs/TEST_PLAN.md docs/QA_MATRIX.md docs/PILOT_RUNBOOK.md docs/DEPLOY.md docs/THIRD_PARTY.md docs/MEMO.md docs/CODE_TOUR.md
commit <<'MSG'
docs: privacy, security, test plan, QA matrix, runbook and deploy guide

Privacy notes (what is and is not collected, retention to be set), a
security checklist mapping each control to where it is tested and listing
the known gaps, the test plan including what is not yet verified, a device
QA matrix, the pilot runbook, deployment steps, third-party licences, the
decision memo template and a code tour.
MSG

# 25 --------------------------------------------------------------------------------------------
stage README.md CHANGELOG.md config/fixtures
commit <<'MSG'
docs: README, changelog and live-check fixtures guide

README with the problem, a diagram, how to run and test, what is verified
and what is not, and limitations. No study results appear anywhere; none
exist yet.
MSG

# 26 --------------------------------------------------------------------------------------------
stage docs/PREREG.md
commit <<'MSG'
docs(prereg): add pre-registration template

Hypotheses, decision rules, the definition of the threshold offset, design
facts the analysis relies on, and the values the author must choose (B,
retention). B and the commit hash are deliberately blank: fill them in,
mirror B into analysis/prereg.yaml, and commit and push as a separate
commit BEFORE any participant uses the app.
MSG

# leftovers: nothing should remain ------------------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  echo "WARNING: files not covered by the plan, committing them separately:" >&2; git status --porcelain >&2
  git add -A; printf 'chore: add remaining project files\n' | git commit -q -F -
fi
echo; echo "Done: $(git rev-list --count HEAD) commits on $(git rev-parse --abbrev-ref HEAD). Next: fill docs/PREREG.md, commit it, push."
