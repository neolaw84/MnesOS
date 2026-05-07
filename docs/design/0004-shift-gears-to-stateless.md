# MnesOS Alpha: Architectural Design & Evolution Report

## Executive Summary
This document outlines the strategic pivot for the MnesOS RPG engine from a stateful, local-first prototype to a stateless, event-sourced web architecture. The primary goal is to support an Alpha web application that allows for branching timelines, state manipulation ("authorized cheating"), and a scalable four-tier physical deployment model.

---

## 1. Core Architectural Shift: From Stateful to Stateless
The current `Orchestrator` maintains an internal `_state` across turns. To support web environments, the Orchestrator will be refactored to be **stateless**.

### Key Decisions:
- **Hydrate on Demand:** Every turn begins with a "Hydration" phase where the state is reconstructed from a `TurnLog` ID.
- **Persistence via Delta:** The Orchestrator no longer saves the entire state; it extracts the `yare_delta` (from `bot_memory_staging`) and appends it to the event store.
- **Stateless Loop:** The backend service receives a `parent_turn_id` and `user_input`, processes the turn, and returns a `new_turn_id`.

---

## 2. Event Sourcing & Tree-Based State
We have moved away from a flat table of turns to a **Tree-based Event Source** model. This allows players to branch timelines and "save" at any specific point in the story.

### Updated Data Models:
- **TurnLog (The Node):**
    - `parent_id`: Links back to the previous state, enabling the tree structure.
    - `yare_delta`: The atomic state changes made during this specific turn.
    - `narrator_text`: Explicitly stored to prevent re-running the graph to see old dialogue.
- **GameSave (The Bookmark):**
    - A simple pointer to a specific `TurnLog.id`. This allows users to have multiple "save files" pointing to different branches of the same game instance.

### State Hydration Logic:
To reconstruct `bot_memory` at any given node:
1. Traverse up the `parent_id` chain to the root.
2. Reverse the list (Root -> Target Node).
3. Sequentially apply every `yare_delta` and message to a blank state object.

---

## 3. GameState Cleanup (Removal of Bloat)
The `GameState` was identified as containing redundant static data. To optimize performance and token usage, we are separating **Static Context** from **Live State**.

### Items Removed from Persistent State:
- `yare_config`, `prompt_directives`, `lore_path`, `lore_content`, `persona_context`.
- **Reasoning:** These are derived from the `CartridgeVersion` and do not change. They will be passed into the graph via `RunnableConfig` (LangChain) rather than being carried in the state dictionary.

### Items Kept in Persistent State:
- `client_messages`: The primary story history.
- `bot_memory`: The current mechanical state of the world.

---

## 4. Four-Tier Physical Deployment Model
The application is designed to be physically decoupled into four layers. Notably, the **App Server (Tier 2)** can run as a **Bundled Backend (Local Sidecar)** on Desktop/Mobile for full anonymity, or on the Cloud.

| Layer | Component | Physical Location |
| :--- | :--- | :--- |
| **Tier 1: Client** | UI (Web/React/Mobile/Desktop) | User's Device |
| **Tier 2: App Server** | FastAPI / Orchestrator | Localhost (Sidecar) or Cloud VM |
| **Tier 3: Persistence** | SQLite / PostgreSQL | Local Disk or Managed Server DB |
| **Tier 4: Cognitive** | LLM Provider Factory | Remote API (OpenRouter / MnesOS Proxied) or Local LLM |

*Note: MnesOS Credits are treated symmetrically as just another LLM Provider at Tier 4. When a Local Sidecar uses MnesOS Credits, it calls a protected MnesOS Server endpoint for atomic credit deduction.*

---

## 5. Security & Accounting (Aspect-Oriented Design)
By making the Orchestrator stateless, we can apply "Aspects" (Middleware/DI) to handle cross-cutting concerns before the game logic fires.

- **Authorization Aspect:** Ensures `request.user_id == target_save.user_id`. Players cannot view or modify turns in trees they do not own.
- **Accounting Aspect:** Uses a **Side-by-Side Auth** model. The identity token (MnesOS DB Auth) and the LLM provider credential (e.g., OpenRouter PKCE token) are passed "in-flight" via headers and resolved *before* graph execution via a Registry Pattern. LLM Keys are never persisted server-side.
- **Cheat-Friendly Policy:** We embrace user-driven state manipulation. Since the system is event-sourced, "cheating" is simply the injection of a `SYSTEM` actor turn with a custom `yare_delta`. The engine handles this natively without breaking the timeline.

---

## 6. Next Steps for Alpha Development
1. **Refactor `Orchestrator.process_turn`** to accept a `parent_turn_id` and return a result object containing the delta.
2. **Update `sqlite3_store.py`** to support the `parent_id` column and the `GameSave` table.
3. **Implement the `Hydrator` utility** to reconstruct state from the TurnLog tree.
4. **Expose the REST API** using a framework like FastAPI, utilizing Dependency Injection for the Auth and Accounting layers.