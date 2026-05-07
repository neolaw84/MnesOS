"""
Unit tests for MnesOS.auth — contract tests for the Stateless Auth Abstraction Layer.

Covers: AuthContext, AuthProvider (ABC), LLMAuthValidator (ABC),
        OpenRouterPKCE concrete strategy, and AuthFactory.

Aligned with ``docs/design/0006-stateless-phase-2.md`` §1 (Auth & Identity
Abstraction / [MnesOS-260507-04]).

All tests express the *required behaviour* of the module.  They will fail until
``src/MnesOS/auth.py`` is implemented and the concrete classes are added.
"""

import pytest
from abc import ABC, abstractmethod
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers – import the module under test (will fail if not yet implemented)
# ---------------------------------------------------------------------------

def _import_auth():
    """Return the auth module, skipping tests gracefully if not yet implemented."""
    try:
        import MnesOS.auth as auth_module
        return auth_module
    except ImportError:
        pytest.fail(
            "MnesOS.auth module is not implemented yet. "
            "Implement src/MnesOS/auth.py to satisfy MnesOS-260507-04."
        )


# ---------------------------------------------------------------------------
# AuthContext
# ---------------------------------------------------------------------------

class TestAuthContext:
    """AuthContext is a Pydantic model that carries resolved identity."""

    def test_importable(self):
        mod = _import_auth()
        assert hasattr(mod, "AuthContext"), "AuthContext must be exported from MnesOS.auth"

    def test_requires_user_id(self):
        mod = _import_auth()
        with pytest.raises(Exception):  # Pydantic ValidationError
            mod.AuthContext()

    def test_user_id_stored(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="player-42")
        assert ctx.user_id == "player-42"

    def test_is_local_defaults_to_false(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="u1")
        assert ctx.is_local is False

    def test_is_local_can_be_set_to_true(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="local-user", is_local=True)
        assert ctx.is_local is True

    def test_metadata_defaults_to_empty_dict(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="u1")
        assert ctx.metadata == {}

    def test_metadata_can_carry_arbitrary_data(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="u1", metadata={"role": "admin", "tier": 1})
        assert ctx.metadata["role"] == "admin"
        assert ctx.metadata["tier"] == 1

    def test_model_is_serialisable(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="u1", is_local=False, metadata={"x": 1})
        d = ctx.model_dump()
        assert d["user_id"] == "u1"
        assert d["is_local"] is False
        assert d["metadata"] == {"x": 1}

    def test_model_roundtrip(self):
        mod = _import_auth()
        ctx = mod.AuthContext(user_id="u99", is_local=True)
        ctx2 = mod.AuthContext(**ctx.model_dump())
        assert ctx2 == ctx


# ---------------------------------------------------------------------------
# AuthProvider (ABC)
# ---------------------------------------------------------------------------

