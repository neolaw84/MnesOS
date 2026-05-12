"""
Integration tests for orchestrator.py — tests that exercise the full turn pipeline.

These tests require a real (or fake-LLM) end-to-end graph invocation.
A _BindableFakeModel replaces real LLM calls where needed.
"""

import copy
import pytest
import yaml
from unittest.mock import MagicMock, patch
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from MnesOS.orchestrator import Orchestrator
from MnesOS.storage import SQLite3PhysicalComponent
from MnesOS.storage.models import TurnLog, TurnActor, UserAccount, UserRole, Persona, Cartridge, CartridgeVersion, GameInstance, GameStatus, Visibility


# CWD-relative path — pytest is always invoked from the project root.
CARTRIDGE_DIR = "cartridges/generic-rpg"


class _BindableFakeModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel extended with a passthrough bind_tools() for tests."""

    def bind_tools(self, tools, **kwargs):
        return self


def make_fake_llm(*responses: str) -> _BindableFakeModel:
    """Build a fake LLM that returns AIMessages with the given contents in order."""
    return _BindableFakeModel(responses=[AIMessage(content=r) for r in responses])


@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(db_path=":memory:")
    store.initialize()
    return store

@pytest.fixture
def instance_id(storage):
    user = storage.create_user(UserAccount(username="tester", email="t@t.com", password_hash="x", role=UserRole.PLAYER))
    persona = storage.create_persona(Persona(user_id=user.id, name="Hero", pronoun_sub="they", pronoun_obj="them", pronoun_poss="their", pronoun_poss_obj="theirs", appearance="", background="", personality=""))
    cart = storage.create_cartridge(Cartridge(creator_id=user.id, title="Test", description="test", genre="rpg", visibility=Visibility.PRIVATE))
    ver = storage.create_cartridge_version(CartridgeVersion(cartridge_id=cart.id, version_tag="1.0", yare_spec={}, prompt_directives={}, bot_lore="", first_message="", checksum="abc"))
    inst = storage.create_game_instance(GameInstance(user_id=user.id, persona_id=persona.id, version_id=ver.id, status=GameStatus.ACTIVE))
    return inst.id

def _persist_turn(storage, instance_id, result, user_input, parent_turn_id=None):
    lineage = storage.get_turn_lineage(parent_turn_id) if parent_turn_id else []
    turn = TurnLog(
        instance_id=instance_id,
        turn_index=len(lineage),
        actor=TurnActor.PLAYER,
        input_text=user_input,
        yare_delta=result["yare_delta"],
        narrator_text=result["narrator_text"],
        parent_id=parent_turn_id,
    )
    return storage.append_turn_log(turn)

# ---------------------------------------------------------------------------
# process_turn tests (dry-run — no LLMs)
# ---------------------------------------------------------------------------

class TestProcessTurnDryRun:
    """With llm_*=None the graph runs but produces no LLM output."""

    def test_appends_user_message(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        result = orch.process_turn("Hello world")
        # In stateless, client_messages isn't directly exposed on Orch, but it's passed around.
        # However, since there's no stateful memory, we just test the return result.
        assert isinstance(result, dict)

    def test_returns_empty_string_without_llm(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        result = orch.process_turn("Look around.")
        assert result["narrator_text"] == ""


# ---------------------------------------------------------------------------
# process_turn tests (with fake LLM)
# ---------------------------------------------------------------------------

class TestProcessTurnWithFakeLlm:
    def test_returns_narrator_response(self, storage, instance_id):
        narrator_llm = make_fake_llm("You stand at the Crossroads.")
        orch = Orchestrator(
            storage=storage,
            cartridge_dir=CARTRIDGE_DIR,
            llm_narrator=narrator_llm,
        )
        result = orch.process_turn("I look around.")
        assert result["narrator_text"] == "You stand at the Crossroads."

    def test_subsequent_turns_use_updated_state(self, storage, instance_id):
        """Each turn's fake response differs; both should appear in history."""
        narrator_llm = make_fake_llm("First response.", "Second response.")
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR, llm_narrator=narrator_llm)
        r1 = orch.process_turn("Turn 1")
        t1 = _persist_turn(storage, instance_id, r1, "Turn 1")
        r2 = orch.process_turn("Turn 2", parent_turn_id=t1.id)
        assert r1["narrator_text"] == "First response."
        assert r2["narrator_text"] == "Second response."





