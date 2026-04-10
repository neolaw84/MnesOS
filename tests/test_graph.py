"""
Unit tests for graph.py node functions and edge routers.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, ToolMessage


class _BindableFakeModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel extended with a passthrough bind_tools() for tests."""
    def bind_tools(self, tools, **kwargs):
        return self

from MnesOS.graph import (
    context_retrieval_node,
    cycle_tick_node,
    director_node,
    npc_brain_node,
    narrator_node,
    get_public_state,
    route_director,
    route_rules,
    route_npc_brain,
    pre_tools_node,
    post_tools_node,
    workflow,
    GameState,
    trigger_event,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

GENERIC_RPG_LORE = (
    os.path.join(os.path.dirname(__file__), "..", "cartridges", "generic-rpg", "bot_lore.md")
)


def make_state(**overrides) -> dict:
    """Builds a minimal GameState-shaped dict for node tests."""
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
                    "is_poisoned_with_asymptomatic_poison": {
                        "type": "bool", "default": False, "visibility": "private"
                    },
                },
                "npc": {
                    "hp":       {"type": "int", "default": 20, "visibility": "public"},
                    "strength": {"type": "int", "default": 5,  "visibility": "public"},
                },
            },
            "events": {
                "deal_damage": {
                    "steps": [
                        {"action": "mutate", "var": "state.npc.hp", "op": "sub", "value": 10},
                        {"action": "note",   "message": "Player deals 10 damage."},
                    ]
                },
                "generic_check": {
                    "inputs": {
                        "stat":       {"type": "string", "description": "Which stat is being tested"},
                        "difficulty": {"type": "int",    "description": "Target number to meet or beat"},
                    },
                    "steps": [
                        {"action": "set",  "var": "temp.roll", "value": "@ roll(1d20) + state.player.level"},
                        {
                            "action": "branch",
                            "conditions": [
                                {
                                    "if": "@ temp.roll >= inputs.difficulty",
                                    "steps": [{"action": "note", "message": "Succeeded!"}],
                                },
                                {
                                    "else": True,
                                    "steps": [{"action": "note", "message": "Failed!"}],
                                },
                            ],
                        },
                    ],
                },
            },
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


# ---------------------------------------------------------------------------
# get_public_state
# ---------------------------------------------------------------------------

class TestGetPublicState:
    def test_public_vars_included(self):
        state = make_state()
        pub = get_public_state(state["bot_memory"], state["yare_config"])
        assert pub["player"]["hp"] == 100
        assert pub["player"]["gold"] == 0

    def test_private_vars_excluded(self):
        state = make_state()
        state["bot_memory"]["player"]["is_poisoned_with_asymptomatic_poison"] = True
        pub = get_public_state(state["bot_memory"], state["yare_config"])
        assert "is_poisoned_with_asymptomatic_poison" not in pub["player"]

    def test_empty_bot_memory_returns_empty(self):
        pub = get_public_state({}, {"state_schema": {}})
        assert pub == {}

    def test_schema_defaults_visibility_to_private(self):
        """A field with no 'visibility' key must be treated as private."""
        bot_memory = {"player": {"secret": 42}}
        yare_config = {
            "state_schema": {
                "player": {"secret": {"type": "int", "default": 0}}  # no visibility key
            }
        }
        pub = get_public_state(bot_memory, yare_config)
        assert "secret" not in pub.get("player", {})


# ---------------------------------------------------------------------------
# context_retrieval_node
# ---------------------------------------------------------------------------

