"""
FastAPI application entry point for MnesOS Alpha.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §1.

Run locally (dev — Vite handles the frontend)::

    uvicorn MnesOS.api.app:app --reload

Run in production (unified — FastAPI serves the built React SPA)::

    MNESOS_STATIC_DIR=/path/to/web-client/dist uvicorn MnesOS.api.app:app
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import logging

logging.basicConfig(level=logging.DEBUG)

from .cartridges import cartridges_router
from .minigames import minigames_router
from .routes import router
from .users import users_router
from .personas import personas_router
from .instances import instances_router
from .saves import saves_router
from .turns import turns_router

app = FastAPI(
    title="MnesOS Alpha API",
    description=(
        "Stateless game engine API for the MnesOS YARE RPG system. "
        "Tech-native Alpha — bring your own LLM key."
    ),
    version="0.5.0-alpha",
)

app.include_router(router, prefix="/api")
app.include_router(cartridges_router, prefix="/api")
app.include_router(minigames_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(personas_router, prefix="/api")
app.include_router(instances_router, prefix="/api")
app.include_router(saves_router, prefix="/api")
app.include_router(turns_router, prefix="/api")

# ── Static SPA serving ────────────────────────────────────────────────────────
# Priority order for locating the built frontend:
#   1. MNESOS_STATIC_DIR env-var (set by release / CI / Docker)
#   2. <package_dir>/static/  (bundled inside the wheel via package-data)
_static_dir: Path | None = None

_env_static = os.environ.get("MNESOS_STATIC_DIR", "").strip()
if _env_static:
    _candidate = Path(_env_static)
    if _candidate.is_dir():
        _static_dir = _candidate

if _static_dir is None:
    _bundled = Path(__file__).parent.parent / "static"
    if _bundled.is_dir():
        _static_dir = _bundled

if _static_dir is not None:
    # Serve assets (JS/CSS/images) from the root mount; this must come AFTER
    # the API routers so that /api/* is never shadowed.
    app.mount(
        "/assets",
        StaticFiles(directory=_static_dir / "assets"),
        name="spa-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """Return index.html for all non-API routes so client-side routing works."""
        index = _static_dir / "index.html"
        return FileResponse(index)
