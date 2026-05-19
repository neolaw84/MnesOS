# MnesOS Architecture Decision Records (ADR)

This document serves as the standalone registry for all major architectural and design decisions made for MnesOS. It captures the "Why" behind the core engine, the chosen implementation patterns, and the alternatives that were considered and discarded.

---

## 1. Core Engine Architecture

### 1.1. Deterministic Rules Execution (YARE)
*   **Decision**: Decouple game mechanics from the LLM using a custom, non-Turing complete rules engine called YARE (YARE Agentic Rules Engine).
*   **Rationale**: LLMs are probabilistic and unreliable for math, inventory management, and deterministic logic. YARE ensures that state mutation is safe, predictable, and bounded (preventing infinite loops), while the LLM acts only as a high-level trigger for these rules.
*   **Status**: Active / Implemented.

### 1.2. Air-Gapped Graph (Director/Minigame Routers/Narrator)
*   **Decision**: Split narrative orchestration into distinct nodes: the **Director** (mechanics/intent), the **Narrator** (prose/rendering), and two minor but important routing nodes: **MinigameInput** and **MinigameOutput**.
*   **Rationale**: Prevents "The Immersion Gap" where raw system data leaks into the story. The Narrator is "air-gapped" and only receives immersive scene directives. The minigame nodes handle structured entry and exit from interactive minigame components without causing the Director to get stuck or misroute the narrative.
*   **Status**: Active / Implemented.

### 1.3. Stateless Event Sourcing (Tree-based State)
*   **Decision**: Rebuild the game state on-the-fly for every turn by applying a chronological chain of mutations (`yare_delta`) from a root state.
*   **Rationale**: Enables native support for branching timelines and prevents the "save scumming" problem. The backend remains stateless, and players can explore alternative outcomes by branching from any prior `TurnLog` ID.
*   **Status**: Active / Implemented in backend. Not implemented in UI.

### 1.4. The Registry Pattern & Side-by-Side Auth
*   **Decision**: Use a dynamic Registry Pattern to inject dependencies (Auth, LLM, Storage) at runtime, and adopt a "Side-by-Side" authentication model where the client manages its own LLM keys (for LLM authentications regardless of which LLM) along with the backend auth for the engine/storage.
*   **Rationale**: Minimizes security liability by never storing user API keys server-side (avoiding a "honey pot"). It also ensures the codebase is environment-agnostic, allowing the exact same engine to run in a cloud SaaS or as a local desktop app.
*   **Status**: Active / Implemented.

---

## 2. Agentic Strategy & Tooling

### 2.1. Tool-Based NPC Intent Model
*   **Decision**: Implement NPCs as tools (`query_npc_intent`) called by the Director rather than assigning them dedicated nodes in the LangGraph or Director acting as the NPCs.
*   **Rationale**: Reduces latency and token costs compared to independent graph nodes. It allows the Director to batch multiple NPC reactions into a single call and provides better control over "Prompt Bleed" (i.e. NPC acting with information they should not know) by strictly filtering NPC context via schema-driven visibility.
*   **Status**: Active / Implemented.

### 2.2. Batch RAG Tooling (`multi_lore_lookup`)
*   **Decision**: World-building retrieval as an on-demand tool called by the Director rather than a pre-turn (blind) injection phase.
*   **Rationale**: Prevents "Context Inflation" by only retrieving lore when relevant to the directing tasks required for current turn. It allows the Director to issue focused, batched queries rather than guessing relevance before the player's intent is processed.
*   **Status**: Active / Implemented.

### 2.3. LLM Tool-based Logic Bridge (YARE to Tools)
*   **Decision**: Convert YARE events defined in a cartridge's `yare.yaml` into native LLM tools rather than using long-form system prompts or dedicated logic nodes.
*   **Rationale**: 
    1. **Minimal Prompts**: Keeps the Director prompt clean by avoiding long lists of available events.
    2. **Capability Discovery**: Enables the LLM to perform native parameter validation and capability discovery.
    3. **Clean Decoupling**: Preserves strict separation between narrative rendering (Narrator) and deterministic state mutation (YARE).
*   **Status**: Active / Implemented.

---

