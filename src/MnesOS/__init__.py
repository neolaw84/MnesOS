"""MnesOS - MnesOS is fully Agentic RPG Game Engine.."""

from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"
__author__ = "neolaw84"
__email__ = "neolaw@gmail.com"

from .cartridge import CartridgeLoader, LoadedCartridge
from .context import VectorLoreStore
from .graph import GameState, build_graph
from .interpreter import YAREInterpreter
from .orchestrator import Orchestrator
from .prompts import DIRECTOR_SYSTEM_PROMPT, NARRATOR_SYSTEM_PROMPT, NPC_SYSTEM_PROMPT

__all__ = [
    "CartridgeLoader",
    "LoadedCartridge",
    "VectorLoreStore",
    "GameState",
    "build_graph",
    "YAREInterpreter",
    "Orchestrator",
    "DIRECTOR_SYSTEM_PROMPT",
    "NARRATOR_SYSTEM_PROMPT",
    "NPC_SYSTEM_PROMPT",
]
