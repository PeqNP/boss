#
# Production — database layer
#
# Schema creation, every SQL statement the app issues, and the row models those
# statements return.
#
# Those row models are network models: they describe how SQLite hands data
# back, not what the app means by it. Fields are spelled as the columns are, so
# building one is a splat; booleans arrive as integers and JSON as text,
# because that is what the store holds.
#
# This module knows nothing about the domain and imports nothing from
# `model.py`. `lib.py` imports both and owns the conversion.
#
# All timestamps are ISO 8601 UTC strings. The client renders local time.
#

import logging
import os
import sqlite3

from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from lib import get_config

DB_NAME = "production.sqlite3"

# Bump when a `create_version_*` function is added, and add it to the chain in
# `start_database`.
CURRENT_VERSION = "1.0.0"


def set_database_name(name: str):
    """Point the app at a different database file.

    Tests call this so a run never touches the real database.
    """
    global DB_NAME
    DB_NAME = name


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


# Every statement closes its connection in a `finally`, and must keep doing so.
#
# A statement that fails — a NOT NULL violation, a bad column name — leaves its
# connection with `in_transaction` true, holding SQLite's write lock. If that
# connection is never closed, every later write in the process fails with
# "database is locked": one rejected request bricks the app until it restarts.
#
# This does not reproduce in a test. CPython drops the frame as the exception
# propagates, the connection is refcounted to zero and closed, and the lock
# goes with it. A web server is different — it retains the traceback to render
# its 500, the traceback holds the frame, and the frame holds the connection.
# So the `finally` is load-bearing in production and invisible in the suite.

def select(query: str, params: Optional[tuple] = None) -> List[Any]:
    conn = get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        records = cursor.fetchall()
        cursor.close()
        return records
    finally:
        conn.close()


