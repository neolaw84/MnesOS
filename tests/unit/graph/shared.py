import pytest
from unittest.mock import MagicMock
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from MnesOS.graph import GameState

class _BindableFakeModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel extended with a passthrough bind_tools() for tests."""
    def bind_tools(self, tools, **kwargs):
        return self

GENERIC_RPG_LORE = "cartridges/generic-rpg/bot_lore.md"

def make_state(**overrides) -> dict:
    """Builds a minimal GameState-shaped dict for node tests."""
    base = {
        "client_messages": [{"role": "user", "content": "I look around."}],
        "agent_messages": [],
        "bot_memory": {
            "player": {"hp": 100, "gold": 0, "level": 1},
            "npc":    {"hp": 20, "strength": 5},
            "current_location": "Crossroads",
        },
        "yare_config": {
            "state_schema": {
                "player": {
                    "hp":    {"type": "int", "default": 100, "visibility": "public"},
                    "gold":  {"type": "int", "default": 0,   "visibility": "public"},
                    "level": {"type": "int", "default": 1,   "visibility": "public"},
                    "is_poisoned_with_asymptomatic_poison": {
                        "type": "bool", "default": False, "visibility": "private"
                    },
                },
                "npc": {
                    "hp":       {"type": "int", "default": 20, "visibility": "public"},
                    "strength": {"type": "int", "default": 5,  "visibility": "public"},
                },
            },
            "events": {
                "deal_damage": {
                    "steps": [
                        {"action": "mutate", "var": "state.npc.hp", "op": "sub", "value": 10},
                        {"action": "note",   "message": "Player deals 10 damage."},
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
                                    "steps": [{"action": "note", "message": "Succeeded!"}],
                                },
                                {
                                    "else": True,
                                    "steps": [{"action": "note", "message": "Failed!"}],
                                },
                            ],
                        },
                    ],
                },
            },
            "macros": {},
        },
        "prompt_directives": {},
        "lore_path": GENERIC_RPG_LORE,
        "lore_content": "",
        "persona_context": {},
        "bot_memory_staging": [],
        "system_notes": [],
        "retrieved_lore": "",
        "iteration_count": 0,
        "turn_phase": "",
        "npc_intent_called": False,
    }
    base.update(overrides)
    return base
