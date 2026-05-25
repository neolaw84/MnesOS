"""
Pydantic request/response schemas for the MnesOS Alpha API.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# UserAccount schemas
# ---------------------------------------------------------------------------

class UserAccountResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: Optional[datetime]

class CreateUserAccountRequest(BaseModel):
    username: str = Field(..., min_length=1)
    email: str
    password: str = Field(..., min_length=6)
    role: str = Field(default="PLAYER")

class UpdateUserAccountRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# ---------------------------------------------------------------------------
# Persona schemas
# ---------------------------------------------------------------------------

class PersonaResponse(BaseModel):
    id: str
    user_id: str
    name: str
    pronoun_sub: str
    pronoun_obj: str
    pronoun_poss: str
    pronoun_poss_obj: str
    appearance: str
    background: str
    personality: str
    created_at: Optional[datetime]

class CreatePersonaRequest(BaseModel):
    name: str
    pronoun_sub: str
    pronoun_obj: str
    pronoun_poss: str
    pronoun_poss_obj: str
    appearance: str
    background: str
    personality: str

class UpdatePersonaRequest(BaseModel):
    name: Optional[str] = None
    pronoun_sub: Optional[str] = None
    pronoun_obj: Optional[str] = None
    pronoun_poss: Optional[str] = None
    pronoun_poss_obj: Optional[str] = None
    appearance: Optional[str] = None
    background: Optional[str] = None
    personality: Optional[str] = None


# ---------------------------------------------------------------------------
# §1.1 Process Turn
# ---------------------------------------------------------------------------

class MinigameInteractionPayload(BaseModel):
    """Structured payload for client-side interactions (e.g. minigames)."""

    interaction_type: Literal["minigame"] = Field(
        default="minigame",
        description="Discriminator for interaction routing.",
    )
    minigame_id: str = Field(..., min_length=1, description="The minigame registry id.")
    status: Literal["completed", "failed", "aborted"]
    metrics: Dict[str, str | int | float | bool] = Field(
        default_factory=dict,
        description="Flat metrics map used for scoring/telemetry.",
    )
    minigame_specific_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deeply nested game-specific payload.",
    )
    triggered_hooks: List[str] = Field(
        default_factory=list,
        description="Narrative hook texts triggered in sequence.",
    )


class TurnRequest(BaseModel):
    """``POST /api/instances/{instance_id}/turn`` request body."""

    parent_turn_id: Optional[str] = Field(
        None,
        description="UUID of the previous turn (None for the first turn).",
    )
    user_input: Optional[str] = Field(
        None,
        min_length=1,
        description="The player's raw text input. Required unless interaction is provided.",
    )
    interaction: Optional[MinigameInteractionPayload] = Field(
        None,
        description="Structured interaction payload (e.g. minigame result).",
    )
    player_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Persisted player preferences (e.g. preferred LLM provider/model).",
    )
    request_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-request config overrides for this turn (highest precedence).",
    )

    @model_validator(mode="after")
    def _validate_one_of_user_input_or_interaction(self) -> "TurnRequest":
        has_user_input = bool(self.user_input)
        has_interaction = self.interaction is not None
        if has_user_input == has_interaction:
            raise ValueError("Provide exactly one of 'user_input' or 'interaction'.")
        return self


class TurnResponse(BaseModel):
    """``POST /api/instances/{instance_id}/turn`` response body."""

    turn_id: str
    narrator_response: str
    yare_delta: Dict[str, Any]

class TurnLogResponse(BaseModel):
    id: str
    instance_id: str
    turn_index: int
    actor: str
    input_text: str
    yare_delta: Any
    narrator_text: str
    parent_id: Optional[str]
    timestamp: Optional[datetime]


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


class CreateInstanceRequest(BaseModel):
    """``POST /api/instances`` request body."""

    version_id: str
    persona_id: str


class CreateInstanceResponse(BaseModel):
    """``POST /api/instances`` response body."""

    instance_id: str
    turn_id: Optional[str] = None

class GameInstanceResponse(BaseModel):
    id: str
    user_id: str
    persona_id: str
    version_id: str
    status: str
    created_at: Optional[datetime]
    last_played_at: Optional[datetime]

class UpdateGameInstanceRequest(BaseModel):
    status: Optional[str] = None




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

class UpdateGameSaveRequest(BaseModel):
    label: str


# ---------------------------------------------------------------------------
# §1.4 Load Game State (Hydration)
# ---------------------------------------------------------------------------


class HydratedStateResponse(BaseModel):
    """``GET /api/instances/{instance_id}/state`` response body."""

    bot_memory: Dict[str, Any]
    client_messages: List[Dict[str, str]]
    current_turn_id: Optional[str] = None
    last_user_input: Optional[str] = None
    last_parent_turn_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Cartridge CRUD schemas
# ---------------------------------------------------------------------------


class CreateCartridgeRequest(BaseModel):
    """``POST /api/cartridges`` request body."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    genre: str = Field(default="")
    visibility: str = Field(default="PUBLIC", description="PUBLIC or PRIVATE")

class UpdateCartridgeRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    genre: Optional[str] = None
    visibility: Optional[str] = Field(None, description="PUBLIC or PRIVATE")


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
    first_message: str
    checksum: str
    yare_js_src: Optional[str] = None
    published_at: Optional[datetime]
