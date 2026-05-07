---
name: mnesos-rpg-engine
description: Create and manage Agentic Role Play Games using the MnesOS engine. Use when the user wants to work with MnesOS cartridges, game logic, or lore.
license: MIT
metadata:
  version: "1.0"
  author: mnesos-team
---

# MnesOS Agentic RPG Engine

This skill enables you to work with the MnesOS Agentic Role Play Game (RPG) Engine.

## Key Philosophies

*   **Stateless Core:** The core gameplay loop is in `src/MnesOS/graph.py`. It is designed to be stateless and static.
*   **Game Cartridges:** All game-specific content is stored in "cartridges" located in the `cartridges/` directory. Each cartridge is a self-contained game.
*   **Deterministic Limits**: The engine allows a maximum of 3 tool calls per turn (`MAX_ITERATIONS = 3`), and LLMs do not invoke parallel tool calls. Keep complex procedural steps encapsulated via `call` steps inside `yare.yaml` events rather than assuming the LLM can resolve the turn through excessive tool-call recursion.
*   **Modernized YARE Evaluator**: The engine's `YAREEvaluator` natively supports advanced evaluation natively, meaning cartridge developers can use bracket access (`array[index]`), object attribute access (`dict.key`), dictionary/list literals, and string concatenation without needing backend engine changes.

## Cartridge Structure

A game cartridge is a directory inside `cartridges/` with the following structure:

*   `cartridges/<game-name>/`:
    *   `prompt_directives.yaml`: Contains the story direction and high-level prompts for the agent. **Important:** When referring to the game state here, use the term `bot_memory` (e.g., `If bot_memory['player']['hp'] < 10`), not `state`.
    *   `bot_lore.md`: The lore and background information for the game world and characters.
    *   `yare.yaml`: Defines the deterministic game logic, rules, and state transitions using the YARE specification.

## How to Work with MnesOS

### Creating a New Game

1.  Create a new directory under `cartridges/` with the name of your game.
2.  Inside the new directory, create the following files:
    *   `prompt_directives.yaml`
    *   `bot_lore.md`
    *   `yare.yaml`
3.  Populate these files with your game's content, following the established format.

### Modifying an Existing Game

1.  Navigate to the directory of the game you want to modify under `cartridges/`.
2.  Edit the `prompt_directives.yaml`, `bot_lore.md`, or `yare.yaml` files to change the game's story, lore, or rules.

## Development & Architecture Conventions

*   **Unified Distribution (SPA + FastAPI):** The React frontend (`web-client/`) is built and staged into the Python package (`src/MnesOS/static/`) so the FastAPI backend can serve it as a single self-contained application using `StaticFiles` with an `index.html` SPA fallback.
*   **Python Packaging:** MnesOS uses modern `pyproject.toml` configuration (`[tool.setuptools.package-data]`) to bundle the built frontend into distributions (sdists and wheels). Legacy `MANIFEST.in` is redundant and deprecated for this workflow. 
*   **Unified E2E Testing:** Playwright tests are executed against the actual FastAPI server serving the built SPA in a production-like manner, rather than against a mock Vite dev server. Absolute ESM pathing (`fileURLToPath(import.meta.url)`) and explicit separation of environments (`reuseExistingServer: false`) ensure stability and determinism in isolated test runners.
*   **Developer Orchestration:** Always use the root `Makefile` for developer tasks:
    *   `make run-web`: Start frontend dev server
    *   `make run-python`: Start backend dev server
    *   `make run-e2e`: Human validation (builds and runs front-to-back using Uvicorn)
    *   `make full-ci`: To run CI locally before PRs.

## Documentation

For more detailed information, refer to the documentation:

*   [references/architecture.md](references/architecture.md): For the overall architecture.
*   [references/cartridge-guide.md](references/cartridge-guide.md): For creating and managing cartridges.
*   [references/yare-specification.md](references/yare-specification.md): For the YARE language used in `yare.yaml`.
*   [references/architecture_analysis.md](references/architecture_analysis.md): In-depth engine architectural analysis.
*   [references/combat_mechanics.md](references/combat_mechanics.md): Deep dive into YARE combat mechanics and counter-play.

## Scripts

This skill includes scripts to help with common tasks.

*   `scripts/create_cartridge.py`: A Python script to create a new game cartridge with the required file structure.
    *   Usage: `python scripts/create_cartridge.py <game-name>`
