"""
MnesOS Alpha API — FastAPI application package.

Exposes the game engine via a RESTful API aligned with
``docs/design/0005-interfaces-and-contracts.md`` §1.
"""

from .auth import AuthSession, AuthValidator, AuthProvider, AuthFactory

__all__ = [
    "AuthSession",
    "AuthValidator",
    "AuthProvider",
    "AuthFactory",
]
