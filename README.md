# MnesOS

MnesOS is an agentic RPG engine that separates deterministic game mechanics from LLM-driven narration.

[![PyPI version](https://badge.fury.io/py/MnesOS.svg)](https://badge.fury.io/py/MnesOS)
[![Documentation](https://img.shields.io/badge/docs-gh--pages-blue)](https://neolaw84.github.io/MnesOS/)

## What It Does

MnesOS combines four concerns into a single turn pipeline:

- `VectorLoreStore` retrieves relevant lore from `bot_lore.md`
- the Director LLM maps player intent to YARE events
- `YAREInterpreter` applies deterministic state changes
- the Director can query NPC intents via the `query_npc_intent` tool
- the Narrator LLM reacts to the resolved turn
The engine state is explicit. The caller passes a `GameState` into `app.invoke(...)` and receives the updated state back.

## Turn Model

The graph itself is stateless between invocations. The client is responsible for persisting and re-supplying the returned game state for the next turn.

- `client_messages`: persistent story history owned by the caller
- agent message lists: per-node, per-turn working prompts rebuilt on each invocation
- `bot_memory`: persistent deterministic world state

## Cartridge Layout

Each cartridge lives under `cartridges/<name>/` and contains:

- `yare.yaml`: procedural rules and state schema
- `bot_lore.md`: markdown lore used for retrieval
- `prompt_directives.yaml`: optional LLM directives for `director`, `npc`, and `narrator`

`prompt_directives` must not be embedded in `yare.yaml`; the loader rejects that configuration.

## Installation

```bash
pip install MnesOS
```

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,docs]"
```

### Run Tests

```bash
python -m pytest
```

### Build Docs

```bash
mkdocs build
```

## Further Reading

- `docs/architecture.md`: current graph architecture and turn flow
- `docs/cartridge-guide.md`: cartridge authoring guidance
- `docs/yare-specification.md`: supported YARE syntax and execution rules

## License

MIT.
