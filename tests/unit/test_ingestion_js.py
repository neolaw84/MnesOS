"""
Unit tests for JS-to-YAML compilation in the ingestion pipeline.

TDD: Tests verify that the cartridge ingestion pipeline accepts yare.js,
compiles it to YAML, and stores both representations.
"""

import pytest
import tempfile
from pathlib import Path

from MnesOS.cartridge import CartridgeLoader


class TestCartridgeLoaderJSSupport:
    """Test CartridgeLoader handles yare.js files."""

    def _write_cartridge_dir(self, tmp_path, yare_content, ext="yaml", lore="Test lore.", first_msg="Hello"):
        """Helper to write a cartridge directory."""
        d = tmp_path / "cart"
        d.mkdir()
        if ext == "yaml":
            (d / "yare.yaml").write_text(yare_content)
        else:
            (d / "yare.js").write_text(yare_content)
        (d / "bot_lore.md").write_text(lore)
        (d / "first-message.md").write_text(first_msg)
        return str(d)

    def test_load_js_cartridge(self, tmp_path):
        """CartridgeLoader loads yare.js and compiles it."""
        js_src = """
export const version = "1.0";
export const state_schema = {
    player: {
        hp: { type: "int", default: 100, min: 0, max: 100 }
    }
};
export const events = {
    heal: {
        description: "Heal the player",
        inputs: { amount: { type: "int", default: 10 } },
        steps: [
            { action: "mutate", var: "state.player.hp", op: "add", value: "@ inputs.amount" }
        ]
    }
};
"""
        cart_dir = self._write_cartridge_dir(tmp_path, js_src, ext="js")
        loaded = CartridgeLoader().load(cart_dir)
        assert loaded.yare_config["version"] == "1.0"
        assert "heal" in loaded.yare_config["events"]
        assert loaded.yare_js_src == js_src

    def test_load_js_cartridge_invalid_syntax(self, tmp_path):
        """CartridgeLoader rejects JS with syntax errors."""
        js_src = """
export const version = "1.0";
export const state_schema = {{{BROKEN;
"""
        cart_dir = self._write_cartridge_dir(tmp_path, js_src, ext="js")
        with pytest.raises(ValueError, match="[Cc]ompil"):
            CartridgeLoader().load(cart_dir)

    def test_load_js_cartridge_unsupported_syntax(self, tmp_path):
        """CartridgeLoader rejects JS with unsupported dynamic constructs."""
        js_src = """
export const version = "1.0";
export const state_schema = fetchFromServer();
export const events = {};
"""
        cart_dir = self._write_cartridge_dir(tmp_path, js_src, ext="js")
        with pytest.raises(ValueError, match="[Cc]ompil"):
            CartridgeLoader().load(cart_dir)

    def test_load_prefers_yaml_over_js(self, tmp_path):
        """When both yare.yaml and yare.js exist, yaml takes precedence."""
        d = tmp_path / "cart"
        d.mkdir()
        (d / "yare.yaml").write_text('version: "1.0"\nstate_schema: {}\nevents: {}')
        (d / "yare.js").write_text('export const version = "1.0"; export const state_schema = {}; export const events = {};')
        (d / "bot_lore.md").write_text("lore")
        (d / "first-message.md").write_text("hi")

        loaded = CartridgeLoader().load(str(d))
        # YAML takes precedence, so yare_js_src should be None
        assert loaded.yare_js_src is None

    def test_loaded_cartridge_has_js_src_attribute(self, tmp_path):
        """LoadedCartridge dataclass has yare_js_src field."""
        from MnesOS.cartridge import LoadedCartridge
        lc = LoadedCartridge(
            yare_config={},
            prompt_directives={},
            lore_path="",
            lore_content="",
        )
        assert hasattr(lc, "yare_js_src")
        assert lc.yare_js_src is None