## 3. LLM Backend & Model Strategy

### 3.1. LLM Consumption Models (Local, BYOK, Hosted)
*   **Decision**: Provide three distinct consumption models for LLMs under a unified Strategy Pattern, all utilizing the "Side-by-Side" authentication model.
    *   **Local**: Executes on the user's hardware (Desktop App only). Requires local storage. (Status: Backlog)
    *   **BYOK (Bring Your Own Key)**: Uses third-party aggregators or providers (OpenRouter, Gemini, OpenAI). (Status: Implemented for OpenRouter)
    *   **Hosted**: Uses a MnesOS-provided API with operator-managed models. Requires a credit/billing management system. (Status: Backlog)
*   **Rationale**: Ensures maximum flexibility for different user personas while maintaining a single code path for orchestration. The **BYOK** model specifically eliminates developer liability for user-generated API traffic in cloud environments.
*   **Status**: Active.

### 3.2. Hardware-Specific Local Model Tiers
*   **Decision**: Optimize for three distinct local hardware tiers: **Tiny** (<4GB VRAM), **Small** (6-8GB), and **Midsize** (12-16GB).
*   **Rationale**: MnesOS is designed for both cloud and local play. Tailoring model selection (e.g., Qwen 7B vs Llama 70B) ensures a performant experience regardless of the user's available hardware.
*   **Status**: Active / Planning.

### 3.3. Model Selection Criteria (JSON & Uncensored)
*   **Decision**: Prioritize models that maintain Hydraulically reliable JSON tool-calling even when uncensored (e.g., Qwen 3 Instruct, Dolphin-Qwen).
*   **Rationale**: The Director must reliably output tool calls to drive the engine. Uncensored models are required for narrative freedom in RPG settings without triggering mainstream safety filters that break roleplay immersion.
*   **Status**: Active.

### 3.4. The Downloader Pattern (Local Distribution)
*   **Decision**: Configure the engine to fetch model weights from Hugging Face at runtime rather than bundling them.
*   **Rationale**: Mitigates developer legal liability for model weights by navigating the complexities of OSI-approved vs AUP licenses (e.g., Llama Community License). Shifting download responsibility to the user at runtime ensures the developer does not "distribute" restricted weights directly, assuming liability transfer for the weight usage.
*   **Status**: Backlog.

---

## 4. Security & Operational Strategy

### 4.1. Multi-Layered Guardrail Strategy Pattern
*   **Decision**: Implement a `GuardrailStrategy` interface that allows dynamic swapping between safety strictness levels (e.g., `StrictSFW` vs `UncensoredRP`).
*   **Rationale**: Allows the engine to support both safe public play and private mature roleplay. Guardrails are applied at the Input (Prompt Guard), Execution (Guardrails AI), and Output (Llama Guard 3) layers.
*   **Status**: Backlog.

### 4.2. Permissive Aggregator Endpoints
*   **Decision**: Route mature or roleplay-heavy traffic exclusively through permissive aggregator endpoints (OpenRouter) or direct IaaS providers (RunPod, Together) rather than mainstream corporate APIs (e.g., OpenAI, Google).
*   **Rationale**: Prevents service interruption from mainstream Trust & Safety proxy bans, ensuring that narrative freedom in RPG contexts is not restricted by rigid corporate filters.
*   **Status**: Backlog.

### 4.3. Regional Geo-Blocking (Australia)
*   **Decision**: Apply IP-based geo-blocking for the hosted cloud service targeting Australia.
*   **Rationale**: Immediate mitigation of regulatory risks in jurisdictions with restrictive or ambiguous internet safety laws.
*   **Note**: This is an **operational/infrastructure** task (e.g., via Cloudflare or Load Balancer rules) and is outside the scope of the MnesOS engine codebase.
*   **Status**: Not Applicable.

---

## 5. Deployment & Interaction Architecture

### 5.1. Decoupled CDN Deployment
*   **Decision**: Separate the backend (pure API) from the frontend (served via CDN), controlled by environment variables.
*   **Rationale**: Reduces expensive compute costs by serving static assets from cheap edge networks, allowing the Python backend to scale independently based purely on LLM orchestration load.
*   **Note**: This architecture is specifically designed to support cloud operators providing MnesOS as a service, enabling enterprise-grade deployment flexibility from within the core codebase.
*   **Status**: Backlog.

