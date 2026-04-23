"""
Unit tests for the MnesOS Alpha FastAPI endpoints.

Uses FastAPI's ``TestClient`` with dependency overrides to inject an
in-memory SQLite3 store and a mock user.  No real LLM calls are made.
"""

import pytest
from fastapi.testclient import TestClient

from MnesOS.api.app import app
from MnesOS.api.deps import get_current_user, get_llm_clients, get_storage
from MnesOS.storage import (
    SQLite3PhysicalComponent,
    UserAccount,
    UserRole,
    Persona,
    Cartridge,
    CartridgeVersion,
    Visibility,
    GameInstance,
    GameStatus,
    TurnLog,
    TurnActor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_USER_ID = "test-user-001"


@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(db_path=":memory:")
    store.initialize()
    return store


@pytest.fixture
def instance_id(storage):
    """Scaffold the full entity chain and return the game instance ID."""
    user = storage.create_user(
        UserAccount(
            username="tester", email="t@t.com",
            password_hash="x", role=UserRole.PLAYER,
        )
    )
    # Update the mock user ID to match what storage assigned
    global MOCK_USER_ID
    MOCK_USER_ID = user.id

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


@pytest.fixture
def client(storage, instance_id):
    """TestClient with dependency overrides for storage, auth, and LLM.

    NOTE: must depend on instance_id so MOCK_USER_ID is set before
    the dependency override captures it.
    """
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_ID
    app.dependency_overrides[get_llm_clients] = lambda: None  # dry-run

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# §1.1  POST /api/instances/{instance_id}/turn
# ---------------------------------------------------------------------------


class TestProcessTurn:
    def test_first_turn_returns_200(self, client, instance_id):
        resp = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "I look around."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "turn_id" in data
        assert "narrator_response" in data
        assert "yare_delta" in data

    def test_chained_turns(self, client, instance_id):
        r1 = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Turn 1"},
        )
        t1_id = r1.json()["turn_id"]

        r2 = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"parent_turn_id": t1_id, "user_input": "Turn 2"},
        )
        assert r2.status_code == 200
        assert r2.json()["turn_id"] != t1_id

    def test_branching_turns(self, client, instance_id):
        r_root = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Start"},
        )
        root_id = r_root.json()["turn_id"]

        r_a = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"parent_turn_id": root_id, "user_input": "Go left"},
        )
        r_b = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"parent_turn_id": root_id, "user_input": "Go right"},
        )
        assert r_a.json()["turn_id"] != r_b.json()["turn_id"]

    def test_missing_user_input_returns_422(self, client, instance_id):
        resp = client.post(
            f"/api/instances/{instance_id}/turn",
            json={},
        )
        assert resp.status_code == 422

    def test_nonexistent_instance_returns_404(self, client):
        resp = client.post(
            "/api/instances/nonexistent-id/turn",
            json={"user_input": "Hello"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# §1.2  POST /api/instances/{instance_id}/inject
# ---------------------------------------------------------------------------


class TestInjectState:
    def test_inject_returns_turn_id(self, client, instance_id):
        resp = client.post(
            f"/api/instances/{instance_id}/inject",
            json={"yare_delta": {"player": {"gold": 999}}},
        )
        assert resp.status_code == 200
        assert "turn_id" in resp.json()

    def test_inject_with_parent(self, client, instance_id, storage):
        # Create a turn first
        r1 = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Walk"},
        )
        parent_id = r1.json()["turn_id"]

        resp = client.post(
            f"/api/instances/{instance_id}/inject",
            json={
                "parent_turn_id": parent_id,
                "yare_delta": {"player": {"hp": 999}},
            },
        )
        assert resp.status_code == 200

        # Verify the injected turn is a SYSTEM actor
        logs = storage.get_turn_logs(instance_id)
        system_logs = [l for l in logs if l.actor == TurnActor.SYSTEM]
        assert len(system_logs) == 1
        assert system_logs[0].yare_delta == {"player": {"hp": 999}}

    def test_inject_then_turn_reflects_state(self, client, instance_id):
        """After injecting gold=999, a subsequent turn should hydrate with that value."""
        # Inject
        r_inject = client.post(
            f"/api/instances/{instance_id}/inject",
            json={"yare_delta": {"player": {"gold": 999}}},
        )
        inject_id = r_inject.json()["turn_id"]

        # Check hydrated state
        resp = client.get(
            f"/api/instances/{instance_id}/state",
            params={"turn_log_id": inject_id},
        )
        assert resp.status_code == 200
        assert resp.json()["bot_memory"]["player"]["gold"] == 999


# ---------------------------------------------------------------------------
# §1.3  POST /api/instances/{instance_id}/saves
# ---------------------------------------------------------------------------


class TestGameSaves:
    def test_create_save(self, client, instance_id):
        # First create a turn to bookmark
        r1 = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Explore"},
        )
        turn_id = r1.json()["turn_id"]

        resp = client.post(
            f"/api/instances/{instance_id}/saves",
            json={"turn_log_id": turn_id, "label": "Before the boss"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "save_id" in data
        assert "created_at" in data

    def test_list_saves_empty(self, client, instance_id):
        resp = client.get(f"/api/instances/{instance_id}/saves")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_saves_returns_created(self, client, instance_id):
        # Create a turn, then two saves
        r1 = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Walk"},
        )
        turn_id = r1.json()["turn_id"]

        client.post(
            f"/api/instances/{instance_id}/saves",
            json={"turn_log_id": turn_id, "label": "Save A"},
        )
        client.post(
            f"/api/instances/{instance_id}/saves",
            json={"turn_log_id": turn_id, "label": "Save B"},
        )

        resp = client.get(f"/api/instances/{instance_id}/saves")
        assert resp.status_code == 200
        saves = resp.json()
        assert len(saves) == 2
        assert saves[0]["label"] == "Save A"
        assert saves[1]["label"] == "Save B"
        assert "id" in saves[0]
        assert "turn_log_id" in saves[0]
        assert "created_at" in saves[0]


# ---------------------------------------------------------------------------
# §1.4  GET /api/instances/{instance_id}/state
# ---------------------------------------------------------------------------


class TestGetGameState:
    def test_initial_state_without_turn_log_id(self, client, instance_id):
        resp = client.get(f"/api/instances/{instance_id}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "bot_memory" in data
        assert "client_messages" in data
        assert data["client_messages"] == []

    def test_hydrated_state_after_turns(self, client, instance_id):
        r1 = client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Hello"},
        )
        turn_id = r1.json()["turn_id"]

        resp = client.get(
            f"/api/instances/{instance_id}/state",
            params={"turn_log_id": turn_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["client_messages"]) >= 1
        assert data["client_messages"][0]["content"] == "Hello"


# ---------------------------------------------------------------------------
# Auth tests (MNS-302)
# ---------------------------------------------------------------------------


class TestAuth:
    def test_missing_user_header_returns_401(self, storage, instance_id):
        """Without the auth override, the raw header check kicks in."""
        app.dependency_overrides[get_storage] = lambda: storage
        app.dependency_overrides[get_llm_clients] = lambda: None
        # Intentionally do NOT override get_current_user
        app.dependency_overrides.pop(get_current_user, None)

        raw_client = TestClient(app)
        # Use a real instance_id so the 404-from-orchestrator doesn't fire
        # before FastAPI validates the missing required header.
        resp = raw_client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Hello"},
        )
        assert resp.status_code == 422  # Missing required header

        app.dependency_overrides.clear()

    def test_wrong_user_returns_403(self, storage, instance_id):
        """A user who doesn't own the instance gets 403."""
        app.dependency_overrides[get_storage] = lambda: storage
        app.dependency_overrides[get_current_user] = lambda: "wrong-user-id"
        app.dependency_overrides[get_llm_clients] = lambda: None

        bad_client = TestClient(app)
        resp = bad_client.post(
            f"/api/instances/{instance_id}/turn",
            json={"user_input": "Hello"},
        )
        assert resp.status_code == 403

        app.dependency_overrides.clear()
