from typing import Annotated, TypedDict, Literal, List, Dict, Any, Optional
import operator
from langgraph.graph import StateGraph, END
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

# ---------------------------------------------------------
# 0. Tool definitions
# ---------------------------------------------------------

@tool
def trigger_event(event_name: str, args: Optional[dict] = None) -> str:
    """
    Trigger a named YARE rules event with optional input arguments.

    Args:
        event_name: The name of the YARE event as defined in the cartridge yare.yaml.
        args: Optional dictionary of input arguments for the event.
    """
    # This function is never called directly — rules_engine_node handles execution.
    # Its schema is used by the LLM to produce structured tool calls.
    return f"Event '{event_name}' queued."


# Import our refined logic components
from interpreter import YAREInterpreter
from context import VectorLoreStore
from prompts import DIRECTOR_SYSTEM_PROMPT, NARRATOR_SYSTEM_PROMPT, NPC_BRAIN_SYSTEM_PROMPT

# ---------------------------------------------------------
# 1. State Definition
# ---------------------------------------------------------

class GameState(TypedDict):
    client_messages: Annotated[list[dict], operator.add]  # game story history, managed by caller
    agent_messages: Annotated[list[Any], add_messages]  # per-turn tool-call and tool-return history
    bot_memory: Dict[str, Any]
    yare_config: Dict[str, Any]
    prompt_directives: Dict[str, str]  # loaded from prompt_directives.yaml, NOT yare.yaml
    lore_path: str
    system_notes: List[str]
    retrieved_lore: str
    iteration_count: int
    turn_phase: str

MAX_ITERATIONS = 3


def _get_last_ai_tool_calls(agent_messages: list) -> list:
    """Return the tool_calls list from the most recent AIMessage, or empty list."""
    for msg in reversed(agent_messages):
        if isinstance(msg, AIMessage):
            return getattr(msg, "tool_calls", []) or []
    return []


def _client_messages_to_langchain_messages(client_messages: List[dict]) -> List[Any]:
    """Convert persisted client story messages into LangChain message objects."""
    converted: List[Any] = []
    for msg in client_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def reset_agent_messages_node(state: GameState) -> dict:
    """Clear any stale agent-side messages at the start of a top-level invoke."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}


def cleanup_agent_messages_node(state: GameState) -> dict:
    """Remove agent-side messages before returning state to the client."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}

# ---------------------------------------------------------
# 2. Graph Nodes
# ---------------------------------------------------------

