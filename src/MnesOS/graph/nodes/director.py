import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from ..state import GameState
from ...constants import MAX_TOOL_CALL, MAX_NPC_INTENT_CALL
from ..utils.messages import _client_messages_to_langchain_messages
from ..utils.time import _format_game_time_context
from ..utils.persona import build_persona_background_context
from ...prompts import DIRECTOR_SYSTEM_PROMPT

def _get_last_ai_tool_calls(agent_messages: list) -> list:
    """Return the tool_calls list from the most recent AIMessage, or empty list."""
    for msg in reversed(agent_messages):
        if isinstance(msg, AIMessage):
            return getattr(msg, "tool_calls", []) or []
    return []

def director_node(state: GameState, config: RunnableConfig, *, llm=None, tools=None) -> dict:
    """
    2. Player Director: Maps user intent to YARE event triggers.

    Static cartridge data (``prompt_directives``, ``persona_context``) is
    read from ``config["configurable"]`` rather than from the graph state.
    LLM can be provided via build_graph closure or per-request via
    ``config["configurable"]["llm_clients"]["director"]`` (BYOK).
    """
    configurable = (config or {}).get("configurable", {})
    loops = state.get("iteration_count", 0) + 1

    c_directives = configurable.get("prompt_directives", {}).get("director", "") or ""
    formatted_prompt = DIRECTOR_SYSTEM_PROMPT.format(
        retrieved_lore=state.get("retrieved_lore", ""),
        bot_memory=json.dumps(state.get("bot_memory", {})),
        system_notes="\n".join(state.get("system_notes", [])),
        npc_intent_calls=state.get("npc_intent_calls", 0),
        max_npc_intent_calls=MAX_NPC_INTENT_CALL,
        max_tool_calls=MAX_TOOL_CALL,
        iteration_count=loops,
        cartridge_directives=c_directives,
        turn_start_time=state.get("turn_start_time", ""),
    )
    persona_background = build_persona_background_context(configurable.get("persona_context", {}))
    system_content = (
        formatted_prompt
        + persona_background
        + _format_game_time_context(state.get("bot_memory", {}))
    )

    # Resolve LLM: closure arg > config BYOK > None (dry-run)
    effective_llm = llm or configurable.get("llm_clients", {}).get("director")

    result = {"iteration_count": loops, "turn_phase": "player"}
    if effective_llm is not None:
        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))

        response = effective_llm.bind_tools(tools or [], parallel_tool_calls=False).invoke(prompt_messages)
        result["agent_messages"] = [response]

    return result
