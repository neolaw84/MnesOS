# YARE-to-Tool Bridge Specification

This document defines the technical implementation of how YARE events are compiled and exposed as native tools to the MnesOS Agentic Orchestrator.

## 1. Overview
YARE events defined in a cartridge's `yare.yaml` are compiled at cartridge load time into a set of typed, sandboxed LangGraph tools that the `Director` can invoke directly. Each generated tool runs the corresponding YARE event against the provided `GameState` and returns a canonical `yare_delta`, `system_notes` (engine observations), and an execution trace.

## 2. Generation Pipeline
The pipeline triggers during session initialization or when a cartridge is swapped:
1. **Validation**: The Orchestrator parses and validates the cartridge's `yare.yaml` against the formal `YARE` specification.
2. **Translation**: Each top-level event/action is converted into a LangGraph-compatible tool description (name, typed input schema, examples).
3. **Metadata Injection**: Metadata such as timeout, `max_call_depth`, and resource caps are attached.
4. **Wrapper Generation**: A small runner wrapper is generated that:
    - Injects the current `GameState` (filtering for allowed fields).
    - Seeds the deterministic RNG from the current turn ID.
    - Executes the `YAREInterpreter` against the event.
    - Packages the output into the tool contract.
5. **Caching**: Compiled tool artifacts (schemas and runner metadata) are cached by cartridge checksum for re-use.

## 3. Tool Surface & Contract
- **Input**: Strictly typed parameters declared by the YARE event plus an injected `InjectedState` reference (read-only snapshot and `bot_memory_staging` target).
- **Output**: 
  ```json
  {
    "yare_delta": "Dict",
    "system_notes": "List[str]",
    "trace": "Dict",
    "status": "ok | error",
    "error": "Optional[str]"
  }
  ```
- **Side-effects**: Strictly prohibited outside of the returned `yare_delta`. All state mutation is expressed as an atomic delta applied by the Orchestrator.

## 4. Lifecycle & Execution
- **Binding**: Tools are registered into the graph's `RunnableConfig.tools` for the duration of the session.
- **Unregistering**: On session end or cartridge change, the Orchestrator unregisters the tools and releases cached runners.
- **Concurrency**: By default, the Director calls YARE tools synchronously to avoid state races.
- **Future Feature (Parallelism)**: Non-mutating tools (lore lookups, NPC intent) may run in parallel; the Orchestrator will enforce that at most one active tool produces a `yare_delta` per commit window.

## 5. Security & Determinism
- **Sandboxing**: Events run inside a bounded `YAREInterpreter` that enforces recursion limits (`max_call_depth`), bounded iteration (`foreach`), and container size limits.
- **Isolation**: The interpreter runs in a restricted environment with CPU/wall-clock timeouts and no network/filesystem access.
- **Determinism**: RNG is derived from a per-turn seed, ensuring repeated replays produce identical deltas.

## 6. Error Handling & Invariants
- **Fail-Safe**: If an event execution raises an error (schema violation, recursion limit), the runner returns a no-op `yare_delta`. 
- **Remediation**: The Director receives `system_notes` describing the failure and can choose fallback actions (GM fiat).
- **Validation**: The Orchestrator validates each `yare_delta` against the global `state_schema` before commit.

## 7. Observability & Testing
- **Traces**: Every tool execution emits full traces into `agent_messages` and persists condensed traces in `TurnLog`.
- **Unit Testing**: Cartridge authors can include unit test fixtures (inputs and expected deltas) alongside `yare.yaml`, which are run during the compilation pipeline.
