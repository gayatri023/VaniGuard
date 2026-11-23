# Changelog

## 0.1.0: first complete build
- Domain logic: spoken Hindi/Hinglish/English amounts, payee matching, validators, confidence, three-tier fail-safe router with a replayable offset score, evaluation metrics.
- API: sessions, scenario cards, audio intake and transcode, three-sample Gemini pipeline, append-only event log, deletion, CSV export, cost caps, rate limits, kill switch, read-only admin API.
- Study machinery: per-card randomised arms (routed vs always-confirm), seeded-error probes, 41-card pool.
- Participant app: Material 3, English and Hinglish, light and dark, PWA, microphone setup with in-app-browser guidance.
- Live dashboard with threshold replay; pre-registered analysis pipeline; synthetic-participant simulator; live-check tool.
- Alembic migrations, Dockerfile, Render blueprint, security headers, documentation set.
- Not yet done: live-model run, real-phone QA, Postgres run, deployment, any real study data.
