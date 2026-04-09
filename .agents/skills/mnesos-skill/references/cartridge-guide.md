# Cartridge Guide

This guide describes how to build and validate a MnesOS cartridge.

## Cartridge Contract

Create a cartridge under `cartridges/<your-game-name>/`.

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

Example:

```markdown
# Crossroads
The crossroads is the first safe settlement outside the ruined highway.

## Goblin Scout
A cautious scavenger who avoids direct combat unless cornered.
```

### `yare.yaml`

Use this file for deterministic state and event logic.

- `state_schema` defines tracked state and defaults
- `macros` define reusable `@` expressions
- `events` define executable steps
- supported actions are `set`, `mutate`, `branch`, `table_roll`, `call`, and `note`

Example:

```yaml
state_schema:
  player:
    hp: { type: int, default: 100, min: 0, max: 100, visibility: public }
  npc:
    hp: { type: int, default: 20, min: 0, visibility: public }

events:
  deal_damage:
    steps:
      - action: mutate
        var: state.npc.hp
        op: sub
        value: 10
      - action: note
        message: "Player deals 10 damage."
```

### `prompt_directives.yaml`

Use this file only for short per-role LLM steering.

Allowed keys:

- `director`
- `npc_brain`
- `narrator`

Example:

```yaml
director: "Prefer explicit mechanical events over narration-only turns."
npc_brain: "Escalate only when the NPC has a clear advantage."
narrator: "Keep the prose terse and grounded."
```

At load time the cartridge loader validates:

- only those three keys are allowed
- each value must be a string
- each value has a length cap
- total directive size has a combined cap
- obvious prompt-injection patterns are rejected

If `prompt_directives` is placed inside `yare.yaml`, the loader rejects the cartridge.

## State Visibility

Each schema field may define `visibility`.

```yaml
state_schema:
  player:
    hp: { type: int, default: 100, min: 0, visibility: public }
    mana: { type: int, default: 50, min: 0, visibility: public }
    hidden_flag: { type: bool, default: false, visibility: private }
```

Behavior:

- `public` fields are eligible for narrator context through `get_public_state`
- omitted `visibility` defaults to `private`
- direct `@ state...` access to private fields is blocked by the interpreter

This keeps hidden mechanics in deterministic state without leaking them into player-facing narration by default.

## Conversion Checklist

1. Extract all stats, resources, and flags into `state_schema`
2. Move every deterministic rule into `events`
3. Add bounds with `min` and `max` where needed
4. Mark player-visible fields with `visibility: public`
5. Move flavor text into `bot_lore.md`
6. Move tone instructions into `prompt_directives.yaml`

## Things Not To Rely On

- do not rely on hardcoded event-name matching in engine code
- do not rely on cartridge-specific NPC behavior embedded in Python nodes
- do not put prompt directives inside `yare.yaml`
- do not assume the engine persists state for you; the client must store and re-supply the returned game state each turn

## Testing

Validate the cartridge by loading it through `CartridgeLoader`, then run the graph with the returned `yare_config`, `prompt_directives`, `lore_path`, and initial state.