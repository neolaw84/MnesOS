"""
FastAPI router for TurnLog reading operations.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..storage import AbstractStorageComponent
from ..storage.models import TurnLog
from .deps import get_current_user, get_storage
from .schemas import TurnLogResponse

logger = logging.getLogger(__name__)

turns_router = APIRouter(prefix="/turns", tags=["turns"])

def _turn_to_response(t: TurnLog) -> TurnLogResponse:
    return TurnLogResponse(
        id=t.id,
        instance_id=t.instance_id,
        turn_index=t.turn_index,
        actor=t.actor.value,
        input_text=t.input_text,
        yare_delta=t.yare_delta,
        narrator_text=t.narrator_text,
        parent_id=t.parent_id,
        timestamp=t.timestamp,
    )

@turns_router.get(
    "/{turn_id}",
    response_model=TurnLogResponse,
    summary="Get a specific turn log",
)
def get_turn(
    turn_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> TurnLogResponse:
    # We don't have get_turn_log by ID in interface currently.
    if hasattr(storage, "get_turn_log"):
        turn = storage.get_turn_log(turn_id)
        if turn is None:
            raise HTTPException(status_code=404, detail="Turn not found")
            
        instance = storage.get_game_instance(turn.instance_id)
        if not instance or instance.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        return _turn_to_response(turn)
    else:
        raise HTTPException(status_code=501, detail="Storage engine does not support fetching specific turns.")

@turns_router.delete(
    "/{turn_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a turn log",
)
def delete_turn(
    turn_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> None:
    if hasattr(storage, "get_turn_log") and hasattr(storage, "delete_turn_log"):
        turn = storage.get_turn_log(turn_id)
        if turn is None:
            raise HTTPException(status_code=404, detail="Turn not found")
            
        instance = storage.get_game_instance(turn.instance_id)
        if not instance or instance.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        storage.delete_turn_log(turn_id)
    else:
        raise HTTPException(status_code=501, detail="Storage engine does not support deleting specific turns.")
