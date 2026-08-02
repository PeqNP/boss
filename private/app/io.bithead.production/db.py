#
# Production — database layer
#
# Schema creation and, from Stage 4, every SQL statement the app issues.
# Nothing outside this module should import sqlite3: business rules live in
# `lib.py` and take and return plain values.
#
# All timestamps are ISO 8601 UTC strings. The client renders local time.
#

import logging
import os
import sqlite3

from typing import Any, List, Optional

from lib import get_config

DB_NAME = "production.sqlite3"

# Bump when a `create_version_*` function is added, and add it to the chain in
# `start_database`.
CURRENT_VERSION = "1.0.0"


def get_db_path() -> str:
    cfg = get_config()
    return os.path.join(cfg.db_path, DB_NAME)


def delete_database():
    """Remove the database file. Used by tests between cases."""
    path = get_db_path()
    if os.path.isfile(path):
        os.unlink(path)


def get_conn():
    """Connection to the Production database.

    Foreign keys are enforced per connection in SQLite and default to off. The
    schema leans on `ON DELETE CASCADE` — deleting a job must take its work
    units, lines, and logs with it — so every connection turns them on.
    """
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def select(query: str, params: Optional[tuple] = None) -> List[Any]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records


def update(query: str, params: tuple) -> int:
    """Run a statement and return the number of rows it changed.

    The count is returned rather than asserted: several rules depend on an
    update matching nothing — claiming a work unit another operator already
    took, for instance — and that is an outcome, not an error.
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    changed = cursor.rowcount
    cursor.close()
    conn.close()
    return changed


def insert(query: str, params: tuple) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rowid = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return rowid


def get_db_version(conn) -> Optional[tuple]:
    """Current schema version, or `None` when the database is not yet created."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT version
            FROM versions
            ORDER BY id DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()
    except sqlite3.OperationalError:
        return None
    if not latest:
        raise Exception("Could not read the Production database version. This is fatal.")
    return tuple(int(v) for v in latest[0].split("."))


