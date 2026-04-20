"""
Unit tests for the MnesOS State Hydrator.

Test coverage:
  - Empty lineage returns cartridge initial state with empty messages
  - Single turn applies delta to bot_memory correctly
  - Multiple turns sequentially build up the state
  - Deep-merge preserves non-overlapping keys
  - client_messages are reconstructed from input_text / narrator_text
  - Turns with empty deltas are handled gracefully
  - System actor turns (injected cheats) apply correctly
  - The result dict has all expected GameState keys
"""

import copy
import pytest

from MnesOS.storage.models import TurnLog, TurnActor
from MnesOS.storage.hydrator import hydrate_state, StateHydrator, _deep_merge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INITIAL_STATE = {
    "player": {"hp": 100, "gold": 0, "level": 1},
    "npc": {"hp": 20, "strength": 5},
    "current_location": "Crossroads",
}


def _make_turn(
    turn_index: int,
    input_text: str = "",
    narrator_text: str = "",
    yare_delta: dict = None,
    actor: TurnActor = TurnActor.PLAYER,
    parent_id: str = None,
    turn_id: str = None,
) -> TurnLog:
    return TurnLog(
        instance_id="inst-1",
        turn_index=turn_index,
        actor=actor,
        input_text=input_text,
        yare_delta=yare_delta or {},
        narrator_text=narrator_text,
        parent_id=parent_id,
        id=turn_id or f"turn-{turn_index}",
    )


# ---------------------------------------------------------------------------
# _deep_merge tests
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_scalar_overwrite(self):
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_new_key_added(self):
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_nested_dict_merge(self):
        base = {"player": {"hp": 100, "gold": 0}}
        overlay = {"player": {"gold": 50}}
        result = _deep_merge(base, overlay)
        assert result == {"player": {"hp": 100, "gold": 50}}

    def test_does_not_mutate_base(self):
        base = {"player": {"hp": 100}}
        overlay = {"player": {"hp": 50}}
        _deep_merge(base, overlay)
        assert base["player"]["hp"] == 100

    def test_empty_overlay(self):
        base = {"a": 1}
        assert _deep_merge(base, {}) == {"a": 1}

    def test_empty_base(self):
        assert _deep_merge({}, {"a": 1}) == {"a": 1}

    def test_list_replaced_not_appended(self):
        base = {"items": [1, 2, 3]}
        overlay = {"items": [4, 5]}
        result = _deep_merge(base, overlay)
        assert result["items"] == [4, 5]


# ---------------------------------------------------------------------------
# hydrate_state tests
# ---------------------------------------------------------------------------


