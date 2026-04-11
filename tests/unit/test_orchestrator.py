"""
Unit tests for orchestrator.py — structural and SRP/DIP compliance tests.

These tests verify the Orchestrator's structure, initial state, and that it
properly delegates to the build_graph factory. No full graph invocation occurs.
"""

import copy
import pytest
from unittest.mock import MagicMock, patch

from MnesOS.orchestrator import Orchestrator, _RETRY_SYSTEM_NOTE


# CWD-relative path — pytest is always invoked from the project root.
CARTRIDGE_DIR = "cartridges/generic-rpg"


# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------

class TestOrchestratorInit:
    def test_loads_cartridge(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        assert orch.cartridge is not None
        assert orch.cartridge.yare_config
        assert orch.cartridge.lore_path

    def test_initial_state_has_all_keys(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        state = orch.state
        for key in (
            "client_messages",
            "agent_messages",
            "bot_memory",
            "bot_memory_staging",
            "yare_config",
            "prompt_directives",
            "lore_path",
            "system_notes",
            "retrieved_lore",
            "iteration_count",
            "turn_phase",
        ):
            assert key in state, f"Missing key: {key}"

    def test_initial_client_messages_empty(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        assert orch.state["client_messages"] == []

    def test_bot_memory_seeded_from_cartridge(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        assert "player" in orch.state["bot_memory"]

    def test_invalid_cartridge_raises(self):
        with pytest.raises(FileNotFoundError):
            Orchestrator("nonexistent/path/to/cartridge")

    def test_compiled_graph_has_expected_nodes(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        node_names = set(orch._app.get_graph().nodes.keys())
        for expected in ("ResetAgentMessages", "Lore", "CycleTick", "Director",
                         "Narrator", "CleanupAgentMessages"):
            assert expected in node_names, f"Missing node: {expected}"
        assert "NPC_Brain" not in node_names, "NPC_Brain should not exist in monolithic mode"


# ---------------------------------------------------------------------------
# SRP / DIP compliance — Orchestrator must delegate graph building
# ---------------------------------------------------------------------------

class TestOrchestratorDelegatesGraphBuilding:
    """
    SRP: Orchestrator must NOT contain graph-assembly logic.
    DIP: Orchestrator must depend on the build_graph factory abstraction.
    """

    def test_orchestrator_calls_build_graph_factory(self):
        with patch("MnesOS.orchestrator.build_graph") as mock_bg:
            mock_bg.return_value = MagicMock()
            Orchestrator(CARTRIDGE_DIR)
            mock_bg.assert_called_once()

    def test_orchestrator_passes_yare_config_to_build_graph(self):
        with patch("MnesOS.orchestrator.build_graph") as mock_bg:
            mock_bg.return_value = MagicMock()
            Orchestrator(CARTRIDGE_DIR)
            call_kwargs = mock_bg.call_args
            all_args = list(call_kwargs.args) + list(call_kwargs.kwargs.values())
            assert any(
                isinstance(a, dict) and "state_schema" in a for a in all_args
            ), "yare_config (dict with state_schema) was not passed to build_graph"

    def test_orchestrator_passes_llms_to_build_graph(self):
        fake_director = MagicMock()
        fake_narrator = MagicMock()
        with patch("MnesOS.orchestrator.build_graph") as mock_bg:
            mock_bg.return_value = MagicMock()
            Orchestrator(
                CARTRIDGE_DIR,
                llm_director=fake_director,
                llm_narrator=fake_narrator,
            )
            call_kwargs = mock_bg.call_args
            all_args = list(call_kwargs.args) + list(call_kwargs.kwargs.values())
            assert fake_director in all_args, "llm_director not forwarded to build_graph"
            assert fake_narrator in all_args, "llm_narrator not forwarded to build_graph"

    def test_build_graph_importable_from_orchestrator_module(self):
        import MnesOS.orchestrator as orch_module
        assert hasattr(orch_module, "build_graph"), (
            "build_graph is not imported/exposed in orchestrator.py"
        )
