"""
FastAPI router for UserAccount CRUD.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..storage import AbstractStorageComponent
from ..storage.models import UserAccount, UserRole
from .deps import get_current_user, get_storage
from .schemas import (
    CreateUserAccountRequest,
    UpdateUserAccountRequest,
    UserAccountResponse,
)

logger = logging.getLogger(__name__)

users_router = APIRouter(prefix="/users", tags=["users"])


def _user_to_response(u: UserAccount) -> UserAccountResponse:
    return UserAccountResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role.value,
        created_at=u.created_at,
    )


@users_router.post(
    "",
    response_model=UserAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def create_user(
    body: CreateUserAccountRequest,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> UserAccountResponse:
    """Create a new user."""
    user = UserAccount(
        username=body.username,
        email=body.email,
        password_hash=body.password,  # In a real app, hash this!
        role=UserRole(body.role),
    )
    created = storage.create_user(user)
    return _user_to_response(created)


@users_router.get(
    "/{user_id}",
    response_model=UserAccountResponse,
    summary="Get a specific user",
)
def get_user(
    user_id: str,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> UserAccountResponse:
    user = storage.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_response(user)


@users_router.put(
    "/{user_id}",
    response_model=UserAccountResponse,
    summary="Update a user",
)
def update_user(
    user_id: str,
    body: UpdateUserAccountRequest,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> UserAccountResponse:
    user = storage.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    if body.username is not None:
        user.username = body.username
    if body.email is not None:
        user.email = body.email
    if body.role is not None:
        user.role = UserRole(body.role)
        
    updated = storage.update_user(user)
    return _user_to_response(updated)


@users_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
)
def delete_user(
    user_id: str,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> None:
    user = storage.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    storage.delete_user(user_id)
