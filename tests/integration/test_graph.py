"""
Integration tests for graph.py — tests that exercise the full compiled workflow.
"""

import pytest
from langchain_core.messages import ToolMessage

from MnesOS.graph import build_graph, GameState


# CWD-relative path — pytest is always invoked from the project root.
GENERIC_RPG_LORE = "cartridges/generic-rpg/bot_lore.md"


def make_state(**overrides) -> dict:
    """Builds a minimal GameState-shaped dict for workflow invocation tests."""
    base = {
        "client_messages": [{"role": "user", "content": "I look around."}],
        "agent_messages": [],
        "bot_memory": {
            "player": {"hp": 100, "gold": 0, "level": 1},
            "npc":    {"hp": 20, "strength": 5, "archetype": ""},
            "current_location": "Crossroads",
        },
        "yare_config": {
            "state_schema": {
                "player": {
                    "hp":    {"type": "int", "default": 100, "visibility": "public"},
                    "gold":  {"type": "int", "default": 0,   "visibility": "public"},
                    "level": {"type": "int", "default": 1,   "visibility": "public"},
                },
                "npc": {
                    "hp":       {"type": "int", "default": 20, "visibility": "public"},
                    "strength": {"type": "int", "default": 5,  "visibility": "public"},
                },
            },
            "events": {},
            "macros": {},
        },
        "prompt_directives": {},
        "lore_path": GENERIC_RPG_LORE,
        "bot_memory_staging": [],
        "system_notes": [],
        "retrieved_lore": "",
        "iteration_count": 0,
        "turn_phase": "",
    }
    base.update(overrides)
    return base


class TestWorkflowAgentMessageCleanup:
    def test_entry_node_clears_stale_agent_messages(self):
        state = make_state(
            agent_messages=[ToolMessage(content="stale", tool_call_id="old_call")],
            client_messages=[{"role": "user", "content": "I look around."}],
        )
        app = build_graph(state["yare_config"])
        result = app.invoke(state)
        assert result.get("agent_messages", []) == []

    def test_exit_node_returns_empty_agent_messages(self):
        state = make_state(
            client_messages=[{"role": "user", "content": "I look around."}],
            agent_messages=[ToolMessage(content="stale", tool_call_id="old_call")],
        )
        app = build_graph(state["yare_config"])
        result = app.invoke(state)
        assert result.get("agent_messages", []) == []
