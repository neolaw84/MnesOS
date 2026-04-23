# MnesOS Alpha: Component Interfaces & Contracts

This document defines the strict boundaries, data models, and API contracts between the four tiers of the MnesOS Alpha web architecture. Adhering to these contracts ensures true parallel development across the Web Client, API Server, AI Graph, and Storage layers.

## 1. REST API Contracts (Tier 1 <-> Tier 2)

This boundary defines how the Web Client (React/Vue) communicates with the FastAPI Server. All endpoints require the client to pass their BYOK token or authentication credential via headers.

### 1.1 Process Turn (Standard Gameplay)

**Endpoint:** `POST /api/instances/{instance_id}/turn`
**Description:** Submits a user's action to the game engine, extending the timeline from a specific node.

**Request Body (JSON):**

```
{
  "parent_turn_id": "uuid-of-the-previous-turn",
  "user_input": "I cast a fireball at the goblin."
}
```

**Response Body (JSON):**

```
{
  "turn_id": "uuid-of-the-newly-created-turn",
  "narrator_response": "The goblin is engulfed in flames...",
  "yare_delta": [
    {
      "type": "event",
      "name": "damage_entity",
      "payload": { "target": "goblin", "amount": 15 }
    }
  ]
}
```

### 1.2 Inject State (Authorized Cheating / Debugging)

**Endpoint:** `POST /api/instances/{instance_id}/inject`
**Description:** Appends a `SYSTEM` turn to the timeline containing manual state mutations.

**Request Body (JSON):**

```
{
  "parent_turn_id": "uuid-of-the-previous-turn",
  "yare_delta": [
    {
      "type": "mutation",
      "path": "items.gold",
      "op": "set",
      "value": 999
    }
  ]
}
```

**Response Body (JSON):**

```
{
  "turn_id": "uuid-of-the-newly-created-turn"
}
```

### 1.3 Game Saves (Timeline Bookmarks)

**Endpoint:** `POST /api/instances/{instance_id}/saves`
**Description:** Creates a labeled bookmark pointing to a specific node in the TurnLog tree.

**Request Body (JSON):**

```
{
  "turn_log_id": "uuid-of-the-turn-to-save",
  "label": "Before the Dragon Fight"
}
```

**Response Body (JSON):**

```
{
  "save_id": "uuid-of-the-new-save",
  "created_at": "2026-04-20T10:44:00Z"
}
```

### 1.4 Load Game State (Hydration)

**Endpoint:** `GET /api/instances/{instance_id}/state`
**Query Parameters:** `?turn_log_id={uuid-of-the-saved-turn}`
**Description:** Reconstructs and returns the fully hydrated game state up to the specified node. The Web Client uses this to render the UI upon loading a save, resuming a session, or time-traveling to a different branch.

**Response Body (JSON):**

```
{
  "bot_memory": {
    "items": { "gold": 999, "potions": 2 },
    "location": "Dragon's Lair"
  },
  "client_messages": [
    { "role": "user", "content": "I enter the cave." },
    { "role": "assistant", "content": "It is dark and smells of sulfur." }
  ]
}
```

## 2. Storage & Persistence Contracts (Tier 2 <-> Tier 3)

This boundary defines how the App Server interacts with the SQLite/Postgres database. It expands `AbstractStorageComponent` to support the tree-based Event Source architecture.

### 2.1 Updated Data Models (`src/MnesOS/storage/models.py`)

```
from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime

@dataclass
class TurnLog:
    instance_id: str
    turn_index: int
    actor: str # e.g., "PLAYER", "NPC", "SYSTEM"
    input_text: str
    yare_delta: Any 
    parent_id: Optional[str] = None  # NEW: Points to previous turn (None = root)
    narrator_text: str = ""          # NEW: Cached narrator output
    id: Optional[str] = None
    timestamp: Optional[datetime] = None

@dataclass
class GameSave:
    instance_id: str
    turn_log_id: str
    label: str
    id: Optional[str] = None
    created_at: Optional[datetime] = None
```

