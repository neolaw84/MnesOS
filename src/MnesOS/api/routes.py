"""
FastAPI route definitions for MnesOS Alpha.

Endpoints aligned with ``docs/design/0005-interfaces-and-contracts.md`` §1:
  - ``POST /api/instances/{instance_id}/turn``   — §1.1 Process Turn
  - ``POST /api/instances/{instance_id}/inject``  — §1.2 Inject State
  - ``POST /api/instances/{instance_id}/saves``   — §1.3 Game Saves
  - ``GET  /api/instances/{instance_id}/state``   — §1.4 Load Game State
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..orchestrator import Orchestrator
from ..storage import (
    AbstractStorageComponent,
    StateHydrator,
    TurnLog,
    TurnActor,
    GameSave,
)
from .deps import (
    get_current_user,
    get_llm_clients,
    get_storage,
    verify_instance_ownership,
)
from .schemas import (
    CreateSaveRequest,
    CreateSaveResponse,
    GameSaveItem,
    HydratedStateResponse,
    InjectRequest,
    InjectResponse,
    TurnRequest,
    TurnResponse,
)

router = APIRouter()

# Default cartridge directory — configurable via env var.
_CARTRIDGE_DIR = os.environ.get("MNESOS_CARTRIDGE_DIR", "cartridges/generic-rpg")


def _get_orchestrator(
    storage: AbstractStorageComponent = Depends(get_storage),
) -> Orchestrator:
    """Build a stateless Orchestrator (no LLMs at build time — BYOK via config)."""
    return Orchestrator(cartridge_dir=_CARTRIDGE_DIR, storage=storage)


# ---------------------------------------------------------------------------
# §1.1  POST /instances/{instance_id}/turn
# ---------------------------------------------------------------------------


@router.post(
    "/instances/{instance_id}/turn",
    response_model=TurnResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a gameplay turn",
)
def process_turn(
    body: TurnRequest,
    instance_id: str = Depends(verify_instance_ownership),
    llm_clients: Optional[Dict[str, Any]] = Depends(get_llm_clients),
    storage: AbstractStorageComponent = Depends(get_storage),
    orch: Orchestrator = Depends(_get_orchestrator),
) -> TurnResponse:
    """Submit a user action, extending the timeline from a specific node."""
    # 1. Invoke orchestrator (stateless — no DB write)
    result = orch.process_turn(
        body.user_input,
        parent_turn_id=body.parent_turn_id,
        llm_clients=llm_clients,
    )

    # 2. Persist TurnLog (API route responsibility per 0005 §3.2)
    lineage = (
        storage.get_turn_lineage(body.parent_turn_id)
        if body.parent_turn_id
        else []
    )
    turn = TurnLog(
        instance_id=instance_id,
        turn_index=len(lineage),
        actor=TurnActor.PLAYER,
        input_text=body.user_input,
        yare_delta=result["yare_delta"],
        narrator_text=result["narrator_text"],
        parent_id=body.parent_turn_id,
    )
    saved = storage.append_turn_log(turn)

    return TurnResponse(
        turn_id=saved.id,
        narrator_response=result["narrator_text"],
        yare_delta=result["yare_delta"],
    )


# ---------------------------------------------------------------------------
# §1.2  POST /instances/{instance_id}/inject
# ---------------------------------------------------------------------------


@router.post(
    "/instances/{instance_id}/inject",
    response_model=InjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Inject a state mutation (authorized cheating)",
)
def inject_state(
    body: InjectRequest,
    instance_id: str = Depends(verify_instance_ownership),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> InjectResponse:
    """Append a SYSTEM turn with a raw yare_delta payload."""
    lineage = (
        storage.get_turn_lineage(body.parent_turn_id)
        if body.parent_turn_id
        else []
    )
    turn = TurnLog(
        instance_id=instance_id,
        turn_index=len(lineage),
        actor=TurnActor.SYSTEM,
        input_text="",
        yare_delta=body.yare_delta,
        narrator_text="",
        parent_id=body.parent_turn_id,
    )
    saved = storage.append_turn_log(turn)
    return InjectResponse(turn_id=saved.id)


# ---------------------------------------------------------------------------
# §1.3  POST /instances/{instance_id}/saves
# ---------------------------------------------------------------------------


@router.post(
    "/instances/{instance_id}/saves",
    response_model=CreateSaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a save bookmark",
)
def create_save(
    body: CreateSaveRequest,
    instance_id: str = Depends(verify_instance_ownership),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> CreateSaveResponse:
    """Create a labeled bookmark pointing to a specific TurnLog node."""
    save = GameSave(
        instance_id=instance_id,
        turn_log_id=body.turn_log_id,
        label=body.label,
    )
    saved = storage.create_game_save(save)
    return CreateSaveResponse(
        save_id=saved.id,
        created_at=saved.created_at,
    )


@router.get(
    "/instances/{instance_id}/saves",
    response_model=List[GameSaveItem],
    summary="List save bookmarks",
)
def list_saves(
    instance_id: str = Depends(verify_instance_ownership),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> List[GameSaveItem]:
    """Return all save bookmarks for the given game instance."""
    saves = storage.list_game_saves(instance_id)
    return [
        GameSaveItem(
            id=s.id,
            instance_id=s.instance_id,
            turn_log_id=s.turn_log_id,
            label=s.label,
            created_at=s.created_at,
        )
        for s in saves
    ]


# ---------------------------------------------------------------------------
# §1.4  GET /instances/{instance_id}/state
# ---------------------------------------------------------------------------


@router.get(
    "/instances/{instance_id}/state",
    response_model=HydratedStateResponse,
    summary="Load hydrated game state",
)
def get_game_state(
    instance_id: str = Depends(verify_instance_ownership),
    turn_log_id: Optional[str] = Query(
        None,
        description="UUID of the turn to hydrate up to. If omitted, returns initial state.",
    ),
    storage: AbstractStorageComponent = Depends(get_storage),
    orch: Orchestrator = Depends(_get_orchestrator),
) -> HydratedStateResponse:
    """Reconstruct and return the fully hydrated game state."""
    if turn_log_id:
        lineage = storage.get_turn_lineage(turn_log_id)
    else:
        lineage = []

    state = StateHydrator.hydrate_state(lineage, orch.cartridge.initial_state)
    return HydratedStateResponse(
        bot_memory=state["bot_memory"],
        client_messages=state["client_messages"],
    )
