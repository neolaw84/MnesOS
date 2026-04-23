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
    GameSave,
)
from .interface import AbstractStorageComponent
from .sqlite3_store import SQLite3PhysicalComponent
from .hydrator import hydrate_state, StateHydrator

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
    "GameSave",
    "AbstractStorageComponent",
    "SQLite3PhysicalComponent",
    "hydrate_state",
    "StateHydrator",
]
