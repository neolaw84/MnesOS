"""
Unit tests for interpreter.YAREInterpreter.

Covers: expression evaluation, all action types (set/mutate/branch/table_roll/
        call/note), schema bounds, call-depth guard, private-variable access
        enforcement, and dice mocking.
"""

import pytest
from unittest.mock import patch
from MnesOS.interpreter import YAREInterpreter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_interp(config=None, state=None):
    config = config or {}
    state  = state  or {}
    return YAREInterpreter(config, state)


# ---------------------------------------------------------------------------
# evaluate() — literal pass-through
# ---------------------------------------------------------------------------

class TestEvaluateLiterals:
    def test_non_string_passthrough(self):
        interp = make_interp()
        assert interp.evaluate(42) == 42
        assert interp.evaluate(3.14) == pytest.approx(3.14)
        assert interp.evaluate(True) is True
        assert interp.evaluate(None) is None

    def test_string_without_at_passthrough(self):
        interp = make_interp()
        assert interp.evaluate("hello") == "hello"

    def test_at_string_integer_literal(self):
        interp = make_interp()
        assert interp.evaluate("@ 5") == 5

    def test_at_string_float_literal(self):
        interp = make_interp()
        assert interp.evaluate("@ 3.14") == pytest.approx(3.14)

    def test_at_string_string_literal(self):
        interp = make_interp()
        assert interp.evaluate("@ 'Safe Haven'") == "Safe Haven"


# ---------------------------------------------------------------------------
# evaluate() — arithmetic
# ---------------------------------------------------------------------------

class TestEvaluateArithmetic:
    def test_addition(self):
        assert make_interp().evaluate("@ 3 + 4") == 7

    def test_subtraction(self):
        assert make_interp().evaluate("@ 10 - 3") == 7

    def test_multiplication(self):
        assert make_interp().evaluate("@ 6 * 7") == 42

    def test_floor_division(self):
        assert make_interp().evaluate("@ 7 // 2") == 3

    def test_modulo(self):
        assert make_interp().evaluate("@ 10 % 3") == 1

    def test_abs_function(self):
        assert make_interp().evaluate("@ abs(-5)") == 5

    def test_time_delta_days(self):
        interp = make_interp()
        result = interp.evaluate("@ time_delta('2026-04-01T00:00:00', '2026-04-03T00:00:00')")
        assert result.days == 2

    def test_time_delta_with_state_values(self):
        interp = make_interp(state={"game_time": {"start": "2026-04-01T10:00:00", "now": "2026-04-01T10:45:00"}})
        result = interp.evaluate("@ time_delta(state.game_time.start, state.game_time.now)")
        assert int(result.total_seconds()) == 2700


# ---------------------------------------------------------------------------
# evaluate() — comparisons and boolean
# ---------------------------------------------------------------------------

class TestEvaluateComparisons:
    def test_equal_true(self):
        assert make_interp().evaluate("@ 5 == 5") is True

    def test_equal_false(self):
        assert make_interp().evaluate("@ 5 == 6") is False

    def test_not_equal(self):
        assert make_interp().evaluate("@ 5 != 6") is True

    def test_less_than(self):
        assert make_interp().evaluate("@ 3 < 5") is True

    def test_greater_than_or_equal(self):
        assert make_interp().evaluate("@ 5 >= 5") is True

    def test_and_both_true(self):
        assert make_interp().evaluate("@ 1 == 1 and 2 == 2") is True

    def test_and_one_false(self):
        assert make_interp().evaluate("@ 1 == 1 and 2 == 3") is False


# ---------------------------------------------------------------------------
# evaluate() — state / temp / inputs access
# ---------------------------------------------------------------------------

