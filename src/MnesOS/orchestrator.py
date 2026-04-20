"""
Orchestrator — MVP Client/Orchestrator for the MnesOS/YARE engine.

Sits between the User Interface, the compiled LangGraph, and the LLM APIs.
Responsibilities:
  - Load and validate a cartridge directory.
  - Compile the LangGraph, injecting per-role LLM instances.
  - (Stateful mode) Maintain the active GameState in memory.
  - (Stateless mode) Hydrate state from storage, invoke graph, persist delta.
  - Expose process_turn() as the single-entry core turn loop.
  - Catch graph-level errors and issue an internal-system-prompt retry.

Static cartridge data (yare_config, prompt_directives, lore_path,
lore_content, persona_context) is passed to the graph via
``RunnableConfig["configurable"]`` instead of being stored in GameState.
"""

import copy
import logging
from typing import Any, Dict, Optional

from .cartridge import CartridgeLoader, LoadedCartridge
from .graph import (
    GameState,
    build_graph,
)
from .storage.interface import AbstractStorageComponent
from .storage.models import TurnLog, TurnActor
from .storage.hydrator import hydrate_state

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

    Supports two operating modes:

    **Stateful mode** (no ``storage``): the orchestrator keeps ``self._state``
    in memory across ``process_turn`` calls.  This is the legacy CLI /
    notebook experience.

    **Stateless mode** (``storage`` provided): each ``process_turn`` call
    receives a ``parent_turn_id``, hydrates state from the turn-log tree,
    invokes the graph, persists the delta, and returns the new turn ID.
    The orchestrator can be destroyed and re-created between turns without
    losing progress.

    Usage (stateful)::

        orch = Orchestrator(cartridge_dir="cartridges/generic-rpg")
        response = orch.process_turn("I look around.")

    Usage (stateless)::

        orch = Orchestrator(
            cartridge_dir="cartridges/generic-rpg",
            storage=my_sqlite_store,
        )
        turn_id = orch.process_turn(
            "I look around.",
            parent_turn_id="prev-turn-uuid",
            instance_id="game-instance-uuid",
        )
    """

    def __init__(
        self,
        cartridge_dir: str,
        persona: Any = None,
        llm_director=None,
        llm_npc=None,
        llm_narrator=None,
        storage: Optional[AbstractStorageComponent] = None,
    ) -> None:
        loader = CartridgeLoader()
        self._cartridge: LoadedCartridge = loader.load(cartridge_dir, persona=persona)
        logger.info("Cartridge loaded from %r", cartridge_dir)

        if self._cartridge.yare_config.get("separate_npc", False):
            raise NotImplementedError(
                "separate_npc=True is not yet implemented. "
                "This feature is planned for a future release. "
                "See docs/feature_roadmap.md for details. "
                "To use the orchestrator, set separate_npc=False or omit it."
            )

        self._storage = storage
        self._app = self._compile_graph(llm_director, llm_npc, llm_narrator)
        logger.info("Graph compiled. Nodes: %s", list(self._app.get_graph().nodes.keys()))

        # Stateful mode keeps an in-memory state; stateless mode does not.
        self._state: Optional[GameState] = (
            self._build_initial_state() if storage is None else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> GameState:
        """The current, live GameState (stateful mode only)."""
        if self._state is None:
            raise RuntimeError(
                "No in-memory state. In stateless mode use "
                "process_turn(user_input, parent_turn_id=..., instance_id=...)."
            )
        return self._state

    @property
    def cartridge(self) -> LoadedCartridge:
        """The loaded cartridge metadata."""
        return self._cartridge

    def reset(self) -> None:
        """Restore the game to its initial state (stateful mode only)."""
        self._state = self._build_initial_state()
        logger.info("Orchestrator state reset to initial cartridge defaults.")

    def process_turn(
        self,
        user_input: str,
        *,
        parent_turn_id: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> str:
        """
        Execute one game turn.

        **Stateful mode** (no ``parent_turn_id``): appends *user_input* to
        the in-memory conversation history, invokes the graph, and returns
        the Narrator's prose response.

        **Stateless mode** (``parent_turn_id`` + ``instance_id``): hydrates
        state from the turn-log tree, invokes the graph, extracts the
        ``yare_delta`` from ``bot_memory_staging``, persists a new
        :class:`TurnLog`, and returns the new turn's ID.

        Returns:
            - Stateful mode: Narrator's prose response string.
            - Stateless mode: The ``id`` of the newly created TurnLog.
        """
        if parent_turn_id is not None or self._storage is not None:
            return self._process_turn_stateless(
                user_input, parent_turn_id=parent_turn_id, instance_id=instance_id
            )
        return self._process_turn_stateful(user_input)

    # ------------------------------------------------------------------
    # Stateful turn (legacy / CLI)
    # ------------------------------------------------------------------

    def _process_turn_stateful(self, user_input: str) -> str:
        """In-memory stateful turn loop (original behavior)."""
        self._state["client_messages"].append({"role": "user", "content": user_input})
        logger.debug("Player: %s", user_input)

        config = self._build_runnable_config()

        for attempt in range(MAX_TURN_RETRIES + 1):
            try:
                new_state = self._app.invoke(self._state, config=config)
                self._state = new_state
                response = self._extract_narrator_response(self._state)
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
    # Stateless turn (web / API)
    # ------------------------------------------------------------------

    def _process_turn_stateless(
        self,
        user_input: str,
        *,
        parent_turn_id: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> str:
        """Hydrate → invoke → persist delta → return new turn ID."""
        if self._storage is None:
            raise RuntimeError(
                "Stateless process_turn requires a storage backend. "
                "Pass storage= to Orchestrator.__init__."
            )
        if instance_id is None:
            raise ValueError("instance_id is required for stateless process_turn.")

        # 1. Hydrate state from lineage
        if parent_turn_id is not None:
            lineage = self._storage.get_turn_lineage(parent_turn_id)
            turn_index = len(lineage)
        else:
            lineage = []
            turn_index = 0

        state = hydrate_state(lineage, self._cartridge.initial_state)
        state["client_messages"].append({"role": "user", "content": user_input})

        # 2. Invoke graph with static cartridge data via config
        config = self._build_runnable_config()
        new_state = self._app.invoke(state, config=config)

        # 3. Extract yare_delta from bot_memory changes
        yare_delta = self._extract_delta(
            self._cartridge.initial_state, lineage, new_state
        )

        # 4. Extract narrator response
        narrator_text = self._extract_narrator_response(new_state)

        # 5. Persist new TurnLog
        turn = TurnLog(
            instance_id=instance_id,
            turn_index=turn_index,
            actor=TurnActor.PLAYER,
            input_text=user_input,
            yare_delta=yare_delta,
            narrator_text=narrator_text,
            parent_id=parent_turn_id,
        )
        saved = self._storage.append_turn_log(turn)
        logger.debug("Persisted turn %s (parent=%s)", saved.id, parent_turn_id)
        return saved.id

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

    @staticmethod
    def _extract_narrator_response(state: dict) -> str:
        """Return the most recent assistant message from client_messages."""
        for msg in reversed(state.get("client_messages", [])):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""

    @staticmethod
    def _extract_delta(
        initial_state: dict, lineage: list, new_state: dict
    ) -> dict:
        """Compute the incremental delta produced by this turn.

        The delta is the difference between the hydrated bot_memory
        *before* the turn and the bot_memory *after* the graph ran.
        We store only top-level keys that changed.
        """
        # Reconstruct pre-turn bot_memory
        pre = copy.deepcopy(initial_state)
        for turn in lineage:
            delta = turn.yare_delta
            if isinstance(delta, dict) and delta:
                from .storage.hydrator import _deep_merge
                pre = _deep_merge(pre, delta)

        post = new_state.get("bot_memory", {})

        # Diff: only include keys whose values actually changed
        diff: Dict[str, Any] = {}
        for key in post:
            if key not in pre or pre[key] != post[key]:
                diff[key] = copy.deepcopy(post[key])
        return diff
