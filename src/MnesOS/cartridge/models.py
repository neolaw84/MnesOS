"""
cartridge.models — Data containers for a loaded MnesOS cartridge.

This module intentionally uses the standard-library ``dataclasses`` module
rather than Pydantic models.  Pydantic would give us automatic runtime
type-checking "for free", but it introduces an extra dependency and its
validation behaviour can change between minor versions, which complicates
backtracking.

Migration note (Pydantic)
~~~~~~~~~~~~~~~~~~~~~~~~~
If the team decides to adopt Pydantic in the future, the migration path is
straightforward:

1. Replace::

       from dataclasses import dataclass, field
       @dataclass
       class LoadedCartridge: ...

   with::

       from pydantic.dataclasses import dataclass
       # or
       from pydantic import BaseModel
       class LoadedCartridge(BaseModel): ...

2. Remove the ``field(default_factory=dict)`` for ``initial_state`` — Pydantic
   uses ``default_factory`` the same way, so the field definition itself barely
   changes.

3. The ``validators.py`` module would then be mostly superseded by Pydantic
   field validators (``@field_validator``), though the injection-pattern
   blocklist should remain as an explicit security check regardless.

All other modules (``loader.py``, ``orchestrator.py``) depend only on the
*attribute names* of ``LoadedCartridge``, not on the class type itself, so
swapping the base class is non-breaking.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LoadedCartridge:
    """
    Fully validated, runtime-ready cartridge.

    Produced by :class:`~MnesOS.cartridge.loader.CartridgeLoader` after
    successfully parsing and validating all files in a cartridge directory.

    Attributes:
        yare_config:        Parsed contents of ``yare.yaml``.  Contains the
                            procedural rule definitions (events, macros,
                            state_schema) but *never* prompt_directives.
        prompt_directives:  Parsed, sanitised contents of
                            ``prompt_directives.yaml``.  Each key is one of
                            ``"director"``, ``"narrator"``, ``"npc_brain"``;
                            each value is a plain prompt-extension string.
        lore_path:          Absolute path (as a string) to ``bot_lore.md``.
                            Passed to :class:`~MnesOS.context.VectorLoreStore`
                            at graph execution time.
        initial_state:      Flat dict of state values derived from the
                            ``default`` fields declared in
                            ``yare_config["state_schema"]``.  Used by the
                            Orchestrator to seed a fresh :class:`~MnesOS.graph.GameState`.
    """

    yare_config: Dict[str, Any]
    prompt_directives: Dict[str, str]
    lore_path: str
    # ``initial_state`` is derived at load time; an empty dict is a valid
    # initial state (cartridge may declare no schema defaults).
    initial_state: Dict[str, Any] = field(default_factory=dict)
