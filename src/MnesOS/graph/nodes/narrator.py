import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from ..state import GameState, get_public_state
from ..utils.messages import _client_messages_to_langchain_messages
from ..utils.time import _format_game_time_context
from ..utils.persona import build_persona_background_context
from ...prompts import NARRATOR_SYSTEM_PROMPT

def narrator_node(state: GameState, config: RunnableConfig, *, llm=None) -> dict:
    """
    4. Narrator: Synthesizes lore, full system results, and user intent.

    Static cartridge data (``yare_config``, ``prompt_directives``,
    ``persona_context``) is read from ``config["configurable"]``.
    """
    configurable = (config or {}).get("configurable", {})
    yare_config = configurable.get("yare_config", {})
    public_state = get_public_state(state["bot_memory"], yare_config)

    result: dict = {"iteration_count": 0, "system_notes": [], "retrieved_lore": ""}

    if llm is not None:
        # Find the Director's final Scene Directive (last AIMessage without tool calls)
        scene_directives = ""
        for msg in reversed(state.get("agent_messages", [])):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                scene_directives = msg.content
                break

        c_directives = configurable.get("prompt_directives", {}).get("narrator", "") or ""
        formatted_prompt = NARRATOR_SYSTEM_PROMPT.format(
            public_state=json.dumps(public_state),
            scene_directives=scene_directives,
            cartridge_directives=c_directives,
        )
        persona_background = build_persona_background_context(configurable.get("persona_context", {}))
        system_content = (
            formatted_prompt
            + persona_background
            + _format_game_time_context(state.get("bot_memory", {}))
        )
        prompt_messages = [SystemMessage(content=system_content)]
        prompt_messages.extend(
            _client_messages_to_langchain_messages(state.get("client_messages", []))
        )
        response = llm.invoke(prompt_messages)
        narrative = response.content
        result["narrative"] = narrative
        result["client_messages"] = [{"role": "assistant", "content": narrative}]

    return result
