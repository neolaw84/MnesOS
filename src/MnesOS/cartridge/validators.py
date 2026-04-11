"""
cartridge.validators — Load-time validation for MnesOS cartridge files.

This module contains **pure functions** that validate the two structured
YAML files that every cartridge must (or optionally may) ship:

* ``prompt_directives.yaml`` — narrative tone hints for LLM nodes.
* ``yare.yaml`` — procedural rules (YARE config).

Design decisions
~~~~~~~~~~~~~~~~
* All functions are *pure* (no I/O) and raise :exc:`ValueError` on the
  first error they encounter.  Callers in ``loader.py`` catch these and
  re-raise with file-location context when helpful.
* No Pydantic is used here.  Each validation rule is an explicit Python
  ``if`` / ``raise`` block so that the logic is fully auditable and can
  be stepped through with a debugger or patched in tests without any
  Pydantic machinery.
* The injection-pattern blocklist (``_INJECTION_PATTERNS``) is intentionally
  conservative.  If a legitimate cartridge author's text is accidentally
  blocked, the pattern can be tightened in ``_INJECTION_PATTERNS`` rather
  than relaxing the check globally.

Pydantic migration note
~~~~~~~~~~~~~~~~~~~~~~~
If you later adopt Pydantic, consider replacing the individual
``_validate_*`` calls with ``@field_validator`` / ``model_validator``
decorators on the ``LoadedCartridge`` model.  Keep the
``_check_injection`` helper as a standalone function — it is a security
control that should survive any model-library swap.
"""

import re
from typing import Any, Dict, List, Set

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Only these keys are permitted in ``prompt_directives.yaml``.
ALLOWED_DIRECTIVE_KEYS: Set[str] = {"director", "narrator", "npc_brain"}

#: Maximum length (chars) for a single directive value.
MAX_DIRECTIVE_LEN: int = 1024 * 1024          # 1 MB

#: Maximum combined length (chars) for all directive values.
MAX_TOTAL_DIRECTIVE_LEN: int = 2 * 1024 * 1024  # 2 MB

#: Maximum length (chars) for a single ``note.message`` field in YARE events.
MAX_NOTE_MSG_LEN: int = 300

#: Maximum length (chars) for a single YARE macro expression.
MAX_MACRO_LEN: int = 200

#: State-variable names that the YARE interpreter reserves for internal use.
#: Cartridge authors must not declare ``state_schema`` domain or field names
#: that clash with these names.
RESERVED_NAMES: Set[str] = {"state", "temp", "inputs", "macros", "config"}

# ---------------------------------------------------------------------------
# Injection-pattern blocklist
# ---------------------------------------------------------------------------

# Each pattern is a regular expression that matches text strongly associated
# with LLM prompt-injection attacks.  Applied to ``prompt_directives.yaml``
# values and to ``note.message`` fields inside ``yare.yaml`` events.
#
# Guidelines for extending this list:
#   * Prefer anchored / bounded patterns (``\b``) to avoid false positives.
#   * Patterns are matched case-insensitively unless stated otherwise.
#   * Add a comment explaining the attack vector each pattern guards against.
_INJECTION_PATTERNS: List[re.Pattern] = [
    # Classic "ignore previous instructions" injections
    re.compile(r"ignore\s+(above|previous|all|prior|instructions)", re.IGNORECASE),
    # Identity-swap openers
    re.compile(r"you\s+are\s+(now|actually)\b", re.IGNORECASE),
    # "SYSTEM:" prefix is valid for engine notes, but only flag it when
    # followed by a known injection keyword.
    re.compile(
        r"\bsystem\s*:\s*(you\s+are|ignore|override|forget|disregard|act\s+as)",
        re.IGNORECASE,
    ),
    # Markdown heading followed by a control keyword
    re.compile(r"#{1,6}\s*(system|instructions|override)", re.IGNORECASE),
    # HTML/XML-like tags (potential template injection or output manipulation)
    re.compile(r"<[^>]{1,60}>"),
    # LLaMA-family special tokens
    re.compile(r"\[INST\]|</?s>|\[/INST\]", re.IGNORECASE),
    # Delimiter spoofing — the engine uses "\n---\n" as a section separator
    re.compile(r"\n---\n"),
    # URL-based exfiltration
    re.compile(r"https?://"),
    # Single-word override verbs
    re.compile(r"\b(disregard|override|jailbreak|bypass)\b", re.IGNORECASE),
    # "New persona/role/instructions/context" injections
    re.compile(r"new\s+(persona|role|instructions|context)\b", re.IGNORECASE),
    # Role-play redirects
    re.compile(r"(act|pretend|behave)\s+as\s+(if\s+)?you", re.IGNORECASE),
]


