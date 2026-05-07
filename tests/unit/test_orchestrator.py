"""
Unit tests for orchestrator.py — structural and SRP/DIP compliance tests.

These tests verify the Orchestrator's structure, initial state, and that it
properly delegates to the build_graph factory. No full graph invocation occurs.
"""

import copy
import pytest
from unittest.mock import MagicMock, patch

from MnesOS.orchestrator import Orchestrator


# CWD-relative path — pytest is always invoked from the project root.
CARTRIDGE_DIR = "cartridges/generic-rpg"


# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------

class TestOrchestratorInit:
    def test_loads_cartridge(self):
        orch = Orchestrator(storage=MagicMock(), cartridge_dir=CARTRIDGE_DIR)
        assert orch.cartridge is not None
        assert orch.cartridge.yare_config
        assert orch.cartridge.lore_path

    def test_invalid_cartridge_raises(self):
        with pytest.raises(FileNotFoundError):
            Orchestrator(storage=MagicMock(), cartridge_dir="nonexistent/path/to/cartridge")

    def test_compiled_graph_has_expected_nodes(self):
        orch = Orchestrator(storage=MagicMock(), cartridge_dir=CARTRIDGE_DIR)
        node_names = set(orch._app.get_graph().nodes.keys())
        for expected in ("ResetAgentMessages", "CycleTick", "Director",
                         "Narrator", "CleanupAgentMessages"):
            assert expected in node_names, f"Missing node: {expected}"
        assert "Lore" not in node_names, "Lore pre-node replaced by multi_lore_lookup tool"
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
            Orchestrator(storage=MagicMock(), cartridge_dir=CARTRIDGE_DIR)
            mock_bg.assert_called_once()

    def test_orchestrator_passes_yare_config_to_build_graph(self):
        with patch("MnesOS.orchestrator.build_graph") as mock_bg:
            mock_bg.return_value = MagicMock()
            Orchestrator(storage=MagicMock(), cartridge_dir=CARTRIDGE_DIR)
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
                storage=MagicMock(),
                cartridge_dir=CARTRIDGE_DIR,
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


# ---------------------------------------------------------------------------
# Stateless mode and error paths
# ---------------------------------------------------------------------------

class TestOrchestratorStateless:
    @pytest.fixture
    def mock_storage(self):
        return MagicMock()

    @pytest.fixture
    def mock_version(self):
        from MnesOS.storage.models import CartridgeVersion
        return CartridgeVersion(
            id="v1", cartridge_id="c1", version_tag="1.0",
            yare_spec={"state_schema": {}, "events": {}, "macros": {}},
            prompt_directives={}, bot_lore="", first_message="", checksum="x"
        )

    @pytest.fixture
    def mock_persona(self):
        from MnesOS.storage.models import Persona
        return Persona(
            id="p1", user_id="u1", name="Aragorn",
            pronoun_sub="he", pronoun_obj="him", pronoun_poss="his", pronoun_poss_obj="his",
            appearance="", background="", personality=""
        )

    def test_orchestrator_stateless_initialization(self, mock_storage, mock_version, mock_persona):
        with patch("MnesOS.orchestrator.CartridgeLoader.load_from_version") as mock_load:
            mock_load.return_value = MagicMock(initial_state={}, yare_config={}, prompt_directives={}, lore_path=None, lore_content=None, persona_context="")
            orch = Orchestrator(cartridge_version=mock_version, persona=mock_persona, storage=mock_storage)
            assert orch._storage == mock_storage

    def test_orchestrator_stateless_process_turn(self, mock_storage, mock_version, mock_persona):
        from MnesOS.storage.models import TurnLog, TurnActor
        with patch("MnesOS.orchestrator.CartridgeLoader.load_from_version") as mock_load, \
             patch("MnesOS.orchestrator.StateHydrator.hydrate_state") as mock_hydrate, \
             patch("MnesOS.orchestrator.build_graph") as mock_build:
            
            mock_load.return_value = MagicMock(initial_state={}, yare_config={}, prompt_directives={}, lore_path=None, lore_content=None, persona_context="")
            mock_hydrate.return_value = {"client_messages": [], "bot_memory": {}}
            
            mock_app = MagicMock()
            mock_app.invoke.return_value = {
                "client_messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
                "bot_memory": {"hp": 90}
            }
            mock_build.return_value = mock_app
            
            orch = Orchestrator(cartridge_version=mock_version, persona=mock_persona, storage=mock_storage)
            mock_storage.get_turn_lineage.return_value = [
                TurnLog(id="t1", instance_id="i1", turn_index=0, actor=TurnActor.PLAYER, input_text="x", yare_delta={"hp": 100})
            ]
            
            result = orch.process_turn("hi", parent_turn_id="t1")
            assert result["narrator_text"] == "hello"
            assert "yare_delta" in result

    def test_orchestrator_value_error_no_dir_no_version(self):
        with pytest.raises(ValueError, match="Must provide either cartridge_dir or cartridge_version"):
            Orchestrator(storage=MagicMock())

    def test_orchestrator_not_implemented_separate_npc(self):
        with patch("MnesOS.orchestrator.CartridgeLoader.load") as mock_load:
            mock_load.return_value = MagicMock(yare_config={"separate_npc": True})
            with pytest.raises(NotImplementedError):
                Orchestrator(storage=MagicMock(), cartridge_dir=CARTRIDGE_DIR)

    def test_orchestrator_extract_narrator_response_empty(self):
        assert Orchestrator._extract_narrator_response({}) == ""
        assert Orchestrator._extract_narrator_response({"client_messages": []}) == ""
        assert Orchestrator._extract_narrator_response({"client_messages": [{"role": "user", "content": "x"}]}) == ""

    def test_orchestrator_extract_delta(self):
        from MnesOS.storage.models import TurnLog, TurnActor
        initial = {"hp": 100, "loc": "cave"}
        lineage = [
            TurnLog(id="t1", instance_id="i1", turn_index=0, actor=TurnActor.SYSTEM, input_text="", yare_delta={"hp": 90})
        ]
        new_state = {"bot_memory": {"hp": 80, "loc": "cave", "gold": 50}}
        
        delta = Orchestrator._extract_delta(initial, lineage, new_state)
        assert delta == {"hp": 80, "gold": 50}
        assert "loc" not in delta