def context_retrieval_node(state: GameState) -> GameState:
    """
    1. Lore Node: Executes FIRST. Grabs the Vector RAG context 
    based on the user's input, current location, active NPCs, and items.
    """
    store = VectorLoreStore.from_file(state["lore_path"])
    content = state['client_messages'][-1].get('content', '')
    
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
        llm: Optional BaseChatModel. When provided, is invoked with the full
             director system prompt (including cartridge directives) and the
             user's message to produce structured tool_calls.
             Wire via: functools.partial(director_node, llm=my_llm)
    """
    loops = state.get("iteration_count", 0) + 1

    # Directives come from prompt_directives.yaml (validated at cartridge load time).
    director_prompt = DIRECTOR_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("director", "")
    if directives:
        director_prompt += "\n\n### Cartridge Directives:\n" + directives

    result = {"iteration_count": loops, "turn_phase": "player"}
    if llm is not None:
        events = list(state.get("yare_config", {}).get("events", {}).keys())
        system_content = director_prompt
        if events:
            system_content += "\n\n### Available Events:\n" + "\n".join(f"- {e}" for e in events)

        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))

        response = llm.bind_tools([trigger_event]).invoke(prompt_messages)
        result["agent_messages"] = [response]

    return result

def npc_brain_node(state: GameState, *, llm=None) -> dict:
    """
    3. NPC Brain: Reads outcomes of the player's tools AND retrieved lore.
    Governs ALL NPCs in the scene proactively.

    Args:
        llm: Optional BaseChatModel. When provided, is invoked with NPC state
             and lore context to decide tactical tool_calls.
             Wire via: functools.partial(npc_brain_node, llm=my_llm)
    """
    # Directives come from prompt_directives.yaml (validated at cartridge load time).
    npc_brain_prompt = NPC_BRAIN_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("npc_brain", "")
    if directives:
        npc_brain_prompt += "\n\n### Cartridge Directives:\n" + directives

    result = {"iteration_count": 0, "turn_phase": "npc"}
    if llm is not None:
        prompt_messages = [SystemMessage(content=npc_brain_prompt)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))
        prompt_messages.append(HumanMessage(content=(
            f"NPC State: {state['bot_memory'].get('npc', {})}\n"
            f"System Notes: {state.get('system_notes', [])}\n"
            f"Retrieved Lore: {state.get('retrieved_lore', '')}"
        )))
        response = llm.bind_tools([trigger_event]).invoke(prompt_messages)
        result["agent_messages"] = [response]

    return result

def rules_engine_node(state: GameState) -> dict:
    """
    4. Deterministic Engine: Handles YARE math for BOTH player and NPC.

    Reads tool calls from the last AIMessage in agent_messages (LangGraph-native pattern).
    Appends ToolMessage results back into agent_messages.
    """
    interpreter = YAREInterpreter(state["yare_config"], state["bot_memory"])
    notes = state.get("system_notes", [])
    tool_messages = []

    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))

    if state.get("turn_phase") == "npc" and calls:
        notes.append("\n--- NPC Turn Resolution ---")

    for call in calls:
        if call["name"] == "trigger_event":
            interpreter.run_event(call["args"]["event_name"], call["args"].get("args") or {})
            event_notes = list(interpreter.notes)
            notes.extend(event_notes)
            if event_notes:
                tool_messages.append(
                    ToolMessage(
                        content="\n".join(event_notes),
                        tool_call_id=call.get("id", call["args"]["event_name"]),
                    )
                )
            interpreter.notes = []

    return {
        "bot_memory": interpreter.state,
        "system_notes": notes,
        "agent_messages": tool_messages,
    }

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
        llm: Optional BaseChatModel. When provided, is invoked with the
             narrator prompt, system_notes, lore, and public state to produce
             prose stored as 'narrative' in the output state.
             Wire via: functools.partial(narrator_node, llm=my_llm)
    """
    # Create a filtered public state for the final output.
    public_state = get_public_state(state["bot_memory"], state["yare_config"])

    # Directives come from prompt_directives.yaml (validated at cartridge load time).
    narrator_prompt = NARRATOR_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("narrator", "")
    if directives:
        narrator_prompt += "\n\n### Cartridge Directives:\n" + directives

    result: dict = {"iteration_count": 0, "system_notes": [], "retrieved_lore": ""}

    if llm is not None:
        prompt_messages = [SystemMessage(content=narrator_prompt)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))
        prompt_messages.append(HumanMessage(content=(
            f"System Notes: {state.get('system_notes', [])}\n"
            f"Retrieved Lore: {state.get('retrieved_lore', '')}\n"
            f"Public State: {public_state}"
        )))
        response = llm.invoke(prompt_messages)
        narrative = response.content
        result["narrative"] = narrative
        # Append narrator response to client_messages so the caller sees it
        result["client_messages"] = [{"role": "assistant", "content": narrative}]

    return result

# ---------------------------------------------------------
# 3. Clean Edge Routers
# ---------------------------------------------------------

def route_director(state: GameState) -> Literal["Tools", "NPC_Brain"]:
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "Tools"
    return "NPC_Brain"

def route_rules(state: GameState) -> Literal["Director", "NPC_Brain", "Narrator"]:
    phase = state.get("turn_phase")
    if phase == "player":
        return "Director"
    else:
        return "NPC_Brain"

def route_npc_brain(state: GameState) -> Literal["Tools", "Narrator"]:
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "Tools"
    return "Narrator"

# ---------------------------------------------------------
# 4. Compilation
# ---------------------------------------------------------
workflow = StateGraph(GameState)

workflow.add_node("ResetAgentMessages", reset_agent_messages_node)
workflow.add_node("Lore", context_retrieval_node)
workflow.add_node("Director", director_node)
workflow.add_node("Tools", rules_engine_node)
workflow.add_node("NPC_Brain", npc_brain_node)
workflow.add_node("Narrator", narrator_node)
workflow.add_node("CleanupAgentMessages", cleanup_agent_messages_node)

# Linear start: Lore is grabbed unconditionally before any LLM decides anything
workflow.set_entry_point("ResetAgentMessages")
workflow.add_edge("ResetAgentMessages", "Lore")
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

workflow.add_edge("Narrator", "CleanupAgentMessages")
workflow.add_edge("CleanupAgentMessages", END)
