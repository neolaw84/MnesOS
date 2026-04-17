# MnesOS Architectural Analysis: Two-Node Graph

This report addresses the architectural analysis of the `YARE interpreter` and the `Agentic Game Graph` found in the MnesOS core engine.

## 1. YARE Interpreter Analysis

### Completeness and Fit for Purpose
The YAML Agentic Rules Engine (YARE), defined in `src/MnesOS/interpreter.py`, is **not strictly Turing Complete** — and this is an optimal and intentional design choice. 
- **What it lacks**: It does not support unbounded looping (there are no `while` or `for` loops within the DSL) and explicitly limits recursion (nested event calling depth is hard-capped at `max_call_depth = 10`).
- **What it provides**: It supports robust conditional branching (`if`/`else` condition logic via the `branch` action), sequential execution, arbitrary nested state mutation (`mutate`, `set`), deterministic RNG (`roll`), and nested state reading.
- **Why it fits**: In the context of an LLM-backed game engine, evaluating deterministic game logic *must always* halt in a predictable timeframe. Allowing Turing-complete boundless loops inside a configuration file would risk the game entering an infinite loop during a tool call, crashing the session entirely. By capping recursion and removing infinite loops, YARE guarantees safe, bounded execution (Total Turing completeness).

### Influence on Narration
A recurring flaw in many LLM-run games is exposing literal dice rolls and rule variables mid-sentence (the "out-of-context numbers" problem). YARE solves this elegantly by air-gapping the system output from the narrative output:
- YARE modifies the state backstage and can emit structured logging details via the `note` action (e.g., `"Player rolled 12 on lockpicking, Chest unlocked"`).
- In `graph.py`, these interpreter logs are collected as `notes` and bundled into `system_notes`, which operates alongside the `agent_messages` history as invisible, LLM-only context.
- **The actual rendering mechanism**: Because the numbers never surface directly to the client's conversation history (`client_messages`), YARE does not spit out raw logs to the user. Instead, the final log of events (`system_notes`) and the `public_state` are routed to an independent **Narrator** LLM node. The Narrator acts as the "renderer", taking the raw deterministic outcomes and converting them flavorfully into high-quality prose.

## 2. Agentic Graph Analysis

The engine leverages a LangGraph state machine (`src/MnesOS/graph.py`) structured across two primary LLM decision nodes: `Director` and `Narrator`. The third logical role, the **NPC Brain**, is implemented as a specialized intent-query tool.

### Fit For Purpose vs. Turn-Based RPGs
The architecture mimics the phases of a classic Turn-Based RPG: `Player Input -> Mechanics Resolution -> NPC Intent -> Final Resolution -> Render Frame`. 

MnesOS recreates this systematically:
1. **Director Node**: The Orchestrator. It maps player intent, resolves mechanics via tools, and queries NPCs for their reactions mid-turn.
2. **NPC Intent Tool (`query_npc_intent`)**: The Actor. It provides autonomous character dialogue and intent when queried by the Director, ensuring persona isolation without the overhead of a separate graph node.
3. **Narrator Node**: The Storyteller. It takes the finalized outcomes and renders them into immersive prose.

### Node Count: The Two-Node Sweet Spot
While previous iterations explored a 3-node graph, the current **two-node architecture with specialized tools** provides the optimal balance of isolation and performance.

- **Why separate Director & Narrator?** 
  Forcing a single agent to handle both strict mechanics resolution and flavorful prose writing leads to "prompt bleed". The Narrator is air-gapped from the raw system notes to ensure it only describes *outcomes*, not *calculations*.
- **Why toolize the NPC Brain?**
  A separate graph node for NPCs creates high latency and redundant context passing (sending history to three agents). By making the NPC Brain a tool available to the Director, we preserve character autonomy and profile isolation while allowing the Director to manage the high-level turn flow in a single coordinated loop.

### Conclusion 
The graph structure implements an LLM-adapted **Model-View-Controller (MVC)** framework. The `Director` acts as the **Controller**, the YARE engine as the **Model**, and the `Narrator` as the **View**. This separation of concerns guarantees deterministic gameplay while allowing for highly variable, high-quality narrative output.
