"""
Builder Agents — Architect & Specialist Multi-Agent System.

[MnesOS-260507-09] Implements a LangGraph orchestrator that delegates
cartridge generation to specialized workers:
  - Architect: Coordinates and integrates the overall cartridge
  - Lore Master: Handles markdown worldbuilding
  - Mechanic (YARE Expert): Handles game rules and state logic
  - Prompter: Handles LLM role steering and intro narrative
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from ..cartridge import CartridgeLoader

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


class BuilderState(TypedDict):
    """State schema for the builder LangGraph."""
    requirements: str
    existing_content: Optional[Dict[str, str]]
    architect_brief: str
    bot_lore: str
    yare_spec: str
    prompt_directives_yaml: str
    first_message: str
    errors: List[str]
    iteration_count: int


# ---------------------------------------------------------------------------
# Technical Specifications
# ---------------------------------------------------------------------------

def _load_doc(filename: str) -> str:
    """Load documentation from the repository or package docs directory."""
    try:
        # 1. Try relative to this file (works in dev/repo root)
        # From src/MnesOS/builder/agents.py -> up 3 levels to root / docs
        doc_path = Path(__file__).parent.parent.parent.parent / "docs" / filename
        
        # 2. Try inside the package (works when installed via wheel/site-packages)
        if not doc_path.exists():
            doc_path = Path(__file__).parent.parent / "docs" / filename

        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not load doc {filename}: {e}")
    return f"Specification for {filename} is currently unavailable."


YARE_SPEC_DOC = _load_doc("yare-specification.md")
MINIGAMES_SCHEMA_DOC = _load_doc("minigames.schema.json")

# ---------------------------------------------------------------------------
# Specialist Prompts
# ---------------------------------------------------------------------------

_LORE_MASTER_PROMPT = """You are the Lore Master specialist for MnesOS cartridge generation.
Your job is to write the foundational worldbuilding (`bot_lore.md`) that will serve as the immutable background knowledge for the LLM personas during gameplay.

# Context & Requirements
Requirements: {requirements}

{existing_context}

{errors_context}

# How to Synthesize Your Output
MnesOS is a hybrid RPG engine where this lore document is injected into the context window of real-time multi-agent actors (the Narrator, Director, and NPCs).
Your lore needs to establish facts that these actors can reliably draw from to flesh out user interactions.
- Flesh out the world constraints defined in the Architect Brief.
- Describe distinct factions, notable NPCs, key locations, and the overarching mood.
- DO NOT invent literal game mechanic rules (like HP points or dice rolls) here; the Mechanic agent handles that in YAML. You provide the flavor and thematic boundaries.

