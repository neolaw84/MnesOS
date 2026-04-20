"""
Pydantic request/response schemas for the MnesOS Alpha API.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# §1.1 Process Turn
# ---------------------------------------------------------------------------


class TurnRequest(BaseModel):
    """``POST /api/instances/{instance_id}/turn`` request body."""

    parent_turn_id: Optional[str] = Field(
        None,
        description="UUID of the previous turn (None for the first turn).",
    )
    user_input: str = Field(
        ...,
        min_length=1,
        description="The player's raw text input.",
    )


class TurnResponse(BaseModel):
    """``POST /api/instances/{instance_id}/turn`` response body."""

    turn_id: str
    narrator_response: str
    yare_delta: Dict[str, Any]


# ---------------------------------------------------------------------------
# §1.2 Inject State
# ---------------------------------------------------------------------------


class InjectRequest(BaseModel):
    """``POST /api/instances/{instance_id}/inject`` request body."""

    parent_turn_id: Optional[str] = Field(
        None,
        description="UUID of the turn to inject after.",
    )
    yare_delta: Dict[str, Any] = Field(
        ...,
        description="Raw JSON payload representing the state mutation.",
    )


class InjectResponse(BaseModel):
    """``POST /api/instances/{instance_id}/inject`` response body."""

    turn_id: str


# ---------------------------------------------------------------------------
# §1.3 Game Saves
# ---------------------------------------------------------------------------


class CreateSaveRequest(BaseModel):
    """``POST /api/instances/{instance_id}/saves`` request body."""

    turn_log_id: str
    label: str = Field(..., min_length=1)


class CreateSaveResponse(BaseModel):
    """``POST /api/instances/{instance_id}/saves`` response body."""

    save_id: str
    created_at: datetime


class GameSaveItem(BaseModel):
    """Single save entry for ``GET /api/instances/{instance_id}/saves``."""

    id: str
    instance_id: str
    turn_log_id: str
    label: str
    created_at: datetime


# ---------------------------------------------------------------------------
# §1.4 Load Game State (Hydration)
# ---------------------------------------------------------------------------


class HydratedStateResponse(BaseModel):
    """``GET /api/instances/{instance_id}/state`` response body."""

    bot_memory: Dict[str, Any]
    client_messages: List[Dict[str, str]]


# ---------------------------------------------------------------------------
# Cartridge CRUD schemas
# ---------------------------------------------------------------------------


class CreateCartridgeRequest(BaseModel):
    """``POST /api/cartridges`` request body."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    genre: str = Field(default="")
    visibility: str = Field(default="PUBLIC", description="PUBLIC or PRIVATE")


class CartridgeResponse(BaseModel):
    """Cartridge entity response."""

    id: str
    creator_id: str
    title: str
    description: str
    genre: str
    visibility: str


# ---------------------------------------------------------------------------
# CartridgeVersion schemas
# ---------------------------------------------------------------------------


class CartridgeVersionResponse(BaseModel):
    """CartridgeVersion entity response."""

    id: str
    cartridge_id: str
    version_tag: str
    yare_spec: Dict[str, Any]
    prompt_directives: Dict[str, Any]
    bot_lore: str
    checksum: str
    published_at: Optional[datetime]
