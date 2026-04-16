# YARE Specification

YARE is the deterministic rules layer used by MnesOS. It is interpreted by `YAREInterpreter` and is intentionally narrower than general Python.

## Top-Level Structure

```yaml
version: "1.0"
state_schema:
  domain:
    field: { type: int|float|string|bool|list, default: 0, min: 0, max: 10, visibility: public }
macros:
  macro_name: "@ expression"
events:
  event_name:
    inputs: [arg1, arg2]
    steps: []
```

## Expressions

Expressions are strings starting with `@`.

Available roots:

- `state.*`
- `temp.*`
- `inputs.*`
- `macros.*`

Supported operators in the current interpreter:

- arithmetic: `+`, `-`, `*`, `/`, `//`, `%`
- comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`
- boolean: `and`, `or`, `not`
- unary: unary `+` and unary `-`

Supported built-ins in the current interpreter:

- `roll(NdX)` (Note: Do **not** put quotes around the dice notation. Write `roll(1d20)` instead of `roll('1d20')`)
- `abs(value)`
- `timedelta(...)`
- `time_delta(timestamp_a, timestamp_b)` (returns `timestamp_b - timestamp_a` as a `timedelta`)

Not currently supported:

- `floor`, `ceil`, `round`
- `now()`
- arbitrary Python literals or function calls outside the whitelist

## State Visibility

`visibility` is optional in `state_schema` and defaults to `private`.

- `public` fields can be exposed to the narrator context through `get_public_state`
- `private` fields are blocked from direct `@ state...` access inside interpreter expressions

## Step Types

### `set`

Assigns a literal or expression result to `state.*` or `temp.*`.

### `mutate`

Applies one of `add`, `sub`, `mul`, or `div`, then clamps to schema `min` and `max` when present.

### `branch`

Evaluates conditions in order and executes only the first matching branch.

Else branches are written as:

```yaml
- else: true
  steps:
    - action: note
      message: "Fallback branch"
```

### `table_roll`

Evaluates `roll`, then maps the result through a table using exact values, ranges like `1-5`, or open-ended ranges like `11+`.

### `call`

Invokes another event. Calls are allowed, but execution depth is capped at 10.

### `list_push`

Appends an item to an array stored at a `state.*` or `temp.*` path. Creates an empty list if the path does not yet exist.

```yaml
- action: list_push
  var: "state.player.inventory"
  item: "'Health Potion'"
```

The engine enforces a hard cap of `MAX_CONTAINER_SIZE` (100) items. Attempting to push beyond this limit raises an error.

### `list_remove`

Removes an item from a list by **index** or by **value**. Exactly one of `index` or `value` must be provided. If the index is out of range, or the value is not found, the list is left unchanged.

```yaml
# Remove by zero-based index
- action: list_remove
  var: "state.player.inventory"
  index: 0

# Remove by value
- action: list_remove
  var: "state.player.inventory"
  value: "'Health Potion'"
```

### `dict_set`

Sets a key-value pair on a dict stored at a `state.*` or `temp.*` path. Creates an empty dict if the path does not yet exist.

```yaml
- action: dict_set
  var: "state.world.flags"
  key: "'bridge_repaired'"
  value: true
```

The engine enforces `MAX_CONTAINER_SIZE` (100) keys per dict and `MAX_DICT_DEPTH` (3) nesting levels. Either limit being exceeded raises an error.

### `dict_delete`

Removes a key from a dict. If the key is absent, the action is a no-op.

```yaml
- action: dict_delete
  var: "state.world.flags"
  key: "'bridge_repaired'"
```

### `foreach`

Iterates a list and executes nested steps once per item.

Example:

```yaml
- action: foreach
  array: "@ state.player.inventory"
  item: item
  index: idx
  steps:
    - action: note
      message: "Item {inputs.idx}: {inputs.item}"
```

### `note`

Appends a string to the interpreter note buffer. `{...}` interpolation is supported and each expression inside braces is evaluated as YARE.

## Execution Model

1. The caller provides current state and event inputs
2. Steps execute sequentially
3. `temp` acts as event-local scratch state
4. `mutate` respects schema bounds when defined
5. `note` accumulates engine observations for later narration
6. Events with `trigger_on: cycle_tick` are automatically executed once per turn cycle before Director logic

YARE is deterministic except where the rules explicitly use `roll(...)`.

## LLM Tool Interface

YARE events are exposed to the LLM through a single LangChain tool:

```python
@tool
def trigger_event(
    event_name: str,
    event_args: dict | None = None,
    # tool_call_id and state are injected — not visible to the LLM
) -> Command:
    """Trigger a named YARE rules event with optional input arguments."""
```

`ToolNode` calls this tool directly. It accesses the full `GameState` via `InjectedState`, runs `YAREInterpreter.run_event(event_name, event_args)`, and returns a `Command` that updates `bot_memory_staging`, `system_notes`, and appends a `ToolMessage` with the event notes. The `post_tools_node` then commits the `bot_memory_staging` update.

### Event Signature Injection

The LLM needs to know which keys belong in `event_args` for each event. Both `director_node` and `npc_brain_node` (when enabled) read the `inputs` lists from `yare_config` and inject event signatures into the system prompt:

```
### Available Events:
- combat_strike(event_args: {attacker, defender, power})
- cast_spell(event_args: {spell_name, mana_cost})
```

This means the LLM receives enough information to populate `event_args` correctly without seeing the full `yare.yaml`.

New events are added in `yare.yaml`. No code changes are required to expose them — the graph reads event signatures dynamically at each invocation.

## Time Sync Extensions

- `state.game_time` is automatically injected into Director, NPC Brain (when enabled), and Narrator prompt context when present.
- Narrator uses a structured tool call for end-of-turn engine actions:
  - `end_of_narration(actions=[{"type":"advance_time","duration":"PT15M"}])`
  - `end_of_narration(actions=[{"type":"set_game_time","value":"2026-04-10T10:00:00+00:00"}])`
- This replaces inline tag parsing and leaves player-facing narration content unchanged.