class TestEvaluateAccess:
    def test_state_access(self):
        interp = make_interp(state={"player": {"hp": 80}})
        assert interp.evaluate("@ state.player.hp") == 80

    def test_temp_access(self):
        interp = make_interp()
        interp.temp["score"] = 15
        assert interp.evaluate("@ temp.score") == 15

    def test_inputs_access(self):
        interp = make_interp()
        assert interp.evaluate("@ inputs.difficulty", context={"difficulty": 12}) == 12

    def test_macro_access(self):
        config = {"macros": {"power_bonus": "@ 3 + 1"}}
        interp = make_interp(config=config)
        assert interp.evaluate("@ macros.power_bonus") == 4

    def test_private_state_access_allowed(self):
        """Visibility is a Narrator-filter concern only; the interpreter must read private fields."""
        config = {
            "state_schema": {
                "player": {
                    "is_poisoned_with_asymptomatic_poison": {
                        "type": "bool", "default": False, "visibility": "private"
                    }
                }
            }
        }
        interp = make_interp(
            config=config,
            state={"player": {"is_poisoned_with_asymptomatic_poison": True}},
        )
        assert interp.evaluate("@ state.player.is_poisoned_with_asymptomatic_poison") is True

    def test_public_state_access_allowed(self):
        """Accessing a public variable via @ expression must succeed."""
        config = {
            "state_schema": {
                "player": {"hp": {"type": "int", "default": 100, "visibility": "public"}}
            }
        }
        interp = make_interp(config=config, state={"player": {"hp": 75}})
        assert interp.evaluate("@ state.player.hp") == 75

    def test_unsupported_expression_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            make_interp().evaluate("@ [1, 2, 3]")  # list literal not supported


# ---------------------------------------------------------------------------
# evaluate() — roll() (deterministic via mock)
# ---------------------------------------------------------------------------

class TestRoll:
    def test_roll_1d20_uses_randint(self):
        interp = make_interp()
        with patch("random.randint", return_value=13) as mock_ri:
            result = interp.evaluate("@ roll(1d20)")
        mock_ri.assert_called_once_with(1, 20)
        assert result == 13

    def test_roll_3d6_sums_three_dice(self):
        interp = make_interp()
        with patch("random.randint", side_effect=[2, 4, 6]):
            result = interp.evaluate("@ roll(3d6)")
        assert result == 12

    def test_roll_explicit_quotes(self):
        """Test that expressions using explicitly quoted notations don't trigger double quotes."""
        interp = make_interp()
        with patch("random.randint", side_effect=[2, 4, 6]):
            result = interp.evaluate("@ roll('3d6')")
        assert result == 12

    def test_roll_plus_modifier(self):
        interp = make_interp(state={"player": {"level": 3}})
        config = {"state_schema": {"player": {"level": {"type": "int", "visibility": "public"}}}}
        interp.config = config
        with patch("random.randint", return_value=10):
            result = interp.evaluate("@ roll(1d20) + state.player.level")
        assert result == 13


# ---------------------------------------------------------------------------
# _execute_step — set
# ---------------------------------------------------------------------------

class TestActionSet:
    def test_set_literal(self):
        interp = make_interp(state={"player": {"hp": 100}})
        interp._execute_step(
            {"action": "set", "var": "state.player.hp", "value": 50}, {}
        )
        assert interp.state["player"]["hp"] == 50

    def test_set_string_literal(self):
        interp = make_interp(state={"current_location": "Crossroads"})
        interp._execute_step(
            {"action": "set", "var": "state.current_location", "value": "'Safe Haven'"}, {}
        )
        assert interp.state["current_location"] == "Safe Haven"

    def test_set_into_temp(self):
        interp = make_interp()
        interp._execute_step(
            {"action": "set", "var": "temp.roll", "value": "@ 7 + 3"}, {}
        )
        assert interp.temp["roll"] == 10


# ---------------------------------------------------------------------------
# _execute_step — mutate + schema bounds
# ---------------------------------------------------------------------------

class TestActionMutate:
    def test_mutate_add(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {"action": "mutate", "var": "state.player.hp", "op": "add", "value": 10}, {}
        )
        assert interp.state["player"]["hp"] == 100  # capped at max=100

    def test_mutate_sub(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {"action": "mutate", "var": "state.player.hp", "op": "sub", "value": 30}, {}
        )
        assert interp.state["player"]["hp"] == 70

    def test_mutate_clamp_at_min(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {"action": "mutate", "var": "state.player.hp", "op": "sub", "value": 9999}, {}
        )
        assert interp.state["player"]["hp"] == 0  # min=0

    def test_mutate_mul(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {"action": "mutate", "var": "state.player.gold", "op": "add", "value": 5}, {}
        )
        interp._execute_step(
            {"action": "mutate", "var": "state.player.gold", "op": "mul", "value": 2}, {}
        )
        assert interp.state["player"]["gold"] == 10

    def test_mutate_dynamic_var(self, minimal_yare_config, minimal_state):
        """var may be an @-expression that resolves to a dotted state path."""
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        # "@ 'state.' + inputs.target + '.hp'" -> "state.npc.hp"
        interp._execute_step(
            {"action": "mutate", "var": "@ 'state.' + inputs.target + '.hp'", "op": "sub", "value": 8},
            {"target": "npc"},
        )
        assert interp.state["npc"]["hp"] == 12  # 20 - 8

    def test_set_dynamic_var(self, minimal_yare_config, minimal_state):
        """var in set action may also be an @-expression."""
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {"action": "set", "var": "@ 'state.' + inputs.field", "value": "'Dungeon'"},
            {"field": "current_location"},
        )
        assert interp.state["current_location"] == "Dungeon"


