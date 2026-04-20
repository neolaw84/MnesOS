"""
MnesOS AbstractStorageComponent — defines the interface every physical storage
back-end must implement.

Implementing a new back-end (e.g. PostgreSQL) only requires:
  1. Subclassing AbstractStorageComponent
  2. Implementing all abstract methods
  3. Switching the configuration flag — no engine-level changes needed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import (
    CartridgeVersion,
    Cartridge,
    GameInstance,
    GameSave,
    Persona,
    TurnLog,
    UserAccount,
)


class AbstractStorageComponent(ABC):
    """
    Repository-pattern interface for the MnesOS persistence layer.

    All CRUD operations and the state-logging append are defined here as
    abstract methods so that every physical store (SQLite3, Postgres, …)
    exposes an identical surface to the orchestrator.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def initialize(self) -> None:
        """Create the schema (tables, indexes) if it does not yet exist."""

    # ------------------------------------------------------------------
    # UserAccount
    # ------------------------------------------------------------------

    @abstractmethod
    def create_user(self, user: UserAccount) -> UserAccount:
        """Persist a new UserAccount and return it with its assigned id."""

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[UserAccount]:
        """Return a UserAccount by primary key, or None if not found."""

    @abstractmethod
    def update_user(self, user: UserAccount) -> UserAccount:
        """Persist changes to an existing UserAccount and return it."""

    @abstractmethod
    def delete_user(self, user_id: str) -> None:
        """Remove a UserAccount by primary key."""

    # ------------------------------------------------------------------
    # Persona
    # ------------------------------------------------------------------

    @abstractmethod
    def create_persona(self, persona: Persona) -> Persona:
        """Persist a new Persona and return it with its assigned id."""

    @abstractmethod
    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """Return a Persona by primary key, or None if not found."""

    @abstractmethod
    def update_persona(self, persona: Persona) -> Persona:
        """Persist changes to an existing Persona and return it."""

    @abstractmethod
    def delete_persona(self, persona_id: str) -> None:
        """Remove a Persona by primary key."""

    # ------------------------------------------------------------------
    # Cartridge
    # ------------------------------------------------------------------

    @abstractmethod
    def create_cartridge(self, cartridge: Cartridge) -> Cartridge:
        """Persist a new Cartridge and return it with its assigned id."""

    @abstractmethod
    def get_cartridge(self, cartridge_id: str) -> Optional[Cartridge]:
        """Return a Cartridge by primary key, or None if not found."""

    @abstractmethod
    def update_cartridge(self, cartridge: Cartridge) -> Cartridge:
        """Persist changes to an existing Cartridge and return it."""

    @abstractmethod
    def delete_cartridge(self, cartridge_id: str) -> None:
        """Remove a Cartridge by primary key."""

    # ------------------------------------------------------------------
    # CartridgeVersion
    # ------------------------------------------------------------------

    @abstractmethod
    def create_cartridge_version(
        self, version: CartridgeVersion
    ) -> CartridgeVersion:
        """Persist a new CartridgeVersion and return it with its assigned id."""

    @abstractmethod
    def list_cartridges(self) -> List[Cartridge]:
        """Return all Cartridge records."""

    @abstractmethod
    def get_cartridge_version(
        self, version_id: str
    ) -> Optional[CartridgeVersion]:
        """Return a CartridgeVersion by primary key, or None if not found."""

    @abstractmethod
    def list_cartridge_versions(self, cartridge_id: str) -> List[CartridgeVersion]:
        """Return all CartridgeVersion records for a given Cartridge, ordered by published_at."""

    # ------------------------------------------------------------------
    # GameInstance
    # ------------------------------------------------------------------

    @abstractmethod
    def create_game_instance(self, instance: GameInstance) -> GameInstance:
        """Persist a new GameInstance and return it with its assigned id."""

    @abstractmethod
    def get_game_instance(self, instance_id: str) -> Optional[GameInstance]:
        """Return a GameInstance by primary key, or None if not found."""

    @abstractmethod
    def update_game_instance(self, instance: GameInstance) -> GameInstance:
        """Persist changes to an existing GameInstance and return it."""

    @abstractmethod
    def get_game_instance_context(
        self, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Return the full context needed to resume a game session.

        Returns a dict with keys:
          ``game_instance`` — :class:`GameInstance`
          ``persona``       — :class:`Persona`
          ``cartridge_version`` — :class:`CartridgeVersion`

        Returns None if the instance does not exist.
        """

    # ------------------------------------------------------------------
    # TurnLog — write-optimized append
    # ------------------------------------------------------------------

    @abstractmethod
    def append_turn_log(self, log: TurnLog) -> TurnLog:
        """
        Atomically append a TurnLog entry and return it with its assigned id.

        Implementations must ensure this operation is an atomic INSERT so that
        concurrent writes cannot corrupt the log sequence.
        """

    @abstractmethod
    def get_turn_logs(
        self, instance_id: str, limit: Optional[int] = None
    ) -> List[TurnLog]:
        """Return TurnLog entries for a GameInstance, ordered by turn_index."""

    @abstractmethod
    def get_turn_lineage(self, turn_id: str) -> List[TurnLog]:
        """
        Traverse up the ``parent_id`` chain from *turn_id* to the root and
        return an ordered list of :class:`TurnLog` objects from root to the
        specified node (inclusive).

        Raises ``KeyError`` if *turn_id* does not exist.
        """

    # ------------------------------------------------------------------
    # GameSave — bookmarks into the turn tree
    # ------------------------------------------------------------------

    @abstractmethod
    def create_game_save(self, save: GameSave) -> GameSave:
        """Persist a new GameSave and return it with its assigned id."""

    @abstractmethod
    def get_game_save(self, save_id: str) -> Optional[GameSave]:
        """Return a GameSave by primary key, or None if not found."""

    @abstractmethod
    def list_game_saves(self, instance_id: str) -> List[GameSave]:
        """Return all GameSave entries for a GameInstance, ordered by created_at."""

    @abstractmethod
    def delete_game_save(self, save_id: str) -> None:
        """Remove a GameSave by primary key."""
