"""
Unit tests for YAREEvaluator (evaluator.py) — Edge cases and error handling.
"""

import pytest
import ast
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from MnesOS.interpreter.evaluator import YAREEvaluator

@pytest.fixture
def mock_store():
    store = MagicMock()
    store.to_numeric = lambda x: float(x) if isinstance(x, str) else x
    return store

@pytest.fixture
def evaluator(mock_store):
    return YAREEvaluator(mock_store)

def test_eval_literal_constant(evaluator):
    # Test ast.Constant (Python 3.8+)
    node = ast.Constant(value=123)
    assert evaluator._eval_node(node, {}) == 123

def test_eval_if_exp_true(evaluator):
    # Test IfExp where test is true
    res = evaluator.evaluate("@ 10 if True else 20", {})
    assert res == 10

def test_eval_timedelta_call(evaluator):
    # Test timedelta(hours=1)
    res = evaluator.evaluate("@ timedelta(hours=1)", {})
    assert res == timedelta(hours=1)

def test_eval_unsupported_node(evaluator):
    # Test a node that is not supported, like a list comprehension
    with pytest.raises(ValueError, match="Unsupported YARE expression node"):
        evaluator.evaluate("@ [x for x in state.items]", {})

def test_parse_timestamp_datetime(evaluator):
    now = datetime.now()
    assert evaluator._parse_timestamp(now) == now

def test_parse_timestamp_float(evaluator):
    ts = 1600000000.0
    expected = datetime.fromtimestamp(ts)
    assert evaluator._parse_timestamp(ts) == expected

def test_parse_timestamp_z_suffix(evaluator):
    ts = "2023-01-01T12:00:00Z"
    res = evaluator._parse_timestamp(ts)
    assert res.year == 2023
    assert res.month == 1
    assert res.day == 1

def test_parse_timestamp_invalid_string(evaluator):
    with pytest.raises(ValueError, match="Unsupported timestamp format"):
        evaluator._parse_timestamp("not-a-date")

def test_parse_timestamp_unsupported_type(evaluator):
    with pytest.raises(TypeError, match="time_delta unsupported type"):
        evaluator._parse_timestamp([])

def test_eval_name_from_context(evaluator):
    assert evaluator.evaluate("@ my_var", {"my_var": "val"}) == "val"

def test_eval_name_fallback_to_store(evaluator, mock_store):
    mock_store.get_path.return_value = "store_val"
    assert evaluator.evaluate("@ other_var", {}) == "store_val"
    mock_store.get_path.assert_called_with("other_var")

def test_eval_not_operator(evaluator):
    assert evaluator.evaluate("@ not True", {}) is False
    assert evaluator.evaluate("@ not False", {}) is True
