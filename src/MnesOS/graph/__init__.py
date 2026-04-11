"""
MnesOS graph sub-package — LangGraph state, nodes, routers, and factory.

Public API
~~~~~~~~~~

**State definition** (from :mod:`.graph`):

.. autoclass:: GameState

**Nodes** (from :mod:`.graph`):

.. autofunction:: context_retrieval_node
.. autofunction:: cycle_tick_node
.. autofunction:: director_node
.. autofunction:: npc_brain_node
.. autofunction:: narrator_node
.. autofunction:: pre_tools_node
.. autofunction:: post_tools_node
.. autofunction:: reset_agent_messages_node
.. autofunction:: cleanup_agent_messages_node

**Edge routers** (from :mod:`.graph`):

.. autofunction:: route_director
.. autofunction:: route_director_separate
.. autofunction:: route_npc_brain
.. autofunction:: route_rules

**Tools** (from :mod:`.graph`):

.. autofunction:: build_yare_event_tools
.. autofunction:: end_of_narration

**Helpers** (from :mod:`.graph`):

.. autofunction:: build_graph
.. autofunction:: get_public_state

**Default workflow** (from :mod:`.graph`):

``workflow`` — a pre-built (but uncompiled) :class:`~langgraph.graph.StateGraph`
for quick visualization or fallback testing.

Backward compatibility
~~~~~~~~~~~~~~~~~~~~~~
All names previously importable from the flat ``MnesOS.graph`` module
(``src/MnesOS/graph.py``) remain importable from ``MnesOS.graph`` (this
package).  Existing ``from MnesOS.graph import X`` statements continue to
work without modification.

Sub-package layout
~~~~~~~~~~~~~~~~~~
::

    MnesOS/graph/
    ├── __init__.py  ← you are here; re-exports public API
    └── graph.py     ← GameState, nodes, routers, build_graph, workflow
"""

from .graph import (
    # State
    GameState,
    MAX_ITERATIONS,
    # Node functions
    cleanup_agent_messages_node,
    context_retrieval_node,
    cycle_tick_node,
    director_node,
    narrator_node,
    npc_brain_node,
    post_tools_node,
    pre_tools_node,
    reset_agent_messages_node,
    # Edge routers
    route_director,
    route_director_separate,
    route_npc_brain,
    route_rules,
    # Tools
    build_yare_event_tools,
    end_of_narration,
    # Helpers
    build_graph,
    get_public_state,
    # Default workflow (for visualization / testing)
    workflow,
)

__all__ = [
    # State
    "GameState",
    "MAX_ITERATIONS",
    # Nodes
    "cleanup_agent_messages_node",
    "context_retrieval_node",
    "cycle_tick_node",
    "director_node",
    "narrator_node",
    "npc_brain_node",
    "post_tools_node",
    "pre_tools_node",
    "reset_agent_messages_node",
    # Routers
    "route_director",
    "route_director_separate",
    "route_npc_brain",
    "route_rules",
    # Tools
    "build_yare_event_tools",
    "end_of_narration",
    # Helpers
    "build_graph",
    "get_public_state",
    # Default workflow
    "workflow",
]