def update(query: str, params: tuple) -> int:
    """Run a statement and return the number of rows it changed.

    The count is returned rather than asserted: several rules depend on an
    update matching nothing — claiming a work unit another operator already
    took, for instance — and that is an outcome, not an error.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        changed = cursor.rowcount
        cursor.close()
        return changed
    finally:
        conn.close()


def insert(query: str, params: tuple) -> int:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rowid = cursor.lastrowid
        conn.commit()
        cursor.close()
        return rowid
    finally:
        conn.close()


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
            -- Who failed it. Recorded outright rather than inferred: failing
            -- clears `assigned_line_id`, and the last step to have completed
            -- may belong to an earlier operator, since a released unit keeps
            -- its progress and is handed on.
            failed_by INTEGER,              -- BOSS user id
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
    try:
        version = get_db_version(conn)
        logging.info(f"Production database version ({version})")
        create_version_1_0_0(conn, version)
    finally:
        conn.close()


# =========================================================================
# Row models
#
# One per query shape, table-shaped or not: joining to save a round trip is
# the data layer's business, and the shape it returns is its own. A query
# selecting a single column returns a list of values instead — a scalar is not
# a shape.
# =========================================================================


class PoolRow(BaseModel):
    id: int
    name: str
    created_at: str
    created_by: int


class PoolResourceRow(BaseModel):
    id: int
    pool_id: int
    name: str
    value: str
    in_service: int
    held_by_line_id: Optional[int]
    sort_order: int


class ProductionLineRow(BaseModel):
    id: int
    name: str
    current_version_id: Optional[int]
    created_at: str
    created_by: int


class ProductionLineVersionRow(BaseModel):
    id: int
    production_line_id: int
    version: int
    frozen: int
    created_at: str


class ProductionLineColumnRow(BaseModel):
    id: int
    version_id: int
    name: str
    sort_order: int


class ProductionLinePoolRow(BaseModel):
    id: int
    version_id: int
    pool_id: int
    pool_name: str
    sort_order: int


class OperationRow(BaseModel):
    id: int
    version_id: int
    name: str
    step: int


class OperationSectionRow(BaseModel):
    id: int
    operation_id: int
    section_type: str
    sort_order: int
    name: Optional[str]
    label: Optional[str]
    required: int
    body: Optional[str]
    image_path: Optional[str]


class OperationSectionOptionRow(BaseModel):
    id: int
    section_id: int
    label: str
    sort_order: int


class JobRow(BaseModel):
    id: int
    name: str
    production_line_id: int
    version_id: Optional[int]
    scheduled_start: str
    scheduled_completion: str
    active: int
    created_at: str
    created_by: int


class WorkUnitRow(BaseModel):
    id: int
    job_id: int
    row_order: int
    input_json: str
    state: str
    assigned_line_id: Optional[int]
    current_step: int
    started_at: Optional[str]
    completed_at: Optional[str]
    failed_at: Optional[str]
    failed_step: Optional[int]
    failed_by: Optional[int]
    requeued_at: Optional[str]


class JobLineRow(BaseModel):
    id: int
    job_id: int
    user_id: int
    state: str
    pause_origin: Optional[str]
    stop_origin: Optional[str]
    stop_reason: Optional[str]
    units_completed: int
    units_failed: int
    joined_at: str
    last_active_at: Optional[str]


class WorkUnitOperationRow(BaseModel):
    id: int
    work_unit_id: int
    step: int
    state: str
    notes: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    completed_by: Optional[int]


class WorkUnitValueRow(BaseModel):
    step: int
    name: str
    value: Optional[str]


class WorkUnitResourceRow(BaseModel):
    pool_name: str
    resource_name: str
    resource_value: str


class WorkUnitEditRow(BaseModel):
    id: int
    work_unit_id: int
    step: int
    name: str
    old_value: Optional[str]
    new_value: Optional[str]
    edited_by: int
    edited_at: str
    steps_reset: int


class LineEventRow(BaseModel):
    id: int
    line_id: int
    event_type: str
    origin: Optional[str]
    reason: Optional[str]
    actor_id: Optional[int]
    started_at: str
    ended_at: Optional[str]


# --- Shapes that come from a join or an aggregate -------------------------

class PoolReferenceRow(BaseModel):
    """A production line version that requires a pool, named for a message."""
    line_name: str
    version: int


class HeldResourceRow(BaseModel):
    resource_name: str
    user_id: int


class LineResourceRow(BaseModel):
    """What a line holds, resolved through to the pool and resource names."""
    pool_id: int
    resource_id: int
    pool_name: str
    resource_name: str
    resource_value: str


class LiveLineRow(BaseModel):
    """A line an operator still holds, with the job it belongs to."""
    id: int
    job_name: str


class StateCountRow(BaseModel):
    state: str
    count: int


class CompletedUnitRow(BaseModel):
    """Only what a throughput calculation reads."""
    id: int
    started_at: Optional[str]
    completed_at: str
    assigned_line_id: Optional[int]


class BlockingIntervalRow(BaseModel):
    """A stretch during which a line could not work. Open while `ended_at` is None."""
    started_at: str
    ended_at: Optional[str]


# =========================================================================
# Queries
#
# Every statement the app issues lives below, one function per query, named
# for what it means rather than what it selects. Business rules in `lib.py`
# call these and never write SQL, so the whole data surface of the app can be
# read in one place — which is also the surface a security review has to check.
# =========================================================================


def _one(query: str, params: tuple):
    rows = select(query, params)
    return rows[0] if rows else None


def _one_as(model, query: str, params: tuple):
    """The first row as `model`, or `None` when the query matched nothing."""
    rows = select(query, params)
    return model(**rows[0]) if rows else None


def _all_as(model, query: str, params: tuple) -> List[Any]:
    return [model(**row) for row in select(query, params)]


# --- Pools ---------------------------------------------------------------

def get_pool(pool_id: int) -> Optional[PoolRow]:
    return _one_as(PoolRow, "SELECT * FROM pools WHERE id = ?", (pool_id,))


def get_pools() -> List[PoolRow]:
    return _all_as(PoolRow, "SELECT * FROM pools ORDER BY name COLLATE NOCASE", ())


def find_pool_named(name: str, exclude_id: Optional[int] = None) -> Optional[PoolRow]:
    """A pool with this name, ignoring case. Names must be unique that way:
    a token finds a pool by name, matched case-insensitively."""
    return _one_as(PoolRow, "SELECT * FROM pools WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
                (name, exclude_id))


def insert_pool(name: str, user_id: int) -> int:
    return insert("INSERT INTO pools (name, created_at, created_by)"
                  " VALUES (?, datetime('now'), ?)", (name, user_id))


def set_pool_name(pool_id: int, name: str) -> int:
    return update("UPDATE pools SET name = ? WHERE id = ?", (name, pool_id))


def delete_pool(pool_id: int) -> int:
    return update("DELETE FROM pools WHERE id = ?", (pool_id,))


def pool_references(pool_id: int) -> List[PoolReferenceRow]:
    """Production line versions requiring a pool, current and historical.

    History counts: a finished work unit is rendered with the version it was
    made under, so a renamed pool would leave its tokens unresolvable.
    """
    return _all_as(PoolReferenceRow,
        "SELECT l.name AS line_name, v.version AS version"
        " FROM production_line_pools p"
        " JOIN production_line_versions v ON v.id = p.version_id"
        " JOIN production_lines l ON l.id = v.production_line_id"
        " WHERE p.pool_id = ? ORDER BY l.name, v.version", (pool_id,))


# --- Pool resources -------------------------------------------------------

def get_resource(resource_id: int) -> Optional[PoolResourceRow]:
    return _one_as(PoolResourceRow, "SELECT * FROM pool_resources WHERE id = ?", (resource_id,))


def get_resource_in_pool(resource_id: int, pool_id: int) -> Optional[PoolResourceRow]:
    return _one_as(PoolResourceRow, "SELECT * FROM pool_resources WHERE id = ? AND pool_id = ?",
                (resource_id, pool_id))


def get_resources(pool_id: int) -> List[PoolResourceRow]:
    return _all_as(
        PoolResourceRow,
        "SELECT * FROM pool_resources WHERE pool_id = ? ORDER BY sort_order", (pool_id,))


def insert_resource(pool_id: int, name: str, value: str, sort_order: int) -> int:
    return insert("INSERT INTO pool_resources (pool_id, name, value, sort_order)"
                  " VALUES (?, ?, ?, ?)", (pool_id, name, value, sort_order))


def update_resource(resource_id: int, name: str, value: str, in_service: int) -> int:
    return update("UPDATE pool_resources SET name = ?, value = ?, in_service = ? WHERE id = ?",
                  (name, value, in_service, resource_id))


def delete_resource(resource_id: int) -> int:
    return update("DELETE FROM pool_resources WHERE id = ?", (resource_id,))


def held_resources(pool_id: int) -> List[HeldResourceRow]:
    return _all_as(HeldResourceRow,
        "SELECT r.name AS resource_name, l.user_id AS user_id"
        " FROM pool_resources r JOIN job_lines l ON l.id = r.held_by_line_id"
        " WHERE r.pool_id = ?", (pool_id,))


def checkout_resource(resource_id: int, line_id: int) -> int:
    """Claim a resource for a line, and report whether the claim landed.

    The conditions are part of the statement rather than checked beforehand,
    so two operators joining at once cannot both take the same card.
    """
    return update(
        "UPDATE pool_resources SET held_by_line_id = ?"
        " WHERE id = ? AND in_service = 1 AND (held_by_line_id IS NULL OR held_by_line_id = ?)",
        (line_id, resource_id, line_id))


def release_resource(resource_id: int) -> int:
    return update("UPDATE pool_resources SET held_by_line_id = NULL WHERE id = ?", (resource_id,))


def release_resources_of_line(line_id: int) -> int:
    return update("UPDATE pool_resources SET held_by_line_id = NULL WHERE held_by_line_id = ?",
                  (line_id,))


# --- Production lines -----------------------------------------------------

def get_production_line(line_id: int) -> Optional[ProductionLineRow]:
    return _one_as(ProductionLineRow, "SELECT * FROM production_lines WHERE id = ?", (line_id,))


def get_production_lines() -> List[ProductionLineRow]:
    return _all_as(
        ProductionLineRow,
        "SELECT * FROM production_lines ORDER BY name COLLATE NOCASE", ())


def insert_production_line(name: str, user_id: int) -> int:
    return insert("INSERT INTO production_lines (name, created_at, created_by)"
                  " VALUES (?, datetime('now'), ?)", (name, user_id))


def set_production_line_name(line_id: int, name: str) -> int:
    return update("UPDATE production_lines SET name = ? WHERE id = ?", (name, line_id))


def set_current_version(line_id: int, version_id: int) -> int:
    return update("UPDATE production_lines SET current_version_id = ? WHERE id = ?",
                  (version_id, line_id))


def delete_production_line(line_id: int) -> int:
    return update("DELETE FROM production_lines WHERE id = ?", (line_id,))


# --- Versions -------------------------------------------------------------

def get_version(version_id: int) -> Optional[ProductionLineVersionRow]:
    return _one_as(
        ProductionLineVersionRow,
        "SELECT * FROM production_line_versions WHERE id = ?", (version_id,))


def get_versions(line_id: int) -> List[ProductionLineVersionRow]:
    return _all_as(
        ProductionLineVersionRow,
        "SELECT * FROM production_line_versions WHERE production_line_id = ?"
        " ORDER BY version DESC", (line_id,))


def insert_version(line_id: int, version: int) -> int:
    return insert("INSERT INTO production_line_versions (production_line_id, version, created_at)"
                  " VALUES (?, ?, datetime('now'))", (line_id, version))


def freeze_version(version_id: int) -> int:
    return update("UPDATE production_line_versions SET frozen = 1 WHERE id = ?", (version_id,))


# --- Declared columns -----------------------------------------------------

def get_columns(version_id: int) -> List[ProductionLineColumnRow]:
    return _all_as(
        ProductionLineColumnRow,
        "SELECT * FROM production_line_columns WHERE version_id = ? ORDER BY sort_order",
        (version_id,))


def insert_column(version_id: int, name: str, sort_order: int) -> int:
    return insert("INSERT INTO production_line_columns (version_id, name, sort_order)"
                  " VALUES (?, ?, ?)", (version_id, name, sort_order))


def delete_columns(version_id: int) -> int:
    return update("DELETE FROM production_line_columns WHERE version_id = ?", (version_id,))


# --- Required pools -------------------------------------------------------

def get_version_pools(version_id: int) -> List[ProductionLinePoolRow]:
    return _all_as(
        ProductionLinePoolRow,
        "SELECT * FROM production_line_pools WHERE version_id = ? ORDER BY sort_order",
        (version_id,))


def insert_version_pool(version_id: int, pool_id: int, pool_name: str, sort_order: int) -> int:
    return insert("INSERT INTO production_line_pools (version_id, pool_id, pool_name, sort_order)"
                  " VALUES (?, ?, ?, ?)", (version_id, pool_id, pool_name, sort_order))


def delete_version_pools(version_id: int) -> int:
    return update("DELETE FROM production_line_pools WHERE version_id = ?", (version_id,))


# --- Operations and sections ----------------------------------------------

def get_operations(version_id: int) -> List[OperationRow]:
    return _all_as(
        OperationRow,
        "SELECT * FROM operations WHERE version_id = ? ORDER BY step", (version_id,))


def get_operation(operation_id: int) -> Optional[OperationRow]:
    return _one_as(OperationRow, "SELECT * FROM operations WHERE id = ?", (operation_id,))


def get_operation_at(version_id: int, step: int) -> Optional[OperationRow]:
    return _one_as(
        OperationRow,
        "SELECT * FROM operations WHERE version_id = ? AND step = ?", (version_id, step))


def get_last_step(version_id: int) -> int:
    row = _one("SELECT MAX(step) AS step FROM operations WHERE version_id = ?", (version_id,))
    return (row["step"] or 0) if row else 0


def count_operations(version_id: int) -> int:
    return _one("SELECT COUNT(*) AS count FROM operations WHERE version_id = ?",
                (version_id,))["count"]


def insert_operation(version_id: int, name: str, step: int) -> int:
    return insert("INSERT INTO operations (version_id, name, step) VALUES (?, ?, ?)",
                  (version_id, name, step))


def get_sections(operation_id: int) -> List[OperationSectionRow]:
    return _all_as(
        OperationSectionRow,
        "SELECT * FROM operation_sections WHERE operation_id = ? ORDER BY sort_order",
        (operation_id,))


def get_section(section_id: int) -> Optional[OperationSectionRow]:
    return _one_as(
        OperationSectionRow,
        "SELECT * FROM operation_sections WHERE id = ?", (section_id,))


def count_sections(operation_id: int) -> int:
    return _one("SELECT COUNT(*) AS count FROM operation_sections WHERE operation_id = ?",
                (operation_id,))["count"]


def insert_section(operation_id: int, section_type: str, sort_order: int, name, label,
                   required, body, image_path) -> int:
    return insert(
        "INSERT INTO operation_sections (operation_id, section_type, sort_order, name, label,"
        " required, body, image_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (operation_id, section_type, sort_order, name, label, required, body, image_path))


def get_section_options(section_id: int) -> List[OperationSectionOptionRow]:
    return _all_as(
        OperationSectionOptionRow,
        "SELECT * FROM operation_section_options WHERE section_id = ? ORDER BY sort_order",
        (section_id,))


def insert_section_option(section_id: int, label: str, sort_order: int) -> int:
    return insert("INSERT INTO operation_section_options (section_id, label, sort_order)"
                  " VALUES (?, ?, ?)", (section_id, label, sort_order))


# --- Jobs -----------------------------------------------------------------

def get_job(job_id: int) -> Optional[JobRow]:
    return _one_as(JobRow, "SELECT * FROM jobs WHERE id = ?", (job_id,))


def get_jobs() -> List[JobRow]:
    return _all_as(JobRow, "SELECT * FROM jobs ORDER BY scheduled_start DESC, name", ())


def get_active_jobs() -> List[JobRow]:
    return _all_as(
        JobRow,
        "SELECT * FROM jobs WHERE active = 1 ORDER BY scheduled_start, name", ())


def get_jobs_using_line(line_id: int) -> List[JobRow]:
    return _all_as(
        JobRow,
        "SELECT * FROM jobs WHERE production_line_id = ? ORDER BY name", (line_id,))


def count_jobs_using_version(version_id: int) -> int:
    return _one("SELECT COUNT(*) AS count FROM jobs WHERE version_id = ?",
                (version_id,))["count"]


def insert_job(name: str, production_line_id: int, scheduled_start: str,
               scheduled_completion: str, user_id: int) -> int:
    return insert(
        "INSERT INTO jobs (name, production_line_id, scheduled_start, scheduled_completion,"
        " created_at, created_by) VALUES (?, ?, ?, ?, datetime('now'), ?)",
        (name, production_line_id, scheduled_start, scheduled_completion, user_id))


def update_job(job_id: int, name: str, production_line_id: int, scheduled_start: str,
               scheduled_completion: str) -> int:
    return update("UPDATE jobs SET name = ?, production_line_id = ?, scheduled_start = ?,"
                  " scheduled_completion = ? WHERE id = ?",
                  (name, production_line_id, scheduled_start, scheduled_completion, job_id))


def pin_job_version(job_id: int, version_id: int) -> int:
    return update("UPDATE jobs SET version_id = ? WHERE id = ?", (version_id, job_id))


def set_job_active(job_id: int, active: bool) -> int:
    return update("UPDATE jobs SET active = ? WHERE id = ?", (1 if active else 0, job_id))


def delete_job(job_id: int) -> int:
    return update("DELETE FROM jobs WHERE id = ?", (job_id,))


# --- Work units -----------------------------------------------------------

def get_work_unit(work_unit_id: int) -> Optional[WorkUnitRow]:
    return _one_as(WorkUnitRow, "SELECT * FROM work_units WHERE id = ?", (work_unit_id,))


def get_work_units(job_id: int) -> List[WorkUnitRow]:
    return _all_as(
        WorkUnitRow,
        "SELECT * FROM work_units WHERE job_id = ? ORDER BY row_order", (job_id,))


def insert_work_unit(job_id: int, row_order: int, input_json: str) -> int:
    return insert("INSERT INTO work_units (job_id, row_order, input_json) VALUES (?, ?, ?)",
                  (job_id, row_order, input_json))


def delete_work_units(job_id: int) -> int:
    return update("DELETE FROM work_units WHERE job_id = ?", (job_id,))


def count_work_units(job_id: int) -> int:
    return _one("SELECT COUNT(*) AS count FROM work_units WHERE job_id = ?", (job_id,))["count"]


def count_unresolved_work_units(job_id: int) -> int:
    return _one("SELECT COUNT(*) AS count FROM work_units WHERE job_id = ?"
                " AND state NOT IN ('complete', 'failed')", (job_id,))["count"]


def count_available_work_units(job_id: int) -> int:
    return _one("SELECT COUNT(*) AS count FROM work_units WHERE job_id = ?"
                " AND state = 'pending' AND assigned_line_id IS NULL", (job_id,))["count"]


def count_work_units_by_state(job_id: int) -> List[StateCountRow]:
    return _all_as(
        StateCountRow,
        "SELECT state, COUNT(*) AS count FROM work_units WHERE job_id = ?"
        " GROUP BY state", (job_id,))


def worked_work_unit_counts(job_id: int) -> List[StateCountRow]:
    return _all_as(
        StateCountRow,
        "SELECT state, COUNT(*) AS count FROM work_units WHERE job_id = ?"
        " AND state IN ('complete', 'failed') GROUP BY state", (job_id,))


# Requeued units first, then units someone already started, then untouched CSV
# order. A partial outranks a fresh unit so work in progress finishes rather
# than accumulating.
QUEUE_ORDER = ("CASE WHEN requeued_at IS NOT NULL THEN 0"
               "      WHEN started_at  IS NOT NULL THEN 1"
               "      ELSE 2 END, row_order")


def claim_next_work_unit(job_id: int, line_id: int) -> int:
    """Assign the next queued unit to a line, reporting whether it landed.

    The selection and the claim are one statement: two operators tapping Pull
    at the same instant must never receive the same unit. The loser sees zero
    rows changed and asks again.
    """
    return update(
        "UPDATE work_units SET assigned_line_id = ?, state = 'in_progress',"
        " started_at = COALESCE(started_at, datetime('now'))"
        " WHERE id = (SELECT id FROM work_units"
        "             WHERE job_id = ? AND state = 'pending' AND assigned_line_id IS NULL"
        f"            ORDER BY {QUEUE_ORDER} LIMIT 1)"
        "   AND state = 'pending' AND assigned_line_id IS NULL",
        (line_id, job_id))


def get_claimed_work_unit(line_id: int) -> Optional[WorkUnitRow]:
    return _one_as(
        WorkUnitRow,
        "SELECT * FROM work_units WHERE assigned_line_id = ? AND state = 'in_progress'"
        " ORDER BY id DESC LIMIT 1", (line_id,))


def set_work_unit_step(work_unit_id: int, step: int) -> int:
    return update("UPDATE work_units SET current_step = ? WHERE id = ?", (step, work_unit_id))


def complete_work_unit(work_unit_id: int, step: int) -> int:
    return update("UPDATE work_units SET state = 'complete', completed_at = datetime('now'),"
                  " current_step = ? WHERE id = ?", (step, work_unit_id))


def fail_work_unit(work_unit_id: int, step: int, user_id: Optional[int]) -> int:
    return update("UPDATE work_units SET state = 'failed', failed_step = ?,"
                  " failed_at = datetime('now'), failed_by = ?,"
                  " assigned_line_id = NULL WHERE id = ?",
                  (step, user_id, work_unit_id))


def requeue_work_unit(work_unit_id: int) -> int:
    return update(
        "UPDATE work_units SET state = 'pending', assigned_line_id = NULL, current_step = 1,"
        " started_at = NULL, completed_at = NULL, failed_at = NULL, failed_step = NULL,"
        " failed_by = NULL, requeued_at = datetime('now') WHERE id = ?", (work_unit_id,))


def release_work_units_of_line(line_id: int) -> int:
    """Return a line's in-progress unit to the queue, keeping its progress."""
    return update("UPDATE work_units SET assigned_line_id = NULL, state = 'pending'"
                  " WHERE assigned_line_id = ? AND state = 'in_progress'", (line_id,))


