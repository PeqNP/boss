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
