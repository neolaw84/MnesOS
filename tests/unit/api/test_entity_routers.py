"""
Unit tests for Persona, UserAccount, GameInstance, GameSave, and Turn API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from MnesOS.api.app import app
from MnesOS.api.deps import get_current_user, get_storage
from MnesOS.storage import (
    SQLite3PhysicalComponent, UserAccount, UserRole,
    Persona, Cartridge, CartridgeVersion, Visibility,
    GameInstance, GameStatus, TurnLog, TurnActor, GameSave,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(db_path=":memory:")
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
        user_id=user.id, name="Aragorn",
        pronoun_sub="he", pronoun_obj="him",
        pronoun_poss="his", pronoun_poss_obj="his",
        appearance="Tall ranger.", background="King in hiding.", personality="Stoic.",
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
        user_id=user.id, persona_id=persona.id,
        version_id=version.id, status=GameStatus.ACTIVE,
    ))


@pytest.fixture
def turn(storage, instance):
    return storage.append_turn_log(TurnLog(
        instance_id=instance.id, turn_index=0,
        actor=TurnActor.SYSTEM, input_text="", yare_delta={},
    ))


@pytest.fixture
def client(storage, user):
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: user.id
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===========================================================================
# PERSONAS
# ===========================================================================

class TestCreatePersona:
    def test_create_persona_returns_201(self, client):
        resp = client.post("/api/personas", json={
            "name": "Legolas", "pronoun_sub": "he", "pronoun_obj": "him",
            "pronoun_poss": "his", "pronoun_poss_obj": "his",
            "appearance": "Elf", "background": "Woodland realm.", "personality": "Swift.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Legolas"
        assert "id" in data


class TestListPersonas:
    def test_list_personas_empty(self, client):
        resp = client.get("/api/personas")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_personas_returns_created(self, client, persona):
        resp = client.get("/api/personas")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Aragorn"


class TestGetPersona:
    def test_get_existing_persona(self, client, persona):
        resp = client.get(f"/api/personas/{persona.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == persona.id

    def test_get_missing_persona_returns_404(self, client):
        resp = client.get("/api/personas/nonexistent")
        assert resp.status_code == 404


class TestUpdatePersona:
    def test_update_persona_name(self, client, persona):
        resp = client.put(f"/api/personas/{persona.id}", json={"name": "Strider"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Strider"

    def test_update_persona_wrong_owner_returns_403(self, client, storage, persona):
        other = storage.create_user(UserAccount(
            username="spy", email="s@s.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.put(f"/api/personas/{persona.id}", json={"name": "X"})
        assert resp.status_code == 403

    def test_update_missing_persona_returns_404(self, client):
        resp = client.put("/api/personas/nonexistent", json={"name": "X"})
        assert resp.status_code == 404


class TestDeletePersona:
    def test_delete_persona_returns_204(self, client, persona):
        resp = client.delete(f"/api/personas/{persona.id}")
        assert resp.status_code == 204

    def test_delete_persona_wrong_owner_returns_403(self, client, storage, persona):
        other = storage.create_user(UserAccount(
            username="intruder", email="i@i.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.delete(f"/api/personas/{persona.id}")
        assert resp.status_code == 403

    def test_delete_missing_persona_returns_404(self, client):
        resp = client.delete("/api/personas/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# USERS
# ===========================================================================

class TestCreateUser:
    def test_create_user_returns_201(self, client):
        resp = client.post("/api/users", json={
            "username": "gandalf", "email": "g@shire.me",
            "password": "mellon", "role": "PLAYER",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "gandalf"
        assert "password" not in data  # password not returned


class TestGetUser:
    def test_get_existing_user(self, client, user):
        resp = client.get(f"/api/users/{user.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == user.id

    def test_get_missing_user_returns_404(self, client):
        resp = client.get("/api/users/nonexistent")
        assert resp.status_code == 404


class TestUpdateUser:
    def test_update_user_email(self, client, user):
        resp = client.put(f"/api/users/{user.id}", json={"email": "new@hero.com"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@hero.com"

    def test_update_missing_user_returns_404(self, client):
        resp = client.put("/api/users/nonexistent", json={"email": "x@x.com"})
        assert resp.status_code == 404


class TestDeleteUser:
    def test_delete_user_returns_204(self, client, user):
        resp = client.delete(f"/api/users/{user.id}")
        assert resp.status_code == 204

    def test_delete_missing_user_returns_404(self, client):
        resp = client.delete("/api/users/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# GAME INSTANCES
# ===========================================================================

class TestCreateInstance:
    def test_create_instance_returns_201(self, client, persona, version):
        resp = client.post("/api/instances", json={
            "persona_id": persona.id, "version_id": version.id,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "instance_id" in data

    def test_create_instance_missing_persona_returns_404(self, client, version):
        resp = client.post("/api/instances", json={
            "persona_id": "nonexistent", "version_id": version.id,
        })
        assert resp.status_code == 404

    def test_create_instance_wrong_persona_owner_returns_403(self, client, storage, version):
        other = storage.create_user(UserAccount(
            username="oth", email="o2@o.com", password_hash="x", role=UserRole.PLAYER
        ))
        other_persona = storage.create_persona(Persona(
            user_id=other.id, name="P", pronoun_sub="they", pronoun_obj="them",
            pronoun_poss="their", pronoun_poss_obj="theirs", appearance="", background="", personality="",
        ))
        resp = client.post("/api/instances", json={
            "persona_id": other_persona.id, "version_id": version.id,
        })
        assert resp.status_code == 403

    def test_create_instance_with_first_message_creates_turn(self, client, storage, persona, cartridge):
        ver_with_msg = storage.create_cartridge_version(CartridgeVersion(
            cartridge_id=cartridge.id, version_tag="2.0",
            yare_spec={}, prompt_directives={}, bot_lore="", first_message="Welcome, hero!",
            checksum="zzz",
        ))
        resp = client.post("/api/instances", json={
            "persona_id": persona.id, "version_id": ver_with_msg.id,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["turn_id"] is not None


class TestListInstances:
    def test_list_instances(self, client, instance):
        resp = client.get("/api/instances")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetInstance:
    def test_get_existing_instance(self, client, instance):
        resp = client.get(f"/api/instances/{instance.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == instance.id

    def test_get_missing_instance_returns_404(self, client):
        resp = client.get("/api/instances/nonexistent")
        assert resp.status_code == 404

    def test_get_instance_wrong_owner_returns_403(self, client, storage, instance):
        other = storage.create_user(UserAccount(
            username="z", email="z@z.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.get(f"/api/instances/{instance.id}")
        assert resp.status_code == 403


class TestUpdateInstance:
    def test_update_instance_status(self, client, instance):
        resp = client.put(f"/api/instances/{instance.id}", json={"status": "PAUSED"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAUSED"

    def test_update_instance_invalid_status(self, client, instance):
        resp = client.put(f"/api/instances/{instance.id}", json={"status": "FLYING"})
        assert resp.status_code == 422

    def test_update_missing_instance_returns_404(self, client):
        resp = client.put("/api/instances/nonexistent", json={"status": "PAUSED"})
        assert resp.status_code == 404


class TestDeleteInstance:
    def test_delete_instance_returns_204(self, client, instance):
        resp = client.delete(f"/api/instances/{instance.id}")
        assert resp.status_code == 204

    def test_delete_missing_instance_returns_404(self, client):
        resp = client.delete("/api/instances/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# GAME SAVES (standalone /api/saves endpoint)
# ===========================================================================

class TestGetSave:
    def test_get_save(self, client, instance, turn, storage):
        save = storage.create_game_save(GameSave(
            instance_id=instance.id, turn_log_id=turn.id, label="Checkpoint"
        ))
        resp = client.get(f"/api/saves/{save.id}")
        assert resp.status_code == 200
        assert resp.json()["label"] == "Checkpoint"

    def test_get_missing_save_returns_404(self, client):
        resp = client.get("/api/saves/nonexistent")
        assert resp.status_code == 404

    def test_get_save_wrong_owner_returns_403(self, client, storage, instance, turn):
        save = storage.create_game_save(GameSave(
            instance_id=instance.id, turn_log_id=turn.id, label="Mine"
        ))
        other = storage.create_user(UserAccount(
            username="burglar", email="b@b.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.get(f"/api/saves/{save.id}")
        assert resp.status_code == 403


class TestUpdateSave:
    def test_update_save_label(self, client, instance, turn, storage):
        save = storage.create_game_save(GameSave(
            instance_id=instance.id, turn_log_id=turn.id, label="Old Label"
        ))
        resp = client.put(f"/api/saves/{save.id}", json={"label": "New Label"})
        assert resp.status_code == 200
        assert resp.json()["label"] == "New Label"

    def test_update_missing_save_returns_404(self, client):
        resp = client.put("/api/saves/nonexistent", json={"label": "X"})
        assert resp.status_code == 404


class TestDeleteSave:
    def test_delete_save_returns_204(self, client, instance, turn, storage):
        save = storage.create_game_save(GameSave(
            instance_id=instance.id, turn_log_id=turn.id, label="Tmp"
        ))
        resp = client.delete(f"/api/saves/{save.id}")
        assert resp.status_code == 204

    def test_delete_missing_save_returns_404(self, client):
        resp = client.delete("/api/saves/nonexistent")
        assert resp.status_code == 404
