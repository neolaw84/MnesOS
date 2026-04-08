"""
Unit tests for graph.py node functions and edge routers.

NOTE — LLM injection points:
    The current node implementations (director_node, npc_brain_node,
    narrator_node) contain STUB / SIMULATED logic instead of real LLM calls.
    When production LLM calls are wired in, those tests that rely on the
    stub keyword-matching behaviour will FAIL and will need to be rewritten
    with proper LLM mocks (e.g. unittest.mock.patch on the LLM client).
    This is intentional — these tests document the expected behaviour and
    serve as regression guards once the real integration is in place.

NOTE — cartridge data leaks:
    The npc_brain_node currently contains hard-coded archetype checks
    (Jackhammer, Breaker, Hidden Beast) that belong in cartridge config, not
    in engine source. Tests that exercise this behaviour are marked with
    TODO comments. They will need updating once the leaks are fixed.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph import (
    context_retrieval_node,
    director_node,
    npc_brain_node,
    rules_engine_node,
    narrator_node,
    get_public_state,
    route_director,
    route_rules,
    route_npc_brain,
    GameState,
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
        "messages": [{"role": "user", "content": "I look around."}],
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
                    "inputs": ["stat", "difficulty"],
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
        "system_notes": [],
        "retrieved_lore": "",
        "tool_calls": [],
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
        state["messages"] = [{"role": "user", "content": "I look at the crossroads."}]
        result = context_retrieval_node(state)
        assert result["retrieved_lore"] != ""

    def test_npc_name_enriches_query(self):
        state = make_state()
        state["bot_memory"]["npc"] = {"name": "Goblin", "archetype": ""}
        state["messages"] = [{"role": "user", "content": "I fight the goblin."}]
        result = context_retrieval_node(state)
        assert isinstance(result["retrieved_lore"], str)

    def test_completely_unrelated_query_returns_empty_or_string(self):
        state = make_state()
        state["messages"] = [{"role": "user", "content": "xyzzy frobozz quux zork"}]
        result = context_retrieval_node(state)
        # Must not raise; may be empty string
        assert isinstance(result["retrieved_lore"], str)


# ---------------------------------------------------------------------------
# director_node
# ---------------------------------------------------------------------------

class TestDirectorNode:
    # NOTE: These tests exercise the STUB keyword-matching logic.
    # They will need to be rewritten with LLM mocks once real LLM calls
    # replace the stub.

    def test_sets_turn_phase_player(self):
        state = make_state(messages=[{"role": "user", "content": "I look around."}])
        result = director_node(state)
        assert result["turn_phase"] == "player"

    def test_increments_iteration_count(self):
        state = make_state(iteration_count=0)
        result = director_node(state)
        assert result["iteration_count"] == 1

    def test_fight_keyword_triggers_resolve_struggle(self):
        # STUB behaviour: keyword "fight" → resolve_struggle event
        state = make_state(messages=[{"role": "user", "content": "I fight the goblin!"}])
        result = director_node(state)
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["args"]["event_name"] == "resolve_struggle"

    def test_struggle_keyword_triggers_resolve_struggle(self):
        state = make_state(messages=[{"role": "user", "content": "I struggle to break free."}])
        result = director_node(state)
        assert any(
            tc["args"]["event_name"] == "resolve_struggle"
            for tc in result["tool_calls"]
        )

    def test_travel_keyword_triggers_travel(self):
        state = make_state(messages=[{"role": "user", "content": "I travel to the haven."}])
        result = director_node(state)
        assert any(
            tc["args"]["event_name"] == "travel"
            for tc in result["tool_calls"]
        )

    def test_ambient_action_produces_no_tool_calls(self):
        state = make_state(messages=[{"role": "user", "content": "I wink at the merchant."}])
        result = director_node(state)
        assert result["tool_calls"] == []

    def test_directives_are_appended_when_present(self):
        """
        NOTE: When real LLM calls exist, this test should assert the LLM was
        called with a prompt that includes the directive text.
        For now it only verifies the node doesn't crash with directives.
        """
        state = make_state(
            prompt_directives={"director": "Prefer combat events."},
            messages=[{"role": "user", "content": "I look around."}],
        )
        result = director_node(state)
        assert "turn_phase" in result  # node ran without error


# ---------------------------------------------------------------------------
# npc_brain_node
# ---------------------------------------------------------------------------

class TestNpcBrainNode:
    # NOTE: The archetype checks below reflect a known cartridge data leak in
    # the engine source (Jackhammer / Breaker / Hidden Beast are hard-coded).
    # These tests will need updating when that is fixed.

    def test_sets_turn_phase_npc(self):
        state = make_state()
        result = npc_brain_node(state)
        assert result["turn_phase"] == "npc"

    def test_resets_iteration_count_to_zero(self):
        state = make_state(iteration_count=2)
        result = npc_brain_node(state)
        assert result["iteration_count"] == 0

    def test_no_tool_calls_for_normal_archetype(self):
        state = make_state()
        state["bot_memory"]["npc"]["archetype"] = "Goblin"
        result = npc_brain_node(state)
        assert result["tool_calls"] == []

    def test_hardcoded_archetype_triggers_generic_check(self):
        # TODO: This test covers the cartridge data leak. Remove once fixed.
        state = make_state()
        state["bot_memory"]["npc"]["archetype"] = "Jackhammer"
        result = npc_brain_node(state)
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["args"]["event_name"] == "generic_check"

    def test_directives_present_does_not_crash(self):
        state = make_state(prompt_directives={"npc_brain": "Act aggressively."})
        result = npc_brain_node(state)
        assert "turn_phase" in result


# ---------------------------------------------------------------------------
# rules_engine_node
# ---------------------------------------------------------------------------

class TestRulesEngineNode:
    def test_executes_tool_call_and_emits_notes(self):
        state = make_state(
            tool_calls=[
                {"name": "trigger_event", "args": {"event_name": "deal_damage"}}
            ],
            turn_phase="player",
        )
        result = rules_engine_node(state)
        assert any("damage" in n for n in result["system_notes"])

    def test_tool_calls_cleared_after_execution(self):
        state = make_state(
            tool_calls=[
                {"name": "trigger_event", "args": {"event_name": "deal_damage"}}
            ],
        )
        result = rules_engine_node(state)
        assert result["tool_calls"] == []

    def test_bot_memory_mutated_correctly(self):
        state = make_state(
            tool_calls=[
                {"name": "trigger_event", "args": {"event_name": "deal_damage"}}
            ],
        )
        result = rules_engine_node(state)
        assert result["bot_memory"]["npc"]["hp"] == 10  # 20 - 10

    def test_npc_phase_appends_separator_note(self):
        state = make_state(
            turn_phase="npc",
            tool_calls=[
                {"name": "trigger_event", "args": {"event_name": "deal_damage"}}
            ],
        )
        result = rules_engine_node(state)
        assert any("NPC Turn" in n for n in result["system_notes"])

    def test_empty_tool_calls_leaves_state_unchanged(self):
        state = make_state(tool_calls=[])
        result = rules_engine_node(state)
        assert result["system_notes"] == []
        assert result["bot_memory"]["npc"]["hp"] == 20

    def test_unknown_event_name_produces_no_notes(self):
        state = make_state(
            tool_calls=[
                {"name": "trigger_event", "args": {"event_name": "undefined_event"}}
            ],
        )
        result = rules_engine_node(state)
        assert result["system_notes"] == []

    def test_non_trigger_event_calls_are_ignored(self):
        state = make_state(
            tool_calls=[
                {"name": "some_other_call", "args": {"event_name": "deal_damage"}}
            ],
        )
        result = rules_engine_node(state)
        assert result["system_notes"] == []


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
# Edge routers
# ---------------------------------------------------------------------------

class TestRouteDirector:
    def test_routes_to_tools_when_calls_present_and_below_max(self):
        state = make_state(
            tool_calls=[{"name": "trigger_event", "args": {"event_name": "attack"}}],
            iteration_count=1,
        )
        assert route_director(state) == "Tools"

    def test_routes_to_npc_brain_when_no_calls(self):
        state = make_state(tool_calls=[], iteration_count=1)
        assert route_director(state) == "NPC_Brain"

    def test_routes_to_npc_brain_when_max_iterations_reached(self):
        state = make_state(
            tool_calls=[{"name": "trigger_event", "args": {"event_name": "attack"}}],
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
            tool_calls=[{"name": "trigger_event", "args": {"event_name": "attack"}}],
            iteration_count=1,
        )
        assert route_npc_brain(state) == "Tools"

    def test_routes_to_narrator_when_no_calls(self):
        state = make_state(tool_calls=[], iteration_count=0)
        assert route_npc_brain(state) == "Narrator"

    def test_routes_to_narrator_when_max_iterations_reached(self):
        state = make_state(
            tool_calls=[{"name": "trigger_event", "args": {"event_name": "attack"}}],
            iteration_count=3,
        )
        assert route_npc_brain(state) == "Narrator"


# ---------------------------------------------------------------------------
# LLM injection point tests
# These tests describe the DESIRED behaviour once real LLM calls are wired in.
# They are expected to FAIL against the current stub implementation because
# the stub ignores the `llm` parameter entirely.
# ---------------------------------------------------------------------------


class TestDirectorNodeWithLLM:
    def test_llm_is_invoked(self):
        """Director must call the LLM when one is provided."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(messages=[{"role": "user", "content": "I examine the ruins."}])
        director_node(state, llm=fake_llm)
        # FAILS: stub never calls llm
        fake_llm.invoke.assert_called_once()

    def test_llm_tool_calls_populate_output_tool_calls(self):
        """tool_calls from the LLM response must become the output tool_calls."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "trigger_event",
                "args": {"event_name": "generic_check", "args": {"stat": "charm", "difficulty": 12}},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        fake_llm = FakeMessagesListChatModel(responses=[ai_msg])
        # "examine" has no stub keyword — stub returns []
        state = make_state(messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        # FAILS: stub returns [] because "examine" matches no keyword
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["args"]["event_name"] == "generic_check"

    def test_llm_no_tool_calls_overrides_stub_keyword_match(self):
        """If the LLM decides no tools are needed, stub keywords must be ignored."""
        ai_msg = AIMessage(content="Just looking around.", tool_calls=[])
        fake_llm = FakeMessagesListChatModel(responses=[ai_msg])
        # "fight" would trigger stub logic, but the LLM says no tools
        state = make_state(messages=[{"role": "user", "content": "I look and fight nothing."}])
        result = director_node(state, llm=fake_llm)
        # FAILS: stub keyword-matches "fight" and returns a tool_call
        assert result["tool_calls"] == []

    def test_directive_included_in_prompt_passed_to_llm(self):
        """The LLM invocation must include the cartridge directive in its input."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(
            prompt_directives={"director": "Prefer skill checks over combat."},
            messages=[{"role": "user", "content": "I parley with the guard."}],
        )
        director_node(state, llm=fake_llm)
        # FAILS: stub never calls llm
        call_arg = fake_llm.invoke.call_args
        assert call_arg is not None
        prompt_text = str(call_arg)
        assert "Prefer skill checks over combat." in prompt_text


