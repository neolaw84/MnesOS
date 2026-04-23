from typing import Annotated, List, Dict, Any, Optional
from langchain_core.tools import tool, InjectedToolCallId, StructuredTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import Field, create_model
from langchain_core.messages import ToolMessage
from ...interpreter import YAREInterpreter

def build_yare_event_tools(yare_config: Dict[str, Any]) -> List[StructuredTool]:
    """Dynamically generate a list of precise LangChain tools from YARE events."""
    tools = []
    events = yare_config.get("events", {})
    if not isinstance(events, dict):
        return []

    for event_name, event_config in events.items():
        if not isinstance(event_config, dict):
            continue

        fields = {}
        inputs_schema = event_config.get("inputs", {})
        if isinstance(inputs_schema, list):
            for k in inputs_schema:
                fields[k] = (Any, Field(default=..., description=str(k)))
        elif isinstance(inputs_schema, dict):
            for k, spec in inputs_schema.items():
                t_str = spec.get("type", "string")
                py_type = str
                if t_str == "int": py_type = int
                elif t_str == "float": py_type = float
                elif t_str == "bool": py_type = bool
                
                desc = spec.get("description", "")
                if "enum" in spec:
                    desc += f" (one of: {', '.join(str(v) for v in spec['enum'])})"
                
                default_val = spec.get("default", ...)
                fields[k] = (py_type, Field(default=default_val, description=desc))

        def create_tool(ename, econfig, efields):
            def _run_dynamic_event(
                *args, 
                tool_call_id: Annotated[str, InjectedToolCallId()] = "", 
                state: Annotated[dict, InjectedState()] = None, 
                **kwargs
            ) -> Command:
                interpreter = YAREInterpreter(yare_config, state["bot_memory"])
                new_notes = []
                
                # Intercept shadow parameter before passing to YARE
                kwargs.pop("engine_time_delta", None)
                
                if (
                    state.get("turn_phase") == "npc"
                    and "\n--- NPC Turn Resolution ---" not in state.get("system_notes", [])
                ):
                    new_notes.append("\n--- NPC Turn Resolution ---")
                
                interpreter.run_event(ename, kwargs)
                new_notes.extend(interpreter.notes)
                
                notes_text = "\n".join(interpreter.notes) if interpreter.notes else f"Event '{ename}': no effect."
                
                return Command(update={
                    "bot_memory_staging": [interpreter.state],
                    "system_notes": new_notes,
                    "agent_messages": [ToolMessage(content=notes_text, tool_call_id=tool_call_id)],
                })

            # Inject internal dependencies into schema so ToolNode knows to supply them,
            # while the Injected... annotations tell the LLM to ignore them.
            efields_with_injected = dict(efields)
            efields_with_injected["tool_call_id"] = (Annotated[str, InjectedToolCallId()], Field(default=""))
            efields_with_injected["state"] = (Annotated[dict, InjectedState()], Field(default=None))
            efields_with_injected["engine_time_delta"] = (str, Field(default="PT0S", description="Estimated in-game time this action takes."))

            ArgsSchema = create_model(f"{ename}_Schema", **efields_with_injected)
            
            # Override docstring specifically for the tool definition
            desc = econfig.get("description", f"Trigger the {ename} event.")
            _run_dynamic_event.__doc__ = desc
            
            return tool(ename, args_schema=ArgsSchema)(_run_dynamic_event)

        t = create_tool(event_name, event_config, fields)
        tools.append(t)

    return tools
