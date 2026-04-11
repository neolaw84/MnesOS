"""
CartridgeLoader — load-time validation for MnesOS cartridge directories.

A cartridge directory must contain:
  yare.yaml              — procedural rules (YARE config, no prompts)
  bot_lore.md            — vector RAG source text
  prompt_directives.yaml — optional narrative tone directives for LLM nodes

Scrutiny layers applied at load time:

  prompt_directives.yaml
    - Only keys "director", "narrator", "npc_brain" are allowed.
    - Each value must be a plain string within MAX_DIRECTIVE_LEN chars.
    - Combined total must not exceed MAX_TOTAL_DIRECTIVE_LEN chars.
    - Injection-pattern blocklist is applied to every directive.

  yare.yaml
    - "prompt_directives" key is rejected outright (belongs in the other file).
    - state_schema domain/field names must not clash with reserved interpreter
      names (state, temp, inputs, macros, config).
    - Every note.message is length-capped and injection-pattern checked.
    - Every call.event must reference a declared event name.
    - Static var paths (non-@ strings) must be rooted at "state." or "temp.".
    - Macro expressions must be @-prefixed strings within MAX_MACRO_LEN chars.
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_DIRECTIVE_KEYS: Set[str] = {"director", "narrator", "npc_brain"}

MAX_DIRECTIVE_LEN = 1024 * 1024        # chars — single directive (1MB)
MAX_TOTAL_DIRECTIVE_LEN = 2 * 1024 * 1024  # chars — all directives combined (2MB)
MAX_NOTE_MSG_LEN = 300          # chars — single note.message
MAX_MACRO_LEN = 200             # chars — single macro expression

RESERVED_NAMES: Set[str] = {"state", "temp", "inputs", "macros", "config"}

# Patterns that are strong indicators of LLM prompt-injection attempts.
# Applied to prompt_directives and note.message fields.
_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(above|previous|all|prior|instructions)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|actually)\b", re.IGNORECASE),
    # "SYSTEM:" alone is a legitimate engine-note prefix in cartridges.
    # Only flag it when followed by a known injection payload keyword.
    re.compile(r"\bsystem\s*:\s*(you\s+are|ignore|override|forget|disregard|act\s+as)", re.IGNORECASE),
    re.compile(r"#{1,6}\s*(system|instructions|override)", re.IGNORECASE),
    re.compile(r"<[^>]{1,60}>"),            # HTML/XML-like tags
    re.compile(r"\[INST\]|</?s>|\[/INST\]", re.IGNORECASE),  # LLaMA tokens
    re.compile(r"\n---\n"),                  # delimiter spoofing (engine uses ---)
    re.compile(r"https?://"),               # URL-based exfiltration
    re.compile(r"\b(disregard|override|jailbreak|bypass)\b", re.IGNORECASE),
    re.compile(r"new\s+(persona|role|instructions|context)\b", re.IGNORECASE),
    re.compile(r"(act|pretend|behave)\s+as\s+(if\s+)?you", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class LoadedCartridge:
    """Fully validated, runtime-ready cartridge."""
    yare_config: Dict[str, Any]
    prompt_directives: Dict[str, str]
    lore_path: str
    initial_state: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_injection(text: str, location: str) -> None:
    """Raise ValueError if text matches any known injection pattern."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"Potential prompt injection in {location!r}: "
                f"matched pattern /{pattern.pattern}/"
            )


def _build_initial_state(state_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Derive initial runtime state from state_schema 'default' values."""
    state: Dict[str, Any] = {}
    for domain, fields in state_schema.items():
        if not isinstance(fields, dict):
            continue
        if "type" in fields:
            # Top-level scalar field (e.g. current_location: {type: string, ...})
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
    """Validate and sanitize the content of prompt_directives.yaml."""
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
                f"Directive {key!r} must be a plain string, got {type(value).__name__}."
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
    """Block reserved names in state_schema domains and field names."""
    for domain, fields in schema.items():
        if domain in RESERVED_NAMES:
            raise ValueError(
                f"state_schema domain {domain!r} clashes with a reserved name."
            )
        if not isinstance(fields, dict) or "type" in fields:
            continue
        for field_name in fields:
            if field_name in RESERVED_NAMES:
                raise ValueError(
                    f"state_schema field {domain}.{field_name!r} clashes with "
                    f"a reserved name."
                )


def _validate_macros(macros: Dict[str, Any]) -> None:
    """Enforce that macros are @-prefixed strings within the length cap."""
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
    """Recursively validate action steps within an event."""
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        loc = f"events.{event_name}.steps[{i}]"
        action = step.get("action")

        # note.message — injection check + length cap
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

        # call.event — must reference a declared event
        if action == "call":
            called = step.get("event")
            if called not in declared_events:
                raise ValueError(
                    f"{loc} calls undefined event {called!r}. "
                    f"Declared events: {declared_events}"
                )

        # static var paths must be rooted at state.* or temp.*
        if action in ("set", "mutate"):
            var = step.get("var", "")
            if isinstance(var, str) and not var.startswith("@"):
                root = var.split(".")[0]
                if root not in ("state", "temp"):
                    raise ValueError(
                        f"{loc}.var {var!r} must start with 'state.' or 'temp.'."
                    )

        # recurse into branch conditions
        if action == "branch":
            for cond in step.get("conditions", []):
                _validate_steps(cond.get("steps", []), event_name, declared_events)


def _validate_events(events: Dict[str, Any]) -> None:
    """Validate all events in the YARE config."""
    declared_events: Set[str] = set(events.keys())
    for event_name, event_body in events.items():
        if not isinstance(event_body, dict):
            continue
        _validate_steps(
            event_body.get("steps", []), event_name, declared_events
        )


def _validate_yare(config: Dict[str, Any]) -> None:
    """Run all deterministic checks on a loaded yare.yaml dict."""
    if "prompt_directives" in config:
        raise ValueError(
            "'prompt_directives' must live in prompt_directives.yaml, "
            "not in yare.yaml. Keep yare.yaml purely procedural."
        )
    
    # Validate separate_npc_brain flag (optional, defaults to False)
    if "separate_npc_brain" in config:
        separate_npc_brain = config["separate_npc_brain"]
        if not isinstance(separate_npc_brain, bool):
            raise ValueError(
                "separate_npc_brain must be a boolean (true or false), "
                f"got {type(separate_npc_brain).__name__}."
            )
    
    _validate_state_schema(config.get("state_schema", {}))
    _validate_macros(config.get("macros", {}))
    _validate_events(config.get("events", {}))


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

class CartridgeLoader:
    """
    Load and validate a cartridge directory.

    Usage::

        loader = CartridgeLoader()
        cartridge = loader.load("cartridges/generic-rpg")

        # Pass results into GameState:
        initial_state = {
            ...
            "yare_config": cartridge.yare_config,
            "prompt_directives": cartridge.prompt_directives,
            "lore_path": cartridge.lore_path,
            "bot_memory": cartridge.initial_state,
        }
    """

    def load(self, cartridge_dir: str) -> LoadedCartridge:
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
                "prompt_directives.yaml validated for cartridge %r "
                "(keys: %s)",
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
