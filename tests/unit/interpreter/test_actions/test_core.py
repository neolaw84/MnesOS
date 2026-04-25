import pytest
from unittest.mock import patch
from ..shared import make_interp
from MnesOS.interpreter import YAREInterpreter

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

class TestActionNote:
    def test_note_appended_to_notes(self):
        interp = make_interp()
        interp._execute_step({"action": "note", "message": "Goblin appears!"}, {})
        assert "Goblin appears!" in interp.notes

    def test_note_interpolation(self, minimal_yare_config, minimal_state):
        interp = YAREInterpreter(minimal_yare_config, minimal_state)
        interp._execute_step(
            {"action": "note", "message": "HP is {state.player.hp}."},
            {},
        )
        assert "HP is 100." in interp.notes

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
                            {"if": "@ item.rare == True", "steps": [{"action": "note", "message": "Rare: {item.name}"}]},
                            {"else": True, "steps": [{"action": "note", "message": "Common: {item.name}"}]},
                        ],
                    }
                ],
            },
            {},
        )
        assert interp.notes == ["Common: Potion", "Rare: Relic"]

class TestActionListOperations:
    def test_action_list_push(self):
        interp = make_interp(state={"player": {"inventory": ["Potion"]}})
        interp._execute_step({"action": "list_push", "var": "state.player.inventory", "value": "'Sword'"}, {})
        assert interp.state["player"]["inventory"] == ["Potion", "Sword"]

    def test_action_list_remove(self):
        interp = make_interp(state={"player": {"inventory": ["Potion", "Sword"]}})
        interp._execute_step({"action": "list_remove", "var": "state.player.inventory", "value": "'Potion'"}, {})
        assert interp.state["player"]["inventory"] == ["Sword"]

class TestActionDictOperations:
    def test_action_dict_set(self):
        interp = make_interp(state={"player": {"stats": {}}})
        interp._execute_step({"action": "dict_set", "var": "state.player.stats", "key": "'STR'", "value": 10}, {})
        assert interp.state["player"]["stats"]["STR"] == 10

    def test_action_dict_delete(self):
        interp = make_interp(state={"player": {"stats": {"STR": 10}}})
        interp._execute_step({"action": "dict_delete", "var": "state.player.stats", "key": "'STR'"}, {})
        assert "STR" not in interp.state["player"]["stats"]
