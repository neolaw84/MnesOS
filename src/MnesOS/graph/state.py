from typing import Annotated, TypedDict, List, Dict, Any, Optional
import operator
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages

def _staging_reducer(existing: Optional[List[Any]], update: Optional[List[Any]]) -> List[Any]:
    """Reducer for bot_memory_staging. None signals a clear; a list is appended."""
    if update is None:
        return []
    if isinstance(update, list):
        return (existing or []) + update
    return existing or []

class GameState(TypedDict):
    client_messages: Annotated[list[dict], operator.add]  # game story history, managed by caller
    agent_messages: Annotated[list[Any], add_messages]  # per-turn tool-call and tool-return history
    bot_memory: Dict[str, Any]
    bot_memory_staging: Annotated[List[Dict[str, Any]], _staging_reducer]  # tool write buffer
    yare_config: Dict[str, Any]
    prompt_directives: Dict[str, str]  # loaded from prompt_directives.yaml, NOT yare.yaml
    lore_path: str
    lore_content: str
    persona_context: Dict[str, str]
    system_notes: Annotated[List[str], operator.add]
    retrieved_lore: str
    iteration_count: int
    turn_phase: str
    npc_intent_called: bool  # tracks whether query_npc_intent was already called this turn

class NPCPresentation(TypedDict):
    """DTO carrying the identifying information for a single NPC.

    Constructed by the Director LLM before calling ``query_npc_intent``.
    The tool is a pure function that reads only this DTO and static templates —
    it never touches ``bot_memory["npcs"]``.
    """
    id: str
    template: Optional[str]
    tags: Optional[List[str]]

class NPCIntentOutput(BaseModel):
    npc_id: str = Field(description="The ID of the NPC this intent belongs to.")
    dialogue: str = Field(description="Exactly what the NPC says out loud. Can be empty.")
    action_intent: str = Field(description="What the NPC is trying to do physically or mechanically.")
    internal_monologue: str = Field(description="The NPC's hidden thoughts and emotions.")

class BatchedNPCIntent(BaseModel):
    intents: List[NPCIntentOutput] = Field(description="List of intents for the requested NPCs.")

def get_public_state(bot_memory: Dict[str, Any], yare_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filters the bot_memory to only include public state variables."""
    public_state = {}
    schema = yare_config.get("state_schema", {})
    for key, value in bot_memory.items():
        if isinstance(value, dict):
            public_state[key] = {}
            for sub_key, sub_value in value.items():
                if schema.get(key, {}).get(sub_key, {}).get("visibility", "private") == "public":
                    public_state[key][sub_key] = sub_value
        else:
            if schema.get(key, {}).get("visibility", "private") == "public":
                public_state[key] = value
    return public_state

def get_npc_visible_state(bot_memory: Dict[str, Any], yare_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filters bot_memory to only include state variables the NPC tool is allowed to see."""
    visible: Dict[str, Any] = {}
    schema = yare_config.get("state_schema", {})
    for key, value in bot_memory.items():
        entry = schema.get(key, {})
        if isinstance(entry, dict) and entry.get("npc_visibility", False):
            visible[key] = value
    return visible
