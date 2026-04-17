from typing import Annotated, TypedDict, Literal, List, Dict, Any, Optional, Tuple
import functools
import json
import operator
import re
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolCallId

# Import our refined logic components
from .interpreter import YAREInterpreter
from .context import VectorLoreStore
from .prompts import DIRECTOR_SYSTEM_PROMPT, NARRATOR_SYSTEM_PROMPT, NPC_SYSTEM_PROMPT
from pydantic import BaseModel, create_model, Field
from langchain_core.tools import StructuredTool

# ---------------------------------------------------------
# 1. State Definition
# ---------------------------------------------------------

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
    system_notes: Annotated[List[str], operator.add]
    retrieved_lore: str
    iteration_count: int
    turn_phase: str
    npc_intent_called: bool  # tracks whether query_npc_intent was already called this turn

MAX_ITERATIONS = 3

# ---------------------------------------------------------
# 0. Tool definitions
# ---------------------------------------------------------

def build_yare_event_tools(yare_config: Dict[str, Any]) -> List[StructuredTool]:
    """Dynamically generate a list of precise LangChain tools from YARE events."""
    tools = []
    events = yare_config.get("events", {})
    if not isinstance(events, dict):
        return []

    for event_name, event_config in events.items():
        if not isinstance(event_config, dict):
            continue

        fields = {}
        inputs_schema = event_config.get("inputs", {})
        if isinstance(inputs_schema, list):
            for k in inputs_schema:
                fields[k] = (Any, Field(default=..., description=str(k)))
        elif isinstance(inputs_schema, dict):
            for k, spec in inputs_schema.items():
                t_str = spec.get("type", "string")
                py_type = str
                if t_str == "int": py_type = int
                elif t_str == "float": py_type = float
                elif t_str == "bool": py_type = bool
                
                desc = spec.get("description", "")
                if "enum" in spec:
                    desc += f" (one of: {', '.join(str(v) for v in spec['enum'])})"
                
                default_val = spec.get("default", ...)
                fields[k] = (py_type, Field(default=default_val, description=desc))

        def create_tool(ename, econfig, efields):
            def _run_dynamic_event(
                *args, 
                tool_call_id: Annotated[str, InjectedToolCallId()] = "", 
                state: Annotated[dict, InjectedState()] = None, 
                **kwargs
            ) -> Command:
                interpreter = YAREInterpreter(state["yare_config"], state["bot_memory"])
                new_notes = []
                
                # Intercept shadow parameter before passing to YARE
                kwargs.pop("_engine_time_delta", None)
                
                if (
                    state.get("turn_phase") == "npc"
                    and "\n--- NPC Turn Resolution ---" not in state.get("system_notes", [])
                ):
                    new_notes.append("\n--- NPC Turn Resolution ---")
                
                interpreter.run_event(ename, kwargs)
                new_notes.extend(interpreter.notes)
                
                notes_text = "\n".join(interpreter.notes) if interpreter.notes else f"Event '{ename}': no effect."
                
                return Command(update={
                    "bot_memory_staging": [interpreter.state],
                    "system_notes": new_notes,
                    "agent_messages": [ToolMessage(content=notes_text, tool_call_id=tool_call_id)],
                })

            # Inject internal dependencies into schema so ToolNode knows to supply them,
            # while the Injected... annotations tell the LLM to ignore them.
            efields_with_injected = dict(efields)
            efields_with_injected["tool_call_id"] = (Annotated[str, InjectedToolCallId()], Field(default=""))
            efields_with_injected["state"] = (Annotated[dict, InjectedState()], Field(default=None))
            efields_with_injected["_engine_time_delta"] = (str, Field(default="PT0S", description="Estimated in-game time this action takes."))

            ArgsSchema = create_model(f"{ename}_Schema", **efields_with_injected)
            
            # Override docstring specifically for the tool definition
            desc = econfig.get("description", f"Trigger the {ename} event.")
            _run_dynamic_event.__doc__ = desc
            
            return tool(ename, args_schema=ArgsSchema)(_run_dynamic_event)

        t = create_tool(event_name, event_config, fields)
        tools.append(t)

    return tools


@tool
def advance_game_time(
    duration: str,
    tool_call_id: Annotated[str, InjectedToolCallId()] = "",
) -> Command:
    """Advance the in-game clock by a given duration without taking any other action. Required format: ISO 8601 (e.g., PT15M, PT2H) or shorthand (e.g., 15m, 2h)."""
    return Command(
        update={
            "agent_messages": [ToolMessage(content=f"Time advanced by {duration}.", tool_call_id=tool_call_id)],
        }
    )

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

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


