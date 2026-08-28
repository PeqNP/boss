#
# Schema drift.
#
# A version records which migrations have run, and a schema still being written
# keeps changing under a version that stays put: `create_version_1_0_0` grows a
# table, the version it writes is still 1.0.0, and a database made yesterday
# matches on version while lacking today's tables. Comparing the objects
# themselves is what sees it.
#
# A missing table surfaces as a 500 from whichever route touches it, pointing
# away from itself. A missing index surfaces as the same answers arriving
# slowly, saying nothing at all.
#
# An app supplies two things: a function bringing a connection up to the
# current schema, and the path to its database file. Everything here is generic
# over those.
#

import os
import re
import sqlite3

from typing import Callable, Dict, List, Tuple

from . import Environment, get_config


class NotDevelopment(Exception):
    """Raised where a rebuild is asked for outside a development machine."""


def _environment():
    """Which kind of machine this is, from the live config."""
    try:
        return get_config().env
    except Exception:
        return None


def _normalise(sql: str) -> str:
    """One definition written two ways, reduced to what it declares.

    Comments and layout are how a schema is kept readable, and neither
    declares anything. Reducing both sides the same way is what lets a
    definition be compared at all — without it, re-indenting a table reads as
    the table having changed.
    """
    without_comments = re.sub(r"--[^\n]*", " ", sql or "")
    collapsed = re.sub(r"\s+", " ", without_comments).strip()
    # Space beside punctuation is layout too. `name TEXT NOT NULL)` and
    # `name TEXT NOT NULL\n)` declare one thing, and a column list broken
    # across lines is the ordinary way to write a table worth reading.
    #
    # Case is left alone. SQLite ignores it in keywords and identifiers alike,
    # but not inside a string — folding one would make `DEFAULT 'Draft'`
    # compare equal to `DEFAULT 'draft'`.
    return re.sub(r"\s*([(),])\s*", r"\1", collapsed)


def _objects(conn) -> Dict[Tuple[str, str], str]:
    """(kind, name) -> definition, for every table and index a connection holds.

    The definition is carried, not just the name. A column that gains a
    constraint — `vendor_type TEXT NOT NULL` becoming `... UNIQUE` — leaves
    the table list, the index list and the row counts all identical, and a
    comparison by name calls that database current while the constraint the
    code relies on is absent from it.

    SQLite's own indexes carry the `sqlite_` prefix and are created for primary
    keys and UNIQUE columns. They are left out because the table that declares
    them is compared in full, which is where that constraint is stated.
    """
    return {
        (row[0], row[1]): _normalise(row[2])
        for row in conn.execute(
            "SELECT type, name, sql FROM sqlite_master"
            " WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%'"
        )
    }


def declared(create_schema: Callable) -> Dict[Tuple[str, str], str]:
    """Everything the schema creates, built in memory.

    Built by running the same function the real database is created by, so the
    comparison is against the schema as it stands rather than against a list
    somebody maintains beside it.
    """
    conn = sqlite3.connect(":memory:")
    try:
        # Nothing is inserted here beyond what the schema seeds itself, and
        # a schema declares its foreign keys in whatever order reads best.
        conn.execute("PRAGMA foreign_keys = OFF")
        create_schema(conn)
        return _objects(conn)
    finally:
        conn.close()


def existing(db_path: str) -> Dict[Tuple[str, str], str]:
    """Everything the database on disk holds."""
    conn = sqlite3.connect(db_path)
    try:
        return _objects(conn)
    finally:
        conn.close()


def seeded(create_schema: Callable) -> dict:
    """How many rows the schema seeds into each table, built in memory."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        create_schema(conn)
        counts = {}
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            rows = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            if rows:
                counts[name] = rows
        return counts
    finally:
        conn.close()


def seed_drift(create_schema: Callable, db_path: str) -> List[str]:
    """Tables the schema seeds that the database has fewer rows in.

    A seed is rows rather than structure, so a table added to `_seed_*` is
    invisible to `drift`: the table was already there, and only its contents
    changed. A database made before the seed never receives it, and the app
    reads an empty list where the installation should have given it a set.

    Fewer rather than different: a seeded table an app has since added to is
    ordinary, and only a shortfall says the seed never ran.
    """
    if not os.path.isfile(db_path):
        return []

    conn = sqlite3.connect(db_path)
    try:
        short = []
        for table, expected in sorted(seeded(create_schema).items()):
            try:
                have = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                continue          # missing table — `drift` reports that one
            if have < expected:
                short.append(f"{table} ({have} of {expected} seeded rows)")
        return short
    finally:
        conn.close()


def drift(create_schema: Callable, db_path: str) -> List[str]:
    """Objects the schema declares that the database lacks or states differently.

    Two ways to be behind, reported apart because they read differently: a
    name that is absent, and a name that is present declaring something else.

    One direction. A table the schema stopped declaring is left where it is —
    it answers no query, and removing it would be a migration.

    A database that has yet to be created returns nothing: the service creates
    it on the way up, and there is nothing to compare until it has.
    """
    if not os.path.isfile(db_path):
        return []
    here, there = declared(create_schema), existing(db_path)

    behind = []
    for key, definition in here.items():
        name = key[1]
        if key not in there:
            behind.append(name)
        elif there[key] != definition:
            behind.append(f"{name} (declared differently)")
    return sorted(behind)


def rebuild(create_schema: Callable, db_path: str) -> None:
    """Delete the database and create it again from the schema.

    The answer while a schema is still moving and there are no migrations, and
    a development tool for that reason: it discards every row. Creating a
    database that has yet to exist reaches the same call.

    The guard is for the day this is wired into something that also runs on a
    server. `bin/update` calls `private/start`, so that path stays clear of
    this entirely.
    """
    env = _environment()
    if env is not Environment.DEV:
        raise NotDevelopment(
            f"Rebuilding a database discards every row, and this machine is"
            f" `env: {getattr(env, 'value', None) or 'unset'}`."
        )
    if os.path.isfile(db_path):
        os.unlink(db_path)

    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)
    finally:
        conn.close()
