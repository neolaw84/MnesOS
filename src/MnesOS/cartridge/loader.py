"""
cartridge.loader — File-system loader for MnesOS cartridge directories.

A cartridge directory must contain:

* ``yare.yaml``              — procedural rules (YARE config, no prompts).
* ``bot_lore.md``            — vector RAG source text.
* ``prompt_directives.yaml`` — optional narrative tone directives for LLM nodes.

The :class:`CartridgeLoader` class reads these files, delegates structural
validation to :mod:`~MnesOS.cartridge.validators`, and returns a fully
validated :class:`~MnesOS.cartridge.models.LoadedCartridge` instance that is
safe to hand to the rest of the engine.

Design decisions
~~~~~~~~~~~~~~~~
* The loader performs **no** LLM calls or network I/O; it is a pure
  filesystem operation that fails fast at startup.
* The loader is a class (rather than a module-level function) so that it can
  be subclassed or dependency-injected in tests without monkey-patching module
  globals.
* ``yaml.safe_load`` is used throughout — ``yaml.load`` is intentionally
  avoided because it can execute arbitrary Python code.
"""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

from .models import LoadedCartridge
from .validators import (
    _build_initial_state,
    _validate_prompt_directives,
    _validate_yare,
)

logger = logging.getLogger(__name__)


class CartridgeLoader:
    """
    Load and validate a cartridge directory.

    Usage::

        loader = CartridgeLoader()
        cartridge = loader.load("cartridges/generic-rpg")

        # Pass results into GameState (via the Orchestrator):
        initial_state = {
            "yare_config":        cartridge.yare_config,
            "prompt_directives":  cartridge.prompt_directives,
            "lore_path":          cartridge.lore_path,
            "bot_memory":         cartridge.initial_state,
        }

    The ``load`` method is the single entry point.  All validation errors
    bubble up as :exc:`ValueError` or :exc:`FileNotFoundError`; no partial
    state is ever returned.
    """

    def load(self, cartridge_dir: str) -> LoadedCartridge:
        """
        Parse and validate all files in *cartridge_dir*.

        Args:
            cartridge_dir: Path (relative or absolute) to the cartridge
                           directory.

        Returns:
            A fully validated :class:`~MnesOS.cartridge.models.LoadedCartridge`.

        Raises:
            FileNotFoundError: If ``yare.yaml`` or ``bot_lore.md`` is missing.
            ValueError:        If any file fails structural or security
                               validation.
        """
        base = Path(cartridge_dir)

        # ── yare.yaml ─────────────────────────────────────────────────────
        yare_path = base / "yare.yaml"
        if not yare_path.exists():
            raise FileNotFoundError(f"yare.yaml not found in {cartridge_dir!r}")
        with yare_path.open() as f:
            yare_config: Dict[str, Any] = yaml.safe_load(f) or {}
        _validate_yare(yare_config)
        logger.info("yare.yaml validated for cartridge %r", cartridge_dir)

        # ── prompt_directives.yaml (optional) ─────────────────────────────
        directives_path = base / "prompt_directives.yaml"
        if directives_path.exists():
            with directives_path.open() as f:
                raw_directives = yaml.safe_load(f) or {}
            prompt_directives = _validate_prompt_directives(raw_directives)
            logger.info(
                "prompt_directives.yaml validated for cartridge %r (keys: %s)",
                cartridge_dir,
                list(prompt_directives.keys()),
            )
        else:
            prompt_directives = {}
            logger.info(
                "No prompt_directives.yaml found in %r — using empty directives.",
                cartridge_dir,
            )

        # ── bot_lore.md ───────────────────────────────────────────────────
        lore_path = base / "bot_lore.md"
        if not lore_path.exists():
            raise FileNotFoundError(f"bot_lore.md not found in {cartridge_dir!r}")

        # ── derive initial state from schema defaults ─────────────────────
        initial_state = _build_initial_state(yare_config.get("state_schema", {}))

        return LoadedCartridge(
            yare_config=yare_config,
            prompt_directives=prompt_directives,
            lore_path=str(lore_path),
            initial_state=initial_state,
        )