def get_units_completed_since(job_id: int, window_minutes: int) -> List[CompletedUnitRow]:
    return _all_as(CompletedUnitRow,
        "SELECT id, started_at, completed_at, assigned_line_id FROM work_units"
        " WHERE job_id = ? AND state = 'complete' AND completed_at IS NOT NULL"
        "   AND completed_at >= datetime('now', ?)",
        (job_id, f"-{int(window_minutes)} minutes"))


# --- Work unit progress ---------------------------------------------------

def get_unit_operation(work_unit_id: int, step: int) -> Optional[WorkUnitOperationRow]:
    return _one_as(
        WorkUnitOperationRow,
        "SELECT * FROM work_unit_operations WHERE work_unit_id = ? AND step = ?",
        (work_unit_id, step))


def get_unit_operations(work_unit_id: int) -> List[WorkUnitOperationRow]:
    return _all_as(
        WorkUnitOperationRow,
        "SELECT * FROM work_unit_operations WHERE work_unit_id = ? ORDER BY step",
        (work_unit_id,))


def insert_unit_operation(work_unit_id: int, step: int, state: str, notes,
                          completed_by, completed: bool) -> int:
    stamp = "datetime('now')" if completed else "NULL"
    return insert(
        f"INSERT INTO work_unit_operations (work_unit_id, step, state, notes, started_at,"
        f" completed_at, completed_by) VALUES (?, ?, ?, ?, datetime('now'), {stamp}, ?)",
        (work_unit_id, step, state, notes, completed_by))


