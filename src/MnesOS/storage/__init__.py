"""
MnesOS Storage Layer.

Provides the logical schema (models), abstract interface, and
SQLite3-backed physical component for persistent game state.
"""

from .models import (
    UserRole,
    Visibility,
    GameStatus,
    TurnActor,
    UserAccount,
    Persona,
    Cartridge,
    CartridgeVersion,
    GameInstance,
    TurnLog,
)
from .interface import AbstractStorageComponent
from .sqlite3_store import SQLite3PhysicalComponent

__all__ = [
    "UserRole",
    "Visibility",
    "GameStatus",
    "TurnActor",
    "UserAccount",
    "Persona",
    "Cartridge",
    "CartridgeVersion",
    "GameInstance",
    "TurnLog",
    "AbstractStorageComponent",
    "SQLite3PhysicalComponent",
]