class TestContextRetrievalNode:
    def test_returns_retrieved_lore_key(self):
        state = make_state()
        result = context_retrieval_node(state)
        assert "retrieved_lore" in result

    def test_retrieved_lore_is_string(self):
        state = make_state()
        result = context_retrieval_node(state)
        assert isinstance(result["retrieved_lore"], str)

    def test_location_enriches_query(self):
        """Including a known location term should return non-empty lore."""
        state = make_state()
        state["bot_memory"]["current_location"] = "Crossroads"
        state["client_messages"] = [{"role": "user", "content": "I look at the crossroads."}]
        result = context_retrieval_node(state)
        assert result["retrieved_lore"] != ""

    def test_npc_name_enriches_query(self):
        state = make_state()
        state["bot_memory"]["npc"] = {"name": "Goblin", "archetype": ""}
        state["client_messages"] = [{"role": "user", "content": "I fight the goblin."}]
        result = context_retrieval_node(state)
        assert isinstance(result["retrieved_lore"], str)

    def test_completely_unrelated_query_returns_empty_or_string(self):
        state = make_state()
        state["client_messages"] = [{"role": "user", "content": "xyzzy frobozz quux zork"}]
        result = context_retrieval_node(state)
        # Must not raise; may be empty string
        assert isinstance(result["retrieved_lore"], str)


# ---------------------------------------------------------------------------
# cycle_tick_node
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# director_node
# ---------------------------------------------------------------------------

class TestDirectorNode:
    def test_sets_turn_phase_player(self):
        state = make_state(client_messages=[{"role": "user", "content": "I look around."}])
        result = director_node(state)
        assert result["turn_phase"] == "player"

    def test_increments_iteration_count(self):
        state = make_state(iteration_count=0)
        result = director_node(state)
        assert result["iteration_count"] == 1

    def test_ambient_action_produces_no_tool_calls(self):
        state = make_state(client_messages=[{"role": "user", "content": "I wink at the merchant."}])
        result = director_node(state)
        # Without an LLM wired, no agent_messages are produced
        assert result.get("agent_messages", []) == []

    def test_directives_are_appended_when_present(self):
        """Verifies the node doesn't crash with directives when no LLM is wired."""
        state = make_state(
            prompt_directives={"director": "Prefer combat events."},
            client_messages=[{"role": "user", "content": "I look around."}],
        )
        result = director_node(state)
        assert "turn_phase" in result  # node ran without error


# ---------------------------------------------------------------------------
# npc_brain_node
# ---------------------------------------------------------------------------

class TestNpcBrainNode:
    def test_sets_turn_phase_npc(self):
        state = make_state()
        result = npc_brain_node(state)
        assert result["turn_phase"] == "npc"

    def test_resets_iteration_count_to_zero(self):
        state = make_state(iteration_count=2)
        result = npc_brain_node(state)
        assert result["iteration_count"] == 0

    def test_directives_present_does_not_crash(self):
        state = make_state(prompt_directives={"npc_brain": "Act aggressively."})
        result = npc_brain_node(state)
        assert "turn_phase" in result


# ---------------------------------------------------------------------------
# trigger_event tool (native LangGraph ToolNode pattern)
# ---------------------------------------------------------------------------

def _ai_msg_with_tool_call(event_name: str, call_id: str = "call_1") -> AIMessage:
    """Build an AIMessage carrying a trigger_event tool call."""
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "trigger_event",
            "args": {"event_name": event_name},
            "id": call_id,
            "type": "tool_call",
        }],
    )


def _make_tools_only_app():
    """Compile a minimal graph containing only the ToolNode for integration tests."""
    from langgraph.graph import StateGraph, END as _END
    from langgraph.prebuilt import ToolNode
    g = StateGraph(GameState)
    g.add_node("T", ToolNode([trigger_event], messages_key="agent_messages"))
    g.set_entry_point("T")
    g.add_edge("T", _END)
    return g.compile()


def _invoke_trigger_event(event_name: str, state: dict, event_args: dict = None, call_id: str = "t1"):
    """Invoke trigger_event using the required ToolCall dict format."""
    tool_args = {"event_name": event_name, "state": state}
    if event_args is not None:
        tool_args["event_args"] = event_args
    return trigger_event.invoke({
        "args": tool_args,
        "name": "trigger_event",
        "type": "tool_call",
        "id": call_id,
    })