class TestAuthProviderABC:
    """AuthProvider must be an abstract base class."""

    def test_importable(self):
        mod = _import_auth()
        assert hasattr(mod, "AuthProvider"), "AuthProvider must be exported from MnesOS.auth"

    def test_is_abstract(self):
        mod = _import_auth()
        with pytest.raises(TypeError):
            mod.AuthProvider()  # type: ignore[abstract]

    def test_subclass_without_resolve_identity_is_abstract(self):
        mod = _import_auth()

        class IncompleteProvider(mod.AuthProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_concrete_subclass_instantiates(self):
        mod = _import_auth()

        class ConcreteProvider(mod.AuthProvider):
            def resolve_identity(self, headers: dict):
                return mod.AuthContext(user_id="u1")

        provider = ConcreteProvider()
        assert provider is not None

    def test_resolve_identity_signature(self):
        """resolve_identity must accept a headers dict and return AuthContext."""
        mod = _import_auth()

        class ConcreteProvider(mod.AuthProvider):
            def resolve_identity(self, headers: dict):
                return mod.AuthContext(user_id=headers.get("x-user-id", "anon"))

        provider = ConcreteProvider()
        ctx = provider.resolve_identity({"x-user-id": "player-7"})
        assert isinstance(ctx, mod.AuthContext)
        assert ctx.user_id == "player-7"

    def test_resolve_identity_raises_on_missing_identity(self):
        """A well-behaved provider raises ValueError/HTTPException for missing credentials."""
        mod = _import_auth()

        class StrictProvider(mod.AuthProvider):
            def resolve_identity(self, headers: dict):
                uid = headers.get("x-user-id")
                if not uid:
                    raise ValueError("Missing identity header")
                return mod.AuthContext(user_id=uid)

        provider = StrictProvider()
        with pytest.raises((ValueError, Exception)):
            provider.resolve_identity({})


# ---------------------------------------------------------------------------
# LLMAuthValidator (ABC)
# ---------------------------------------------------------------------------

class TestLLMAuthValidatorABC:
    """LLMAuthValidator must be an abstract base class."""

    def test_importable(self):
        mod = _import_auth()
        assert hasattr(mod, "LLMAuthValidator"), (
            "LLMAuthValidator must be exported from MnesOS.auth"
        )

    def test_is_abstract(self):
        mod = _import_auth()
        with pytest.raises(TypeError):
            mod.LLMAuthValidator()  # type: ignore[abstract]

    def test_subclass_without_validate_is_abstract(self):
        mod = _import_auth()

        class Incomplete(mod.LLMAuthValidator):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_instantiates(self):
        mod = _import_auth()

        class ConcreteValidator(mod.LLMAuthValidator):
            def validate_provider_keys(self, headers: dict) -> dict:
                return {"key": headers.get("x-api-key", "")}

        validator = ConcreteValidator()
        assert validator is not None

    def test_validate_provider_keys_returns_dict(self):
        mod = _import_auth()

        class ConcreteValidator(mod.LLMAuthValidator):
            def validate_provider_keys(self, headers: dict) -> dict:
                return {"openrouter_key": headers.get("x-openrouter-key", "")}

        validator = ConcreteValidator()
        result = validator.validate_provider_keys({"x-openrouter-key": "sk-abc"})
        assert isinstance(result, dict)
        assert result.get("openrouter_key") == "sk-abc"

    def test_validate_provider_keys_empty_headers_returns_dict(self):
        mod = _import_auth()

        class PermissiveValidator(mod.LLMAuthValidator):
            def validate_provider_keys(self, headers: dict) -> dict:
                return {}

        validator = PermissiveValidator()
        result = validator.validate_provider_keys({})
        assert isinstance(result, dict)

    def test_validate_provider_keys_raises_on_invalid_key(self):
        """A strict validator raises on invalid/missing keys."""
        mod = _import_auth()

        class StrictValidator(mod.LLMAuthValidator):
            def validate_provider_keys(self, headers: dict) -> dict:
                key = headers.get("x-openrouter-key")
                if not key:
                    raise ValueError("Missing LLM provider key")
                return {"openrouter_key": key}

        validator = StrictValidator()
        with pytest.raises(ValueError):
            validator.validate_provider_keys({})


# ---------------------------------------------------------------------------
# OpenRouterPKCE concrete strategy
# ---------------------------------------------------------------------------

class TestOpenRouterPKCE:
    """OpenRouterPKCE is a concrete AuthProvider using JWT bearer tokens."""

    @staticmethod
    def _make_fake_jwt(sub: str) -> str:
        """Build a minimal fake JWT with ``sub`` claim for testing."""
        import base64
        import json
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": sub}).encode()
        ).rstrip(b"=").decode()
        return f"header.{payload}.signature"

    def test_importable(self):
        mod = _import_auth()
        assert hasattr(mod, "OpenRouterPKCE"), (
            "OpenRouterPKCE must be exported from MnesOS.auth"
        )

    def test_is_auth_provider_subclass(self):
        mod = _import_auth()
        assert issubclass(mod.OpenRouterPKCE, mod.AuthProvider)

    def test_instantiates_without_arguments(self):
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        assert provider is not None

    def test_resolve_identity_extracts_user_id_from_bearer(self):
        """JWT bearer token in Authorization header should yield an AuthContext."""
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        fake_jwt = self._make_fake_jwt("user-123")
        headers = {"authorization": f"Bearer {fake_jwt}"}
        ctx = provider.resolve_identity(headers)
        assert isinstance(ctx, mod.AuthContext)
        assert ctx.user_id == "user-123"

    def test_resolve_identity_missing_authorization_raises(self):
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        with pytest.raises(Exception):
            provider.resolve_identity({})

    def test_resolve_identity_non_bearer_scheme_raises(self):
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        with pytest.raises(Exception):
            provider.resolve_identity({"authorization": "Basic dXNlcjpwYXNz"})

    def test_resolve_identity_malformed_jwt_raises(self):
        """A token that cannot be decoded should raise, not silently fail."""
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        with pytest.raises(Exception):
            provider.resolve_identity({"authorization": "Bearer not.a.valid.jwt.here"})

    def test_resolve_identity_returns_is_local_false(self):
        """OpenRouter identity is never local."""
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        headers = {"authorization": f"Bearer {self._make_fake_jwt('u99')}"}
        ctx = provider.resolve_identity(headers)
        assert ctx.is_local is False

    def test_validate_provider_keys_extracts_openrouter_key(self):
        """OpenRouterPKCE also implements LLMAuthValidator to extract the API key."""
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        if not isinstance(provider, mod.LLMAuthValidator):
            pytest.skip("OpenRouterPKCE does not implement LLMAuthValidator in this version")
        result = provider.validate_provider_keys({"x-openrouter-key": "sk-test-abc"})
        assert isinstance(result, dict)
        assert result.get("openrouter_key") == "sk-test-abc" or "sk-test-abc" in result.values()

    def test_validate_provider_keys_missing_key_raises(self):
        mod = _import_auth()
        provider = mod.OpenRouterPKCE()
        if not isinstance(provider, mod.LLMAuthValidator):
            pytest.skip("OpenRouterPKCE does not implement LLMAuthValidator in this version")
        with pytest.raises(Exception):
            provider.validate_provider_keys({})


