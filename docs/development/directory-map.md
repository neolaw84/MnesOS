# MnesOS Directory Map & Runtimes

This document outlines the repository layout and technology stack for MnesOS to help locate files efficiently.

## Environment & Runtimes
- **Type of Project**: Python backend library & engine serving a built React single-page application (SPA).
- **Core Languages**: Python (>=3.12) & TypeScript/JavaScript.
- **Frameworks & Tooling**: `langgraph`, `FastAPI`, `pytest`, React, Vite, `vitest`, `playwright`, `mkdocs`.

## Repository Architecture

### `src/MnesOS/`
Main Python source code housing the stateless core engine.
- **`graph.py` / nodes**: LangGraph setups, agent states, and specialized tool execution logic.
- **API & Middleware**: FastAPI routing, auth abstraction layers, and side-by-side credential verification.
- **Static Assets**: Staging target (`src/MnesOS/static/`) for built frontend SPA bundles served via FastAPI `StaticFiles`.

### `web-client/`
The modern React frontend interface built with Vite and TypeScript.
- **Important Configs**: `package.json`, `vite.config.ts`, `playwright.config.ts`.
- **Integration**: Communicates with the stateless backend REST API, handling in-flight authentication credentials.

### `cartridges/`
Preconfigured "game discs" containing game-specific content, logic, and runtime parameters. Each game folder contains:
- **`yare.yaml`**: Deterministic game logic, variables, and procedural turn-based events using the YARE specification.
- **`bot_lore.md`**: Core markdown-based background lore used for contextual vector embeddings/retrieval.
- **`prompt_directives.yaml`**: Directives for LLM personas (`director`, `npc`, `narrator`). Use `bot_memory` to refer to game state here. **Never** embed this directive text directly into `yare.yaml`.
- **`first-message.md`**: Optional initial prompt to kickstart the narrative engine.

### Supporting Directories
- **`docs/`**: Centralized knowledge base, design documents, language specs, and routing indexes.
- **`scripts/`**: Utility workflows (`delete_db.py`, `migrate_db.py`, `setup_github_rules.py`, `create_cartridge.py`).
- **`tests/`**: Mapped unit and integration validations executed via `pytest`. Configuration managed in `pyproject.toml`.