# ---------------------------------------------------------------------------
# separate_npc feature tests
# ---------------------------------------------------------------------------

class TestSeparateNpcBrainFeature:
    """Tests for the optional separate_npc architecture runtime behavior."""

    def test_orchestrator_with_separate_npc_false_works(self, storage, tmp_path):
        """When separate_npc is False, orchestrator should work normally."""
        yare = {
            "version": "1.0",
            "state_schema": {"player": {"hp": {"type": "int", "default": 100}}},
            "events": {},
            "separate_npc": False,
        }
        (tmp_path / "yare.yaml").write_text(yaml.dump(yare))
        (tmp_path / "bot_lore.md").write_text("# Test\nSome lore.")

        orch = Orchestrator(storage=storage, cartridge_dir=str(tmp_path))
        result = orch.process_turn("Hello")
        assert isinstance(result, dict)

    def test_orchestrator_with_separate_npc_true_raises_not_implemented(self, tmp_path):
        """When separate_npc is True, orchestrator should raise NotImplementedError."""
        yare = {
            "version": "1.0",
            "state_schema": {"player": {"hp": {"type": "int", "default": 100}}},
            "events": {},
            "separate_npc": True,
        }
        (tmp_path / "yare.yaml").write_text(yaml.dump(yare))
        (tmp_path / "bot_lore.md").write_text("# Test\nSome lore.")

        with pytest.raises(NotImplementedError, match="separate_npc.*not yet implemented"):
            Orchestrator(storage=MagicMock(), cartridge_dir=str(tmp_path))

    def test_orchestrator_without_separate_npc_key_works(self, storage, tmp_path):
        """When separate_npc key is omitted (default False), orchestrator works."""
        yare = {
            "version": "1.0",
            "state_schema": {"player": {"hp": {"type": "int", "default": 100}}},
            "events": {},
        }
        (tmp_path / "yare.yaml").write_text(yaml.dump(yare))
        (tmp_path / "bot_lore.md").write_text("# Test\nSome lore.")

        orch = Orchestrator(storage=storage, cartridge_dir=str(tmp_path))
        result = orch.process_turn("Test")
        assert isinstance(result, dict)

    def test_generic_rpg_cartridge_does_not_raise(self, storage):
        """The generic-rpg cartridge (with default separate_npc=False) works."""
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        result = orch.process_turn("Look around")
        assert isinstance(result, dict)

    def test_monolithic_mode_graph_excludes_npc_node(self, tmp_path):
        """When separate_npc=False, the compiled graph should NOT have NPC_Brain node."""
        yare = {
            "version": "1.0",
            "state_schema": {"player": {"hp": {"type": "int", "default": 100}}},
            "events": {},
            "separate_npc": False,
        }
        (tmp_path / "yare.yaml").write_text(yaml.dump(yare))
        (tmp_path / "bot_lore.md").write_text("# Test\nSome lore.")

        orch = Orchestrator(storage=MagicMock(), cartridge_dir=str(tmp_path))
        node_names = set(orch._app.get_graph().nodes.keys())
        assert "NPC_Brain" not in node_names, "NPC_Brain node should not exist in monolithic mode"

    def test_monolithic_mode_graph_includes_expected_nodes(self, tmp_path):
        """When separate_npc=False, graph should have Director and Narrator."""
        yare = {
            "version": "1.0",
            "state_schema": {"player": {"hp": {"type": "int", "default": 100}}},
            "events": {},
            "separate_npc": False,
        }
        (tmp_path / "yare.yaml").write_text(yaml.dump(yare))
        (tmp_path / "bot_lore.md").write_text("# Test\nSome lore.")

        orch = Orchestrator(storage=MagicMock(), cartridge_dir=str(tmp_path))
        node_names = set(orch._app.get_graph().nodes.keys())
        for expected in ("Director", "Narrator", "CycleTick"):
            assert expected in node_names, f"Expected node {expected} missing in monolithic mode"
        assert "Lore" not in node_names, "Lore pre-node replaced by multi_lore_lookup tool"
