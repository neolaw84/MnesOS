"""
Tests for [MnesOS-260507-09] Builder Backend – Architect & Specialist Multi-Agent System.

TDD: Tests define expected behavior of the builder agent orchestrator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from MnesOS.builder.agents import (
    BuilderOrchestrator,
    BuilderRequest,
    BuilderResult,
    SpecialistRole,
)


class TestBuilderRequest:
    """Validate the input schema for the builder."""

    def test_request_requires_requirements_text(self):
        req = BuilderRequest(requirements="Create a dungeon crawler RPG")
        assert req.requirements == "Create a dungeon crawler RPG"

    def test_request_accepts_existing_content(self):
        req = BuilderRequest(
            requirements="Make it harder",
            existing_content={
                "bot_lore": "# Old Lore",
                "first_message": "Welcome",
                "prompt_directives": "director: Be strict",
                "yare_spec": "state_schema: {}",
            },
        )
        assert req.existing_content["bot_lore"] == "# Old Lore"

    def test_request_defaults_existing_to_none(self):
        req = BuilderRequest(requirements="Create a game")
        assert req.existing_content is None


class TestBuilderResult:
    """Validate the output schema of the builder."""

    def test_result_contains_four_files(self):
        result = BuilderResult(
            bot_lore="# World",
            first_message="You awake...",
            prompt_directives="director: strict narrator",
            yare_spec="state_schema:\n  player:\n    hp: {type: int, default: 100}",
        )
        assert result.bot_lore == "# World"
        assert result.first_message == "You awake..."
        assert "director" in result.prompt_directives
        assert "state_schema" in result.yare_spec


class TestBuilderOrchestrator:
    """Test the orchestrator's coordination logic."""

    def test_orchestrator_instantiation(self):
        """Orchestrator can be created with an LLM client."""
        mock_llm = MagicMock()
        orch = BuilderOrchestrator(llm=mock_llm)
        assert orch is not None

    def test_orchestrator_has_specialist_roles(self):
        """The orchestrator defines standard specialist roles."""
        assert SpecialistRole.LORE_MASTER is not None
        assert SpecialistRole.MECHANIC is not None
        assert SpecialistRole.PROMPTER is not None
        assert SpecialistRole.ARCHITECT is not None

    def test_generate_returns_builder_result(self):
        """generate() should return a complete BuilderResult."""
        mock_llm = MagicMock()
        # Mock the LLM to return valid content
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="Generated content"))

        orch = BuilderOrchestrator(llm=mock_llm)
        request = BuilderRequest(requirements="Create a simple adventure game")

        result = orch.generate(request)
        assert isinstance(result, BuilderResult)
        assert result.bot_lore != ""
        assert result.first_message != ""
        assert result.prompt_directives != ""
        assert result.yare_spec != ""

    def test_generate_iterative_uses_existing_content(self):
        """When existing_content is provided, the orchestrator uses it as context."""
        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="Updated content"))

        orch = BuilderOrchestrator(llm=mock_llm)
        request = BuilderRequest(
            requirements="Make combat harder",
            existing_content={
                "bot_lore": "# Original Lore",
                "first_message": "Hello",
                "prompt_directives": "director: nice",
                "yare_spec": "state_schema: {}",
            },
        )

        result = orch.generate(request)
        assert isinstance(result, BuilderResult)