class TestHydrateState:
    def test_empty_lineage_returns_initial_state(self):
        result = hydrate_state([], INITIAL_STATE)
        assert result["bot_memory"] == INITIAL_STATE
        assert result["client_messages"] == []

    def test_does_not_mutate_initial_state(self):
        original = copy.deepcopy(INITIAL_STATE)
        turn = _make_turn(0, yare_delta={"player": {"hp": 50}})
        hydrate_state([turn], INITIAL_STATE)
        assert INITIAL_STATE == original

    def test_single_turn_applies_delta(self):
        turn = _make_turn(
            0,
            input_text="I attack.",
            narrator_text="You swing your sword.",
            yare_delta={"npc": {"hp": 10}},
        )
        result = hydrate_state([turn], INITIAL_STATE)
        assert result["bot_memory"]["npc"]["hp"] == 10
        assert result["bot_memory"]["player"]["hp"] == 100  # unchanged

    def test_multiple_turns_sequential_deltas(self):
        turns = [
            _make_turn(0, input_text="Turn 1", narrator_text="Response 1",
                        yare_delta={"player": {"gold": 10}}),
            _make_turn(1, input_text="Turn 2", narrator_text="Response 2",
                        yare_delta={"player": {"gold": 25}}),
            _make_turn(2, input_text="Turn 3", narrator_text="Response 3",
                        yare_delta={"npc": {"hp": 5}}),
        ]
        result = hydrate_state(turns, INITIAL_STATE)
        assert result["bot_memory"]["player"]["gold"] == 25  # last delta wins
        assert result["bot_memory"]["npc"]["hp"] == 5

    def test_client_messages_reconstructed(self):
        turns = [
            _make_turn(0, input_text="Hello", narrator_text="Greetings, traveler."),
            _make_turn(1, input_text="I look around.", narrator_text="You see a forest."),
        ]
        result = hydrate_state(turns, INITIAL_STATE)
        assert len(result["client_messages"]) == 4
        assert result["client_messages"][0] == {"role": "user", "content": "Hello"}
        assert result["client_messages"][1] == {"role": "assistant", "content": "Greetings, traveler."}
        assert result["client_messages"][2] == {"role": "user", "content": "I look around."}
        assert result["client_messages"][3] == {"role": "assistant", "content": "You see a forest."}

    def test_turn_with_empty_delta(self):
        turn = _make_turn(0, input_text="I wait.", narrator_text="Nothing happens.", yare_delta={})
        result = hydrate_state([turn], INITIAL_STATE)
        assert result["bot_memory"] == INITIAL_STATE

    def test_turn_with_none_delta(self):
        turn = _make_turn(0, input_text="I wait.", narrator_text="Nothing.", yare_delta=None)
        result = hydrate_state([turn], INITIAL_STATE)
        assert result["bot_memory"] == INITIAL_STATE

    def test_system_actor_injects_delta(self):
        """System (cheat) turns should apply their delta like any other."""
        turn = _make_turn(
            0,
            actor=TurnActor.SYSTEM,
            yare_delta={"player": {"gold": 999}},
        )
        result = hydrate_state([turn], INITIAL_STATE)
        assert result["bot_memory"]["player"]["gold"] == 999

    def test_deep_nested_merge(self):
        initial = {"world": {"regions": {"forest": {"danger": 3}}}}
        turn = _make_turn(0, yare_delta={"world": {"regions": {"forest": {"danger": 7}}}})
        result = hydrate_state([turn], initial)
        assert result["bot_memory"]["world"]["regions"]["forest"]["danger"] == 7

    def test_new_top_level_keys_added_by_delta(self):
        turn = _make_turn(0, yare_delta={"quest_active": True})
        result = hydrate_state([turn], INITIAL_STATE)
        assert result["bot_memory"]["quest_active"] is True

    def test_result_has_all_gamestate_keys(self):
        result = hydrate_state([], INITIAL_STATE)
        expected_keys = {
            "client_messages", "agent_messages", "bot_memory",
            "bot_memory_staging", "system_notes", "retrieved_lore",
            "iteration_count", "turn_phase", "npc_intent_called",
        }
        assert set(result.keys()) == expected_keys

    def test_result_ephemeral_fields_are_reset(self):
        """Ephemeral fields should always be fresh (empty) after hydration."""
        turns = [
            _make_turn(0, input_text="x", narrator_text="y", yare_delta={"player": {"hp": 50}}),
        ]
        result = hydrate_state(turns, INITIAL_STATE)
        assert result["agent_messages"] == []
        assert result["bot_memory_staging"] == []
        assert result["system_notes"] == []
        assert result["retrieved_lore"] == ""
        assert result["iteration_count"] == 0
        assert result["turn_phase"] == ""
        assert result["npc_intent_called"] is False

    def test_turn_without_narrator_text_skips_assistant_message(self):
        turn = _make_turn(0, input_text="I arrive.", narrator_text="")
        result = hydrate_state([turn], INITIAL_STATE)
        assert len(result["client_messages"]) == 1
        assert result["client_messages"][0]["role"] == "user"

    def test_turn_without_input_text_skips_user_message(self):
        """System turns may have no input_text."""
        turn = _make_turn(0, input_text="", narrator_text="System applied.", actor=TurnActor.SYSTEM)
        result = hydrate_state([turn], INITIAL_STATE)
        assert len(result["client_messages"]) == 1
        assert result["client_messages"][0]["role"] == "assistant"


class TestStateHydratorClass:
    """Tests for the StateHydrator class interface (per 0005 §3.1)."""

    def test_class_has_static_method(self):
        assert hasattr(StateHydrator, "hydrate_state")
        assert callable(StateHydrator.hydrate_state)

    def test_class_produces_same_result_as_function(self):
        turns = [
            _make_turn(0, input_text="Hi", narrator_text="Hello.",
                        yare_delta={"player": {"gold": 10}}),
        ]
        from_func = hydrate_state(turns, INITIAL_STATE)
        from_class = StateHydrator.hydrate_state(turns, INITIAL_STATE)
        assert from_func == from_class

    def test_class_empty_lineage(self):
        result = StateHydrator.hydrate_state([], INITIAL_STATE)
        assert result["bot_memory"] == INITIAL_STATE
        assert result["client_messages"] == []
