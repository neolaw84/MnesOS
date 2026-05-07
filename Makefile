# Makefile for MnesOS common developer tasks

VENV=venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
NPM=npm
PLAYWRIGHT=npx playwright

.PHONY: help setup python-test web-test build stage e2e package full-ci clean

help:
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  setup         Create venv and install python dev deps"
	@echo "  python-test   Run Python unit tests (pytest)"
	@echo "  web-test      Run web unit tests (Vitest + coverage)"
	@echo "  build         Build web-client (tsc + vite)"
	@echo "  stage         Stage built web-client into src/MnesOS/static"
	@echo "  e2e           Run Playwright E2E (unified mode)"
	@echo "  run-web       Start frontend dev server (foreground)"
	@echo "  run-python    Start backend dev server (uvicorn, foreground)"
	@echo "  run-e2e       Start backend for manual E2E (no Playwright; uses real OpenRouter)"
	@echo "  package       Build Python wheel and sdist"
	@echo "  full-ci       Run python-test, web-test, build+stage, e2e, package"
	@echo "  clean         Clean build artifacts"

setup:
	python -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PIP) install -e ".[dev]"

python-test:
	$(PY) -m pytest --maxfail=1 -q

web-test:
	cd web-client && $(NPM) ci && $(NPM) run test:coverage

build:
	cd web-client && $(NPM) ci && $(NPM) run build

stage:
	rm -rf src/MnesOS/static
	mkdir -p src/MnesOS/static
	cp -r web-client/dist/. src/MnesOS/static/

e2e: build stage
	cd web-client && CI=true $(PLAYWRIGHT) test --project chromium

run-web:
	@echo "Starting web dev server in web-client (foreground)"
	cd web-client && $(NPM) ci && $(NPM) run dev

run-python:
	@echo "Starting backend (uvicorn) in foreground"
	MNESOS_DB_PATH=artifacts/mnesos-dev.db MNESOS_STATIC_DIR=src/MnesOS/static OPENROUTER_BASE_URL=http://127.0.0.1:8899/api/v1 $(PY) -m uvicorn MnesOS.api.app:app --host 0.0.0.0 --port 8000

run-e2e: build stage
	@echo "Starting backend for manual E2E (uses real OpenRouter)."
	@echo "Visit http://localhost:8000 in your browser to exercise the SPA."
	@echo "Press Ctrl-C to stop the server when finished."
	MNESOS_DB_PATH=artifacts/mnesos-e2e.db MNESOS_STATIC_DIR=src/MnesOS/static OPENROUTER_BASE_URL=$${OPENROUTER_BASE_URL:-} $(PY) -m uvicorn MnesOS.api.app:app --host 0.0.0.0 --port 8000

package:
	$(PY) -m build

full-ci: python-test web-test e2e package

clean:
	rm -rf dist build src/MnesOS/static web-client/node_modules
	find . -name "__pycache__" -type d -exec rm -rf {} +
