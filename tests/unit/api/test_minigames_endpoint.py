"""
Unit tests for the minigame registry discovery endpoint.

TDD: Tests verify the /api/minigames endpoint returns available
minigame configurations from the compiled schema.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


class TestMinigamesEndpoint:
    """Test GET /api/minigames returns minigame registry data."""

    @pytest.fixture
    def client(self):
        from MnesOS.api.app import app
        return TestClient(app)

    def test_get_minigames_returns_list(self, client):
        """GET /api/minigames returns a JSON list of minigames."""
        resp = client.get("/api/minigames")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_minigame_entry_has_required_fields(self, client):
        """Each minigame entry has minigame_id, difficulty_schema, output_schema."""
        resp = client.get("/api/minigames")
        assert resp.status_code == 200
        data = resp.json()
        if len(data) > 0:
            entry = data[0]
            assert "minigame_id" in entry
            assert "difficulty_schema" in entry
            assert "output_schema" in entry

    def test_lights_out_in_registry(self, client):
        """The lights_out minigame appears in the registry."""
        resp = client.get("/api/minigames")
        data = resp.json()
        ids = [m["minigame_id"] for m in data]
        assert "lights_out" in ids
