"""
Unit tests for the FastAPI dependencies in MnesOS.
"""

import os
import pytest
from fastapi import HTTPException, Header
from MnesOS.api.deps import get_current_user, verify_instance_ownership, get_llm_clients, get_storage
from MnesOS.storage import SQLite3PhysicalComponent, GameInstance, GameStatus

class MockStorage:
    def __init__(self, instance=None):
        self.instance = instance
    def get_game_instance(self, instance_id):
        return self.instance

def test_get_current_user_valid():
    from unittest.mock import MagicMock
    mock_request = MagicMock()
    # No x-provider → defaults to openrouter; no authorization header → falls back to x-user-id
    mock_request.headers = {"x-user-id": "user-123"}
    assert get_current_user(mock_request) == "user-123"

def test_verify_instance_ownership_success():
    storage = MockStorage(GameInstance(id="inst-1", user_id="user-1", persona_id="p1", version_id="v1", status=GameStatus.ACTIVE))
    assert verify_instance_ownership("inst-1", "user-1", storage) == "inst-1"

def test_verify_instance_ownership_not_found():
    storage = MockStorage(None)
    with pytest.raises(HTTPException) as exc:
        verify_instance_ownership("inst-1", "user-1", storage)
    assert exc.value.status_code == 404

def test_verify_instance_ownership_forbidden():
    storage = MockStorage(GameInstance(id="inst-1", user_id="user-owner", persona_id="p1", version_id="v1", status=GameStatus.ACTIVE))
    with pytest.raises(HTTPException) as exc:
        verify_instance_ownership("inst-1", "user-intruder", storage)
    assert exc.value.status_code == 403

def test_get_llm_clients_none():
    from unittest.mock import MagicMock
    mock_request = MagicMock()
    mock_request.headers = {}  # no provider, no key
    # LocalAuthProvider doesn't implement LLMAuthValidator → returns None
    result = get_llm_clients(mock_request)
    assert result is None

def test_get_llm_clients_with_openrouter_key():
    from unittest.mock import MagicMock
    mock_request = MagicMock()
    mock_request.headers = {
        "x-provider": "openrouter",
        "x-openrouter-key": "sk-test-key",
    }
    result = get_llm_clients(mock_request)
    assert result is not None
    assert result.get("openrouter_key") == "sk-test-key"

def test_get_llm_clients_missing_key_returns_none():
    from unittest.mock import MagicMock
    mock_request = MagicMock()
    mock_request.headers = {"x-provider": "openrouter"}  # no key header
    result = get_llm_clients(mock_request)
    assert result is None

def test_get_storage_initialization():
    # We test it doesn't crash and returns a component
    # Use a temp env var to avoid hitting actual DB
    os.environ["MNESOS_DB_PATH"] = ":memory:"
    from MnesOS.api import deps
    deps._storage_instance = None # reset singleton
    storage = get_storage()
    assert isinstance(storage, SQLite3PhysicalComponent)
    # Check singleton
    assert get_storage() is storage