def _format_game_time_context(bot_memory: Dict[str, Any]) -> str:
    """Return a small prompt snippet for in-game time context."""
    if "game_time" not in bot_memory:
        return ""
    return (
        "\n\n### In-Game Time Context:\n"
        f"state.game_time = {bot_memory.get('game_time')!r}\n"
        "Use this as canonical in-game time context."
    )


def _parse_duration_token(token: str) -> timedelta:
    token = token.strip()
    iso = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", token)
    if iso:
        h = int(iso.group(1) or 0)
        m = int(iso.group(2) or 0)
        s = int(iso.group(3) or 0)
        if h == 0 and m == 0 and s == 0:
            raise ValueError(
                f"advance_time duration cannot be empty (received: {token!r}; "
                "expected ISO duration like 'PT15M' or shorthand like '15m')"
            )
        return timedelta(hours=h, minutes=m, seconds=s)

    simple = re.fullmatch(r"(\d+)\s*([dhms])", token.lower())
    if simple:
        val = int(simple.group(1))
        unit = simple.group(2)
        if unit == "d":
            return timedelta(days=val)
        if unit == "h":
            return timedelta(hours=val)
        if unit == "m":
            return timedelta(minutes=val)
        return timedelta(seconds=val)

    raise ValueError(f"Unsupported advance_time duration format: {token!r}")


def _coerce_game_time_to_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def reset_agent_messages_node(state: GameState) -> dict:
    """Clear any stale agent-side messages at the start of a top-level invoke."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)], "npc_intent_called": False}


def cleanup_agent_messages_node(state: GameState) -> dict:
    """Remove agent-side messages before returning state to the client."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}


def pre_tools_node(state: GameState) -> dict:
    """Clear the YARE state staging buffer before tool execution."""
    return {"bot_memory_staging": None}


def post_tools_node(state: GameState) -> dict:
    """Commit the last staged YARE state snapshot into bot_memory, and reconcile time."""
    staging = state.get("bot_memory_staging") or []
    result: dict = {"bot_memory_staging": None}
    
    current_memory = staging[-1] if staging else state.get("bot_memory", {})
    new_memory = dict(current_memory)
    
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    total_delta = timedelta()
    for call in calls:
        args = call.get("args", {})
        delta_str = args.get("_engine_time_delta")
        if call.get("name") == "advance_game_time":
            delta_str = args.get("duration")
            
        if delta_str:
            try:
                total_delta += _parse_duration_token(delta_str)
            except ValueError:
                pass
                
    if total_delta.total_seconds() > 0:
        current_time = new_memory.get("game_time")
        base_dt = _coerce_game_time_to_datetime(current_time)
        if base_dt is not None:
            new_dt = base_dt + total_delta
            new_memory["game_time"] = new_dt.isoformat()

    if staging or total_delta.total_seconds() > 0:
        result["bot_memory"] = new_memory
        
    return result

# ---------------------------------------------------------
# 2. Graph Nodes
# ---------------------------------------------------------

def context_retrieval_node(state: GameState) -> dict:
    """
    1. Lore Node: Executes FIRST. Grabs the Vector RAG context
    based on the user's input, current location, active NPCs, and items.
    """
    store = VectorLoreStore.from_file(state["lore_path"])
    content = state['client_messages'][-1].get('content', '')

    query_parts = [content]
    memory = state.get("bot_memory", {})

    if "current_location" in memory:
        query_parts.append(str(memory["current_location"]))

    npc_data = memory.get("npc", {})
    if isinstance(npc_data, dict):
        if "name" in npc_data:
            query_parts.append(str(npc_data["name"]))

        # Check for Name Mode template
        if "template" in npc_data:
            query_parts.append(str(npc_data["template"]))

        # Check for Tag Mode array (can be multiple tags!)
        if "tags" in npc_data and isinstance(npc_data["tags"], list):
            query_parts.extend([str(tag) for tag in npc_data["tags"]])

    inventory = memory.get("inventory", [])
    if isinstance(inventory, list):
        query_parts.extend([str(item) for item in inventory])

    query_text = " ".join(query_parts)
    lore = store.query(query_text, top_k=3)
    return {"retrieved_lore": lore}


