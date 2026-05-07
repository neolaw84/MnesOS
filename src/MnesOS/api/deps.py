"""
FastAPI dependency-injection aspects for MnesOS Alpha.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §5:
  - **get_current_user** — resolve identity via :class:`~MnesOS.auth.AuthFactory`.
  - **verify_instance_ownership** — ensure the requesting user owns the game.
  - **get_llm_clients** — BYOK: read the ``X-OpenRouter-Key`` header and
    instantiate per-request LangChain models via :class:`~MnesOS.llm.LLMFactory`.
  - **get_storage** — provide the storage singleton.
  - **get_orchestrator** — provide an Orchestrator bound to a cartridge.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from ..auth import AuthContext, AuthFactory
from ..config import LLMRoleConfig
from ..llm import build_default_factory
from ..storage import (
    AbstractStorageComponent,
    SQLite3PhysicalComponent,
)

# Application-wide LLMFactory instance — populated with all built-in providers.
_llm_factory = build_default_factory()

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
    except (ValueError, Exception) as exc:
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


def get_llm_clients(
    x_openrouter_key: Optional[str] = Header(
        None,
        description="OpenRouter API key for BYOK. Optional.",
    ),
) -> Optional[Dict[str, Any]]:
    """Instantiate per-request LangChain chat models using the caller's key.

    If no key is provided, returns ``None`` — the graph runs in dry-run
    mode (no LLM calls).

    Delegates to the application-wide :class:`~MnesOS.llm.LLMFactory` so
    that the model instantiation logic is centralised in one place and any
    provider can be swapped without touching this function.
    """
    if not x_openrouter_key:
        return None

    model_name = os.environ.get("MNESOS_DEFAULT_MODEL", "google/gemini-2.5-flash-lite")
    keys = {"openrouter_key": x_openrouter_key}

    try:
        director = _llm_factory.create_chat_client(
            LLMRoleConfig(provider="openrouter", model_name=model_name, temperature=0.0),
            keys,
        )
        narrator = _llm_factory.create_chat_client(
            LLMRoleConfig(provider="openrouter", model_name=model_name, temperature=0.8),
            keys,
        )
        npc = _llm_factory.create_chat_client(
            LLMRoleConfig(provider="openrouter", model_name=model_name, temperature=0.5),
            keys,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc

    return {"director": director, "narrator": narrator, "npc": npc}
