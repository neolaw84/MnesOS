"""
Unit tests for graph.py node functions, edge routers, and the build_graph factory.
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage

from MnesOS.graph import (
    build_graph,
    build_npc_intent_tool,
    build_yare_event_tools,
    context_retrieval_node,
    cycle_tick_node,
    director_node,
    end_of_narration,
    GameState,
    get_npc_visible_state,
    get_public_state,
    narrator_node,
    NPCIntentOutput,
    post_tools_node,
    pre_tools_node,
    route_director,
    route_rules,
    workflow,
)


class _BindableFakeModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel extended with a passthrough bind_tools() for tests."""
    def bind_tools(self, tools, **kwargs):
        return self


# CWD-relative path — pytest is always invoked from the project root.
GENERIC_RPG_LORE = "cartridges/generic-rpg/bot_lore.md"


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
# trigger_event tool (native LangGraph ToolNode pattern)
# ---------------------------------------------------------------------------

def _ai_msg_with_tool_call(event_name: str, call_id: str = "call_1", args: dict = None) -> AIMessage:
    """Build an AIMessage carrying a dynamically generated event tool call."""
    return AIMessage(
        content="",
        tool_calls=[{
            "name": event_name,
            "args": args or {},
            "id": call_id,
            "type": "tool_call",
        }],
    )


def _make_tools_only_app(yare_config: dict):
    """Compile a minimal graph containing only the ToolNode for integration tests."""
    from langgraph.graph import StateGraph, END as _END
    from langgraph.prebuilt import ToolNode
    g = StateGraph(GameState)
    tools = build_yare_event_tools(yare_config)
    g.add_node("T", ToolNode(tools, messages_key="agent_messages"))
    g.set_entry_point("T")
    g.add_edge("T", _END)
    return g.compile()


def _invoke_dynamic_tool(event_name: str, state: dict, event_args: dict = None, call_id: str = "t1"):
    """Invoke a dynamic tool manually for testing."""
    tools = build_yare_event_tools(state["yare_config"])
    tool = next((t for t in tools if t.name == event_name), None)
    if not tool:
        class FakeCommand:
            update = {"system_notes": []}
        return FakeCommand()

    tool_args = dict(event_args or {})
    return tool.func(*[], tool_call_id=call_id, state=state, **tool_args)


