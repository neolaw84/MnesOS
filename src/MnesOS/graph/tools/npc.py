import json
from typing import Annotated, List, Dict, Any, Optional
from langchain_core.tools import tool, InjectedToolCallId, StructuredTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import SystemMessage, ToolMessage
from ..state import NPCPresentation, BatchedNPCIntent, get_npc_visible_state
from ..utils.messages import _client_messages_to_langchain_messages
from ...prompts import NPC_SYSTEM_PROMPT

def build_npc_intent_tool(npc_llm, yare_config: Dict[str, Any] = None, prompt_directives: Dict[str, str] = None) -> StructuredTool:
    """Factory that returns a ``query_npc_intent`` tool wired to *npc_llm*.

    ``yare_config`` and ``prompt_directives`` are closed over at build time
    so the tool no longer reads them from graph state.
    """
    _yare_config = yare_config or {}
    _prompt_directives = prompt_directives or {}

    @tool
    def query_npc_intent(
        present_npcs: List[NPCPresentation],
        scene_context: str,
        history_turns: int,
        dm_directives: str = "",
        tool_call_id: Annotated[str, InjectedToolCallId()] = "",
        state: Annotated[dict, InjectedState()] = None,
    ) -> Command:
        """Call this to see how a list of NPCs want to react before you calculate the rules.

        present_npcs is a list of NPCPresentation DTOs constructed by the Director.
        Each DTO contains the NPC's id, template (optional), and tags (optional).
        scene_context is a brief synthesis of the immediate physical environment.
        """
        state = state or {}
        bot_memory: Dict[str, Any] = state.get("bot_memory", {})
        npc_templates: Dict[str, Any] = _yare_config.get("npc_templates", {})

        # Get attention budget settings with defaults
        settings = _yare_config.get("engine_settings", {})
        min_credit = settings.get("npc_min_credit_threshold", 5)
        max_npcs = settings.get("max_batched_npcs", 3)

        # Score each NPC using the DTO — no bot_memory["npcs"] lookup
        scored_npcs = []
        for npc in (present_npcs or []):
            nid = npc.get("id", "")
            score = 0
            # Credit from Name template
            if tmpl := npc_templates.get(npc.get("template")):
                score += tmpl.get("credit", 0)
            # Credit from Tags
            for tag in (npc.get("tags") or []):
                if tmpl := npc_templates.get(tag):
                    score += tmpl.get("credit", 0)
            if score >= min_credit:
                scored_npcs.append({"id": nid, "score": score, "dto": npc})

        # Sort by score descending, then slice to max_npcs
        scored_npcs.sort(key=lambda x: x["score"], reverse=True)
        top_entries = scored_npcs[:max_npcs]
        
        # 1. Assemble history (most recent N turns, capped at 10)
        client_messages = state.get("client_messages", [])
        n = min(max(history_turns, 0), 10)
        history = client_messages[-n:] if n else []
        history_text = "\n".join(
            f"{m.get('role','user').capitalize()}: {m.get('content','')}" for m in history
        )

        # 2. Assemble lore
        lore_text: str = state.get("retrieved_lore", "")

        # 3. Assemble NPC-visible state
        visible_state = get_npc_visible_state(bot_memory, _yare_config)

        # 4. Build batched profile text for top NPCs using DTO data
        profile_parts: list[str] = []
        for entry in top_entries:
            nid = entry["id"]
            npc_dto: Dict[str, Any] = entry["dto"]
            npc_desc_parts: list[str] = []

            template_key = npc_dto.get("template")
            if template_key and template_key in npc_templates:
                npc_desc_parts.append(npc_templates[template_key].get("description", ""))

            for tag in (npc_dto.get("tags") or []):
                if tag in npc_templates:
                    npc_desc_parts.append(npc_templates[tag].get("description", ""))

            npc_desc = " ".join(filter(None, npc_desc_parts)) or f"NPC id={nid}"
            profile_parts.append(f"NPC: {nid} | Profile: {npc_desc}")

        profile_text = "\n".join(profile_parts) if profile_parts else "No qualifying NPCs."

        # 5. When no NPCs qualify, return early without querying the LLM
        if not top_entries:
            return Command(
                update={
                    "agent_messages": [ToolMessage(content=profile_text, tool_call_id=tool_call_id)],
                }
            )

        # 6. Build prompt and invoke the LLM with structured output
        c_directives = _prompt_directives.get("npc", "") or ""
        formatted_prompt = NPC_SYSTEM_PROMPT.format(
            visible_state=json.dumps(visible_state),
            lore_text=lore_text,
            history_text=history_text,
            scene_context=scene_context,
            dm_directives=dm_directives,
            batched_profiles=profile_text,
            cartridge_directives=c_directives,
        )
        prompt_messages = [SystemMessage(content=formatted_prompt)]

        structured_llm = npc_llm.with_structured_output(BatchedNPCIntent)
        result: BatchedNPCIntent = structured_llm.invoke(prompt_messages)

        return Command(
            update={
                "npc_intent_called": True,
                "agent_messages": [ToolMessage(content=result.model_dump_json(), tool_call_id=tool_call_id)],
            }
        )

    return query_npc_intent
