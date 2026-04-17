from ..shared import make_state
from MnesOS.graph.nodes.system import (
    cycle_tick_node, 
    pre_tools_node, 
    post_tools_node, 
    reset_agent_messages_node, 
    cleanup_agent_messages_node,
)
from MnesOS.graph import route_director, route_rules
from MnesOS.graph.state import GameState
from langchain_core.messages import RemoveMessage, ToolMessage
from datetime import timedelta

class TestCycleTickNode:
    def test_cycle_tick_runs_triggered_event(self):
        state = make_state(
            yare_config={
                "state_schema": {
                    "game_time": {"type": "string", "default": "2026-04-10T00:00:00", "visibility": "public"},
                },
                "events": {
                    "tick": {
                        "trigger_on": "cycle_tick",
                        "steps": [
                            {"action": "set", "var": "state.game_time", "value": "'2026-04-10T00:10:00'"},
                            {"action": "note", "message": "Cycle tick applied."},
                        ],
                    }
                },
                "macros": {},
            },
            bot_memory={"game_time": "2026-04-10T00:00:00"},
        )
        result = cycle_tick_node(state)
        assert result["bot_memory"]["game_time"] == "2026-04-10T00:10:00"
        assert any("Cycle tick" in n for n in result.get("system_notes", []))

    def test_cycle_tick_no_registered_events_is_noop(self):
        state = make_state()
        result = cycle_tick_node(state)
        assert result == {}

class TestResetAgentMessagesNode:
    def test_clears_agent_messages(self):
        state = make_state(agent_messages=["stale"])
        result = reset_agent_messages_node(state)
        assert any(isinstance(m, RemoveMessage) for m in result["agent_messages"])
    
    def test_resets_npc_intent_called(self):
        state = make_state(npc_intent_called=True)
        result = reset_agent_messages_node(state)
        assert result["npc_intent_called"] is False

class TestCleanupAgentMessagesNode:
    def test_clears_agent_messages(self):
        state = make_state(agent_messages=["stale"])
        result = cleanup_agent_messages_node(state)
        assert any(isinstance(m, RemoveMessage) for m in result["agent_messages"])

class TestPreToolsNode:
    def test_clears_staging_by_returning_none(self):
        state = make_state(bot_memory_staging=[{"npc": {"hp": 5}}])
        result = pre_tools_node(state)
        assert result["bot_memory_staging"] is None

    def test_does_not_touch_bot_memory(self):
        state = make_state()
        result = pre_tools_node(state)
        assert "bot_memory" not in result

class TestPostToolsNode:
    def test_post_tools_extracts_and_sums_time_delta_from_tools(self):
        from langchain_core.messages import AIMessage
        from datetime import datetime
        
        state = make_state(bot_memory_staging=[], bot_memory={"game_time": "2026-04-10T08:00:00+00:00"})
        
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "some_tool", "args": {"engine_time_delta": "PT15M"}, "id": "1"},
                {"name": "advance_game_time", "args": {"duration": "PT45M"}, "id": "2"},
            ]
        )
        state["agent_messages"] = [ai_msg]
        
        result = post_tools_node(state)
        
        assert result["bot_memory"]["game_time"] == "2026-04-10T09:00:00+00:00"

    def test_commits_last_staging_entry_to_bot_memory(self):
        state = make_state(bot_memory_staging=[
            {"npc": {"hp": 15}},
            {"npc": {"hp": 10}},
        ])
        result = post_tools_node(state)
        assert result["bot_memory"]["npc"]["hp"] == 10

    def test_clears_staging_after_commit(self):
        state = make_state(bot_memory_staging=[{"npc": {"hp": 5}}])
        result = post_tools_node(state)
        assert result["bot_memory_staging"] is None

    def test_no_staging_leaves_bot_memory_unchanged(self):
        state = make_state(bot_memory_staging=[])
        result = post_tools_node(state)
        assert "bot_memory" not in result
        assert result["bot_memory_staging"] is None

class TestRouterLogic:
    def test_route_director_to_pretools_if_calls(self):
        from langchain_core.messages import AIMessage
        state = make_state(agent_messages=[AIMessage(content="", tool_calls=[{"name": "t1", "args": {}, "id": "1"}])])
        assert route_director(state) == "PreTools"

    def test_route_director_to_narrator_if_no_calls(self):
        from langchain_core.messages import AIMessage
        state = make_state(agent_messages=[AIMessage(content="hello")])
        assert route_director(state) == "Narrator"

    def test_route_rules_always_to_director(self):
        assert route_rules({}) == "Director"
