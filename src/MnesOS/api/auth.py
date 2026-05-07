"""
Auth Abstraction Layer for MnesOS.

Provides abstract interfaces to decouple from specific auth providers
(OpenRouter PKCE, Google OAuth, etc.).

Aligned with docs/to-do-260507.md Phase 2 [MnesOS-260507-04].
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel


class AuthSession(BaseModel):
    """Represents a validated authentication session."""

    user_id: str
    provider: str
    access_token: str
    metadata: Dict[str, Any]


class AuthValidator(ABC):
    """Abstract base class for token validation strategies."""

    @abstractmethod
    async def validate_token(self, token: str) -> AuthSession:
        """Validates the raw token/PKCE payload and constructs the session.

        Parameters
        ----------
        token : str
            The raw authentication token to validate.

        Returns
        -------
        AuthSession
            A validated session containing user_id, provider, access_token, and metadata.

        Raises
        ------
        HTTPException
            If the token is invalid or expired.
        """
        pass


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns
        -------
        str
            Provider name, e.g., 'openrouter_pkce', 'google_oauth'.
        """
        pass

    @abstractmethod
    def get_validator(self) -> AuthValidator:
        """Return the validator instance for this provider.

        Returns
        -------
        AuthValidator
            The validator implementation for this auth provider.
        """
        pass


class AuthFactory:
    """Factory for instantiating auth providers based on request headers."""

    _providers: Dict[str, AuthProvider] = {}

    @classmethod
    def register_provider(cls, provider: AuthProvider) -> None:
        """Register an auth provider in the factory.

        Parameters
        ----------
        provider : AuthProvider
            The provider instance to register.
        """
        cls._providers[provider.provider_name] = provider

    @staticmethod
    def get_provider(x_provider_header: str) -> AuthProvider:
        """Look up and return the registered provider.

        Parameters
        ----------
        x_provider_header : str
            The value from the X-Provider request header.

        Returns
        -------
        AuthProvider
            The registered provider instance.

        Raises
        ------
        KeyError
            If no provider is registered for the given name.
        """
        if x_provider_header not in AuthFactory._providers:
            raise KeyError(
                f"Auth provider '{x_provider_header}' not registered. "
                f"Available providers: {list(AuthFactory._providers.keys())}"
            )
        return AuthFactory._providers[x_provider_header]