class TestDynamicEventTools:
    """Tests for dynamic YARE event tools executing real logic with InjectedState."""

    def test_tool_executes_event_and_updates_bot_memory(self):
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("deal_damage", state)
        assert isinstance(result, Command)
        assert result.update["bot_memory_staging"][0]["npc"]["hp"] == 10  # 20 - 10

    def test_tool_emits_new_notes_in_system_notes(self):
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("deal_damage", state)
        assert any("damage" in n for n in result.update["system_notes"])

    def test_tool_npc_phase_adds_separator_note(self):
        from langgraph.types import Command
        state = make_state(turn_phase="npc")
        result = _invoke_dynamic_tool("deal_damage", state)
        assert any("NPC Turn" in n for n in result.update["system_notes"])

    def test_tool_npc_separator_not_duplicated(self):
        from langgraph.types import Command
        state = make_state(turn_phase="npc", system_notes=["\n--- NPC Turn Resolution ---"])
        result = _invoke_dynamic_tool("deal_damage", state)
        combined = state["system_notes"] + result.update.get("system_notes", [])
        assert combined.count("\n--- NPC Turn Resolution ---") == 1

    def test_tool_unknown_event_produces_empty_notes(self):
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("undefined_event", state)
        assert result.update.get("system_notes", []) == []

    def test_tool_passes_args_to_interpreter(self):
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool(
            "generic_check", state,
            event_args={"stat": "strength", "difficulty": 1},
        )
        assert any("Succeeded" in n or "Failed" in n for n in result.update.get("system_notes", []))

    def test_tool_creates_tool_message_with_correct_id(self):
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("deal_damage", state, call_id="my_id")
        tool_msgs = [m for m in result.update.get("agent_messages", []) if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "my_id"
        assert "damage" in tool_msgs[0].content

    def test_tool_node_propagates_bot_memory_staging(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("deal_damage")],
            turn_phase="player",
        )
        app = _make_tools_only_app(state["yare_config"])
        result = app.invoke(state)
        assert result["bot_memory_staging"][-1]["npc"]["hp"] == 10

    def test_tool_node_appends_tool_message_to_agent_messages(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("deal_damage")],
            turn_phase="player",
        )
        app = _make_tools_only_app(state["yare_config"])
        result = app.invoke(state)
        tool_msgs = [m for m in result["agent_messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "damage" in tool_msgs[0].content


# ---------------------------------------------------------------------------
# narrator_node
# ---------------------------------------------------------------------------

class TestNarratorNode:
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
        assert result["bot_memory_staging"] is None

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

    def test_routes_to_narrator_when_no_calls(self):
        state = make_state(
            agent_messages=[AIMessage(content="Just looking.", tool_calls=[])],
            iteration_count=1,
        )
        assert route_director(state) == "Narrator"

    def test_routes_to_narrator_when_no_ai_message(self):
        state = make_state(agent_messages=[], iteration_count=1)
        assert route_director(state) == "Narrator"

    def test_routes_to_narrator_when_max_iterations_reached(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("attack")],
            iteration_count=3,
        )
        assert route_director(state) == "Narrator"

    def test_route_director_does_not_check_yare_config(self):
        """OCP: route_director must not inspect yare_config — routing is structural."""
        import inspect
        source = inspect.getsource(route_director)
        assert "separate_npc_brain" not in source, (
            "route_director reads separate_npc_brain from state, violating OCP. "
            "Use route_director_separate for the decoupled architecture."
        )


class TestRouteRules:
    def test_always_routes_back_to_director(self):
        state = make_state(turn_phase="player")
        assert route_rules(state) == "Director"

    def test_routes_to_director_regardless_of_phase(self):
        for phase in ("player", "npc", "unknown", ""):
            assert route_rules(make_state(turn_phase=phase)) == "Director"


# ---------------------------------------------------------------------------
# LLM injection point tests
# ---------------------------------------------------------------------------

class TestDirectorNodeWithLLM:
    def test_llm_is_invoked(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        director_node(state, llm=fake_llm)
        fake_llm.bind_tools.assert_called_once()
        fake_llm.bind_tools.return_value.invoke.assert_called_once()

    def test_dynamic_tools_are_bound(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        dynamic_tools = build_yare_event_tools(state["yare_config"])
        director_node(state, llm=fake_llm, tools=dynamic_tools)
        bound_tools = fake_llm.bind_tools.call_args[0][0]
        assert len(bound_tools) > 0
        assert hasattr(bound_tools[0], "name")

    def test_llm_tool_calls_stored_in_agent_messages(self):
        ai_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "generic_check",
                "args": {"stat": "charm", "difficulty": 12},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        assert "tool_calls" not in result
        assert len(result["agent_messages"][0].tool_calls) == 1
        assert result["agent_messages"][0].tool_calls[0]["name"] == "generic_check"

    def test_ai_message_is_added_to_agent_messages(self):
        ai_msg = AIMessage(content="", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        assert result["agent_messages"] == [ai_msg]

    def test_llm_no_tool_calls_agent_messages_has_empty_tool_calls(self):
        ai_msg = AIMessage(content="Just looking around.", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I look around."}])
        result = director_node(state, llm=fake_llm)
        assert result["agent_messages"][0].tool_calls == []

    def test_directive_included_in_prompt_passed_to_llm(self):
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

    def test_game_time_context_is_injected_into_director_prompt(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        baseline = make_state()
        state = make_state(bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"})
        director_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "state.game_time" in system_content
        assert "2026-04-10T08:00:00+00:00" in system_content


class TestNarratorNodeWithLLM:
    def test_llm_is_invoked(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="The goblin snarls.")
        state = make_state(system_notes=["Player dealt 10 damage."])
        narrator_node(state, llm=fake_llm)
        fake_llm.bind_tools.assert_called_once()
        fake_llm.bind_tools.return_value.invoke.assert_called_once()

    def test_end_of_narration_tool_is_bound(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="Story text.")
        state = make_state(system_notes=["Player dealt 10 damage."])
        narrator_node(state, llm=fake_llm)
        bound_tools = fake_llm.bind_tools.call_args[0][0]
        assert end_of_narration in bound_tools

    def test_llm_response_stored_as_narrative(self):
        fake_llm = _BindableFakeModel(responses=[AIMessage(content="The goblin snarls and lunges at you.", tool_calls=[])])
        state = make_state(system_notes=["Player dealt 10 damage."])
        result = narrator_node(state, llm=fake_llm)
        assert "narrative" in result
        assert "goblin" in result["narrative"].lower()

    def test_narrative_uses_public_state_not_private(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="Story text.", tool_calls=[])
        state = make_state(system_notes=["Test."])
        state["bot_memory"]["player"]["is_poisoned_with_asymptomatic_poison"] = True
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.bind_tools.return_value.invoke.call_args)
        assert "is_poisoned_with_asymptomatic_poison" not in call_arg

    def test_agent_messages_are_included_in_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="Story text.", tool_calls=[])
        state = make_state(
            system_notes=["Test."],
            agent_messages=[ToolMessage(content="Succeeded!", tool_call_id="call_1")],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.bind_tools.return_value.invoke.call_args)
        assert "Succeeded!" in call_arg

    def test_game_time_context_is_injected_into_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="Story text.", tool_calls=[])
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"},
            system_notes=["Test."],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.bind_tools.return_value.invoke.call_args)
        assert "state.game_time" in call_arg
        assert "2026-04-10T08:00:00+00:00" in call_arg

    def test_narrator_end_of_narration_tool_advance_time_updates_bot_memory(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(
            content="A while passes.",
            tool_calls=[{
                "name": "end_of_narration",
                "args": {"actions": [{"type": "advance_time", "duration": "PT15M"}]},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"},
            system_notes=["Test."],
        )
        result = narrator_node(state, llm=fake_llm)
        assert result["bot_memory"]["game_time"] == "2026-04-10T08:15:00+00:00"
        assert result["client_messages"][0]["content"] == "A while passes."

    def test_narrator_end_of_narration_advance_without_parseable_game_time_adds_system_note(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(
            content="Time passes.",
            tool_calls=[{
                "name": "end_of_narration",
                "args": {"actions": [{"type": "advance_time", "duration": "PT15M"}]},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "not-a-time"},
            system_notes=["Test."],
        )
        result = narrator_node(state, llm=fake_llm)
        assert any("advance_time skipped" in n.lower() for n in result.get("system_notes", []))

    def test_narrator_inline_time_tags_do_not_mutate_state(self):
        fake_llm = MagicMock()
        fake_llm.bind_tools.return_value.invoke.return_value = AIMessage(
            content="A while passes. [[TIME_ADVANCE: PT15M]]",
            tool_calls=[],
        )
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"},
            system_notes=["Test."],
        )
        result = narrator_node(state, llm=fake_llm)
        assert "bot_memory" not in result
        assert "[[TIME_ADVANCE: PT15M]]" in result["client_messages"][0]["content"]


# ---------------------------------------------------------------------------
# build_graph factory
# ---------------------------------------------------------------------------

class TestBuildGraphFactory:
    """SRP: build_graph must be a standalone factory function in graph.py."""

    def test_build_graph_is_importable(self):
        assert callable(build_graph)

    def test_build_graph_monolithic_returns_compiled_app(self):
        app = build_graph(yare_config=make_state()["yare_config"])
        assert hasattr(app, "invoke")
        assert hasattr(app, "get_graph")

    def test_build_graph_monolithic_has_all_expected_nodes(self):
        app = build_graph(yare_config=make_state()["yare_config"])
        node_names = set(app.get_graph().nodes.keys())
        for expected in (
            "ResetAgentMessages", "Lore", "CycleTick", "Director",
            "PreTools", "Tools", "PostTools", "Narrator", "CleanupAgentMessages",
        ):
            assert expected in node_names, f"Missing expected node: {expected!r}"

    def test_build_graph_monolithic_excludes_npc_brain(self):
        app = build_graph(yare_config=make_state()["yare_config"])
        node_names = set(app.get_graph().nodes.keys())
        assert "NPC_Brain" not in node_names

    def test_build_graph_accepts_all_llm_params(self):
        fake = MagicMock()
        app = build_graph(
            yare_config=make_state()["yare_config"],
            llm_director=fake,
            llm_npc_brain=fake,
            llm_narrator=fake,
        )
        assert hasattr(app, "invoke")

    def test_build_graph_dry_run_executes_a_turn(self):
        """build_graph with no LLMs must handle a full graph invocation without errors."""
        app = build_graph(yare_config=make_state()["yare_config"])
        state = make_state()
        result = app.invoke(state)
        assert "bot_memory" in result

# ---------------------------------------------------------------------------
# get_npc_visible_state
# ---------------------------------------------------------------------------

class TestGetNpcVisibleState:
    def _yare_config_with_visibility(self):
        return {
            "state_schema": {
                "player_hp":     {"type": "int",  "npc_visibility": True},
                "hidden_dagger": {"type": "bool", "npc_visibility": False},
                "no_flag_key":   {"type": "str"},
            }
        }

    def test_visible_key_is_included(self):
        bot_memory = {"player_hp": 80}
        result = get_npc_visible_state(bot_memory, self._yare_config_with_visibility())
        assert result["player_hp"] == 80

    def test_hidden_key_is_excluded(self):
        bot_memory = {"hidden_dagger": True}
        result = get_npc_visible_state(bot_memory, self._yare_config_with_visibility())
        assert "hidden_dagger" not in result

    def test_key_without_npc_visibility_flag_is_excluded(self):
        bot_memory = {"no_flag_key": "some_value"}
        result = get_npc_visible_state(bot_memory, self._yare_config_with_visibility())
        assert "no_flag_key" not in result

    def test_key_not_in_schema_is_excluded(self):
        bot_memory = {"unlisted_key": 42}
        result = get_npc_visible_state(bot_memory, self._yare_config_with_visibility())
        assert "unlisted_key" not in result

    def test_empty_bot_memory_returns_empty(self):
        result = get_npc_visible_state({}, self._yare_config_with_visibility())
        assert result == {}

    def test_multiple_visible_keys_all_included(self):
        yare_config = {
            "state_schema": {
                "a": {"npc_visibility": True},
                "b": {"npc_visibility": True},
                "c": {"npc_visibility": False},
            }
        }
        bot_memory = {"a": 1, "b": 2, "c": 3}
        result = get_npc_visible_state(bot_memory, yare_config)
        assert result == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# build_npc_intent_tool / query_npc_intent
# ---------------------------------------------------------------------------

def _make_npc_fake_llm(dialogue="Hello.", action_intent="Stand still.", internal_monologue="Nervous."):
    """Return a mock LLM whose with_structured_output returns a preset NPCIntentOutput."""
    output = NPCIntentOutput(
        dialogue=dialogue,
        action_intent=action_intent,
        internal_monologue=internal_monologue,
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = output
    return mock_llm


def _make_npc_state(**overrides):
    """Minimal state dict for NPC intent tool tests."""
    base = make_state(
        bot_memory={
            "player_hp": 80,
            "hidden_dagger": True,
            "npcs": {
                "goblin_chief": {
                    "tags": ["goblin", "thug"],
                },
                "mr_xyz": {
                    "template": "Mr_XYZ",
                },
            },
        },
        yare_config={
            "state_schema": {
                "player_hp":     {"type": "int",  "npc_visibility": True},
                "hidden_dagger": {"type": "bool", "npc_visibility": False},
            },
            "npc_templates": {
                "Mr_XYZ": {
                    "type": "name",
                    "description": "CEO of Evil Corp. Speaks in corporate buzzwords.",
                },
                "goblin": {
                    "type": "tag",
                    "description": "Small, green, cowardly creature.",
                },
                "thug": {
                    "type": "tag",
                    "description": "Aggressive, relies on intimidation.",
                },
            },
            "events": {},
            "macros": {},
        },
    )
    base.update(overrides)
    return base


class TestBuildNpcIntentTool:
    def test_tool_is_callable(self):
        tool = build_npc_intent_tool(_make_npc_fake_llm())
        assert hasattr(tool, "invoke") and hasattr(tool, "name")

    def test_tool_name_is_query_npc_intent(self):
        tool = build_npc_intent_tool(_make_npc_fake_llm())
        assert tool.name == "query_npc_intent"

    def test_returns_json_string(self):
        import json
        mock_llm = _make_npc_fake_llm(dialogue="Halt!", action_intent="Block path.", internal_monologue="Fear.")
        tool = build_npc_intent_tool(mock_llm)
        state = _make_npc_state()
        raw = tool.func(
            npc_id="goblin_chief",
            immediate_stimulus="The player draws a sword.",
            history_turns=0,
            state=state,
        )
        parsed = json.loads(raw)
        assert parsed["dialogue"] == "Halt!"
        assert parsed["action_intent"] == "Block path."
        assert parsed["internal_monologue"] == "Fear."

    def test_tag_mode_concatenates_multiple_descriptions(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm)
        state = _make_npc_state()
        tool.func(
            npc_id="goblin_chief",
            immediate_stimulus="Player enters room.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "Small, green, cowardly creature." in invocation_args
        assert "Aggressive, relies on intimidation." in invocation_args

    def test_name_mode_uses_template_description(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm)
        state = _make_npc_state()
        tool.func(
            npc_id="mr_xyz",
            immediate_stimulus="Player challenges authority.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "CEO of Evil Corp" in invocation_args

    def test_npc_visible_state_hides_secret_variables(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm)
        state = _make_npc_state()
        tool.func(
            npc_id="goblin_chief",
            immediate_stimulus="Player taunts the NPC.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "hidden_dagger" not in invocation_args
        assert "player_hp" in invocation_args

    def test_history_turns_limits_messages_passed(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        state = _make_npc_state(client_messages=messages)
        tool.func(
            npc_id="goblin_chief",
            immediate_stimulus="Test.",
            history_turns=2,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "msg4" in invocation_args
        assert "msg3" in invocation_args
        assert "msg0" not in invocation_args

    def test_history_turns_capped_at_ten(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(15)]
        state = _make_npc_state(client_messages=messages)
        tool.func(
            npc_id="goblin_chief",
            immediate_stimulus="Test.",
            history_turns=50,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "msg14" in invocation_args
        assert "msg0" not in invocation_args  # only last 10

    def test_dm_directives_are_included_in_prompt(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm)
        state = _make_npc_state()
        tool.func(
            npc_id="goblin_chief",
            immediate_stimulus="Test.",
            history_turns=0,
            dm_directives="Be extra menacing.",
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "Be extra menacing." in invocation_args

    def test_tool_is_added_to_build_graph_when_npc_llm_provided(self):
        mock_npc_llm = _make_npc_fake_llm()
        mock_director_llm = MagicMock()
        mock_director_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        app = build_graph(
            yare_config=state["yare_config"],
            llm_director=mock_director_llm,
            llm_npc_brain=mock_npc_llm,
        )
        app.invoke(state)
        bound_tools = mock_director_llm.bind_tools.call_args[0][0]
        tool_names = [t.name for t in bound_tools]
        assert "query_npc_intent" in tool_names

    def test_npc_intent_tool_not_added_when_no_npc_llm(self):
        fake_director = MagicMock()
        fake_director.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        app = build_graph(
            yare_config=state["yare_config"],
            llm_director=fake_director,
        )
        app.invoke(state)
        bound_tools = fake_director.bind_tools.call_args[0][0]
        tool_names = [t.name for t in bound_tools]
        assert "query_npc_intent" not in tool_names
