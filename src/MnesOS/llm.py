"""
LLM Provider Factory for MnesOS.

Implements the ``LLMProvider`` interface and the ``LLMFactory`` registry that
allows the engine to remain completely agnostic to which LLM backend is
actually being used at runtime.

Aligned with ``docs/design/0006-stateless-phase-2.md`` §3 (LLM Provider
Factory / [MnesOS-260507-05]).

Concrete providers:
    - :class:`OpenRouterProvider` — ChatOpenAI pointed at OpenRouter's API.
    - :class:`GeminiProvider`     — Google Generative AI via langchain-google-genai.

Usage::

    from MnesOS.config import LLMRoleConfig
    from MnesOS.llm import build_default_factory

    factory = build_default_factory()
    chat = factory.create_chat_client(
        LLMRoleConfig(provider="openrouter", model_name="google/gemini-2.5-flash"),
        keys={"openrouter_key": "sk-..."},
    )
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from .config import LLMRoleConfig


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Contract for any LLM Provider (OpenRouter, Gemini, Local, …)."""

    @abstractmethod
    def get_chat_model(self, config: LLMRoleConfig, keys: dict) -> BaseChatModel:
        """Return a configured LangChain :class:`~langchain_core.language_models.BaseChatModel`.

        Parameters
        ----------
        config:
            Role-specific LLM settings (model name, temperature, max_tokens…).
        keys:
            Provider-specific credentials extracted from the request headers.
            Concrete providers document the expected key names.
        """

    @abstractmethod
    def get_embeddings_model(self, config: LLMRoleConfig, keys: dict) -> Embeddings:
        """Return a configured LangChain :class:`~langchain_core.embeddings.Embeddings`.

        Parameters
        ----------
        config:
            Role-specific LLM settings (model name, …).
        keys:
            Provider-specific credentials.
        """


# ---------------------------------------------------------------------------
# Concrete: OpenRouter
# ---------------------------------------------------------------------------

_OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    """LLM provider backed by `OpenRouter <https://openrouter.ai>`_.

    Expected key names
    ------------------
    ``openrouter_key``
        The caller's OpenRouter API key (``sk-or-...``).  Must be supplied by
        the request via the ``X-OpenRouter-Key`` header — no server-side
        env-var fallback is provided (strict BYOK).
    ``openrouter_base_url`` *(optional)*
        Override the base URL (useful for tests / proxies).
    """

    def get_chat_model(self, config: LLMRoleConfig, keys: dict) -> BaseChatModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "langchain_openai is required for OpenRouterProvider. "
                "Install it with: pip install langchain-openai"
            ) from exc

        api_key = keys.get("openrouter_key", "")
        base_url = (
            keys.get("openrouter_base_url")
            or os.environ.get("OPENROUTER_BASE_URL")
            or _OPENROUTER_DEFAULT_BASE_URL
        )

        model_name = config.model_name or "google/gemini-2.5-flash"
        kwargs: dict = {
            "model": model_name,
            "api_key": api_key,
            "base_url": base_url,
            "temperature": config.temperature,
            "default_headers": {
                "HTTP-Referer": "https://github.com/neolaw84/MnesOS",
                "X-Title": "MnesOS",
            },
        }
        if config.max_tokens is not None:
            kwargs["max_tokens"] = config.max_tokens

        return ChatOpenAI(**kwargs)

    def get_embeddings_model(self, config: LLMRoleConfig, keys: dict) -> Embeddings:
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise ImportError(
                "langchain_openai is required for OpenRouterProvider. "
                "Install it with: pip install langchain-openai"
            ) from exc

        api_key = keys.get("openrouter_key", "")
        base_url = (
            keys.get("openrouter_base_url")
            or os.environ.get("OPENROUTER_BASE_URL")
            or _OPENROUTER_DEFAULT_BASE_URL
        )

        model_name = config.model_name or "text-embedding-ada-002"
        return OpenAIEmbeddings(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
        )