def cycle_tick_node(state: GameState) -> dict:
    """
    Run any YARE event configured with trigger_on: cycle_tick once per graph cycle.
    """
    events = state.get("yare_config", {}).get("events", {}) or {}
    tick_events = [
        name for name, cfg in events.items()
        if isinstance(cfg, dict) and cfg.get("trigger_on") == "cycle_tick"
    ]
    if not tick_events:
        return {}

    interpreter = YAREInterpreter(state["yare_config"], state["bot_memory"])
    new_notes: List[str] = []
    for event_name in tick_events:
        start = len(interpreter.notes)
        interpreter.run_event(event_name, {})
        new_notes.extend(interpreter.notes[start:])

    result: dict = {"bot_memory": interpreter.state}
    if new_notes:
        result["system_notes"] = new_notes
    return result


def director_node(state: GameState, *, llm=None, tools=None) -> dict:
    """
    2. Player Director: Maps user intent to YARE event triggers.

    Args:
        llm: Optional BaseChatModel. Bound to dynamic tools and invoked with the
             full director system prompt plus story history.
        tools: List of dynamic StructuredTools for available events.
    """
    loops = state.get("iteration_count", 0) + 1

    c_directives = state.get("prompt_directives", {}).get("director", "") or ""
    formatted_prompt = DIRECTOR_SYSTEM_PROMPT.format(
        retrieved_lore=state.get("retrieved_lore", ""),
        bot_memory=json.dumps(state.get("bot_memory", {})),
        system_notes="\n".join(state.get("system_notes", [])),
        npc_intent_called=state.get("npc_intent_called", False),
        cartridge_directives=c_directives,
    )
    system_content = formatted_prompt + _format_game_time_context(state.get("bot_memory", {}))

    result = {"iteration_count": loops, "turn_phase": "player"}
    if llm is not None:
        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))

        response = llm.bind_tools(tools or [], parallel_tool_calls=False).invoke(prompt_messages)
        result["agent_messages"] = [response]

    return result


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
    """Filters bot_memory to only include state variables the NPC tool is allowed to see.

    A top-level key is included only when its schema entry has ``npc_visibility: true``.
    Keys absent from the schema, or whose schema entry lacks the flag, are excluded.
    """
    visible: Dict[str, Any] = {}
    schema = yare_config.get("state_schema", {})
    for key, value in bot_memory.items():
        entry = schema.get(key, {})
        if isinstance(entry, dict) and entry.get("npc_visibility", False):
            visible[key] = value
    return visible


# ---------------------------------------------------------
# NPC Intent Tool
# ---------------------------------------------------------

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


