from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from ..shared import make_state, _BindableFakeModel
from MnesOS.graph.nodes.director import director_node
from MnesOS.graph.tools.yare import build_yare_event_tools

class TestDirectorNode:
    def test_sets_turn_phase_player(self):
        state = make_state(client_messages=[{"role": "user", "content": "I look around."}])
        result = director_node(state)
        assert result["turn_phase"] == "player"

    def test_increments_iteration_count(self):
        state = make_state(iteration_count=0)
        result = director_node(state)
        assert result["iteration_count"] == 1

    def test_ambient_action_produces_no_tool_calls(self):
        state = make_state(client_messages=[{"role": "user", "content": "I wink at the merchant."}])
        result = director_node(state)
        # Without an LLM wired, no agent_messages are produced
        assert result.get("agent_messages", []) == []

    def test_directives_are_appended_when_present(self):
        """Verifies the node doesn't crash with directives when no LLM is wired."""
        state = make_state(
            prompt_directives={"director": "Prefer combat events."},
            client_messages=[{"role": "user", "content": "I look around."}],
        )
        result = director_node(state)
        assert "turn_phase" in result  # node ran without error

class TestDirectorNodeWithLLM:
    def test_llm_is_invoked(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        director_node(state, llm=fake_llm)
        fake_llm.bind_tools.assert_called_once()
        fake_llm.bind_tools.return_value.invoke.assert_called_once()

    def test_dynamic_tools_are_bound(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        dynamic_tools = build_yare_event_tools(state["yare_config"])
        director_node(state, llm=fake_llm, tools=dynamic_tools)
        bound_tools = fake_llm.bind_tools.call_args[0][0]
        assert len(bound_tools) > 0
        assert hasattr(bound_tools[0], "name")

    def test_llm_tool_calls_stored_in_agent_messages(self):
        ai_msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "generic_check",
                "args": {"stat": "charm", "difficulty": 12},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        assert "tool_calls" not in result
        assert len(result["agent_messages"][0].tool_calls) == 1
        assert result["agent_messages"][0].tool_calls[0]["name"] == "generic_check"

    def test_ai_message_is_added_to_agent_messages(self):
        ai_msg = AIMessage(content="", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I examine the ruins."}])
        result = director_node(state, llm=fake_llm)
        assert result["agent_messages"] == [ai_msg]

    def test_llm_no_tool_calls_agent_messages_has_empty_tool_calls(self):
        ai_msg = AIMessage(content="Just looking around.", tool_calls=[])
        fake_llm = _BindableFakeModel(responses=[ai_msg])
        state = make_state(client_messages=[{"role": "user", "content": "I look around."}])
        result = director_node(state, llm=fake_llm)
        assert result["agent_messages"][0].tool_calls == []

    def test_directive_included_in_prompt_passed_to_llm(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state(
            prompt_directives={"director": "Prefer skill checks over combat."},
            client_messages=[{"role": "user", "content": "I parley with the guard."}],
        )
        director_node(state, llm=fake_llm)
        call_arg = fake_llm.bind_tools.return_value.invoke.call_args
        assert call_arg is not None
        prompt_text = str(call_arg)
        # Fix: the prompt_text from str(call_arg) might look different depending on LangChain versions
        # We can just check the content of the system message if we wanted but this works if the patch is correct.
        assert "Prefer skill checks over combat." in prompt_text

    def test_game_time_context_is_injected_into_director_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="", tool_calls=[])
        baseline = make_state()
        state = make_state(bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"})
        director_node(state, llm=fake_llm)
        system_content = fake_llm.bind_tools.return_value.invoke.call_args[0][0][0].content
        assert "state.game_time" in system_content
        assert "2026-04-10T08:00:00+00:00" in system_content
