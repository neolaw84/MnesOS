import pytest
from unittest.mock import patch
from .shared import make_interp

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
        assert interp.evaluate("@ inputs.difficulty", context={"inputs": {"difficulty": 12}}) == 12

    def test_macro_access(self):
        config = {"macros": {"power_bonus": "@ 3 + 1"}}
        interp = make_interp(state=None)
        interp.config = config
        assert interp.evaluate("@ macros.power_bonus") == 4

    def test_private_state_access_allowed(self):
        interp = make_interp(state={"player": {"is_poisoned_with_asymptomatic_poison": True}})
        # Config would usually hold schema, but interpreter just reads for evaluate()
        assert interp.evaluate("@ state.player.is_poisoned_with_asymptomatic_poison") is True

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

class TestNumericCoercion:
    def test_to_numeric_ints_floats(self):
        interp = make_interp()
        assert interp._to_numeric(5) == 5
        assert interp._to_numeric(3.14) == pytest.approx(3.14)
    
    def test_to_numeric_strings(self):
        interp = make_interp()
        assert interp._to_numeric("10") == 10
        assert interp._to_numeric("3.5") == pytest.approx(3.5)
    
    def test_to_numeric_invalid_returns_zero(self):
        interp = make_interp()
        assert interp._to_numeric("abc") == 0
        assert interp._to_numeric(None) == 0

class TestASTDeprecationsAndEdgeCases:
    def test_ast_num_deprecation_fallback(self):
        """Ensures the interpreter handles ast.Num nodes gracefully for backward compatibility."""
        import ast
        interp = make_interp()
        node = ast.Num(n=42)
        assert interp._eval_node(node) == 42

    def test_ast_str_deprecation_fallback(self):
        """Ensures the interpreter handles ast.Str nodes gracefully for backward compatibility."""
        import ast
        interp = make_interp()
        node = ast.Str(s="test")
        assert interp._eval_node(node) == "test"

class TestComplexYAREOperators:
    def test_unary_not(self):
        interp = make_interp()
        assert interp.evaluate("@ not True") is False
        assert interp.evaluate("@ not False") is True

    def test_logical_or(self):
        interp = make_interp()
        assert interp.evaluate("@ True or False") is True
        assert interp.evaluate("@ False or False") is False

    def test_conditional_truthiness(self):
        interp = make_interp(state={"player": {"hp": 0}})
        assert interp.evaluate("@ 'Alive' if state.player.hp > 0 else 'Dead'") == "Dead"

class TestComplexExpressions:
    def test_multi_term_addition_with_dice_and_vars(self):
        # Formula: roll(3d6) + NPC skill + PC speed bonus
        state = {"active_npcs": {"npc_1": {"skill_mod": 10}}}
        interp = make_interp(state=state)
        interp.temp["pc_speed_bonus"] = 5
        
        with patch("random.randint", side_effect=[2, 4, 6]): # Sum = 12
            expr = "@ roll(3d6) + state.active_npcs.npc_1.skill_mod + temp.pc_speed_bonus"
            assert interp.evaluate(expr) == 27 # 12 + 10 + 5

    def test_nested_ternary_speed_bonuses(self):
        # SFW logic: fast (5), slow (1), normal (2), expert (1)
        expr = "@ (5 if 'fast' in temp.speed else (1 if 'slow' in temp.speed else (2 if 'normal' in temp.speed else (1 if 'expert' in temp.speed else 0))))"
        
        interp = make_interp()
        
        # Case 1: Fast
        interp.temp["speed"] = "speed_fast"
        assert interp.evaluate(expr) == 5
        
        # Case 2: Slow
        interp.temp["speed"] = "speed_slow"
        assert interp.evaluate(expr) == 1
        
        # Case 3: Fallback
        interp.temp["speed"] = "idle"
        assert interp.evaluate(expr) == 0
