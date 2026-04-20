"""
Orchestrator — MVP Client/Orchestrator for the MnesOS/YARE engine.

Sits between the User Interface, the compiled LangGraph, and the LLM APIs.
Responsibilities:
  - Load and validate a cartridge directory.
  - Compile the LangGraph, injecting per-role LLM instances.
  - Maintain the active GameState (conversation history + bot_memory).
  - Expose process_turn(user_input) as the single-entry core turn loop.
  - Catch graph-level errors and issue an internal-system-prompt retry.

Static cartridge data (yare_config, prompt_directives, lore_path,
lore_content, persona_context) is passed to the graph via
``RunnableConfig["configurable"]`` instead of being stored in GameState.
"""

import copy
import logging
from typing import Any, Dict

from .cartridge import CartridgeLoader, LoadedCartridge
from .graph import (
    GameState,
    build_graph,
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
            llm_npc=ChatOpenAI(model="gpt-4o-mini", temperature=0.5),
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
        persona: Any = None,
        llm_director=None,
        llm_npc=None,
        llm_narrator=None,
    ) -> None:
        """
        Initialize the Orchestrator.

        Args:
            cartridge_dir: Path to the cartridge directory containing
                           yare.yaml, bot_lore.md, and optionally
                           prompt_directives.yaml.
            llm_director:  LangChain BaseChatModel for the Director node.
            llm_npc: LangChain BaseChatModel for the NPC Brain node.
            llm_narrator:  LangChain BaseChatModel for the Narrator node.
        """
        loader = CartridgeLoader()
        self._cartridge: LoadedCartridge = loader.load(cartridge_dir, persona=persona)
        logger.info("Cartridge loaded from %r", cartridge_dir)

        # Check for separate_npc feature flag
        if self._cartridge.yare_config.get("separate_npc", False):
            raise NotImplementedError(
                "separate_npc=True is not yet implemented. "
                "This feature is planned for a future release. "
                "See docs/feature_roadmap.md for details. "
                "To use the orchestrator, set separate_npc=False or omit it."
            )

        self._app = self._compile_graph(llm_director, llm_npc, llm_narrator)
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

        config = self._build_runnable_config()

        for attempt in range(MAX_TURN_RETRIES + 1):
            try:
                new_state = self._app.invoke(self._state, config=config)
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
            "system_notes": [],
            "retrieved_lore": "",
            "iteration_count": 0,
            "turn_phase": "",
        }

    def _build_runnable_config(self) -> dict:
        """Build the ``RunnableConfig`` dict carrying static cartridge data."""
        return {
            "configurable": {
                "yare_config": self._cartridge.yare_config,
                "prompt_directives": self._cartridge.prompt_directives,
                "lore_path": self._cartridge.lore_path,
                "lore_content": self._cartridge.lore_content,
                "persona_context": self._cartridge.persona_context,
            }
        }

    def _compile_graph(self, llm_director, llm_npc, llm_narrator):
        """Delegate graph compilation to the build_graph factory in graph.py."""
        return build_graph(
            yare_config=self._cartridge.yare_config,
            llm_director=llm_director,
            llm_npc=llm_npc,
            llm_narrator=llm_narrator,
            prompt_directives=self._cartridge.prompt_directives,
        )

    def _extract_narrator_response(self) -> str:
        """Return the most recent assistant message from client_messages."""
        for msg in reversed(self._state.get("client_messages", [])):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""
