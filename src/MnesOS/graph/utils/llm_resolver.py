"""
LLM resolution helper for LangGraph nodes.

Nodes call :func:`resolve_llm` to obtain a LangChain chat model from the
``RunnableConfig["configurable"]`` dict, falling back to a closure-injected
instance (legacy / test support) and finally returning ``None`` (dry-run).

Resolution order
----------------
1. *fallback* — closure arg provided at graph-compile time (legacy / tests).
2. Dynamic — ``configurable["llm_clients"]`` (raw keys dict) +
   ``configurable["{role}_llm"]`` (LLMRoleConfig dict) → built via LLMFactory.
3. ``None`` — no LLM available; node runs in dry-run mode.
"""

from __future__ import annotations

from typing import Any, Optional

from ...config import LLMRoleConfig
from ...llm import build_default_factory

# Module-level factory shared across all nodes in the same process.
_llm_factory = build_default_factory()


def resolve_llm(
    configurable: dict,
    role: str,
    fallback: Optional[Any] = None,
) -> Optional[Any]:
    """Return a LangChain chat model for *role*, or ``None`` in dry-run mode.

    Parameters
    ----------
    configurable:
        The ``config["configurable"]`` dict from the node's ``RunnableConfig``.
    role:
        One of ``"director"``, ``"narrator"``, ``"npc"``.  The function looks
        for ``configurable["{role}_llm"]`` (a serialised :class:`LLMRoleConfig`
        dict) and ``configurable["llm_clients"]`` (the raw keys dict from
        :func:`~MnesOS.api.deps.get_llm_clients`).
    fallback:
        A pre-built LangChain model injected at graph-compile time (used by
        tests and the legacy CLI path).  Checked first.

    Returns
    -------
    BaseChatModel | None
    """
    if fallback is not None:
        return fallback

    keys = configurable.get("llm_clients") or {}
    role_config_dict = configurable.get(f"{role}_llm") or {}

    if keys and isinstance(keys, dict) and role_config_dict and isinstance(role_config_dict, dict):
        try:
            role_cfg = LLMRoleConfig(**role_config_dict)
            return _llm_factory.create_chat_client(role_cfg, keys)
        except (ValueError, ImportError):
            pass

    return None