# ---------------------------------------------------------------------------
# _execute_step — branch
# ---------------------------------------------------------------------------

class TestActionBranch:
    def test_branch_if_true(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {
                "action": "branch",
                "conditions": [
                    {
                        "if": "@ 1 == 1",
                        "steps": [
                            {"action": "set", "var": "temp.hit", "value": True}
                        ],
                    }
                ],
            },
            {},
        )
        assert interp.temp.get("hit") is True

    def test_branch_if_false_uses_else(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {
                "action": "branch",
                "conditions": [
                    {
                        "if": "@ 1 == 2",
                        "steps": [{"action": "set", "var": "temp.result", "value": "'if-branch'"}],
                    },
                    {
                        "else": True,
                        "steps": [{"action": "set", "var": "temp.result", "value": "'else-branch'"}],
                    },
                ],
            },
            {},
        )
        assert interp.temp.get("result") == "else-branch"

    def test_only_first_matching_condition_executes(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {
                "action": "branch",
                "conditions": [
                    {
                        "if": "@ 1 == 1",
                        "steps": [{"action": "set", "var": "temp.which", "value": 1}],
                    },
                    {
                        "if": "@ 2 == 2",
                        "steps": [{"action": "set", "var": "temp.which", "value": 2}],
                    },
                ],
            },
            {},
        )
        assert interp.temp.get("which") == 1


# ---------------------------------------------------------------------------
# _execute_step — table_roll
# ---------------------------------------------------------------------------