class TestNpcBrainNodeWithLLM:
    def test_llm_is_invoked(self):
        """NPC Brain must call the LLM when one is provided."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        npc_brain_node(state, llm=fake_llm)
        # FAILS: stub never calls llm
        fake_llm.invoke.assert_called_once()

    def test_llm_tool_calls_for_unlisted_archetype(self):
        """LLM-driven tool calls must be used even for archetypes not in the stub list."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "trigger_event",
                "args": {"event_name": "counter_attack"},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        fake_llm = FakeMessagesListChatModel(responses=[ai_msg])
        state = make_state()
        state["bot_memory"]["npc"]["archetype"] = "Wolf"  # not in hard-coded stub list
        result = npc_brain_node(state, llm=fake_llm)
        # FAILS: stub ignores llm; Wolf archetype returns []
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["args"]["event_name"] == "counter_attack"

    def test_llm_no_tool_calls_overrides_stub_hardcoded_archetype(self):
        """If the LLM decides NPCs stand down, the hard-coded archetype check must be bypassed."""
        ai_msg = AIMessage(content="The NPC holds back.", tool_calls=[])
        fake_llm = FakeMessagesListChatModel(responses=[ai_msg])
        state = make_state()
        state["bot_memory"]["npc"]["archetype"] = "Jackhammer"  # in hard-coded stub list
        result = npc_brain_node(state, llm=fake_llm)
        # FAILS: stub keyword-matches Jackhammer and returns a tool_call
        assert result["tool_calls"] == []