# ---------------------------------------------------------------------------
# AuthFactory
# ---------------------------------------------------------------------------

class TestAuthFactory:
    """AuthFactory selects the correct AuthProvider based on request headers."""

    def test_importable(self):
        mod = _import_auth()
        assert hasattr(mod, "AuthFactory"), (
            "AuthFactory must be exported from MnesOS.auth"
        )

    def test_create_returns_openrouter_pkce_for_openrouter_provider(self):
        mod = _import_auth()
        provider = mod.AuthFactory.create({"x-provider": "openrouter"})
        assert isinstance(provider, mod.OpenRouterPKCE)

    def test_create_returns_local_provider_for_local_mode(self):
        mod = _import_auth()
        # "local" mode should exist and return a provider that yields is_local=True
        provider = mod.AuthFactory.create({"x-provider": "local"})
        assert isinstance(provider, mod.AuthProvider)
        ctx = provider.resolve_identity({})
        assert ctx.is_local is True

    def test_create_unknown_provider_raises(self):
        mod = _import_auth()
        with pytest.raises((ValueError, KeyError, Exception)):
            mod.AuthFactory.create({"x-provider": "nonexistent-provider-xyz"})

    def test_create_missing_provider_header_uses_default(self):
        """If the X-Provider header is absent, a sensible default must be returned."""
        mod = _import_auth()
        # Should not raise; a default provider (e.g., OpenRouterPKCE) is used
        provider = mod.AuthFactory.create({})
        assert isinstance(provider, mod.AuthProvider)

    def test_factory_is_not_instantiated(self):
        """AuthFactory is a utility with static/class methods, not a mutable instance."""
        mod = _import_auth()
        # create() should be accessible without instantiating AuthFactory
        assert callable(getattr(mod.AuthFactory, "create", None)), (
            "AuthFactory.create must be a classmethod or staticmethod"
        )

    def test_provider_header_is_case_insensitive(self):
        """Headers are conventionally case-insensitive; the factory must handle this."""
        mod = _import_auth()
        # Both "openrouter" and "OpenRouter" should map to OpenRouterPKCE
        p1 = mod.AuthFactory.create({"x-provider": "openrouter"})
        p2 = mod.AuthFactory.create({"x-provider": "OpenRouter"})
        assert type(p1) == type(p2)


# ---------------------------------------------------------------------------
# Integration: AuthProvider + LLMAuthValidator contract together
# ---------------------------------------------------------------------------

class TestAuthIntegration:
    """Verify both ABCs can be implemented together in a single class."""

    def test_dual_implementation_is_possible(self):
        mod = _import_auth()

        class DualProvider(mod.AuthProvider, mod.LLMAuthValidator):
            def resolve_identity(self, headers: dict):
                return mod.AuthContext(user_id=headers.get("x-user-id", "anon"))

            def validate_provider_keys(self, headers: dict) -> dict:
                key = headers.get("x-api-key", "")
                return {"key": key}

        provider = DualProvider()
        ctx = provider.resolve_identity({"x-user-id": "u5"})
        keys = provider.validate_provider_keys({"x-api-key": "sk-xyz"})
        assert ctx.user_id == "u5"
        assert keys["key"] == "sk-xyz"

    def test_auth_context_user_id_non_empty_string(self):
        mod = _import_auth()
        with pytest.raises(Exception):
            mod.AuthContext(user_id="")  # Empty string must be rejected
