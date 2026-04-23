"""
Unit tests for the TurnLog API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from MnesOS.api.app import app
from MnesOS.api.deps import get_current_user, get_storage
from MnesOS.storage import (
    SQLite3PhysicalComponent, UserAccount, UserRole,
    Persona, Cartridge, CartridgeVersion, Visibility,
    GameInstance, GameStatus, TurnLog, TurnActor
)

@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(":memory:")
    store.initialize()
    return store

@pytest.fixture
def user(storage):
    return storage.create_user(UserAccount(
        username="hero", email="h@h.com", password_hash="x", role=UserRole.PLAYER
    ))

@pytest.fixture
def persona(storage, user):
    return storage.create_persona(Persona(
        user_id=user.id, name="Aragorn", pronoun_sub="he", pronoun_obj="him",
        pronoun_poss="his", pronoun_poss_obj="his", appearance="", background="", personality="",
    ))

@pytest.fixture
def cartridge(storage, user):
    return storage.create_cartridge(Cartridge(
        creator_id=user.id, title="T", description="", genre="", visibility=Visibility.PUBLIC
    ))

@pytest.fixture
def version(storage, cartridge):
    return storage.create_cartridge_version(CartridgeVersion(
        cartridge_id=cartridge.id, version_tag="1.0",
        yare_spec={}, prompt_directives={}, bot_lore="", first_message="", checksum="x",
    ))

@pytest.fixture
def instance(storage, user, persona, version):
    return storage.create_game_instance(GameInstance(
        user_id=user.id, persona_id=persona.id, version_id=version.id, status=GameStatus.ACTIVE,
    ))

@pytest.fixture
def turn(storage, instance):
    return storage.append_turn_log(TurnLog(
        instance_id=instance.id, turn_index=0, actor=TurnActor.PLAYER, input_text="hello", yare_delta={},
    ))

@pytest.fixture
def client(storage, user):
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: user.id
    yield TestClient(app)
    app.dependency_overrides.clear()

class TestGetTurn:
    def test_get_existing_turn(self, client, turn):
        resp = client.get(f"/api/turns/{turn.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == turn.id

    def test_get_missing_turn_returns_404(self, client):
        resp = client.get("/api/turns/nonexistent")
        assert resp.status_code == 404

    def test_get_turn_wrong_owner_returns_403(self, client, storage, turn):
        other = storage.create_user(UserAccount(
            username="spy", email="s@s.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.get(f"/api/turns/{turn.id}")
        assert resp.status_code == 403

class TestDeleteTurn:
    def test_delete_turn_returns_204(self, client, turn):
        resp = client.delete(f"/api/turns/{turn.id}")
        assert resp.status_code == 204

    def test_delete_missing_turn_returns_404(self, client):
        resp = client.delete("/api/turns/nonexistent")
        assert resp.status_code == 404

    def test_delete_turn_wrong_owner_returns_403(self, client, storage, turn):
        other = storage.create_user(UserAccount(
            username="intruder", email="i@i.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.delete(f"/api/turns/{turn.id}")
        assert resp.status_code == 403
