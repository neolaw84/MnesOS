# Cartridge Guide

This guide describes how to build and validate a MnesOS cartridge.

## Cartridge Contract

Create a cartridge under `cartridges/<your-game-name>/` (or `data/cartridges/<your-game-name>/`).

Required files:

1. `yare.yaml`
2. `bot_lore.md`

Optional file:

3. `prompt_directives.yaml`

`yare.yaml` stays procedural. Narrative steering belongs in `prompt_directives.yaml`, not in the rules file.

## What Goes Where

### `bot_lore.md`

Use this file for world facts, NPC descriptions, locations, factions, and items.

- structure content with markdown headers because the lore store chunks on `#`, `##`, and `###`
- keep mechanics out of lore text
- use descriptive section names so retrieval has strong anchors

### `yare.yaml`

Use this file for deterministic state and event logic.

- `state_schema` defines tracked state and defaults
- `macros` define reusable `@` expressions
- `events` define executable steps
- supported actions are `set`, `mutate`, `branch`, `table_roll`, `call`, and `note`

**`MAX_ITERATIONS` constraint**: The engine enforces a hard cap of `MAX_ITERATIONS = 3` tool-call
loops per phase (player phase and NPC phase independently). This means the Director and NPC Brain
each have at most 3 chances to call `trigger_event` before the engine moves on. Design your events
to be self-contained and to avoid requiring long chains of dependent calls:

- prefer a single event that calls sub-events via the `call` action rather than relying on the LLM
  to chain multiple `trigger_event` calls
- do **not** model flows like "cast → check_hit → apply_damage" as three separate events; fold the
  chain into a single event's `steps` using `branch` and `call`
- use `note` actions liberally so the LLM understands what happened without needing to make
  a follow-up tool call

### `prompt_directives.yaml`

Use this file only for short per-role LLM steering.

Allowed keys:

- `director`
- `npc_brain`
- `narrator`

## State Visibility

Each schema field may define `visibility`.

- `public` fields are eligible for narrator context through `get_public_state`
- omitted `visibility` defaults to `private`
- direct `@ state...` access to private fields is blocked by the interpreter
