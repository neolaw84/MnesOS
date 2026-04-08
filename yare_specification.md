# YAML Agentic Rules Engine (YARE) Specification

YARE is a domain-specific language designed for deterministic state management in LLM-driven role-playing games. It follows a non-cyclic Directed Acyclic Graph (DAG) execution model to ensure security and termination in multi-tenant web environments.

## 1. Core Grammar

A YARE configuration is a single YAML document with the following top-level structure:

```yaml
version: "1.0"
state_schema:   # Variable definitions and constraints
  domain:
    variable: { type: string|int|float|bool|datetime, min: val, max: val, default: val }
macros:         # Reusable expressions (Pure functions)
  macro_name: "@ expression"
events:         # Executable procedures
  event_name:
    inputs: [arg1, arg2]
    steps: [ActionStep, ...]
```

---

## 2. Expressions (The `@` Sub-language)

Expressions are strings starting with `@`. They are evaluated within a sandboxed environment with access to:
- **`state.*`**: Access to current game state.
- **`inputs.*`**: Access to event arguments.
- **`temp.*`**: Access to local step variables.
- **`macros.*`**: Invocations of defined macros.

### 2.1 Operators
`+`, `-`, `*`, `/`, `%`, `==`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `not`

### 2.2 Built-in Functions
- `roll(NdX)`: Standard dice notation.
- `abs(val)`, `floor(val)`, `ceil(val)`, `round(val)`: Standard math.
- `timedelta(days=0, hours=0, minutes=0)`: Time math.
- `now()`: Current engine time (from `state.time`).

---

## 3. Vocabulary (Action Steps)

Steps are executed sequentially within an event.

### 3.1 `set`
Assigns a value to a variable.
- `var`: Target path (e.g., `temp.score` or `state.player.status`).
- `value`: Literal or `@ expression`.

### 3.2 `mutate`
Performs an arithmetic operation while respecting `min`/`max` schema bounds.
- `var`: Target path (must be numeric).
- `op`: `add` | `sub` | `mul` | `div`.
- `value`: Literal or `@ expression`.

### 3.3 `branch`
Conditional execution path.
- `conditions`: Array of `{ if: "@ expr", steps: [...] }`.
- Optional: Last item can be `{ else: { steps: [...] } }`.

### 3.4 `table_roll`
Maps an expression result to a value using a lookup table.
- `var`: Target path.
- `roll`: `@ expression` (usually a dice roll).
- `table`: Map of `range` or `value` to `result`. Supporting ranges like `10-12` or `15+`.

### 3.5 `call`
Invokes another event (procedure call).
- `event`: Name of the event to execute.
- `args`: Mapping of `{ input_name: "@ expression" }`.
- *Note: Execution depth is capped at 10 to prevent cycles.*

### 3.6 `note`
Emits an irrefutable observation to the Narrator LLM.
- `message`: Literal or string interpolation with `{expression}` syntax.

---

## 4. Execution Model

1. **State Injection**: The engine loads the current `state` object.
2. **Context Resolution**: `inputs` are mapped to the local scope.
3. **Step Sequence**: Steps are processed linearly. 
4. **Boundary Enforcement**: Every `mutate` action verifies the result against the `state_schema`.
5. **Output**: The engine returns the modified `state` and the accumulated `notes`.

> [!IMPORTANT]
> To maintain the DAG nature, recursion is prohibited. Parallel execution is not supported. All state changes are immediate and atomic within the event execution.
