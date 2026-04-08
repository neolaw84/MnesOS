from typing import Annotated, TypedDict, Literal, Optional, List, Dict, Any
import operator
from langgraph.graph import StateGraph, END

# Import our refined logic components
from interpreter import YAREInterpreter
from context import VectorLoreStore
from prompts import DIRECTOR_SYSTEM_PROMPT, NARRATOR_SYSTEM_PROMPT, NPC_BRAIN_SYSTEM_PROMPT

# ---------------------------------------------------------
# 1. State Definition
# ---------------------------------------------------------

class GameState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    bot_memory: Dict[str, Any]
    yare_config: Dict[str, Any]
    prompt_directives: Dict[str, str]  # loaded from prompt_directives.yaml, NOT yare.yaml
    lore_path: str
    system_notes: List[str]
    retrieved_lore: str
    tool_calls: List[dict]
    iteration_count: int
    turn_phase: str

MAX_ITERATIONS = 3

# ---------------------------------------------------------
# 2. Graph Nodes
# ---------------------------------------------------------

def context_retrieval_node(state: GameState) -> GameState:
    """
    1. Lore Node: Executes FIRST. Grabs the Vector RAG context 
    based on the user's input, current location, active NPCs, and items.
    """
    store = VectorLoreStore.from_file(state["lore_path"])
    content = state['messages'][-1].get('content', '')
    
    # Base query starts with the user's explicit action
    query_parts = [content]
    
    # Dynamically extract lore-relevant keywords from the game state
    memory = state.get("bot_memory", {})
    
    # 1. Location context
    if "current_location" in memory:
        query_parts.append(str(memory["current_location"]))
        
    # 2. Character & Creature context
    npc_data = memory.get("npc", {})
    if isinstance(npc_data, dict):
        if "archetype" in npc_data: query_parts.append(str(npc_data["archetype"]))
        if "name" in npc_data: query_parts.append(str(npc_data["name"]))
        if "species" in npc_data: query_parts.append(str(npc_data["species"]))
        
    # 3. Item & Inventory context (if the game tracks them)
    inventory = memory.get("inventory", [])
    if isinstance(inventory, list):
        query_parts.extend([str(item) for item in inventory])
        
    # Combine into a single dense query text
    query_text = " ".join(query_parts)
    
    # Increase top_k slightly to capture multifaceted scenes (Location + NPC)
    lore = store.query(query_text, top_k=3)
    
    return {"retrieved_lore": lore}

def director_node(state: GameState, *, llm=None) -> dict:
    """
    2. Player Director: Maps user intent to YARE event triggers.
    Has access to `retrieved_lore` to better understand interactions.

    Args:
        llm: Optional BaseChatModel. When provided, should be invoked to parse
             user intent and return structured tool_calls. Currently unused —
             stub keyword-matching logic runs instead.
             Wire via: functools.partial(director_node, llm=my_llm)
    """
    loops = state.get("iteration_count", 0) + 1
    simulated_calls = []
    content = state['messages'][-1].get('content', '').lower()
    
    # Directives come from prompt_directives.yaml (validated at cartridge load time).
    director_prompt = DIRECTOR_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("director", "")
    if directives:
        director_prompt += "\n\n### Cartridge Directives:\n" + directives

    if "fight" in content or "struggle" in content:
        simulated_calls.append({"name": "trigger_event", "args": {"event_name": "resolve_struggle"}})
    elif "travel" in content:
        simulated_calls.append({"name": "trigger_event", "args": {"event_name": "travel"}})
    
    return {"tool_calls": simulated_calls, "iteration_count": loops, "turn_phase": "player"}

def npc_brain_node(state: GameState, *, llm=None) -> dict:
    """
    3. NPC Brain: Reads outcomes of the player's tools AND retrieved lore.
    Governs ALL NPCs in the scene proactively.

    Args:
        llm: Optional BaseChatModel. When provided, should be invoked with
             NPC state and lore context to decide tactical tool_calls.
             Currently unused — stub hard-coded archetype check runs instead.
             Wire via: functools.partial(npc_brain_node, llm=my_llm)
    """
    simulated_calls = []
    
    # Directives come from prompt_directives.yaml (validated at cartridge load time).
    npc_brain_prompt = NPC_BRAIN_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("npc_brain", "")
    if directives:
        npc_brain_prompt += "\n\n### Cartridge Directives:\n" + directives

    # Example logic: The NPC reads the Lore, Archetype, and System Notes.
    archetype = state["bot_memory"].get("npc", {}).get("archetype", "")
    if archetype in ["Jackhammer", "Breaker", "Hidden Beast"]:
        simulated_calls.append({
            "name": "trigger_event", 
            "args": {"event_name": "generic_check", "args": {"stat": "stamina", "difficulty": 15}}
        })
        
    return {"tool_calls": simulated_calls, "iteration_count": 0, "turn_phase": "npc"}

