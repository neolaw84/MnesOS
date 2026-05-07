"""
Unit tests for MnesOS.config — LLMRoleConfig, MnesOSRuntimeConfig, ConfigMerger.
"""

import pytest
from MnesOS.config import ConfigMerger, LLMRoleConfig, MnesOSRuntimeConfig, _deep_update


# ---------------------------------------------------------------------------
# _deep_update helper
# ---------------------------------------------------------------------------

class TestDeepUpdate:
    def test_simple_override(self):
        result = _deep_update({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_dict_merged_not_replaced(self):
        base = {"role": {"provider": "openrouter", "temperature": 0.7}}
        override = {"role": {"temperature": 0.9}}
        result = _deep_update(base, override)
        assert result["role"]["provider"] == "openrouter"
        assert result["role"]["temperature"] == 0.9

    def test_non_dict_value_replaces_nested(self):
        base = {"role": {"nested": {"x": 1}}}
        override = {"role": "flat_value"}
        result = _deep_update(base, override)
        assert result["role"] == "flat_value"

    def test_does_not_mutate_inputs(self):
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        _deep_update(base, override)
        assert "y" not in base["a"]


# ---------------------------------------------------------------------------
# LLMRoleConfig schema
# ---------------------------------------------------------------------------

class TestLLMRoleConfig:
    def test_defaults(self):
        cfg = LLMRoleConfig()
        assert cfg.provider == "openrouter"
        assert cfg.model_name == ""
        assert cfg.temperature == 0.7
        assert cfg.max_tokens is None

    def test_explicit_values(self):
        cfg = LLMRoleConfig(
            provider="gemini",
            model_name="google/gemini-2.5-flash",
            temperature=0.5,
            max_tokens=1024,
        )
        assert cfg.provider == "gemini"
        assert cfg.model_name == "google/gemini-2.5-flash"
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 1024

    def test_model_dump_roundtrip(self):
        cfg = LLMRoleConfig(provider="local", model_name="llama3", temperature=0.3)
        dumped = cfg.model_dump()
        restored = LLMRoleConfig(**dumped)
        assert restored == cfg


# ---------------------------------------------------------------------------
# MnesOSRuntimeConfig schema
# ---------------------------------------------------------------------------

class TestMnesOSRuntimeConfig:
    def test_defaults(self):
        cfg = MnesOSRuntimeConfig()
        for role_attr in ("director_llm", "narrator_llm", "npc_llm", "embedding_llm"):
            role_cfg = getattr(cfg, role_attr)
            assert isinstance(role_cfg, LLMRoleConfig)
            assert role_cfg.provider == "openrouter"
        assert cfg.yare_config == {}
        assert cfg.prompt_directives == {}

    def test_explicit_roles(self):
        role = LLMRoleConfig(provider="gemini", model_name="flash")
        cfg = MnesOSRuntimeConfig(director_llm=role, yare_config={"state_schema": {}})
        assert cfg.director_llm.provider == "gemini"
        assert cfg.yare_config == {"state_schema": {}}


# ---------------------------------------------------------------------------
# ConfigMerger.merge
# ---------------------------------------------------------------------------

class TestConfigMerger:
    def test_cartridge_defaults_only(self):
        cartridge = {
            "yare_config": {"state_schema": {"hp": {"type": "int"}}},
            "prompt_directives": {"director": "Be concise."},
        }
        cfg = ConfigMerger.merge(cartridge, {}, {})
        assert cfg.yare_config == cartridge["yare_config"]
        assert cfg.prompt_directives == {"director": "Be concise."}
        # LLM roles fall back to system defaults
        assert cfg.director_llm.provider == "openrouter"

    def test_player_settings_override_cartridge(self):
        cartridge = {"director_llm": {"provider": "openrouter", "model_name": "base"}}
        player = {"director_llm": {"model_name": "player_model"}}
        cfg = ConfigMerger.merge(cartridge, player, {})
        assert cfg.director_llm.provider == "openrouter"
        assert cfg.director_llm.model_name == "player_model"

    def test_request_overrides_are_highest_precedence(self):
        cartridge = {"director_llm": {"provider": "openrouter", "temperature": 0.5}}
        player = {"director_llm": {"temperature": 0.6}}
        request = {"director_llm": {"temperature": 0.9}}
        cfg = ConfigMerger.merge(cartridge, player, request)
        assert cfg.director_llm.temperature == 0.9

    def test_partial_override_preserves_other_fields(self):
        cartridge = {
            "director_llm": {"provider": "gemini", "model_name": "flash", "temperature": 0.7}
        }
        request = {"director_llm": {"temperature": 0.2}}
        cfg = ConfigMerger.merge(cartridge, {}, request)
        assert cfg.director_llm.provider == "gemini"
        assert cfg.director_llm.model_name == "flash"
        assert cfg.director_llm.temperature == 0.2

    def test_prompt_directives_merged(self):
        cartridge = {"prompt_directives": {"director": "default director"}}
        player = {"prompt_directives": {"narrator": "vivid narrator"}}
        cfg = ConfigMerger.merge(cartridge, player, {})
        assert cfg.prompt_directives["director"] == "default director"
        assert cfg.prompt_directives["narrator"] == "vivid narrator"

    def test_all_four_llm_roles_produced(self):
        cfg = ConfigMerger.merge({}, {}, {})
        for role in ("director_llm", "narrator_llm", "npc_llm", "embedding_llm"):
            assert isinstance(getattr(cfg, role), LLMRoleConfig)

    def test_empty_layers_give_defaults(self):
        cfg = ConfigMerger.merge({}, {}, {})
        assert isinstance(cfg, MnesOSRuntimeConfig)
        assert cfg.yare_config == {}
        assert cfg.prompt_directives == {}

    def test_max_tokens_override(self):
        cartridge = {"narrator_llm": {"provider": "openrouter", "model_name": "m"}}
        request = {"narrator_llm": {"max_tokens": 512}}
        cfg = ConfigMerger.merge(cartridge, {}, request)
        assert cfg.narrator_llm.max_tokens == 512
        assert cfg.narrator_llm.model_name == "m"


# ---------------------------------------------------------------------------
# Orchestrator._build_runnable_config integration
# ---------------------------------------------------------------------------

class TestOrchestratorBuildRunnableConfig:
    """Verify that the Orchestrator maps MnesOSRuntimeConfig into configurable."""

    def _make_orchestrator(self):
        from unittest.mock import MagicMock, patch
        with patch("MnesOS.orchestrator.build_graph") as mock_bg:
            mock_bg.return_value = MagicMock()
            from MnesOS.orchestrator import Orchestrator
            orch = Orchestrator(storage=MagicMock(), cartridge_dir="cartridges/generic-rpg")
        return orch

    def test_runnable_config_includes_llm_role_keys(self):
        orch = self._make_orchestrator()
        runtime = MnesOSRuntimeConfig(
            director_llm=LLMRoleConfig(provider="gemini", model_name="flash"),
        )
        result = orch._build_runnable_config(runtime_config=runtime)
        configurable = result["configurable"]
        for key in ("director_llm", "narrator_llm", "npc_llm", "embedding_llm"):
            assert key in configurable, f"Missing key: {key}"

    def test_runnable_config_uses_merged_yare_and_directives(self):
        orch = self._make_orchestrator()
        runtime = MnesOSRuntimeConfig(
            yare_config={"overridden": True},
            prompt_directives={"director": "custom"},
        )
        result = orch._build_runnable_config(runtime_config=runtime)
        configurable = result["configurable"]
        assert configurable["yare_config"] == {"overridden": True}
        assert configurable["prompt_directives"] == {"director": "custom"}

    def test_runnable_config_preserves_lore_fields(self):
        orch = self._make_orchestrator()
        result = orch._build_runnable_config(runtime_config=MnesOSRuntimeConfig())
        configurable = result["configurable"]
        assert "lore_path" in configurable
        assert "lore_content" in configurable
        assert "persona_context" in configurable

    def test_runnable_config_without_runtime_config_uses_cartridge(self):
        orch = self._make_orchestrator()
        result = orch._build_runnable_config()
        configurable = result["configurable"]
        assert "yare_config" in configurable
        assert "prompt_directives" in configurable
        for key in ("director_llm", "narrator_llm", "npc_llm", "embedding_llm"):
            assert key not in configurable

    def test_process_turn_passes_runtime_config(self):
        from unittest.mock import MagicMock, patch
        from MnesOS.storage.models import TurnLog, TurnActor

        with patch("MnesOS.orchestrator.build_graph") as mock_bg, \
             patch("MnesOS.orchestrator.CartridgeLoader.load") as mock_load, \
             patch("MnesOS.orchestrator.StateHydrator.hydrate_state") as mock_hydrate:

            mock_load.return_value = MagicMock(
                initial_state={}, yare_config={},
                prompt_directives={}, lore_path=None,
                lore_content=None, persona_context="",
                first_message="",
            )
            mock_hydrate.return_value = {"client_messages": [], "bot_memory": {}}

            mock_app = MagicMock()
            mock_app.invoke.return_value = {
                "client_messages": [{"role": "assistant", "content": "ok"}],
                "bot_memory": {},
            }
            mock_bg.return_value = mock_app

            from MnesOS.orchestrator import Orchestrator
            mock_storage = MagicMock()
            mock_storage.get_turn_lineage.return_value = []
            orch = Orchestrator(storage=mock_storage, cartridge_dir="cartridges/generic-rpg")

            orch.process_turn(
                "hello",
                player_settings={"director_llm": {"provider": "gemini"}},
                request_overrides={"director_llm": {"temperature": 0.1}},
            )

            # Verify invoke was called and configurable has LLM role keys
            call_args = mock_app.invoke.call_args
            config = call_args[1]["config"] if "config" in call_args[1] else call_args[0][1]
            configurable = config["configurable"]
            assert configurable["director_llm"]["provider"] == "gemini"
            assert configurable["director_llm"]["temperature"] == 0.1