# ---------------------------------------------------------------------------
# Concrete: Gemini (Google Generative AI)
# ---------------------------------------------------------------------------


class GeminiProvider(LLMProvider):
    """LLM provider backed by Google Generative AI (Gemini).

    Requires ``langchain-google-genai``::

        pip install langchain-google-genai

    Expected key names
    ------------------
    ``gemini_key``
        The caller's Google AI Studio API key.  Falls back to the
        ``GOOGLE_API_KEY`` environment variable.
    """

    def get_chat_model(self, config: LLMRoleConfig, keys: dict) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError(
                "langchain_google_genai is required for GeminiProvider. "
                "Install it with: pip install langchain-google-genai"
            ) from exc

        api_key = (
            keys.get("gemini_key")
            or os.environ.get("GOOGLE_API_KEY", "")
        )

        kwargs: dict = {
            "model": config.model_name,
            "google_api_key": api_key,
            "temperature": config.temperature,
        }
        if config.max_tokens is not None:
            kwargs["max_output_tokens"] = config.max_tokens

        return ChatGoogleGenerativeAI(**kwargs)

    def get_embeddings_model(self, config: LLMRoleConfig, keys: dict) -> Embeddings:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except ImportError as exc:
            raise ImportError(
                "langchain_google_genai is required for GeminiProvider. "
                "Install it with: pip install langchain-google-genai"
            ) from exc

        api_key = (
            keys.get("gemini_key")
            or os.environ.get("GOOGLE_API_KEY", "")
        )

        return GoogleGenerativeAIEmbeddings(
            model=config.model_name,
            google_api_key=api_key,
        )


# ---------------------------------------------------------------------------
# Factory / Registry
# ---------------------------------------------------------------------------


class LLMFactory:
    """Registry and factory for instantiating concrete LLM providers.

    Providers are registered under short names (``"openrouter"``,
    ``"gemini"``, ``"local"``, …).  The :class:`~MnesOS.config.LLMRoleConfig`
    ``provider`` field is used as the registry key at dispatch time.

    Example::

        factory = LLMFactory()
        factory.register_provider("openrouter", OpenRouterProvider())
        chat = factory.create_chat_client(role_cfg, keys={"openrouter_key": "sk-..."})
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """Register *provider* under *name*.  Overwrites any existing entry."""
        self._providers[name] = provider

    def create_chat_client(self, config: LLMRoleConfig, keys: dict) -> BaseChatModel:
        """Resolve the provider for ``config.provider`` and return a chat model.

        Raises
        ------
        ValueError
            If no provider is registered under ``config.provider``.
        """
        provider = self._providers.get(config.provider)
        if provider is None:
            raise ValueError(
                f"Unknown provider: {config.provider!r}. "
                f"Registered providers: {list(self._providers.keys())}"
            )
        return provider.get_chat_model(config, keys)

    def create_embeddings_client(self, config: LLMRoleConfig, keys: dict) -> Embeddings:
        """Resolve the provider for ``config.provider`` and return an embeddings model.

        Raises
        ------
        ValueError
            If no provider is registered under ``config.provider``.
        """
        provider = self._providers.get(config.provider)
        if provider is None:
            raise ValueError(
                f"Unknown provider: {config.provider!r}. "
                f"Registered providers: {list(self._providers.keys())}"
            )
        return provider.get_embeddings_model(config, keys)


# ---------------------------------------------------------------------------
# Convenience factory builder
# ---------------------------------------------------------------------------


def build_default_factory() -> LLMFactory:
    """Return an :class:`LLMFactory` pre-populated with all built-in providers.

    Providers registered:
      - ``"openrouter"`` → :class:`OpenRouterProvider`
      - ``"gemini"``     → :class:`GeminiProvider`
    """
    factory = LLMFactory()
    factory.register_provider("openrouter", OpenRouterProvider())
    factory.register_provider("gemini", GeminiProvider())
    return factory
