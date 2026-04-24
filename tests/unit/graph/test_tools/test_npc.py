from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from ..shared import make_state, make_config, _DEFAULT_YARE_CONFIG, _BindableFakeModel
from MnesOS.graph.tools.npc import build_npc_intent_tool, BatchedNPCIntent
from MnesOS.graph.factory import build_graph

def _make_npc_fake_llm(npc_id="goblin_1", dialogue="Grr!", action_intent="Attack player.", internal_monologue="Hungry."):
    """Helper to build a mock LLM that returns a structured BatchedNPCIntent."""
    mock_llm = MagicMock()
    # Mock the with_structured_output behavior
    structured_mock = MagicMock()
    mock_llm.with_structured_output.return_value = structured_mock
    
    # Setup response
    from MnesOS.graph.state import NPCIntentOutput
    response = BatchedNPCIntent(intents=[
        NPCIntentOutput(npc_id=npc_id, dialogue=dialogue, action_intent=action_intent, internal_monologue=internal_monologue)
    ])
    structured_mock.invoke.return_value = response
    return mock_llm

_NPC_YARE_CONFIG = {
    "state_schema": {
        "player_hp": {"type": "int", "default": 20, "npc_visibility": True},
        "hidden_dagger": {"type": "bool", "default": True, "npc_visibility": False},
    },
    "npc_templates": {
        "goblin": {"description": "Small, green, cowardly creature.", "credit": 3},
        "thug": {"description": "Aggressive, relies on intimidation.", "credit": 5},
        "Mr_XYZ": {"description": "CEO of Evil Corp", "credit": 20},
    },
    "events": {},
    "macros": {},
}

def _make_npc_state(**overrides):
    """Build a state with the complex NPC-related structures needed for tool tests."""
    return make_state(
        bot_memory={"player_hp": 20, "hidden_dagger": True},
        **overrides
    )

def _make_credit_scoring_state(templates: dict, engine_settings: dict = None) -> tuple:
    """Build a minimal state and yare_config for credit-scoring tests.
    Returns (state, yare_config) tuple.
    """
    yare_config = {
        "state_schema": {},
        "npc_templates": templates,
        "events": {},
        "macros": {},
    }
    if engine_settings is not None:
        yare_config["engine_settings"] = engine_settings
    return make_state(), yare_config

