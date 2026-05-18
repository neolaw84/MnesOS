# MnesOS Core Design Philosophy

This document outlines the core engineering philosophy behind MnesOS and the expected mindset for developers and AI contributors working on the project.

## AI Engineering Mindset
When contributing to MnesOS, adhere to the following behavioral expectations:
- **Autonomous Senior Ownership**: Do not blindly follow superficial prompts or surface-level bug reports. Evaluate the deeper systemic root cause.
- **Holistic Stack Alignment**: Always maintain semantic alignment across system boundaries. If backend API structures or return models are modified, proactively locate and refactor the corresponding client ingestion logic (`web-client/`) without waiting for explicit instruction.
- **Proactive Refactoring**: If supporting files, utilities, or validation schemas must be modernized to implement a feature cleanly, perform the refactor immediately.
- **Rigorous Multi-Step Reasoning**: Think methodically through complex logic patterns, clearly stating operational assumptions and evaluating edge cases before modifying core engine state flows.

---

## Engine Architecture Philosophies

### 1. Air-Gapping Determinism from Narration
MnesOS cleanly separates numerical stat tracking from narrative immersion to solve hallucination and out-of-context mechanics reporting.
- **Deterministic Mechanics (YARE)**: All mathematical operations, item transactions, checks, and time transitions execute purely inside code-based logic triggered by the LLM. 
- **Isolated Narration**: The resulting mechanical traces are hidden as system backstage logs (`system_notes`). A decoupled `Narrator` LLM node receives only filtered public state buffers to craft rich, immersive prose without leaking raw variable states into dialogue.

### 2. Pure Stateless Core
The backend engine (`src/MnesOS/graph.py`) retains no operational memory across network turns.
- **Pure Functional Graph**: The state graph acts purely as a deterministic pure function: `f(State, Input) -> NewState`.
- **Decoupled Persistence**: The engine is strictly decoupled from the storage layer. Game state is persisted as a versioned, event-sourced timeline in the database, enabling the client to request execution from any historical point (infinite branching) without the engine maintaining session memory across network turns.
- **Event-Sourced World vs Framework State**: The game world state (`GameState`) is structurally decoupled from the AI framework's internal memory (e.g., LangGraph checkpointers). This ensures the game history is structured, queryable, and independent of the AI agent running it.
- **Strict Input Constraining**: When the world state requires a specific interaction (e.g., a mini-game or UI form), the engine natively tracks this (`_pending_interaction`) and uses a hard gate (Input Router) to bypass the LLM intent parser entirely, forcing determinism during narrative locks.

### 3. Bounded Engine Constraints
To prevent mechanical infinite loops and resource overruns, engine loops are strictly bounded:
- **Max Iterations**: LangGraph turn limits enforce a strict cap (`MAX_ITERATIONS = 3`) on consecutive autonomous tool invocations per turn.
- **Encapsulated Event Procedures**: Cartridge developers must encapsulate intricate procedural workflows within deterministic event chains (`call` directives in `yare.yaml`) rather than relying on endless recursive LLM tool-calling.
- **Modernized Evaluator Context**: The engine natively parses bracket notation (`arr[i]`), attribute access (`obj.val`), and nested literals directly inside configuration expressions without requiring core interpreter modifications.