def rules_engine_node(state: GameState) -> GameState:
    """
    4. Deterministic Engine: Handles YARE math for BOTH player and NPC.
    """
    interpreter = YAREInterpreter(state["yare_config"], state["bot_memory"])
    notes = state.get("system_notes", [])
    
    if state.get("turn_phase") == "npc" and len(state.get("tool_calls", [])) > 0:
        notes.append("\n--- NPC Turn Resolution ---")
    
    for call in state.get("tool_calls", []):
        if call["name"] == "trigger_event":
            interpreter.run_event(call["args"]["event_name"], call["args"].get("args", {}))
            notes.extend(interpreter.notes)
            interpreter.notes = [] 
            
    return {"bot_memory": interpreter.state, "system_notes": notes, "tool_calls": []}

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

def narrator_node(state: GameState, *, llm=None) -> dict:
    """
    5. Narrator: Synthesizes lore, full system results, and user intent.

    Args:
        llm: Optional BaseChatModel. When provided, should be invoked with
             the narrator prompt + system_notes + lore to produce prose, and
             the result stored as 'narrative' in the returned state dict.
             Currently unused — stub clears notes and returns nothing.
             Wire via: functools.partial(narrator_node, llm=my_llm)
    """
    # Create a filtered public state for the final output.
    public_state = get_public_state(state["bot_memory"], state["yare_config"])
    
    # Directives come from prompt_directives.yaml (validated at cartridge load time).
    narrator_prompt = NARRATOR_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("narrator", "")
    if directives:
        narrator_prompt += "\n\n### Cartridge Directives:\n" + directives

    # Here you would use an LLM with the narrator_prompt, system_notes, retrieved_lore
    # and public_state to generate the narrative.
    # For this example, we'll just clear the notes and lore.
    
    return {"iteration_count": 0, "system_notes": [], "retrieved_lore": ""}

# ---------------------------------------------------------
# 3. Clean Edge Routers
# ---------------------------------------------------------

def route_director(state: GameState) -> Literal["Tools", "NPC_Brain"]:
    if state.get("tool_calls") and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "Tools"
    return "NPC_Brain"

def route_rules(state: GameState) -> Literal["Director", "NPC_Brain", "Narrator"]:
    phase = state.get("turn_phase")
    if phase == "player":
        # Loop back to director if it has more tools, else natural routing will push to NPC
        return "Director"
    else:
        # Loop back to NPC Brain to see if it has more tactical moves
        return "NPC_Brain"

def route_npc_brain(state: GameState) -> Literal["Tools", "Narrator"]:
    if state.get("tool_calls") and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "Tools"
    return "Narrator"

# ---------------------------------------------------------
# 4. Compilation
# ---------------------------------------------------------
workflow = StateGraph(GameState)

workflow.add_node("Lore", context_retrieval_node)
workflow.add_node("Director", director_node)
workflow.add_node("Tools", rules_engine_node)
workflow.add_node("NPC_Brain", npc_brain_node)
workflow.add_node("Narrator", narrator_node)

# Linear start: Lore is grabbed unconditionally before any LLM decides anything
workflow.set_entry_point("Lore")
workflow.add_edge("Lore", "Director")

workflow.add_conditional_edges("Director", route_director, {
    "Tools": "Tools",
    "NPC_Brain": "NPC_Brain"
})

workflow.add_conditional_edges("NPC_Brain", route_npc_brain, {
    "Tools": "Tools",
    "Narrator": "Narrator"
})

workflow.add_conditional_edges("Tools", route_rules, {
    "Director": "Director",
    "NPC_Brain": "NPC_Brain",
    "Narrator": "Narrator"
})

workflow.add_edge("Narrator", END)
