from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from ...exceptions import InteractionRoutingError
from ...interpreter import YAREInterpreter
from ..state import GameState


def minigame_input_node(state: GameState, config: RunnableConfig) -> dict:
    """Securely route structured interaction payloads into deterministic YARE events.

    Currently supports:
    - ``interaction_type == "minigame"``: resolves a pending minigame by invoking the
      trusted ``resolver_event`` stored in ``bot_memory["_pending_interaction"]``.
    """
    interaction = state.get("incoming_interaction")
    if not interaction:
        return {}

    if interaction.get("interaction_type") != "minigame":
        return {"incoming_interaction": None}

    bot_memory: Dict[str, Any] = dict(state.get("bot_memory") or {})
    pending = bot_memory.get("_pending_interaction")
    if not isinstance(pending, dict):
        raise InteractionRoutingError(
            f"No valid pending minigame interaction to resolve "
            f"(expected dict, got {type(pending).__name__})."
        )

    if pending.get("interaction_type") != "minigame":
        raise InteractionRoutingError("Pending interaction is not a minigame.")

    pending_minigame_id = pending.get("minigame_id")
    incoming_minigame_id = interaction.get("minigame_id")
    if not pending_minigame_id or pending_minigame_id != incoming_minigame_id:
        raise InteractionRoutingError(
            "minigame_id mismatch between pending interaction and incoming payload."
        )

    resolver_event = pending.get("resolver_event")
    if not isinstance(resolver_event, str) or not resolver_event:
        raise InteractionRoutingError("Pending minigame interaction is missing resolver_event.")

    configurable = (config or {}).get("configurable", {})
    yare_config = configurable.get("yare_config", {}) or {}
    if resolver_event not in (yare_config.get("events", {}) or {}):
        raise InteractionRoutingError(f"Unknown resolver_event: {resolver_event!r}")

    # Run the resolver deterministically (no LLM involved).
    interpreter = YAREInterpreter(yare_config, bot_memory)
    interpreter.run_event(
        resolver_event,
        {
            "status": interaction.get("status"),
            "metrics": interaction.get("metrics") or {},
            "minigame_specific_data": interaction.get("minigame_specific_data") or {},
        },
    )

    # Always clear pending interaction server-side to prevent replay attacks.
    new_memory = dict(interpreter.state)
    new_memory.pop("_pending_interaction", None)

    new_notes = list(state.get("system_notes") or [])
    new_notes.append(f"Minigame resolved: {pending_minigame_id}")
    new_notes.extend(interpreter.notes)

    # Inform the Director about the outcome via agent_messages
    outcome_msg = (
        f"MINIGAME RESOLVED: {pending_minigame_id}\n"
        f"Status: {interaction.get('status')}\n"
        f"Metrics: {interaction.get('metrics')}\n"
        f"System Notes: {', '.join(interpreter.notes)}"
    )

    return {
        "bot_memory": new_memory,
        "system_notes": new_notes,
        "agent_messages": [HumanMessage(content=outcome_msg)],
        "incoming_interaction": None,
    }

