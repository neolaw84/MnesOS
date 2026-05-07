"""
Hierarchical Configuration for MnesOS runtime.

Implements the ``MnesOSRuntimeConfig`` schema and the ``ConfigMerger`` that
combines three layers of settings in ascending order of precedence:

    Cartridge Defaults  <  Player Settings  <  Request Overrides

Aligned with ``docs/design/0006-stateless-phase-2.md`` §2 (Hierarchical
Configuration contract).
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class LLMRoleConfig(BaseModel):
    """Configuration for a single LLM role (director, narrator, npc, embedding)."""

    provider: str = "openrouter"
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class MnesOSRuntimeConfig(BaseModel):
    """The final, merged configuration used for a single ``process_turn`` request."""

    director_llm: LLMRoleConfig = LLMRoleConfig()
    narrator_llm: LLMRoleConfig = LLMRoleConfig()
    npc_llm: LLMRoleConfig = LLMRoleConfig()
    embedding_llm: LLMRoleConfig = LLMRoleConfig()

    # Cartridge specifics mapped into the run
    yare_config: Dict[str, Any] = {}
    prompt_directives: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Merger
# ---------------------------------------------------------------------------

_LLM_ROLE_KEYS = ("director_llm", "narrator_llm", "npc_llm", "embedding_llm")


def _deep_update(base: dict, override: dict) -> dict:
    """Return a new dict that deep-merges *override* into *base*.

    Nested dicts are merged recursively; all other values are replaced.
    Neither *base* nor *override* is mutated.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


class ConfigMerger:
    """Utility for building a :class:`MnesOSRuntimeConfig` from layered dicts."""

    @staticmethod
    def merge(
        cartridge_defaults: dict,
        player_settings: dict,
        request_overrides: dict,
    ) -> MnesOSRuntimeConfig:
        """Merge three config layers into a :class:`MnesOSRuntimeConfig`.

        Precedence (highest wins):

        1. *request_overrides*
        2. *player_settings*
        3. *cartridge_defaults*

        Each input dict may contain any subset of the top-level keys defined
        in :class:`MnesOSRuntimeConfig`.  LLM role keys (``director_llm``,
        ``narrator_llm``, ``npc_llm``, ``embedding_llm``) are merged
        recursively so that a player can override only ``temperature`` without
        having to specify the full role config.

        Parameters
        ----------
        cartridge_defaults:
            Typically built from a :class:`~MnesOS.cartridge.LoadedCartridge`
            (``yare_config``, ``prompt_directives``, and optional LLM hints).
        player_settings:
            Persisted player preferences (e.g. preferred provider/model).
        request_overrides:
            Per-request overrides supplied by the frontend for this turn.

        Returns
        -------
        MnesOSRuntimeConfig
        """
        merged: dict = {}
        for layer in (cartridge_defaults, player_settings, request_overrides):
            merged = _deep_update(merged, layer)

        # Build per-role LLMRoleConfig objects from the merged dicts
        role_configs: Dict[str, LLMRoleConfig] = {}
        for role in _LLM_ROLE_KEYS:
            role_data = merged.get(role)
            if isinstance(role_data, dict):
                role_configs[role] = LLMRoleConfig(**role_data)
            elif isinstance(role_data, LLMRoleConfig):
                role_configs[role] = role_data
            else:
                role_configs[role] = LLMRoleConfig()

        return MnesOSRuntimeConfig(
            **role_configs,
            yare_config=merged.get("yare_config", {}),
            prompt_directives=merged.get("prompt_directives", {}),
        )
