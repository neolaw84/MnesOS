"""
MnesOS Logical Schema — data models for the persistence layer.

These dataclasses define the six entities of the MnesOS ecosystem:
UserAccount, Persona, Cartridge, CartridgeVersion, GameInstance, TurnLog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    PLAYER = "PLAYER"
    CREATOR = "CREATOR"


class Visibility(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class GameStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class TurnActor(str, Enum):
    PLAYER = "PLAYER"
    NPC = "NPC"
    SYSTEM = "SYSTEM"
    NARRATOR = "NARRATOR"


# ---------------------------------------------------------------------------
# Entity dataclasses
# ---------------------------------------------------------------------------


@dataclass
class UserAccount:
    """
    Represents a registered MnesOS user.

    Relations:
      1:N with Persona
      1:N with Cartridge (as creator)
      1:N with GameInstance
    """

    username: str
    email: str
    password_hash: str
    role: UserRole
    id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Persona:
    """
    A player's in-game identity, including pronoun tokens for template
    substitution (``{{user}}``, ``{{sub}}``, ``{{obj}}``, etc.) and
    narrative background context.

    Relations:
      N:1 with UserAccount
      1:N with GameInstance
    """

    user_id: str
    name: str
    pronoun_sub: str
    pronoun_obj: str
    pronoun_poss: str
    pronoun_poss_obj: str
    appearance: str
    background: str
    personality: str
    id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Cartridge:
    """
    A game cartridge created by a CREATOR user.

    Relations:
      N:1 with UserAccount
      1:N with CartridgeVersion
    """

    creator_id: str
    title: str
    description: str
    genre: str
    visibility: Visibility
    id: Optional[str] = None


@dataclass
class CartridgeVersion:
    """
    An immutable, versioned snapshot of a cartridge's content.

    ``yare_spec`` and ``prompt_directives`` are stored as JSON blobs and
    deserialized back to dicts on retrieval.

    Relations:
      N:1 with Cartridge
      1:N with GameInstance
    """

    cartridge_id: str
    version_tag: str
    yare_spec: Any          # dict — serialized to/from JSON
    prompt_directives: Any  # dict — serialized to/from JSON
    bot_lore: str
    checksum: str
    id: Optional[str] = None
    published_at: Optional[datetime] = None


@dataclass
class GameInstance:
    """
    A single play-through session linking a user, persona, and cartridge
    version.

    Relations:
      N:1 with UserAccount
      N:1 with Persona
      N:1 with CartridgeVersion
      1:N with TurnLog
    """

    user_id: str
    persona_id: str
    version_id: str
    status: GameStatus
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_played_at: Optional[datetime] = None


@dataclass
class TurnLog:
    """
    An immutable record of a single game turn (atomic append).

    ``yare_delta`` captures the state-change events fired during the turn,
    stored as a JSON blob.

    Relations:
      N:1 with GameInstance
    """

    instance_id: str
    turn_index: int
    actor: TurnActor
    input_text: str
    yare_delta: Any     # dict — serialized to/from JSON
    id: Optional[str] = None
    timestamp: Optional[datetime] = None
