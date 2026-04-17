from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, ToolMessage
from ..shared import make_state, _BindableFakeModel
from MnesOS.graph.nodes.narrator import narrator_node

class TestNarratorNode:
    def test_clears_system_notes(self):
        state = make_state(system_notes=["Player dealt 10 damage.", "NPC is hurt."])
        result = narrator_node(state)
        assert result["system_notes"] == []

    def test_clears_retrieved_lore(self):
        state = make_state(retrieved_lore="Some lore text.")
        result = narrator_node(state)
        assert result["retrieved_lore"] == ""

    def test_resets_iteration_count(self):
        state = make_state(iteration_count=3)
        result = narrator_node(state)
        assert result["iteration_count"] == 0

    def test_directives_present_does_not_crash(self):
        state = make_state(
            prompt_directives={"narrator": "Be poetic."},
            system_notes=["Hit!"],
        )
        result = narrator_node(state)
        assert result["system_notes"] == []

class TestNarratorNodeWithLLM:
    def test_llm_is_invoked(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="The goblin snarls.")
        state = make_state(system_notes=["Player dealt 10 damage."])
        narrator_node(state, llm=fake_llm)
        fake_llm.invoke.assert_called_once()

    def test_llm_response_stored_as_narrative(self):
        fake_llm = _BindableFakeModel(responses=[AIMessage(content="The goblin snarls and lunges at you.", tool_calls=[])])
        state = make_state(system_notes=["Player dealt 10 damage."])
        result = narrator_node(state, llm=fake_llm)
        assert "narrative" in result
        assert "goblin" in result["narrative"].lower()

    def test_narrative_uses_public_state_not_private(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.", tool_calls=[])
        state = make_state(system_notes=["Test."])
        state["bot_memory"]["player"]["is_poisoned_with_asymptomatic_poison"] = True
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "is_poisoned_with_asymptomatic_poison" not in call_arg

    def test_scene_directive_is_extracted_from_agent_messages(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.", tool_calls=[])
        state = make_state(
            system_notes=["Test."],
            agent_messages=[AIMessage(content="The scene directive from the Director.", tool_calls=[])],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "The scene directive from the Director." in call_arg

    def test_game_time_context_is_injected_into_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story text.", tool_calls=[])
        baseline = make_state()
        state = make_state(
            bot_memory={**baseline["bot_memory"], "game_time": "2026-04-10T08:00:00+00:00"},
            system_notes=["Test."],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "state.game_time" in call_arg
        assert "2026-04-10T08:00:00+00:00" in call_arg

class TestNarratorNodeSceneDirectiveFilter:
    """Tests that narrator_node strictly isolates the Director's Scene Directive
    and hides system_notes and raw tool traces from the Narrator."""

    def test_system_notes_not_in_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story.", tool_calls=[])
        state = make_state(
            system_notes=["SECRET: player.hp = 42", "Roll succeeded with modifier 3"],
            agent_messages=[AIMessage(content="The Director's summary.", tool_calls=[])],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "SECRET: player.hp = 42" not in call_arg
        assert "Roll succeeded with modifier 3" not in call_arg

    def test_tool_call_messages_not_in_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story.", tool_calls=[])
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{"name": "trigger_event", "args": {"event": "deal_damage"}, "id": "call_x", "type": "tool_call"}],
        )
        state = make_state(
            system_notes=["Damage dealt."],
            agent_messages=[
                ai_with_tool,
                ToolMessage(content="Engine result: hp -10", tool_call_id="call_x"),
                AIMessage(content="The Director's final clean summary.", tool_calls=[]),
            ],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "trigger_event" not in call_arg
        assert "Engine result: hp -10" not in call_arg

    def test_scene_directive_present_in_narrator_prompt(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story.", tool_calls=[])
        scene_directive = "The goblin steps forward menacingly."
        state = make_state(
            system_notes=["hp -10"],
            agent_messages=[
                AIMessage(content="", tool_calls=[{"name": "trigger_event", "args": {}, "id": "c1", "type": "tool_call"}]),
                ToolMessage(content="Tool result", tool_call_id="c1"),
                AIMessage(content=scene_directive, tool_calls=[]),
            ],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert scene_directive in call_arg

    def test_last_plain_ai_message_is_used_as_scene_directive(self):
        """When multiple plain AIMessages exist, only the last one is used."""
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story.", tool_calls=[])
        state = make_state(
            system_notes=[],
            agent_messages=[
                AIMessage(content="First Director message.", tool_calls=[]),
                AIMessage(content="Final Director summary.", tool_calls=[]),
            ],
        )
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "Final Director summary." in call_arg
        assert "First Director message." not in call_arg

    def test_empty_agent_messages_produces_empty_scene_directive(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Story.", tool_calls=[])
        state = make_state(system_notes=[], agent_messages=[])
        narrator_node(state, llm=fake_llm)
        call_arg = str(fake_llm.invoke.call_args)
        assert "SCENE DIRECTIVES" in call_arg