def update_unit_operation(row_id: int, state: str, notes, completed_by, completed: bool) -> int:
    stamp = "datetime('now')" if completed else "NULL"
    return update(f"UPDATE work_unit_operations SET state = ?, notes = ?, completed_at = {stamp},"
                  f" completed_by = ? WHERE id = ?", (state, notes, completed_by, row_id))


def get_completed_steps_after(work_unit_id: int, step: int) -> List[int]:
    return [row["step"] for row in select(
        "SELECT step FROM work_unit_operations WHERE work_unit_id = ? AND step > ?"
        " AND state = 'complete'", (work_unit_id, step))]


def reset_operations_after(work_unit_id: int, step: int) -> int:
    return update("UPDATE work_unit_operations SET state = 'pending', completed_at = NULL,"
                  " completed_by = NULL WHERE work_unit_id = ? AND step > ?",
                  (work_unit_id, step))


def delete_unit_operations(work_unit_id: int) -> int:
    return update("DELETE FROM work_unit_operations WHERE work_unit_id = ?", (work_unit_id,))


def get_unit_values(work_unit_id: int) -> List[WorkUnitValueRow]:
    return _all_as(
        WorkUnitValueRow,
        "SELECT step, name, value FROM work_unit_values WHERE work_unit_id = ?",
        (work_unit_id,))


