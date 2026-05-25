"""
Unit tests for the YARE JavaScript-to-YAML compiler.

Tests the static AST-based compilation of JavaScript YARE specs
into the standard YARE YAML intermediate representation.

TDD: These tests are written FIRST before the implementation.
"""

import pytest
import yaml

from MnesOS.yare_js_compiler import (
    compile_js_to_yare,
    YareJSCompilationError,
)


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------


class TestCompileJSToYareBasicStructure:
    """Test that basic JS YARE structures compile to valid YAML."""

    def test_minimal_spec(self):
        """A minimal JS spec with version and empty state compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {};
"""
        result = compile_js_to_yare(js_src)
        assert result["version"] == "1.0"
        assert result["state_schema"] == {}
        assert result["events"] == {}

    def test_version_extraction(self):
        """Version string is extracted from export."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {};
"""
        result = compile_js_to_yare(js_src)
        assert result["version"] == "1.0"

    def test_missing_version_raises(self):
        """Missing version export raises compilation error."""
        js_src = """
export const state_schema = {};
export const events = {};
"""
        with pytest.raises(YareJSCompilationError, match="version"):
            compile_js_to_yare(js_src)


# ---------------------------------------------------------------------------
# State schema tests
# ---------------------------------------------------------------------------


class TestStateSchemaCompilation:
    """Test state_schema JS object compiles correctly."""

    def test_simple_state_schema(self):
        """Simple state schema with typed fields compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {
    player: {
        hp: { type: "int", default: 100, min: 0, max: 100 },
        name: { type: "string", default: "Hero" }
    }
};
export const events = {};
"""
        result = compile_js_to_yare(js_src)
        assert result["state_schema"]["player"]["hp"]["type"] == "int"
        assert result["state_schema"]["player"]["hp"]["default"] == 100
        assert result["state_schema"]["player"]["hp"]["min"] == 0
        assert result["state_schema"]["player"]["hp"]["max"] == 100
        assert result["state_schema"]["player"]["name"]["default"] == "Hero"

    def test_visibility_field(self):
        """State schema visibility flag is preserved."""
        js_src = """
export const version = "1.0";
export const state_schema = {
    location: { type: "string", default: "tavern", visibility: "public" }
};
export const events = {};
"""
        result = compile_js_to_yare(js_src)
        assert result["state_schema"]["location"]["visibility"] == "public"

    def test_list_type_default(self):
        """State with list type and empty default compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {
    inventory: { type: "list", default: [] }
};
export const events = {};
"""
        result = compile_js_to_yare(js_src)
        assert result["state_schema"]["inventory"]["type"] == "list"
        assert result["state_schema"]["inventory"]["default"] == []


# ---------------------------------------------------------------------------
# Macros tests
# ---------------------------------------------------------------------------


class TestMacrosCompilation:
    """Test macros compile correctly."""

    def test_macro_definition(self):
        """Macros are compiled as @-prefixed expressions."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const macros = {
    damage_roll: "@ roll(1d20) + state.player.strength"
};
export const events = {};
"""
        result = compile_js_to_yare(js_src)
        assert result["macros"]["damage_roll"] == "@ roll(1d20) + state.player.strength"


# ---------------------------------------------------------------------------
# Events tests
# ---------------------------------------------------------------------------


