"""
Auth Abstraction Layer for MnesOS.

Implements the ``AuthProvider`` / ``LLMAuthValidator`` interface and the
``AuthFactory`` registry that allows the engine to remain agnostic to
which identity / LLM-key provider is in use at runtime.

Aligned with ``docs/design/0006-stateless-phase-2.md`` §1 (Auth & Identity
Abstraction / [MnesOS-260507-04]).

Classes
-------
AuthContext
    Pydantic model carrying resolved identity for one request.
AuthProvider
    ABC: ``resolve_identity(headers) → AuthContext``.
LLMAuthValidator
    ABC: ``validate_provider_keys(headers) → dict``.
OpenRouterPKCE
    Concrete strategy: JWT Bearer token → AuthContext + OpenRouter key extraction.
LocalAuthProvider
    Concrete strategy: always returns a local identity (dev / offline mode).
AuthFactory
    Static factory that selects the correct provider from ``X-Provider`` header.
"""

from __future__ import annotations

import base64
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# AuthContext
# ---------------------------------------------------------------------------


class AuthContext(BaseModel):
    """Resolved identity for a single request.

    Parameters
    ----------
    user_id:
        Non-empty string identifier for the authenticated user.
    is_local:
        ``True`` when running in local/offline dev mode.
    metadata:
        Arbitrary provider-specific extras (roles, tier, etc.).
    """

    user_id: str
    is_local: bool = False
    metadata: Dict[str, Any] = {}

    @field_validator("user_id")
    @classmethod
    def _user_id_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("user_id must be a non-empty string")
        return v


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------


class AuthProvider(ABC):
    """Abstract strategy for resolving user identity from request headers."""

    @abstractmethod
    def resolve_identity(self, headers: dict) -> AuthContext:
        """Resolve identity from *headers* and return an :class:`AuthContext`.

        Parameters
        ----------
        headers:
            Case-normalised request headers (lowercase keys recommended).

        Raises
        ------
        ValueError
            If required identity headers are absent or malformed.
        """


class LLMAuthValidator(ABC):
    """Abstract strategy for extracting and validating LLM provider API keys."""

    @abstractmethod
    def validate_provider_keys(self, headers: dict) -> dict:
        """Extract LLM provider credentials from *headers*.

        Returns
        -------
        dict
            Provider-specific keys (e.g. ``{"openrouter_key": "sk-…"}``).

        Raises
        ------
        ValueError
            If required API key headers are missing or invalid.
        """


# ---------------------------------------------------------------------------
# Concrete: OpenRouterPKCE
# ---------------------------------------------------------------------------


def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload of a JWT without verifying the signature.

    Raises
    ------
    ValueError
        If *token* is not a three-segment JWT or the payload cannot be parsed.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"Malformed JWT: expected 3 segments, got {len(parts)}")

    payload_b64 = parts[1]
    # Restore padding
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception as exc:
        raise ValueError(f"JWT payload decoding failed: {exc}") from exc


class OpenRouterPKCE(AuthProvider, LLMAuthValidator):
    """Auth strategy for the OpenRouter PKCE flow.

    Identity
    --------
    Reads a ``Authorization: Bearer <jwt>`` header and extracts the ``sub``
    claim as ``user_id``.

    LLM keys
    --------
    Reads the ``X-OpenRouter-Key`` header and returns it as
    ``{"openrouter_key": value}``.
    """

    # ------------------------------------------------------------------
    # AuthProvider
    # ------------------------------------------------------------------

    def resolve_identity(self, headers: dict) -> AuthContext:
        """Extract user identity from a JWT Bearer token.

        Parameters
        ----------
        headers:
            Request headers (keys should be lowercase).

        Raises
        ------
        ValueError
            If ``authorization`` header is missing, not a Bearer scheme,
            or the JWT payload cannot be decoded / lacks a ``sub`` claim.
        """
        auth_header: Optional[str] = headers.get("authorization")
        if not auth_header:
            raise ValueError("Missing 'authorization' header")

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer":
            raise ValueError(
                f"Unsupported authorization scheme: {scheme!r}. Expected 'Bearer'."
            )

        payload = _decode_jwt_payload(token)
        sub = payload.get("sub")
        if not sub:
            raise ValueError("JWT payload missing 'sub' claim")

        return AuthContext(user_id=sub, is_local=False)

    # ------------------------------------------------------------------
    # LLMAuthValidator
    # ------------------------------------------------------------------

    def validate_provider_keys(self, headers: dict) -> dict:
        """Extract the OpenRouter API key from the ``X-OpenRouter-Key`` header.

        Raises
        ------
        ValueError
            If the header is absent or empty.
        """
        key = headers.get("x-openrouter-key") or headers.get("X-OpenRouter-Key")
        if not key:
            raise ValueError(
                "Missing 'X-OpenRouter-Key' header required for OpenRouter provider."
            )
        return {"openrouter_key": key}


# ---------------------------------------------------------------------------
# Concrete: LocalAuthProvider (dev / offline mode)
# ---------------------------------------------------------------------------

_LOCAL_USER_ID = "local-user"


class LocalAuthProvider(AuthProvider):
    """Auth provider for local / offline development mode.

    Always returns a fixed :class:`AuthContext` with ``is_local=True``
    regardless of what headers are present.
    """

    def resolve_identity(self, headers: dict) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id=_LOCAL_USER_ID, is_local=True)


# ---------------------------------------------------------------------------
# AuthFactory
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, type[AuthProvider]] = {
    "openrouter": OpenRouterPKCE,
    "local": LocalAuthProvider,
}

_DEFAULT_PROVIDER = "openrouter"


class AuthFactory:
    """Static factory that selects an :class:`AuthProvider` from request headers.

    The ``X-Provider`` header (case-insensitive) determines which strategy is
    returned.  If the header is absent the default provider (``openrouter``) is
    used.

    Example::

        provider = AuthFactory.create({"x-provider": "openrouter"})
        ctx = provider.resolve_identity(request_headers)
    """

    @staticmethod
    def create(headers: dict) -> AuthProvider:
        """Return the :class:`AuthProvider` matching the ``x-provider`` header.

        Parameters
        ----------
        headers:
            Request headers (keys compared case-insensitively).

        Raises
        ------
        ValueError
            If the ``x-provider`` value is not a registered provider name.
        """
        provider_name = (
            headers.get("x-provider")
            or headers.get("X-Provider")
            or _DEFAULT_PROVIDER
        ).lower()

        provider_cls = _PROVIDER_REGISTRY.get(provider_name)
        if provider_cls is None:
            registered = list(_PROVIDER_REGISTRY.keys())
            raise ValueError(
                f"Unknown auth provider: {provider_name!r}. "
                f"Registered providers: {registered}"
            )
        return provider_cls()
