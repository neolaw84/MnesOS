"""
Unit tests for orchestrator.py — the MVP Orchestrator.

All tests run without real LLM calls.  The dry-run mode (llm_*=None) is used
for most assertions; a _BindableFakeModel is used where we need to verify
LLM-driven paths.
"""

import os
import copy
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from MnesOS.orchestrator import Orchestrator, _RETRY_SYSTEM_NOTE


class _BindableFakeModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel extended with a passthrough bind_tools() for tests."""

    def bind_tools(self, tools, **kwargs):
        return self


CARTRIDGE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "cartridges", "generic-rpg"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_llm(*responses: str) -> _BindableFakeModel:
    """Build a fake LLM that returns AIMessages with the given contents in order."""
    return _BindableFakeModel(responses=[AIMessage(content=r) for r in responses])


# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------

class TestOrchestratorInit:
    def test_loads_cartridge(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        assert orch.cartridge is not None
        assert orch.cartridge.yare_config
        assert orch.cartridge.lore_path

    def test_initial_state_has_all_keys(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        state = orch.state
        for key in (
            "client_messages",
            "agent_messages",
            "bot_memory",
            "bot_memory_staging",
            "yare_config",
            "prompt_directives",
            "lore_path",
            "system_notes",
            "retrieved_lore",
            "iteration_count",
            "turn_phase",
        ):
            assert key in state, f"Missing key: {key}"

    def test_initial_client_messages_empty(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        assert orch.state["client_messages"] == []

    def test_bot_memory_seeded_from_cartridge(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        # generic-rpg has a player domain in state_schema
        assert "player" in orch.state["bot_memory"]

    def test_invalid_cartridge_raises(self):
        with pytest.raises(FileNotFoundError):
            Orchestrator("/nonexistent/path/to/cartridge")

    def test_compiled_graph_has_expected_nodes(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        node_names = set(orch._app.get_graph().nodes.keys())
        for expected in ("ResetAgentMessages", "Lore", "CycleTick", "Director",
                         "NPC_Brain", "Narrator", "CleanupAgentMessages"):
            assert expected in node_names, f"Missing node: {expected}"


# ---------------------------------------------------------------------------
# process_turn tests (dry-run — no LLMs)
# ---------------------------------------------------------------------------

class TestProcessTurnDryRun:
    """With llm_*=None the graph runs but produces no LLM output."""

    def test_appends_user_message(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        orch.process_turn("Hello world")
        messages = orch.state["client_messages"]
        assert any(m["role"] == "user" and m["content"] == "Hello world" for m in messages)

    def test_returns_empty_string_without_llm(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        result = orch.process_turn("Look around.")
        assert result == ""

    def test_multiple_turns_accumulate_history(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        orch.process_turn("First turn")
        orch.process_turn("Second turn")
        user_msgs = [m for m in orch.state["client_messages"] if m["role"] == "user"]
        assert len(user_msgs) == 2
        assert user_msgs[0]["content"] == "First turn"
        assert user_msgs[1]["content"] == "Second turn"

    def test_state_is_updated_after_turn(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        orch.process_turn("Some action")
        # After a dry-run turn the state object should be a new dict returned by invoke
        assert isinstance(orch.state, dict)
        assert "bot_memory" in orch.state

    def test_bot_memory_preserved_across_turns(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        initial_memory = copy.deepcopy(orch.state["bot_memory"])
        orch.process_turn("Nothing special")
        # No events were triggered so memory should remain the same
        assert orch.state["bot_memory"] == initial_memory


# ---------------------------------------------------------------------------
# process_turn tests (with fake LLM)
# ---------------------------------------------------------------------------

class TestProcessTurnWithFakeLlm:
    def test_returns_narrator_response(self):
        narrator_llm = make_fake_llm("You stand at the Crossroads.")
        orch = Orchestrator(
            CARTRIDGE_DIR,
            llm_narrator=narrator_llm,
        )
        result = orch.process_turn("I look around.")
        assert result == "You stand at the Crossroads."

    def test_narrator_response_added_to_history(self):
        narrator_llm = make_fake_llm("The goblin growls.")
        orch = Orchestrator(CARTRIDGE_DIR, llm_narrator=narrator_llm)
        orch.process_turn("Attack!")
        assistant_msgs = [
            m for m in orch.state["client_messages"] if m["role"] == "assistant"
        ]
        assert any("goblin" in m["content"] for m in assistant_msgs)

    def test_subsequent_turns_use_updated_state(self):
        """Each turn's fake response differs; both should appear in history."""
        narrator_llm = make_fake_llm("First response.", "Second response.")
        orch = Orchestrator(CARTRIDGE_DIR, llm_narrator=narrator_llm)
        r1 = orch.process_turn("Turn 1")
        r2 = orch.process_turn("Turn 2")
        assert r1 == "First response."
        assert r2 == "Second response."


