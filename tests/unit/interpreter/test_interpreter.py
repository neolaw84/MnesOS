import pytest
from unittest.mock import patch
from .shared import make_interp
from MnesOS.interpreter import YAREInterpreter, MAX_CONTAINER_SIZE, MAX_DICT_DEPTH

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

class TestInterpreterSystemLimits:
    def test_max_container_size_enforced_list_push(self):
        interp = make_interp(state={"list": [1] * MAX_CONTAINER_SIZE})
        with pytest.raises(ValueError, match="MAX_CONTAINER_SIZE"):
            interp._execute_step({"action": "list_push", "var": "state.list", "value": 2}, {})
        assert len(interp.state["list"]) == MAX_CONTAINER_SIZE


    def test_max_container_size_enforced_dict_set(self):
        interp = make_interp(state={"dict": {str(i): i for i in range(MAX_CONTAINER_SIZE)}})
        with pytest.raises(ValueError, match="MAX_CONTAINER_SIZE"):
            interp._execute_step({"action": "dict_set", "var": "state.dict", "key": "'extra'", "value": 1}, {})
        assert "extra" not in interp.state["dict"]


    def test_max_dict_depth_enforced(self):
        interp = make_interp()
        # Create a value that is already at MAX_DICT_DEPTH
        nested_val = 1
        for _ in range(MAX_DICT_DEPTH):
            nested_val = {"step": nested_val}
        
        # Try to set this nested dict into another dict, which would make total depth = MAX_DICT_DEPTH + 1
        with pytest.raises(ValueError, match="MAX_DICT_DEPTH"):
            interp._execute_step({"action": "dict_set", "var": "state.any", "key": "'deep'", "value": nested_val}, {})