def build_npc_intent_tool(npc_llm) -> StructuredTool:
    """Factory that returns a ``query_npc_intent`` tool wired to *npc_llm*."""

    @tool
    def query_npc_intent(
        present_npcs: List[NPCPresentation],
        scene_context: str,
        history_turns: int,
        dm_directives: str = "",
        tool_call_id: Annotated[str, InjectedToolCallId()] = "",
        state: Annotated[dict, InjectedState()] = None,
    ) -> Command:
        """Call this to see how a list of NPCs want to react before you calculate the rules.

        present_npcs is a list of NPCPresentation DTOs constructed by the Director.
        Each DTO contains the NPC's id, template (optional), and tags (optional).
        scene_context is a brief synthesis of the immediate physical environment.
        """
        state = state or {}
        yare_config: Dict[str, Any] = state.get("yare_config", {})
        bot_memory: Dict[str, Any] = state.get("bot_memory", {})
        npc_templates: Dict[str, Any] = yare_config.get("npc_templates", {})

        # Get attention budget settings with defaults
        settings = yare_config.get("engine_settings", {})
        min_credit = settings.get("npc_min_credit_threshold", 5)
        max_npcs = settings.get("max_batched_npcs", 3)

        # Score each NPC using the DTO — no bot_memory["npcs"] lookup
        scored_npcs = []
        for npc in (present_npcs or []):
            nid = npc.get("id", "")
            score = 0
            # Credit from Name template
            if tmpl := npc_templates.get(npc.get("template")):
                score += tmpl.get("credit", 0)
            # Credit from Tags
            for tag in (npc.get("tags") or []):
                if tmpl := npc_templates.get(tag):
                    score += tmpl.get("credit", 0)
            if score >= min_credit:
                scored_npcs.append({"id": nid, "score": score, "dto": npc})

        # Sort by score descending, then slice to max_npcs
        scored_npcs.sort(key=lambda x: x["score"], reverse=True)
        top_entries = scored_npcs[:max_npcs]
        top_npc_ids = [entry["id"] for entry in top_entries]

        # 1. Assemble history (most recent N turns, capped at 10)
        client_messages = state.get("client_messages", [])
        n = min(max(history_turns, 0), 10)
        history = client_messages[-n:] if n else []
        history_text = "\n".join(
            f"{m.get('role','user').capitalize()}: {m.get('content','')}" for m in history
        )

        # 2. Assemble lore
        lore_text: str = state.get("retrieved_lore", "")

        # 3. Assemble NPC-visible state
        visible_state = get_npc_visible_state(bot_memory, yare_config)

        # 4. Build batched profile text for top NPCs using DTO data
        profile_parts: list[str] = []
        for entry in top_entries:
            nid = entry["id"]
            npc_dto: Dict[str, Any] = entry["dto"]
            npc_desc_parts: list[str] = []

            # Name-mode: single template reference
            template_key = npc_dto.get("template")
            if template_key and template_key in npc_templates:
                npc_desc_parts.append(npc_templates[template_key].get("description", ""))

            # Tag-mode: concatenate multiple tag descriptions
            for tag in (npc_dto.get("tags") or []):
                if tag in npc_templates:
                    npc_desc_parts.append(npc_templates[tag].get("description", ""))

            npc_desc = " ".join(filter(None, npc_desc_parts)) or f"NPC id={nid}"
            profile_parts.append(f"NPC: {nid} | Profile: {npc_desc}")

        profile_text = "\n".join(profile_parts) if profile_parts else "No qualifying NPCs."

        # 5. When no NPCs qualify, return early without querying the LLM
        if not top_entries:
            return Command(
                update={
                    "agent_messages": [ToolMessage(content=profile_text, tool_call_id=tool_call_id)],
                }
            )

        # 6. Build prompt and invoke the LLM with structured output
        c_directives = state.get("prompt_directives", {}).get("npc", "") or ""
        formatted_prompt = NPC_SYSTEM_PROMPT.format(
            visible_state=json.dumps(visible_state),
            lore_text=lore_text,
            history_text=history_text,
            scene_context=scene_context,
            dm_directives=dm_directives,
            batched_profiles=profile_text,
            cartridge_directives=c_directives,
        )
        prompt_messages = [SystemMessage(content=formatted_prompt)]

        structured_llm = npc_llm.with_structured_output(BatchedNPCIntent)
        result: BatchedNPCIntent = structured_llm.invoke(prompt_messages)

        return Command(
            update={
                "npc_intent_called": True,
                "agent_messages": [ToolMessage(content=result.model_dump_json(), tool_call_id=tool_call_id)],
            }
        )

    return query_npc_intent


def narrator_node(state: GameState, *, llm=None) -> dict:
    """
    4. Narrator: Synthesizes lore, full system results, and user intent.

    Args:
        llm: Optional BaseChatModel. Invoked with the narrator prompt,
             system_notes, lore, and public state to produce prose.
             Wire via: functools.partial(narrator_node, llm=my_llm)
    """
    public_state = get_public_state(state["bot_memory"], state["yare_config"])

    result: dict = {"iteration_count": 0, "system_notes": [], "retrieved_lore": ""}

    if llm is not None:
        # Find the Director's final Scene Directive (last AIMessage without tool calls)
        scene_directives = ""
        for msg in reversed(state.get("agent_messages", [])):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                scene_directives = msg.content
                break

        c_directives = state.get("prompt_directives", {}).get("narrator", "") or ""
        formatted_prompt = NARRATOR_SYSTEM_PROMPT.format(
            public_state=json.dumps(public_state),
            scene_directives=scene_directives,
            cartridge_directives=c_directives,
        )
        system_content = formatted_prompt + _format_game_time_context(state.get("bot_memory", {}))
        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        response = llm.invoke(prompt_messages)
        narrative = response.content
        result["narrative"] = narrative
        result["client_messages"] = [{"role": "assistant", "content": narrative}]

    return result

# ---------------------------------------------------------
# 3. Edge Routers
# ---------------------------------------------------------

def route_director(state: GameState) -> Literal["PreTools", "Narrator"]:
    """Route from Director based on tool calls."""
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "PreTools"
    return "Narrator"