def get_unit_values_at(work_unit_id: int, step: int) -> List[WorkUnitValueRow]:
    return _all_as(
        WorkUnitValueRow,
        "SELECT step, name, value FROM work_unit_values WHERE work_unit_id = ?"
        " AND step = ?", (work_unit_id, step))


def put_unit_value(work_unit_id: int, step: int, name: str, value) -> int:
    return update("INSERT OR REPLACE INTO work_unit_values (work_unit_id, step, name, value)"
                  " VALUES (?, ?, ?, ?)", (work_unit_id, step, name, value))


def delete_unit_values(work_unit_id: int) -> int:
    return update("DELETE FROM work_unit_values WHERE work_unit_id = ?", (work_unit_id,))


def insert_unit_edit(work_unit_id: int, step: int, name: str, old_value, new_value,
                     edited_by: int, steps_reset: int) -> int:
    return insert("INSERT INTO work_unit_edits (work_unit_id, step, name, old_value, new_value,"
                  " edited_by, edited_at, steps_reset)"
                  " VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)",
                  (work_unit_id, step, name, old_value, new_value, edited_by, steps_reset))


def get_unit_edits(work_unit_id: int) -> List[WorkUnitEditRow]:
    return _all_as(
        WorkUnitEditRow,
        "SELECT * FROM work_unit_edits WHERE work_unit_id = ? ORDER BY edited_at",
        (work_unit_id,))