Output ONLY the markdown content using standard Markdown headers (#, ##, ###) to chunk sections clearly. Do not use code fences.
"""

_MECHANIC_PROMPT = """You are the YARE Mechanic specialist for MnesOS cartridge generation.
Your job is translating the Architect's conceptual design and the Lore Master's world into concrete, deterministic YARE game rules in YAML.

# Context & Requirements
Requirements: {requirements}

{errors_context}

{existing_context}

# Reference Documentation
Below are the reference manuals for the YARE engine and available minigames.
<yare_spec>
{yare_spec_doc}
</yare_spec>

<minigames_spec>
{minigames_doc}
</minigames_spec>

# How to Synthesize Your Output
The YARE rules you define act as the rigid skeletal structure beneath the LLM's narrative roleplay.
You must map the story hooks and mechanics outlined in the Architect Brief into actual `state_schema` and `events`.
- Define state variables that the LLM Directors and Narrators will need to read (mark them `public`).
- Build events that transition the story between distinct phases or act as consequences for player actions.
- Minigame integration requires special attention: Link minigame interactions fluidly with your events.

STRICT RULES:
1. Dice Notation: Use "@ roll(NdM)" without quotes. Example: value: @ roll(2d6)
2. Semantic Grounding: Use `note` steps with "[SYSTEM LOG: message {{state.var}}]" to pass concrete data flashes to the LLM Narrator upon state changes.
3. List/Dict Ops: Use `list_push`, `list_remove`, `dict_set`, `dict_delete`, or `foreach` for complex data.
4. Minigame Event Pairs: Every minigame requires a setup event (triggering it via the `minigame` step configure based on schema) and a consequence event (e.g., `on_puzzle_complete`) to process result.

Write robust, well-commented YAML. Output ONLY the YAML content (no code fences).
"""

_PROMPTER_PROMPT = """You are the Prompter specialist for MnesOS cartridge generation.
Your job is to write LLM role steering directives (`prompt_directives.yaml`) and the intro narrative (`first_message.md`) that shape the player's immediate experience.

# Context & Requirements
Requirements: {requirements}

{existing_context}

{errors_context}

# How to Synthesize Your Output
The Architect defined the overall flow, Lore Master defined the world, and Mechanic configured rigid state variables. You connect these systems to the LLM actors.
- `director` orchestrates pacing and hidden states.
- `narrator` describes the world.
- `npc` controls named characters.
Instruct these personas on *how* to speak and *what* parts of the state matter.

STRICT RULES for prompt_directives.yaml:
1. MnesOS injects dynamic game state into the prompt contexts as `bot_memory`. You must explicitly instruct the personas to check their memory! (e.g. "Adapt tone if bot_memory['player']['hp'] is low.")
2. DO NOT use the archaic "state." prefix. Always refer to state as `bot_memory`.
3. Focus on psychological behavior and tone.

Generate two outputs separated by "---SPLIT---" on its own line:
1. prompt_directives.yaml content (keys: director, narrator, npc)
2. first_message.md content (the opening narrative)

Output format:
director: |
  [your director prompt]
narrator: |
  [your narrator prompt]
npc: |
  [your npc prompt]
---SPLIT---
[Your opening narrative hook]"""

_ARCHITECT_PROMPT = """You are the Architect for the MnesOS text-based RPG engine.
Your job is to coordinate the design of a complete game "cartridge" based on the user's requirements.
A cartridge in MnesOS is a bundle containing the game's lore, its deterministic rules, and its LLM narrative steering prompts.

Requirements: {requirements}

# MnesOS Engine Capabilities Summary
- The engine uses a deterministic YAML-based rule system called "YARE".
- YARE handles states (e.g. Health, Inventory) using variables, numbers, lists.
- YARE supports deterministic minigames that the player can interact with.
  Refer to the provided Minigames Schema for available minigames.
- State variables defined as `public` are visible to the LLM Narrator;
  `private` variables are hidden but can be used for logic.

# Minigames Reference
{minigames_doc}

# Orchestration Role
You must provide a structured design brief that the specialist agents will use.
The agents are Lore Master, Mechanic, and Prompter.
Ensure your plan is formatted as YAML to save tokens while remaining structured.
DO NOT write raw YARE code or full lore text.

Output your design brief in this exact YAML structure:
theme_and_lore: |
  Briefly describe the world, setting, key factions, and general atmosphere.
mechanics_and_state: |
  List the core state variables (e.g. tracking health, clues) and minigames.
narrative_tone: |
  Describe the tone the narrators should take and the voice of the characters.
"""


# ---------------------------------------------------------------------------
# LangGraph Nodes
# ---------------------------------------------------------------------------

def architect_node(state: BuilderState, llm: Any) -> Dict[str, Any]:
    prompt = _ARCHITECT_PROMPT.format(
        requirements=state["requirements"],
        minigames_doc=MINIGAMES_SCHEMA_DOC
    )
    brief = _invoke_llm(llm, prompt)
    return {"architect_brief": brief}


def lore_node(state: BuilderState, llm: Any) -> Dict[str, Any]:
    existing_context = _format_existing(state.get("existing_content"))
    errors_context = _format_errors(state.get("errors"))
    prompt = _LORE_MASTER_PROMPT.format(
        requirements=state["requirements"], 
        existing_context=existing_context,
        errors_context=errors_context
    )
    content = _invoke_llm(llm, prompt)
    return {"bot_lore": content}


def mechanic_node(state: BuilderState, llm: Any) -> Dict[str, Any]:
    existing_context = _format_existing(state.get("existing_content"))
    errors_context = _format_errors(state.get("errors"))
    lore_summary = f"World Lore Info:\n{state.get('bot_lore', '')[:1000]}"
    full_context = f"{existing_context}\n\nArchitect Brief: {state.get('architect_brief')}\n\n{lore_summary}"
    
    prompt = _MECHANIC_PROMPT.format(
        requirements=state["requirements"],
        yare_spec_doc=YARE_SPEC_DOC,
        minigames_doc=MINIGAMES_SCHEMA_DOC,
        existing_context=full_context,
        errors_context=errors_context
    )
    content = _invoke_llm(llm, prompt)
    return {"yare_spec": content}


def prompter_node(state: BuilderState, llm: Any) -> Dict[str, Any]:
    existing_context = _format_existing(state.get("existing_content"))
    errors_context = _format_errors(state.get("errors"))
    lore_summary = f"World Lore Info:\n{state.get('bot_lore', '')[:1000]}"
    full_context = f"{existing_context}\n\nArchitect Brief: {state.get('architect_brief')}\n\n{lore_summary}"

    prompt = _PROMPTER_PROMPT.format(
        requirements=state["requirements"],
        existing_context=full_context,
        errors_context=errors_context
    )
    output = _invoke_llm(llm, prompt)
    directives, first_msg = _parse_prompter_output(output)
    return {"prompt_directives_yaml": directives, "first_message": first_msg}


def validator_node(state: BuilderState) -> Dict[str, Any]:
    yare_spec = state.get("yare_spec", "")
    prompt_directives = state.get("prompt_directives_yaml", "")
    bot_lore = state.get("bot_lore", "")
    first_message = state.get("first_message", "")
    
    errors = []
    
    # If content is clearly dummy/invalid, fail early
    if yare_spec in ["Generated content", "Updated content", "@ roll(1d20)"]:
        errors.append("Invalid YARE content provided by mock/LLM.")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "yare.yaml").write_text(yare_spec)
        (tmp_path / "prompt_directives.yaml").write_text(prompt_directives)
        (tmp_path / "bot_lore.md").write_text(bot_lore)
        (tmp_path / "first-message.md").write_text(first_message)
        
        try:
            loader = CartridgeLoader()
            loader.load(tmp_dir)
        except Exception as e:
            errors.append(f"Cartridge compilation failed: {str(e)}")
            # Print actual error for debugging
            print(f"DEBUG: Validation error: {e}")
            
    return {"errors": errors, "iteration_count": state.get("iteration_count", 0) + 1}


def build_builder_graph(llm: Any):
    from functools import partial
    
    builder = StateGraph(BuilderState)
    
    builder.add_node("architect", partial(architect_node, llm=llm))
    builder.add_node("lore_master", partial(lore_node, llm=llm))
    builder.add_node("mechanic", partial(mechanic_node, llm=llm))
    builder.add_node("prompter", partial(prompter_node, llm=llm))
    builder.add_node("validator", validator_node)
    
    builder.set_entry_point("architect")
    builder.add_edge("architect", "lore_master")
    builder.add_edge("lore_master", "mechanic")
    builder.add_edge("mechanic", "prompter")
    builder.add_edge("prompter", "validator")
    
    def retry_policy(state: BuilderState):
        if state.get("errors") and state.get("iteration_count", 0) < 3:
            return "retry"
        return "end"

    builder.add_conditional_edges(
        "validator",
        retry_policy,
        {
            "retry": "architect", 
            "end": END
        }
    )
    
    return builder.compile()


class BuilderOrchestrator:
    """Orchestrates specialist agents to generate a complete cartridge.

    Uses a LangGraph workflow:
    1. Architect creates a design brief
    2. Lore Master generates bot_lore.md
    3. Mechanic generates yare.yaml
    4. Prompter generates prompt_directives.yaml + first_message.md
    5. Validator checks for compiler errors and retries iff needed
    """

    def __init__(self, llm: Any):
        self._llm = llm
        self._graph = build_builder_graph(llm)

    def generate(self, request: BuilderRequest) -> BuilderResult:
        """Generate a complete 4-file cartridge from a requirements prompt."""
        initial_state = BuilderState(
            requirements=request.requirements,
            existing_content=request.existing_content,
            architect_brief="",
            bot_lore="",
            yare_spec="",
            prompt_directives_yaml="",
            first_message="",
            errors=[],
            iteration_count=0
        )
        
        final_state = self._graph.invoke(initial_state)
        
        return BuilderResult(
            bot_lore=final_state.get("bot_lore") or "# World Lore\\n\\nA mysterious world awaits.",
            first_message=final_state.get("first_message") or "You find yourself at the beginning of an adventure.",
            prompt_directives=final_state.get("prompt_directives_yaml") or "director: Guide the player through the story",
            yare_spec=final_state.get("yare_spec") or "state_schema: {}\\nevents: {}\\nmacros: {}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_llm(llm: Any, prompt: str) -> str:
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}", exc_info=True)
        # Re-raise so the graph or test knows something is wrong
        raise


def _format_existing(existing: Optional[Dict[str, str]]) -> str:
    if not existing:
        return ""
    parts = []
    for key, value in existing.items():
        if value:
            parts.append(f"--- Existing {key} ---\\n{value[:2000]}")
    return "\\n\\n".join(parts)


def _format_errors(errors: Optional[List[str]]) -> str:
    if not errors:
        return ""
    return "--- PREVIOUS ERRORS TO FIX ---\\n" + "\\n".join(errors)


def _parse_prompter_output(output: str) -> tuple[str, str]:
    if "---SPLIT---" in output:
        parts = output.split("---SPLIT---", 1)
        directives = parts[0].strip()
        first_msg = parts[1].strip()
        return directives, first_msg
    return output[:500], output[500:] if len(output) > 500 else output