class TestTriggerEventTool:
    """Tests for trigger_event executing real YARE logic with InjectedState."""

    def test_tool_executes_event_and_updates_bot_memory(self):
        """trigger_event must run the event and stage updated bot_memory via Command."""
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_trigger_event("deal_damage", state)
        assert isinstance(result, Command)
        assert result.update["bot_memory_staging"][0]["npc"]["hp"] == 10  # 20 - 10

    def test_tool_emits_new_notes_in_system_notes(self):
        """trigger_event must return new YARE notes (not full list) via Command.update."""
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_trigger_event("deal_damage", state)
        assert any("damage" in n for n in result.update["system_notes"])

    def test_tool_npc_phase_adds_separator_note(self):
        """trigger_event must prepend the NPC separator when turn_phase == 'npc'."""
        from langgraph.types import Command
        state = make_state(turn_phase="npc")
        result = _invoke_trigger_event("deal_damage", state)
        assert any("NPC Turn" in n for n in result.update["system_notes"])

    def test_tool_npc_separator_not_duplicated(self):
        """Separator must not be added if already present in state.system_notes."""
        from langgraph.types import Command
        state = make_state(turn_phase="npc", system_notes=["\n--- NPC Turn Resolution ---"])
        result = _invoke_trigger_event("deal_damage", state)
        combined = state["system_notes"] + result.update.get("system_notes", [])
        assert combined.count("\n--- NPC Turn Resolution ---") == 1

    def test_tool_unknown_event_produces_empty_notes(self):
        """An unrecognised event name must produce no notes."""
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_trigger_event("undefined_event", state)
        assert result.update.get("system_notes", []) == []

    def test_tool_passes_args_to_interpreter(self):
        """LLM-supplied args (e.g. difficulty) must reach the YARE interpreter."""
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_trigger_event(
            "generic_check", state,
            event_args={"stat": "strength", "difficulty": 1},  # difficulty=1 guarantees success
        )
        assert any("Succeeded" in n or "Failed" in n for n in result.update.get("system_notes", []))

    def test_tool_creates_tool_message_with_correct_id(self):
        """trigger_event must include a ToolMessage with the correct tool_call_id."""
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_trigger_event("deal_damage", state, call_id="my_id")
        tool_msgs = [m for m in result.update.get("agent_messages", []) if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "my_id"
        assert "damage" in tool_msgs[0].content

    def test_tool_node_propagates_bot_memory_staging(self):
        """ToolNode must push the state snapshot into bot_memory_staging."""
        app = _make_tools_only_app()
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("deal_damage")],
            turn_phase="player",
        )
        result = app.invoke(state)
        assert result["bot_memory_staging"][-1]["npc"]["hp"] == 10

    def test_tool_node_appends_tool_message_to_agent_messages(self):
        """ToolNode must add the ToolMessage from Command.update to agent_messages."""
        app = _make_tools_only_app()
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("deal_damage")],
            turn_phase="player",
        )
        result = app.invoke(state)
        tool_msgs = [m for m in result["agent_messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "damage" in tool_msgs[0].content


# ---------------------------------------------------------------------------
# narrator_node
# ---------------------------------------------------------------------------

class TestNarratorNode:
    # NOTE: When real LLM calls are wired into narrator_node, these tests
    # will need to be supplemented with mock LLM assertions.

    def test_clears_system_notes(self):
        state = make_state(system_notes=["Player dealt 10 damage.", "NPC is hurt."])
        result = narrator_node(state)
        assert result["system_notes"] == []

    def test_clears_retrieved_lore(self):
        state = make_state(retrieved_lore="Some lore text.")
        result = narrator_node(state)
        assert result["retrieved_lore"] == ""

    def test_resets_iteration_count(self):
        state = make_state(iteration_count=3)
        result = narrator_node(state)
        assert result["iteration_count"] == 0

    def test_directives_present_does_not_crash(self):
        state = make_state(
            prompt_directives={"narrator": "Be poetic."},
            system_notes=["Hit!"],
        )
        result = narrator_node(state)
        assert result["system_notes"] == []


# ---------------------------------------------------------------------------
# pre_tools_node / post_tools_node
# ---------------------------------------------------------------------------

class TestPreToolsNode:
    def test_clears_staging_by_returning_none(self):
        state = make_state(bot_memory_staging=[{"npc": {"hp": 5}}])
        result = pre_tools_node(state)
        assert result["bot_memory_staging"] is None  # sentinel that triggers reducer clear

    def test_does_not_touch_bot_memory(self):
        state = make_state()
        result = pre_tools_node(state)
        assert "bot_memory" not in result


class TestPostToolsNode:
    def test_commits_last_staging_entry_to_bot_memory(self):
        state = make_state(bot_memory_staging=[
            {"npc": {"hp": 15}},
            {"npc": {"hp": 10}},
        ])
        result = post_tools_node(state)
        assert result["bot_memory"]["npc"]["hp"] == 10  # last entry wins

    def test_clears_staging_after_commit(self):
        state = make_state(bot_memory_staging=[{"npc": {"hp": 5}}])
        result = post_tools_node(state)
        assert result["bot_memory_staging"] is None

    def test_no_staging_leaves_bot_memory_unchanged(self):
        state = make_state(bot_memory_staging=[])
        result = post_tools_node(state)
        assert "bot_memory" not in result
        assert result["bot_memory_staging"] is None


# ---------------------------------------------------------------------------
# Edge routers
# ---------------------------------------------------------------------------

class TestRouteDirector:
    def test_routes_to_tools_when_calls_present_and_below_max(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("attack")],
            iteration_count=1,
        )
        assert route_director(state) == "PreTools"

    def test_routes_to_npc_brain_when_no_calls(self):
        state = make_state(
            agent_messages=[AIMessage(content="Just looking.", tool_calls=[])],
            iteration_count=1,
        )
        assert route_director(state) == "NPC_Brain"

    def test_routes_to_npc_brain_when_no_ai_message(self):
        state = make_state(agent_messages=[], iteration_count=1)
        assert route_director(state) == "NPC_Brain"

    def test_routes_to_npc_brain_when_max_iterations_reached(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("attack")],
            iteration_count=3,  # MAX_ITERATIONS == 3
        )
        assert route_director(state) == "NPC_Brain"


