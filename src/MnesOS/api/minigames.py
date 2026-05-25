"""
FastAPI router for minigame registry discovery.

Endpoints:
  GET /api/minigames — list all registered minigames with their schemas
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)

minigames_router = APIRouter(prefix="/minigames", tags=["minigames"])

# Path to the compiled minigame schema (generated at build time)
_SCHEMA_PATHS = [
    # In development: docs/minigames.schema.json (always present)
    Path(__file__).resolve().parents[3] / "docs" / "minigames.schema.json",
    # In production: bundled with static assets
    Path(__file__).resolve().parents[1] / "static" / "schemas" / "minigames.json",
]


def _load_minigame_schema() -> List[Dict[str, Any]]:
    """Load the aggregated minigame schema from disk."""
    for schema_path in _SCHEMA_PATHS:
        if schema_path.exists():
            try:
                with schema_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("minigames", [])
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load minigame schema from %s: %s", schema_path, e)
                continue
    logger.warning("No minigame schema file found at any known path.")
    return []


@minigames_router.get(
    "",
    response_model=List[Dict[str, Any]],
    summary="List all registered minigames with their schemas",
)
def list_minigames() -> List[Dict[str, Any]]:
    """Return minigame configurations from the compiled registry."""
    return _load_minigame_schema()