class TestBuildNpcIntentTool:
    def test_tool_is_callable(self):
        tool = build_npc_intent_tool(_make_npc_fake_llm(), yare_config=_NPC_YARE_CONFIG)
        assert hasattr(tool, "invoke") and hasattr(tool, "name")

    def test_tool_name_is_query_npc_intent(self):
        tool = build_npc_intent_tool(_make_npc_fake_llm(), yare_config=_NPC_YARE_CONFIG)
        assert tool.name == "query_npc_intent"

    def test_returns_batched_command(self):
        import json
        from langgraph.types import Command
        mock_llm = _make_npc_fake_llm(npc_id="goblin_chief", dialogue="Halt!", action_intent="Block path.", internal_monologue="Fear.")
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        state = _make_npc_state()
        result = tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="The player draws a sword in the dimly lit tavern.",
            history_turns=0,
            state=state,
        )
        assert isinstance(result, Command)
        assert result.update["npc_intent_calls"] == 1
        msg = result.update["agent_messages"][0]
        parsed = json.loads(msg.content)
        assert parsed["intents"][0]["dialogue"] == "Halt!"
        assert parsed["intents"][0]["action_intent"] == "Block path."
        assert parsed["intents"][0]["internal_monologue"] == "Fear."

    def test_tag_mode_concatenates_multiple_descriptions(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        state = _make_npc_state()
        tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="Player enters room.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "Small, green, cowardly creature." in invocation_args
        assert "Aggressive, relies on intimidation." in invocation_args

    def test_name_mode_uses_template_description(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        state = _make_npc_state()
        tool.func(
            present_npcs=[{"id": "mr_xyz", "template": "Mr_XYZ", "tags": []}],
            scene_context="Player challenges authority.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "CEO of Evil Corp" in invocation_args

    def test_npc_visible_state_hides_secret_variables(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        state = _make_npc_state()
        tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="Player taunts the NPC.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "hidden_dagger" not in invocation_args
        assert "player_hp" in invocation_args

    def test_history_turns_limits_messages_passed(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        state = _make_npc_state(client_messages=messages)
        tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="Test.",
            history_turns=2,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "msg4" in invocation_args
        assert "msg3" in invocation_args
        assert "msg0" not in invocation_args

    def test_history_turns_capped_at_ten(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(15)]
        state = _make_npc_state(client_messages=messages)
        tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="Test.",
            history_turns=50,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "msg14" in invocation_args
        assert "msg0" not in invocation_args  # only last 10

    def test_dm_directives_are_included_in_prompt(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        state = _make_npc_state()
        tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="Test.",
            history_turns=0,
            dm_directives="Be extra menacing.",
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "Be extra menacing." in invocation_args

    def test_scene_context_is_included_in_prompt(self):
        mock_llm = _make_npc_fake_llm()
        tool = build_npc_intent_tool(mock_llm, yare_config=_NPC_YARE_CONFIG)
        state = _make_npc_state()
        tool.func(
            present_npcs=[{"id": "goblin_chief", "template": None, "tags": ["goblin", "thug"]}],
            scene_context="Torches flicker. The smell of smoke fills the air.",
            history_turns=0,
            state=state,
        )
        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "Torches flicker" in invocation_args

    def test_tool_is_added_to_build_graph_when_npc_llm_provided(self):
        mock_npc_llm = _make_npc_fake_llm()
        mock_director_llm = MagicMock()
        mock_director_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        config = make_config(yare_config=_DEFAULT_YARE_CONFIG)
        app = build_graph(
            yare_config=_DEFAULT_YARE_CONFIG,
            llm_director=mock_director_llm,
            llm_npc=mock_npc_llm,
        )
        app.invoke(state, config=config)
        bound_tools = mock_director_llm.bind_tools.call_args[0][0]
        tool_names = [t.name for t in bound_tools]
        assert "query_npc_intent" in tool_names

    def test_npc_intent_tool_not_added_when_no_npc_llm(self):
        fake_director = MagicMock()
        fake_director.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=[])
        state = make_state()
        config = make_config(yare_config=_DEFAULT_YARE_CONFIG)
        app = build_graph(
            yare_config=_DEFAULT_YARE_CONFIG,
            llm_director=fake_director,
        )
        app.invoke(state, config=config)
        bound_tools = fake_director.bind_tools.call_args[0][0]
        tool_names = [t.name for t in bound_tools]
        assert "query_npc_intent" not in tool_names

class TestNpcCreditScoring:
    """Tests for the attention-budget scoring and filtering logic in query_npc_intent."""

    def test_npcs_below_threshold_are_excluded(self):
        """NPCs whose accumulated credit is below min_credit_threshold are not queried."""
        mock_llm = _make_npc_fake_llm()

        state, yare_config = _make_credit_scoring_state(
            templates={
                "boss_tmpl":   {"description": "The big boss.", "credit": 10},
                "minion_tmpl": {"description": "A weak minion.", "credit": 2},
            },
            engine_settings={"npc_min_credit_threshold": 5, "max_batched_npcs": 3},
        )
        tool = build_npc_intent_tool(mock_llm, yare_config=yare_config)

        tool.func(
            present_npcs=[
                {"id": "boss",    "template": "boss_tmpl",   "tags": []},
                {"id": "minion1", "template": "minion_tmpl", "tags": []},
                {"id": "minion2", "template": "minion_tmpl", "tags": []},
            ],
            scene_context="Battle starts.",
            history_turns=0,
            state=state,
        )

        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "boss" in invocation_args
        assert "minion1" not in invocation_args
        assert "minion2" not in invocation_args

    def test_list_is_capped_at_max_batched_npcs(self):
        """When more NPCs pass the threshold than max_batched_npcs, only the top N are queried."""
        mock_llm = _make_npc_fake_llm()

        state, yare_config = _make_credit_scoring_state(
            templates={
                "high":   {"description": "High credit NPC.", "credit": 10},
                "medium": {"description": "Medium credit NPC.", "credit": 5},
            },
            engine_settings={"npc_min_credit_threshold": 5, "max_batched_npcs": 3},
        )
        tool = build_npc_intent_tool(mock_llm, yare_config=yare_config)

        tool.func(
            present_npcs=[
                {"id": "npc_a", "template": "high",   "tags": []},
                {"id": "npc_b", "template": "high",   "tags": []},
                {"id": "npc_c", "template": "high",   "tags": []},
                {"id": "npc_d", "template": "medium", "tags": []},
            ],
            scene_context="Big fight.",
            history_turns=0,
            state=state,
        )

        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        # npc_a, npc_b, npc_c occupy the top 3 slots; npc_d should be excluded
        assert "npc_a" in invocation_args
        assert "npc_b" in invocation_args
        assert "npc_c" in invocation_args
        assert "npc_d" not in invocation_args

    def test_tag_credits_accumulate_across_multiple_tags(self):
        """Credits from multiple tags are summed together for the score."""
        mock_llm = _make_npc_fake_llm()

        state, yare_config = _make_credit_scoring_state(
            templates={
                "tag_a": {"description": "Tag A description.", "credit": 3},
                "tag_b": {"description": "Tag B description.", "credit": 3},
            },
            engine_settings={"npc_min_credit_threshold": 5, "max_batched_npcs": 3},
        )
        tool = build_npc_intent_tool(mock_llm, yare_config=yare_config)

        tool.func(
            present_npcs=[
                {"id": "combo_npc",  "template": None, "tags": ["tag_a", "tag_b"]},  # 3+3=6 passes
                {"id": "single_npc", "template": None, "tags": ["tag_a"]},            # 3 — filtered
            ],
            scene_context="Encounter begins.",
            history_turns=0,
            state=state,
        )

        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "combo_npc" in invocation_args
        assert "single_npc" not in invocation_args

    def test_default_threshold_and_max_applied_when_no_engine_settings(self):
        """When engine_settings is absent, defaults (threshold=5, max=3) are used."""
        mock_llm = _make_npc_fake_llm()

        state, yare_config = _make_credit_scoring_state(
            templates={
                "hero_tmpl": {"description": "A hero NPC.", "credit": 8},
                "weak_tmpl": {"description": "A weak NPC.", "credit": 1},
            },
        )
        tool = build_npc_intent_tool(mock_llm, yare_config=yare_config)

        tool.func(
            present_npcs=[
                {"id": "hero_npc", "template": "hero_tmpl", "tags": []},
                {"id": "weak_npc", "template": "weak_tmpl", "tags": []},
            ],
            scene_context="Test defaults.",
            history_turns=0,
            state=state,
        )

        invocation_args = str(mock_llm.with_structured_output.return_value.invoke.call_args)
        assert "hero_npc" in invocation_args
        assert "weak_npc" not in invocation_args

class TestNpcIntentCalledFlag:
    """Tests for the npc_intent_called state flag."""

    def test_reset_agent_messages_node_sets_npc_intent_called_false(self):
        """reset_agent_messages_node must reset npc_intent_called to False each turn."""
        from MnesOS.graph.nodes.system import reset_agent_messages_node
        state = make_state()
        state["npc_intent_calls"] = 2
        result = reset_agent_messages_node(state)
        assert result["npc_intent_calls"] == 0

    def test_npc_intent_called_reset_even_when_previously_false(self):
        from MnesOS.graph.nodes.system import reset_agent_messages_node
        state = make_state()
        state["npc_intent_calls"] = 0
        result = reset_agent_messages_node(state)
        assert result["npc_intent_calls"] == 0

    def test_query_npc_intent_sets_npc_intent_called_true(self):
        """Invoking query_npc_intent must update npc_intent_called to True via the Command."""
        from langgraph.types import Command
        mock_llm = _make_npc_fake_llm()

        state, yare_config = _make_credit_scoring_state(
            templates={"boss_tmpl": {"description": "The boss.", "credit": 10}},
            engine_settings={"npc_min_credit_threshold": 5, "max_batched_npcs": 3},
        )
        tool = build_npc_intent_tool(mock_llm, yare_config=yare_config)

        result = tool.func(
            present_npcs=[{"id": "boss", "template": "boss_tmpl", "tags": []}],
            scene_context="Fight!",
            history_turns=0,
            state=state,
        )

        assert isinstance(result, Command)
        assert result.update["npc_intent_calls"] == 1

    def test_no_qualifying_npcs_does_not_set_npc_intent_called(self):
        """When no NPCs pass the threshold, npc_intent_called must NOT be set to True."""
        from langgraph.types import Command
        mock_llm = _make_npc_fake_llm()

        state, yare_config = _make_credit_scoring_state(
            templates={"weak_tmpl": {"description": "Very weak.", "credit": 1}},
            engine_settings={"npc_min_credit_threshold": 5, "max_batched_npcs": 3},
        )
        tool = build_npc_intent_tool(mock_llm, yare_config=yare_config)

        result = tool.func(
            present_npcs=[{"id": "weak", "template": "weak_tmpl", "tags": []}],
            scene_context="Fight!",
            history_turns=0,
            state=state,
        )

        assert isinstance(result, Command)
        assert "npc_intent_calls" not in result.update
        # LLM must not have been invoked
        mock_llm.with_structured_output.return_value.invoke.assert_not_called()