def get_unit_resources(work_unit_id: int) -> List[WorkUnitResourceRow]:
    return _all_as(
        WorkUnitResourceRow,
        "SELECT pool_name, resource_name, resource_value FROM work_unit_resources"
        " WHERE work_unit_id = ?", (work_unit_id,))


def put_unit_resource(work_unit_id: int, pool_name: str, resource_name: str,
                      resource_value: str) -> int:
    return update("INSERT OR REPLACE INTO work_unit_resources"
                  " (work_unit_id, pool_name, resource_name, resource_value)"
                  " VALUES (?, ?, ?, ?)",
                  (work_unit_id, pool_name, resource_name, resource_value))


def delete_unit_resources(work_unit_id: int) -> int:
    return update("DELETE FROM work_unit_resources WHERE work_unit_id = ?", (work_unit_id,))


# --- Lines ----------------------------------------------------------------

def get_line(line_id: int) -> Optional[JobLineRow]:
    return _one_as(JobLineRow, "SELECT * FROM job_lines WHERE id = ?", (line_id,))


def get_line_for(job_id: int, user_id: int) -> Optional[JobLineRow]:
    return _one_as(
        JobLineRow,
        "SELECT * FROM job_lines WHERE job_id = ? AND user_id = ?", (job_id, user_id))


