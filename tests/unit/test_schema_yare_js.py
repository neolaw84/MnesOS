"""
Unit tests for CartridgeVersion schema — yare_type and yare_spec_raw fields.

Verifies that CartridgeVersion model, storage layer, and API schemas correctly
handle yare source tracking (replaces the former yare_js_src field).
"""

import pytest

from MnesOS.storage.models import CartridgeVersion


class TestCartridgeVersionModel:
    """Test CartridgeVersion dataclass includes yare_type and yare_spec_raw."""

    def test_yare_spec_raw_field_exists(self):
        """CartridgeVersion has yare_spec_raw attribute (nullable) and yare_type defaults to 'yaml'."""
        cv = CartridgeVersion(
            cartridge_id="c1",
            version_tag="1.0.0",
            yare_spec={"version": "1.0"},
            prompt_directives={},
            bot_lore="lore",
            first_message="hello",
            checksum="abc123",
        )
        assert cv.yare_spec_raw is None
        assert cv.yare_type == "yaml"

    def test_yare_spec_raw_set(self):
        """CartridgeVersion can store JS source in yare_spec_raw with yare_type='js'."""
        js_src = 'export const version = "1.0";'
        cv = CartridgeVersion(
            cartridge_id="c1",
            version_tag="1.0.0",
            yare_spec={"version": "1.0"},
            prompt_directives={},
            bot_lore="lore",
            first_message="hello",
            checksum="abc123",
            yare_type="js",
            yare_spec_raw=js_src,
        )
        assert cv.yare_spec_raw == js_src
        assert cv.yare_type == "js"


class TestSQLiteStoreYareJsSrc:
    """Test SQLite store persists and retrieves yare_type and yare_spec_raw."""

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
        """Creating a JS version persists yare_type='js' and yare_spec_raw."""
        js_src = 'export const version = "1.0"; export const events = {};'
        version = store.create_cartridge_version(CartridgeVersion(
            cartridge_id=sample_cartridge.id,
            version_tag="1.0.0",
            yare_spec={"version": "1.0", "events": {}},
            prompt_directives={},
            bot_lore="lore text",
            first_message="hello world",
            checksum="deadbeef",
            yare_type="js",
            yare_spec_raw=js_src,
        ))
        assert version.id is not None

        # Retrieve and verify
        fetched = store.get_cartridge_version(version.id)
        assert fetched is not None
        assert fetched.yare_spec_raw == js_src
        assert fetched.yare_type == "js"

    def test_create_version_without_js_src(self, store, sample_cartridge):
        """Creating a YAML version stores yare_type='yaml' and yare_spec_raw=None."""
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
        assert fetched.yare_spec_raw is None
        assert fetched.yare_type == "yaml"

    def test_version_response_includes_js_src(self, store, sample_cartridge):
        """API response schema includes yare_type and yare_spec_raw."""
        from MnesOS.api.schemas import CartridgeVersionResponse
        # Verify the schema fields exist
        fields = CartridgeVersionResponse.model_fields
        assert "yare_type" in fields
        assert "yare_spec_raw" in fields

