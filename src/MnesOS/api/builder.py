"""
FastAPI router for the "I'm Feeling Lucky" Cartridge Generator.

[MnesOS-260525-09] Provides:
  POST /api/builder/generate — Invoke the multi-agent builder system to generate
  a complete 4-file cartridge from a text requirements prompt.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..builder.agents import BuilderOrchestrator, BuilderRequest, BuilderResult
from .deps import get_current_user, get_llm_clients

logger = logging.getLogger(__name__)

builder_router = APIRouter(prefix="/builder", tags=["builder"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Request body for cartridge generation."""
    requirements: str = Field(
        ...,
        min_length=1,
        description="Plain English requirements for the cartridge to generate.",
    )
    existing_content: Optional[Dict[str, str]] = Field(
        None,
        description="Optional existing cartridge files for iterative refinement.",
    )


class GenerateResponse(BaseModel):
    """Response body containing the generated cartridge files."""
    bot_lore: str
    first_message: str
    prompt_directives: str
    yare_spec: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@builder_router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate a cartridge from text requirements",
)
def generate_cartridge(
    body: GenerateRequest,
    user_id: str = Depends(get_current_user),
    llm_clients: Optional[Dict[str, Any]] = Depends(get_llm_clients),
) -> GenerateResponse:
    """Invoke the multi-agent builder to generate a complete 4-file cartridge.

    When ``existing_content`` is provided, the builder refines the existing
    cartridge rather than generating from scratch.
    """
    from ..llm import build_default_factory

    # Build a chat client for the builder
    factory = build_default_factory()
    llm = None
    if llm_clients:
        try:
            llm = factory.create_chat_client(
                provider="openrouter",
                api_key=llm_clients.get("openrouter_key", ""),
                model="google/gemini-2.0-flash-001",
            )
        except Exception as e:
            logger.warning(f"Failed to create LLM client for builder: {e}")

    if llm is None:
        # Dry-run mode: create a mock LLM that returns placeholder content
        llm = _create_placeholder_llm()

    request = BuilderRequest(
        requirements=body.requirements,
        existing_content=body.existing_content,
    )

    orchestrator = BuilderOrchestrator(llm=llm)
    result = orchestrator.generate(request)

    return GenerateResponse(
        bot_lore=result.bot_lore,
        first_message=result.first_message,
        prompt_directives=result.prompt_directives,
        yare_spec=result.yare_spec,
    )


def _create_placeholder_llm():
    """Create a placeholder LLM for dry-run/testing mode."""

    class _PlaceholderLLM:
        def invoke(self, prompt: str):
            class _Response:
                content = (
                    "# Generated World\n\n"
                    "A mysterious fantasy world filled with adventure.\n\n"
                    "## Characters\n"
                    "- The Hero: A brave adventurer\n"
                    "- The Villain: A dark sorcerer\n\n"
                    "---SPLIT---\n"
                    "<DIRECTIVES>\n"
                    "director: Guide the player through narrative choices\n"
                    "narrator: Describe scenes with vivid imagery\n"
                    "npc: Speak authentically for your character\n"
                    "</DIRECTIVES>\n"
                    "---SPLIT---\n"
                    "<FIRST_MESSAGE>\n"
                    "You awaken in a dimly lit chamber. Stone walls surround you.\n"
                    "</FIRST_MESSAGE>"
                )
            return _Response()

    return _PlaceholderLLM()
