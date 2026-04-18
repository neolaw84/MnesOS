"""
Unit tests for the MnesOS storage persistence layer.

TDD: these tests are written BEFORE the implementation to define the contract.

Test coverage:
  AC0 — GameInstance context retrieval (Persona + CartridgeVersion) via SQLite
  AC1 — AbstractStorageComponent defines the expected interface
  AC2 — SQLite3PhysicalComponent concretely satisfies the interface
  AC3 — TurnLog insertions are atomic appends (write-optimized)
  AC4 — Migration creates tables and indexes (via in-memory DB)
  AC5 — delete_db utility removes the database file
"""

import importlib
import inspect
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

from MnesOS.storage.models import (
    UserAccount,
    UserRole,
    Persona,
    Cartridge,
    CartridgeVersion,
    GameInstance,
    GameStatus,
    TurnLog,
    TurnActor,
    Visibility,
)
from MnesOS.storage.interface import AbstractStorageComponent
from MnesOS.storage.sqlite3_store import SQLite3PhysicalComponent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    """Return a SQLite3PhysicalComponent backed by an in-memory database."""
    s = SQLite3PhysicalComponent(":memory:")
    s.initialize()
    return s


@pytest.fixture
def sample_user(store):
    """Persist and return a sample UserAccount."""
    user = UserAccount(
        username="aragorn",
        email="aragorn@gondor.me",
        password_hash="$2b$12$hashed",
        role=UserRole.PLAYER,
    )
    return store.create_user(user)


@pytest.fixture
def sample_creator(store):
    """Persist and return a creator UserAccount."""
    creator = UserAccount(
        username="tolkien",
        email="tolkien@shire.me",
        password_hash="$2b$12$hashed_creator",
        role=UserRole.CREATOR,
    )
    return store.create_user(creator)


@pytest.fixture
def sample_persona(store, sample_user):
    """Persist and return a Persona linked to sample_user."""
    persona = Persona(
        user_id=sample_user.id,
        name="Strider",
        lore="A ranger from the North.",
        pronoun_sub="he",
        pronoun_obj="him",
        pronoun_poss="his",
        pronoun_poss_obj="his",
    )
    return store.create_persona(persona)


@pytest.fixture
def sample_cartridge(store, sample_creator):
    """Persist and return a Cartridge."""
    cartridge = Cartridge(
        creator_id=sample_creator.id,
        title="The Fellowship",
        description="An epic quest to destroy the One Ring.",
        genre="High Fantasy",
        visibility=Visibility.PUBLIC,
    )
    return store.create_cartridge(cartridge)


@pytest.fixture
def sample_version(store, sample_cartridge):
    """Persist and return a CartridgeVersion."""
    version = CartridgeVersion(
        cartridge_id=sample_cartridge.id,
        version_tag="v1.0.0",
        yare_spec={"state_schema": {"player": {"hp": {"type": "int", "default": 100}}}},
        prompt_directives={"narrator": "Speak in a grand epic tone."},
        bot_lore="The world of Middle Earth...",
        checksum="abc123",
    )
    return store.create_cartridge_version(version)


@pytest.fixture
def sample_instance(store, sample_user, sample_persona, sample_version):
    """Persist and return a GameInstance."""
    instance = GameInstance(
        user_id=sample_user.id,
        persona_id=sample_persona.id,
        version_id=sample_version.id,
        status=GameStatus.ACTIVE,
    )
    return store.create_game_instance(instance)


# ---------------------------------------------------------------------------
# AC1 — AbstractStorageComponent defines the expected interface
# ---------------------------------------------------------------------------