def get_lines(job_id: int) -> List[JobLineRow]:
    return _all_as(
        JobLineRow,
        "SELECT * FROM job_lines WHERE job_id = ? ORDER BY joined_at", (job_id,))


def get_working_lines(job_id: int) -> List[JobLineRow]:
    return _all_as(
        JobLineRow,
        "SELECT * FROM job_lines WHERE job_id = ? AND state = 'working'", (job_id,))


def get_live_lines_elsewhere(user_id: int, job_id: int, live_states: tuple) -> List[LiveLineRow]:
    """Lines this operator still holds on other jobs. One line at a time."""
    return _all_as(LiveLineRow,
        "SELECT l.id, j.name AS job_name FROM job_lines l JOIN jobs j ON j.id = l.job_id"
        " WHERE l.user_id = ? AND l.job_id != ? AND l.state IN (?, ?, ?)",
        (user_id, job_id) + live_states)


def get_live_line_user_ids(job_id: int, live_states: tuple) -> List[int]:
    return [row["user_id"] for row in select(
        "SELECT DISTINCT user_id FROM job_lines WHERE job_id = ? AND state IN (?, ?, ?)",
        (job_id,) + live_states)]


def insert_line(job_id: int, user_id: int) -> int:
    return insert("INSERT INTO job_lines (job_id, user_id, state, joined_at, last_active_at)"
                  " VALUES (?, ?, 'working', datetime('now'), datetime('now'))",
                  (job_id, user_id))


def set_line_working(line_id: int) -> int:
    return update("UPDATE job_lines SET state = 'working', pause_origin = NULL,"
                  " stop_origin = NULL, stop_reason = NULL, last_active_at = datetime('now')"
                  " WHERE id = ?", (line_id,))


def set_line_paused(line_id: int, origin: str) -> int:
    return update("UPDATE job_lines SET state = 'paused', pause_origin = ?,"
                  " last_active_at = datetime('now') WHERE id = ?", (origin, line_id))


def set_line_stopped(line_id: int, origin: str, reason) -> int:
    return update("UPDATE job_lines SET state = 'stopped', stop_origin = ?, stop_reason = ?,"
                  " last_active_at = datetime('now') WHERE id = ?", (origin, reason, line_id))


def set_line_left(line_id: int) -> int:
    return update("UPDATE job_lines SET state = 'left', pause_origin = NULL, stop_origin = NULL,"
                  " stop_reason = NULL, last_active_at = datetime('now') WHERE id = ?", (line_id,))


def resume_admin_paused_lines(job_id: int) -> int:
    """Clear only the pauses a job stop raised, leaving operators on break."""
    return update("UPDATE job_lines SET state = 'working', pause_origin = NULL"
                  " WHERE job_id = ? AND state = 'paused' AND pause_origin = 'admin'", (job_id,))


def touch_line(line_id: int) -> int:
    return update("UPDATE job_lines SET last_active_at = datetime('now') WHERE id = ?", (line_id,))


def increment_units_completed(line_id: int) -> int:
    return update("UPDATE job_lines SET units_completed = units_completed + 1,"
                  " last_active_at = datetime('now') WHERE id = ?", (line_id,))


def increment_units_failed(line_id: int) -> int:
    return update("UPDATE job_lines SET units_failed = units_failed + 1,"
                  " last_active_at = datetime('now') WHERE id = ?", (line_id,))


# --- Line resources -------------------------------------------------------

def get_line_resources(line_id: int) -> List[LineResourceRow]:
    return _all_as(LineResourceRow,
        "SELECT jlr.pool_id, jlr.resource_id, p.name AS pool_name,"
        "       r.name AS resource_name, r.value AS resource_value"
        " FROM job_line_resources jlr"
        " JOIN pools p ON p.id = jlr.pool_id"
        " JOIN pool_resources r ON r.id = jlr.resource_id"
        " WHERE jlr.line_id = ?", (line_id,))


