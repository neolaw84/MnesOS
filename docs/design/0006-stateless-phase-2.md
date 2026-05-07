# 0006: Stateless Phase 2 & Interface Contracts

## Context & Goals
The ambition for MnesOS includes:
- A single web-based client (which will be wrapped into Mobile and Desktop apps).
- Access to multiple LLMs across all apps: MnesOS LLM (paid via credits) and OpenRouter LLMs (via PKCE).
- An additional option for the Desktop app to use local LLMs.
- Server-side DBMS (provided by MnesOS) for storing GameState, Cartridges, GameInstances, etc., necessitating authentication against a user/player table and authorization for DB objects.
- A co-existing authorization model where MnesOS Auth (for DB objects) operates alongside OpenRouter PKCE (for LLM credits).
- The option for Desktop apps to save data in a Local DBMS.

This document records the brainstorming and final design decisions for implementing the interface contracts needed for Phase 2 (Stateless Auth Abstraction Layer, LLM Provider Factory, Hierarchical Config).

---

## Final Understanding Lock

*   **Logic (The Brain)**: A single `Orchestrator` (LangGraph) that runs on both the Central Server and the Local Sidecar (for Desktop/Mobile).
*   **Identity**: All requests have a `user_id`. In Local Mode, it’s a stable "Local User" ID to ensure identical code-paths and schema compatibility.
*   **Providers**:
    *   **LLM**: Determined **per request**. Users can set preferences via the frontend settings menu. Mappings/presets (e.g., "Deep Thinking", "Good Story") or "Custom" options allow fine-grained LLM selection for the Director, NPC Intent, Narrator, and Embedding (Lore Retrieval).
    *   **MnesOS LLM**: Treated as just another provider. Always proxied through a managed server-side endpoint to ensure atomic credit deduction and inference.
    *   **OpenRouter**: PKCE tokens are managed by the frontend and passed "in-flight" per request.
*   **Storage**: Handled by a unified interface pointing to either a remote DBMS (Postgres) or local DBMS (SQLite).

---

## Adopted Design: The Registry Pattern (Approach 1)

To keep the codebase identical across environments (Server vs. Local) and minimize the blast radius (affecting only ~5-8% of the backend code), we adopted the **Registry Pattern**.

Dependencies are resolved *before* the LangGraph is invoked, passing fully initialized abstract interfaces down to the engine.

### Concrete Interface Contracts (Phase 2 Implementation)

The following Python interface contracts form the blueprint for implementing the Phase 2 tickets.

#### 1. Auth & Identity Abstraction (`[MnesOS-260507-04]`)

```python
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

class AuthContext(BaseModel):
    user_id: str
    is_local: bool = False
    metadata: dict = {}

class AuthProvider(ABC):
    """Abstract Base Class for resolving player identity."""
    
    @abstractmethod
    def resolve_identity(self, headers: dict) -> AuthContext:
        """Extracts and validates identity from request headers (e.g., JWT or Local Mock)."""
        pass

class LLMAuthValidator(ABC):
    """Abstract Base Class for validating 3rd party or MnesOS LLM credentials."""
    
    @abstractmethod
    def validate_provider_keys(self, headers: dict) -> dict:
        """
        Extracts keys (e.g., X-OpenRouter-Key) or PKCE tokens from headers.
        Returns a dictionary of valid keys to pass to the LLMFactory.
        """
        pass
```

#### 2. Hierarchical Configuration (`[MnesOS-260507-06]`)

```python
from pydantic import BaseModel
from typing import Dict, Any, Optional

class LLMRoleConfig(BaseModel):
    provider: str      # e.g., "mnesos", "openrouter", "local"
    model_name: str    # e.g., "google/gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

class MnesOSRuntimeConfig(BaseModel):
    """The final, merged configuration used for a single process_turn request."""
    director_llm: LLMRoleConfig
    narrator_llm: LLMRoleConfig
    npc_llm: LLMRoleConfig
    embedding_llm: LLMRoleConfig
    
    # Cartridge specifics mapped into the run
    yare_config: Dict[str, Any]
    prompt_directives: Dict[str, str]

class ConfigMerger:
    @staticmethod
    def merge(cartridge_defaults: dict, player_settings: dict, request_overrides: dict) -> MnesOSRuntimeConfig:
        """
        Merges configs in order of precedence:
        1. Request Overrides (Highest)
        2. Player Settings
        3. Cartridge Defaults (Lowest)
        """
        pass
```

#### 3. LLM Provider Factory (`[MnesOS-260507-05]`)

