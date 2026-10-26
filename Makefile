.PHONY: check test lint format run openapi frontend bump help

PY ?= uv run python
UV ?= uv

help:
	@echo "Targets: check test lint format run openapi frontend bump"

check: lint test

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

test:
	$(UV) run pytest -q --cov=app --cov-report=term-missing 2>&1 | head -n 100; \
	exit_code=$$?; echo "---"; $(UV) run pytest -q --no-cov 2>&1 | tail -n 20; exit $$exit_code

test-only:
	$(UV) run pytest -q

run:
	$(UV) run uvicorn app.main:app --reload --port 8000

openapi:
	$(PY) -c "import json; from app.main import app; open('openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), indent=2)); print('wrote openapi.json')"

frontend:
	cd frontend && npm ci && npm run build

bump:
ifndef V
	@echo "Usage: make bump V=0.3.1"; exit 1
endif
	$(PY) scripts/bump_version.py $(V)

sync:
	$(UV) sync --all-extras

docker:
	docker compose up --build
