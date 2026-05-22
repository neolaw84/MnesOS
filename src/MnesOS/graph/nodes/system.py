import ast
from datetime import timedelta
from typing import Any, Dict, List
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain_core.messages import RemoveMessage
from langchain_core.runnables import RunnableConfig
from ..state import GameState
from ..utils.time import _parse_duration_token, _coerce_game_time_to_datetime
from ..utils.messages import _client_messages_to_langchain_messages
from ...interpreter import YAREInterpreter
from .director import _get_last_ai_tool_calls

def reset_agent_messages_node(state: GameState) -> dict:
    """Clear any stale agent-side messages at the start of a top-level invoke."""
    current_game_time = state.get("bot_memory", {}).get("game_time", "")
    return {
        "agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)], 
        "npc_intent_calls": 0,
        "turn_start_time": current_game_time
    }

def cleanup_agent_messages_node(state: GameState) -> dict:
    """Remove agent-side messages before returning state to the client."""
    return {"agent_messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}

def pre_tools_node(state: GameState) -> dict:
    """Clear the YARE state staging buffer before tool execution."""
    return {"bot_memory_staging": None}

def _normalize_pending_interaction(bot_memory: Dict[str, Any]) -> Dict[str, Any]:
    pending = bot_memory.get("_pending_interaction")
    if pending is None or isinstance(pending, dict):
        return bot_memory
    normalized: Dict[str, Any] | None = None
    if isinstance(pending, str):
        pending_str = pending.strip()
        if pending_str:
            try:
                parsed = ast.literal_eval(pending_str)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, dict):
                normalized = parsed
    if normalized is None:
        normalized = {}
    bot_memory["_pending_interaction"] = normalized
    return bot_memory

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
        delta_str = args.get("engine_time_delta")
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
        result["bot_memory"] = _normalize_pending_interaction(new_memory)
        
    return result

def cycle_tick_node(state: GameState, config: RunnableConfig) -> dict:
    """
    Run any YARE event configured with trigger_on: cycle_tick once per graph cycle.

    ``yare_config`` is read from ``config["configurable"]``.
    """
    configurable = (config or {}).get("configurable", {})
    yare_config = configurable.get("yare_config", {})
    events = yare_config.get("events", {}) or {}
    tick_events = [
        name for name, cfg in events.items()
        if isinstance(cfg, dict) and cfg.get("trigger_on") == "cycle_tick"
    ]
    if not tick_events:
        return {}

    interpreter = YAREInterpreter(yare_config, state["bot_memory"])
    new_notes: List[str] = []
    for event_name in tick_events:
        start = len(interpreter.notes)
        interpreter.run_event(event_name, {})
        new_notes.extend(interpreter.notes[start:])

    result: dict = {"bot_memory": _normalize_pending_interaction(interpreter.state)}
    if new_notes:
        result["system_notes"] = new_notes
    return result
