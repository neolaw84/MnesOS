import pytest
from fastapi.testclient import TestClient

from MnesOS.api.app import app
from MnesOS.api.deps import get_current_user, get_storage
from MnesOS.storage import SQLite3PhysicalComponent, UserAccount, UserRole, Cartridge, CartridgeVersion, Visibility

MOCK_USER_ID = "test-user"


@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(db_path=":memory:")
    store.initialize()
    return store


@pytest.fixture
def user(storage):
    return storage.create_user(UserAccount(
        username="creator",
        email="creator@example.com",
        password_hash="x",
        role=UserRole.CREATOR,
    ))


@pytest.fixture
def cartridge(storage, user):
    return storage.create_cartridge(Cartridge(
        creator_id=user.id,
        title="Builder Test Cartridge",
        description="desc",
        genre="rpg",
        visibility=Visibility.PRIVATE,
    ))


@pytest.fixture
def client(storage, user):
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: user.id
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_publish_version_success(client, storage, cartridge):
    payload = {
        "version_tag": "1.0.0",
        "first_message": "# Welcome to the builder",
        "prompt_directives": "director: Maintain a noir tone throughout.",
        "yare_rules": "state_schema: {}\nevents: {}\nmacros: {}",
        "yare_type": "yaml",
        "bot_lore": "Ancient ruins whisper beneath the city.",
    }

    response = client.post(f"/api/cartridges/{cartridge.id}/versions/publish", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["cartridge_id"] == cartridge.id
    assert data["version_tag"] == "1.0.0"

    versions = storage.list_cartridge_versions(cartridge.id)
    assert len(versions) == 1
    assert versions[0].version_tag == "1.0.0"


def test_publish_version_missing_fields(client, cartridge):
    response = client.post(
        f"/api/cartridges/{cartridge.id}/versions/publish",
        json={
            "version_tag": "1.0.0",
            "first_message": "# Welcome",
            "prompt_directives": "director: {}",
            "yare_type": "yaml",
            "bot_lore": "Lore",
        },
    )

    assert response.status_code == 422



def test_publish_version_cartridge_not_found(client):
    response = client.post(
        "/api/cartridges/nonexistent/versions/publish",
        json={
            "version_tag": "1.0.0",
            "first_message": "# Welcome",
            "prompt_directives": "director: {}",
            "yare_rules": "state_schema: {}",
            "yare_type": "yaml",
            "bot_lore": "Lore",
        },
    )

    assert response.status_code == 404



def test_publish_version_not_owner(client, storage, cartridge):
    intruder = storage.create_user(UserAccount(
        username="intruder",
        email="intruder@example.com",
        password_hash="x",
        role=UserRole.CREATOR,
    ))
    app.dependency_overrides[get_current_user] = lambda: intruder.id

    response = client.post(
        f"/api/cartridges/{cartridge.id}/versions/publish",
        json={
            "version_tag": "1.0.0",
            "first_message": "# Welcome",
            "prompt_directives": "director: {}",
            "yare_rules": "state_schema: {}",
            "yare_type": "yaml",
            "bot_lore": "Lore",
        },
    )

    assert response.status_code == 403
