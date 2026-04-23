"""
Unit tests for cartridge and cartridge version API endpoints.
"""

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from MnesOS.api.app import app
from MnesOS.api.deps import get_current_user, get_storage
from MnesOS.storage import SQLite3PhysicalComponent, UserAccount, UserRole, Cartridge, CartridgeVersion, Visibility

MOCK_USER_ID = "test-cartridge-user"


@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(db_path=":memory:")
    store.initialize()
    return store


@pytest.fixture
def user(storage):
    return storage.create_user(UserAccount(
        username="creator", email="c@c.com",
        password_hash="x", role=UserRole.CREATOR,
    ))


@pytest.fixture
def cartridge(storage, user):
    return storage.create_cartridge(Cartridge(
        creator_id=user.id, title="Test Cartridge",
        description="desc", genre="rpg", visibility=Visibility.PUBLIC,
    ))


@pytest.fixture
def version(storage, cartridge):
    return storage.create_cartridge_version(CartridgeVersion(
        cartridge_id=cartridge.id, version_tag="1.0",
        yare_spec={"state_schema": {}, "events": {}, "macros": {}},
        prompt_directives={}, bot_lore="Some lore.", first_message="",
        checksum="abc123",
    ))


@pytest.fixture
def client(storage, user):
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: user.id
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Cartridge CRUD
# ---------------------------------------------------------------------------