class TestEventsCompilation:
    """Test event definitions compile correctly."""

    def test_simple_event_with_inputs(self):
        """Event with inputs and steps compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    combat_strike: {
        description: "Execute a melee attack",
        inputs: {
            attacker: { type: "string", default: "player" },
            power: { type: "int", default: 0 }
        },
        steps: [
            { action: "set", var: "temp.roll", value: "@ roll(1d20) + inputs.power" },
            { action: "note", message: "Attack roll: {temp.roll}" }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        event = result["events"]["combat_strike"]
        assert event["description"] == "Execute a melee attack"
        assert event["inputs"]["attacker"]["type"] == "string"
        assert event["inputs"]["attacker"]["default"] == "player"
        assert len(event["steps"]) == 2
        assert event["steps"][0]["action"] == "set"
        assert event["steps"][0]["var"] == "temp.roll"
        assert event["steps"][1]["action"] == "note"

    def test_event_with_branch(self):
        """Event with branch conditions compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    check_hp: {
        inputs: {},
        steps: [
            {
                action: "branch",
                conditions: [
                    {
                        if: "@ state.player.hp <= 0",
                        steps: [
                            { action: "note", message: "Player is dead!" }
                        ]
                    },
                    {
                        else: true,
                        steps: [
                            { action: "note", message: "Player is alive." }
                        ]
                    }
                ]
            }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        event = result["events"]["check_hp"]
        branch = event["steps"][0]
        assert branch["action"] == "branch"
        assert len(branch["conditions"]) == 2
        assert branch["conditions"][0]["if"] == "@ state.player.hp <= 0"
        assert branch["conditions"][1]["else"] is True

    def test_event_with_mutate(self):
        """Event with mutate step compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    heal: {
        inputs: { amount: { type: "int", default: 10 } },
        steps: [
            { action: "mutate", var: "state.player.hp", op: "add", value: "@ inputs.amount" }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        step = result["events"]["heal"]["steps"][0]
        assert step["action"] == "mutate"
        assert step["op"] == "add"
        assert step["var"] == "state.player.hp"

    def test_event_with_call(self):
        """Event with call step compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    attack_sequence: {
        inputs: {},
        steps: [
            { action: "call", event: "combat_strike", inputs: { attacker: "player" } }
        ]
    },
    combat_strike: {
        inputs: { attacker: { type: "string" } },
        steps: []
    }
};
"""
        result = compile_js_to_yare(js_src)
        step = result["events"]["attack_sequence"]["steps"][0]
        assert step["action"] == "call"
        assert step["event"] == "combat_strike"

    def test_event_with_list_push(self):
        """Event with list_push step compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    add_item: {
        inputs: { item_name: { type: "string" } },
        steps: [
            { action: "list_push", var: "state.inventory", item: "@ inputs.item_name" }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        step = result["events"]["add_item"]["steps"][0]
        assert step["action"] == "list_push"
        assert step["var"] == "state.inventory"

    def test_event_with_foreach(self):
        """Event with foreach step compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    show_inventory: {
        inputs: {},
        steps: [
            {
                action: "foreach",
                array: "@ state.inventory",
                item: "item",
                index: "idx",
                steps: [
                    { action: "note", message: "Item {inputs.idx}: {inputs.item}" }
                ]
            }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        step = result["events"]["show_inventory"]["steps"][0]
        assert step["action"] == "foreach"
        assert step["array"] == "@ state.inventory"
        assert step["item"] == "item"
        assert step["index"] == "idx"
        assert len(step["steps"]) == 1

    def test_event_with_table_roll(self):
        """Event with table_roll step compiles."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = {
    random_loot: {
        inputs: {},
        steps: [
            {
                action: "table_roll",
                roll: "1d6",
                var: "temp.loot",
                table: {
                    "1-2": "gold",
                    "3-4": "potion",
                    "5-6": "gem"
                }
            }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        step = result["events"]["random_loot"]["steps"][0]
        assert step["action"] == "table_roll"
        assert step["roll"] == "1d6"
        assert step["table"]["1-2"] == "gold"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestCompilationErrors:
    """Test that invalid JS raises appropriate errors."""

    def test_syntax_error_raises(self):
        """Malformed JS raises compilation error."""
        js_src = """
export const version = "1.0"
export const state_schema = {{{BROKEN
"""
        with pytest.raises(YareJSCompilationError):
            compile_js_to_yare(js_src)

    def test_unsupported_function_calls_raise(self):
        """Function calls (non-literal) in object positions raise errors."""
        js_src = """
export const version = "1.0";
export const state_schema = computeSchema();
export const events = {};
"""
        with pytest.raises(YareJSCompilationError):
            compile_js_to_yare(js_src)

    def test_non_object_events_raises(self):
        """Events must be an object literal."""
        js_src = """
export const version = "1.0";
export const state_schema = {};
export const events = "not_an_object";
"""
        with pytest.raises(YareJSCompilationError):
            compile_js_to_yare(js_src)


# ---------------------------------------------------------------------------
# Programmatic generation tests (loops)
# ---------------------------------------------------------------------------


class TestProgrammaticGeneration:
    """Test JS-native features like loops for rule generation."""

    def test_loop_generated_events(self):
        """Events generated via for-loop compile correctly."""
        js_src = """
export const version = "1.0";
export const state_schema = {};

const events = {};
const elements = ["fire", "ice", "lightning"];
for (const elem of elements) {
    events[elem + "_spell"] = {
        description: "Cast " + elem + " spell",
        inputs: { power: { type: "int", default: 5 } },
        steps: [
            { action: "note", message: "Cast " + elem + "!" }
        ]
    };
}
export { events };
"""
        result = compile_js_to_yare(js_src)
        assert "fire_spell" in result["events"]
        assert "ice_spell" in result["events"]
        assert "lightning_spell" in result["events"]
        assert result["events"]["fire_spell"]["description"] == "Cast fire spell"

    def test_helper_function_generated_steps(self):
        """Steps generated by helper functions compile."""
        js_src = """
export const version = "1.0";
export const state_schema = {};

function makeHealStep(amount) {
    return { action: "mutate", var: "state.player.hp", op: "add", value: amount };
}

export const events = {
    small_heal: {
        inputs: {},
        steps: [makeHealStep(10)]
    },
    big_heal: {
        inputs: {},
        steps: [makeHealStep(50)]
    }
};
"""
        result = compile_js_to_yare(js_src)
        assert result["events"]["small_heal"]["steps"][0]["value"] == 10
        assert result["events"]["big_heal"]["steps"][0]["value"] == 50


# ---------------------------------------------------------------------------
# Round-trip consistency test
# ---------------------------------------------------------------------------


class TestRoundTripConsistency:
    """Ensure compiled output produces valid YARE that passes existing validators."""

    def test_compiled_output_is_valid_yaml_serializable(self):
        """Compiled dict can be serialized to YAML without error."""
        js_src = """
export const version = "1.0";
export const state_schema = {
    player: {
        hp: { type: "int", default: 100, min: 0, max: 100 }
    }
};
export const events = {
    heal: {
        inputs: { amount: { type: "int", default: 10 } },
        steps: [
            { action: "mutate", var: "state.player.hp", op: "add", value: "@ inputs.amount" }
        ]
    }
};
"""
        result = compile_js_to_yare(js_src)
        # Should serialize cleanly to YAML
        yaml_str = yaml.dump(result, default_flow_style=False)
        # And reload back identically
        reloaded = yaml.safe_load(yaml_str)
        assert reloaded["version"] == "1.0"
        assert reloaded["events"]["heal"]["steps"][0]["action"] == "mutate"
