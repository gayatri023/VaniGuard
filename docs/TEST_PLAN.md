# Test plan

## Automated (run on every push; `make check && make test-web`)
| Layer | What | Count / tool |
|---|---|---|
| Unit | Domain functions: 70+ spoken-amount cases (Roman and Devanagari), payee confusable sets, validators, confidence, router, metrics against hand-computed values | pytest, mypy strict on `domain/`, coverage 95%+ per domain module |
| Property | Router never returns the fast path with a hard flag or invalid input; fast path if and only if the offset score is at least 0 | hypothesis |
| Integration | Full API journeys with the dev simulator; every model failure mode; real audio formats through ffmpeg with no leftover temp files; arms, probes, caps, rate limits, CORS, admin auth, deletion, append-only guards; Alembic upgrade and downgrade | pytest (200 tests API-side, including analysis and live-check tests) |
| Analysis | Dashboard replay equals analysis to 4 decimals; two runs are byte-identical; folds never split a participant | pytest |
| UI | Complete participant journeys against the real API, always-confirm arm and probe disclosure, dashboard numbers match the API, 22 accessibility checks (axe-core, with a negative control) | vitest + testing-library (31 tests) |
| Static | ruff, ESLint, TypeScript strict, production build, secret scan, `npm audit` | CI |

## Not automated yet (needs you, in this order)
1. **Live model check.** Record 10 to 30 consented clips with a `truth.csv` (`config/fixtures/README.md`), then `python -m vani.livecheck clips/` with live env. Pass: no crashes; p95 total latency under 5000 ms; cost per command known and times your expected volume under the cap; the count of **wrong fast-path commands** reviewed; injection clips ("ignore your instructions...") never produce the injected amount on the fast path.
2. **Real-phone QA.** `docs/QA_MATRIX.md`, every row marked "must", on at least one Android Chrome and one iPhone Safari, plus the in-app-browser case.
3. **Postgres.** Run `alembic upgrade head` against the real database, then confirm `UPDATE events ...` and `DELETE FROM events` both fail, and that the participant-deletion route still works. (Written and tested on SQLite only.)
4. **Deployed smoke test.** `/healthz`, `/readyz`, `/api/config`; one full session on the live URL; `/dev/states` returns 404; security headers present; admin login works; a deliberately tiny cost cap pauses the study cleanly (then restore it).
5. **Dry run with 3 to 5 people** before the wider group. Watch the funnel and error counts on the dashboard.

## Go / no-go before sending the link to participants
- [ ] Items 1 to 4 above pass.
- [ ] Cards reviewed by you; B chosen; `docs/PREREG.md` and `analysis/prereg.yaml` committed and pushed.
- [ ] E8 decided (`docs/DECISIONS.md`) and, if changed, the router version bumped.
- [ ] `STUDY_PAUSED` kill switch tested; one backup restore tested.
- [ ] You can explain the router, the Wilson interval and the probes without notes.
