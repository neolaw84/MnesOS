"""MnesOS domain exceptions.

Keep these lightweight and dependency-free so they can be used from core engine
code (graph nodes, orchestrator) and API adapters.
"""


class InteractionRoutingError(ValueError):
    """Raised when an incoming structured interaction cannot be securely routed."""

