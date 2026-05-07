"""
Unit tests for MnesOS.llm — contract tests for the LLM Provider Factory.

Covers: LLMProvider (ABC), LLMFactory (registry & factory methods).

Aligned with ``docs/design/0006-stateless-phase-2.md`` §3 (LLM Provider
Factory / [MnesOS-260507-05]).

All tests express the *required behaviour* of the module.  They will fail until
``src/MnesOS/llm.py`` is implemented and the concrete classes are added.
"""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers – import the module under test (will fail if not yet implemented)
# ---------------------------------------------------------------------------

def _import_llm():
    """Return the llm module, skipping tests gracefully if not yet implemented."""
    try:
        import MnesOS.llm as llm_module
        return llm_module
    except ImportError:
        pytest.fail(
            "MnesOS.llm module is not implemented yet. "
            "Implement src/MnesOS/llm.py to satisfy MnesOS-260507-05."
        )


def _make_role_config(provider="openrouter", model_name="test-model", temperature=0.7):
    """Construct an LLMRoleConfig using the already-implemented config module."""
    from MnesOS.config import LLMRoleConfig
    return LLMRoleConfig(provider=provider, model_name=model_name, temperature=temperature)


# ---------------------------------------------------------------------------
# LLMProvider (ABC)
# ---------------------------------------------------------------------------

