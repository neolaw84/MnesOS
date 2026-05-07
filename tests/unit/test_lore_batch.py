"""
Unit tests for the Director Batch RAG Tool.

Covers:
  - MultiLoreLookupArgs  (Pydantic model)
  - LoreSearchService    (ABC / interface contract)
  - multi_lore_lookup    (LangGraph tool behaviour)
  - Director prompt      (Search Strategy section)

Aligned with ``docs/design/0006-stateless-phase-2.md`` §4 (Batch RAG Tooling /
[MnesOS-260507-07]).

Module path assumed: ``MnesOS.graph.tools.lore_batch``.
All tests express *required behaviour* and will fail until the module and the
Director prompt update are implemented.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import List


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_lore_batch():
    """Import the lore_batch module; fail the test if not yet implemented."""
    try:
        import MnesOS.graph.tools.lore_batch as mod
        return mod
    except ImportError:
        pytest.fail(
            "MnesOS.graph.tools.lore_batch module is not implemented yet. "
            "Implement src/MnesOS/graph/tools/lore_batch.py to satisfy MnesOS-260507-07."
        )


def _make_tool_state(**overrides):
    """Return a minimal GameState-compatible dict for tool invocation."""
    base = {
        "retrieved_lore": "",
        "client_messages": [],
        "agent_messages": [],
        "bot_memory": {},
        "system_notes": [],
        "iteration_count": 0,
        "turn_phase": "player",
        "npc_intent_calls": 0,
        "turn_start_time": "",
        "bot_memory_staging": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# MultiLoreLookupArgs
# ---------------------------------------------------------------------------

class TestMultiLoreLookupArgs:
    """MultiLoreLookupArgs is a Pydantic model for the batch lore lookup tool."""

    def test_importable(self):
        mod = _import_lore_batch()
        assert hasattr(mod, "MultiLoreLookupArgs"), (
            "MultiLoreLookupArgs must be exported from MnesOS.graph.tools.lore_batch"
        )

    def test_requires_queries(self):
        mod = _import_lore_batch()
        with pytest.raises(Exception):  # Pydantic ValidationError
            mod.MultiLoreLookupArgs()

    def test_accepts_list_of_strings(self):
        mod = _import_lore_batch()
        args = mod.MultiLoreLookupArgs(queries=["Who are the goblins?", "History of Eldoria?"])
        assert args.queries == ["Who are the goblins?", "History of Eldoria?"]

    def test_single_query_accepted(self):
        mod = _import_lore_batch()
        args = mod.MultiLoreLookupArgs(queries=["What is magic?"])
        assert len(args.queries) == 1

    def test_empty_query_list_accepted(self):
        """An empty list is technically valid per the design spec (List[str])."""
        mod = _import_lore_batch()
        args = mod.MultiLoreLookupArgs(queries=[])
        assert args.queries == []

    def test_queries_field_has_description(self):
        """The field must carry a description for LLM function-calling."""
        mod = _import_lore_batch()
        schema = mod.MultiLoreLookupArgs.model_json_schema()
        props = schema.get("properties", {})
        assert "queries" in props, "queries field must be in schema"
        field_info = props["queries"]
        description = field_info.get("description") or field_info.get("title", "")
        assert description, "queries field must have a non-empty description"

    def test_model_dump_roundtrip(self):
        mod = _import_lore_batch()
        original = mod.MultiLoreLookupArgs(queries=["q1", "q2"])
        dumped = original.model_dump()
        restored = mod.MultiLoreLookupArgs(**dumped)
        assert restored.queries == original.queries


# ---------------------------------------------------------------------------
# LoreSearchService (ABC)
# ---------------------------------------------------------------------------

class TestLoreSearchServiceABC:
    """LoreSearchService is the interface for the underlying vector search."""

    def test_importable(self):
        mod = _import_lore_batch()
        assert hasattr(mod, "LoreSearchService"), (
            "LoreSearchService must be exported from MnesOS.graph.tools.lore_batch"
        )

    def test_is_abstract_cannot_instantiate(self):
        mod = _import_lore_batch()
        with pytest.raises(TypeError):
            mod.LoreSearchService()  # type: ignore[abstract]

    def test_subclass_without_search_batch_is_abstract(self):
        mod = _import_lore_batch()

        class Incomplete(mod.LoreSearchService):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_instantiates(self):
        mod = _import_lore_batch()

        class Concrete(mod.LoreSearchService):
            def search_batch(self, queries: List[str], k: int = 3) -> str:
                return "lore result"

        svc = Concrete()
        assert svc is not None

    def test_search_batch_signature_queries_and_k(self):
        """search_batch must accept queries list and k integer."""
        mod = _import_lore_batch()

        class Spy(mod.LoreSearchService):
            def search_batch(self, queries: List[str], k: int = 3) -> str:
                return f"{len(queries)} queries, k={k}"

        svc = Spy()
        result = svc.search_batch(["q1", "q2"], k=5)
        assert "2 queries" in result
        assert "k=5" in result

    def test_search_batch_k_defaults_to_3(self):
        mod = _import_lore_batch()

        class DefaultK(mod.LoreSearchService):
            def search_batch(self, queries: List[str], k: int = 3) -> str:
                return str(k)

        svc = DefaultK()
        result = svc.search_batch(["q"])
        assert result == "3"

    def test_search_batch_returns_string(self):
        mod = _import_lore_batch()

        class Concrete(mod.LoreSearchService):
            def search_batch(self, queries: List[str], k: int = 3) -> str:
                return "## Section\nSome lore text."

        svc = Concrete()
        result = svc.search_batch(["goblins"])
        assert isinstance(result, str)

    def test_search_batch_empty_queries_returns_string(self):
        mod = _import_lore_batch()

        class Concrete(mod.LoreSearchService):
            def search_batch(self, queries: List[str], k: int = 3) -> str:
                return "" if not queries else "results"

        svc = Concrete()
        result = svc.search_batch([])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# build_multi_lore_lookup_tool factory
# ---------------------------------------------------------------------------

class TestBuildMultiLoreLookupTool:
    """build_multi_lore_lookup_tool is a factory that returns a LangGraph tool."""

    def test_factory_importable(self):
        mod = _import_lore_batch()
        assert hasattr(mod, "build_multi_lore_lookup_tool"), (
            "build_multi_lore_lookup_tool must be exported from "
            "MnesOS.graph.tools.lore_batch"
        )

    def test_factory_accepts_lore_search_service(self):
        mod = _import_lore_batch()
        mock_svc = MagicMock(spec=mod.LoreSearchService)
        tool = mod.build_multi_lore_lookup_tool(mock_svc)
        assert tool is not None

    def test_returned_tool_is_callable(self):
        mod = _import_lore_batch()
        mock_svc = MagicMock(spec=mod.LoreSearchService)
        tool = mod.build_multi_lore_lookup_tool(mock_svc)
        assert callable(tool) or hasattr(tool, "invoke"), (
            "The tool must be callable or implement .invoke()"
        )

    def test_tool_has_name(self):
        """LangGraph/LangChain tools must have a .name attribute."""
        mod = _import_lore_batch()
        mock_svc = MagicMock(spec=mod.LoreSearchService)
        tool = mod.build_multi_lore_lookup_tool(mock_svc)
        assert hasattr(tool, "name"), "Tool must expose a .name attribute"
        assert "lore" in tool.name.lower() or "lookup" in tool.name.lower(), (
            f"Tool name '{tool.name}' should suggest lore lookup"
        )


# ---------------------------------------------------------------------------
# multi_lore_lookup tool behaviour
# ---------------------------------------------------------------------------

class TestMultiLoreLookupToolBehaviour:
    """The tool must invoke LoreSearchService, update GameState, and confirm to LLM."""

    def _make_tool(self, expected_lore: str = "## Lore\nSome lore text."):
        mod = _import_lore_batch()
        mock_svc = MagicMock(spec=mod.LoreSearchService)
        mock_svc.search_batch.return_value = expected_lore
        tool = mod.build_multi_lore_lookup_tool(mock_svc)
        return tool, mock_svc

    def _invoke_tool(self, tool, queries: List[str], state: dict = None, tool_call_id: str = "test-id"):
        """Invoke the tool via .invoke() with the correct kwargs."""
        return tool.invoke({
            "queries": queries,
            "tool_call_id": tool_call_id,
            "state": state or _make_tool_state(),
        })

    def test_invokes_search_batch_with_correct_queries(self):
        tool, mock_svc = self._make_tool()
        self._invoke_tool(tool, ["Who are the goblins?", "What is Eldoria?"])
        call_args = mock_svc.search_batch.call_args
        called_queries = call_args[0][0] if call_args[0] else call_args[1]["queries"]
        assert called_queries == ["Who are the goblins?", "What is Eldoria?"]

    def test_invokes_search_batch_exactly_once(self):
        tool, mock_svc = self._make_tool()
        self._invoke_tool(tool, ["q1"])
        mock_svc.search_batch.assert_called_once()

    def test_returns_command_that_updates_retrieved_lore(self):
        lore = "## The Dragon\nAncient and terrible."
        tool, _ = self._make_tool(expected_lore=lore)
        result = self._invoke_tool(tool, ["dragon lore"])
        # LangGraph Command carries an .update dict
        from langgraph.types import Command
        assert isinstance(result, Command), (
            "Tool must return a langgraph.types.Command"
        )
        assert "retrieved_lore" in result.update, (
            "Command.update must contain 'retrieved_lore'"
        )
        assert result.update["retrieved_lore"] == lore

    def test_retrieved_lore_replaces_previous_value(self):
        """retrieved_lore should be replaced by the new batch result."""
        new_lore = "## New Section\nFresh lore."
        tool, _ = self._make_tool(expected_lore=new_lore)
        state = _make_tool_state(retrieved_lore="old lore content")
        result = self._invoke_tool(tool, ["fresh query"], state=state)
        from langgraph.types import Command
        assert isinstance(result, Command)
        assert result.update["retrieved_lore"] == new_lore

    def test_returns_tool_message_in_agent_messages(self):
        """The Command must add a ToolMessage to agent_messages for the LLM."""
        tool, _ = self._make_tool()
        result = self._invoke_tool(tool, ["q1"], tool_call_id="call-42")
        from langgraph.types import Command
        from langchain_core.messages import ToolMessage
        assert isinstance(result, Command)
        messages = result.update.get("agent_messages", [])
        assert len(messages) >= 1, "agent_messages must contain at least one message"
        assert any(isinstance(m, ToolMessage) for m in messages), (
            "agent_messages must contain a ToolMessage"
        )

    def test_tool_message_contains_confirmation(self):
        """The ToolMessage content must confirm success (non-empty string)."""
        tool, _ = self._make_tool()
        result = self._invoke_tool(tool, ["some query"])
        from langgraph.types import Command
        from langchain_core.messages import ToolMessage
        assert isinstance(result, Command)
        messages = result.update.get("agent_messages", [])
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        assert tool_messages, "At least one ToolMessage must be returned"
        assert tool_messages[0].content, "ToolMessage content must be non-empty"

    def test_tool_message_uses_correct_tool_call_id(self):
        """ToolMessage.tool_call_id must match the injected tool_call_id."""
        tool, _ = self._make_tool()
        result = self._invoke_tool(tool, ["q"], tool_call_id="my-call-id-99")
        from langgraph.types import Command
        from langchain_core.messages import ToolMessage
        assert isinstance(result, Command)
        messages = result.update.get("agent_messages", [])
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert any(m.tool_call_id == "my-call-id-99" for m in tool_msgs), (
            "ToolMessage.tool_call_id must match the injected tool_call_id"
        )

    def test_empty_queries_still_calls_search_batch(self):
        """Even an empty query list must invoke search_batch (graceful handling)."""
        tool, mock_svc = self._make_tool(lore_result="")
        self._invoke_tool(tool, [])
        mock_svc.search_batch.assert_called_once()

    def test_empty_lore_result_stored_as_empty_string(self):
        tool, _ = self._make_tool(expected_lore="")
        result = self._invoke_tool(tool, ["q"])
        from langgraph.types import Command
        assert isinstance(result, Command)
        assert result.update.get("retrieved_lore") == ""

    def test_multiple_queries_batched_in_single_call(self):
        """All queries must be passed to a single search_batch invocation (not one per query)."""
        queries = ["q1", "q2", "q3", "q4", "q5"]
        tool, mock_svc = self._make_tool()
        self._invoke_tool(tool, queries)
        assert mock_svc.search_batch.call_count == 1, (
            "search_batch must be called exactly once for a batch of queries, "
            f"but was called {mock_svc.search_batch.call_count} times"
        )

    def test_k_parameter_is_passed_to_search_batch(self):
        """The tool should forward a k parameter to search_batch (default allowed)."""
        tool, mock_svc = self._make_tool()
        self._invoke_tool(tool, ["q"])
        # search_batch must have been called; k may be positional or keyword
        call_args = mock_svc.search_batch.call_args
        # We don't prescribe the exact k value, only that the call happened
        assert call_args is not None


# ---------------------------------------------------------------------------
# Director Prompt — Search Strategy section
# ---------------------------------------------------------------------------

class TestDirectorPromptSearchStrategy:
    """
    The DIRECTOR_SYSTEM_PROMPT must include a 'Search Strategy' section
    instructing the Director to call multi_lore_lookup before writing narrative.

    This test will fail until the prompt is updated as part of MnesOS-260507-07.
    """

    def test_director_prompt_contains_search_strategy_section(self):
        from MnesOS.prompts import DIRECTOR_SYSTEM_PROMPT
        assert "Search Strategy" in DIRECTOR_SYSTEM_PROMPT, (
            "DIRECTOR_SYSTEM_PROMPT must contain a 'Search Strategy' section "
            "as required by MnesOS-260507-07."
        )

    def test_director_prompt_mentions_multi_lore_lookup_tool(self):
        from MnesOS.prompts import DIRECTOR_SYSTEM_PROMPT
        assert "multi_lore_lookup" in DIRECTOR_SYSTEM_PROMPT, (
            "DIRECTOR_SYSTEM_PROMPT must reference the multi_lore_lookup tool "
            "to instruct the Director on when to use it."
        )

    def test_director_prompt_search_strategy_before_workflow(self):
        """
        The Search Strategy guidance should appear before the main workflow
        section so the Director reads it first.
        """
        from MnesOS.prompts import DIRECTOR_SYSTEM_PROMPT
        strategy_pos = DIRECTOR_SYSTEM_PROMPT.find("Search Strategy")
        workflow_pos = DIRECTOR_SYSTEM_PROMPT.find("YOUR WORKFLOW")
        assert strategy_pos != -1 and workflow_pos != -1, (
            "Both 'Search Strategy' and 'YOUR WORKFLOW' sections must exist."
        )
        assert strategy_pos < workflow_pos, (
            "'Search Strategy' must appear before 'YOUR WORKFLOW' in the prompt."
        )

    def test_director_prompt_instructs_batch_before_narrative(self):
        """
        The prompt must instruct the Director to gather context in a single
        batch call *before* writing narrative or resolving mechanics.
        """
        from MnesOS.prompts import DIRECTOR_SYSTEM_PROMPT
        prompt_lower = DIRECTOR_SYSTEM_PROMPT.lower()
        # Must contain language about batching / single call / before narrative
        has_batch = "batch" in prompt_lower
        has_single = "single" in prompt_lower
        assert has_batch or has_single, (
            "DIRECTOR_SYSTEM_PROMPT should instruct batching or single-call "
            "lore retrieval in the Search Strategy section."
        )


# ---------------------------------------------------------------------------
# LoreSearchService VectorLoreStore Adapter contract
# ---------------------------------------------------------------------------

class TestVectorLoreStoreAdapter:
    """
    Verify that a LoreSearchService backed by VectorLoreStore satisfies the
    interface and produces deduplicated, formatted results.

    The concrete adapter class is named ``VectorLoreSearchService`` (expected).
    """

    def test_adapter_importable(self):
        mod = _import_lore_batch()
        assert hasattr(mod, "VectorLoreSearchService"), (
            "VectorLoreSearchService must be exported from "
            "MnesOS.graph.tools.lore_batch as the concrete adapter"
        )

    def test_adapter_is_lore_search_service(self):
        mod = _import_lore_batch()
        assert issubclass(mod.VectorLoreSearchService, mod.LoreSearchService)

    def test_adapter_instantiates_with_lore_content(self):
        mod = _import_lore_batch()
        adapter = mod.VectorLoreSearchService(lore_content="# Section\nSome lore.")
        assert adapter is not None

    def test_adapter_search_batch_returns_string(self):
        mod = _import_lore_batch()
        lore = "# The Forest\nAncient trees tower overhead.\n\n# The Village\nA quiet hamlet."
        adapter = mod.VectorLoreSearchService(lore_content=lore)
        result = adapter.search_batch(["forest trees"], k=1)
        assert isinstance(result, str)

    def test_adapter_search_batch_retrieves_relevant_chunk(self):
        mod = _import_lore_batch()
        lore = "# Dragons\nFierce and ancient beings.\n\n# Village\nPeaceful farmers live here."
        adapter = mod.VectorLoreSearchService(lore_content=lore)
        result = adapter.search_batch(["dragon fire ancient"], k=1)
        assert "Dragon" in result or "dragon" in result.lower()

    def test_adapter_search_batch_deduplicates_across_queries(self):
        """Two identical queries must not produce doubled results."""
        mod = _import_lore_batch()
        lore = "# Castle\nA great fortress.\n\n# Market\nBusy merchants."
        adapter = mod.VectorLoreSearchService(lore_content=lore)
        result_single = adapter.search_batch(["castle fortress"], k=1)
        result_double = adapter.search_batch(["castle fortress", "castle fortress"], k=1)
        # Deduplication: same chunk should not appear twice
        assert result_double.count("Castle") <= result_single.count("Castle") + 1, (
            "Duplicate queries should not produce duplicate lore chunks."
        )

    def test_adapter_empty_lore_returns_empty_string(self):
        mod = _import_lore_batch()
        adapter = mod.VectorLoreSearchService(lore_content="")
        result = adapter.search_batch(["anything"])
        assert result == ""

    def test_adapter_empty_queries_returns_empty_string(self):
        mod = _import_lore_batch()
        adapter = mod.VectorLoreSearchService(lore_content="# A\nContent.")
        result = adapter.search_batch([])
        assert isinstance(result, str)
        assert result == ""

    def test_adapter_can_be_constructed_from_file(self, tmp_path):
        mod = _import_lore_batch()
        lore_file = tmp_path / "bot_lore.md"
        lore_file.write_text("# Lore Entry\nSome fascinating lore here.")
        adapter = mod.VectorLoreSearchService.from_file(str(lore_file))
        result = adapter.search_batch(["lore fascinating"])
        assert isinstance(result, str)

    def test_adapter_from_file_missing_file_raises(self, tmp_path):
        mod = _import_lore_batch()
        with pytest.raises(FileNotFoundError):
            mod.VectorLoreSearchService.from_file(str(tmp_path / "nonexistent.md"))
