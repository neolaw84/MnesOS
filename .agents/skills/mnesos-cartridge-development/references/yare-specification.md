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

Supported built-ins in the current interpreter:

- `roll(NdX)`
- `abs(value)`
- `timedelta(...)`

## Step Types

### `set`
Assigns a literal or expression result to `state.*` or `temp.*`.

### `mutate`
Applies one of `add`, `sub`, `mul`, or `div`, then clamps to schema `min` and `max` when present.

### `branch`
Evaluates conditions in order and executes only the first matching branch.

### `table_roll`
Evaluates `roll`, then maps the result through a table using exact values, ranges like `1-5`, or open-ended ranges like `11+`.

### `call`
Invokes another event. Calls are allowed, but execution depth is capped at 10.

### `note`
Appends a string to the interpreter note buffer. `{...}` interpolation is supported.

## Execution Model
1. The caller provides current state and event inputs
2. Steps execute sequentially
3. `temp` acts as event-local scratch state
4. `mutate` respects schema bounds when defined
5. `note` accumulates engine observations for later narration