class TestRouteRules:
    def test_player_phase_routes_back_to_director(self):
        state = make_state(turn_phase="player")
        assert route_rules(state) == "Director"

    def test_npc_phase_routes_back_to_npc_brain(self):
        state = make_state(turn_phase="npc")
        assert route_rules(state) == "NPC_Brain"

    def test_unknown_phase_routes_to_npc_brain(self):
        state = make_state(turn_phase="unknown")
        assert route_rules(state) == "NPC_Brain"


class TestRouteNpcBrain:
    def test_routes_to_tools_when_calls_present_and_below_max(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("attack")],
            iteration_count=1,
        )
        assert route_npc_brain(state) == "PreTools"

    def test_routes_to_narrator_when_no_calls(self):
        state = make_state(
            agent_messages=[AIMessage(content="Standing down.", tool_calls=[])],
            iteration_count=0,
        )
        assert route_npc_brain(state) == "Narrator"

    def test_routes_to_narrator_when_no_ai_message(self):
        state = make_state(agent_messages=[], iteration_count=0)
        assert route_npc_brain(state) == "Narrator"

    def test_routes_to_narrator_when_max_iterations_reached(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("attack")],
            iteration_count=3,
        )
        assert route_npc_brain(state) == "Narrator"


# ---------------------------------------------------------------------------
# LLM injection point tests
# ---------------------------------------------------------------------------


