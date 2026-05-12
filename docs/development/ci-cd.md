# MnesOS CI/CD Pipelines & Build Instructions

To ensure consistent builds and prevent environment issues, developers and AI agents must strictly utilize built-in `Makefile` commands rather than invoking direct package manager scripts.

## Continuous Integration Gating Rules
Automated workflows in `.github/workflows/` enforce strict merge criteria:
1. **Targeting Main (`ci-main.yml`)**: **STRICT RULE**: All Pull Requests targeting the `main` branch **MUST** originate directly from the `dev` branch. Any other origin path is instantly rejected.
2. **Targeting Dev (`ci-dev.yml`)**: Uses selective execution (`dorny/paths-filter`) to conditionally run Python unit tests, Web frontend tests, and E2E browser tests. Explicitly enforces a strict 60%-80% test line-coverage criteria inline.

---

## Local Development & Verification Commands

### 1. Environment Initialization
Always run this before testing or building to instantiate environments correctly.
- **Command**: `make setup`
- **Details**: Scaffolds a virtual environment (`./venv`) and installs core project dependencies in editable mode (`pip install -e ".[dev]"`).

### 2. Unit Testing
- **Backend (Python)**: `make python-test` executes `pytest` targeting the `tests/` directory with enforced line coverage thresholds.
- **Frontend (Web)**: `make web-test` executes `vitest` coverage runners across `web-client/`.

### 3. Frontend Build & Staging Pipeline
Because FastAPI statically serves the React application bundle, JS assets must be compiled and moved into the backend source directory.
1. **Compile**: `make build` triggers Vite to render static assets to `web-client/dist/`.
2. **Stage**: `make stage` copies compiled assets into `src/MnesOS/static/`.
> **Mandatory Flow**: Both commands must run sequentially to reflect UI updates when serving from the Python backend.

### 4. End-to-End (E2E) Browser Testing
Playwright launches the FastAPI server via `uvicorn` using a dedicated OpenRouter mock proxy. 
> [!WARNING]
> Bare calls to `make e2e` or `make run-e2e` will fail if the global system Python runtime differs from the virtual environment. A common error reads: `Error: Process from config.webServer was not able to start. Exit code: 1`.

- **CRITICAL WORKAROUND**: Always prefix E2E execution with the absolute path to the virtual environment binary:
  ```bash
  PYTHON_BIN=$(pwd)/venv/bin/python make e2e
  ```

### 5. Full Pre-Flight CI Checks
To perfectly emulate remote GitHub Actions checks locally before pushing code:
- **Command**: `PYTHON_BIN=$(pwd)/venv/bin/python make full-ci`
- **Sequence**: Executes `make python-test`, `make web-test`, sandbox-isolated E2E tests, and wheel packaging tests across `MnesOS.egg-info`.

### 6. Local Dev Servers
Execute components individually during active feature iteration:
- **Frontend SPA Client Only**: `make run-web` starts the Vite dev server proxy.
- **Backend API REST Only**: `make run-python` starts the FastAPI process.
- **Full Sandbox Play Loop**: `PYTHON_BIN=$(pwd)/venv/bin/python make run-e2e` runs the fully compiled stack with local OpenRouter mock proxying. Ensure `make build` and `make stage` are run first.
