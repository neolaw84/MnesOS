"""
CartridgeLoader — load-time validation for MnesOS cartridge directories.

A cartridge directory must contain:
  yare.yaml              — procedural rules (YARE config, no prompts)
  bot_lore.md            — vector RAG source text
  prompt_directives.yaml — optional narrative tone directives for LLM nodes

Scrutiny layers applied at load time:

  prompt_directives.yaml
    - Only keys "director", "narrator", "npc" are allowed.
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
from typing import Any, Dict, List, Mapping, Optional, Set

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_DIRECTIVE_KEYS: Set[str] = {"director", "narrator", "npc"}

MAX_DIRECTIVE_LEN = 1024 * 1024        # chars — single directive (1MB)
MAX_TOTAL_DIRECTIVE_LEN = 2 * 1024 * 1024  # chars — all directives combined (2MB)
MAX_NOTE_MSG_LEN = 300          # chars — single note.message
MAX_MACRO_LEN = 200             # chars — single macro expression
MAX_CONTAINER_SIZE = 100        # max items in a list or keys in a dict
MAX_DICT_DEPTH = 3              # max nesting depth for dict fields

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
    lore_content: str
    first_message: str = ""
    persona_context: Dict[str, str] = field(default_factory=dict)
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


def _extract_persona_tokens(persona: Optional[Any]) -> Dict[str, str]:
    """Extract canonical persona tokens used for macro compilation and prompt context."""
    if persona is None:
        return {}

    def getter(key: str) -> Any:
        if isinstance(persona, Mapping):
            return persona.get(key)
        return getattr(persona, key, None)

    return {
        "user": str(getter("name") or ""),
        "sub": str(getter("pronoun_sub") or ""),
        "obj": str(getter("pronoun_obj") or ""),
        "poss": str(getter("pronoun_poss") or ""),
        "poss_obj": str(getter("pronoun_poss_obj") or ""),
        "appearance": str(getter("appearance") or ""),
        "background": str(getter("background") or ""),
        "personality": str(getter("personality") or ""),
    }


def _compile_persona_macros(text: str, persona_tokens: Dict[str, str]) -> str:
    """Deterministically replace standard persona macros in text."""
    if not text or not persona_tokens:
        return text

    compiled = text
    macro_map = {
        "{{user}}": persona_tokens.get("user", ""),
        "{{sub}}": persona_tokens.get("sub", ""),
        "{{obj}}": persona_tokens.get("obj", ""),
        "{{poss}}": persona_tokens.get("poss", ""),
        "{{poss_obj}}": persona_tokens.get("poss_obj", ""),
    }
    for macro, replacement in macro_map.items():
        compiled = compiled.replace(macro, replacement)
    return compiled


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

def _compute_dict_depth(d: Any) -> int:
    """Return the nesting depth of a dict.

    Returns 1 for a flat dict, 2 for one level of nesting, etc.
    Non-dict values do not contribute a level.
    """
    if not isinstance(d, dict) or not d:
        return 0
    return 1 + max(_compute_dict_depth(v) for v in d.values())


def _validate_container_default(spec: Dict[str, Any], loc: str) -> None:
    """Enforce MAX_CONTAINER_SIZE and MAX_DICT_DEPTH on a schema field's default value."""
    field_type = spec.get("type")
    default = spec.get("default")
    if default is None:
        return
    if field_type == "list":
        if isinstance(default, list) and len(default) > MAX_CONTAINER_SIZE:
            raise ValueError(
                f"{loc}: default list length {len(default)} exceeds "
                f"MAX_CONTAINER_SIZE ({MAX_CONTAINER_SIZE})."
            )
    elif field_type == "dict":
        if isinstance(default, dict):
            if len(default) > MAX_CONTAINER_SIZE:
                raise ValueError(
                    f"{loc}: default dict size {len(default)} exceeds "
                    f"MAX_CONTAINER_SIZE ({MAX_CONTAINER_SIZE})."
                )
            if _compute_dict_depth(default) > MAX_DICT_DEPTH:
                raise ValueError(
                    f"{loc}: default dict depth exceeds MAX_DICT_DEPTH ({MAX_DICT_DEPTH})."
                )


