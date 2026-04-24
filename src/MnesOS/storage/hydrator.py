"""
MnesOS State Hydrator — reconstructs ``GameState`` from a lineage of
:class:`TurnLog` delta events.

The hydration process:

1. Start from the cartridge's ``initial_state`` (the defaults declared in
   ``yare_config.state_schema``).
2. Walk the ordered lineage from root → target node.
3. For each turn, deep-merge the ``yare_delta`` into ``bot_memory`` and
   append the user input and narrator text to ``client_messages``.

The result is a ``GameState``-shaped dict ready for the next graph
invocation.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from .models import TurnLog, TurnActor


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *overlay* into a **copy** of *base*.

    Scalar values in *overlay* overwrite those in *base*.  Dict values are
    merged recursively.  All other types (lists, etc.) are replaced.
    """
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class StateHydrator:
    """Utility class to reconstruct ``GameState`` from event-sourced turn logs.

    Aligned with the interface contract defined in
    ``docs/design/0005-interfaces-and-contracts.md`` §3.1.
    """

    @staticmethod
    def hydrate_state(
        turn_lineage: List[TurnLog],
        initial_bot_memory: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Reconstruct a ``GameState``-shaped dict from a lineage of turns.

        Parameters
        ----------
        turn_lineage:
            Ordered list of :class:`TurnLog` objects from root (index 0)
            to the target node (index -1).  An empty list is valid and
            returns the initial state with no conversation history.
        initial_bot_memory:
            The ``bot_memory`` defaults derived from the cartridge's
            ``yare_config.state_schema``.

        Returns
        -------
        dict
            A dict with the keys expected by :class:`GameState`:
            ``client_messages``, ``agent_messages``, ``bot_memory``,
            ``bot_memory_staging``, ``system_notes``, ``retrieved_lore``,
            ``iteration_count``, ``turn_phase``, ``npc_intent_calls``.
        """
        bot_memory: Dict[str, Any] = copy.deepcopy(initial_bot_memory)
        client_messages: List[Dict[str, str]] = []

        for turn in turn_lineage:
            # Apply yare_delta to bot_memory
            delta = turn.yare_delta
            if isinstance(delta, dict) and delta:
                bot_memory = _deep_merge(bot_memory, delta)

            # Reconstruct conversation history
            if turn.input_text:
                client_messages.append({
                    "role": "user",
                    "content": turn.input_text,
                })
            if turn.narrator_text:
                client_messages.append({
                    "role": "assistant",
                    "content": turn.narrator_text,
                })

        return {
            "client_messages": client_messages,
            "agent_messages": [],
            "bot_memory": bot_memory,
            "bot_memory_staging": [],
            "system_notes": [],
            "retrieved_lore": "",
            "iteration_count": 0,
            "turn_phase": "",
            "npc_intent_calls": 0,
        }


# Backward-compatible module-level function alias
def hydrate_state(
    turn_lineage: List[TurnLog],
    cartridge_initial_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Module-level convenience wrapper around :meth:`StateHydrator.hydrate_state`."""
    return StateHydrator.hydrate_state(turn_lineage, cartridge_initial_state)
