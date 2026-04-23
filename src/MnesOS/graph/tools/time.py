from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command

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