### 2.2 Storage Interface Additions (`src/MnesOS/storage/interface.py`)

```
from typing import List

class AbstractStorageComponent(ABC):
    # ... existing methods ...

    @abstractmethod
    def get_turn_lineage(self, turn_id: str) -> List[TurnLog]:
        """
        Traverses the parent_id chain from the given turn_id up to the root.
        Returns the ordered list of TurnLogs from [Root, ..., target_turn_id].
        """
        pass

    @abstractmethod
    def create_game_save(self, save: GameSave) -> GameSave:
        pass

    @abstractmethod
    def get_game_saves(self, instance_id: str) -> List[GameSave]:
        pass
```

## 3. Core Engine Orchestration (Tier 2 Internal)

This boundary defines how the FastAPI routes execute the business logic statelessly.

### 3.1 State Hydrator (`src/MnesOS/storage/hydrator.py`)

```
from typing import List, Dict, Any
from MnesOS.storage.models import TurnLog

class StateHydrator:
    @staticmethod
    def hydrate_state(turn_lineage: List[TurnLog], initial_bot_memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a sequential lineage of turns and applies their `yare_delta` payloads
        to the `initial_bot_memory`, returning the reconstructed GameState fields:
        `bot_memory` and `client_messages`.
        """
        pass
```

### 3.2 Stateless Orchestrator (`src/MnesOS/orchestrator.py`)

```
from typing import Dict, Any

class Orchestrator:
    def __init__(self, cartridge_dir: str, storage: AbstractStorageComponent):
        # Initializes cartridge metadata and storage bindings.
        # DOES NOT maintain self._state.
        pass

    def process_turn(self, parent_turn_id: Optional[str], user_input: str, llm_clients: dict) -> Dict[str, Any]:
        """
        1. Calls `storage.get_turn_lineage(parent_turn_id)`
        2. Calls `StateHydrator.hydrate_state()`
        3. Appends user_input to client_messages
        4. Invokes the LangGraph compiled app, passing static config via RunnableConfig
        5. Returns a dict containing:
           - 'narrator_text': str
           - 'yare_delta': list
        Note: The Orchestrator does NOT save the turn to the DB; the API route handles that.
        """
        pass
```

## 4. LangGraph Context & Config (Tier 2 <-> Tier 4)

This boundary defines what data is passed to the AI Graph nodes during invocation. It strictly separates live state (mutated by the graph) from static configuration (read-only).

### 4.1 Live State (`src/MnesOS/graph/state.py`)

This state is passed as the primary argument to graph nodes and is modified during execution.

```
from typing import TypedDict, Annotated, List, Dict, Any
import operator
from langgraph.graph.message import add_messages

class GameState(TypedDict):
    # Persistent/Event-Sourced
    client_messages: Annotated[list[dict], operator.add] 
    bot_memory: Dict[str, Any]
    
    # Ephemeral (Reset each process_turn invocation)
    agent_messages: Annotated[list[Any], add_messages]
    bot_memory_staging: Annotated[List[Dict[str, Any]], _staging_reducer] # Becomes yare_delta
    system_notes: Annotated[List[str], operator.add]
    retrieved_lore: str
    iteration_count: int
    turn_phase: str
    npc_intent_called: bool
```

### 4.2 Static Configuration (`RunnableConfig`)

Nodes access this via the secondary `config` parameter provided by LangGraph.

```
# Expected structure of config["configurable"] passed during app.invoke()
{
    "yare_config": Dict[str, Any],        # Loaded from yare.yaml
    "prompt_directives": Dict[str, str],  # Loaded from prompt_directives.yaml
    "lore_path": str,                     # Path to bot_lore.md
    "lore_content": str,                  # Content of bot_lore.md
    "persona_context": Dict[str, str],    # Rendered player persona text
    "llm_clients": {                      # Injected by the API Aspect (AuthZ/BYOK)
        "director": BaseChatModel,
        "narrator": BaseChatModel,
        "npc": BaseChatModel
    }
}
```