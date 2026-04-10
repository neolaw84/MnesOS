"""
Orchestrator — MVP Client/Orchestrator for the MnesOS/YARE engine.

Sits between the User Interface, the compiled LangGraph, and the LLM APIs.
Responsibilities:
  - Load and validate a cartridge directory.
  - Compile the LangGraph, injecting per-role LLM instances.
  - Maintain the active GameState (conversation history + bot_memory).
  - Expose process_turn(user_input) as the single-entry core turn loop.
  - Catch graph-level errors and issue an internal-system-prompt retry.
"""

import copy
import functools
import logging
from typing import Any, Dict

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .cartridge import CartridgeLoader, LoadedCartridge
from .graph import (
    GameState,
    trigger_event,
    reset_agent_messages_node,
    cleanup_agent_messages_node,
    context_retrieval_node,
    cycle_tick_node,
    director_node,
    npc_brain_node,
    narrator_node,
    pre_tools_node,
    post_tools_node,
    route_director,
    route_npc_brain,
    route_rules,
)

logger = logging.getLogger(__name__)

# Maximum number of automatic retries when a turn fails with a recoverable error.
MAX_TURN_RETRIES = 1

_RETRY_SYSTEM_NOTE = (
    "SYSTEM: The previous attempt returned an error. "
    "Please respond with valid JSON and only call declared events."
)


class Orchestrator:
    """
    MVP Orchestrator for the MnesOS YARE engine.

    Usage::

        from langchain_openai import ChatOpenAI
        from MnesOS import Orchestrator

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        orch = Orchestrator(
            cartridge_dir="cartridges/generic-rpg",
            llm_director=llm,
            llm_npc_brain=ChatOpenAI(model="gpt-4o-mini", temperature=0.5),
            llm_narrator=ChatOpenAI(model="gpt-4o-mini", temperature=0.8),
        )

        response = orch.process_turn("I arrive at the Crossroads and look around.")
        print(response)

    All three LLM parameters are optional; omitting them runs the graph in
    "dry" mode (no LLM calls), which is useful for testing.
    """

    def __init__(
        self,
        cartridge_dir: str,
        llm_director=None,
        llm_npc_brain=None,
        llm_narrator=None,
    ) -> None:
        """
        Initialize the Orchestrator.

        Args:
            cartridge_dir: Path to the cartridge directory containing
                           yare.yaml, bot_lore.md, and optionally
                           prompt_directives.yaml.
            llm_director:  LangChain BaseChatModel for the Director node.
            llm_npc_brain: LangChain BaseChatModel for the NPC Brain node.
            llm_narrator:  LangChain BaseChatModel for the Narrator node.
        """
        loader = CartridgeLoader()
        self._cartridge: LoadedCartridge = loader.load(cartridge_dir)
        logger.info("Cartridge loaded from %r", cartridge_dir)

        self._app = self._compile_graph(llm_director, llm_npc_brain, llm_narrator)
        logger.info("Graph compiled. Nodes: %s", list(self._app.get_graph().nodes.keys()))

        self._state: GameState = self._build_initial_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> GameState:
        """The current, live GameState including conversation history."""
        return self._state

    @property
    def cartridge(self) -> LoadedCartridge:
        """The loaded cartridge metadata."""
        return self._cartridge

    def reset(self) -> None:
        """Restore the game to its initial state (clears conversation history)."""
        self._state = self._build_initial_state()
        logger.info("Orchestrator state reset to initial cartridge defaults.")

    def process_turn(self, user_input: str) -> str:
        """
        Execute one game turn.

        Appends *user_input* to the conversation history, invokes the
        compiled graph, and returns the Narrator's prose response.

        On a recoverable graph error the orchestrator appends an internal
        system note and retries once.  If the retry also fails the
        exception is re-raised.

        Args:
            user_input: The player's raw text input.

        Returns:
            The Narrator's prose response string (empty string if no
            narrator response was produced, e.g. in dry-run mode).
        """
        self._state["client_messages"].append({"role": "user", "content": user_input})
        logger.debug("Player: %s", user_input)

        for attempt in range(MAX_TURN_RETRIES + 1):
            try:
                new_state = self._app.invoke(self._state)
                self._state = new_state
                response = self._extract_narrator_response()
                logger.debug("Narrator: %s", response[:120] if response else "(none)")
                return response
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Turn attempt %d/%d failed: %s — %s",
                    attempt + 1,
                    MAX_TURN_RETRIES + 1,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                if attempt < MAX_TURN_RETRIES:
                    self._state["system_notes"] = (
                        self._state.get("system_notes") or []
                    ) + [_RETRY_SYSTEM_NOTE]
                else:
                    raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_initial_state(self) -> GameState:
        """Construct a fresh GameState from cartridge defaults."""
        return {
            "client_messages": [],
            "agent_messages": [],
            "bot_memory": copy.deepcopy(self._cartridge.initial_state),
            "bot_memory_staging": [],
            "yare_config": self._cartridge.yare_config,
            "prompt_directives": self._cartridge.prompt_directives,
            "lore_path": self._cartridge.lore_path,
            "system_notes": [],
            "retrieved_lore": "",
            "iteration_count": 0,
            "turn_phase": "",
        }

    def _compile_graph(self, llm_director, llm_npc_brain, llm_narrator):
        """Build and compile a fresh LangGraph, injecting LLM instances."""
        graph = StateGraph(GameState)

        graph.add_node("ResetAgentMessages", reset_agent_messages_node)
        graph.add_node("Lore", context_retrieval_node)
        graph.add_node("CycleTick", cycle_tick_node)
        graph.add_node("Director", functools.partial(director_node, llm=llm_director))
        graph.add_node("PreTools", pre_tools_node)
        graph.add_node("Tools", ToolNode([trigger_event], messages_key="agent_messages"))
        graph.add_node("PostTools", post_tools_node)
        graph.add_node("NPC_Brain", functools.partial(npc_brain_node, llm=llm_npc_brain))
        graph.add_node("Narrator", functools.partial(narrator_node, llm=llm_narrator))
        graph.add_node("CleanupAgentMessages", cleanup_agent_messages_node)

        graph.set_entry_point("ResetAgentMessages")
        graph.add_edge("ResetAgentMessages", "Lore")
        graph.add_edge("Lore", "CycleTick")
        graph.add_edge("CycleTick", "Director")

        graph.add_conditional_edges(
            "Director", route_director, {"PreTools": "PreTools", "NPC_Brain": "NPC_Brain"}
        )
        graph.add_edge("PreTools", "Tools")
        graph.add_edge("Tools", "PostTools")
        graph.add_conditional_edges(
            "PostTools", route_rules, {"Director": "Director", "NPC_Brain": "NPC_Brain"}
        )
        graph.add_conditional_edges(
            "NPC_Brain", route_npc_brain, {"PreTools": "PreTools", "Narrator": "Narrator"}
        )
        graph.add_edge("Narrator", "CleanupAgentMessages")
        graph.add_edge("CleanupAgentMessages", END)

        return graph.compile()

    def _extract_narrator_response(self) -> str:
        """Return the most recent assistant message from client_messages."""
        for msg in reversed(self._state.get("client_messages", [])):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""