class TestNarratorNodeWithLLM:
    def test_llm_is_invoked(self):
        """Narrator must call the LLM when one is provided."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="The goblin snarls.")
        state = make_state(system_notes=["Player dealt 10 damage."])
        narrator_node(state, llm=fake_llm)
        # FAILS: stub never calls llm
        fake_llm.invoke.assert_called_once()

    def test_llm_response_stored_as_narrative(self):
        """The LLM prose response must be stored under 'narrative' in the output state."""
        fake_llm = FakeListChatModel(responses=["The goblin snarls and lunges at you."])
        state = make_state(system_notes=["Player dealt 10 damage."])
        result = narrator_node(state, llm=fake_llm)
        # FAILS: stub returns no 'narrative' key
        assert "narrative" in result
        assert "goblin" in result["narrative"].lower()

    def test_narrative_uses_public_state_not_private(self):
        """The LLM must only receive public state variables in its context."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.")
        state = make_state(system_notes=["Test."])
        state["bot_memory"]["player"]["is_poisoned_with_asymptomatic_poison"] = True
        narrator_node(state, llm=fake_llm)
        # FAILS: stub never calls llm
        fake_llm.invoke.assert_called_once()
        call_arg = str(fake_llm.invoke.call_args)
        assert "is_poisoned_with_asymptomatic_poison" not in call_arg
