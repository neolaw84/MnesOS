# Makefile for MnesOS common developer tasks

# Platform detection
ifeq ($(OS),Windows_NT)
    # Windows commands
    RM = del /f /q
    RMDIR = rd /s /q
    MKDIR = mkdir
    CP = xcopy /e /i /y
    VENV_BIN = Scripts
    # Path handling helper
    FIXPATH = $(subst /,\,$1)
    SET_ENV = set $1 &&
    P = $(subst /,\,$1)
else
    # Linux/macOS commands
    RM = rm -f
    RMDIR = rm -rf
    MKDIR = mkdir -p
    CP = cp -r
    VENV_BIN = bin
    FIXPATH = $1
    SET_ENV = $1
    P = $1
endif

VENV=venv
PY=$(call P,$(VENV)/$(VENV_BIN)/python)
PIP=$(call P,$(VENV)/$(VENV_BIN)/pip)
NPM=npm
PLAYWRIGHT=npx playwright

.PHONY: help setup python-test web-test build stage e2e package full-ci clean sync-refs

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
	@echo "  sync-refs     Synchronize docs/ to standalone agent skill references/ directories"
	@echo "  package       Build Python wheel and sdist"
	@echo "  full-ci       Run python-test, web-test, build+stage, e2e, package"
	@echo "  clean         Clean build artifacts"

setup:
	python -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PIP) install -e ".[dev]"
	git config core.hooksPath .githooks

python-test:
	$(PY) -m pytest --maxfail=1 -q

web-test:
	cd web-client && $(NPM) ci && $(NPM) run test:coverage

build:
	cd web-client && $(NPM) ci && $(NPM) run build

stage:
	$(RMDIR) $(call FIXPATH,src/MnesOS/static) || (exit 0)
	$(MKDIR) $(call FIXPATH,src/MnesOS/static)
	$(CP) $(call FIXPATH,web-client/dist/.) $(call FIXPATH,src/MnesOS/static/)

e2e: build stage
	cd web-client && CI=true $(PLAYWRIGHT) test --project chromium

run-web:
	@echo "Starting web dev server in web-client (foreground)"
	cd web-client && $(NPM) ci && $(NPM) run dev

run-python:
	@echo "Starting backend (uvicorn) in foreground"
	$(call SET_ENV,PYTHONPATH=src) $(call SET_ENV,MNESOS_DB_PATH=artifacts/mnesos.db) $(call SET_ENV,MNESOS_STATIC_DIR=src/MnesOS/static) $(call SET_ENV,OPENROUTER_BASE_URL=http://127.0.0.1:8899/api/v1) $(PY) -m uvicorn MnesOS.api.app:app --reload --host 0.0.0.0 --port 8000

run-e2e: build stage
	@echo "Starting backend for manual E2E (uses real OpenRouter)."
	@echo "Visit http://localhost:8000 in your browser to exercise the SPA."
	@echo "Press Ctrl-C to stop the server when finished."
	$(call SET_ENV,PYTHONPATH=src) $(call SET_ENV,MNESOS_DB_PATH=artifacts/mnesos.db) $(call SET_ENV,MNESOS_STATIC_DIR=src/MnesOS/static) $(call SET_ENV,OPENROUTER_BASE_URL=$(OPENROUTER_BASE_URL)) $(PY) -m uvicorn MnesOS.api.app:app --reload --host 0.0.0.0 --port 8000

sync-refs:
	@echo "Synchronizing docs/ to standalone agent skill references/ directories"
	$(PY) scripts/sync_skill_references.py

package: sync-refs build stage
	$(PY) -m build

full-ci: python-test web-test e2e package

clean:
	$(RMDIR) dist build $(call FIXPATH,src/MnesOS/static) $(call FIXPATH,web-client/node_modules) || (exit 0)
ifeq ($(OS),Windows_NT)
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
else
	find . -name "__pycache__" -type d -exec rm -rf {} +
endif