def _check_injection(text: str, location: str) -> None:
    """
    Raise :exc:`ValueError` if *text* matches any known injection pattern.

    Args:
        text:     The string to inspect.
        location: Human-readable description used in the error message
                  (e.g. ``"prompt_directives.narrator"``).

    Raises:
        ValueError: If a blocklisted pattern is found.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"Potential prompt injection in {location!r}: "
                f"matched pattern /{pattern.pattern}/"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_initial_state(state_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive the initial runtime state from ``state_schema`` ``default`` values.

    Walks the ``state_schema`` mapping and collects every field's ``default``
    value into a flat-by-domain dict:

    * A top-level *scalar* field (one that has a ``"type"`` key directly under
      the domain) is stored at ``state[domain]``.
    * A *nested* domain (a dict of sub-fields without a ``"type"`` key at
      the top level) is stored as ``state[domain][field_name]``.

    Args:
        state_schema: The ``state_schema`` mapping from a validated
                      ``yare_config`` dict.

    Returns:
        A fresh ``dict`` that represents the initial game state.  Fields with
        no ``"default"`` declared will be present with a value of ``None``.
    """
    state: Dict[str, Any] = {}
    for domain, fields in state_schema.items():
        if not isinstance(fields, dict):
            continue
        if "type" in fields:
            # Top-level scalar field, e.g. ``current_location: {type: string, ...}``
            state[domain] = fields.get("default")
        else:
            state[domain] = {
                k: v.get("default")
                for k, v in fields.items()
                if isinstance(v, dict)
            }
    return state


# ---------------------------------------------------------------------------
# Validators — prompt_directives.yaml
# ---------------------------------------------------------------------------

def _validate_prompt_directives(raw: Any) -> Dict[str, str]:
    """
    Validate and sanitize the content of ``prompt_directives.yaml``.

    Checks:
    * The top-level value must be a YAML mapping (dict).
    * Only ``ALLOWED_DIRECTIVE_KEYS`` (``"director"``, ``"narrator"``,
      ``"npc_brain"``) are permitted.
    * Each value must be a plain ``str``.
    * Individual values must not exceed ``MAX_DIRECTIVE_LEN`` chars.
    * The combined length of all values must not exceed
      ``MAX_TOTAL_DIRECTIVE_LEN`` chars.
    * Each value is passed through the injection-pattern blocklist.

    Args:
        raw: The Python object produced by ``yaml.safe_load`` of the file.

    Returns:
        A ``Dict[str, str]`` containing only the validated key/value pairs.

    Raises:
        ValueError: On any constraint violation.
    """
    if not isinstance(raw, dict):
        raise ValueError("prompt_directives.yaml must be a YAML mapping.")

    unknown = set(raw.keys()) - ALLOWED_DIRECTIVE_KEYS
    if unknown:
        raise ValueError(
            f"Unknown directive keys: {unknown}. Allowed: {ALLOWED_DIRECTIVE_KEYS}"
        )

    cleaned: Dict[str, str] = {}
    total_len = 0

    for key, value in raw.items():
        if not isinstance(value, str):
            raise ValueError(
                f"Directive {key!r} must be a plain string, "
                f"got {type(value).__name__}."
            )
        if len(value) > MAX_DIRECTIVE_LEN:
            raise ValueError(
                f"Directive {key!r} exceeds max length "
                f"({len(value)} > {MAX_DIRECTIVE_LEN} chars)."
            )
        _check_injection(value, f"prompt_directives.{key}")
        cleaned[key] = value
        total_len += len(value)

    if total_len > MAX_TOTAL_DIRECTIVE_LEN:
        raise ValueError(
            f"Combined directive text ({total_len} chars) exceeds max allowed "
            f"({MAX_TOTAL_DIRECTIVE_LEN} chars)."
        )

    return cleaned


# ---------------------------------------------------------------------------
# Validators — yare.yaml
# ---------------------------------------------------------------------------

def _validate_state_schema(schema: Dict[str, Any]) -> None:
    """
    Block reserved names in ``state_schema`` domain and field names.

    The YARE interpreter reserves a set of root-level names (``state``,
    ``temp``, ``inputs``, ``macros``, ``config``) for its own namespaces.
    Cartridge authors must not use these names as domain or field names
    because the interpreter would silently shadow or corrupt them at runtime.

    Args:
        schema: The ``state_schema`` mapping from ``yare_config``.

    Raises:
        ValueError: If any domain or field name clashes with
                    :data:`RESERVED_NAMES`.
    """
    for domain, fields in schema.items():
        if domain in RESERVED_NAMES:
            raise ValueError(
                f"state_schema domain {domain!r} clashes with a reserved name."
            )
        # A domain that itself carries a ``"type"`` key is a scalar field —
        # it has no sub-fields to inspect.
        if not isinstance(fields, dict) or "type" in fields:
            continue
        for field_name in fields:
            if field_name in RESERVED_NAMES:
                raise ValueError(
                    f"state_schema field {domain}.{field_name!r} clashes with "
                    f"a reserved name."
                )


