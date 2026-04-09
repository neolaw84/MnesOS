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

- `roll(NdX)`
- `abs(value)`
- `timedelta(...)`

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

### `note`

Appends a string to the interpreter note buffer. `{...}` interpolation is supported and each expression inside braces is evaluated as YARE.

## Execution Model

1. The caller provides current state and event inputs
2. Steps execute sequentially
3. `temp` acts as event-local scratch state
4. `mutate` respects schema bounds when defined
5. `note` accumulates engine observations for later narration

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

`ToolNode` calls this tool directly. It accesses the full `GameState` via `InjectedState`, runs `YAREInterpreter.run_event(event_name, event_args)`, and returns a `Command` that updates `bot_memory`, `system_notes`, and appends a `ToolMessage` with the event notes.

### Event Signature Injection

The LLM needs to know which keys belong in `event_args` for each event. Both `director_node` and `npc_brain_node` read the `inputs` lists from `yare_config` and inject event signatures into the system prompt:

```
### Available Events:
- combat_strike(event_args: {attacker, defender, power})
- cast_spell(event_args: {spell_name, mana_cost})
```

This means the LLM receives enough information to populate `event_args` correctly without seeing the full `yare.yaml`.

New events are added in `yare.yaml`. No code changes are required to expose them — the graph reads event signatures dynamically at each invocation.