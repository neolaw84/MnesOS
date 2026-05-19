# MnesOS

MnesOS is a stateless, event-sourced agentic RPG engine that can operate on a Bring-Your-Own-Key (BYOK) model. It is designed to solve the unreliability of traditional "LLM-only" RPGs by explicitly separating deterministic logic and prose generation/narration from high-fidelity orchestration.

> **Fun Fact:** The name MnesOS (pronounced NESS-O-S) is derived from the Greek goddess of memory and remembrance, "Mnemosyne". 

## 🌟 Key Features & Architecture

* **Deterministic Rules (YARE)**: All state mutation, math operations, and RNG are handled by the non-Turing complete YARE Agentic Rules Engine (YARE) rather than the LLM.

* **Air-Gapped Narration**: MnesOS utilizes a two-node LangGraph structure (Director and Narrator), isolating system mechanics and numbers from the narrative output.

* **Stateless & Branchable**: The backend retains no operational memory across network turns, employing a tree-based event source model that natively supports branching timelines.

* **Secure Identity**: Uses a zero-knowledge, side-by-side authentication approach where LLM API keys are passed in-flight via PKCE and never stored on the server.

*For comprehensive details on the engine's mechanics and design constraints, read the [Architecture Design](docs/design/architecture.md) and [Core Philosophy](docs/design/philosophy.md) documents.*

## 🚀 Getting Started

### For Players

MnesOS can be installed as a pre-compiled Python package, bundling the backend and frontend into a single instance:

```bash
pip install MnesOS[api]
uvicorn MnesOS.api.app:app --host 127.0.0.1 --port 8000

```

*Refer to the [Player Guide](docs/guides/player-guide.md) for full instructions on setting up your environment, navigating the UI, and connecting your local OpenRouter credentials.*

### For Cartridge Developers

MnesOS games are distributed as "Cartridges". A cartridge typically contains:

* `yare.yaml`: Defines the deterministic state schema and logic. Read the [YARE Specification](docs/yare-specification.md) for syntax rules and capabilities.

* `bot_lore.md`: Markdown-formatted world facts, item definitions, and NPC details used for context retrieval.

* `prompt_directives.yaml`: Per-role steering instructions for the Director, Narrator, and NPC roles.

* `first-message.md`: The opening scene of the game.

*Check the [Cartridge Developer Guide](docs/guides/cartridge-developer-guide.md) to learn about best practices, including semantic grounding and phase-based combat intention.*

### For Engine Contributors

MnesOS requires Python 3.12+ and Node.js (v20+ LTS) for full-stack, split-terminal development.

* **Setup & Testing**: Learn about `Makefile` commands, continuous integration gating rules, and test runners in the [CI/CD & Build Instructions](docs/development/ci-cd.md).

* **Codebase Structure**: Familiarize yourself with the Python/React layers and directory locations in the [Directory Map](docs/development/directory-map.md).

* **Interfaces**: Review the generated [API Reference](docs/api.md) for backend endpoint details.

## 📚 Full Documentation Map

Our detailed documentation is organized tightly by domain:

* **Core Architecture**: [Architecture](docs/design/architecture.md) | [Philosophy](docs/design/philosophy.md) | [YARE Spec](docs/yare-specification.md) | [API](docs/api.md)

* **Guides**: [Player Guide](docs/guides/player-guide.md) | [Cartridge Dev Guide](docs/guides/cartridge-developer-guide.md)

* **Development**: [Directory Map](docs/development/directory-map.md) | [CI/CD](docs/development/ci-cd.md)

* **AI Context**: [AI Knowledge Map](docs/ai-index.md)