import pytest

from MnesOS.exceptions import InteractionRoutingError
from MnesOS.graph.nodes.input_router import input_router_node

from ..shared import make_config, make_state


_YARE_WITH_RESOLVER = {
    "state_schema": {},
    "events": {
        "hack_terminal_resolve": {
            "inputs": ["status", "metrics", "minigame_specific_data"],
            "steps": [
                {"action": "set", "var": "state.last_minigame_status", "value": "@ inputs.status"},
                {"action": "set", "var": "state.last_minigame_metrics", "value": "@ inputs.metrics"},
                {"action": "set", "var": "state.last_minigame_data", "value": "@ inputs.minigame_specific_data"},
                {"action": "note", "message": "Resolved minigame."},
            ],
        }
    },
    "macros": {},
}


class TestInputRouterNode:
    def test_minigame_routes_to_resolver_and_clears_pending(self):
        state = make_state()
        state["bot_memory"]["_pending_interaction"] = {
            "interaction_type": "minigame",
            "minigame_id": "lights_out",
            "resolver_event": "hack_terminal_resolve",
            "config": {"difficulty": {}, "assets": {}, "narrative_hooks": {}},
        }
        state["incoming_interaction"] = {
            "interaction_type": "minigame",
            "minigame_id": "lights_out",
            "status": "completed",
            "metrics": {"time_taken_ms": 1234, "rank": "A"},
            "minigame_specific_data": {"moves_made": 12},
        }

        config = make_config(yare_config=_YARE_WITH_RESOLVER)
        result = input_router_node(state, config)

        new_memory = result["bot_memory"]
        assert new_memory["last_minigame_status"] == "completed"
        assert new_memory["last_minigame_metrics"]["rank"] == "A"
        assert new_memory["last_minigame_data"]["moves_made"] == 12
        assert "_pending_interaction" not in new_memory
        assert result["incoming_interaction"] is None
        assert any("Minigame resolved: lights_out" in n for n in result["system_notes"])

    def test_minigame_id_mismatch_raises(self):
        state = make_state()
        state["bot_memory"]["_pending_interaction"] = {
            "interaction_type": "minigame",
            "minigame_id": "lights_out",
            "resolver_event": "hack_terminal_resolve",
            "config": {},
        }
        state["incoming_interaction"] = {
            "interaction_type": "minigame",
            "minigame_id": "other_game",
            "status": "completed",
            "metrics": {},
            "minigame_specific_data": {},
        }
        config = make_config(yare_config=_YARE_WITH_RESOLVER)

        with pytest.raises(InteractionRoutingError):
            input_router_node(state, config)

    def test_no_pending_interaction_raises(self):
        state = make_state(incoming_interaction={
            "interaction_type": "minigame",
            "minigame_id": "lights_out",
            "status": "completed",
            "metrics": {},
            "minigame_specific_data": {},
        })
        config = make_config(yare_config=_YARE_WITH_RESOLVER)

        with pytest.raises(InteractionRoutingError):
            input_router_node(state, config)

    def test_non_minigame_interaction_is_cleared(self):
        state = make_state(incoming_interaction={"interaction_type": "dialog"})
        config = make_config(yare_config=_YARE_WITH_RESOLVER)

        result = input_router_node(state, config)
        assert result["incoming_interaction"] is None

