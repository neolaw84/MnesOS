"""
Integration tests for the stateless Orchestrator flow (MNS-203).

Tests use an in-memory SQLite3 store and the generic-rpg cartridge
to verify that the Orchestrator can hydrate state, invoke the graph,
persist deltas, and chain turns via parent_turn_id — all without
keeping any in-memory state between turns.
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
)
from MnesOS.storage.hydrator import hydrate_state


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
            yare_spec={}, prompt_directives={}, bot_lore="", checksum="abc",
        )
    )
    inst = storage.create_game_instance(
        GameInstance(
            user_id=user.id, persona_id=persona.id,
            version_id=ver.id, status=GameStatus.ACTIVE,
        )
    )
    return inst.id


# ---------------------------------------------------------------------------
# Core stateless flow
# ---------------------------------------------------------------------------


class TestStatelessOrchestrator:
    """Core stateless turn-processing tests."""

    def test_first_turn_returns_turn_id(self, storage, instance_id):
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        turn_id = orch.process_turn(
            "I look around.",
            parent_turn_id=None,
            instance_id=instance_id,
        )
        assert isinstance(turn_id, str)
        assert len(turn_id) > 0

    def test_persisted_turn_log_exists(self, storage, instance_id):
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        turn_id = orch.process_turn(
            "Hello!",
            parent_turn_id=None,
            instance_id=instance_id,
        )
        logs = storage.get_turn_logs(instance_id)
        assert len(logs) == 1
        assert logs[0].id == turn_id
        assert logs[0].input_text == "Hello!"
        assert logs[0].actor == TurnActor.PLAYER

    def test_consecutive_turns_chain_via_parent_id(self, storage, instance_id):
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        t1 = orch.process_turn(
            "Turn 1", parent_turn_id=None, instance_id=instance_id,
        )
        t2 = orch.process_turn(
            "Turn 2", parent_turn_id=t1, instance_id=instance_id,
        )
        t3 = orch.process_turn(
            "Turn 3", parent_turn_id=t2, instance_id=instance_id,
        )

        logs = storage.get_turn_logs(instance_id)
        assert len(logs) == 3
        assert logs[1].parent_id == t1
        assert logs[2].parent_id == t2

    def test_stateless_no_internal_state(self, storage, instance_id):
        """The orchestrator must not hold in-memory state in stateless mode."""
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        assert orch._state is None
        with pytest.raises(RuntimeError, match="No in-memory state"):
            _ = orch.state

    def test_orchestrator_can_be_destroyed_and_recreated(self, storage, instance_id):
        """Instantiate, process, destroy, re-instantiate, continue."""
        orch1 = Orchestrator(CARTRIDGE_DIR, storage=storage)
        t1 = orch1.process_turn(
            "I look around.", parent_turn_id=None, instance_id=instance_id,
        )
        del orch1  # destroy

        # Re-create and continue from where we left off
        orch2 = Orchestrator(CARTRIDGE_DIR, storage=storage)
        t2 = orch2.process_turn(
            "I go north.", parent_turn_id=t1, instance_id=instance_id,
        )
        assert t2 != t1
        logs = storage.get_turn_logs(instance_id)
        assert len(logs) == 2

    def test_branching_timeline(self, storage, instance_id):
        """Two turns branching from the same parent create separate paths."""
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        root = orch.process_turn(
            "Beginning.", parent_turn_id=None, instance_id=instance_id,
        )
        branch_a = orch.process_turn(
            "I go left.", parent_turn_id=root, instance_id=instance_id,
        )
        branch_b = orch.process_turn(
            "I go right.", parent_turn_id=root, instance_id=instance_id,
        )
        assert branch_a != branch_b

        lineage_a = storage.get_turn_lineage(branch_a)
        lineage_b = storage.get_turn_lineage(branch_b)
        # Both lineages share the root
        assert lineage_a[0].id == lineage_b[0].id
        # But diverge at the second node
        assert lineage_a[1].id != lineage_b[1].id


class TestStatelessOrchestratorErrors:
    """Error handling for stateless mode."""

    def test_missing_instance_id_raises(self, storage):
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        with pytest.raises(ValueError, match="instance_id is required"):
            orch.process_turn("Hi", parent_turn_id=None)

    def test_invalid_parent_turn_id_raises(self, storage, instance_id):
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        with pytest.raises(KeyError):
            orch.process_turn(
                "Hi",
                parent_turn_id="nonexistent-turn-id",
                instance_id=instance_id,
            )


class TestStatelessDeltaPersistence:
    """Verify that yare_delta is correctly extracted and persisted."""

    def test_delta_is_dict(self, storage, instance_id):
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        turn_id = orch.process_turn(
            "I attack!", parent_turn_id=None, instance_id=instance_id,
        )
        logs = storage.get_turn_logs(instance_id)
        assert isinstance(logs[0].yare_delta, dict)

    def test_hydration_from_persisted_turns_matches_initial_state(self, storage, instance_id):
        """When no YARE events fire (dry-run), hydrated state should match initial."""
        orch = Orchestrator(CARTRIDGE_DIR, storage=storage)
        t1 = orch.process_turn(
            "I wait.", parent_turn_id=None, instance_id=instance_id,
        )
        lineage = storage.get_turn_lineage(t1)
        state = hydrate_state(lineage, orch.cartridge.initial_state)
        # In dry-run mode (no LLMs), bot_memory shouldn't change
        assert state["bot_memory"] == orch.cartridge.initial_state
