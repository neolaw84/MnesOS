import functools
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .state import GameState
from .nodes.system import (
    reset_agent_messages_node,
    cleanup_agent_messages_node,
    pre_tools_node,
    post_tools_node,
    cycle_tick_node,
)
from .nodes.director import director_node, _get_last_ai_tool_calls
from .nodes.lore import context_retrieval_node
from .nodes.narrator import narrator_node
from .tools.yare import build_yare_event_tools
from .tools.time import advance_game_time
from .tools.npc import build_npc_intent_tool

MAX_ITERATIONS = 3

def route_director(state: GameState) -> Literal["PreTools", "Narrator"]:
    """Route from Director based on tool calls."""
    calls = _get_last_ai_tool_calls(state.get("agent_messages", []))
    if calls and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "PreTools"
    return "Narrator"

def route_rules(state: GameState) -> Literal["Director"]:
    """After ToolNode fires, always return to the Director."""
    return "Director"

def build_graph(
    yare_config: Dict[str, Any],
    llm_director=None,
    llm_npc=None,
    llm_narrator=None,
    prompt_directives: Dict[str, str] | None = None,
):
    """
    Build and compile a LangGraph for the given YARE config and LLM instances.

    Static cartridge data that was formerly carried in ``GameState`` is now
    closed over at build time (for tools) or passed at invoke time via
    ``RunnableConfig["configurable"]`` (for nodes).
    """
    prompt_directives = prompt_directives or {}
    dynamic_tools = build_yare_event_tools(yare_config)
    dynamic_tools.append(advance_game_time)

    if llm_npc is not None:
        dynamic_tools = dynamic_tools + [
            build_npc_intent_tool(llm_npc, yare_config=yare_config, prompt_directives=prompt_directives)
        ]

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
