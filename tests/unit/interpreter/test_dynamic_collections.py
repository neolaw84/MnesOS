"""
Tests for dynamic collection support in YAREEvaluator and InterpreterStore.
"""

import pytest
from MnesOS.interpreter.evaluator import YAREEvaluator
from MnesOS.interpreter.store import InterpreterStore


def test_subscript_dynamic_dict_access():
    config = {}
    state = {"entities": {"e1": {"health": 50}}}
    store = InterpreterStore(config, state)
    ev = YAREEvaluator(store)
    ctx = {"inputs": {"target_id": "e1"}}
    res = ev.evaluate("@ state.entities[inputs.target_id].health", ctx)
    assert res == 50


def test_dict_and_list_literals():
    config = {}
    state = {}
    store = InterpreterStore(config, state)
    ev = YAREEvaluator(store)
    ctx = {"temp": {"id": "x42"}, "inputs": {"val": 7}}
    d = ev.evaluate("@ {'id': temp.id, 'health': 100}", ctx)
    assert isinstance(d, dict)
    assert d["id"] == "x42"
    assert d["health"] == 100

    lst = ev.evaluate("@ [1, inputs.val, 'a']", ctx)
    assert isinstance(lst, list)
    assert lst[0] == 1
    assert lst[1] == 7
    assert lst[2] == 'a'


def test_attribute_resolves_local_context():
    config = {}
    state = {}
    store = InterpreterStore(config, state)
    ev = YAREEvaluator(store)
    ctx = {"current_entity": {"health": 99}}
    assert ev.evaluate("@ current_entity.health", ctx) == 99


def test_store_get_set_path_with_list_indices():
    config = {}
    state = {"entities": [{"id": "a", "health": 10}, {"id": "b", "health": 5}]}
    store = InterpreterStore(config, state)

    assert store.get_path("state.entities.1.health") == 5
    store.set_path("state.entities.0.health", 20)
    assert store.get_path("state.entities.0.health") == 20
