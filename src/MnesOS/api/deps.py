"""
FastAPI dependency-injection aspects for MnesOS Alpha.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §5:
  - **get_current_user** — mock basic-auth for Alpha.
  - **verify_instance_ownership** — ensure the requesting user owns the game.
  - **get_llm_clients** — BYOK: read the ``X-OpenRouter-Key`` header and
    instantiate per-request LangChain models.
  - **get_storage** — provide the storage singleton.
  - **get_orchestrator** — provide an Orchestrator bound to a cartridge.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status

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
        db_path = os.environ.get("MNESOS_DB_PATH", "mnesos.db")
        _storage_instance = SQLite3PhysicalComponent(db_path=db_path)
        _storage_instance.initialize()
    return _storage_instance


# ---------------------------------------------------------------------------
# Authentication — mock basic-auth for Alpha
# ---------------------------------------------------------------------------


def get_current_user(
    x_user_id: str = Header(
        ...,
        description="Mock user ID header (Alpha auth).",
    ),
) -> str:
    """Extract and return the current user ID from the request header.

    In the Alpha release this is a simple header-based mock.  Replace
    with JWT / OAuth in production.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header.",
        )
    return x_user_id


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

    Uses ``langchain_openai.ChatOpenAI`` pointed at the OpenRouter base
    URL so any model available on OpenRouter can be used.
    """
    if not x_openrouter_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "langchain_openai is not installed. "
                "Install it to enable BYOK LLM support."
            ),
        )

    base_url = os.environ.get(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    model_name = os.environ.get("MNESOS_DEFAULT_MODEL", "openai/gpt-4o-mini")

    director = ChatOpenAI(
        model=model_name, api_key=x_openrouter_key,
        base_url=base_url, temperature=0,
    )
    narrator = ChatOpenAI(
        model=model_name, api_key=x_openrouter_key,
        base_url=base_url, temperature=0.8,
    )
    npc = ChatOpenAI(
        model=model_name, api_key=x_openrouter_key,
        base_url=base_url, temperature=0.5,
    )
    return {"director": director, "narrator": narrator, "npc": npc}