def _validate_state_schema(schema: Dict[str, Any]) -> None:
    """Block reserved names in state_schema domains and field names; enforce container limits."""
    for domain, fields in schema.items():
        if domain in RESERVED_NAMES:
            raise ValueError(
                f"state_schema domain {domain!r} clashes with a reserved name."
            )
        if not isinstance(fields, dict) or "type" in fields:
            if isinstance(fields, dict):
                _validate_container_default(fields, f"state_schema.{domain}")
            continue
        for field_name, field_spec in fields.items():
            if field_name in RESERVED_NAMES:
                raise ValueError(
                    f"state_schema field {domain}.{field_name!r} clashes with "
                    f"a reserved name."
                )
            if isinstance(field_spec, dict):
                _validate_container_default(field_spec, f"state_schema.{domain}.{field_name}")


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


# ---------------------------------------------------------------------------
# Step-level validators (Single Responsibility handlers)
# ---------------------------------------------------------------------------

def _validate_note_step(step: Dict[str, Any], loc: str) -> None:
    """Validate a note action: length cap and injection check."""
    msg = step.get("message", "")
    if not isinstance(msg, str):
        raise ValueError(f"{loc}.message must be a string.")
    if len(msg) > MAX_NOTE_MSG_LEN:
        raise ValueError(
            f"{loc}.message exceeds max length "
            f"({len(msg)} > {MAX_NOTE_MSG_LEN} chars)."
        )
    _check_injection(msg, f"{loc}.message")


def _validate_call_step(step: Dict[str, Any], loc: str, declared_events: Set[str]) -> None:
    """Validate a call action: referenced event must be declared."""
    called = step.get("event")
    if called not in declared_events:
        raise ValueError(
            f"{loc} calls undefined event {called!r}. "
            f"Declared events: {declared_events}"
        )


def _validate_var_step(step: Dict[str, Any], loc: str) -> None:
    """Validate that a static var path is rooted at state.* or temp.*."""
    var = step.get("var", "")
    if isinstance(var, str) and not var.startswith("@"):
        root = var.split(".")[0]
        if root not in ("state", "temp"):
            raise ValueError(
                f"{loc}.var {var!r} must start with 'state.' or 'temp.'."
            )


def _validate_list_push_step(step: Dict[str, Any], loc: str) -> None:
    """Validate a list_push action: var path must be rooted at state.* or temp.*."""
    _validate_var_step(step, loc)


def _validate_list_remove_step(step: Dict[str, Any], loc: str) -> None:
    """Validate a list_remove action: var path and presence of index or value."""
    _validate_var_step(step, loc)
    if "index" not in step and "value" not in step:
        raise ValueError(
            f"{loc}: list_remove must specify either 'index' or 'value'."
        )


def _validate_dict_set_step(step: Dict[str, Any], loc: str) -> None:
    """Validate a dict_set action: var path must be rooted at state.* or temp.*."""
    _validate_var_step(step, loc)


def _validate_dict_delete_step(step: Dict[str, Any], loc: str) -> None:
    """Validate a dict_delete action: var path must be rooted at state.* or temp.*."""
    _validate_var_step(step, loc)


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

        if action == "note":
            _validate_note_step(step, loc)
        elif action == "call":
            _validate_call_step(step, loc, declared_events)
        elif action in ("set", "mutate"):
            _validate_var_step(step, loc)
        elif action == "list_push":
            _validate_list_push_step(step, loc)
        elif action == "list_remove":
            _validate_list_remove_step(step, loc)
        elif action == "dict_set":
            _validate_dict_set_step(step, loc)
        elif action == "dict_delete":
            _validate_dict_delete_step(step, loc)
        elif action == "branch":
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


