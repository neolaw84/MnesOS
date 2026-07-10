# Brainstorm: Replacing YARE Specs with Full JS in V8 Isolates

This document outlines the design direction, pros, cons, security implications, and developer adoption impact of replacing the custom YARE YAML/AST specification with full Javascript, executed within securely sandboxed V8 isolates.

## 1. Design Direction

Currently, YARE events are written in YAML (or Python/JS that compiles to a YAML AST) and executed via a custom `YAREInterpreter`. Shifting to full Javascript running in V8 isolates fundamentally changes the architecture from interpreting a restricted AST to embedding a full language runtime.

### Key Architectural Shifts:
*   **Runtime Engine Migration:** Replace the custom `YAREInterpreter` in the Python backend with a V8 engine integration. In a Python environment, this is typically achieved using bindings like `PyMiniRacer`, `STPyV8`, or offloading execution to an isolated Rust service using `deno_core`.
*   **State Marshalling (The Bridge):** The engine serializes the current `GameState` (JSON) into the V8 isolate, executes the Javascript event handler, and captures the returned `yare_delta`, `system_notes`, and mutations.
*   **API Injection:** Instead of a limited set of declarative actions, the V8 isolate is injected with a restricted global API (e.g., `MnesOS.updateState()`, `MnesOS.rollDice()`) that interacts safely with the host environment.
*   **Execution Model:** Cartridge load time involves bundling or parsing the JS. At runtime, when an LLM triggers an event tool, the Orchestrator boots a V8 isolate (or reuses a warmed one via isolate snapshots), injects the state, and calls the appropriate JS function.

### Event Detection (How MnesOS Discovers JS Events)
Since YARE events must be presented as LangGraph tools, the host orchestrator needs to know which functions exist, what arguments they expect, and their descriptions. There are three primary design patterns for this:

1.  **Option A: Runtime Export Querying (Recommended)**
    *   *Mechanism:* The cartridge loader evaluates `yare.js` in a setup V8 isolate and queries the module exports. If a function is exported, it is considered a YARE event.
    *   *Schema Definition:* Developers export an explicit configuration object or define schema metadata alongside the handler. For example:
        ```javascript
        export const events = {
            giveItem: {
                description: "Gives an item to a target character.",
                parameters: { targetId: "string", itemId: "string" },
                handler: (state, args) => { ... }
            }
        };
        ```
2.  **Option B: JSDoc Static AST Parsing**
    *   *Mechanism:* Use a Python AST parser (like `swc` or `babel`-based tool) to parse the file before execution.
    *   *Schema Definition:* Read functions directly from the file, extracting types and descriptions from JSDoc tags. This allows developers to write clean, standard Javascript:
        ```javascript
        /**
         * Gives an item to a target character.
         * @param {string} targetId
         * @param {string} itemId
         */
        export function giveItem(state, { targetId, itemId }) { ... }
        ```
3.  **Option C: Decorators (TypeScript/Babel)**
    *   *Mechanism:* Use TC39/TypeScript decorators to mark event handlers. While elegant, this requires compiling the TS/JS beforehand, adding compilation complexity to cartridge loading.

---

## 2. Ease of Adoption by Cartridge Developers

**Impact: Extremely Positive**

*   **Zero Learning Curve for DSLs:** Developers no longer need to learn the idiosyncrasies, limitations, or schema of the custom YARE YAML DSL. Javascript/Typescript is universally understood.
*   **Tooling & DX (Developer Experience):** 
    *   Developers can use standard IDEs (VSCode) with full intellisense, linting (ESLint), and formatting (Prettier).
    *   Typescript can be natively supported by providing a `@types/mnesos` package, allowing developers to write strictly typed logic against the game state schema.
*   **Standard Ecosystem:** Developers can utilize familiar programming constructs (loops, complex conditionals, math operations) without hoping the AST compiler supports them.
*   **Easier Testing:** Cartridge developers can write standard Jest or Mocha tests for their game logic completely independent of the MnesOS Python backend.

---

## 3. Security & Determinism

**Impact: Highly Secure**

V8 isolates were designed exactly for this use case: executing untrusted third-party code securely.

*   **Total Sandboxing:** By default, a raw V8 isolate has **no access** to the host filesystem, network, or OS environment. It only knows what is explicitly injected into its global scope.
*   **Resource Limits:**
    *   **CPU / Timeouts:** Isolates can be configured to forcefully terminate if execution exceeds a time limit (e.g., 50ms), preventing infinite loops or CPU exhaustion.
    *   **Memory / Heap Limits:** Isolates can be given a strict heap size limit (e.g., 8MB). If a cartridge tries to allocate massive arrays, V8 terminates execution safely.
*   **Determinism:** 
    *   In-game time should be passed as a non-mutable state parameter rather than relying on `Date.now()`.
    *   If seed-reproducible random numbers are not required, standard `Math.random()` can be left auto-enabled in the isolate. If repeatability is desired later, the host can inject a seeded PRNG.

---

## 4. Pros and Cons

### Pros
*   **Unbounded Expressiveness:** Developers have Turing-complete control to implement complex RPG mechanics (e.g., pathfinding, complex stat scaling, procedural generation).
*   **Engine Simplification:** The MnesOS team no longer has to maintain a custom DSL interpreter or parse trees. V8 handles all language semantics.
*   **Snapshotting:** V8 supports isolate snapshots. This is **not auto-enabled** by default; the host implementation must compile the standard library/boilerplates once and serialize the heap into a snapshot file. At runtime, new isolates can be booted from this snapshot in microseconds.
*   **Performance (Computation):** V8 JIT is highly optimized. Complex logic will run faster than a Python-based custom interpreter.

### Cons
*   **Marshalling Overhead:** Passing the game state back and forth via JSON serialization has a cost. However, **relative to LLM latency (500ms - 3000ms+), a few milliseconds of serialization overhead is completely negligible.** 
*   **Dependency Complexity:** PyV8/MiniRacer binds C++ V8 binaries to Python. This introduces cross-platform binary dependency challenges during package distribution, but is manageable.
*   **Black Box Execution:** Statically analyzing JS logic is hard. However, cartridge quality is governed by player feedback; buggy/infinite loops will naturally lead to low cartridge ratings, making static prevention unnecessary.

---

## 5. Repository Strategy

### Shall we fork this repo and maintain two versions (YAML vs V8)?
**Decision: Yes, fork/branch the repository to perform a clean break.**

Given that MnesOS does not yet have widespread public adoption, maintaining complex backward-compatibility layers (like a pluggable multi-runner architecture) is unnecessary overhead. Creating a fork or a dedicated major branch specifically for the V8 isolate execution engine is the most efficient path forward.

**Pros of a Clean Fork/Branch:**
1.  **Codebase Simplification:** We can completely strip out the custom Python `YAREInterpreter`, AST validation pipelines, and YAML translation logic.
2.  **No Legacy Baggage:** The engine doesn't need to support both runner types, keeping the runtime footprint and codebase size much smaller and easier to maintain.
3.  **Faster Development:** We don't have to write deprecation paths or migrate old cartridges; we can design the V8 bridge purely for optimal modern JS/TS patterns from day one.
