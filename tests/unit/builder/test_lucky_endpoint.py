"""
Tests for [MnesOS-260525-09] Backend – "I'm feeling Lucky" Cartridge Generator Agent.

TDD: Tests for the API endpoint that invokes the builder agent.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from MnesOS.api.app import app
from MnesOS.api.deps import get_current_user, get_llm_clients, get_storage
from MnesOS.storage import SQLite3PhysicalComponent, UserAccount, UserRole


MOCK_USER_ID = "builder-test-user-001"


@pytest.fixture
def storage():
    store = SQLite3PhysicalComponent(db_path=":memory:")
    store.initialize()
    return store


@pytest.fixture
def client(storage):
    user = storage.create_user(
        UserAccount(
            username="builder_tester", email="b@t.com",
            password_hash="x", role=UserRole.PLAYER,
        )
    )
    global MOCK_USER_ID
    MOCK_USER_ID = user.id

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_ID
    app.dependency_overrides[get_llm_clients] = lambda: {"openrouter_key": "test-key"}

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestLuckyGenerateEndpoint:
    """Test the POST /api/builder/generate endpoint."""

    def test_generate_returns_200_with_cartridge_files(self, client):
        """A valid requirements prompt returns a complete cartridge."""
        resp = client.post(
            "/api/builder/generate",
            json={"requirements": "Create a simple dungeon crawler game"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "bot_lore" in data
        assert "first_message" in data
        assert "prompt_directives" in data
        assert "yare_spec" in data

    def test_generate_with_existing_content_for_refinement(self, client):
        """Providing existing content triggers iterative refinement mode."""
        resp = client.post(
            "/api/builder/generate",
            json={
                "requirements": "Make the combat system harder",
                "existing_content": {
                    "bot_lore": "# A dungeon",
                    "first_message": "Welcome",
                    "prompt_directives": "director: Strict narrator",
                    "yare_spec": "state_schema:\n  player:\n    hp: {type: int, default: 100}",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "bot_lore" in data
        assert "yare_spec" in data

    def test_generate_requires_requirements_field(self, client):
        """Missing requirements field returns 422."""
        resp = client.post(
            "/api/builder/generate",
            json={},
        )
        assert resp.status_code == 422

    def test_generate_empty_requirements_returns_422(self, client):
        """Empty string requirements returns 422."""
        resp = client.post(
            "/api/builder/generate",
            json={"requirements": ""},
        )
        assert resp.status_code == 422