class TestLLMProviderABC:
    """LLMProvider must be an abstract base class with two abstract methods."""

    def test_importable(self):
        mod = _import_llm()
        assert hasattr(mod, "LLMProvider"), "LLMProvider must be exported from MnesOS.llm"

    def test_is_abstract_cannot_instantiate_directly(self):
        mod = _import_llm()
        with pytest.raises(TypeError):
            mod.LLMProvider()  # type: ignore[abstract]

    def test_subclass_missing_get_chat_model_is_abstract(self):
        mod = _import_llm()

        class Partial(mod.LLMProvider):
            def get_embeddings_model(self, config, keys):
                return MagicMock()

        with pytest.raises(TypeError):
            Partial()

    def test_subclass_missing_get_embeddings_model_is_abstract(self):
        mod = _import_llm()

        class Partial(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

        with pytest.raises(TypeError):
            Partial()

    def test_concrete_subclass_instantiates(self):
        mod = _import_llm()

        class Concrete(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        provider = Concrete()
        assert provider is not None

    def test_get_chat_model_receives_config_and_keys(self):
        mod = _import_llm()
        received = {}

        class Spy(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                received["config"] = config
                received["keys"] = keys
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        spy = Spy()
        role_cfg = _make_role_config(provider="openrouter", model_name="flash")
        keys = {"openrouter_key": "sk-abc"}
        spy.get_chat_model(role_cfg, keys)
        assert received["config"] == role_cfg
        assert received["keys"] == keys

    def test_get_embeddings_model_receives_config_and_keys(self):
        mod = _import_llm()
        received = {}

        class Spy(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                received["config"] = config
                received["keys"] = keys
                return MagicMock()

        spy = Spy()
        role_cfg = _make_role_config(provider="openrouter", model_name="embed-v3")
        keys = {"openrouter_key": "sk-xyz"}
        spy.get_embeddings_model(role_cfg, keys)
        assert received["config"] == role_cfg
        assert received["keys"] == keys


# ---------------------------------------------------------------------------
# LLMFactory — Registry
# ---------------------------------------------------------------------------

class TestLLMFactoryRegistry:
    """LLMFactory must maintain a registry of named providers."""

    def test_importable(self):
        mod = _import_llm()
        assert hasattr(mod, "LLMFactory"), "LLMFactory must be exported from MnesOS.llm"

    def test_instantiates_with_empty_registry(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        assert factory is not None

    def test_register_provider_stores_provider(self):
        mod = _import_llm()

        class FakeProvider(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        factory = mod.LLMFactory()
        fp = FakeProvider()
        factory.register_provider("fake", fp)
        # Should be retrievable afterwards
        assert factory._providers.get("fake") is fp

    def test_register_multiple_providers(self):
        mod = _import_llm()

        class Provider1(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        class Provider2(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        factory = mod.LLMFactory()
        factory.register_provider("p1", Provider1())
        factory.register_provider("p2", Provider2())
        assert "p1" in factory._providers
        assert "p2" in factory._providers

    def test_register_overwrites_existing_provider(self):
        mod = _import_llm()

        class Prov(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        factory = mod.LLMFactory()
        p1 = Prov()
        p2 = Prov()
        factory.register_provider("same", p1)
        factory.register_provider("same", p2)
        assert factory._providers["same"] is p2

    def test_separate_factory_instances_have_independent_registries(self):
        mod = _import_llm()

        class FakeProv(mod.LLMProvider):
            def get_chat_model(self, config, keys):
                return MagicMock()

            def get_embeddings_model(self, config, keys):
                return MagicMock()

        f1 = mod.LLMFactory()
        f2 = mod.LLMFactory()
        f1.register_provider("only-in-f1", FakeProv())
        assert "only-in-f1" not in f2._providers


# ---------------------------------------------------------------------------
# LLMFactory — create_chat_client
# ---------------------------------------------------------------------------

class TestLLMFactoryCreateChatClient:
    """create_chat_client dispatches to the registered provider."""

    def _factory_with_mock(self, provider_name="openrouter"):
        mod = _import_llm()
        mock_model = MagicMock()
        mock_provider = MagicMock(spec=mod.LLMProvider)
        mock_provider.get_chat_model.return_value = mock_model
        factory = mod.LLMFactory()
        factory.register_provider(provider_name, mock_provider)
        return factory, mock_provider, mock_model

    def test_returns_model_from_provider(self):
        factory, mock_provider, mock_model = self._factory_with_mock("openrouter")
        cfg = _make_role_config(provider="openrouter", model_name="flash")
        result = factory.create_chat_client(cfg, {"openrouter_key": "sk-test"})
        assert result is mock_model

    def test_passes_config_to_provider(self):
        factory, mock_provider, _ = self._factory_with_mock("openrouter")
        cfg = _make_role_config(provider="openrouter", model_name="gpt-4")
        keys = {"openrouter_key": "sk-x"}
        factory.create_chat_client(cfg, keys)
        mock_provider.get_chat_model.assert_called_once_with(cfg, keys)

    def test_passes_keys_to_provider(self):
        factory, mock_provider, _ = self._factory_with_mock("openrouter")
        cfg = _make_role_config(provider="openrouter")
        keys = {"openrouter_key": "sk-secret"}
        factory.create_chat_client(cfg, keys)
        _, call_keys = mock_provider.get_chat_model.call_args[0]
        assert call_keys == keys

    def test_unknown_provider_raises_value_error(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        cfg = _make_role_config(provider="ghost")
        with pytest.raises(ValueError, match="ghost"):
            factory.create_chat_client(cfg, {})

    def test_empty_registry_raises_for_any_provider(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        cfg = _make_role_config(provider="openrouter")
        with pytest.raises(ValueError):
            factory.create_chat_client(cfg, {})

    def test_dispatches_to_correct_provider_when_multiple_registered(self):
        mod = _import_llm()
        model_a = MagicMock(name="model_a")
        model_b = MagicMock(name="model_b")

        prov_a = MagicMock(spec=mod.LLMProvider)
        prov_a.get_chat_model.return_value = model_a
        prov_b = MagicMock(spec=mod.LLMProvider)
        prov_b.get_chat_model.return_value = model_b

        factory = mod.LLMFactory()
        factory.register_provider("a", prov_a)
        factory.register_provider("b", prov_b)

        result = factory.create_chat_client(_make_role_config(provider="b"), {})
        assert result is model_b
        prov_a.get_chat_model.assert_not_called()

    def test_called_multiple_times_each_invokes_provider(self):
        mod = _import_llm()
        mock_provider = MagicMock(spec=mod.LLMProvider)
        mock_provider.get_chat_model.return_value = MagicMock()
        factory = mod.LLMFactory()
        factory.register_provider("openrouter", mock_provider)
        cfg = _make_role_config(provider="openrouter")
        factory.create_chat_client(cfg, {})
        factory.create_chat_client(cfg, {})
        assert mock_provider.get_chat_model.call_count == 2


# ---------------------------------------------------------------------------
# LLMFactory — create_embeddings_client
# ---------------------------------------------------------------------------

class TestLLMFactoryCreateEmbeddingsClient:
    """create_embeddings_client dispatches to the registered provider."""

    def _factory_with_mock(self, provider_name="openrouter"):
        mod = _import_llm()
        mock_embed = MagicMock()
        mock_provider = MagicMock(spec=mod.LLMProvider)
        mock_provider.get_embeddings_model.return_value = mock_embed
        factory = mod.LLMFactory()
        factory.register_provider(provider_name, mock_provider)
        return factory, mock_provider, mock_embed

    def test_returns_embeddings_model_from_provider(self):
        factory, _, mock_embed = self._factory_with_mock("openrouter")
        cfg = _make_role_config(provider="openrouter", model_name="embed-v3")
        result = factory.create_embeddings_client(cfg, {"openrouter_key": "sk-e"})
        assert result is mock_embed

    def test_passes_config_to_provider(self):
        factory, mock_provider, _ = self._factory_with_mock("openrouter")
        cfg = _make_role_config(provider="openrouter", model_name="embed-large")
        keys = {"openrouter_key": "sk-y"}
        factory.create_embeddings_client(cfg, keys)
        mock_provider.get_embeddings_model.assert_called_once_with(cfg, keys)

    def test_unknown_provider_raises_value_error(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        cfg = _make_role_config(provider="phantom")
        with pytest.raises(ValueError, match="phantom"):
            factory.create_embeddings_client(cfg, {})

    def test_empty_registry_raises(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        cfg = _make_role_config(provider="gemini")
        with pytest.raises(ValueError):
            factory.create_embeddings_client(cfg, {})

    def test_dispatches_to_correct_provider_when_multiple_registered(self):
        mod = _import_llm()
        embed_a = MagicMock(name="embed_a")
        embed_b = MagicMock(name="embed_b")

        prov_a = MagicMock(spec=mod.LLMProvider)
        prov_a.get_embeddings_model.return_value = embed_a
        prov_b = MagicMock(spec=mod.LLMProvider)
        prov_b.get_embeddings_model.return_value = embed_b

        factory = mod.LLMFactory()
        factory.register_provider("a", prov_a)
        factory.register_provider("b", prov_b)

        result = factory.create_embeddings_client(_make_role_config(provider="a"), {})
        assert result is embed_a
        prov_b.get_embeddings_model.assert_not_called()

    def test_chat_and_embeddings_are_independent(self):
        """Registering a provider supplies both chat and embeddings independently."""
        mod = _import_llm()
        mock_chat = MagicMock(name="chat_model")
        mock_embed = MagicMock(name="embed_model")
        mock_provider = MagicMock(spec=mod.LLMProvider)
        mock_provider.get_chat_model.return_value = mock_chat
        mock_provider.get_embeddings_model.return_value = mock_embed

        factory = mod.LLMFactory()
        factory.register_provider("openrouter", mock_provider)
        cfg = _make_role_config(provider="openrouter")

        chat = factory.create_chat_client(cfg, {})
        embed = factory.create_embeddings_client(cfg, {})
        assert chat is mock_chat
        assert embed is mock_embed
        assert chat is not embed


# ---------------------------------------------------------------------------
# LLMFactory — error message quality
# ---------------------------------------------------------------------------

class TestLLMFactoryErrorMessages:
    def test_error_message_contains_provider_name_for_chat(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        cfg = _make_role_config(provider="my-special-provider")
        with pytest.raises(ValueError) as exc_info:
            factory.create_chat_client(cfg, {})
        assert "my-special-provider" in str(exc_info.value)

    def test_error_message_contains_provider_name_for_embeddings(self):
        mod = _import_llm()
        factory = mod.LLMFactory()
        cfg = _make_role_config(provider="another-unknown-provider")
        with pytest.raises(ValueError) as exc_info:
            factory.create_embeddings_client(cfg, {})
        assert "another-unknown-provider" in str(exc_info.value)
