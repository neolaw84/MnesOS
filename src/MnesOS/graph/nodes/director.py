import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, AIMessage
from ..state import GameState
from ..utils.messages import _client_messages_to_langchain_messages
from ..utils.time import _format_game_time_context
from ...prompts import DIRECTOR_SYSTEM_PROMPT

def _get_last_ai_tool_calls(agent_messages: list) -> list:
    """Return the tool_calls list from the most recent AIMessage, or empty list."""
    for msg in reversed(agent_messages):
        if isinstance(msg, AIMessage):
            return getattr(msg, "tool_calls", []) or []
    return []

def director_node(state: GameState, *, llm=None, tools=None) -> dict:
    """
    2. Player Director: Maps user intent to YARE event triggers.
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
