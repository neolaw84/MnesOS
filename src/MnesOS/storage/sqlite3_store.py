"""
MnesOS SQLite3PhysicalComponent — SQLite-backed implementation of
AbstractStorageComponent.

Design notes
------------
* Uses a single ``sqlite3.Connection`` per component instance with
  ``isolation_level=None`` (autocommit) for TurnLog appends; all other
  mutating operations are wrapped in explicit transactions via the
  connection's context-manager protocol.
* JSON blobs (``yare_spec``, ``prompt_directives``, ``yare_delta``) are
  serialized on write and deserialized on read.
* All primary keys are UUID4 strings to allow future migration to a
  distributed store without key collisions.
* ``initialize()`` is idempotent — uses ``CREATE TABLE IF NOT EXISTS``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .interface import AbstractStorageComponent
from .models import (
    CartridgeVersion,
    Cartridge,
    GameInstance,
    GameSave,
    GameStatus,
    Persona,
    TurnActor,
    TurnLog,
    UserAccount,
    UserRole,
    Visibility,
)

# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ts_to_str(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_ts(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS user_accounts (
    id           TEXT PRIMARY KEY,
    username     TEXT NOT NULL UNIQUE,
    email        TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personas (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES user_accounts(id),
    name             TEXT NOT NULL,
    pronoun_sub      TEXT NOT NULL,
    pronoun_obj      TEXT NOT NULL,
    pronoun_poss     TEXT NOT NULL,
    pronoun_poss_obj TEXT NOT NULL,
    appearance       TEXT NOT NULL DEFAULT '',
    background       TEXT NOT NULL DEFAULT '',
    personality      TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cartridges (
    id          TEXT PRIMARY KEY,
    creator_id  TEXT NOT NULL REFERENCES user_accounts(id),
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    genre       TEXT NOT NULL DEFAULT '',
    visibility  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cartridge_versions (
    id                TEXT PRIMARY KEY,
    cartridge_id      TEXT NOT NULL REFERENCES cartridges(id),
    version_tag       TEXT NOT NULL,
    yare_spec         TEXT NOT NULL DEFAULT '{}',
    prompt_directives TEXT NOT NULL DEFAULT '{}',
    bot_lore          TEXT NOT NULL DEFAULT '',
    first_message     TEXT NOT NULL DEFAULT '',
    checksum          TEXT NOT NULL,
    yare_js_src       TEXT DEFAULT NULL,
    published_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_instances (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES user_accounts(id),
    persona_id     TEXT NOT NULL REFERENCES personas(id),
    version_id     TEXT NOT NULL REFERENCES cartridge_versions(id),
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    last_played_at TEXT
);

CREATE TABLE IF NOT EXISTS turn_logs (
    id            TEXT PRIMARY KEY,
    instance_id   TEXT NOT NULL REFERENCES game_instances(id),
    turn_index    INTEGER NOT NULL,
    actor         TEXT NOT NULL,
    input_text    TEXT NOT NULL DEFAULT '',
    yare_delta    TEXT NOT NULL DEFAULT '{}',
    narrator_text TEXT NOT NULL DEFAULT '',
    parent_id     TEXT REFERENCES turn_logs(id),
    timestamp     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_saves (
    id           TEXT PRIMARY KEY,
    instance_id  TEXT NOT NULL REFERENCES game_instances(id),
    turn_log_id  TEXT NOT NULL REFERENCES turn_logs(id),
    label        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_personas_user_id
    ON personas(user_id);

CREATE INDEX IF NOT EXISTS idx_cartridges_creator_id
    ON cartridges(creator_id);

CREATE INDEX IF NOT EXISTS idx_cartridge_versions_cartridge_id
    ON cartridge_versions(cartridge_id);

CREATE INDEX IF NOT EXISTS idx_game_instances_user_id
    ON game_instances(user_id);

CREATE INDEX IF NOT EXISTS idx_game_instances_persona_id
    ON game_instances(persona_id);

CREATE INDEX IF NOT EXISTS idx_game_instances_version_id
    ON game_instances(version_id);

CREATE INDEX IF NOT EXISTS idx_turn_logs_instance_id
    ON turn_logs(instance_id);

CREATE INDEX IF NOT EXISTS idx_turn_logs_instance_turn
    ON turn_logs(instance_id, turn_index);

CREATE INDEX IF NOT EXISTS idx_turn_logs_parent_id
    ON turn_logs(parent_id);

CREATE INDEX IF NOT EXISTS idx_game_saves_instance_id
    ON game_saves(instance_id);

CREATE INDEX IF NOT EXISTS idx_game_saves_turn_log_id
    ON game_saves(turn_log_id);
"""


