"""
FastAPI application entry point for MnesOS Alpha.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §1.

Run locally::

    uvicorn MnesOS.api.app:app --reload
"""

from fastapi import FastAPI
import logging

logging.basicConfig(level=logging.DEBUG)

from .cartridges import cartridges_router
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
app.include_router(users_router, prefix="/api")
app.include_router(personas_router, prefix="/api")
app.include_router(instances_router, prefix="/api")
app.include_router(saves_router, prefix="/api")
app.include_router(turns_router, prefix="/api")
