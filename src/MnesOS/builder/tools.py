"""
Builder Tools — YARE Translator & Auto-Validator.

[MnesOS-260507-10] Provides:
  - yare_translate: English → (YAML Block + Logic Explanation)
  - cartridge_validate: Wraps CartridgeLoader validation for builder feedback
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

import yaml

from ..cartridge import (
    ALLOWED_DIRECTIVE_KEYS,
    MAX_DIRECTIVE_LEN,
    MAX_TOTAL_DIRECTIVE_LEN,
    _check_injection,
)

logger = logging.getLogger(__name__)


def yare_translate(
    english_description: str,
    llm: Any,
) -> Dict[str, str]:
    """Translate an English game rule description into a YARE YAML block.

    Args:
        english_description: Plain English description of the game rule.
        llm: An LLM client instance with an .invoke() method.

    Returns:
        A dict with "yaml_block" (the generated YAML) and "explanation"
        (a plain-English logic explanation).
    """
    prompt = (
        "You are a YARE (YARE Agentic Rules Engine) expert for the MnesOS RPG system.\n\n"
        "Convert the following English game rule description into valid YARE YAML.\n"
        "Use YARE actions: set, mutate (op: add/sub/mul/div), branch (if/else), "
        "note (message), roll (NdM format), call (event), foreach.\n\n"
        f"Description: {english_description}\n\n"
        "Output format:\n"
        "```yaml\n[your YARE YAML here]\n```\n"
        "EXPLANATION: [brief explanation of what the YAML does]"
    )

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.warning(f"YARE translate failed: {e}")
        return {"yaml_block": "", "explanation": f"Translation failed: {e}"}

    # Parse the response
    yaml_block = _extract_yaml_block(content)
    explanation = _extract_explanation(content)

    return {
        "yaml_block": yaml_block,
        "explanation": explanation,
    }


def cartridge_validate(
    yare_spec: Dict[str, Any],
    prompt_directives: Dict[str, str],
    bot_lore: str,
    first_message: str,
) -> Dict[str, Any]:
    """Validate a cartridge's components and return structured feedback.

    Args:
        yare_spec: The parsed YARE specification dict.
        prompt_directives: The prompt directives dict.
        bot_lore: The bot lore markdown content.
        first_message: The first message content.

    Returns:
        A dict with "valid" (bool), "errors" (list of error strings),
        and "warnings" (list of warning strings).
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Validate YARE spec structure
    _validate_yare_spec(yare_spec, errors, warnings)

    # Validate prompt directives
    _validate_directives(prompt_directives, errors, warnings)

    # Validate bot_lore
    if not bot_lore or not bot_lore.strip():
        warnings.append("bot_lore is empty. Consider adding world background.")

    # Validate first_message
    if not first_message or not first_message.strip():
        warnings.append("first_message is empty. Consider adding an intro narrative.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _extract_yaml_block(content: str) -> str:
    """Extract a YAML code block from LLM response."""
    match = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: try to find YAML-like content
    lines = content.split("\n")
    yaml_lines = [l for l in lines if not l.startswith("EXPLANATION")]
    return "\n".join(yaml_lines).strip()


def _extract_explanation(content: str) -> str:
    """Extract the EXPLANATION line from LLM response."""
    match = re.search(r"EXPLANATION:\s*(.+)", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _validate_yare_spec(
    spec: Dict[str, Any], errors: List[str], warnings: List[str]
) -> None:
    """Validate the YARE specification dict structure."""
    if not isinstance(spec, dict):
        errors.append("yare_spec must be a dict.")
        return

    # Required top-level keys
    if "state_schema" not in spec:
        errors.append("yare_spec is missing required 'state_schema' key.")

    if "events" not in spec:
        errors.append("yare_spec is missing required 'events' key.")

    if "macros" not in spec:
        warnings.append("yare_spec is missing 'macros' key (defaults to empty).")

    # Validate events structure
    events = spec.get("events", {})
    if isinstance(events, dict):
        for event_name, event_def in events.items():
            if not isinstance(event_def, dict):
                errors.append(f"Event '{event_name}' must be a dict.")
                continue
            if "steps" not in event_def:
                errors.append(f"Event '{event_name}' is missing 'steps' key.")

    # Validate state_schema structure
    state_schema = spec.get("state_schema", {})
    if not isinstance(state_schema, dict):
        errors.append("state_schema must be a dict.")


def _validate_directives(
    directives: Dict[str, str], errors: List[str], warnings: List[str]
) -> None:
    """Validate prompt directives."""
    if not isinstance(directives, dict):
        errors.append("prompt_directives must be a dict.")
        return

    for key, value in directives.items():
        if key not in ALLOWED_DIRECTIVE_KEYS:
            warnings.append(
                f"Directive key '{key}' is not standard. "
                f"Allowed keys: {sorted(ALLOWED_DIRECTIVE_KEYS)}"
            )

        if not isinstance(value, str):
            errors.append(f"Directive '{key}' value must be a string.")
            continue

        if len(value) > MAX_DIRECTIVE_LEN:
            errors.append(
                f"Directive '{key}' exceeds max length ({len(value)} > {MAX_DIRECTIVE_LEN})."
            )

        # Check for injection patterns
        try:
            _check_injection(value, f"prompt_directives.{key}")
        except ValueError as e:
            errors.append(f"Potential injection in directive '{key}': {e}")

    # Check total length
    total_len = sum(len(v) for v in directives.values() if isinstance(v, str))
    if total_len > MAX_TOTAL_DIRECTIVE_LEN:
        errors.append(
            f"Combined directives exceed max total length ({total_len} > {MAX_TOTAL_DIRECTIVE_LEN})."
        )
