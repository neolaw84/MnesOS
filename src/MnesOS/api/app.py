"""
FastAPI application entry point for MnesOS Alpha.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §1.

Run locally::

    uvicorn MnesOS.api.app:app --reload
"""

from fastapi import FastAPI

from .cartridges import cartridges_router
from .routes import router

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
