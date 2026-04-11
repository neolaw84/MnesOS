"""
MnesOS cartridge sub-package — everything cartridge-related in one place.

Public API
~~~~~~~~~~

**Data containers** (from :mod:`.models`):

.. autoclass:: LoadedCartridge
   :members:

**Validators** (from :mod:`.validators`):

The private ``_validate_*`` helpers are re-exported here so that test suites
and advanced callers can import them directly from ``MnesOS.cartridge``
without needing to know the internal sub-module layout.  Their leading
underscore signals that they are *implementation details* subject to change,
but they are deliberately kept importable for white-box testing.

.. autofunction:: _validate_prompt_directives
.. autofunction:: _validate_yare
.. autofunction:: _validate_state_schema
.. autofunction:: _validate_macros
.. autofunction:: _validate_events
.. autofunction:: _build_initial_state
.. autodata:: MAX_DIRECTIVE_LEN
.. autodata:: MAX_TOTAL_DIRECTIVE_LEN
.. autodata:: MAX_NOTE_MSG_LEN
.. autodata:: MAX_MACRO_LEN

**Loader** (from :mod:`.loader`):

.. autoclass:: CartridgeLoader
   :members:

Backward compatibility
~~~~~~~~~~~~~~~~~~~~~~
All names previously importable from the flat ``MnesOS.cartridge`` module
(``src/MnesOS/cartridge.py``) remain importable from ``MnesOS.cartridge``
(this package).  Any existing ``from MnesOS.cartridge import X`` statement
will continue to work without modification.

Sub-package layout
~~~~~~~~~~~~~~~~~~
::

    MnesOS/cartridge/
    ├── __init__.py      ← you are here; re-exports public API
    ├── models.py        ← LoadedCartridge dataclass
    ├── validators.py    ← pure validation functions and constants
    └── loader.py        ← CartridgeLoader (filesystem + YAML parsing)
"""

# --- models ---
from .models import LoadedCartridge

# --- validators (constants) ---
from .validators import (
    ALLOWED_DIRECTIVE_KEYS,
    MAX_DIRECTIVE_LEN,
    MAX_MACRO_LEN,
    MAX_NOTE_MSG_LEN,
    MAX_TOTAL_DIRECTIVE_LEN,
    RESERVED_NAMES,
)

# --- validators (functions) ---
# Private helpers are re-exported intentionally; they are used directly in
# unit tests and by downstream callers who need fine-grained validation.
from .validators import (
    _build_initial_state,
    _check_injection,
    _validate_events,
    _validate_macros,
    _validate_prompt_directives,
    _validate_state_schema,
    _validate_steps,
    _validate_yare,
)

# --- loader ---
from .loader import CartridgeLoader

__all__ = [
    # models
    "LoadedCartridge",
    # validators — constants
    "ALLOWED_DIRECTIVE_KEYS",
    "MAX_DIRECTIVE_LEN",
    "MAX_MACRO_LEN",
    "MAX_NOTE_MSG_LEN",
    "MAX_TOTAL_DIRECTIVE_LEN",
    "RESERVED_NAMES",
    # validators — helpers (exported for testing / advanced use)
    "_build_initial_state",
    "_check_injection",
    "_validate_events",
    "_validate_macros",
    "_validate_prompt_directives",
    "_validate_state_schema",
    "_validate_steps",
    "_validate_yare",
    # loader
    "CartridgeLoader",
]
