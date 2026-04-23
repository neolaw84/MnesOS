"""
FastAPI router for GameInstance CRUD.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..storage import AbstractStorageComponent
from ..storage.models import GameInstance, Persona, GameStatus, TurnLog, TurnActor
from .deps import get_current_user, get_storage
from .schemas import (
    CreateInstanceRequest,
    CreateInstanceResponse,
    GameInstanceResponse,
    UpdateGameInstanceRequest,
)

logger = logging.getLogger(__name__)

instances_router = APIRouter(prefix="/instances", tags=["instances"])


def _instance_to_response(i: GameInstance) -> GameInstanceResponse:
    return GameInstanceResponse(
        id=i.id,
        user_id=i.user_id,
        persona_id=i.persona_id,
        version_id=i.version_id,
        status=i.status.value,
        created_at=i.created_at,
        last_played_at=i.last_played_at,
    )


@instances_router.post(
    "",
    response_model=CreateInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap a new game instance",
)
def create_instance(
    body: CreateInstanceRequest,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> CreateInstanceResponse:
    """Create a new game instance for the provided persona."""
    persona = storage.get_persona(body.persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    if persona.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this Persona")

    instance = GameInstance(
        user_id=user_id,
        persona_id=body.persona_id,
        version_id=body.version_id,
        status=GameStatus.ACTIVE,
    )
    created_instance = storage.create_game_instance(instance)

    turn_id = None
    version = storage.get_cartridge_version(body.version_id)
    if version and version.first_message:
        turn = TurnLog(
            instance_id=created_instance.id,
            turn_index=0,
            actor=TurnActor.SYSTEM,
            input_text="",
            yare_delta={},
            narrator_text=version.first_message,
            parent_id=None,
        )
        saved = storage.append_turn_log(turn)
        turn_id = saved.id

    return CreateInstanceResponse(instance_id=created_instance.id, turn_id=turn_id)


@instances_router.get(
    "",
    response_model=List[GameInstanceResponse],
    summary="List game instances for current user",
)
def list_instances(
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> List[GameInstanceResponse]:
    # SQLite3Store needs list_game_instances method or we can add it later if missing.
    # We will add it shortly.
    if hasattr(storage, "list_game_instances"):
        instances = storage.list_game_instances(user_id)
    else:
        raise HTTPException(status_code=501, detail="Storage engine does not support listing game instances.")
    return [_instance_to_response(i) for i in instances]


@instances_router.get(
    "/{instance_id}",
    response_model=GameInstanceResponse,
    summary="Get a specific game instance",
)
def get_instance(
    instance_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> GameInstanceResponse:
    instance = storage.get_game_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    if instance.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return _instance_to_response(instance)


@instances_router.put(
    "/{instance_id}",
    response_model=GameInstanceResponse,
    summary="Update game instance metadata",
)
def update_instance(
    instance_id: str,
    body: UpdateGameInstanceRequest,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> GameInstanceResponse:
    instance = storage.get_game_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    if instance.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if body.status is not None:
        try:
            instance.status = GameStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status")
            
    updated = storage.update_game_instance(instance)
    return _instance_to_response(updated)


@instances_router.delete(
    "/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a game instance",
)
def delete_instance(
    instance_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> None:
    instance = storage.get_game_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    if instance.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if hasattr(storage, "delete_game_instance"):
        storage.delete_game_instance(instance_id)
    else:
        raise HTTPException(status_code=501, detail="Storage engine does not support deleting instances.")