def _validate_macros(macros: Dict[str, Any]) -> None:
    """
    Enforce that YARE macros are ``@``-prefixed strings within the length cap.

    A YARE macro expression must begin with ``@`` so that the interpreter
    can distinguish it from a bare literal string.  Macros are also
    length-capped to prevent runaway expressions that could slow down the
    AST evaluator.

    Args:
        macros: The ``macros`` mapping from ``yare_config``.

    Raises:
        ValueError: If any macro expression is not ``@``-prefixed or exceeds
                    :data:`MAX_MACRO_LEN` chars.
    """
    for name, expr in macros.items():
        if not isinstance(expr, str) or not expr.startswith("@"):
            raise ValueError(
                f"Macro {name!r} must be an '@'-prefixed expression string."
            )
        if len(expr) > MAX_MACRO_LEN:
            raise ValueError(
                f"Macro {name!r} exceeds max length "
                f"({len(expr)} > {MAX_MACRO_LEN} chars)."
            )


def _validate_steps(
    steps: List[Any],
    event_name: str,
    declared_events: Set[str],
) -> None:
    """
    Recursively validate action steps within a YARE event.

    Covers:
    * ``note.message`` — injection check + length cap.
    * ``call.event`` — must reference a declared event name.
    * ``set`` / ``mutate``.var — static (non-``@``) paths must be rooted at
      ``state.`` or ``temp.``.
    * ``branch`` — recurses into each condition's ``steps`` list.

    Args:
        steps:            List of step dicts from an event body.
        event_name:       Name of the containing event (used in error messages).
        declared_events:  Set of all event names declared in the YARE config.

    Raises:
        ValueError: On any constraint violation.
    """
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        loc = f"events.{event_name}.steps[{i}]"
        action = step.get("action")

        # --- note.message: injection check + length cap ---
        if action == "note":
            msg = step.get("message", "")
            if not isinstance(msg, str):
                raise ValueError(f"{loc}.message must be a string.")
            if len(msg) > MAX_NOTE_MSG_LEN:
                raise ValueError(
                    f"{loc}.message exceeds max length "
                    f"({len(msg)} > {MAX_NOTE_MSG_LEN} chars)."
                )
            _check_injection(msg, f"{loc}.message")

        # --- call.event: must reference a declared event ---
        if action == "call":
            called = step.get("event")
            if called not in declared_events:
                raise ValueError(
                    f"{loc} calls undefined event {called!r}. "
                    f"Declared events: {declared_events}"
                )

        # --- set / mutate .var: static paths must start with state. or temp. ---
        if action in ("set", "mutate"):
            var = step.get("var", "")
            # Dynamic paths start with ``@`` and are resolved at runtime;
            # we cannot validate them statically.
            if isinstance(var, str) and not var.startswith("@"):
                root = var.split(".")[0]
                if root not in ("state", "temp"):
                    raise ValueError(
                        f"{loc}.var {var!r} must start with 'state.' or 'temp.'."
                    )

        # --- branch: recurse into each condition's nested steps ---
        if action == "branch":
            for cond in step.get("conditions", []):
                _validate_steps(cond.get("steps", []), event_name, declared_events)


def _validate_events(events: Dict[str, Any]) -> None:
    """
    Validate all events in the YARE config.

    Iterates over every event body and delegates to :func:`_validate_steps`
    for step-level validation.

    Args:
        events: The ``events`` mapping from ``yare_config``.

    Raises:
        ValueError: If any event or step fails validation.
    """
    declared_events: Set[str] = set(events.keys())
    for event_name, event_body in events.items():
        if not isinstance(event_body, dict):
            continue
        _validate_steps(
            event_body.get("steps", []), event_name, declared_events
        )


def _validate_yare(config: Dict[str, Any]) -> None:
    """
    Run all deterministic checks on a loaded ``yare.yaml`` dict.

    Validation order:
    1. Reject the ``"prompt_directives"`` key — it must live in the
       separate ``prompt_directives.yaml`` file so that yare.yaml stays
       purely procedural and can be safely logged / version-controlled.
    2. Validate the optional ``separate_npc_brain`` flag (must be bool).
    3. Validate ``state_schema`` domain/field names against reserved names.
    4. Validate macro expressions.
    5. Validate event steps recursively.

    Args:
        config: The Python dict produced by ``yaml.safe_load`` of ``yare.yaml``.

    Raises:
        ValueError: On any constraint violation.
    """
    # 1. Reject prompt_directives inside yare.yaml
    if "prompt_directives" in config:
        raise ValueError(
            "'prompt_directives' must live in prompt_directives.yaml, "
            "not in yare.yaml. Keep yare.yaml purely procedural."
        )

    # 2. Validate separate_npc_brain flag (optional, defaults to False)
    if "separate_npc_brain" in config:
        separate_npc_brain = config["separate_npc_brain"]
        if not isinstance(separate_npc_brain, bool):
            raise ValueError(
                "separate_npc_brain must be a boolean (true or false), "
                f"got {type(separate_npc_brain).__name__}."
            )

    # 3–5. Delegate to sub-validators
    _validate_state_schema(config.get("state_schema", {}))
    _validate_macros(config.get("macros", {}))
    _validate_events(config.get("events", {}))