class TestAbstractStorageInterface:
    def test_is_abstract(self):
        """AbstractStorageComponent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractStorageComponent()

    def test_has_user_crud_methods(self):
        methods = {
            "create_user",
            "get_user",
            "update_user",
            "delete_user",
        }
        for m in methods:
            assert hasattr(AbstractStorageComponent, m), f"Missing method: {m}"

    def test_has_persona_crud_methods(self):
        methods = {"create_persona", "get_persona", "update_persona", "delete_persona"}
        for m in methods:
            assert hasattr(AbstractStorageComponent, m), f"Missing method: {m}"

    def test_has_cartridge_crud_methods(self):
        methods = {
            "create_cartridge",
            "get_cartridge",
            "update_cartridge",
            "delete_cartridge",
        }
        for m in methods:
            assert hasattr(AbstractStorageComponent, m), f"Missing method: {m}"

    def test_has_cartridge_version_crud_methods(self):
        methods = {
            "create_cartridge_version",
            "get_cartridge_version",
        }
        for m in methods:
            assert hasattr(AbstractStorageComponent, m), f"Missing method: {m}"

    def test_has_game_instance_methods(self):
        methods = {
            "create_game_instance",
            "get_game_instance",
            "update_game_instance",
            "get_game_instance_context",
        }
        for m in methods:
            assert hasattr(AbstractStorageComponent, m), f"Missing method: {m}"

    def test_has_turn_log_method(self):
        assert hasattr(AbstractStorageComponent, "append_turn_log")

    def test_abstract_methods_are_abstract(self):
        abstract_methods = getattr(AbstractStorageComponent, "__abstractmethods__", set())
        required = {
            "create_user",
            "get_user",
            "create_persona",
            "get_persona",
            "create_cartridge",
            "get_cartridge",
            "create_cartridge_version",
            "get_cartridge_version",
            "create_game_instance",
            "get_game_instance",
            "get_game_instance_context",
            "append_turn_log",
        }
        for m in required:
            assert m in abstract_methods, f"{m!r} must be abstract"


# ---------------------------------------------------------------------------
# AC2 — SQLite3PhysicalComponent implements the interface
# ---------------------------------------------------------------------------


class TestSQLite3PhysicalComponentIsConcreteImplementation:
    def test_is_subclass_of_abstract(self):
        assert issubclass(SQLite3PhysicalComponent, AbstractStorageComponent)

    def test_can_be_instantiated_with_memory_db(self):
        s = SQLite3PhysicalComponent(":memory:")
        assert s is not None

    def test_initialize_creates_tables(self):
        s = SQLite3PhysicalComponent(":memory:")
        s.initialize()
        # Verify all six tables exist via the store's own connection
        table_names = s._get_table_names()
        expected = {
            "user_accounts",
            "personas",
            "cartridges",
            "cartridge_versions",
            "game_instances",
            "turn_logs",
        }
        assert expected.issubset(table_names)


# ---------------------------------------------------------------------------
# UserAccount CRUD
# ---------------------------------------------------------------------------


class TestUserAccountCRUD:
    def test_create_user_assigns_id(self, store, sample_user):
        assert sample_user.id is not None

    def test_create_user_assigns_created_at(self, store, sample_user):
        assert sample_user.created_at is not None

    def test_get_user_by_id(self, store, sample_user):
        fetched = store.get_user(sample_user.id)
        assert fetched is not None
        assert fetched.username == "aragorn"
        assert fetched.email == "aragorn@gondor.me"
        assert fetched.role == UserRole.PLAYER

    def test_get_user_returns_none_for_missing(self, store):
        assert store.get_user("nonexistent-id") is None

    def test_update_user_email(self, store, sample_user):
        sample_user.email = "king@gondor.me"
        updated = store.update_user(sample_user)
        assert updated.email == "king@gondor.me"
        fetched = store.get_user(sample_user.id)
        assert fetched.email == "king@gondor.me"

    def test_delete_user(self, store, sample_user):
        store.delete_user(sample_user.id)
        assert store.get_user(sample_user.id) is None

    def test_username_is_unique(self, store, sample_user):
        duplicate = UserAccount(
            username="aragorn",  # same username
            email="other@gondor.me",
            password_hash="$2b$12$other",
            role=UserRole.PLAYER,
        )
        with pytest.raises(Exception):
            store.create_user(duplicate)

    def test_email_is_unique(self, store, sample_user):
        duplicate = UserAccount(
            username="aragorn2",
            email="aragorn@gondor.me",  # same email
            password_hash="$2b$12$other",
            role=UserRole.PLAYER,
        )
        with pytest.raises(Exception):
            store.create_user(duplicate)


# ---------------------------------------------------------------------------
# Persona CRUD
# ---------------------------------------------------------------------------


class TestPersonaCRUD:
    def test_create_persona_assigns_id(self, store, sample_persona):
        assert sample_persona.id is not None

    def test_create_persona_assigns_created_at(self, store, sample_persona):
        assert sample_persona.created_at is not None

    def test_get_persona_by_id(self, store, sample_persona):
        fetched = store.get_persona(sample_persona.id)
        assert fetched is not None
        assert fetched.name == "Strider"
        assert fetched.pronoun_sub == "he"

    def test_get_persona_returns_none_for_missing(self, store):
        assert store.get_persona("nonexistent-id") is None

    def test_update_persona_lore(self, store, sample_persona):
        sample_persona.lore = "A ranger from the North, heir of Isildur."
        updated = store.update_persona(sample_persona)
        assert updated.lore == "A ranger from the North, heir of Isildur."

    def test_delete_persona(self, store, sample_persona):
        store.delete_persona(sample_persona.id)
        assert store.get_persona(sample_persona.id) is None


# ---------------------------------------------------------------------------
# Cartridge CRUD
# ---------------------------------------------------------------------------


class TestCartridgeCRUD:
    def test_create_cartridge_assigns_id(self, store, sample_cartridge):
        assert sample_cartridge.id is not None

    def test_get_cartridge_by_id(self, store, sample_cartridge):
        fetched = store.get_cartridge(sample_cartridge.id)
        assert fetched is not None
        assert fetched.title == "The Fellowship"
        assert fetched.visibility == Visibility.PUBLIC

    def test_get_cartridge_returns_none_for_missing(self, store):
        assert store.get_cartridge("nonexistent-id") is None

    def test_update_cartridge_visibility(self, store, sample_cartridge):
        sample_cartridge.visibility = Visibility.PRIVATE
        updated = store.update_cartridge(sample_cartridge)
        assert updated.visibility == Visibility.PRIVATE

    def test_delete_cartridge(self, store, sample_cartridge):
        store.delete_cartridge(sample_cartridge.id)
        assert store.get_cartridge(sample_cartridge.id) is None


# ---------------------------------------------------------------------------
# CartridgeVersion CRUD
# ---------------------------------------------------------------------------


class TestCartridgeVersionCRUD:
    def test_create_version_assigns_id(self, store, sample_version):
        assert sample_version.id is not None

    def test_create_version_assigns_published_at(self, store, sample_version):
        assert sample_version.published_at is not None

    def test_get_version_by_id(self, store, sample_version):
        fetched = store.get_cartridge_version(sample_version.id)
        assert fetched is not None
        assert fetched.version_tag == "v1.0.0"
        assert fetched.checksum == "abc123"

    def test_get_version_yare_spec_is_deserialized(self, store, sample_version):
        fetched = store.get_cartridge_version(sample_version.id)
        assert isinstance(fetched.yare_spec, dict)
        assert "state_schema" in fetched.yare_spec

    def test_get_version_prompt_directives_is_deserialized(self, store, sample_version):
        fetched = store.get_cartridge_version(sample_version.id)
        assert isinstance(fetched.prompt_directives, dict)
        assert fetched.prompt_directives["narrator"] == "Speak in a grand epic tone."


# ---------------------------------------------------------------------------
# GameInstance CRUD
# ---------------------------------------------------------------------------


class TestGameInstanceCRUD:
    def test_create_instance_assigns_id(self, store, sample_instance):
        assert sample_instance.id is not None

    def test_create_instance_assigns_created_at(self, store, sample_instance):
        assert sample_instance.created_at is not None

    def test_get_instance_by_id(self, store, sample_instance):
        fetched = store.get_game_instance(sample_instance.id)
        assert fetched is not None
        assert fetched.status == GameStatus.ACTIVE

    def test_update_instance_status(self, store, sample_instance):
        sample_instance.status = GameStatus.PAUSED
        updated = store.update_game_instance(sample_instance)
        assert updated.status == GameStatus.PAUSED

    def test_update_instance_last_played_at(self, store, sample_instance):
        now = datetime.now(timezone.utc)
        sample_instance.last_played_at = now
        updated = store.update_game_instance(sample_instance)
        assert updated.last_played_at is not None


# ---------------------------------------------------------------------------
# AC0 — GameInstance context retrieval (Persona + CartridgeVersion)
# ---------------------------------------------------------------------------


class TestGameInstanceContextRetrieval:
    """
    AC0: Unit tests verify that a GameInstance successfully retrieves its full
    context (Persona + CartridgeVersion) from the SQLite backend.
    """

    def test_get_context_returns_dict(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        assert isinstance(context, dict)

    def test_get_context_contains_persona(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        assert "persona" in context
        persona = context["persona"]
        assert isinstance(persona, Persona)
        assert persona.name == "Strider"

    def test_get_context_contains_cartridge_version(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        assert "cartridge_version" in context
        version = context["cartridge_version"]
        assert isinstance(version, CartridgeVersion)
        assert version.version_tag == "v1.0.0"

    def test_get_context_contains_game_instance(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        assert "game_instance" in context
        assert context["game_instance"].id == sample_instance.id

    def test_get_context_persona_pronouns_are_correct(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        persona = context["persona"]
        assert persona.pronoun_sub == "he"
        assert persona.pronoun_obj == "him"
        assert persona.pronoun_poss == "his"
        assert persona.pronoun_poss_obj == "his"

    def test_get_context_yare_spec_is_deserialized_dict(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        assert isinstance(context["cartridge_version"].yare_spec, dict)

    def test_get_context_returns_none_for_missing_instance(self, store):
        result = store.get_game_instance_context("nonexistent-id")
        assert result is None

    def test_get_context_bot_lore_accessible(self, store, sample_instance):
        context = store.get_game_instance_context(sample_instance.id)
        assert context["cartridge_version"].bot_lore == "The world of Middle Earth..."


# ---------------------------------------------------------------------------
# AC3 — TurnLog atomic appends
# ---------------------------------------------------------------------------


class TestTurnLogAppend:
    def test_append_turn_log_assigns_id(self, store, sample_instance):
        log = TurnLog(
            instance_id=sample_instance.id,
            turn_index=0,
            actor=TurnActor.PLAYER,
            input_text="I draw my sword.",
            yare_delta={"events_fired": ["deal_damage"]},
        )
        saved = store.append_turn_log(log)
        assert saved.id is not None

    def test_append_turn_log_assigns_timestamp(self, store, sample_instance):
        log = TurnLog(
            instance_id=sample_instance.id,
            turn_index=0,
            actor=TurnActor.PLAYER,
            input_text="I draw my sword.",
            yare_delta={},
        )
        saved = store.append_turn_log(log)
        assert saved.timestamp is not None

    def test_append_multiple_turn_logs_in_order(self, store, sample_instance):
        for i in range(5):
            log = TurnLog(
                instance_id=sample_instance.id,
                turn_index=i,
                actor=TurnActor.PLAYER if i % 2 == 0 else TurnActor.NARRATOR,
                input_text=f"Turn {i} action.",
                yare_delta={"turn": i},
            )
            store.append_turn_log(log)

        logs = store.get_turn_logs(sample_instance.id)
        assert len(logs) == 5
        assert [l.turn_index for l in logs] == list(range(5))

    def test_turn_log_yare_delta_is_deserialized(self, store, sample_instance):
        log = TurnLog(
            instance_id=sample_instance.id,
            turn_index=0,
            actor=TurnActor.SYSTEM,
            input_text="Game initialized.",
            yare_delta={"initial": True, "events_fired": []},
        )
        saved = store.append_turn_log(log)
        fetched = store.get_turn_logs(sample_instance.id)
        assert isinstance(fetched[0].yare_delta, dict)
        assert fetched[0].yare_delta["initial"] is True

    def test_append_turn_log_all_actors(self, store, sample_instance):
        for idx, actor in enumerate(TurnActor):
            log = TurnLog(
                instance_id=sample_instance.id,
                turn_index=idx,
                actor=actor,
                input_text=f"Action by {actor.value}.",
                yare_delta={},
            )
            saved = store.append_turn_log(log)
            assert saved.id is not None


# ---------------------------------------------------------------------------
# AC4 — Migration initializes tables and indexes
# ---------------------------------------------------------------------------


class TestMigration:
    def test_initialize_is_idempotent(self):
        """Calling initialize() twice must not raise an error."""
        s = SQLite3PhysicalComponent(":memory:")
        s.initialize()
        s.initialize()  # second call must be a no-op

    def test_indexes_exist_after_initialize(self):
        s = SQLite3PhysicalComponent(":memory:")
        s.initialize()
        index_names = s._get_index_names()
        # At minimum, indexes on FK columns for join performance
        assert len(index_names) > 0

    def test_migrate_script_is_importable(self):
        import importlib.util, pathlib
        script = pathlib.Path("scripts/migrate_db.py")
        assert script.exists(), "scripts/migrate_db.py must exist"

    def test_migrate_script_creates_db_file(self, tmp_path):
        db_path = str(tmp_path / "test_mnesos.db")
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "migrate_db", pathlib.Path("scripts/migrate_db.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run(db_path)
        assert pathlib.Path(db_path).exists()

    def test_migrate_script_creates_all_tables(self, tmp_path):
        db_path = str(tmp_path / "test_mnesos.db")
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "migrate_db", pathlib.Path("scripts/migrate_db.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        expected = {
            "user_accounts",
            "personas",
            "cartridges",
            "cartridge_versions",
            "game_instances",
            "turn_logs",
        }
        assert expected.issubset(tables)


# ---------------------------------------------------------------------------
# AC5 — delete_db utility
# ---------------------------------------------------------------------------


class TestDeleteDbScript:
    def test_delete_script_is_importable(self):
        import pathlib
        script = pathlib.Path("scripts/delete_db.py")
        assert script.exists(), "scripts/delete_db.py must exist"

    def test_delete_script_removes_file(self, tmp_path):
        db_path = tmp_path / "mnesos.db"
        db_path.write_text("fake db")
        assert db_path.exists()

        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "delete_db", pathlib.Path("scripts/delete_db.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run(str(db_path))
        assert not db_path.exists()

    def test_delete_script_is_safe_when_file_missing(self, tmp_path):
        db_path = str(tmp_path / "nonexistent.db")

        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "delete_db", pathlib.Path("scripts/delete_db.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Must not raise
        mod.run(db_path)
