from .shared import make_state, make_config, _DEFAULT_YARE_CONFIG
from MnesOS.graph.state import get_public_state, get_npc_visible_state

class TestGetPublicState:
    def test_public_vars_included(self):
        state = make_state()
        pub = get_public_state(state["bot_memory"], _DEFAULT_YARE_CONFIG)
        assert pub["player"]["hp"] == 100
        assert pub["player"]["gold"] == 0

    def test_private_vars_excluded(self):
        state = make_state()
        state["bot_memory"]["player"]["is_poisoned_with_asymptomatic_poison"] = True
        pub = get_public_state(state["bot_memory"], _DEFAULT_YARE_CONFIG)
        assert "is_poisoned_with_asymptomatic_poison" not in pub["player"]

    def test_empty_bot_memory_returns_empty(self):
        pub = get_public_state({}, {"state_schema": {}})
        assert pub == {}

    def test_schema_defaults_visibility_to_private(self):
        """A field with no 'visibility' key must be treated as private."""
        bot_memory = {"player": {"secret": 42}}
        yare_config = {
            "state_schema": {
                "player": {"secret": {"type": "int", "default": 0}}  # no visibility key
            }
        }
        pub = get_public_state(bot_memory, yare_config)
        assert "secret" not in pub.get("player", {})

class TestGetNpcVisibleState:
    def test_npc_visible_vars_included(self):
        yare_config = {
            "state_schema": {
                "player": {"npc_visibility": True},
                "secret": {"npc_visibility": False}
            }
        }
        bot_memory = {"player": {"hp": 100}, "secret": "shh"}
        visible = get_npc_visible_state(bot_memory, yare_config)
        assert "player" in visible
        assert "secret" not in visible

    def test_missing_schema_entry_is_excluded(self):
        yare_config = {"state_schema": {}}
        bot_memory = {"some_var": 42}
        visible = get_npc_visible_state(bot_memory, yare_config)
        assert visible == {}
