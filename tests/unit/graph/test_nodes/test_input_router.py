"""
Tests for [MnesOS-260516-10] Graph – Input Router Node for Pending States.

Requirements:
1. Free-text inputs MUST be rejected when a _pending_interaction exists → raise InteractionRoutingError.
2. The HTTP error code for interaction routing mismatches MUST be 409 Conflict (not 400).
3. MinigameInput node should still route valid interactions to the YARE resolver.
"""

import pytest

from MnesOS.exceptions import InteractionRoutingError
from MnesOS.graph.nodes.minigame_input import minigame_input_node

from ..shared import make_config, make_state


_YARE_WITH_RESOLVER = {
    "state_schema": {},
    "events": {
        "hack_terminal_resolve": {
            "inputs": ["status", "metrics", "minigame_specific_data"],
            "steps": [
                {"action": "set", "var": "state.resolved", "value": True},
                {"action": "note", "message": "Resolved hack minigame."},
            ],
        }
    },
    "macros": {},
}

_PENDING_INTERACTION = {
    "interaction_type": "minigame",
    "minigame_id": "lights_out",
    "resolver_event": "hack_terminal_resolve",
    "config": {"difficulty": {}, "assets": {}, "narrative_hooks": {}},
}


class TestFreeTextRejection:
    """Free-text inputs MUST be rejected when a _pending_interaction is present."""

    def test_free_text_rejected_when_pending_interaction_exists(self):
        """If user sends free text while minigame is pending, raise InteractionRoutingError."""
        state = make_state()
        state["bot_memory"]["_pending_interaction"] = _PENDING_INTERACTION
        # No incoming_interaction means this is a normal free-text turn
        state["incoming_interaction"] = None

        config = make_config(yare_config=_YARE_WITH_RESOLVER)

        with pytest.raises(InteractionRoutingError, match="pending"):
            minigame_input_node(state, config)

    def test_free_text_allowed_when_no_pending_interaction(self):
        """Normal free-text turns pass through when no pending interaction exists."""
        state = make_state()
        # No _pending_interaction and no incoming_interaction
        state["incoming_interaction"] = None

        config = make_config(yare_config=_YARE_WITH_RESOLVER)

        result = minigame_input_node(state, config)
        # Should return empty dict (pass-through)
        assert result == {}


class TestConflictValidation:
    """Interaction type/id mismatches should use specific error messages for 409 mapping."""

    def test_interaction_type_mismatch_raises_routing_error(self):
        """Submitting a non-minigame interaction when pending expects minigame → 409."""
        state = make_state()
        state["bot_memory"]["_pending_interaction"] = _PENDING_INTERACTION
        state["incoming_interaction"] = {
            "interaction_type": "action_form",
            "minigame_id": "lights_out",
            "status": "completed",
            "metrics": {},
            "minigame_specific_data": {},
        }

        config = make_config(yare_config=_YARE_WITH_RESOLVER)

        with pytest.raises(InteractionRoutingError):
            minigame_input_node(state, config)