```python
from abc import ABC, abstractmethod
from typing import List, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

class LLMProvider(ABC):
    """Contract for any LLM Provider (OpenRouter, MnesOS, Local)."""
    
    @abstractmethod
    def get_chat_model(self, config: LLMRoleConfig, keys: dict) -> BaseChatModel:
        """Returns a configured LangChain Chat Model."""
        pass
        
    @abstractmethod
    def get_embeddings_model(self, config: LLMRoleConfig, keys: dict) -> Embeddings:
        """Returns a configured LangChain Embeddings Model."""
        pass

class LLMFactory:
    """Registry and factory for instantiating concrete LLM providers."""
    
    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        
    def register_provider(self, name: str, provider: LLMProvider):
        self._providers[name] = provider
        
    def create_chat_client(self, config: LLMRoleConfig, keys: dict) -> BaseChatModel:
        provider = self._providers.get(config.provider)
        if not provider:
            raise ValueError(f"Unknown provider: {config.provider}")
        return provider.get_chat_model(config, keys)
        
    def create_embeddings_client(self, config: LLMRoleConfig, keys: dict) -> Embeddings:
        provider = self._providers.get(config.provider)
        if not provider:
            raise ValueError(f"Unknown provider: {config.provider}")
        return provider.get_embeddings_model(config, keys)

#### 4. Batch RAG Tooling (`[MnesOS-260507-07]`)

To optimize cost and context usage, lore retrieval is shifted from a "pre-node injection" to a "Director-initiated tool call."

```python
from pydantic import BaseModel, Field
from typing import List

class MultiLoreLookupArgs(BaseModel):
    """Arguments for the batch lore retrieval tool."""
    queries: List[str] = Field(
        ..., 
        description="A list of specific search queries or questions about the world lore, mechanics, or entities."
    )

class LoreSearchService(ABC):
    """Interface for the underlying vector search implementation."""
    
    @abstractmethod
    def search_batch(self, queries: List[str], k: int = 3) -> str:
        """
        Executes multiple vector searches and returns a deduplicated, 
        formatted string of retrieved lore snippets.
        """
        pass
```

**Graph Integration Contract:**
- **State Change**: The `retrieved_lore` field in `GameState` remains a `str`, but it is initialized as an empty string.
- **Tool Logic**: The `multi_lore_lookup` tool, when called by the Director, invokes the `LoreSearchService`, updates the `GameState["retrieved_lore"]` field, and returns a confirmation message to the Director.
- **Director Prompt**: The system prompt must be updated to include a "Search Strategy" section, instructing the agent to gather all necessary context in a single batch call before writing the narrative or resolving mechanics.
```

### Workflow
The `process_turn` API receives a `MnesOSRequestConfig`. The Backend utilizes an `LLMFactory` to instantiate the 4 required clients (Director, NPC, Narrator, Embedding) on the fly based on the request configuration/headers, injecting them into the graph.

### Architectural Highlights
*   **Bundled Backend**: The Desktop app ships with a bundled MnesOS Python backend. This enables "full anonymity" (local graph, local DB) and "synced gameplay" (calling remote DB) using the exact same codebase by flipping the API target from `localhost` to `api.mnesos.com`.
*   **MnesOS as a Provider**: By treating MnesOS credits symmetrically as an `LLMProvider`, the Orchestrator remains completely agnostic to the source of the intelligence.

---

## Discarded Ideas & Abandoned Choices

This section preserves the alternatives explored during the brainstorming session and the rationale for their rejection.

### 1. Dual-Gateway Architecture
* **Description:** The MnesOS backend only handles MnesOS DB auth; for OpenRouter LLM calls, the client talks directly to OpenRouter (or a passthrough proxy) using the PKCE token, bypassing the main MnesOS game engine.
* **Reason for Abandonment:** The backend uses a managed LangGraph graph that needs direct access to the LLM to orchestrate gameplay turns. Bypassing the backend for LLM calls breaks the orchestration engine entirely.

### 2. Linked Identity (Server-side Persistence of OpenRouter Tokens)
* **Description:** The MnesOS backend stores the OpenRouter OAuth tokens/refresh tokens in the user's profile once authenticated, providing a seamless "set up once and forget" experience across all devices.
* **Reason for Abandonment:** Storing third-party OAuth/Refresh tokens in the database makes the MnesOS DB a high-value target ("honey pot"). It introduces severe security liability and headaches for keeping the users' keys safe from theft.
* **Adopted Alternative:** Option B (Side-by-Side / Frontend Managed Auth), where keys are passed in-flight via headers and exist only in the client's secure storage and the backend's RAM during the request lifecycle.

### 3. Context-Driven Strategy (Approach 2 for Interfaces)
* **Description:** The `Orchestrator` is initialized with a "Context Object" containing the `User`, `Storage`, and a `ClientFactory`. Every node in the LangGraph extracts the context and resolves its own client dynamically mid-execution.
* **Reason for Abandonment:** While it provides high developer ergonomics, it requires rewriting every single file in `graph/nodes/` and `graph/tools/` (~15% to 20% codebase impact). The Context object risks becoming a "God Object" that is hard to mock and test in isolation.
* **Adopted Alternative:** The Registry Pattern, which limits refactoring to the API boundary (`deps.py`) and graph setup (`factory.py`), keeping the core engine pure.