class TestActionTableRoll:
    def test_table_roll_range_match(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        with patch("random.randint", return_value=5):
            interp._execute_step(
                {
                    "action": "table_roll",
                    "var": "temp.archetype",
                    "roll": "@ roll(1d20)",
                    "table": {"1-5": "Goblin", "6-10": "Orc", "11+": "Dragon"},
                },
                {},
            )
        assert interp.temp.get("archetype") == "Goblin"

    def test_table_roll_plus_match(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        with patch("random.randint", return_value=15):
            interp._execute_step(
                {
                    "action": "table_roll",
                    "var": "temp.archetype",
                    "roll": "@ roll(1d20)",
                    "table": {"1-10": "Normal", "11+": "Boss"},
                },
                {},
            )
        assert interp.temp.get("archetype") == "Boss"


# ---------------------------------------------------------------------------
# _execute_step — note
# ---------------------------------------------------------------------------

class TestActionNote:
    def test_note_appended_to_notes(self):
        interp = make_interp()
        interp._execute_step({"action": "note", "message": "Goblin appears!"}, {})
        assert "Goblin appears!" in interp.notes

    def test_note_interpolation(self):
        interp = make_interp(state={"player": {"hp": 75}})
        interp.config = {
            "state_schema": {"player": {"hp": {"type": "int", "visibility": "public"}}}
        }
        interp._execute_step(
            {"action": "note", "message": "HP is {state.player.hp}."},
            {},
        )
        assert "HP is 75." in interp.notes

    def test_note_without_interpolation_braces(self):
        interp = make_interp()
        interp._execute_step({"action": "note", "message": "Simple fixed message."}, {})
        assert interp.notes == ["Simple fixed message."]


# ---------------------------------------------------------------------------
# _execute_step — foreach
# ---------------------------------------------------------------------------

class TestActionForeach:
    def test_foreach_iterates_list_and_branches_per_item(self):
        interp = make_interp(
            state={"player": {"inventory": [{"name": "Potion", "rare": False}, {"name": "Relic", "rare": True}]}}
        )
        interp._execute_step(
            {
                "action": "foreach",
                "array": "@ state.player.inventory",
                "item": "item",
                "steps": [
                    {
                        "action": "branch",
                        "conditions": [
                            {"if": "@ inputs.item.rare == True", "steps": [{"action": "note", "message": "Rare: {inputs.item.name}"}]},
                            {"else": True, "steps": [{"action": "note", "message": "Common: {inputs.item.name}"}]},
                        ],
                    }
                ],
            },
            {},
        )
        assert interp.notes == ["Common: Potion", "Rare: Relic"]

    def test_foreach_non_list_raises(self):
        interp = make_interp(state={"player": {"inventory": "not-a-list"}})
        with pytest.raises(TypeError, match="must resolve to a list"):
            interp._execute_step(
                {"action": "foreach", "array": "@ state.player.inventory", "steps": []},
                {},
            )


# ---------------------------------------------------------------------------
# run_event — end-to-end
# ---------------------------------------------------------------------------

class TestRunEvent:
    def test_run_event_deal_damage(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp.run_event("deal_damage")
        assert interp.state["npc"]["hp"] == 10  # 20 - 10
        assert any("damage" in n for n in interp.notes)

    def test_run_event_undefined_does_nothing(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp.run_event("nonexistent_event")
        assert interp.notes == []
        assert interp.state == minimal_state

    def test_run_event_max_call_depth_guard(self, minimal_yare_config, minimal_state):
        """When call depth exceeds the limit, a SYSTEM note is emitted and execution halts."""
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp.call_depth = interp.max_call_depth + 1
        interp.run_event("deal_damage")
        assert any("Max event call depth" in n for n in interp.notes)
        # State must be unchanged because execution was halted
        assert interp.state["npc"]["hp"] == 20

    def test_run_event_generic_check_success(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        with patch("random.randint", return_value=20):  # always 20 on 1d20
            interp.run_event("generic_check", {"stat": "hp", "difficulty": 10})
        assert any("Succeeded" in n for n in interp.notes)

    def test_run_event_generic_check_failure(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        with patch("random.randint", return_value=1):  # always 1 on 1d20 → 1+1=2 < 10
            interp.run_event("generic_check", {"stat": "hp", "difficulty": 10})
        assert any("Failed" in n for n in interp.notes)


# ---------------------------------------------------------------------------
# run_event — enum enforcement
# ---------------------------------------------------------------------------

class TestRunEventEnumEnforcement:
    _CONFIG = {
        "events": {
            "strike": {
                "inputs": {
                    "target": {"type": "string", "default": "npc", "enum": ["player", "npc"]},
                },
                "steps": [{"action": "note", "message": "target is {inputs.target}"}],
            }
        }
    }

    def test_exact_lowercase_passes_through(self):
        interp = YAREInterpreter(self._CONFIG, {})
        interp.run_event("strike", {"target": "npc"})
        assert interp.notes[-1] == "target is npc"

    def test_uppercase_normalized_to_lowercase(self):
        interp = YAREInterpreter(self._CONFIG, {})
        interp.run_event("strike", {"target": "NPC"})
        assert interp.notes[-1] == "target is npc"

    def test_mixed_case_normalized(self):
        interp = YAREInterpreter(self._CONFIG, {})
        interp.run_event("strike", {"target": "Player"})
        assert interp.notes[-1] == "target is player"

    def test_invalid_value_falls_back_to_default(self):
        interp = YAREInterpreter(self._CONFIG, {})
        interp.run_event("strike", {"target": "enemy"})
        assert interp.notes[-1] == "target is npc"

    def test_missing_input_uses_default(self):
        interp = YAREInterpreter(self._CONFIG, {})
        interp.run_event("strike", {})
        assert interp.notes[-1] == "target is npc"


# ---------------------------------------------------------------------------
# _get_path / _set_path — case-insensitive key fallback
# ---------------------------------------------------------------------------

class TestPathCaseInsensitiveFallback:
    def test_get_path_exact_case(self):
        interp = make_interp(state={"npc": {"hp": 20}})
        assert interp._get_path("state.npc.hp") == 20

    def test_get_path_uppercase_falls_back(self):
        interp = make_interp(state={"npc": {"hp": 20}})
        assert interp._get_path("state.NPC.hp") == 20

    def test_get_path_mixed_case_falls_back(self):
        interp = make_interp(state={"player": {"hp": 100}})
        assert interp._get_path("state.Player.hp") == 100

    def test_set_path_uppercase_modifies_existing_key(self):
        interp = make_interp(state={"npc": {"hp": 20}})
        interp._set_path("state.NPC.hp", 5)
        assert interp.state["npc"]["hp"] == 5

    def test_set_path_does_not_create_new_cased_key(self):
        interp = make_interp(state={"npc": {"hp": 20}})
        interp._set_path("state.NPC.hp", 5)
        assert "NPC" not in interp.state
