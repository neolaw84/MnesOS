"""
Orchestrator — MVP Client/Orchestrator for the MnesOS/YARE engine.

Sits between the User Interface, the compiled LangGraph, and the LLM APIs.
Responsibilities:
  - Load and validate a cartridge directory.
  - Compile the LangGraph, injecting per-role LLM instances.
  - (Stateful mode) Maintain the active GameState in memory.
  - (Stateless mode) Hydrate state from storage, invoke graph, return result.
  - Expose process_turn() as the single-entry core turn loop.
  - Catch graph-level errors and issue an internal-system-prompt retry.

Aligned with ``docs/design/0005-interfaces-and-contracts.md`` §3.2:
  - Stateless ``process_turn`` returns ``{'narrator_text', 'yare_delta'}``
    and does NOT persist to the database.  The API route handles persistence.
  - LLMs may be injected per-request via ``llm_clients`` (BYOK pattern).
"""

import copy
import json
import logging
from typing import Any, Dict, Optional

from .cartridge import CartridgeLoader, LoadedCartridge
from .graph import (
    GameState,
    build_graph,
)
from .storage.interface import AbstractStorageComponent
from .storage.models import TurnLog, TurnActor
from .storage.hydrator import StateHydrator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)




class Orchestrator:
    """
    MVP Orchestrator for the MnesOS YARE engine.

    Supports two operating modes:

    **Stateful mode** (no ``storage``): the orchestrator keeps ``self._state``
    in memory across ``process_turn`` calls.  This is the legacy CLI /
    notebook experience.

    **Stateless mode** (``storage`` provided): each ``process_turn`` call
    receives a ``parent_turn_id``, hydrates state from the turn-log tree,
    invokes the graph, and returns the result dict.  The orchestrator does
    NOT persist to the database — the API route handles that.

    Usage (stateful)::

        orch = Orchestrator(cartridge_dir="cartridges/generic-rpg")
        response = orch.process_turn("I look around.")

    Usage (stateless)::

        orch = Orchestrator(
            cartridge_version=my_cartridge_version,
            persona=my_persona,
            storage=my_sqlite_store,
        )
        result = orch.process_turn(
            "I look around.",
            parent_turn_id="prev-turn-uuid",
        )
        # result == {"narrator_text": "...", "yare_delta": {...}}
    """

    def __init__(
        self,
        storage: AbstractStorageComponent,
        cartridge_dir: Optional[str] = None,
        cartridge_version: Optional[Any] = None,
        persona: Any = None,
        llm_director=None,
        llm_npc=None,
        llm_narrator=None,
    ) -> None:
        loader = CartridgeLoader()
        if cartridge_version:
            self._cartridge: LoadedCartridge = loader.load_from_version(cartridge_version, persona=persona)
            logger.info("Cartridge loaded from DB version %s", cartridge_version.id)
        elif cartridge_dir:
            self._cartridge: LoadedCartridge = loader.load(cartridge_dir, persona=persona)
            logger.info("Cartridge loaded from %r", cartridge_dir)
        else:
            raise ValueError("Must provide either cartridge_dir or cartridge_version.")

        if self._cartridge.yare_config.get("separate_npc", False):
            raise NotImplementedError(
                "separate_npc=True is not yet implemented. "
                "This feature is planned for a future release. "
                "See docs/feature_roadmap.md for details. "
                "To use the orchestrator, set separate_npc=False or omit it."
            )

        if storage is None:
            raise ValueError("A storage backend is required for Orchestrator.")
        self._storage = storage
        self._app = self._compile_graph(llm_director, llm_npc, llm_narrator)
        logger.info("Graph compiled. Nodes: %s", list(self._app.get_graph().nodes.keys()))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------



    @property
    def cartridge(self) -> LoadedCartridge:
        """The loaded cartridge metadata."""
        return self._cartridge

    def process_turn(
        self,
        user_input: str,
        *,
        parent_turn_id: Optional[str] = None,
        llm_clients: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute one game turn.
        
        Hydrates state from the turn-log tree, invokes the graph, and returns a result dict.
        The Orchestrator does NOT save the turn to the DB; the API route handles that.

        Parameters
        ----------
        user_input : str
            The player's raw text input.
        parent_turn_id : str, optional
            ID of the previous turn. If None, assumes a new game starting at Turn 0.
        llm_clients : dict, optional
            Per-request LLM instances for BYOK. Keys: ``"director"``,
            ``"narrator"``, ``"npc"``.

        Returns
        -------
        dict
            ``{"narrator_text": str, "yare_delta": dict}``.
        """
        if self._storage is None:
            raise RuntimeError("process_turn requires a storage backend.")

        # 1. Hydrate state from lineage
        if parent_turn_id is not None:
            lineage = self._storage.get_turn_lineage(parent_turn_id)
        else:
            lineage = []

        state = StateHydrator.hydrate_state(lineage, self._cartridge.initial_state)
        state["client_messages"].append({"role": "user", "content": user_input})

        # 2. Invoke graph with static cartridge data + BYOK LLMs via config
        config = self._build_runnable_config(llm_clients=llm_clients)
        logger.debug("INVOKING GRAPH with hydrated state: %s", json.dumps(state, indent=2, default=str) if state else "None")
        new_state = self._app.invoke(state, config=config)
        logger.debug("GRAPH RESULT: %s", json.dumps(new_state, indent=2, default=str) if new_state else "None")

        # 3. Extract yare_delta from bot_memory changes
        yare_delta = self._extract_delta(
            self._cartridge.initial_state, lineage, new_state
        )

        # 4. Extract narrator response
        narrator_text = self._extract_narrator_response(new_state)

        return {
            "narrator_text": narrator_text,
            "yare_delta": yare_delta,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------



    def _build_runnable_config(
        self,
        llm_clients: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Build the ``RunnableConfig`` dict carrying static cartridge data.

        If *llm_clients* is provided the dict is included under
        ``configurable["llm_clients"]`` so graph nodes can pick them up
        for BYOK invocations (per 0005 §4.2).
        """
        configurable: Dict[str, Any] = {
            "yare_config": self._cartridge.yare_config,
            "prompt_directives": self._cartridge.prompt_directives,
            "lore_path": self._cartridge.lore_path,
            "lore_content": self._cartridge.lore_content,
            "persona_context": self._cartridge.persona_context,
        }
        if llm_clients:
            configurable["llm_clients"] = llm_clients
        return {"configurable": configurable}

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
        from .storage.hydrator import _deep_merge

        # Reconstruct pre-turn bot_memory
        pre = copy.deepcopy(initial_state)
        for turn in lineage:
            delta = turn.yare_delta
            if isinstance(delta, dict) and delta:
                pre = _deep_merge(pre, delta)

        post = new_state.get("bot_memory", {})

        # Diff: only include keys whose values actually changed
        diff: Dict[str, Any] = {}
        for key in post:
            if key not in pre or pre[key] != post[key]:
                diff[key] = copy.deepcopy(post[key])
        return diff
