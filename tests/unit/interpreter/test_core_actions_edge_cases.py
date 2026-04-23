"""
Unit tests for YARE interpreter actions (core.py) — Edge cases and error handling.
"""

import pytest
from unittest.mock import MagicMock
from MnesOS.interpreter.actions.core import InterpreterActions

@pytest.fixture
def mock_interpreter():
    interp = MagicMock()
    interp.evaluate = lambda expr, ctx: expr # simple mock: expr is value
    interp.store.coerce = lambda val, var: val
    interp.store.get_path = lambda var: 10 # default value
    interp.store.get_schema = lambda var: {}
    interp.store.to_numeric = lambda val: int(val) if isinstance(val, (str, int)) else val
    interp.notes = []
    return interp

@pytest.fixture
def actions(mock_interpreter):
    return InterpreterActions(mock_interpreter)

def test_set_action_type_error(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[123, "val"]) # first call returns non-str for var
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "set", "var": 123, "value": "val"}, {})

def test_mutate_action_type_error(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[123, "val"])
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "mutate", "var": 123, "op": "add", "value": 5}, {})

def test_mutate_action_none_path(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    mock_interpreter.store.get_path = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="mutate: path 'x' resolved to None"):
        actions.execute_step({"action": "mutate", "var": "x", "op": "add", "value": 5}, {})

def test_mutate_action_unknown_op(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    mock_interpreter.store.get_path = MagicMock(return_value=10)
    with pytest.raises(ValueError, match="mutate: unknown op 'jump'"):
        actions.execute_step({"action": "mutate", "var": "x", "op": "jump", "value": 5}, {})

def test_table_roll_type_error(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[5, 123]) # roll=5, var=123
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "table_roll", "roll": 5, "var": 123, "table": {}}, {})

def test_call_action(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    actions.execute_step({"action": "call", "event": "on_hit", "args": {"dmg": 10}}, {})
    mock_interpreter.run_event.assert_called_once_with("on_hit", {"dmg": 10})

def test_list_push_type_error_var(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[123, "val"])
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "list_push", "var": 123, "item": "val"}, {})

def test_list_push_not_a_list(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    mock_interpreter.store.get_path = MagicMock(return_value="not-a-list")
    with pytest.raises(TypeError, match="not a list"):
        actions.execute_step({"action": "list_push", "var": "x", "item": "val"}, {})

def test_list_remove_type_error_var(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[123, "val"])
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "list_remove", "var": 123, "value": "val"}, {})

def test_list_remove_not_a_list(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    mock_interpreter.store.get_path = MagicMock(return_value="not-a-list")
    with pytest.raises(TypeError, match="not a list"):
        actions.execute_step({"action": "list_remove", "var": "x", "value": "val"}, {})

def test_dict_set_type_error_var(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[123, "k", "v"])
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "dict_set", "var": 123, "key": "k", "value": "v"}, {})

def test_dict_set_not_a_dict(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    mock_interpreter.store.get_path = MagicMock(return_value="not-a-dict")
    with pytest.raises(TypeError, match="not a dict"):
        actions.execute_step({"action": "dict_set", "var": "x", "key": "k", "value": "v"}, {})

def test_dict_delete_type_error_var(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(side_effect=[123, "k"])
    with pytest.raises(TypeError, match="'var' must resolve to a string path"):
        actions.execute_step({"action": "dict_delete", "var": 123, "key": "k"}, {})

def test_dict_delete_not_a_dict(actions, mock_interpreter):
    mock_interpreter.evaluate = lambda e, c: e
    mock_interpreter.store.get_path = MagicMock(return_value="not-a-dict")
    with pytest.raises(TypeError, match="not a dict"):
        actions.execute_step({"action": "dict_delete", "var": "x", "key": "k"}, {})

def test_foreach_not_a_list(actions, mock_interpreter):
    mock_interpreter.evaluate = MagicMock(return_value="not-a-list")
    with pytest.raises(TypeError, match="must resolve to a list"):
        actions.execute_step({"action": "foreach", "array": "x", "steps": []}, {})

def test_match_range_plus(actions, mock_interpreter):
    assert actions._match_range("10+", 10)
    assert actions._match_range("10+", 15)
    assert not actions._match_range("10+", 5)

def test_match_range_int(actions, mock_interpreter):
    assert actions._match_range(5, 5)
    assert not actions._match_range(5, 6)