def put_line_resource(line_id: int, pool_id: int, resource_id: int) -> int:
    return update("INSERT OR REPLACE INTO job_line_resources (line_id, pool_id, resource_id)"
                  " VALUES (?, ?, ?)", (line_id, pool_id, resource_id))


def delete_line_resource(line_id: int, resource_id: int) -> int:
    return update("DELETE FROM job_line_resources WHERE line_id = ? AND resource_id = ?",
                  (line_id, resource_id))


def delete_line_resources(line_id: int) -> int:
    return update("DELETE FROM job_line_resources WHERE line_id = ?", (line_id,))


# --- Line events ----------------------------------------------------------

def insert_line_event(line_id: int, event_type: str, origin, reason, actor_id) -> int:
    return insert("INSERT INTO line_events (line_id, event_type, origin, reason, actor_id,"
                  " started_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                  (line_id, event_type, origin, reason, actor_id))


def insert_closed_line_event(line_id: int, event_type: str, actor_id) -> int:
    """An event with no duration — joining or leaving happens at an instant."""
    return insert("INSERT INTO line_events (line_id, event_type, actor_id, started_at, ended_at)"
                  " VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                  (line_id, event_type, actor_id))


def close_line_events(line_id: int) -> int:
    """Close every open pause or stop interval on a line."""
    return update("UPDATE line_events SET ended_at = datetime('now')"
                  " WHERE line_id = ? AND event_type IN ('pause', 'stop') AND ended_at IS NULL",
                  (line_id,))


def close_admin_pause_events(job_id: int) -> int:
    return update("UPDATE line_events SET ended_at = datetime('now')"
                  " WHERE event_type = 'pause' AND ended_at IS NULL AND origin = 'admin'"
                  "   AND line_id IN (SELECT id FROM job_lines WHERE job_id = ?)", (job_id,))


def get_blocking_events(line_id: int) -> List[BlockingIntervalRow]:
    """Pause and stop intervals on a line, open ones included."""
    return _all_as(BlockingIntervalRow, "SELECT started_at, ended_at FROM line_events"
                  " WHERE line_id = ? AND event_type IN ('pause', 'stop')", (line_id,))


def get_line_events(line_id: int) -> List[LineEventRow]:
    return _all_as(
        LineEventRow,
        "SELECT * FROM line_events WHERE line_id = ? ORDER BY started_at", (line_id,))


def set_operation_name(operation_id: int, name: str) -> int:
    return update("UPDATE operations SET name = ? WHERE id = ?", (name, operation_id))


def set_operation_step(operation_id: int, step: int) -> int:
    return update("UPDATE operations SET step = ? WHERE id = ?", (step, operation_id))


def delete_operation(operation_id: int) -> int:
    return update("DELETE FROM operations WHERE id = ?", (operation_id,))


def update_section(section_id: int, section_type: str, name, label, required, body) -> int:
    return update("UPDATE operation_sections SET section_type = ?, name = ?, label = ?,"
                  " required = ?, body = ? WHERE id = ?",
                  (section_type, name, label, required, body, section_id))


def set_section_sort_order(section_id: int, sort_order: int) -> int:
    return update("UPDATE operation_sections SET sort_order = ? WHERE id = ?",
                  (sort_order, section_id))


def set_section_image(section_id: int, image_path) -> int:
    return update("UPDATE operation_sections SET image_path = ? WHERE id = ?",
                  (image_path, section_id))


def delete_section(section_id: int) -> int:
    return update("DELETE FROM operation_sections WHERE id = ?", (section_id,))


def delete_section_options(section_id: int) -> int:
    return update("DELETE FROM operation_section_options WHERE section_id = ?", (section_id,))


def get_live_lines_for(user_id: int, live_states: tuple) -> List[JobLineRow]:
    """Every line this operator still holds. One at a time is the rule."""
    return _all_as(
        JobLineRow,
        "SELECT * FROM job_lines WHERE user_id = ? AND state IN (?, ?, ?) ORDER BY joined_at",
        (user_id,) + live_states)


def get_work_units_for_line(line_id: int) -> List[WorkUnitRow]:
    return _all_as(WorkUnitRow, "SELECT * FROM work_units WHERE assigned_line_id = ?", (line_id,))


def close_intervals_at_last_active() -> int:
    """End every open pause or stop at its line's last activity.

    Used once on start-up: an interval left open by a restart would otherwise
    read as blocking forever.
    """
    return update(
        "UPDATE line_events SET ended_at = COALESCE("
        "    (SELECT last_active_at FROM job_lines WHERE id = line_events.line_id),"
        "    started_at)"
        " WHERE event_type IN ('pause', 'stop') AND ended_at IS NULL", ())