### 5.2. Stateless Interactive Routing (`_pending_interaction`)
*   **Decision**: Handle UI constraints (forms, mini-games) by tracking a `_pending_interaction` flag in the YARE database state, resolving it via a deterministic "Minigame Input Node" that bypasses the Director LLM.
*   **Rationale**: Avoids the "Interrupt Trap" (LangGraph checkpointers pausing mid-tool). It keeps the backend purely RESTful and stateless. It guarantees that players cannot bypass narrative constraints by typing free-text, as the Minigame Input Node enforces structured JSON submission.
*   **Status**: Active / Implemented.

### 5.3. High-Level Language Authoring (yare.py / yare.js)
*   **Decision**: Provide cartridge developers with the ability to author the YARE specification using conventional programming languages, beginning with Python and JavaScript.
*   **Rationale**: YAML is excellent for engine execution but lacks the modularity, type-safety, and logic-reuse capabilities (loops, helper functions) required for complex cartridges. Providing Py/JS SDKs improves developer productivity and allows for programmatic generation of rules while maintaining YAML as the underlying portable engine standard.
*   **Status**: Backlog.

### 5.4. Explicit Py/JS 1-to-1 Compiler Mapping
*   **Decision**: SDKs (`yare.py`, `yare.js`) must maintain a strict 1-to-1 mapping between high-level language functions and YARE YAML events, requiring developers to explicitly manage state transitions and asynchronous multi-turn interactions.
*   **Rationale**: Prevents building "compiler magic" that attempts to implicitly untangle asynchronous game loops (e.g., automatically splitting a single procedural function into multiple turn-based states). By keeping the YAML as a strict Intermediate Representation (IR) and forcing explicit event handling, the engine remains predictable, deterministic, and easy to debug.
*   **Status**: Backlog.

---

## 6. Discarded Ideas & Abandoned Patterns

### 6.1. Dual-Gateway (Client-Side LLM Calls)
*   **Abandoned In Favor Of**: Backend Managed Orchestration.
*   **Rationale**: Bypassing the backend for LLM calls (talking directly to OpenRouter from the client) breaks the orchestration engine, as the LangGraph graph needs direct access to the model to drive game turns.

### 6.2. Linked Identity (Server-side Persistence of API Keys)
*   **Abandoned In Favor Of**: Side-by-Side / Frontend Managed Auth.
*   **Rationale**: Storing third-party OAuth/Refresh tokens or API keys in the MnesOS database creates a severe security liability ("honey pot"). Client-managed keys ensure user security and engine portability.

### 6.3. Context-Driven Strategy
*   **Abandoned In Favor Of**: The Registry Pattern.
*   **Rationale**: Initializing the `Orchestrator` with a "Context Object" (User, Storage, Factory) provided high ergonomics but would require refactoring 15-20% of the codebase across all nodes and tools. Furthermore, a central Context object risks becoming a "God Object" that is difficult to mock and test in isolation. The Registry Pattern achieves similar goals by limiting refactoring to the API boundary and graph setup.

### 6.4. Standalone NPC Brain Nodes
*   **Abandoned In Favor Of**: NPC Intent Tool.
*   **Rationale**: Dedicated graph nodes for NPCs added unnecessary latency and were too rigid for dynamic scenes.
    *   **Redundancy**: For simple physical certainties (e.g., an NPC's reaction to an injury), the Director can use "GM Fiat" to determine the outcome without an extra LLM call.
    *   **Multi-NPC Rigidity**: A fixed node cannot efficiently handle a dynamic number of NPCs. Toolizing the intent allows the Director to batch multiple reactions into a single call only when tactical or emotional complexity warrants it.

### 6.5. Per-Turn Lore Pre-Node Injection
*   **Abandoned In Favor Of**: Batch RAG Tooling.
*   **Rationale**: Injecting lore at the start of every turn results in context inflation and wasted tokens for trivial actions. Active retrieval by the Director is more precise and efficient as it only requests information after the player's intent is known.
