"""
FastAPI router for GameSave CRUD.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..storage import AbstractStorageComponent
from ..storage.models import GameSave
from .deps import get_current_user, get_storage, verify_instance_ownership
from .schemas import (
    CreateSaveRequest,
    CreateSaveResponse,
    GameSaveItem,
    UpdateGameSaveRequest,
)

logger = logging.getLogger(__name__)

saves_router = APIRouter(prefix="/saves", tags=["saves"])

def _save_to_response(s: GameSave) -> GameSaveItem:
    return GameSaveItem(
        id=s.id,
        instance_id=s.instance_id,
        turn_log_id=s.turn_log_id,
        label=s.label,
        created_at=s.created_at,
    )

@saves_router.get(
    "/{save_id}",
    response_model=GameSaveItem,
    summary="Get a specific game save",
)
def get_save(
    save_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> GameSaveItem:
    save = storage.get_game_save(save_id)
    if save is None:
        raise HTTPException(status_code=404, detail="Save not found")
    
    # Verify ownership
    instance = storage.get_game_instance(save.instance_id)
    if not instance or instance.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    return _save_to_response(save)

@saves_router.put(
    "/{save_id}",
    response_model=GameSaveItem,
    summary="Update a game save label",
)
def update_save(
    save_id: str,
    body: UpdateGameSaveRequest,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> GameSaveItem:
    save = storage.get_game_save(save_id)
    if save is None:
        raise HTTPException(status_code=404, detail="Save not found")
        
    instance = storage.get_game_instance(save.instance_id)
    if not instance or instance.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    save.label = body.label
    # need update_game_save
    if hasattr(storage, "update_game_save"):
        updated = storage.update_game_save(save)
        return _save_to_response(updated)
    else:
        raise HTTPException(status_code=501, detail="Storage engine does not support updating saves.")

@saves_router.delete(
    "/{save_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a game save",
)
def delete_save(
    save_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> None:
    save = storage.get_game_save(save_id)
    if save is None:
        raise HTTPException(status_code=404, detail="Save not found")
        
    instance = storage.get_game_instance(save.instance_id)
    if not instance or instance.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    storage.delete_game_save(save_id)