class TestCreateCartridge:
    def test_create_cartridge_returns_201(self, client):
        resp = client.post("/api/cartridges", json={
            "title": "New Game", "description": "A game", "genre": "rpg", "visibility": "PUBLIC"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Game"
        assert "id" in data

    def test_create_cartridge_invalid_visibility(self, client):
        resp = client.post("/api/cartridges", json={
            "title": "X", "description": "", "genre": "", "visibility": "INVALID"
        })
        assert resp.status_code == 422


class TestListCartridges:
    def test_list_cartridges_empty(self, client):
        resp = client.get("/api/cartridges")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_cartridges_returns_created(self, client, cartridge):
        resp = client.get("/api/cartridges")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Cartridge"


class TestGetCartridge:
    def test_get_existing_cartridge(self, client, cartridge):
        resp = client.get(f"/api/cartridges/{cartridge.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cartridge.id

    def test_get_missing_cartridge_returns_404(self, client):
        resp = client.get("/api/cartridges/nonexistent")
        assert resp.status_code == 404


class TestUpdateCartridge:
    def test_update_cartridge_title(self, client, cartridge):
        resp = client.put(f"/api/cartridges/{cartridge.id}", json={"title": "Updated Title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_cartridge_visibility(self, client, cartridge):
        resp = client.put(f"/api/cartridges/{cartridge.id}", json={"visibility": "PRIVATE"})
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PRIVATE"

    def test_update_cartridge_wrong_owner_returns_403(self, client, storage, cartridge):
        other_user = storage.create_user(UserAccount(
            username="other", email="o@o.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other_user.id
        resp = client.put(f"/api/cartridges/{cartridge.id}", json={"title": "Hijacked"})
        assert resp.status_code == 403

    def test_update_missing_cartridge_returns_404(self, client):
        resp = client.put("/api/cartridges/nonexistent", json={"title": "X"})
        assert resp.status_code == 404


class TestDeleteCartridge:
    def test_delete_cartridge_returns_204(self, client, cartridge):
        resp = client.delete(f"/api/cartridges/{cartridge.id}")
        assert resp.status_code == 204

    def test_delete_cartridge_wrong_owner_returns_403(self, client, storage, cartridge):
        other = storage.create_user(UserAccount(
            username="intruder", email="i@i.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.delete(f"/api/cartridges/{cartridge.id}")
        assert resp.status_code == 403

    def test_delete_missing_cartridge_returns_404(self, client):
        resp = client.delete("/api/cartridges/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CartridgeVersion CRUD
# ---------------------------------------------------------------------------

MINIMAL_YARE = b"""
state_schema: {}
events: {}
macros: {}
"""

MINIMAL_LORE = b"Some generic lore content."


class TestCreateCartridgeVersion:
    def test_upload_individual_files_returns_201(self, client, cartridge):
        resp = client.post(
            f"/api/cartridges/{cartridge.id}/versions",
            data={"version_tag": "2.0"},
            files={
                "yare_file": ("yare.yaml", MINIMAL_YARE, "text/plain"),
                "lore_file": ("bot_lore.md", MINIMAL_LORE, "text/plain"),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version_tag"] == "2.0"
        assert data["cartridge_id"] == cartridge.id

    def test_upload_zip_returns_201(self, client, cartridge):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("yare.yaml", MINIMAL_YARE)
            zf.writestr("bot_lore.md", MINIMAL_LORE)
        buf.seek(0)
        resp = client.post(
            f"/api/cartridges/{cartridge.id}/versions",
            data={"version_tag": "3.0"},
            files={"zip_file": ("cartridge.zip", buf.read(), "application/zip")},
        )
        assert resp.status_code == 201
        assert resp.json()["version_tag"] == "3.0"

    def test_upload_bad_zip_returns_422(self, client, cartridge):
        resp = client.post(
            f"/api/cartridges/{cartridge.id}/versions",
            data={"version_tag": "x"},
            files={"zip_file": ("bad.zip", b"not a zip", "application/zip")},
        )
        assert resp.status_code == 422

    def test_upload_zip_missing_yare_returns_422(self, client, cartridge):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("bot_lore.md", MINIMAL_LORE)  # no yare.yaml
        buf.seek(0)
        resp = client.post(
            f"/api/cartridges/{cartridge.id}/versions",
            data={"version_tag": "x"},
            files={"zip_file": ("cartridge.zip", buf.read(), "application/zip")},
        )
        assert resp.status_code == 422

    def test_upload_to_missing_cartridge_returns_404(self, client):
        resp = client.post(
            "/api/cartridges/nonexistent/versions",
            data={"version_tag": "1.0"},
            files={
                "yare_file": ("yare.yaml", MINIMAL_YARE, "text/plain"),
                "lore_file": ("bot_lore.md", MINIMAL_LORE, "text/plain"),
            },
        )
        assert resp.status_code == 404

    def test_upload_no_files_returns_422(self, client, cartridge):
        resp = client.post(
            f"/api/cartridges/{cartridge.id}/versions",
            data={"version_tag": "1.0"},
        )
        assert resp.status_code == 422


class TestListCartridgeVersions:
    def test_list_versions_empty(self, client, cartridge):
        resp = client.get(f"/api/cartridges/{cartridge.id}/versions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_versions_returns_created(self, client, cartridge, version):
        resp = client.get(f"/api/cartridges/{cartridge.id}/versions")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["version_tag"] == "1.0"

    def test_list_versions_missing_cartridge_returns_404(self, client):
        resp = client.get("/api/cartridges/nonexistent/versions")
        assert resp.status_code == 404


class TestGetCartridgeVersion:
    def test_get_version(self, client, cartridge, version):
        resp = client.get(f"/api/cartridges/{cartridge.id}/versions/{version.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == version.id

    def test_get_version_wrong_cartridge_returns_404(self, client, storage, cartridge, version):
        # Create a second cartridge
        other = storage.create_cartridge(Cartridge(
            creator_id=cartridge.creator_id, title="Other", description="", genre="", visibility=Visibility.PRIVATE
        ))
        resp = client.get(f"/api/cartridges/{other.id}/versions/{version.id}")
        assert resp.status_code == 404

    def test_get_version_missing_returns_404(self, client, cartridge):
        resp = client.get(f"/api/cartridges/{cartridge.id}/versions/nonexistent")
        assert resp.status_code == 404


class TestDeleteCartridgeVersion:
    def test_delete_version_returns_204(self, client, cartridge, version):
        resp = client.delete(f"/api/cartridges/{cartridge.id}/versions/{version.id}")
        assert resp.status_code == 204

    def test_delete_version_wrong_owner_returns_403(self, client, storage, cartridge, version):
        other = storage.create_user(UserAccount(
            username="thief", email="t@t.com", password_hash="x", role=UserRole.PLAYER
        ))
        app.dependency_overrides[get_current_user] = lambda: other.id
        resp = client.delete(f"/api/cartridges/{cartridge.id}/versions/{version.id}")
        assert resp.status_code == 403

    def test_delete_version_missing_returns_404(self, client, cartridge):
        resp = client.delete(f"/api/cartridges/{cartridge.id}/versions/nonexistent")
        assert resp.status_code == 404
