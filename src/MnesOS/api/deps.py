"""
FastAPI dependency-injection aspects for MnesOS Alpha.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §5:
  - **get_current_user** — resolve identity via :class:`~MnesOS.auth.AuthFactory`.
  - **verify_instance_ownership** — ensure the requesting user owns the game.
  - **get_llm_clients** — BYOK: extract raw provider keys via
    :class:`~MnesOS.auth.LLMAuthValidator`; LangChain clients are built later
    inside the graph nodes via :class:`~MnesOS.llm.LLMFactory`.
  - **get_storage** — provide the storage singleton.
  - **get_orchestrator** — provide an Orchestrator bound to a cartridge.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from ..auth import AuthContext, AuthFactory, LLMAuthValidator
from ..storage import (
    AbstractStorageComponent,
    SQLite3PhysicalComponent,
)

# ---------------------------------------------------------------------------
# Storage singleton
# ---------------------------------------------------------------------------

_storage_instance: Optional[AbstractStorageComponent] = None


def get_storage() -> AbstractStorageComponent:
    """Return the application-wide storage component.

    On first call the SQLite3 store is created and initialized.
    Override this dependency in tests to inject a mock/in-memory store.
    """
    global _storage_instance
    if _storage_instance is None:
        db_path = os.environ.get("MNESOS_DB_PATH", "artifacts/mnesos.db")
        _storage_instance = SQLite3PhysicalComponent(db_path=db_path)
        _storage_instance.initialize()
    return _storage_instance


# ---------------------------------------------------------------------------
# Authentication — mock basic-auth for Alpha
# ---------------------------------------------------------------------------


def get_current_user(request: Request) -> str:
    """Resolve the current user identity via :class:`~MnesOS.auth.AuthFactory`.

    The ``X-Provider`` header (default: ``openrouter``) selects the auth strategy.
    The resolved :class:`~MnesOS.auth.AuthContext` ``user_id`` is returned so
    downstream code can use it without knowing which provider was active.

    Raises HTTP 401 if identity cannot be resolved.
    """
    headers = dict(request.headers)
    try:
        provider = AuthFactory.create(headers)
        ctx: AuthContext = provider.resolve_identity(headers)
    except ValueError as exc:
        # Fall back to legacy X-User-Id header for backward compatibility
        x_user_id = request.headers.get("x-user-id", "").strip()
        if x_user_id:
            return x_user_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {exc}",
        ) from exc
    return ctx.user_id


# ---------------------------------------------------------------------------
# Authorization — verify ownership
# ---------------------------------------------------------------------------


def verify_instance_ownership(
    instance_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> str:
    """Ensure the requesting user owns the game instance.

    Returns *instance_id* on success so downstream code can use it.
    Raises 403 if the user does not own the instance, 404 if it
    does not exist.
    """
    instance = storage.get_game_instance(instance_id)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game instance {instance_id!r} not found.",
        )
    if instance.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this game instance.",
        )
    return instance_id


# ---------------------------------------------------------------------------
# BYOK — bring-your-own-key LLM client factory
# ---------------------------------------------------------------------------


def get_llm_clients(request: Request) -> Optional[Dict[str, Any]]:
    """Extract per-request LLM provider keys for BYOK.

    Returns a raw keys dictionary (e.g. ``{"openrouter_key": "sk-…"}``), or
    ``None`` when no credentials are present (dry-run mode).

    Key extraction is delegated to the provider's
    :class:`~MnesOS.auth.LLMAuthValidator` interface, keeping provider-specific
    header names out of this function.  The :class:`~MnesOS.llm.LLMFactory`
    is then invoked later by the orchestrator/graph nodes using the
    ``MnesOSRuntimeConfig`` to build the actual LangChain clients.
    """
    headers = dict(request.headers)
    try:
        provider = AuthFactory.create(headers)
    except ValueError:
        return None

    if not isinstance(provider, LLMAuthValidator):
        return None

    try:
        return provider.validate_provider_keys(headers)
    except ValueError:
        return None