def _validate_npc_templates(templates: Any) -> None:
    """Validate the optional npc_templates mapping in yare.yaml."""
    if not isinstance(templates, dict):
        raise ValueError("npc_templates must be a YAML mapping.")

    valid_types = {"name", "tag"}
    for key, entry in templates.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"npc_templates entry {key!r} must be a mapping with 'type' and 'description'."
            )
        entry_type = entry.get("type")
        if entry_type not in valid_types:
            raise ValueError(
                f"npc_templates entry {key!r} has invalid type {entry_type!r}. "
                f"Allowed values: {valid_types}."
            )
        description = entry.get("description")
        if description is None or not isinstance(description, str):
            raise ValueError(
                f"npc_templates entry {key!r} must have a 'description' string."
            )


def _validate_yare(config: Dict[str, Any]) -> None:
    """Run all deterministic checks on a loaded yare.yaml dict."""
    if "prompt_directives" in config:
        raise ValueError(
            "'prompt_directives' must live in prompt_directives.yaml, "
            "not in yare.yaml. Keep yare.yaml purely procedural."
        )
    
    # Validate separate_npc flag (optional, defaults to False)
    if "separate_npc" in config:
        separate_npc = config["separate_npc"]
        if not isinstance(separate_npc, bool):
            raise ValueError(
                "separate_npc must be a boolean (true or false), "
                f"got {type(separate_npc).__name__}."
            )

    # Validate npc_templates (optional)
    if "npc_templates" in config:
        _validate_npc_templates(config["npc_templates"])

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

    def load(self, cartridge_dir: str, persona: Optional[Any] = None) -> LoadedCartridge:
        base = Path(cartridge_dir)
        persona_tokens = _extract_persona_tokens(persona)

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
            prompt_directives = {
                key: _compile_persona_macros(value, persona_tokens)
                for key, value in prompt_directives.items()
            }
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
        lore_content = _compile_persona_macros(
            lore_path.read_text(encoding="utf-8"), persona_tokens
        )

        # ── first-message.md (optional) ───────────────────────────────────
        fm_path = base / "first-message.md"
        first_message = ""
        if fm_path.exists():
            first_message = _compile_persona_macros(
                fm_path.read_text(encoding="utf-8"), persona_tokens
            )

        # ── derive initial state from schema defaults ─────────────────────
        initial_state = _build_initial_state(yare_config.get("state_schema", {}))

        return LoadedCartridge(
            yare_config=yare_config,
            prompt_directives=prompt_directives,
            lore_path=str(lore_path),
            lore_content=lore_content,
            first_message=first_message,
            persona_context={
                "appearance": persona_tokens.get("appearance", ""),
                "background": persona_tokens.get("background", ""),
                "personality": persona_tokens.get("personality", ""),
            },
            initial_state=initial_state,
        )

    def load_from_version(self, version: Any, persona: Optional[Any] = None) -> LoadedCartridge:
        """Load a cartridge directly from a CartridgeVersion DB record."""
        persona_tokens = _extract_persona_tokens(persona)

        yare_config = version.yare_spec
        _validate_yare(yare_config)
        logger.info("yare_spec validated from CartridgeVersion %s", version.id)

        prompt_directives = {
            key: _compile_persona_macros(value, persona_tokens)
            for key, value in version.prompt_directives.items()
        }
        logger.info(
            "prompt_directives validated from CartridgeVersion %s (keys: %s)",
            version.id,
            list(prompt_directives.keys()),
        )

        lore_content = _compile_persona_macros(
            version.bot_lore, persona_tokens
        )

        first_message = _compile_persona_macros(
            getattr(version, "first_message", ""), persona_tokens
        )

        initial_state = _build_initial_state(yare_config.get("state_schema", {}))

        return LoadedCartridge(
            yare_config=yare_config,
            prompt_directives=prompt_directives,
            lore_path=f"db://{version.id}",
            lore_content=lore_content,
            first_message=first_message,
            persona_context={
                "appearance": persona_tokens.get("appearance", ""),
                "background": persona_tokens.get("background", ""),
                "personality": persona_tokens.get("personality", ""),
            },
            initial_state=initial_state,
        )

