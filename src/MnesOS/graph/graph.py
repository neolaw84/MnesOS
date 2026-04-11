"""
graph.graph — LangGraph state definition, nodes, edge routers, and factory.

This module is the single source of truth for the MnesOS turn graph.  It is
intentionally kept in a sub-package (``MnesOS/graph/``) so that graph-related
helpers can be split into additional sibling modules in the future without
changing import paths for callers that use ``from MnesOS.graph import ...``.

Refactoring note
~~~~~~~~~~~~~~~~
If graph complexity grows, consider extracting:
* ``nodes.py``   — the individual node functions (director_node, narrator_node,
                   npc_brain_node, context_retrieval_node, …)
* ``routers.py`` — the edge-routing functions (route_director, route_rules, …)
* ``tools.py``   — build_yare_event_tools and related helpers

The ``graph.graph`` module would then import and re-assemble them.  The
``MnesOS/graph/__init__.py`` re-export layer means that callers do *not* need
to be updated when this internal split happens.
"""

from typing import Annotated, TypedDict, Literal, List, Dict, Any, Optional, Tuple
import functools
import operator
import re
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolCallId

# Import our refined logic components from the parent package.
# The graph sub-package lives at MnesOS/graph/, so sibling modules such as
# interpreter, context, and prompts are one level up (``..``).
from ..interpreter import YAREInterpreter
from ..context import VectorLoreStore
from ..prompts import DIRECTOR_SYSTEM_PROMPT, NARRATOR_SYSTEM_PROMPT, NPC_BRAIN_SYSTEM_PROMPT
from pydantic import create_model, Field
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

            ArgsSchema = create_model(f"{ename}_Schema", **efields_with_injected)
            
            # Override docstring specifically for the tool definition
            desc = econfig.get("description", f"Trigger the {ename} event.")
            _run_dynamic_event.__doc__ = desc
            
            return tool(ename, args_schema=ArgsSchema)(_run_dynamic_event)

        t = create_tool(event_name, event_config, fields)
        tools.append(t)

    return tools


@tool
def end_of_narration(
    actions: Optional[list[dict]] = None,
    tool_call_id: Annotated[str, InjectedToolCallId()] = "",
    state: Annotated["GameState", InjectedState()] = None,
) -> Command:
    """
    Apply end-of-narration engine actions from the narrator.

    Supported actions:
      - {"type": "advance_time", "duration": "PT15M"} (also 15m/2h/1d/30s)
      - {"type": "set_game_time", "value": "2026-04-10T10:00:00+00:00"}
    """
    updated_memory, warnings = _apply_end_of_narration_actions(
        state.get("bot_memory", {}),
        actions or [],
    )
    notes_text = "\n".join(warnings) if warnings else "end_of_narration: no effect."
    update: Dict[str, Any] = {
        "agent_messages": [ToolMessage(content=notes_text, tool_call_id=tool_call_id)],
    }
    if updated_memory is not None:
        update["bot_memory"] = updated_memory
    if warnings:
        update["system_notes"] = warnings
    return Command(update=update)

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


