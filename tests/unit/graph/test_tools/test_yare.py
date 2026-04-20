from langchain_core.messages import AIMessage, ToolMessage
from ..shared import make_state, _DEFAULT_YARE_CONFIG, GameState
from MnesOS.graph.tools.yare import build_yare_event_tools

def _ai_msg_with_tool_call(event_name: str, call_id: str = "call_1", args: dict = None) -> AIMessage:
    """Build an AIMessage carrying a dynamically generated event tool call."""
    return AIMessage(
        content="",
        tool_calls=[{
            "name": event_name,
            "args": args or {},
            "id": call_id,
            "type": "tool_call",
        }],
    )

def _make_tools_only_app(yare_config: dict):
    """Compile a minimal graph containing only the ToolNode for integration tests."""
    from langgraph.graph import StateGraph, END as _END
    from langgraph.prebuilt import ToolNode
    g = StateGraph(GameState)
    tools = build_yare_event_tools(yare_config)
    g.add_node("T", ToolNode(tools, messages_key="agent_messages"))
    g.set_entry_point("T")
    g.add_edge("T", _END)
    return g.compile()

def _invoke_dynamic_tool(event_name: str, state: dict, event_args: dict = None, call_id: str = "t1", yare_config: dict = None):
    """Invoke a dynamic tool manually for testing."""
    config = yare_config or _DEFAULT_YARE_CONFIG
    tools = build_yare_event_tools(config)
    tool = next((t for t in tools if t.name == event_name), None)
    if not tool:
        class FakeCommand:
            update = {"system_notes": []}
        return FakeCommand()

    tool_args = dict(event_args or {})
    return tool.func(*[], tool_call_id=call_id, state=state, **tool_args)

class TestDynamicEventTools:
    """Tests for dynamic YARE event tools executing real logic with InjectedState."""

    def test_tool_executes_event_and_updates_bot_memory(self):
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("deal_damage", state)
        assert isinstance(result, Command)
        assert result.update["bot_memory_staging"][0]["npc"]["hp"] == 10  # 20 - 10

    def test_tool_emits_new_notes_in_system_notes(self):
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("deal_damage", state)
        assert any("damage" in n for n in result.update["system_notes"])

    def test_tool_npc_phase_adds_separator_note(self):
        from langgraph.types import Command
        state = make_state(turn_phase="npc")
        result = _invoke_dynamic_tool("deal_damage", state)
        assert any("NPC Turn" in n for n in result.update["system_notes"])

    def test_tool_npc_separator_not_duplicated(self):
        from langgraph.types import Command
        state = make_state(turn_phase="npc", system_notes=["\n--- NPC Turn Resolution ---"])
        result = _invoke_dynamic_tool("deal_damage", state)
        combined = state["system_notes"] + result.update.get("system_notes", [])
        assert combined.count("\n--- NPC Turn Resolution ---") == 1

    def test_tool_unknown_event_produces_empty_notes(self):
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("undefined_event", state)
        assert result.update.get("system_notes", []) == []

    def test_tool_passes_args_to_interpreter(self):
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool(
            "generic_check", state,
            event_args={"stat": "strength", "difficulty": 1},
        )
        assert any("Succeeded" in n or "Failed" in n for n in result.update.get("system_notes", []))

    def test_tool_creates_tool_message_with_correct_id(self):
        from langgraph.types import Command
        state = make_state(turn_phase="player")
        result = _invoke_dynamic_tool("deal_damage", state, call_id="my_id")
        tool_msgs = [m for m in result.update.get("agent_messages", []) if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "my_id"
        assert "damage" in tool_msgs[0].content

    def test_tool_node_propagates_bot_memory_staging(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("deal_damage")],
            turn_phase="player",
        )
        app = _make_tools_only_app(_DEFAULT_YARE_CONFIG)
        result = app.invoke(state)
        assert result["bot_memory_staging"][-1]["npc"]["hp"] == 10

    def test_tool_node_appends_tool_message_to_agent_messages(self):
        state = make_state(
            agent_messages=[_ai_msg_with_tool_call("deal_damage")],
            turn_phase="player",
        )
        app = _make_tools_only_app(_DEFAULT_YARE_CONFIG)
        result = app.invoke(state)
        tool_msgs = [m for m in result["agent_messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "damage" in tool_msgs[0].content
