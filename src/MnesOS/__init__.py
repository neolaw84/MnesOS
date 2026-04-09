"""MnesOS - MnesOS is fully Agentic RPG Game Engine.."""

__version__ = "0.1.0"
__author__ = "neolaw84"
__email__ = "neolaw@gmail.com"

from .cartridge import CartridgeLoader, LoadedCartridge
from .context import VectorLoreStore
from .graph import GameState, workflow, trigger_event
from .interpreter import YAREInterpreter
from .prompts import DIRECTOR_SYSTEM_PROMPT, NARRATOR_SYSTEM_PROMPT, NPC_BRAIN_SYSTEM_PROMPT

__all__ = [
    "CartridgeLoader",
    "LoadedCartridge",
    "VectorLoreStore",
    "GameState",
    "workflow",
    "trigger_event",
    "YAREInterpreter",
    "DIRECTOR_SYSTEM_PROMPT",
    "NARRATOR_SYSTEM_PROMPT",
    "NPC_BRAIN_SYSTEM_PROMPT",
]