# ---------------------------------------------------------------------------
# reset() tests
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_client_messages(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        orch.process_turn("Some input")
        orch.reset()
        assert orch.state["client_messages"] == []

    def test_reset_restores_bot_memory(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        original_memory = copy.deepcopy(orch.state["bot_memory"])
        # Manually corrupt memory then reset
        orch._state["bot_memory"]["player"]["hp"] = 0
        orch.reset()
        assert orch.state["bot_memory"] == original_memory

    def test_reset_clears_system_notes(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        orch._state["system_notes"] = ["some note"]
        orch.reset()
        assert orch.state["system_notes"] == []

    def test_reset_after_multiple_turns(self):
        orch = Orchestrator(CARTRIDGE_DIR)
        orch.process_turn("Turn A")
        orch.process_turn("Turn B")
        orch.reset()
        assert orch.state["client_messages"] == []
        assert orch.state["iteration_count"] == 0


# ---------------------------------------------------------------------------
# Error handling / retry tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_retry_on_graph_error(self):
        """If the graph raises, the orchestrator retries once with a system note."""
        orch = Orchestrator(CARTRIDGE_DIR)
        call_count = {"n": 0}

        original_invoke = orch._app.invoke

        def flaky_invoke(state):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ValueError("Simulated transient graph error")
            return original_invoke(state)

        orch._app.invoke = flaky_invoke  # type: ignore[method-assign]
        result = orch.process_turn("Test input")
        assert call_count["n"] == 2
        # The retry system note should have been injected
        # (it was added to state before the retry, then state was replaced by invoke)
        assert isinstance(result, str)

    def test_retry_system_note_injected(self):
        """Verify the retry system note is injected into state before the retry call."""
        orch = Orchestrator(CARTRIDGE_DIR)
        captured_notes = []
        original_invoke = orch._app.invoke
        call_count = {"n": 0}

        def capturing_invoke(state):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("forced error")
            captured_notes.extend(state.get("system_notes", []))
            return original_invoke(state)

        orch._app.invoke = capturing_invoke  # type: ignore[method-assign]
        orch.process_turn("test")
        assert any(_RETRY_SYSTEM_NOTE in note for note in captured_notes)

    def test_persistent_error_is_reraised(self):
        """If both attempts fail, the exception is re-raised."""
        orch = Orchestrator(CARTRIDGE_DIR)

        def always_fail(state):
            raise RuntimeError("always fails")

        orch._app.invoke = always_fail  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="always fails"):
            orch.process_turn("test")


# ---------------------------------------------------------------------------
# State isolation tests
# ---------------------------------------------------------------------------

class TestStateIsolation:
    def test_two_orchestrators_independent(self):
        """Two Orchestrator instances do not share state."""
        orch_a = Orchestrator(CARTRIDGE_DIR)
        orch_b = Orchestrator(CARTRIDGE_DIR)
        orch_a.process_turn("Player A's action")
        assert orch_b.state["client_messages"] == []

    def test_reset_does_not_mutate_cartridge_initial_state(self):
        """reset() must deep-copy initial_state so mutations don't leak."""
        orch = Orchestrator(CARTRIDGE_DIR)
        original = copy.deepcopy(orch.cartridge.initial_state)
        orch._state["bot_memory"]["player"]["hp"] = 0
        orch.reset()
        assert orch.cartridge.initial_state == original
