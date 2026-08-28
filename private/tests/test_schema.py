#
# Schema drift, for a development database with no migrations yet.
#
# The helper under test is generic, so it is exercised against a toy schema
# rather than any app's. What an app supplies is a function that brings a
# connection up to the current schema, and the path to its database file.
#

import os
import sqlite3
import tempfile

import pytest

from lib import schema


# --- A schema to drift away from ------------------------------------------
#
# Two versions of the same app: `v1` is what a database on disk was made from,
# `v2` is what the code declares today. The version they write is identical,
# which is the whole of what makes drift invisible.

def v1(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS widgets ("
                 " id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_name ON widgets(name)")
    conn.commit()


def v2(conn):
    """`v1` plus a table, plus an index on a table `v1` already had."""
    v1(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS gadgets ("
                 " id INTEGER PRIMARY KEY, widget_id INTEGER NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gadgets_widget_id"
                 " ON gadgets(widget_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_expr"
                 " ON widgets(LOWER(name))")
    # A UNIQUE column, which SQLite backs with an index of its own named
    # `sqlite_autoindex_doodads_1`. It arrives with the table that declares it.
    conn.execute("CREATE TABLE IF NOT EXISTS doodads ("
                 " id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE)")
    conn.commit()


def v2_constrained(conn):
    """`v2` with a constraint added to a column of a table it already had.

    The name is the same on both sides, and so is every index. What changed is
    inside the definition.
    """
    v2(conn)
    conn.execute("DROP TABLE widgets")
    conn.execute("CREATE TABLE widgets ("
                 " id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_name ON widgets(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_expr"
                 " ON widgets(LOWER(name))")
    conn.commit()


def v2_spaced(conn):
    """`v2` written out differently, declaring the same thing."""
    conn.execute("CREATE TABLE IF NOT EXISTS widgets (\n"
                 "    id   INTEGER PRIMARY KEY,\n"
                 "    name TEXT NOT NULL   -- what it is called\n"
                 ")")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_name ON widgets(name)")
    conn.execute("CREATE TABLE IF NOT EXISTS gadgets ("
                 " id INTEGER PRIMARY KEY, widget_id INTEGER NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gadgets_widget_id"
                 " ON gadgets(widget_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_widgets_expr"
                 " ON widgets(LOWER(name))")
    conn.execute("CREATE TABLE IF NOT EXISTS doodads ("
                 " id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE)")
    conn.commit()


@pytest.fixture
def db_path():
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "test-drift.sqlite3")
    yield path
    if os.path.isfile(path):
        os.unlink(path)
    os.rmdir(directory)


def make(path, create):
    conn = sqlite3.connect(path)
    try:
        create(conn)
    finally:
        conn.close()


# --- The exceptions -------------------------------------------------------
#
# `schema` manages tables and indexes. It has no interface for rows, and
# whether a rebuild discards them is the thing most worth proving — so these
# two reach past it, each with one job.

def seed_a_row(path):
    """Put something in the database worth losing."""
    conn = sqlite3.connect(path)
    try:
        conn.execute("INSERT INTO widgets (name) VALUES ('keep me')")
        conn.commit()
    finally:
        conn.close()


def row_count(path):
    """How much survived."""
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM widgets").fetchone()[0]
    finally:
        conn.close()


def add_a_table(path, name):
    """A table the schema knows nothing about."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()


def test_a_database_that_matches_its_schema():
    """Nothing to say, which is the ordinary answer."""
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "test-drift.sqlite3")
    make(path, v2)

    assert schema.drift(v2, path) == [], "it: reports nothing when they agree"

    os.unlink(path)
    os.rmdir(directory)


def test_a_database_made_before_the_schema_grew(db_path):
    """The case the version cannot see."""
    make(db_path, v1)

    missing = schema.drift(v2, db_path)

    # describe: what is missing
    assert "gadgets" in missing, "it: names the table the schema declares"
    assert "idx_gadgets_widget_id" in missing, \
        "it: names an index on the table that is also missing"
    assert "idx_widgets_expr" in missing, \
        "it: and an index on a table the database already had"
    assert "widgets" not in missing, "it: leaves alone what is already there"
    assert missing == sorted(missing), "it: reads in a settled order"

    # SQLite backs a UNIQUE column with an index it names itself. It arrives
    # with the table, so naming it would report the same absence twice.
    assert "doodads" in missing, "it: names the table"
    assert not [m for m in missing if m.startswith("sqlite_")], \
        "it: and says nothing about the index SQLite made for it"


def test_a_database_that_has_more_than_the_schema(db_path):
    """A table the schema stopped declaring is left where it is."""
    make(db_path, v2)
    add_a_table(db_path, "leftovers")

    assert schema.drift(v2, db_path) == [], \
        "it: says nothing about a table nobody asks for — it answers no query"


def test_a_database_that_does_not_exist_yet(db_path):
    """First run. There is nothing to compare, and nothing wrong."""
    assert schema.drift(v2, db_path) == [], \
        "it: leaves a database that has yet to be created to be created"


def test_rebuilding(db_path):
    """Delete and create again, which is the answer while there are no migrations."""
    make(db_path, v1)
    seed_a_row(db_path)
    assert schema.drift(v2, db_path) != []

    # describe: rebuilding it
    schema.rebuild(v2, db_path)
    assert schema.drift(v2, db_path) == [], "it: matches the schema afterwards"

    assert row_count(db_path) == 0, \
        "it: carries no rows — this is a development database"


def test_rebuilding_a_database_that_does_not_exist(db_path):
    """First run reaches the same call, and creates the database."""
    schema.rebuild(v2, db_path)

    assert os.path.isfile(db_path), "it: creates it"
    assert schema.drift(v2, db_path) == []


def test_rebuilding_outside_development(db_path, monkeypatch):
    """A development tool, and a guard for the day it is wired somewhere else."""
    make(db_path, v1)
    seed_a_row(db_path)
    monkeypatch.setattr(schema, "_environment", lambda: schema.Environment.PROD)

    with pytest.raises(schema.NotDevelopment):
        schema.rebuild(v2, db_path)

    assert row_count(db_path) == 1, "it: leaves the row where it was"
    assert schema.drift(v2, db_path) != [], "it: still drifted, and still there"


def v3(conn):
    """`v2` plus seeds — the same tables, with rows in two of them.

    `doodads` is one `v1` never had, so a database made from `v1` is short a
    table *and* its seed. `drift` reports the first and this reports nothing
    about it: one absence, named once.
    """
    v2(conn)
    conn.execute("INSERT INTO widgets (name) VALUES ('shipped')")
    conn.execute("INSERT INTO doodads (code) VALUES ('shipped')")
    conn.commit()


def test_what_a_schema_seeds():
    """The tables a schema puts rows in, and how many."""
    assert schema.seeded(v3) == {"widgets": 1, "doodads": 1}, \
        "it: names only the tables it seeds, and a table it leaves empty is not one"


def test_a_database_made_before_a_seed(db_path):
    """A seed is rows, so the structure agrees while the contents do not."""
    make(db_path, v2)

    assert schema.drift(v3, db_path) == [], \
        "it: has every table and index the schema declares"
    assert schema.seed_drift(v3, db_path) == \
        ["doodads (0 of 1 seeded rows)", "widgets (0 of 1 seeded rows)"], \
        "it: and is short the rows the seed puts there"


def test_a_seed_on_a_table_the_database_lacks(db_path):
    """`drift` names the missing table. This says nothing more about it."""
    make(db_path, v1)

    assert "doodads" in schema.drift(v3, db_path), "it: is a missing table"
    assert schema.seed_drift(v3, db_path) == ["widgets (0 of 1 seeded rows)"], \
        "it: is left out here — one absence, reported once"


def test_a_seeded_table_somebody_has_added_to(db_path):
    """More rows than the seed is ordinary, and says nothing."""
    make(db_path, v3)
    seed_a_row(db_path)

    assert schema.seed_drift(v3, db_path) == [], \
        "it: only a shortfall means the seed never ran"


def test_a_database_that_does_not_exist_has_no_seed_drift(db_path):
    assert schema.seed_drift(v3, db_path) == []
    assert not os.path.isfile(db_path), \
        "it: leaves the file uncreated — a check makes no databases"


def test_a_column_that_changed(db_path):
    """Drift inside a definition, where every name still agrees.

    Adding a constraint to a column leaves the table list, the index list and
    the row counts identical. Comparing names alone calls that database
    current, and the constraint the code relies on is not in it.
    """
    schema.rebuild(v2, db_path)
    assert schema.drift(v2, db_path) == []

    drifted = schema.drift(v2_constrained, db_path)

    assert drifted == ["widgets (declared differently)"], \
        "it: names the table whose definition moved, and says which kind it is"

    # describe: rebuilding against the new declaration
    schema.rebuild(v2_constrained, db_path)
    assert schema.drift(v2_constrained, db_path) == []


def test_a_schema_written_out_differently(db_path):
    """The same declaration, reformatted."""
    schema.rebuild(v2, db_path)

    assert schema.drift(v2_spaced, db_path) == [], \
        "it: is not drift — indentation and a comment declare nothing"
