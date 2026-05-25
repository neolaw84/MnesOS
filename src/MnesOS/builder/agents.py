"""
Builder Agents — Architect & Specialist Multi-Agent System.

[MnesOS-260507-09] Implements a LangGraph-style orchestrator that delegates
cartridge generation to specialized workers:
  - Architect: Coordinates and integrates the overall cartridge
  - Lore Master: Handles markdown worldbuilding
  - Mechanic (YARE Expert): Handles game rules and state logic
  - Prompter: Handles LLM role steering and intro narrative
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SpecialistRole(Enum):
    """Specialist agent roles in the builder pipeline."""
    ARCHITECT = "architect"
    LORE_MASTER = "lore_master"
    MECHANIC = "mechanic"
    PROMPTER = "prompter"


@dataclass
class BuilderRequest:
    """Input request for the builder agent system."""
    requirements: str
    existing_content: Optional[Dict[str, str]] = None


@dataclass
class BuilderResult:
    """Output of the builder agent system — a complete 4-file cartridge."""
    bot_lore: str
    first_message: str
    prompt_directives: str
    yare_spec: str


# ---------------------------------------------------------------------------
# Specialist Prompts
# ---------------------------------------------------------------------------

_LORE_MASTER_PROMPT = """You are the Lore Master specialist for MnesOS cartridge generation.
Your job is to write rich, immersive world lore in Markdown format.

Requirements: {requirements}

{existing_context}

Generate the bot_lore.md content. Write detailed world background, characters,
locations, and history. Output ONLY the markdown content."""

_MECHANIC_PROMPT = """You are the YARE Mechanic specialist for MnesOS cartridge generation.
Your job is to write valid YARE game rules in YAML format.

Requirements: {requirements}

{existing_context}

Generate valid YARE YAML with:
- state_schema (with types, defaults, visibility)
- events (with steps using action/mutate/branch/note/roll)
- macros (if needed)

Include rich YAML comments for every generated state/event.
Output ONLY the YAML content (no code fences)."""

_PROMPTER_PROMPT = """You are the Prompter specialist for MnesOS cartridge generation.
Your job is to write LLM role steering directives and the intro narrative.

Requirements: {requirements}

{existing_context}

Generate two outputs separated by "---SPLIT---":
1. prompt_directives.yaml content (keys: director, narrator, npc)
2. first_message.md content (the opening narrative)

Output format:
<DIRECTIVES>
director: [your director prompt]
narrator: [your narrator prompt]
npc: [your npc prompt]
</DIRECTIVES>
---SPLIT---
<FIRST_MESSAGE>
[Your opening narrative]
</FIRST_MESSAGE>"""

_ARCHITECT_PROMPT = """You are the Architect for MnesOS cartridge generation.
You coordinate the overall cartridge design based on requirements.

Requirements: {requirements}

{existing_context}

Provide a brief design plan (2-3 sentences each) for:
1. World/Lore theme
2. Game mechanics and state variables
3. Narrative tone and character voice

Output a short design brief."""


class BuilderOrchestrator:
    """Orchestrates specialist agents to generate a complete cartridge.

    Uses a simple sequential pipeline:
    1. Architect creates a design brief
    2. Lore Master generates bot_lore.md
    3. Mechanic generates yare.yaml
    4. Prompter generates prompt_directives.yaml + first_message.md
    """

    def __init__(self, llm: Any):
        self._llm = llm

    def generate(self, request: BuilderRequest) -> BuilderResult:
        """Generate a complete 4-file cartridge from a requirements prompt."""
        existing_context = self._format_existing(request.existing_content)

        # Step 1: Architect designs the plan
        architect_brief = self._invoke_specialist(
            _ARCHITECT_PROMPT, request.requirements, existing_context
        )

        # Step 2: Lore Master generates world lore
        lore_context = f"Design Brief: {architect_brief}\n\n{existing_context}"
        bot_lore = self._invoke_specialist(
            _LORE_MASTER_PROMPT, request.requirements, lore_context
        )

        # Step 3: Mechanic generates YARE rules
        mechanic_context = f"Design Brief: {architect_brief}\n\n{existing_context}"
        yare_spec = self._invoke_specialist(
            _MECHANIC_PROMPT, request.requirements, mechanic_context
        )

        # Step 4: Prompter generates directives and first message
        prompter_context = f"Design Brief: {architect_brief}\nWorld Lore Summary: {bot_lore[:500]}\n\n{existing_context}"
        prompter_output = self._invoke_specialist(
            _PROMPTER_PROMPT, request.requirements, prompter_context
        )

        prompt_directives, first_message = self._parse_prompter_output(prompter_output)

        return BuilderResult(
            bot_lore=bot_lore or "# World Lore\n\nA mysterious world awaits.",
            first_message=first_message or "You find yourself at the beginning of an adventure.",
            prompt_directives=prompt_directives or "director: Guide the player through the story",
            yare_spec=yare_spec or "state_schema: {}\nevents: {}\nmacros: {}",
        )

    def _invoke_specialist(self, prompt_template: str, requirements: str, context: str) -> str:
        """Invoke a specialist LLM with a formatted prompt."""
        prompt = prompt_template.format(
            requirements=requirements,
            existing_context=context,
        )
        try:
            response = self._llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as e:
            logger.warning(f"Specialist invocation failed: {e}")
            return ""

    def _format_existing(self, existing: Optional[Dict[str, str]]) -> str:
        """Format existing content as context for specialists."""
        if not existing:
            return ""
        parts = []
        for key, value in existing.items():
            if value:
                parts.append(f"--- Existing {key} ---\n{value[:2000]}")
        return "\n\n".join(parts)

    def _parse_prompter_output(self, output: str) -> tuple[str, str]:
        """Parse the prompter's combined output into directives and first message."""
        if "---SPLIT---" in output:
            parts = output.split("---SPLIT---", 1)
            directives = self._extract_between(parts[0], "<DIRECTIVES>", "</DIRECTIVES>")
            first_msg = self._extract_between(parts[1], "<FIRST_MESSAGE>", "</FIRST_MESSAGE>")
            return directives or parts[0].strip(), first_msg or parts[1].strip()

        # Fallback: use the entire output as both
        return output[:500], output[500:] if len(output) > 500 else output

    def _extract_between(self, text: str, start_tag: str, end_tag: str) -> str:
        """Extract text between tags."""
        pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""
