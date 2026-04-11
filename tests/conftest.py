"""
Shared fixtures for MnesOS unit tests.

sys.path is patched here so all test modules can import directly from src/
without an editable-install being required during development.
"""

import sys
import pytest

# Ensure src/ is importable regardless of how pytest is invoked.
# pytest is always run from the project root (testpaths=["tests"] in pyproject.toml).
if "src" not in sys.path:
    sys.path.insert(0, "src")

# ---------------------------------------------------------------------------
# Shared YARE fixtures (generic-rpg themed)
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_yare_config():
    """Smallest valid YARE config for interpreter / rules-engine tests."""
    return {
        "state_schema": {
            "player": {
                "hp":    {"type": "int", "default": 100, "min": 0, "max": 100, "visibility": "public"},
                "gold":  {"type": "int", "default": 0,   "min": 0,             "visibility": "public"},
                "level": {"type": "int", "default": 1,                         "visibility": "public"},
                "is_poisoned_with_asymptomatic_poison": {
                    "type": "bool", "default": False, "visibility": "private"
                },
            },
            "npc": {
                "hp":       {"type": "int", "default": 20, "min": 0, "visibility": "public"},
                "strength": {"type": "int", "default": 5,            "visibility": "public"},
            },
            "current_location": {"type": "string", "default": "Crossroads"},
        },
        "macros": {
            "power_bonus": "@ state.player.level + 1",
        },
        "events": {
            "deal_damage": {
                "steps": [
                    {"action": "mutate", "var": "state.npc.hp", "op": "sub", "value": 10},
                    {"action": "note",   "message": "Player deals 10 damage to the NPC."},
                ]
            },
            "heal_player": {
                "steps": [
                    {"action": "mutate", "var": "state.player.hp", "op": "add", "value": 20},
                    {"action": "note",   "message": "Player heals 20 HP."},
                ]
            },
            "generic_check": {
                "inputs": {
                    "stat":       {"type": "string", "description": "Which stat is being tested"},
                    "difficulty": {"type": "int",    "description": "Target number to meet or beat"},
                },
                "steps": [
                    {"action": "set",  "var": "temp.roll", "value": "@ roll(1d20) + state.player.level"},
                    {
                        "action": "branch",
                        "conditions": [
                            {
                                "if": "@ temp.roll >= inputs.difficulty",
                                "steps": [{"action": "note", "message": "Action Succeeded!"}],
                            },
                            {
                                "else": True,
                                "steps": [{"action": "note", "message": "Action Failed!"}],
                            },
                        ],
                    },
                ],
            },
        },
    }


@pytest.fixture
def minimal_state():
    """Initial bot_memory matching minimal_yare_config defaults."""
    return {
        "player": {"hp": 100, "gold": 0, "level": 1, "is_poisoned_with_asymptomatic_poison": False},
        "npc":    {"hp": 20, "strength": 5},
        "current_location": "Crossroads",
    }


@pytest.fixture
def generic_rpg_cartridge_dir():
    """Path to the generic-rpg cartridge directory (CWD-relative)."""
    return "cartridges/generic-rpg"