def _apply_end_of_narration_actions(
    bot_memory: Dict[str, Any],
    actions: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Apply structured narrator end-of-narration actions to bot_memory."""
    if not actions:
        return None, []

    updated = dict(bot_memory)
    current = updated.get("game_time")
    warnings: List[str] = []
    changed = False

    for action in actions:
        if not isinstance(action, dict):
            warnings.append("SYSTEM: end_of_narration skipped invalid action payload.")
            continue

        kind = str(action.get("type", "")).strip().lower()
        if kind == "set_game_time":
            value = str(action.get("value", "")).strip()
            if not value:
                warnings.append("SYSTEM: end_of_narration set_game_time skipped because value is empty.")
                continue
            updated["game_time"] = value
            current = value
            changed = True
            continue

        if kind == "advance_time":
            duration = str(action.get("duration", "")).strip()
            if not duration:
                warnings.append("SYSTEM: end_of_narration advance_time skipped because duration is empty.")
                continue
            base_dt = _coerce_game_time_to_datetime(current)
            if base_dt is None:
                warnings.append(
                    f"SYSTEM: end_of_narration advance_time skipped because state.game_time is missing or unparseable (current value: {current!r})."
                )
                continue
            try:
                delta = _parse_duration_token(duration)
            except ValueError as exc:
                warnings.append(f"SYSTEM: end_of_narration advance_time skipped ({exc}).")
                continue
            new_dt = base_dt + delta
            updated["game_time"] = new_dt.isoformat()
            current = updated["game_time"]
            changed = True
            continue

        warnings.append(f"SYSTEM: end_of_narration skipped unknown action type '{kind}'.")

    return (updated if changed else None), warnings


def reset_agent_messages_node(state: GameState) -> dict:
    """Clear any stale agent-side messages at the start of a top-level invoke."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}


def cleanup_agent_messages_node(state: GameState) -> dict:
    """Remove agent-side messages before returning state to the client."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}


def pre_tools_node(state: GameState) -> dict:
    """Clear the YARE state staging buffer before tool execution."""
    return {"bot_memory_staging": None}


def post_tools_node(state: GameState) -> dict:
    """Commit the last staged YARE state snapshot into bot_memory."""
    staging = state.get("bot_memory_staging") or []
    result: dict = {"bot_memory_staging": None}
    if staging:
        result["bot_memory"] = staging[-1]
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
        if "archetype" in npc_data: query_parts.append(str(npc_data["archetype"]))
        if "name" in npc_data: query_parts.append(str(npc_data["name"]))
        if "species" in npc_data: query_parts.append(str(npc_data["species"]))

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

    director_prompt = DIRECTOR_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("director", "")
    if directives:
        director_prompt += "\n\n### Cartridge Directives:\n" + directives

    result = {"iteration_count": loops, "turn_phase": "player"}
    if llm is not None:
        system_content = director_prompt
        system_content += _format_game_time_context(state.get("bot_memory", {}))

        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))

        response = llm.bind_tools(tools or [], parallel_tool_calls=False).invoke(prompt_messages)
        result["agent_messages"] = [response]

    return result


def npc_brain_node(state: GameState, *, llm=None, tools=None) -> dict:
    """
    3. NPC Brain: Reads outcomes of the player's tools AND retrieved lore.
    Governs ALL NPCs in the scene proactively.

    Args:
        llm: Optional BaseChatModel. Bound to dynamic tools and invoked with NPC
             state and lore context to decide tactical actions.
        tools: List of dynamic StructuredTools for available events.
    """
    npc_brain_prompt = NPC_BRAIN_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("npc_brain", "")
    if directives:
        npc_brain_prompt += "\n\n### Cartridge Directives:\n" + directives

    result = {"iteration_count": 0, "turn_phase": "npc"}
    if llm is not None:
        system_content = npc_brain_prompt
        system_content += _format_game_time_context(state.get("bot_memory", {}))
        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))
        prompt_messages.append(HumanMessage(content=(
            f"NPC State: {state['bot_memory'].get('npc', {})}\n"
            f"System Notes: {state.get('system_notes', [])}\n"
            f"Retrieved Lore: {state.get('retrieved_lore', '')}"
        )))
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


def narrator_node(state: GameState, *, llm=None) -> dict:
    """
    4. Narrator: Synthesizes lore, full system results, and user intent.

    Args:
        llm: Optional BaseChatModel. Invoked with the narrator prompt,
             system_notes, lore, and public state to produce prose.
             Wire via: functools.partial(narrator_node, llm=my_llm)
    """
    public_state = get_public_state(state["bot_memory"], state["yare_config"])

    narrator_prompt = NARRATOR_SYSTEM_PROMPT
    directives = state.get("prompt_directives", {}).get("narrator", "")
    if directives:
        narrator_prompt += "\n\n### Cartridge Directives:\n" + directives

    result: dict = {"iteration_count": 0, "system_notes": [], "retrieved_lore": ""}

    if llm is not None:
        end_of_narration_contract = (
            "\n\n### End of Narration Contract:\n"
            "If engine-side end-of-narration actions are needed, call tool end_of_narration with:\n"
            "- actions: [{type:'advance_time', duration:'PT15M'}]\n"
            "- actions: [{type:'set_game_time', value:'2026-04-10T10:00:00+00:00'}]\n"
            "You may include both actions and narrative text in the same response."
        )
        prompt_messages = [SystemMessage(content=narrator_prompt + _format_game_time_context(state.get("bot_memory", {})) + end_of_narration_contract)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))
        prompt_messages.append(HumanMessage(content=(
            f"System Notes: {state.get('system_notes', [])}\n"
            f"Retrieved Lore: {state.get('retrieved_lore', '')}\n"
            f"Public State: {public_state}"
        )))
        response = llm.bind_tools([end_of_narration], parallel_tool_calls=False).invoke(prompt_messages)
        narrative = response.content
        result["narrative"] = narrative
        result["client_messages"] = [{"role": "assistant", "content": narrative}]

        current_memory = state.get("bot_memory", {})
        warnings: List[str] = []
        changed = False
        for call in (getattr(response, "tool_calls", None) or []):
            if call.get("name") != "end_of_narration":
                continue
            cmd = end_of_narration.func(
                actions=(call.get("args") or {}).get("actions"),
                tool_call_id=call.get("id", ""),
                state={**state, "bot_memory": current_memory},
            )
            if isinstance(cmd, Command):
                update = cmd.update or {}
                if "bot_memory" in update:
                    current_memory = update["bot_memory"]
                    changed = True
                warnings.extend(update.get("system_notes", []))
        if changed:
            result["bot_memory"] = current_memory
        if warnings:
            result["system_notes"] = warnings

    return result

# ---------------------------------------------------------
# 3. Edge Routers
# ---------------------------------------------------------

def route_director(state: GameState) -> Literal["PreTools", "Narrator"]:
    """Route from Director in monolithic mode based on tool calls."""
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "PreTools"
    return "Narrator"


def route_director_separate(state: GameState) -> Literal["PreTools", "NPC_Brain"]:
    """Route from Director in decoupled (separate NPC brain) mode based on tool calls."""
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "PreTools"
    return "NPC_Brain"


def route_rules(state: GameState) -> Literal["Director", "NPC_Brain"]:
    """After ToolNode fires, return to the LLM that triggered it."""
    phase = state.get("turn_phase")
    if phase == "player":
        return "Director"
    return "NPC_Brain"


def route_npc_brain(state: GameState) -> Literal["PreTools", "Narrator"]:
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "PreTools"
    return "Narrator"

# ---------------------------------------------------------
# 4. Graph Factory
# ---------------------------------------------------------

def build_graph(
    yare_config: Dict[str, Any],
    llm_director=None,
    llm_npc_brain=None,
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
        llm_npc_brain: LangChain BaseChatModel for the NPC Brain node (optional).
        llm_narrator:  LangChain BaseChatModel for the Narrator node (optional).

    Returns:
        A compiled LangGraph application ready for invoke().
    """
    dynamic_tools = build_yare_event_tools(yare_config)
    separate_npc_brain = yare_config.get("separate_npc_brain", False)

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

    if separate_npc_brain:
        graph.add_node("NPC_Brain", functools.partial(npc_brain_node, llm=llm_npc_brain, tools=dynamic_tools))
        graph.add_conditional_edges(
            "Director", route_director_separate, {"PreTools": "PreTools", "NPC_Brain": "NPC_Brain"}
        )
        graph.add_edge("PreTools", "Tools")
        graph.add_edge("Tools", "PostTools")
        graph.add_conditional_edges(
            "PostTools", route_rules, {"Director": "Director", "NPC_Brain": "NPC_Brain"}
        )
        graph.add_conditional_edges(
            "NPC_Brain", route_npc_brain, {"PreTools": "PreTools", "Narrator": "Narrator"}
        )
    else:
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
