import pytest
from .shared import make_interp

class TestPathLogic:
    def test_get_path_simple(self):
        interp = make_interp(state={"player": {"hp": 100}})
        assert interp._get_path("state.player.hp") == 100

    def test_get_path_temp(self):
        interp = make_interp()
        interp.temp["x"] = 42
        assert interp._get_path("temp.x") == 42

    def test_get_path_missing_returns_none(self):
        interp = make_interp()
        assert interp._get_path("state.missing") is None

    def test_set_path_simple(self):
        interp = make_interp(state={"player": {"hp": 100}})
        interp._set_path("state.player.hp", 80)
        assert interp.state["player"]["hp"] == 80

    def test_set_path_creates_intermediate_dicts(self):
        interp = make_interp()
        interp._set_path("state.new.nested.var", "val")
        assert interp.state["new"]["nested"]["var"] == "val"

class TestPathCaseInsensitiveFallback:
    def test_get_path_fallback(self):
        interp = make_interp(state={"Player": {"HP": 100}})
        # Exact match fails, fallback to case-insensitive
        assert interp._get_path("state.player.hp") == 100

    def test_set_path_fallback(self):
        interp = make_interp(state={"Player": {"HP": 100}})
        interp._set_path("state.player.hp", 50)
        assert interp.state["Player"]["HP"] == 50

class TestDictDepth:
    def test_flat_dict_has_depth_one(self):
        interp = make_interp()
        assert interp._dict_depth({"a": 1, "b": 2}) == 1

    def test_two_level_dict_has_depth_two(self):
        interp = make_interp()
        assert interp._dict_depth({"a": {"b": 1}}) == 2

    def test_three_level_dict_has_depth_three(self):
        interp = make_interp()
        assert interp._dict_depth({"a": {"b": {"c": 1}}}) == 3

    def test_non_dict_value_has_depth_zero(self):
        interp = make_interp()
        assert interp._dict_depth("not a dict") == 0

    def test_empty_dict_has_depth_zero(self):
        interp = make_interp()
        assert interp._dict_depth({}) == 0
