#
# Workspace database.
#
# One row is one icon on one surface. Name and icon are not stored. A read
# fills them from installed.json. The guest is user id 2, seeded here. A
# signed-in user's starting list is not a seed.
#

import logging
import os
import sqlite3

from typing import Optional

from lib import get_config

DB_NAME = "workspace.sqlite3"

# Bump only when a different plan adds the next function in `start_database`.
CURRENT_VERSION = "1.0.0"

# The same id as `Global.guestUserId` and `GUEST_USER_ID` in the client.
GUEST_USER_ID = 2

# Desktop order for the guest. The dock has no guest rows.
GUEST_DESKTOP = (
    "io.bithead.json-formatter",
    "io.bithead.tutorial",
    "io.bithead.lean-visualizer",
    "io.bithead.wordy",
)


def set_database_name(name: str):
    """Point the app at a different database file.

    Tests call this so a run never touches the real database.
    """
    global DB_NAME
    DB_NAME = name


def get_db_path() -> str:
    """Path of the workspace database file."""
    cfg = get_config()
    return os.path.join(cfg.db_path, DB_NAME)


def delete_database():
    """Remove the database file. Tests call this between cases."""
    path = get_db_path()
    if os.path.isfile(path):
        os.unlink(path)


def get_conn() -> sqlite3.Connection:
    """Connection to the workspace database.

    The caller closes it, in a `finally`.
    """
    return sqlite3.connect(get_db_path())


def get_db_version(conn) -> Optional[tuple]:
    """Current schema version, or None when the schema is not yet created."""
    try:
        row = conn.execute(
            "SELECT version FROM versions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        raise Exception(
            "Could not read the workspace database version. This is fatal."
        )
    return tuple(int(part) for part in row[0].split("."))


def create_version_1_0_0(conn, version):
    """Create the workspace schema and seed the guest desktop.

    Returns without doing anything when the database is already at this
    version or beyond.
    """
    if version is not None and version >= (1, 0, 0):
        return

    conn.executescript(
        """
        CREATE TABLE versions (
            version TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        -- One icon on one surface, for one BOSS user.
        -- The account itself lives in the other service. user_id is that id.
        -- User id 2 is the guest.
        CREATE TABLE link (
            user_id   INTEGER NOT NULL,
            surface   TEXT NOT NULL CHECK (surface IN ('desktop', 'dock')),
            position  INTEGER NOT NULL, -- 0-based order within the surface
            bundle_id TEXT NOT NULL,
            PRIMARY KEY (user_id, surface, bundle_id),
            UNIQUE (user_id, surface, position)
        );

        -- bundle_id is a trailing primary-key column that names another record.
        CREATE INDEX idx_link_bundle_id ON link (bundle_id);
        """
    )
    conn.execute(
        "INSERT INTO versions (version, created_at)"
        " VALUES (?, datetime('now'))",
        (CURRENT_VERSION,)
    )
    conn.executemany(
        "INSERT INTO link (user_id, surface, position, bundle_id)"
        " VALUES (?, 'desktop', ?, ?)",
        [
            (GUEST_USER_ID, position, bundle_id)
            for position, bundle_id in enumerate(GUEST_DESKTOP)
        ]
    )
    conn.commit()


def create_schema(conn):
    """Bring a connection up to the current schema, whatever version it is at.

    `bin/check-db` runs this into an empty database to see what the schema
    declares, so this is the one definition of that.
    """
    version = get_db_version(conn)
    create_version_1_0_0(conn, version)


def start_database():
    """Create the database when it is missing, and bring it up to the schema."""
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = get_conn()
    try:
        logging.info("Workspace database version (%s)", get_db_version(conn))
        create_schema(conn)
    finally:
        conn.close()
