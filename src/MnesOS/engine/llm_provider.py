"""
LLM Provider Abstraction Layer for MnesOS.

Provides abstract interfaces for LLM and embedding providers to enable
multi-model and multi-provider support. Merges LLM provisioning with
hierarchical configuration.

Aligned with docs/to-do-260507.md Phase 2 [MnesOS-260507-05 & 06].
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field


class MnesOSRuntimeConfig(BaseModel):
    """Merged configuration passed into LangGraph's RunnableConfig.

    This configuration combines cartridge defaults, player settings,
    and request-level overrides to provide hierarchical control over
    LLM parameters.
    """

    cartridge_id: str
    provider_name: str = "openrouter"
    model_name: str = "anthropic/claude-3-opus"
    temperature: float = 0.7
    max_tokens: int = 1024
    provider_kwargs: Dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM and embedding providers.

    Implementations instantiate provider-specific chat models and embeddings
    (e.g., ChatOpenAI wrapper for OpenRouter, ChatGoogleGenerativeAI for Gemini).
    """

    @abstractmethod
    def get_chat_model(self, config: MnesOSRuntimeConfig) -> BaseChatModel:
        """Instantiate the provider's chat model.

        Parameters
        ----------
        config : MnesOSRuntimeConfig
            The merged runtime configuration containing model parameters.

        Returns
        -------
        BaseChatModel
            A LangChain chat model instance configured for this provider.
        """
        pass

    @abstractmethod
    def get_embeddings(self, config: MnesOSRuntimeConfig) -> Embeddings:
        """Instantiate the provider's embeddings model.

        Parameters
        ----------
        config : MnesOSRuntimeConfig
            The merged runtime configuration containing model parameters.

        Returns
        -------
        Embeddings
            A LangChain embeddings instance configured for this provider.
        """
        pass