# ---------------------------------------------------------------------------
# SQLite3PhysicalComponent
# ---------------------------------------------------------------------------


class SQLite3PhysicalComponent(AbstractStorageComponent):
    """
    SQLite3-backed physical storage component.

    Parameters
    ----------
    db_path:
        Filesystem path to the ``.db`` file, or ``":memory:"`` for an
        in-process in-memory database (useful for testing).
    """

    def __init__(self, db_path: str = os.environ.get("MNESOS_DB_PATH", "artifacts/mnesos.db")) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            if self._db_path != ":memory:":
                parent_dir = os.path.dirname(self._db_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
        return self._conn

    def _get_table_names(self) -> Set[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {row["name"] for row in rows}

    def _get_index_names(self) -> Set[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        return {row["name"] for row in rows}

    def _get_personas_column_names(self) -> Set[str]:
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(personas)").fetchall()
        return {row["name"] for row in rows}

    def _migrate_personas_table(self) -> None:
        """
        Apply additive, backward-compatible migrations for legacy ``personas`` schema.

        Older databases may still have the prior ``lore``-centric table definition.
        We preserve existing data and add newly required columns if missing.
        """
        conn = self._get_conn()
        columns = self._get_personas_column_names()
        missing_column_ddls = {
            "appearance": "ALTER TABLE personas ADD COLUMN appearance TEXT NOT NULL DEFAULT ''",
            "background": "ALTER TABLE personas ADD COLUMN background TEXT NOT NULL DEFAULT ''",
            "personality": "ALTER TABLE personas ADD COLUMN personality TEXT NOT NULL DEFAULT ''",
        }
        with conn:
            for column, ddl in missing_column_ddls.items():
                if column not in columns:
                    conn.execute(ddl)

    def _get_turn_logs_column_names(self) -> Set[str]:
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(turn_logs)").fetchall()
        return {row["name"] for row in rows}

    def _migrate_turn_logs_table(self) -> None:
        """
        Apply additive migrations for the ``turn_logs`` table to support
        tree-based event sourcing (``parent_id``, ``narrator_text``).
        """
        conn = self._get_conn()
        columns = self._get_turn_logs_column_names()
        missing_column_ddls = {
            "parent_id": "ALTER TABLE turn_logs ADD COLUMN parent_id TEXT REFERENCES turn_logs(id)",
            "narrator_text": "ALTER TABLE turn_logs ADD COLUMN narrator_text TEXT NOT NULL DEFAULT ''",
        }
        with conn:
            for column, ddl in missing_column_ddls.items():
                if column not in columns:
                    conn.execute(ddl)

    def _get_cartridge_versions_column_names(self) -> Set[str]:
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(cartridge_versions)").fetchall()
        return {row["name"] for row in rows}

    def _migrate_cartridge_versions_table(self) -> None:
        """
        Apply additive migrations for the ``cartridge_versions`` table to support
        storing YARE JavaScript source code (``yare_js_src``).
        """
        conn = self._get_conn()
        columns = self._get_cartridge_versions_column_names()
        missing_column_ddls = {
            "yare_js_src": "ALTER TABLE cartridge_versions ADD COLUMN yare_js_src TEXT DEFAULT NULL",
        }
        with conn:
            for column, ddl in missing_column_ddls.items():
                if column not in columns:
                    conn.execute(ddl)

    @staticmethod
    def _new_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _json_dump(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def _json_load(s: str) -> Any:
        return json.loads(s)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create schema idempotently (``IF NOT EXISTS``)."""
        conn = self._get_conn()
        conn.executescript(_DDL)
        conn.executescript(_INDEXES)
        self._migrate_personas_table()
        self._migrate_turn_logs_table()
        self._migrate_cartridge_versions_table()
        # Ensure default local-user exists to satisfy foreign key constraints
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_accounts
                    (id, username, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "local-user",
                    "local-user",
                    "local@example.com",
                    "",
                    "CREATOR",
                    _ts_to_str(_now_utc()),
                ),
            )

    # ------------------------------------------------------------------
    # UserAccount
    # ------------------------------------------------------------------

    def create_user(self, user: UserAccount) -> UserAccount:
        user.id = self._new_id()
        user.created_at = _now_utc()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO user_accounts
                    (id, username, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.email,
                    user.password_hash,
                    user.role.value,
                    _ts_to_str(user.created_at),
                ),
            )
        return user

    def get_user(self, user_id: str) -> Optional[UserAccount]:
        row = self._get_conn().execute(
            "SELECT * FROM user_accounts WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return UserAccount(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=UserRole(row["role"]),
            created_at=_str_to_ts(row["created_at"]),
        )

    def update_user(self, user: UserAccount) -> UserAccount:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                UPDATE user_accounts
                SET username=?, email=?, password_hash=?, role=?
                WHERE id=?
                """,
                (
                    user.username,
                    user.email,
                    user.password_hash,
                    user.role.value,
                    user.id,
                ),
            )
        return user

    def delete_user(self, user_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM user_accounts WHERE id=?", (user_id,))

    # ------------------------------------------------------------------
    # Persona
    # ------------------------------------------------------------------

    def create_persona(self, persona: Persona) -> Persona:
        persona.id = self._new_id()
        persona.created_at = _now_utc()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO personas
                    (id, user_id, name, pronoun_sub, pronoun_obj,
                     pronoun_poss, pronoun_poss_obj, appearance,
                     background, personality, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    persona.id,
                    persona.user_id,
                    persona.name,
                    persona.pronoun_sub,
                    persona.pronoun_obj,
                    persona.pronoun_poss,
                    persona.pronoun_poss_obj,
                    persona.appearance,
                    persona.background,
                    persona.personality,
                    _ts_to_str(persona.created_at),
                ),
            )
        return persona

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        row = self._get_conn().execute(
            "SELECT * FROM personas WHERE id = ?", (persona_id,)
        ).fetchone()
        if row is None:
            return None
        return Persona(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            pronoun_sub=row["pronoun_sub"],
            pronoun_obj=row["pronoun_obj"],
            pronoun_poss=row["pronoun_poss"],
            pronoun_poss_obj=row["pronoun_poss_obj"],
            appearance=row["appearance"],
            background=row["background"],
            personality=row["personality"],
            created_at=_str_to_ts(row["created_at"]),
        )

    def list_personas(self, user_id: str) -> List[Persona]:
        rows = self._get_conn().execute(
            "SELECT * FROM personas WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,)
        ).fetchall()
        return [
            Persona(
                id=row["id"],
                user_id=row["user_id"],
                name=row["name"],
                pronoun_sub=row["pronoun_sub"],
                pronoun_obj=row["pronoun_obj"],
                pronoun_poss=row["pronoun_poss"],
                pronoun_poss_obj=row["pronoun_poss_obj"],
                appearance=row["appearance"],
                background=row["background"],
                personality=row["personality"],
                created_at=_str_to_ts(row["created_at"]),
            )
            for row in rows
        ]

    def update_persona(self, persona: Persona) -> Persona:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                UPDATE personas
                SET user_id=?, name=?, pronoun_sub=?, pronoun_obj=?,
                    pronoun_poss=?, pronoun_poss_obj=?, appearance=?,
                    background=?, personality=?
                WHERE id=?
                """,
                (
                    persona.user_id,
                    persona.name,
                    persona.pronoun_sub,
                    persona.pronoun_obj,
                    persona.pronoun_poss,
                    persona.pronoun_poss_obj,
                    persona.appearance,
                    persona.background,
                    persona.personality,
                    persona.id,
                ),
            )
        return persona

    def delete_persona(self, persona_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM personas WHERE id=?", (persona_id,))

    # ------------------------------------------------------------------
    # Cartridge
    # ------------------------------------------------------------------

    def create_cartridge(self, cartridge: Cartridge) -> Cartridge:
        cartridge.id = self._new_id()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO cartridges
                    (id, creator_id, title, description, genre, visibility)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cartridge.id,
                    cartridge.creator_id,
                    cartridge.title,
                    cartridge.description,
                    cartridge.genre,
                    cartridge.visibility.value,
                ),
            )
        return cartridge

    def get_cartridge(self, cartridge_id: str) -> Optional[Cartridge]:
        row = self._get_conn().execute(
            "SELECT * FROM cartridges WHERE id = ?", (cartridge_id,)
        ).fetchone()
        if row is None:
            return None
        return Cartridge(
            id=row["id"],
            creator_id=row["creator_id"],
            title=row["title"],
            description=row["description"],
            genre=row["genre"],
            visibility=Visibility(row["visibility"]),
        )

    def update_cartridge(self, cartridge: Cartridge) -> Cartridge:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                UPDATE cartridges
                SET creator_id=?, title=?, description=?, genre=?, visibility=?
                WHERE id=?
                """,
                (
                    cartridge.creator_id,
                    cartridge.title,
                    cartridge.description,
                    cartridge.genre,
                    cartridge.visibility.value,
                    cartridge.id,
                ),
            )
        return cartridge

    def delete_cartridge(self, cartridge_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM cartridges WHERE id=?", (cartridge_id,))

    def list_cartridges(self) -> List[Cartridge]:
        rows = self._get_conn().execute(
            "SELECT * FROM cartridges ORDER BY title"
        ).fetchall()
        return [
            Cartridge(
                id=row["id"],
                creator_id=row["creator_id"],
                title=row["title"],
                description=row["description"],
                genre=row["genre"],
                visibility=Visibility(row["visibility"]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # CartridgeVersion
    # ------------------------------------------------------------------

    def create_cartridge_version(
        self, version: CartridgeVersion
    ) -> CartridgeVersion:
        version.id = self._new_id()
        version.published_at = _now_utc()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO cartridge_versions
                    (id, cartridge_id, version_tag, yare_spec, prompt_directives,
                     bot_lore, first_message, checksum, yare_js_src, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.id,
                    version.cartridge_id,
                    version.version_tag,
                    self._json_dump(version.yare_spec),
                    self._json_dump(version.prompt_directives),
                    version.bot_lore,
                    version.first_message,
                    version.checksum,
                    version.yare_js_src,
                    _ts_to_str(version.published_at),
                ),
            )
        return version

    def get_cartridge_version(
        self, version_id: str
    ) -> Optional[CartridgeVersion]:
        row = self._get_conn().execute(
            "SELECT * FROM cartridge_versions WHERE id = ?", (version_id,)
        ).fetchone()
        if row is None:
            return None
        return CartridgeVersion(
            id=row["id"],
            cartridge_id=row["cartridge_id"],
            version_tag=row["version_tag"],
            yare_spec=self._json_load(row["yare_spec"]),
            prompt_directives=self._json_load(row["prompt_directives"]),
            bot_lore=row["bot_lore"],
            first_message=row["first_message"],
            checksum=row["checksum"],
            yare_js_src=row["yare_js_src"] if "yare_js_src" in row.keys() else None,
            published_at=_str_to_ts(row["published_at"]),
        )

    def list_cartridge_versions(self, cartridge_id: str) -> List[CartridgeVersion]:
        rows = self._get_conn().execute(
            "SELECT * FROM cartridge_versions WHERE cartridge_id = ? ORDER BY published_at",
            (cartridge_id,),
        ).fetchall()
        return [
            CartridgeVersion(
                id=row["id"],
                cartridge_id=row["cartridge_id"],
                version_tag=row["version_tag"],
                yare_spec=self._json_load(row["yare_spec"]),
                prompt_directives=self._json_load(row["prompt_directives"]),
                bot_lore=row["bot_lore"],
                first_message=row["first_message"],
                checksum=row["checksum"],
                yare_js_src=row["yare_js_src"] if "yare_js_src" in row.keys() else None,
                published_at=_str_to_ts(row["published_at"]),
            )
            for row in rows]
    def delete_cartridge_version(self, version_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM cartridge_versions WHERE id = ?", (version_id,))

    # ------------------------------------------------------------------
    # GameInstance
    # ------------------------------------------------------------------

    def create_game_instance(self, instance: GameInstance) -> GameInstance:
        instance.id = self._new_id()
        instance.created_at = _now_utc()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO game_instances
                    (id, user_id, persona_id, version_id, status,
                     created_at, last_played_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instance.id,
                    instance.user_id,
                    instance.persona_id,
                    instance.version_id,
                    instance.status.value,
                    _ts_to_str(instance.created_at),
                    _ts_to_str(instance.last_played_at),
                ),
            )
        return instance

    def get_game_instance(self, instance_id: str) -> Optional[GameInstance]:
        row = self._get_conn().execute(
            "SELECT * FROM game_instances WHERE id = ?", (instance_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_game_instance(row)

    def update_game_instance(self, instance: GameInstance) -> GameInstance:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                UPDATE game_instances
                SET user_id=?, persona_id=?, version_id=?, status=?,
                    last_played_at=?
                WHERE id=?
                """,
                (
                    instance.user_id,
                    instance.persona_id,
                    instance.version_id,
                    instance.status.value,
                    _ts_to_str(instance.last_played_at),
                    instance.id,
                ),
            )
        return instance

    def list_game_instances(self, user_id: str) -> List[GameInstance]:
        rows = self._get_conn().execute(
            "SELECT * FROM game_instances WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [self._row_to_game_instance(row) for row in rows]

    def delete_game_instance(self, instance_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM game_saves WHERE instance_id = ?", (instance_id,))
            conn.execute("DELETE FROM turn_logs WHERE instance_id = ?", (instance_id,))
            conn.execute("DELETE FROM game_instances WHERE id = ?", (instance_id,))

    def get_game_instance_context(
        self, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the full context for a GameInstance in a single joined query.

        Returns a dict with ``game_instance``, ``persona``, and
        ``cartridge_version`` keys, or None if the instance does not exist.
        """
        row = self._get_conn().execute(
            """
            SELECT
                gi.id            AS gi_id,
                gi.user_id       AS gi_user_id,
                gi.persona_id    AS gi_persona_id,
                gi.version_id    AS gi_version_id,
                gi.status        AS gi_status,
                gi.created_at    AS gi_created_at,
                gi.last_played_at AS gi_last_played_at,

                p.id             AS p_id,
                p.user_id        AS p_user_id,
                p.name           AS p_name,
                p.pronoun_sub    AS p_pronoun_sub,
                p.pronoun_obj    AS p_pronoun_obj,
                p.pronoun_poss   AS p_pronoun_poss,
                p.pronoun_poss_obj AS p_pronoun_poss_obj,
                p.appearance     AS p_appearance,
                p.background     AS p_background,
                p.personality    AS p_personality,
                p.created_at     AS p_created_at,

                cv.id            AS cv_id,
                cv.cartridge_id  AS cv_cartridge_id,
                cv.version_tag   AS cv_version_tag,
                cv.yare_spec     AS cv_yare_spec,
                cv.prompt_directives AS cv_prompt_directives,
                cv.bot_lore      AS cv_bot_lore,
                cv.first_message AS cv_first_message,
                cv.checksum      AS cv_checksum,
                cv.published_at  AS cv_published_at

            FROM game_instances gi
            JOIN personas p          ON p.id  = gi.persona_id
            JOIN cartridge_versions cv ON cv.id = gi.version_id
            WHERE gi.id = ?
            """,
            (instance_id,),
        ).fetchone()

        if row is None:
            return None

        game_instance = GameInstance(
            id=row["gi_id"],
            user_id=row["gi_user_id"],
            persona_id=row["gi_persona_id"],
            version_id=row["gi_version_id"],
            status=GameStatus(row["gi_status"]),
            created_at=_str_to_ts(row["gi_created_at"]),
            last_played_at=_str_to_ts(row["gi_last_played_at"]),
        )
        persona = Persona(
            id=row["p_id"],
            user_id=row["p_user_id"],
            name=row["p_name"],
            pronoun_sub=row["p_pronoun_sub"],
            pronoun_obj=row["p_pronoun_obj"],
            pronoun_poss=row["p_pronoun_poss"],
            pronoun_poss_obj=row["p_pronoun_poss_obj"],
            appearance=row["p_appearance"],
            background=row["p_background"],
            personality=row["p_personality"],
            created_at=_str_to_ts(row["p_created_at"]),
        )
        cartridge_version = CartridgeVersion(
            id=row["cv_id"],
            cartridge_id=row["cv_cartridge_id"],
            version_tag=row["cv_version_tag"],
            yare_spec=self._json_load(row["cv_yare_spec"]),
            prompt_directives=self._json_load(row["cv_prompt_directives"]),
            bot_lore=row["cv_bot_lore"],
            first_message=row["cv_first_message"],
            checksum=row["cv_checksum"],
            published_at=_str_to_ts(row["cv_published_at"]),
        )

        return {
            "game_instance": game_instance,
            "persona": persona,
            "cartridge_version": cartridge_version,
        }

    # ------------------------------------------------------------------
    # TurnLog — write-optimized atomic append
    # ------------------------------------------------------------------

    def append_turn_log(self, log: TurnLog) -> TurnLog:
        """
        Atomically insert a TurnLog entry.

        Uses an explicit ``BEGIN IMMEDIATE`` transaction to serialise
        concurrent writers and prevent torn writes on the log sequence.
        """
        log.id = self._new_id()
        log.timestamp = _now_utc()
        conn = self._get_conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO turn_logs
                    (id, instance_id, turn_index, actor, input_text,
                     yare_delta, narrator_text, parent_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.instance_id,
                    log.turn_index,
                    log.actor.value,
                    log.input_text,
                    self._json_dump(log.yare_delta),
                    log.narrator_text,
                    log.parent_id,
                    _ts_to_str(log.timestamp),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return log

    def get_turn_logs(
        self, instance_id: str, limit: Optional[int] = None
    ) -> List[TurnLog]:
        sql = (
            "SELECT * FROM turn_logs WHERE instance_id = ? "
            "ORDER BY turn_index ASC"
        )
        params: tuple = (instance_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (instance_id, limit)
        rows = self._get_conn().execute(sql, params).fetchall()
        return [self._row_to_turn_log(row) for row in rows]

    def get_turn_log(self, turn_id: str) -> Optional[TurnLog]:
        row = self._get_conn().execute(
            "SELECT * FROM turn_logs WHERE id = ?", (turn_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_turn_log(row)

    def delete_turn_log(self, turn_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM turn_logs WHERE id = ?", (turn_id,))

    def get_turn_lineage(self, turn_id: str) -> List[TurnLog]:
        """
        Walk up the ``parent_id`` chain from *turn_id* to the root and
        return the path ordered root → … → *turn_id*.

        Raises ``KeyError`` if *turn_id* does not exist.
        """
        conn = self._get_conn()
        chain: List[TurnLog] = []
        current_id: Optional[str] = turn_id

        while current_id is not None:
            row = conn.execute(
                "SELECT * FROM turn_logs WHERE id = ?", (current_id,)
            ).fetchone()
            if row is None:
                if not chain:
                    raise KeyError(f"TurnLog with id {turn_id!r} not found")
                break
            turn_log = self._row_to_turn_log(row)
            chain.append(turn_log)
            current_id = turn_log.parent_id

        chain.reverse()
        return chain

    # ------------------------------------------------------------------
    # GameSave — bookmarks into the turn tree
    # ------------------------------------------------------------------

    def create_game_save(self, save: GameSave) -> GameSave:
        save.id = self._new_id()
        save.created_at = _now_utc()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO game_saves
                    (id, instance_id, turn_log_id, label, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    save.id,
                    save.instance_id,
                    save.turn_log_id,
                    save.label,
                    _ts_to_str(save.created_at),
                ),
            )
        return save

    def get_game_save(self, save_id: str) -> Optional[GameSave]:
        row = self._get_conn().execute(
            "SELECT * FROM game_saves WHERE id = ?", (save_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_game_save(row)

    def update_game_save(self, save: GameSave) -> GameSave:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                UPDATE game_saves
                SET label = ?
                WHERE id = ?
                """,
                (save.label, save.id),
            )
        return save

    def list_game_saves(self, instance_id: str) -> List[GameSave]:
        rows = self._get_conn().execute(
            "SELECT * FROM game_saves WHERE instance_id = ? ORDER BY created_at ASC",
            (instance_id,),
        ).fetchall()
        return [self._row_to_game_save(row) for row in rows]

    def delete_game_save(self, save_id: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM game_saves WHERE id=?", (save_id,))

    # ------------------------------------------------------------------
    # Private row-to-model helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_game_instance(row: sqlite3.Row) -> GameInstance:
        return GameInstance(
            id=row["id"],
            user_id=row["user_id"],
            persona_id=row["persona_id"],
            version_id=row["version_id"],
            status=GameStatus(row["status"]) if row["status"] else GameStatus.ACTIVE,
            created_at=_str_to_ts(row["created_at"]),
            last_played_at=_str_to_ts(row["last_played_at"]),
        )

    def _row_to_turn_log(self, row: sqlite3.Row) -> TurnLog:
        return TurnLog(
            id=row["id"],
            instance_id=row["instance_id"],
            turn_index=row["turn_index"],
            actor=TurnActor(row["actor"]),
            input_text=row["input_text"],
            yare_delta=self._json_load(row["yare_delta"]),
            narrator_text=row["narrator_text"],
            parent_id=row["parent_id"],
            timestamp=_str_to_ts(row["timestamp"]),
        )

    @staticmethod
    def _row_to_game_save(row: sqlite3.Row) -> GameSave:
        return GameSave(
            id=row["id"],
            instance_id=row["instance_id"],
            turn_log_id=row["turn_log_id"],
            label=row["label"],
            created_at=_str_to_ts(row["created_at"]),
        )