class TestDirectorNodeWithLLM:
    def test_llm_is_invoked(self):
        """Director must call bind_tools then invoke when an LLM is provided."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        director_node(state, llm=fake_llm)
        fake_llm.bind_tools.assert_called_once()
        fake_llm.bind_tools.return_value.invoke.assert_called_once()

    def test_trigger_event_tool_is_bound(self):
        """Director must bind the trigger_event tool to the LLM."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        director_node(state, llm=fake_llm)
        bound_tools = fake_llm.bind_tools.call_args[0][0]
        assert trigger_event in bound_tools

    def test_llm_tool_calls_stored_in_agent_messages(self):
        """tool_calls from the LLM response must live in agent_messages, not a separate field."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "trigger_event",
                "args": {"event_name": "generic_check", "event_args": {"stat": "charm", "difficulty": 12}},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        assert "tool_calls" not in result
        assert len(result["agent_messages"][0].tool_calls) == 1
        assert result["agent_messages"][0].tool_calls[0]["args"]["event_name"] == "generic_check"

    def test_ai_message_is_added_to_agent_messages(self):
        ai_msg = AIMessage(content="", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        assert result["agent_messages"] == [ai_msg]

    def test_llm_no_tool_calls_agent_messages_has_empty_tool_calls(self):
        """When the LLM returns no tool calls the AIMessage has an empty tool_calls list."""
        ai_msg = AIMessage(content="Just looking around.", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I look around."}])
        result = director_node(state, llm=fake_llm)
        assert result["agent_messages"][0].tool_calls == []

    def test_directive_included_in_prompt_passed_to_llm(self):
        """The LLM invocation must include the cartridge directive in its input."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(
            prompt_directives={"director": "Prefer skill checks over combat."},
            client_messages=[{"role": "user", "content": "I parley with the guard."}],
        )
        director_node(state, llm=fake_llm)
        call_arg = fake_llm.bind_tools.return_value.invoke.call_args
        assert call_arg is not None
        prompt_text = str(call_arg)
        assert "Prefer skill checks over combat." in prompt_text

    def test_event_signatures_with_inputs_in_director_prompt(self):
        """Events with inputs must show their event_args schema in the director prompt."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I attack."}])
        director_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "generic_check(event_args: {" in system_content
        assert "stat: string" in system_content
        assert "difficulty: int" in system_content

    def test_event_without_inputs_shown_as_bare_name_in_director_prompt(self):
        """Events with no inputs list must appear without an event_args suffix."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I attack."}])
        director_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "deal_damage" in system_content
        assert "deal_damage(event_args" not in system_content

    def test_game_time_context_is_injected_into_director_prompt(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        baseline = make_state()
        state = make_state(bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"})
        director_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "state.game_time" in system_content
        assert "2026-04-10T08:00:00+00:00" in system_content


class TestNpcBrainNodeWithLLM:
    def test_llm_is_invoked(self):
        """NPC Brain must call bind_tools then invoke when an LLM is provided."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        npc_brain_node(state, llm=fake_llm)
        fake_llm.bind_tools.assert_called_once()
        fake_llm.bind_tools.return_value.invoke.assert_called_once()

    def test_trigger_event_tool_is_bound(self):
        """NPC Brain must bind the trigger_event tool to the LLM."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        npc_brain_node(state, llm=fake_llm)
        bound_tools = fake_llm.bind_tools.call_args[0][0]
        assert trigger_event in bound_tools

    def test_llm_tool_calls_stored_in_agent_messages(self):
        """LLM tool calls must live in agent_messages, not a separate field."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "trigger_event",
                "args": {"event_name": "counter_attack"},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state()
        state["bot_memory"]["npc"]["archetype"] = "Wolf"
        result = npc_brain_node(state, llm=fake_llm)
        assert "tool_calls" not in result
        assert len(result["agent_messages"][0].tool_calls) == 1
        assert result["agent_messages"][0].tool_calls[0]["args"]["event_name"] == "counter_attack"

    def test_agent_messages_are_included_in_npc_prompt(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(agent_messages=[ToolMessage(content="Succeeded!", tool_call_id="call_1")])
        npc_brain_node(state, llm=fake_llm)
        call_arg = str(fake_llm.bind_tools.return_value.invoke.call_args)
        assert "Succeeded!" in call_arg

    def test_llm_no_tool_calls_agent_messages_has_empty_tool_calls(self):
        """When NPC Brain LLM returns no tool calls, AIMessage has empty tool_calls."""
        ai_msg = AIMessage(content="The NPC holds back.", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state()
        result = npc_brain_node(state, llm=fake_llm)
        assert result["agent_messages"][0].tool_calls == []

    def test_event_signatures_with_inputs_in_npc_brain_prompt(self):
        """Events with inputs must show their event_args schema in the NPC Brain prompt."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        npc_brain_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "generic_check(event_args: {" in system_content
        assert "stat: string" in system_content
        assert "difficulty: int" in system_content

    def test_event_without_inputs_shown_as_bare_name_in_npc_brain_prompt(self):
        """Events with no inputs list must appear without an event_args suffix in NPC Brain."""
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        npc_brain_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "deal_damage" in system_content
        assert "deal_damage(event_args" not in system_content

    def test_game_time_context_is_injected_into_npc_prompt(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        baseline = make_state()
        state = make_state(bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"})
        npc_brain_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "state.game_time" in system_content
        assert "2026-04-10T08:00:00+00:00" in system_content


class TestNarratorNodeWithLLM:
    def test_llm_is_invoked(self):
        """Narrator must call the LLM when one is provided."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="The goblin snarls.")
        state = make_state(system_notes=["Player dealt 10 damage."])
        narrator_node(state, llm=fake_llm)
        fake_llm.invoke.assert_called_once()

    def test_llm_response_stored_as_narrative(self):
        """The LLM prose response must be stored under 'narrative' in the output state."""
        fake_llm = FakeListChatModel(responses=["The goblin snarls and lunges at you."])
        state = make_state(system_notes=["Player dealt 10 damage."])
        result = narrator_node(state, llm=fake_llm)
        assert "narrative" in result
        assert "goblin" in result["narrative"].lower()

    def test_narrative_uses_public_state_not_private(self):
        """The LLM must only receive public state variables in its context."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.")
        state = make_state(system_notes=["Test."])
        state["bot_memory"]["player"]["is_poisoned_with_asymptomatic_poison"] = True
        narrator_node(state, llm=fake_llm)
        fake_llm.invoke.assert_called_once()
        call_arg = str(fake_llm.invoke.call_args)
        assert "is_poisoned_with_asymptomatic_poison" not in call_arg

    def test_agent_messages_are_included_in_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.")
        state = make_state(
            system_notes=["Test."],
            agent_messages=[ToolMessage(content="Succeeded!", tool_call_id="call_1")],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "Succeeded!" in call_arg

    def test_game_time_context_is_injected_into_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.")
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"},
            system_notes=["Test."],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "state.game_time" in call_arg
        assert "2026-04-10T08:00:00+00:00" in call_arg

    def test_narrator_time_advance_tag_updates_bot_memory(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="A while passes. [[TIME_ADVANCE: PT15M]]")
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"},
            system_notes=["Test."],
        )
        result = narrator_node(state, llm=fake_llm)
        assert result["bot_memory"]["game_time"] == "2026-04-10T08:15:00+00:00"
        assert "[[TIME_ADVANCE" not in result["client_messages"][0]["content"]


class TestWorkflowAgentMessageCleanup:
    def test_entry_node_clears_stale_agent_messages(self):
        app = workflow.compile()
        state = make_state(
            agent_messages=[ToolMessage(content="stale", tool_call_id="old_call")],
            client_messages=[{"role": "user", "content": "I look around."}],
        )
        result = app.invoke(state)
        assert result.get("agent_messages", []) == []

    def test_exit_node_returns_empty_agent_messages(self):
        app = workflow.compile()
        state = make_state(
            client_messages=[{"role": "user", "content": "I look around."}],
            agent_messages=[ToolMessage(content="stale", tool_call_id="old_call")],
        )
        result = app.invoke(state)
        assert result.get("agent_messages", []) == []
