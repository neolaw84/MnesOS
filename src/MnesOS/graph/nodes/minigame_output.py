import json
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from ..state import GameState
from ..utils.messages import _client_messages_to_langchain_messages
from ..utils.llm_resolver import resolve_llm
from ...prompts import MINIGAME_OUTPUT_SYSTEM_PROMPT

def minigame_output_node(state: GameState, config: RunnableConfig, *, llm=None) -> dict:
    """
    Minigame Output Router (Director-lite): Tool-less node that sets up
    the Scene Directives for the Narrator immediately after a minigame is requested.
    """
    configurable = (config or {}).get("configurable", {})
    bot_memory = dict(state.get("bot_memory", {}))
    pending = bot_memory.get("_pending_interaction", {})
    pending_id = pending.get("minigame_id", "Unknown Minigame")

    formatted_prompt = MINIGAME_OUTPUT_SYSTEM_PROMPT.format(
        pending_minigame_id=pending_id
    )

    effective_llm = resolve_llm(configurable, "director", fallback=llm)

    result = {"turn_phase": "player"}
    if effective_llm is not None:
        prompt_messages = [SystemMessage(content=formatted_prompt)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        prompt_messages.extend(state.get("agent_messages", []))

        # Do NOT bind tools. Just regular invocation.
        response = effective_llm.invoke(prompt_messages)
        result["agent_messages"] = [response]

    return result
