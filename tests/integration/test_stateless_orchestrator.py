"""
Integration tests for the stateless Orchestrator flow (MNS-203).

Tests use an in-memory SQLite3 store and the generic-rpg cartridge
to verify that the Orchestrator can hydrate state, invoke the graph,
and return result dicts — all without keeping any in-memory state
between turns.

Per 0005 §3.2 the Orchestrator does NOT persist to the database.
The API route handles that.  These tests verify persistence is done
by the test itself (mimicking the API route).
"""

import copy
import pytest

from MnesOS.orchestrator import Orchestrator
from MnesOS.storage import (
    SQLite3PhysicalComponent,
    TurnLog,
    TurnActor,
    GameInstance,
    GameStatus,
    UserAccount,
    UserRole,
    Persona,
    Cartridge,
    CartridgeVersion,
    Visibility,
    StateHydrator,
)


CARTRIDGE_DIR = "cartridges/generic-rpg"


@pytest.fixture
def storage():
    """Create and initialize an in-memory SQLite3 store."""
    store = SQLite3PhysicalComponent(db_path=":memory:")
    store.initialize()
    return store


@pytest.fixture
def instance_id(storage):
    """Scaffold user/persona/cartridge/version/game-instance rows so
    foreign-key constraints are satisfied, and return the instance ID.
    """
    user = storage.create_user(
        UserAccount(username="tester", email="t@t.com", password_hash="x", role=UserRole.PLAYER)
    )
    persona = storage.create_persona(
        Persona(
            user_id=user.id, name="Hero",
            pronoun_sub="they", pronoun_obj="them",
            pronoun_poss="their", pronoun_poss_obj="theirs",
            appearance="", background="", personality="",
        )
    )
    cart = storage.create_cartridge(
        Cartridge(
            creator_id=user.id, title="Test", description="test",
            genre="rpg", visibility=Visibility.PRIVATE,
        )
    )
    ver = storage.create_cartridge_version(
        CartridgeVersion(
            cartridge_id=cart.id, version_tag="1.0",
            yare_spec={}, prompt_directives={}, bot_lore="", first_message="", checksum="abc",
        )
    )
    inst = storage.create_game_instance(
        GameInstance(
            user_id=user.id, persona_id=persona.id,
            version_id=ver.id, status=GameStatus.ACTIVE,
        )
    )
    return inst.id


def _persist_turn(storage, instance_id, result, user_input, parent_turn_id=None):
    """Helper mimicking the API route: persist a TurnLog from orchestrator result."""
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
# Core stateless flow
# ---------------------------------------------------------------------------


class TestStatelessOrchestrator:
    """Core stateless turn-processing tests."""

    def test_first_turn_returns_result_dict(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        result = orch.process_turn(
            "I look around.",
            parent_turn_id=None,
        )
        assert isinstance(result, dict)
        assert "narrator_text" in result
        assert "yare_delta" in result

    def test_result_narrator_text_is_string(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        result = orch.process_turn("Hello!", parent_turn_id=None)
        assert isinstance(result["narrator_text"], str)

    def test_result_yare_delta_is_dict(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        result = orch.process_turn("I attack!", parent_turn_id=None)
        assert isinstance(result["yare_delta"], dict)

    def test_consecutive_turns_chain_via_parent_id(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)

        r1 = orch.process_turn("Turn 1", parent_turn_id=None)
        t1 = _persist_turn(storage, instance_id, r1, "Turn 1")

        r2 = orch.process_turn("Turn 2", parent_turn_id=t1.id)
        t2 = _persist_turn(storage, instance_id, r2, "Turn 2", parent_turn_id=t1.id)

        r3 = orch.process_turn("Turn 3", parent_turn_id=t2.id)
        t3 = _persist_turn(storage, instance_id, r3, "Turn 3", parent_turn_id=t2.id)

        logs = storage.get_turn_logs(instance_id)
        assert len(logs) == 3
        assert logs[1].parent_id == t1.id
        assert logs[2].parent_id == t2.id



    def test_orchestrator_can_be_destroyed_and_recreated(self, storage, instance_id):
        """Instantiate, process, destroy, re-instantiate, continue."""
        orch1 = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        r1 = orch1.process_turn("I look around.", parent_turn_id=None)
        t1 = _persist_turn(storage, instance_id, r1, "I look around.")
        del orch1  # destroy

        # Re-create and continue from where we left off
        orch2 = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        r2 = orch2.process_turn("I go north.", parent_turn_id=t1.id)
        t2 = _persist_turn(storage, instance_id, r2, "I go north.", parent_turn_id=t1.id)

        assert t2.id != t1.id
        logs = storage.get_turn_logs(instance_id)
        assert len(logs) == 2

    def test_branching_timeline(self, storage, instance_id):
        """Two turns branching from the same parent create separate paths."""
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        r_root = orch.process_turn("Beginning.", parent_turn_id=None)
        t_root = _persist_turn(storage, instance_id, r_root, "Beginning.")

        r_a = orch.process_turn("I go left.", parent_turn_id=t_root.id)
        t_a = _persist_turn(storage, instance_id, r_a, "I go left.", parent_turn_id=t_root.id)

        r_b = orch.process_turn("I go right.", parent_turn_id=t_root.id)
        t_b = _persist_turn(storage, instance_id, r_b, "I go right.", parent_turn_id=t_root.id)

        assert t_a.id != t_b.id

        lineage_a = storage.get_turn_lineage(t_a.id)
        lineage_b = storage.get_turn_lineage(t_b.id)
        # Both lineages share the root
        assert lineage_a[0].id == lineage_b[0].id
        # But diverge at the second node
        assert lineage_a[1].id != lineage_b[1].id

    def test_does_not_persist_to_db(self, storage, instance_id):
        """Per 0005 §3.2, orchestrator must NOT write to storage."""
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        orch.process_turn("Hello", parent_turn_id=None)
        logs = storage.get_turn_logs(instance_id)
        assert len(logs) == 0  # Orchestrator did NOT save


class TestStatelessOrchestratorErrors:
    """Error handling for stateless mode."""

    def test_no_storage_raises(self):
        with pytest.raises(ValueError, match="storage backend is required"):
            Orchestrator(storage=None, cartridge_dir=CARTRIDGE_DIR)

    def test_invalid_parent_turn_id_raises(self, storage, instance_id):
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        with pytest.raises(KeyError):
            orch.process_turn(
                "Hi",
                parent_turn_id="nonexistent-turn-id",
            )


class TestStatelessDeltaPersistence:
    """Verify that yare_delta is correctly extracted."""

    def test_hydration_from_persisted_turns_matches_initial_state(self, storage, instance_id):
        """When no YARE events fire (dry-run), hydrated state should match initial."""
        orch = Orchestrator(storage=storage, cartridge_dir=CARTRIDGE_DIR)
        r1 = orch.process_turn("I wait.", parent_turn_id=None)
        t1 = _persist_turn(storage, instance_id, r1, "I wait.")

        lineage = storage.get_turn_lineage(t1.id)
        state = StateHydrator.hydrate_state(lineage, orch.cartridge.initial_state)
        # In dry-run mode (no LLMs), bot_memory shouldn't change
        expected_memory = copy.deepcopy(orch.cartridge.initial_state)
        expected_memory["game_time"] = "2026-04-01T00:00:00"
        assert state["bot_memory"] == expected_memory
