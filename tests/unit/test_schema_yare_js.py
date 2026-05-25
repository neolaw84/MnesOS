"""
Unit tests for CartridgeVersion schema update to support yare_js_src.

TDD: Tests written FIRST — verifies that CartridgeVersion model,
storage layer, and API schemas correctly handle the new yare_js_src field.
"""

import pytest

from MnesOS.storage.models import CartridgeVersion


class TestCartridgeVersionModel:
    """Test CartridgeVersion dataclass includes yare_js_src."""

    def test_yare_js_src_field_exists(self):
        """CartridgeVersion has yare_js_src attribute (nullable)."""
        cv = CartridgeVersion(
            cartridge_id="c1",
            version_tag="1.0.0",
            yare_spec={"version": "1.0"},
            prompt_directives={},
            bot_lore="lore",
            first_message="hello",
            checksum="abc123",
        )
        assert cv.yare_js_src is None

    def test_yare_js_src_set(self):
        """CartridgeVersion can store JS source."""
        js_src = 'export const version = "1.0";'
        cv = CartridgeVersion(
            cartridge_id="c1",
            version_tag="1.0.0",
            yare_spec={"version": "1.0"},
            prompt_directives={},
            bot_lore="lore",
            first_message="hello",
            checksum="abc123",
            yare_js_src=js_src,
        )
        assert cv.yare_js_src == js_src


class TestSQLiteStoreYareJsSrc:
    """Test SQLite store persists and retrieves yare_js_src."""

    @pytest.fixture
    def store(self, tmp_path):
        from MnesOS.storage.sqlite3_store import SQLite3PhysicalComponent
        db_path = str(tmp_path / "test.db")
        store = SQLite3PhysicalComponent(db_path)
        store.initialize()
        return store

    @pytest.fixture
    def sample_user(self, store):
        from MnesOS.storage.models import UserAccount, UserRole
        user = store.create_user(UserAccount(
            username="testdev",
            email="dev@test.com",
            password_hash="hash",
            role=UserRole.CREATOR,
        ))
        return user

    @pytest.fixture
    def sample_cartridge(self, store, sample_user):
        from MnesOS.storage.models import Cartridge, Visibility
        cart = store.create_cartridge(Cartridge(
            creator_id=sample_user.id,
            title="Test Cart",
            description="",
            genre="RPG",
            visibility=Visibility.PUBLIC,
        ))
        return cart

    def test_create_version_with_js_src(self, store, sample_cartridge):
        """Creating a version with yare_js_src persists it."""
        js_src = 'export const version = "1.0"; export const events = {};'
        version = store.create_cartridge_version(CartridgeVersion(
            cartridge_id=sample_cartridge.id,
            version_tag="1.0.0",
            yare_spec={"version": "1.0", "events": {}},
            prompt_directives={},
            bot_lore="lore text",
            first_message="hello world",
            checksum="deadbeef",
            yare_js_src=js_src,
        ))
        assert version.id is not None

        # Retrieve and verify
        fetched = store.get_cartridge_version(version.id)
        assert fetched is not None
        assert fetched.yare_js_src == js_src

    def test_create_version_without_js_src(self, store, sample_cartridge):
        """Creating a version without yare_js_src stores None."""
        version = store.create_cartridge_version(CartridgeVersion(
            cartridge_id=sample_cartridge.id,
            version_tag="1.0.0",
            yare_spec={"version": "1.0"},
            prompt_directives={},
            bot_lore="lore text",
            first_message="hello",
            checksum="deadbeef",
        ))
        fetched = store.get_cartridge_version(version.id)
        assert fetched.yare_js_src is None

    def test_version_response_includes_js_src(self, store, sample_cartridge):
        """API response schema includes yare_js_src."""
        from MnesOS.api.schemas import CartridgeVersionResponse
        # Verify the schema field exists
        fields = CartridgeVersionResponse.model_fields
        assert "yare_js_src" in fields