def route_rules(state: GameState) -> Literal["Director"]:
    """After ToolNode fires, always return to the Director."""
    return "Director"

# ---------------------------------------------------------
# 4. Graph Factory
# ---------------------------------------------------------

def build_graph(
    yare_config: Dict[str, Any],
    llm_director=None,
    llm_npc=None,
    llm_narrator=None,
):
    """
    Build and compile a LangGraph for the given YARE config and LLM instances.

    This is the single authoritative factory for constructing the MnesOS graph.
    The Orchestrator (and any other runner) should call this rather than
    assembling the graph inline.

    Args:
        yare_config:   Parsed YARE configuration dict (from yare.yaml).
        llm_director:  LangChain BaseChatModel for the Director node (optional).
        llm_npc: LangChain BaseChatModel for the NPC Brain tool (optional).
        llm_narrator:  LangChain BaseChatModel for the Narrator node (optional).

    Returns:
        A compiled LangGraph application ready for invoke().
    """
    dynamic_tools = build_yare_event_tools(yare_config)
    dynamic_tools.append(advance_game_time)

    if llm_npc is not None:
        dynamic_tools = dynamic_tools + [build_npc_intent_tool(llm_npc)]

    graph = StateGraph(GameState)

    graph.add_node("ResetAgentMessages", reset_agent_messages_node)
    graph.add_node("Lore", context_retrieval_node)
    graph.add_node("CycleTick", cycle_tick_node)
    graph.add_node("Director", functools.partial(director_node, llm=llm_director, tools=dynamic_tools))
    graph.add_node("PreTools", pre_tools_node)

    if dynamic_tools:
        graph.add_node("Tools", ToolNode(dynamic_tools, messages_key="agent_messages"))
    else:
        graph.add_node("Tools", lambda state: state)

    graph.add_node("PostTools", post_tools_node)
    graph.add_node("Narrator", functools.partial(narrator_node, llm=llm_narrator))
    graph.add_node("CleanupAgentMessages", cleanup_agent_messages_node)

    graph.set_entry_point("ResetAgentMessages")
    graph.add_edge("ResetAgentMessages", "Lore")
    graph.add_edge("Lore", "CycleTick")
    graph.add_edge("CycleTick", "Director")

    graph.add_conditional_edges(
        "Director", route_director, {"PreTools": "PreTools", "Narrator": "Narrator"}
    )
    graph.add_edge("PreTools", "Tools")
    graph.add_edge("Tools", "PostTools")
    graph.add_conditional_edges(
        "PostTools", route_rules, {"Director": "Director"}
    )

    graph.add_edge("Narrator", "CleanupAgentMessages")
    graph.add_edge("CleanupAgentMessages", END)

    return graph.compile()


# ---------------------------------------------------------
# 5. Default workflow (for visualization / testing)
# ---------------------------------------------------------
@tool
def _dummy_tool() -> str:
    """Dummy tool for graph visualization fallback."""
    return "Dummy"

# Default workflow for visualization and testing (uses monolithic architecture)
workflow = StateGraph(GameState)

workflow.add_node("ResetAgentMessages", reset_agent_messages_node)
workflow.add_node("Lore", context_retrieval_node)
workflow.add_node("CycleTick", cycle_tick_node)
workflow.add_node("Director", director_node)
workflow.add_node("PreTools", pre_tools_node)
workflow.add_node("Tools", ToolNode([_dummy_tool], messages_key="agent_messages"))
workflow.add_node("PostTools", post_tools_node)
workflow.add_node("Narrator", narrator_node)
workflow.add_node("CleanupAgentMessages", cleanup_agent_messages_node)

workflow.set_entry_point("ResetAgentMessages")
workflow.add_edge("ResetAgentMessages", "Lore")
workflow.add_edge("Lore", "CycleTick")
workflow.add_edge("CycleTick", "Director")

# Monolithic architecture: Director routes to Narrator (no separate NPC_Brain)
workflow.add_conditional_edges("Director", route_director, {
    "PreTools": "PreTools",
    "Narrator": "Narrator",
})

workflow.add_edge("PreTools", "Tools")
workflow.add_edge("Tools", "PostTools")

workflow.add_conditional_edges("PostTools", route_rules, {
    "Director": "Director",
})

workflow.add_edge("Narrator", "CleanupAgentMessages")
workflow.add_edge("CleanupAgentMessages", END)
