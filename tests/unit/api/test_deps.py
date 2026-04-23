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
    assert get_current_user("user-123") == "user-123"

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
    assert get_llm_clients(None) is None

def test_get_llm_clients_with_key():
    # Mock ChatOpenAI
    try:
        from unittest.mock import MagicMock
        import sys
        mock_langchain = MagicMock()
        sys.modules["langchain_openai"] = mock_langchain
        
        clients = get_llm_clients("test-key")
        assert clients is not None
        assert "director" in clients
        assert "narrator" in clients
        assert "npc" in clients
    finally:
        if "langchain_openai" in sys.modules:
            del sys.modules["langchain_openai"]

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
