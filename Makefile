.PHONY: setup test test-web lint typecheck check demo dev-api dev-web seed export-csv analyze demo-analysis
setup:
	pip install -e "apps/api[dev]" && cd apps/web && npm install
test:
	cd apps/api && python -m pytest -q
test-web:    ## boots 3 dev APIs, runs all UI tests (journey, arms, admin dashboard, accessibility)
	bash scripts/test-web.sh
lint:
	cd apps/api && ruff check . && cd ../web && npm run lint
typecheck:
	cd apps/api && mypy --strict vani/domain && cd ../web && npm run typecheck
check: lint typecheck test
demo:
	cd apps/api && python -m vani.demo "Priya ko dedh sau rupaye bhej do"
dev-api:
	cd apps/api && VANI_DEV=1 python -m uvicorn vani.app:create_app --factory --reload --port 8000
dev-web:
	cd apps/web && npm run dev
seed:        ## SYNTHETIC participants, for trying the dashboard and analysis. Never results.
	python -m vani.simulate --n 40 --db sqlite:///$(CURDIR)/data/synthetic.db
export-csv:  ## one CSV per table + commands_flat.csv from DATABASE_URL (default: data/synthetic.db)
	DATABASE_URL=$${DATABASE_URL:-sqlite:///$(CURDIR)/data/synthetic.db} python -m vani.export $(CURDIR)/data/export
analyze:     ## raw CSV -> analysis/output/results.md, figures/, tables/ (fixed seeds)
	python analysis/run.py
demo-analysis: seed export-csv analyze
