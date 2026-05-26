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
    BuilderState,
    build_builder_graph,
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


class TestBuilderGraphTDD:
    """TDD tests for the new LangGraph-based builder."""

    def test_graph_compilation(self):
        """Verify the builder graph can be built and compiled correctly."""
        mock_llm = MagicMock()
        graph = build_builder_graph(mock_llm)
        assert graph is not None
        # Verify it has the expected nodes
        node_names = [n for n in graph.nodes]
        assert "architect" in node_names
        assert "lore_master" in node_names
        assert "mechanic" in node_names
        assert "prompter" in node_names
        assert "validator" in node_names

    def test_prompt_directive_compliance(self):
        """Verify final prompt_directives use bot_memory and NOT state."""
        mock_llm = MagicMock()
        orch = BuilderOrchestrator(llm=mock_llm)
        request = BuilderRequest(requirements="Cyberpunk detective")
        
        # We'll mock llm.invoke to return content that includes bot_memory
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="director: use bot_memory[hp]\n---SPLIT---\nHello"))
        
        result = orch.generate(request)
        assert "bot_memory" in result.prompt_directives
        assert "state." not in result.prompt_directives

    def test_yare_dice_compliance(self):
        """Verify yare_spec uses @ roll(1d20) without quotes."""
        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="@ roll(1d20)"))
        orch = BuilderOrchestrator(llm=mock_llm)
        request = BuilderRequest(requirements="Combat with dice")
        
        result = orch.generate(request)
        assert "@ roll(" in result.yare_spec
        assert "@ roll('" not in result.yare_spec
        assert "@ roll(\"" not in result.yare_spec

    def test_yare_compiler_validation_retry(self):
        """Verify retry logic works when CartridgeLoader fails."""
        mock_llm = MagicMock()
        
        # 'roll' is not a valid action name, it's a function inside expressions.
        # This will fail the _validate_steps action check.
        invalid_yare = "events:\n  attack:\n    steps:\n      - action: roll\n        var: state.damage\n        value: 10"
        
        # This is valid: uses 'set' action and correct "@ roll(1d6)" syntax (quoted).
        valid_yare = "events:\n  attack:\n    steps:\n      - action: set\n        var: state.damage\n        value: \"@ roll(1d6)\""
        
        # Mock responses for the graph execution
        call_count = 0
        def side_effect(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1: return MagicMock(content="Architect R1")
            if call_count == 2: return MagicMock(content="# Lore R1")
            if call_count == 3: return MagicMock(content=invalid_yare)
            if call_count == 4: return MagicMock(content="director: x1\n---SPLIT---\ny1")
            if call_count == 5: return MagicMock(content="Architect R2")
            if call_count == 6: return MagicMock(content="# Lore R2")
            if call_count == 7: return MagicMock(content=valid_yare)
            if call_count == 8: return MagicMock(content="director: x2\n---SPLIT---\ny2")
            return MagicMock(content=f"Extra Call {call_count}")

        mock_llm.invoke.side_effect = side_effect
        
        orch = BuilderOrchestrator(llm=mock_llm)
        request = BuilderRequest(requirements="Test retry")
        
        result = orch.generate(request)
        
        # Verify both final output AND transition signals
        assert "@ roll(1d6)" in result.yare_spec
        assert "x2" in result.prompt_directives
        assert "y2" in result.first_message
        
        # Check call count: 4 nodes * 2 iterations = 8 calls
        assert call_count >= 8
