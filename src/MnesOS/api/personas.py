"""
FastAPI router for Persona CRUD.
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ..storage import AbstractStorageComponent
from ..storage.models import Persona
from .deps import get_current_user, get_storage
from .schemas import (
    CreatePersonaRequest,
    UpdatePersonaRequest,
    PersonaResponse,
)

logger = logging.getLogger(__name__)

personas_router = APIRouter(prefix="/personas", tags=["personas"])


def _persona_to_response(p: Persona) -> PersonaResponse:
    return PersonaResponse(
        id=p.id,
        user_id=p.user_id,
        name=p.name,
        pronoun_sub=p.pronoun_sub,
        pronoun_obj=p.pronoun_obj,
        pronoun_poss=p.pronoun_poss,
        pronoun_poss_obj=p.pronoun_poss_obj,
        appearance=p.appearance,
        background=p.background,
        personality=p.personality,
        created_at=p.created_at,
    )


@personas_router.post(
    "",
    response_model=PersonaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new persona",
)
def create_persona(
    body: CreatePersonaRequest,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> PersonaResponse:
    persona = Persona(
        user_id=user_id,
        name=body.name,
        pronoun_sub=body.pronoun_sub,
        pronoun_obj=body.pronoun_obj,
        pronoun_poss=body.pronoun_poss,
        pronoun_poss_obj=body.pronoun_poss_obj,
        appearance=body.appearance,
        background=body.background,
        personality=body.personality,
    )
    created = storage.create_persona(persona)
    return _persona_to_response(created)


@personas_router.get(
    "",
    response_model=list[PersonaResponse],
    summary="List all personas for the current user",
)
def list_personas(
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> list[PersonaResponse]:
    if hasattr(storage, "list_personas"):
        personas = storage.list_personas(user_id)
        return [_persona_to_response(p) for p in personas]
    else:
        raise HTTPException(status_code=501, detail="Storage engine does not support listing personas.")


@personas_router.get(
    "/{persona_id}",
    response_model=PersonaResponse,
    summary="Get a specific persona",
)
def get_persona(
    persona_id: str,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> PersonaResponse:
    persona = storage.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return _persona_to_response(persona)


@personas_router.put(
    "/{persona_id}",
    response_model=PersonaResponse,
    summary="Update a persona",
)
def update_persona(
    persona_id: str,
    body: UpdatePersonaRequest,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> PersonaResponse:
    persona = storage.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    if persona.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if body.name is not None:
        persona.name = body.name
    if body.pronoun_sub is not None:
        persona.pronoun_sub = body.pronoun_sub
    if body.pronoun_obj is not None:
        persona.pronoun_obj = body.pronoun_obj
    if body.pronoun_poss is not None:
        persona.pronoun_poss = body.pronoun_poss
    if body.pronoun_poss_obj is not None:
        persona.pronoun_poss_obj = body.pronoun_poss_obj
    if body.appearance is not None:
        persona.appearance = body.appearance
    if body.background is not None:
        persona.background = body.background
    if body.personality is not None:
        persona.personality = body.personality
        
    updated = storage.update_persona(persona)
    return _persona_to_response(updated)


@personas_router.delete(
    "/{persona_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a persona",
)
def delete_persona(
    persona_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> None:
    persona = storage.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    if persona.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        storage.delete_persona(persona_id)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this persona because it is currently being used by one or more game instances."
        )