def create_version_1_0_0(conn, version):
    """Create the initial schema.

    Table order follows dependencies, with two deliberate cycles: a pool
    resource points at the line holding it, and a production line points at its
    current version. SQLite resolves foreign key targets when a statement runs
    rather than when the table is declared, so the cycles are legal — but the
    order below still reads top-down for anyone learning the model.
    """
    if version is not None:
        return CURRENT_VERSION

    cursor = conn.cursor()
    cursor.execute("BEGIN TRANSACTION")

    cursor.execute("""
        CREATE TABLE versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            create_date TEXT NOT NULL
        )
    """)

    # -- Pools (global) ---------------------------------------------------

    cursor.execute("""
        CREATE TABLE pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            -- Token key: {pool.<name>}. May contain spaces.
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by INTEGER NOT NULL     -- BOSS user id
        )
    """)
    # Names are matched case-insensitively when a token resolves, so they must
    # be unique the same way.
    cursor.execute("CREATE UNIQUE INDEX idx_pools_name ON pools(name COLLATE NOCASE)")

    cursor.execute("""
        CREATE TABLE pool_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_id INTEGER NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
            name TEXT NOT NULL,             -- e.g. "Card 2"
            value TEXT NOT NULL,            -- interpolated value, e.g. "67890"
            in_service INTEGER NOT NULL DEFAULT 1,
            -- NULL = available. A resource is exclusive: one line at a time.
            held_by_line_id INTEGER REFERENCES job_lines(id),
            sort_order INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX idx_pool_resources_pool ON pool_resources(pool_id)")

    # -- Production lines (templates, versioned) ---------------------------

    cursor.execute("""
        CREATE TABLE production_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,             -- the product, e.g. "CR-One Reader"
            current_version_id INTEGER,     -- set once the first version exists
            created_at TEXT NOT NULL,
            created_by INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE production_line_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_line_id INTEGER NOT NULL
                REFERENCES production_lines(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,       -- 1-based, monotonic per line
            -- Set to 1 the first time a job starts against this version. A
            -- frozen version is immutable; the next edit deep-copies it into
            -- version + 1, so a finished work unit can always be shown exactly
            -- as its operator saw it.
            frozen INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(production_line_id, version)
        )
    """)

    cursor.execute("""
        CREATE TABLE production_line_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL
                REFERENCES production_line_versions(id) ON DELETE CASCADE,
            -- CSV header; token key {work_unit.<name>}
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE production_line_pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL
                REFERENCES production_line_versions(id) ON DELETE CASCADE,
            pool_id INTEGER NOT NULL REFERENCES pools(id),
            -- Denormalized so a historical version stays readable and its
            -- tokens stay resolvable. Renaming a pool is blocked while any
            -- version references it, so this cannot drift.
            pool_name TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL
                REFERENCES production_line_versions(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            -- 1-based; token key {operation.<step>.<name>}
            step INTEGER NOT NULL,
            UNIQUE(version_id, step)
        )
    """)

    cursor.execute("""
        CREATE TABLE operation_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
            -- description | image | text | number | checkbox | options
            section_type TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            name TEXT,                      -- input sections: token key
            label TEXT,                     -- input sections: shown to the operator
            required INTEGER NOT NULL DEFAULT 0,
            body TEXT,                      -- description sections: text with tokens
            -- Image sections: /upload/io.bithead.production/<file>. Each row
            -- owns its file outright — forking a frozen version copies the file
            -- as well as the row — so deleting a section can always delete its
            -- file unconditionally.
            image_path TEXT
        )
    """)
    cursor.execute("CREATE INDEX idx_sections_operation ON operation_sections(operation_id)")

    cursor.execute("""
        CREATE TABLE operation_section_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL
                REFERENCES operation_sections(id) ON DELETE CASCADE,
            label TEXT NOT NULL,            -- also the stored value when selected
            sort_order INTEGER NOT NULL
        )
    """)

    # -- Jobs and work units ----------------------------------------------

    cursor.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            production_line_id INTEGER NOT NULL REFERENCES production_lines(id),
            -- Pinned when the admin taps Start. NULL until then, which is also
            -- how "has never started" is determined.
            version_id INTEGER REFERENCES production_line_versions(id),
            scheduled_start TEXT NOT NULL,      -- YYYY-MM-DD
            scheduled_completion TEXT NOT NULL, -- YYYY-MM-DD, >= scheduled_start
            active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by INTEGER NOT NULL         -- admin who created the job
        )
    """)

    cursor.execute("""
        CREATE TABLE work_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            row_order INTEGER NOT NULL,     -- CSV row order; primary queue key
            -- {header: value} for every column in the CSV, including columns
            -- the production line did not declare. Undeclared columns are
            -- exported but are not interpolatable.
            input_json TEXT NOT NULL,
            -- pending | in_progress | complete | failed
            state TEXT NOT NULL DEFAULT 'pending',
            assigned_line_id INTEGER REFERENCES job_lines(id),  -- NULL = unassigned
            current_step INTEGER NOT NULL DEFAULT 1,
            started_at TEXT,                -- first time the unit was pulled
            completed_at TEXT,
            failed_at TEXT,
            failed_step INTEGER,
            -- Set by an admin requeue; sorts the unit to the front.
            requeued_at TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_work_units_queue
        ON work_units(job_id, state, assigned_line_id, row_order)
    """)

    # Queue order:
    #   ORDER BY CASE WHEN requeued_at IS NOT NULL THEN 0
    #                 WHEN started_at  IS NOT NULL THEN 1
    #                 ELSE 2 END,
    #            row_order
    # Requeued first, then partially-worked units, then untouched CSV order.

    # -- Lines (one permanent record per job + operator) --------------------

    cursor.execute("""
        CREATE TABLE job_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,       -- BOSS user id
            state TEXT NOT NULL,            -- working | paused | stopped | left
            pause_origin TEXT,              -- operator | admin | window
            stop_origin TEXT,               -- operator | admin
            stop_reason TEXT,               -- optional operator-supplied andon reason
            units_completed INTEGER NOT NULL DEFAULT 0,
            units_failed INTEGER NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL,
            last_active_at TEXT,
            -- Rejoining reuses the record: a line is permanent, and carries the
            -- operator's history for metrics.
            UNIQUE(job_id, user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE job_line_resources (
            line_id INTEGER NOT NULL REFERENCES job_lines(id) ON DELETE CASCADE,
            pool_id INTEGER NOT NULL REFERENCES pools(id),
            resource_id INTEGER NOT NULL REFERENCES pool_resources(id),
            -- Exactly one resource per required pool.
            PRIMARY KEY (line_id, pool_id)
        )
    """)

    # -- Work unit progress and logs ---------------------------------------

    cursor.execute("""
        CREATE TABLE work_unit_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
            step INTEGER NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',  -- pending | complete
            notes TEXT,
            started_at TEXT,                -- first time the step was shown
            completed_at TEXT,
            completed_by INTEGER,           -- BOSS user id
            UNIQUE(work_unit_id, step)
        )
    """)

    cursor.execute("""
        CREATE TABLE work_unit_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
            step INTEGER NOT NULL,
            name TEXT NOT NULL,             -- section name; {operation.<step>.<name>}
            -- text/number: as entered. checkbox: '1' | '0'. options: the label.
            value TEXT,
            UNIQUE(work_unit_id, step, name)
        )
    """)

    cursor.execute("""
        CREATE TABLE work_unit_resources (
            work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
            pool_name TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            -- Copied so the record survives a later edit to the resource.
            resource_value TEXT NOT NULL,
            PRIMARY KEY (work_unit_id, pool_name)
        )
    """)

    cursor.execute("""
        CREATE TABLE work_unit_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
            step INTEGER NOT NULL,
            name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            edited_by INTEGER NOT NULL,
            edited_at TEXT NOT NULL,
            -- How many later operations the edit invalidated.
            steps_reset INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE line_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id INTEGER NOT NULL REFERENCES job_lines(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,       -- join | leave | pause | stop
            origin TEXT,                    -- operator | admin | window
            reason TEXT,
            actor_id INTEGER,               -- BOSS user id who caused it
            started_at TEXT NOT NULL,
            -- NULL while a pause/stop interval is open. Throughput subtracts
            -- open and closed blocked intervals from wall-clock time.
            ended_at TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_line_events_line
        ON line_events(line_id, event_type, ended_at)
    """)

    cursor.execute(
        "INSERT INTO versions (version, create_date) VALUES (?, datetime('now'))",
        ("1.0.0",)
    )
    conn.commit()
    cursor.close()
    return "1.0.0"


def start_database():
    """Create or migrate the database. Called once when the service starts."""
    conn = get_conn()
    version = get_db_version(conn)
    logging.info(f"Production database version ({version})")
    create_version_1_0_0(conn, version)
    conn.close()
