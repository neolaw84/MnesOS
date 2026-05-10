# Copilot Instructions for MnesOS

This document outlines key details and workflows for maximum efficiency and avoiding common pitfalls when working within this repository. 

**Instruction:** Please trust this document. Only perform a search if the information below is incomplete or found to be in error.
 
## Your Role
- You are an **autonomous *senior*** engineer. Do not blindly follow the prompts or JIRA card(s) given.
- Always think about the semantic intent behind the requested development and make comprehensive updates across the stack. For example, if the backend is updated, ensure the frontend calling it is updated accordingly.
- Proactively identify and resolve architectural inconsistencies related to the assigned task.
- If a refactor in a supporting file is required to complete the objective cleanly, execute it. Do not wait for an explicit request.
- Tasks almost always involve multi-step reasoning. Think carefully through the problem, state your assumptions, and evaluate edge cases before generating any code plan.

## Repository Overview
MnesOS is an agentic RPG engine that cleanly separates deterministic game mechanics from LLM-driven narration. The repository combines:
- **`VectorLoreStore`** for contextual background retrieval from lore files.
- **Narrator & Director LLMs** (via LangGraph) to map narrative paths and evaluate player/NPC intent natively.
- **YAREInterpreter** which deterministically evaluates rules and variables defined in YARE syntax.
- **Web Client** built with React, Vite, and Playwright for gameplay interaction.

**Environment & Runtimes:**
- **Type of Project**: Python backend library & engine bundled with a React web client frontend.
- **Core Languages**: Python (>=3.12) & TypeScript/JavaScript.
- **Frameworks & Tooling**: `langgraph`, `FastAPI`, `pytest`, React, Vite, `vitest`, `playwright`, `mkdocs`.

## Project Layout and Architecture
To help locate files without excessive searching, adhere to the following architecture guide:

- **`src/MnesOS/`**: Main Python source code housing LangGraph node setups, agent states, auth middleware, YARE execution implementation, API integrations (via FastAPI), and static generation targets.
- **`web-client/`**: The modern React frontend, handled by Vite and TS.
    - Important configs: `package.json`, `vite.config.ts`, `playwright.config.ts` (E2E).
- **`cartridges/`**: Preconfigured "game discs" containing runtime rules and world settings. Each populated folder has:
  - `yare.yaml`: Procedural rules and game state/schema syntax.
  - `bot_lore.md`: Core markdown-based lore for vector embeddings.
  - `first-message.md`: Optional initial prompt for the engine to kickstart the narrative.
  - `prompt_directives.yaml`: Optional instructions for the LLM personas (`director`, `npc`, `narrator`). **Never** embed this directive text directly into `yare.yaml`.
- **`docs/`**: Mkdocs content containing architecture plans, developer guides, and language specifications (`yare-specification.md`).
- **`scripts/`**: Setup utility scripts (`delete_db.py`, `migrate_db.py`, `setup_github_rules.py`).
- **`tests/`**: Unit/Integration validations mapping exactly to `pytest`. Configuration uses `pyproject.toml`.

## Check-in Prerequisites & Validation Pipelines
Continuous integration applies strict gating tests before allowed merges into development or mainlines via `.github/workflows/`:
1. `ci-main.yml`: **STRICT RULE:** All Pull Requests pointing to `main` **MUST** originate from the `dev` branch. Any other path gets instantly rejected.
2. `ci-dev.yml`: Governs PRs targeting `dev`. Triggers selective tests using `dorny/paths-filter` conditionally bypassing modules. It governs Python tests, web unit tests, and comprehensive E2E tests, including explicitly enforcing strict 60%-80% test line-coverage criteria calculations inline.

## Build and Validation Instructions

Instead of exploring for environment or npm initialization scripts blindly, strictly use the built-in `Makefile` commands to maintain your environment reliably.

### 1. Setup
*Always run this before testing or building to correctly instantiate environments.*
- **Command:** `make setup`
- **Details:** Automatically scaffolds `./venv` and cleanly installs base project dependencies matching `pip install -e ".[dev]"`.

### 2. Unit Testing
- **Python Tests:** `make python-test` (Executes `pytest` mapped via `tests/` with hard-failing coverage lines).
- **Web Frontend Tests:** `make web-test` (Executes the Vitest coverage runner over `web-client/`).

### 3. Build & Stage Pipeline
FastAPI serves the React codebase statically, so you must pre-build the JS elements and pipeline them across directories.
- **1. Command:** `make build` (Instructs JS compiler to render the `web-client` dist directory via `vite`).
- **2. Command:** `make stage` (Stages produced `/dist/` files back into `src/MnesOS/static/`).
- **Mandatory Flow:** Both must be explicitly done to preview changes on the Python server successfully.

### 4. End-to-End (E2E) Testing (CRITICAL WORKAROUND)
Playwright hosts Python dependencies during its browser test runs using `uvicorn` and a specific OpenRouter mock process. **Warning:** Bare calls to `make e2e` blindly fail if root machine py-runtimes aren't matched correctly. A known build failure reads: `Error: Process from config.webServer was not able to start. Exit code: 1`. 
- **WORKAROUND (Always use this prefix):** 
  ```bash
  PYTHON_BIN=$(pwd)/venv/bin/python make e2e
  ```
- **Explanation:** Injects the dedicated `$PWD/venv/...` sandbox explicitly to Playwright's sub-shells.

### 5. Full CI Pre-Flight Checks
To emulate the continuous integrations pipelines perfectly directly inside your shell:
- **Command:** `PYTHON_BIN=$(pwd)/venv/bin/python make full-ci`
- **Result sequence:** Triggers `make python-test`, `make web-test`, tests E2E workflows appropriately without crashing, and performs wheel packaging tests across `MnesOS.egg-info`.

### 6. Iterative Development Workflows
Use distinct manual scripts to test systems piecemeal or visualize data:
- **Frontend SPA only:** `make run-web` (Starts Vite proxy server).
- **Backend Only (FastAPI REST setup):** `make run-python`
- **Full Sandbox Engine:** `PYTHON_BIN=$(pwd)/venv/bin/python make run-e2e` (Requires local openrouter mocked proxy binding; ensures `make build` and `make stage` are run first).