#!/usr/bin/env python3
#
# Production — business rule tests
#
# Written before the implementation: these encode the rules agreed during the
# design interview and recorded in plan.md. Every one is expected to fail until
# Stage 4 fills in `lib.py`, `tokens.py`, and `csvimport.py`.
#
# State is built with `db.insert` rather than through `lib`, so a test exercises
# one rule against a known database rather than depending on rules that are
# themselves unimplemented.
#

import json
import logging
import pytest

from lib import configure_logging
from libtest import *

get_app_module("io.bithead.production")
from io.bithead.production import db, tokens, csvimport, export
from io.bithead.production.lib import *
from io.bithead.production import lib

logging.basicConfig(filename="unittests.log", encoding="utf-8", level=logging.INFO)

ADMIN = 1
OPERATOR = 4
OTHER_OPERATOR = 5


def fresh_database():
    """A database containing only the schema."""
    db.set_database_name("test-production.sqlite3")
    db.delete_database()
    db.start_database()


# --- Builders ------------------------------------------------------------
#
# Small helpers so a test reads as the situation it describes rather than a
# wall of inserts.

def make_pool(name="Test card", resources=None):
    pool_id = db.insert(
        "INSERT INTO pools (name, created_at, created_by) VALUES (?, datetime('now'), ?)",
        (name, ADMIN))
    for order, (rname, value) in enumerate(resources or [("Card 1", "12345")]):
        db.insert(
            "INSERT INTO pool_resources (pool_id, name, value, sort_order) VALUES (?, ?, ?, ?)",
            (pool_id, rname, value, order))
    return pool_id


def make_line(name="CR-One Reader", columns=("Location", "Group", "Asset"), pool_ids=()):
    line_id = db.insert(
        "INSERT INTO production_lines (name, created_at, created_by) VALUES (?, datetime('now'), ?)",
        (name, ADMIN))
    version_id = db.insert(
        "INSERT INTO production_line_versions (production_line_id, version, created_at)"
        " VALUES (?, 1, datetime('now'))", (line_id,))
    db.update("UPDATE production_lines SET current_version_id = ? WHERE id = ?",
              (version_id, line_id))
    for order, column in enumerate(columns):
        db.insert(
            "INSERT INTO production_line_columns (version_id, name, sort_order) VALUES (?, ?, ?)",
            (version_id, column, order))
    for order, pool_id in enumerate(pool_ids):
        row = db.select("SELECT name FROM pools WHERE id = ?", (pool_id,))[0]
        db.insert(
            "INSERT INTO production_line_pools (version_id, pool_id, pool_name, sort_order)"
            " VALUES (?, ?, ?, ?)", (version_id, pool_id, row["name"], order))
    return line_id, version_id


def make_operation(version_id, step, name, sections=()):
    operation_id = db.insert(
        "INSERT INTO operations (version_id, name, step) VALUES (?, ?, ?)",
        (version_id, name, step))
    for order, section in enumerate(sections):
        db.insert(
            "INSERT INTO operation_sections"
            " (operation_id, section_type, sort_order, name, label, required, body)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (operation_id, section.get("type"), order, section.get("name"),
             section.get("label"), 1 if section.get("required") else 0, section.get("body")))
    return operation_id


def make_job(line_id, version_id=None, name="July CR-One Run", active=0):
    return db.insert(
        "INSERT INTO jobs (name, production_line_id, version_id, scheduled_start,"
        " scheduled_completion, active, created_at, created_by)"
        " VALUES (?, ?, ?, '2026-07-06', '2026-08-14', ?, datetime('now'), ?)",
        (name, line_id, version_id, active, ADMIN))


def make_work_units(job_id, count=3):
    ids = []
    for row_order in range(1, count + 1):
        ids.append(db.insert(
            "INSERT INTO work_units (job_id, row_order, input_json) VALUES (?, ?, ?)",
            (job_id, row_order, json.dumps({"Location": f"Bay {row_order}",
                                            "Group": "Group A",
                                            "Asset": f"AST-99{row_order:02d}"}))))
    return ids


def make_job_line(job_id, user_id=OPERATOR, state="working"):
    return db.insert(
        "INSERT INTO job_lines (job_id, user_id, state, joined_at)"
        " VALUES (?, ?, ?, datetime('now'))", (job_id, user_id, state))


def state_of(table, row_id, column):
    return db.select(f"SELECT {column} FROM {table} WHERE id = ?", (row_id,))[0][column]


# --- Tokens --------------------------------------------------------------

def test_token_parse_and_render():
    context = {
        "workUnit": {"Location": "Bay 4", "Group": "Group A"},
        "pools": {"Test card": "67890"},
        "operations": {"1": {"serial": "CR1-00042"}, "2": {"led_ok": True, "empty": ""}}
    }

    # describe: parsing
    assert tokens.parse("{a.b} and {c.d}") == ["a.b", "c.d"], "it: returns every token, without braces"
    assert tokens.parse("nothing here") == [], "it: returns nothing when there are no tokens"
    assert tokens.parse(None) == [], "it: tolerates absent text"

    # describe: work unit tokens
    assert tokens.render("Assign to {work_unit.Location}", context) == "Assign to Bay 4"
    assert tokens.render("{work_unit.location}", context) == "Bay 4", \
        "it: matches a column name case-insensitively"

    # describe: operation tokens
    assert tokens.render("Serial {operation.1.serial}", context) == "Serial CR1-00042"

    # describe: pool tokens
    assert tokens.render("Expect {pool.Test card}", context) == "Expect 67890", \
        "it: resolves a pool name containing a space"
    assert tokens.render("{pool.test CARD}", context) == "67890", \
        "it: matches a pool name case-insensitively"

    # describe: rendering captured values
    assert tokens.render("{operation.2.led_ok}", context) == "Yes", \
        "it: renders a ticked checkbox as Yes"
    assert tokens.render_value(False) == "No"
    assert tokens.render_value(2) == "2"

    # describe: a key that exists but holds no value
    assert tokens.render("[{operation.2.empty}]", context) == "[]", \
        "it: renders an empty string, not the token"

    # describe: a key that does not exist
    assert tokens.render("{work_unit.Nope}", context) == "{work_unit.Nope}", \
        "it: leaves an unresolvable token exactly as written"
    assert tokens.render("{pool.Nope}", context) == "{pool.Nope}"
    assert tokens.render("{operation.9.serial}", context) == "{operation.9.serial}"
    assert tokens.render("{bogus.x}", context) == "{bogus.x}"
    assert tokens.render("{plain}", context) == "{plain}", \
        "it: ignores a token with no namespace"

    # describe: text with no tokens
    assert tokens.render("plain text", context) == "plain text"
    assert tokens.render(None, context) == "", "it: renders absent text as empty"


def test_line_validation():
    columns = ["Location", "Asset"]
    pools = ["Test card"]
    prior = {1: ["serial"], 2: ["result"]}

    # describe: every token resolves
    assert tokens.validate("Assign to {work_unit.Location}", 2, columns, pools, prior) == []
    assert tokens.validate("Expect {pool.Test card}", 2, columns, pools, prior) == []
    assert tokens.validate("Serial {operation.1.serial}", 2, columns, pools, prior) == [], \
        "it: accepts a backward reference"

    # describe: undeclared column
    errors = tokens.validate("{work_unit.Nope}", 2, columns, pools, prior)
    assert len(errors) == 1, "it: reports the offending token"
    assert errors[0].token == "work_unit.Nope"

    # describe: undeclared pool
    assert len(tokens.validate("{pool.Nope}", 2, columns, pools, prior)) == 1

    # describe: forward reference
    assert len(tokens.validate("{operation.3.x}", 2, columns, pools, prior)) == 1, \
        "it: rejects a reference to a later step"

    # describe: self reference
    assert len(tokens.validate("{operation.2.result}", 2, columns, pools, prior)) == 1, \
        "it: rejects a reference to its own step"

    # describe: unknown section on a valid step
    assert len(tokens.validate("{operation.1.nope}", 2, columns, pools, prior)) == 1


# --- Production line versioning ------------------------------------------

def test_versioning():
    fresh_database()
    line_id, version_id = make_line()
    make_operation(version_id, 1, "Scan reader",
                   [{"type": "text", "name": "serial", "label": "Serial", "required": True}])

    # describe: the version has never been started
    assert editable_version(line_id) == version_id, "it: edits in place"
    assert state_of("production_line_versions", version_id, "frozen") == 0

    # describe: a job starts against the version
    job_id = make_job(line_id)
    make_work_units(job_id, 1)
    start_job(ADMIN, job_id)
    assert state_of("production_line_versions", version_id, "frozen") == 1, \
        "it: freezes the version the job pinned"
    assert state_of("jobs", job_id, "version_id") == version_id

    # describe: editing a frozen version
    forked_id = editable_version(line_id)
    assert forked_id != version_id, "it: forks rather than mutating"
    assert state_of("production_line_versions", forked_id, "version") == 2
    assert state_of("production_lines", line_id, "current_version_id") == forked_id

    # describe: the fork is a deep copy
    original = db.select("SELECT name FROM production_line_columns WHERE version_id = ?"
                         " ORDER BY sort_order", (version_id,))
    copied = db.select("SELECT name FROM production_line_columns WHERE version_id = ?"
                       " ORDER BY sort_order", (forked_id,))
    assert [r["name"] for r in original] == [r["name"] for r in copied], \
        "it: carries the declared columns forward"
    old_ops = db.select("SELECT id FROM operations WHERE version_id = ?", (version_id,))
    new_ops = db.select("SELECT id FROM operations WHERE version_id = ?", (forked_id,))
    assert len(old_ops) == len(new_ops)
    assert {r["id"] for r in old_ops}.isdisjoint({r["id"] for r in new_ops}), \
        "it: gives the copies new ids, so a stale client must reload"

    # describe: the started job keeps what it pinned
    assert state_of("jobs", job_id, "version_id") == version_id, \
        "it: leaves a running job on the version it started with"

    # describe: deleting a line a job references
    with pytest.raises(Blocked):
        delete_production_line(ADMIN, line_id)


# --- CSV import ----------------------------------------------------------

def test_csv_import():
    fresh_database()
    line_id, version_id = make_line()
    job_id = make_job(line_id)
    columns = ["Location", "Group", "Asset"]

    valid = b"Location,Group,Asset\nBay 1,Group A,AST-9901\nBay 2,Group B,AST-9902\n"

    # describe: a valid file
    result = csvimport.preview(job_id, valid, columns)
    assert result.errors == []
    assert result.row_count == 2
    assert db.select("SELECT COUNT(*) c FROM work_units WHERE job_id = ?", (job_id,))[0]["c"] == 0, \
        "it: writes nothing until the upload is committed"

    # describe: committing
    assert csvimport.commit(job_id, result.upload_id) == 2
    rows = db.select("SELECT row_order, input_json FROM work_units WHERE job_id = ?"
                     " ORDER BY row_order", (job_id,))
    assert [r["row_order"] for r in rows] == [1, 2], "it: keeps the file's row order"
    assert json.loads(rows[0]["input_json"])["Location"] == "Bay 1"

    # describe: a column the line did not declare
    extra = b"Location,Group,Asset,PO Number\nBay 1,Group A,AST-9901,PO-2231\n"
    result = csvimport.preview(job_id, extra, columns)
    assert result.errors == [], "it: accepts columns beyond the contract"
    csvimport.commit(job_id, result.upload_id)
    stored = json.loads(db.select("SELECT input_json FROM work_units WHERE job_id = ?",
                                  (job_id,))[0]["input_json"])
    assert stored["PO Number"] == "PO-2231", "it: keeps them for the export"

    # describe: a missing declared column
    result = csvimport.preview(job_id, b"Location,Group\nBay 1,Group A\n", columns)
    assert any("Asset" in e["message"] for e in result.errors), "it: names the missing column"

    # describe: an empty value in a declared column
    result = csvimport.preview(job_id, b"Location,Group,Asset\nBay 1,,AST-9901\n", columns)
    assert len(result.errors) == 1
    assert result.errors[0]["line"] == 2, "it: names the offending line"

    # describe: duplicate rows
    dupes = b"Location,Group,Asset\nBay 1,Group A,AST-9901\nBay 1,Group A,AST-9901\n"
    assert len(csvimport.preview(job_id, dupes, columns).errors) >= 1

    # describe: a header-only file
    assert len(csvimport.preview(job_id, b"Location,Group,Asset\n", columns).errors) >= 1

    # describe: the job has already started
    db.update("UPDATE jobs SET version_id = ?, active = 1 WHERE id = ?", (version_id, job_id))
    with pytest.raises((Blocked, ValidationError)):
        csvimport.commit(job_id, csvimport.preview(job_id, valid, columns).upload_id)


# --- The work unit queue -------------------------------------------------

def test_work_unit_queue():
    fresh_database()
    line_id, version_id = make_line()
    job_id = make_job(line_id, version_id, active=1)
    units = make_work_units(job_id, 3)
    line = make_job_line(job_id)

    # describe: the first pull
    unit = pull_work_unit(OPERATOR, line)
    assert unit["id"] == units[0], "it: takes the lowest row order"
    assert state_of("work_units", units[0], "state") == "in_progress"
    assert state_of("work_units", units[0], "started_at") is not None
    assert state_of("work_units", units[0], "assigned_line_id") == line

    # describe: a released partial outranks an untouched unit
    db.update("UPDATE work_units SET assigned_line_id = NULL, state = 'pending' WHERE id = ?",
              (units[0],))
    other = make_job_line(job_id, OTHER_OPERATOR)
    assert pull_work_unit(OTHER_OPERATOR, other)["id"] == units[0], \
        "it: hands back the partially-worked unit before a fresh one"

    # describe: a requeued unit outranks a partial
    db.update("UPDATE work_units SET assigned_line_id = NULL, state = 'pending' WHERE id = ?",
              (units[0],))
    db.update("UPDATE work_units SET requeued_at = datetime('now'), state = 'pending' WHERE id = ?",
              (units[2],))
    assert pull_work_unit(OPERATOR, line)["id"] == units[2], "it: puts a requeue at the front"

    # describe: two operators pulling at once
    db.update("UPDATE work_units SET assigned_line_id = NULL, state = 'pending',"
              " requeued_at = NULL WHERE job_id = ?", (job_id,))
    first = pull_work_unit(OPERATOR, line)
    second = pull_work_unit(OTHER_OPERATOR, other)
    assert first["id"] != second["id"], "it: never hands the same unit to two lines"

    # describe: nothing available
    db.update("UPDATE work_units SET state = 'complete', assigned_line_id = NULL WHERE job_id = ?",
              (job_id,))
    assert pull_work_unit(OPERATOR, line) is None, "it: returns nothing rather than raising"

    # describe: the job is not active
    db.update("UPDATE work_units SET state = 'pending' WHERE job_id = ?", (job_id,))
    db.update("UPDATE jobs SET active = 0 WHERE id = ?", (job_id,))
    with pytest.raises(Blocked):
        pull_work_unit(OPERATOR, line)


# --- Completing an operation ---------------------------------------------

def test_operation_completion():
    fresh_database()
    pool_id = make_pool()
    line_id, version_id = make_line(pool_ids=[pool_id])
    make_operation(version_id, 1, "Scan",
                   [{"type": "text", "name": "serial", "label": "Serial", "required": True}])
    make_operation(version_id, 2, "Check",
                   [{"type": "checkbox", "name": "led_ok", "label": "LED", "required": True}])
    job_id = make_job(line_id, version_id, active=1)
    unit = make_work_units(job_id, 1)[0]
    line = make_job_line(job_id)
    db.update("UPDATE work_units SET assigned_line_id = ?, state = 'in_progress' WHERE id = ?",
              (line, unit))

    # describe: a required text section left blank
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 1, {"serial": ""}, "")

    # describe: every required section present
    result = complete_operation(OPERATOR, unit, 1, {"serial": "CR1-00042"}, "Second attempt")
    assert result["nextStep"] == 2
    assert result["unitComplete"] is False
    assert state_of("work_units", unit, "current_step") == 2

    # describe: what was captured
    value = db.select("SELECT value FROM work_unit_values WHERE work_unit_id = ? AND step = 1"
                      " AND name = 'serial'", (unit,))
    assert value[0]["value"] == "CR1-00042", "it: stores one row per named section"
    op = db.select("SELECT * FROM work_unit_operations WHERE work_unit_id = ? AND step = 1",
                   (unit,))[0]
    assert op["state"] == "complete"
    assert op["completed_by"] == OPERATOR
    assert op["completed_at"] is not None
    assert op["notes"] == "Second attempt"

    # describe: a required checkbox left unticked
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 2, {"led_ok": False}, "")

    # describe: completing out of order
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 1, {"serial": "X"}, "")

    # describe: the last step
    result = complete_operation(OPERATOR, unit, 2, {"led_ok": True}, "")
    assert result["unitComplete"] is True
    assert state_of("work_units", unit, "state") == "complete"
    assert state_of("work_units", unit, "completed_at") is not None
    assert state_of("job_lines", line, "units_completed") == 1
    resources = db.select("SELECT * FROM work_unit_resources WHERE work_unit_id = ?", (unit,))
    assert len(resources) == 1, "it: snapshots the resources the line held"
    assert resources[0]["resource_value"] == "12345", \
        "it: copies the value so a later edit cannot rewrite history"


def test_operation_edit():
    fresh_database()
    line_id, version_id = make_line()
    for step in range(1, 6):
        make_operation(version_id, step, f"Step {step}",
                       [{"type": "text", "name": f"v{step}", "label": "V"}])
    job_id = make_job(line_id, version_id, active=1)
    unit = make_work_units(job_id, 1)[0]
    line = make_job_line(job_id)
    db.update("UPDATE work_units SET assigned_line_id = ?, state = 'in_progress',"
              " current_step = 6 WHERE id = ?", (line, unit))
    for step in range(1, 6):
        db.insert("INSERT INTO work_unit_operations (work_unit_id, step, state, completed_at,"
                  " completed_by) VALUES (?, ?, 'complete', datetime('now'), ?)",
                  (unit, step, OPERATOR))
        db.insert("INSERT INTO work_unit_values (work_unit_id, step, name, value)"
                  " VALUES (?, ?, ?, ?)", (unit, step, f"v{step}", "original"))

    # describe: editing step 2 of 5
    result = edit_operation(OPERATOR, unit, 2, {"v2": "corrected"}, "")
    assert result["stepsReset"] == 3, "it: resets every later step"
    later = db.select("SELECT state FROM work_unit_operations WHERE work_unit_id = ? AND step > 2",
                      (unit,))
    assert all(r["state"] == "pending" for r in later)
    assert state_of("work_units", unit, "current_step") == 3, \
        "it: returns the operator to the first step that is now incomplete"

    # describe: the correction is recorded
    edit = db.select("SELECT * FROM work_unit_edits WHERE work_unit_id = ?", (unit,))[0]
    assert edit["old_value"] == "original"
    assert edit["new_value"] == "corrected"
    assert edit["edited_by"] == OPERATOR
    assert edit["steps_reset"] == 3

    # describe: values already captured downstream
    kept = db.select("SELECT value FROM work_unit_values WHERE work_unit_id = ? AND step = 4",
                     (unit,))
    assert kept[0]["value"] == "original", \
        "it: keeps what was captured, so re-completing shows the previous entry"

    # describe: editing the last completed step
    db.update("UPDATE work_unit_operations SET state = 'complete' WHERE work_unit_id = ?", (unit,))
    assert edit_operation(OPERATOR, unit, 5, {"v5": "x"}, "")["stepsReset"] == 0

    # describe: editing a unit that is finished
    db.update("UPDATE work_units SET state = 'complete' WHERE id = ?", (unit,))
    with pytest.raises(Blocked):
        edit_operation(OPERATOR, unit, 1, {"v1": "y"}, "")


def test_fail_and_requeue():
    fresh_database()
    line_id, version_id = make_line()
    make_operation(version_id, 1, "Scan")
    job_id = make_job(line_id, version_id, active=1)
    units = make_work_units(job_id, 2)
    line = make_job_line(job_id)
    db.update("UPDATE work_units SET assigned_line_id = ?, state = 'in_progress' WHERE id = ?",
              (line, units[0]))

    # describe: failing without notes
    with pytest.raises(ValidationError):
        fail_operation(OPERATOR, units[0], 1, {}, "")

    # describe: failing with notes
    fail_operation(OPERATOR, units[0], 1, {}, "Reader will not power on")
    assert state_of("work_units", units[0], "state") == "failed"
    assert state_of("work_units", units[0], "failed_step") == 1
    assert state_of("work_units", units[0], "failed_at") is not None
    assert state_of("job_lines", line, "units_failed") == 1

    # describe: a failed unit leaves the queue
    assert pull_work_unit(OPERATOR, line)["id"] == units[1], \
        "it: is never handed to another operator"

    # describe: requeueing
    result = requeue_work_unit(ADMIN, units[0])
    assert state_of("work_units", units[0], "state") == "pending"
    assert state_of("work_units", units[0], "requeued_at") is not None
    assert state_of("work_units", units[0], "failed_at") is None
    assert db.select("SELECT COUNT(*) c FROM work_unit_operations WHERE work_unit_id = ?"
                     " AND state = 'complete'", (units[0],))[0]["c"] == 0, \
        "it: clears the progress it had"

    # describe: requeueing onto a finished job
    db.update("UPDATE work_units SET state = 'complete' WHERE job_id = ?", (job_id,))
    db.update("UPDATE work_units SET state = 'failed' WHERE id = ?", (units[1],))
    db.update("UPDATE jobs SET active = 0 WHERE id = ?", (job_id,))
    result = requeue_work_unit(ADMIN, units[1])
    assert result["jobReactivated"] is True
    assert state_of("jobs", job_id, "active") == 1

    # describe: requeueing a unit that has not failed
    db.update("UPDATE work_units SET state = 'complete' WHERE id = ?", (units[0],))
    with pytest.raises(Blocked):
        requeue_work_unit(ADMIN, units[0])


# --- Pools ---------------------------------------------------------------

def test_pool_checkout():
    fresh_database()
    pool_id = make_pool(resources=[("Card 1", "12345"), ("Card 2", "67890")])
    line_id, version_id = make_line(pool_ids=[pool_id])
    make_operation(version_id, 1, "Scan")
    job_id = make_job(line_id, version_id, active=1)
    make_work_units(job_id, 2)
    card1, card2 = [r["id"] for r in db.select(
        "SELECT id FROM pool_resources WHERE pool_id = ? ORDER BY sort_order", (pool_id,))]

    # describe: joining with a required pool
    result = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card1}])
    line = result["lineId"]
    assert state_of("pool_resources", card1, "held_by_line_id") == line
    assert db.select("SELECT COUNT(*) c FROM job_line_resources WHERE line_id = ?",
                     (line,))[0]["c"] == 1

    # describe: a resource another line already holds
    with pytest.raises(Blocked):
        join_line(OTHER_OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card1}])

    # describe: a resource that is out of service
    db.update("UPDATE pool_resources SET in_service = 0 WHERE id = ?", (card2,))
    with pytest.raises(Blocked):
        join_line(OTHER_OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card2}])
    db.update("UPDATE pool_resources SET in_service = 1 WHERE id = ?", (card2,))

    # describe: a required pool left unchosen
    with pytest.raises((Blocked, ValidationError)):
        join_line(OTHER_OPERATOR, job_id, [])

    # describe: leaving the line
    leave_line(OPERATOR, line)
    assert state_of("pool_resources", card1, "held_by_line_id") is None, \
        "it: returns every resource the line held"
    assert state_of("job_lines", line, "state") == "left"
    assert db.select("SELECT COUNT(*) c FROM job_lines WHERE id = ?", (line,))[0]["c"] == 1, \
        "it: keeps the line record, which carries the operator's metrics"

    # describe: forcing a resource back
    other = join_line(OTHER_OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card2}])["lineId"]
    return_resource(ADMIN, card2)
    assert state_of("pool_resources", card2, "held_by_line_id") is None
    assert state_of("job_lines", other, "state") != "left", \
        "it: frees the resource without ending the line"


def test_pool_rules():
    fresh_database()
    unused = make_pool("Printer")
    used = make_pool("Test card")
    line_id, version_id = make_line(pool_ids=[used])

    # describe: renaming a pool nothing references
    rename_pool(ADMIN, unused, "Label printer")
    assert db.select("SELECT name FROM pools WHERE id = ?", (unused,))[0]["name"] == "Label printer"

    # describe: renaming a pool the current version requires
    with pytest.raises(Blocked) as raised:
        rename_pool(ADMIN, used, "Cards")
    assert raised.value.blockers, "it: names what stands in the way"

    # describe: renaming a pool only a historical version requires
    forked = editable_version(line_id)
    db.update("DELETE FROM production_line_pools WHERE version_id = ?", (forked,))
    # it: keeps history renderable by refusing the rename
    with pytest.raises(Blocked):
        rename_pool(ADMIN, used, "Cards")

    # describe: a duplicate name, differing only by case
    with pytest.raises((Blocked, ValidationError)):
        rename_pool(ADMIN, unused, "test card")

    # describe: deleting a pool with a resource checked out
    job_id = make_job(line_id, version_id, active=1)
    line = make_job_line(job_id)
    resource = db.select("SELECT id FROM pool_resources WHERE pool_id = ?", (unused,))[0]["id"]
    db.update("UPDATE pool_resources SET held_by_line_id = ? WHERE id = ?", (line, resource))
    with pytest.raises(Blocked):
        delete_pool(ADMIN, unused)

    # describe: deleting a pool nothing references
    db.update("UPDATE pool_resources SET held_by_line_id = NULL WHERE id = ?", (resource,))
    delete_pool(ADMIN, unused)
    assert db.select("SELECT COUNT(*) c FROM pool_resources WHERE pool_id = ?",
                     (unused,))[0]["c"] == 0, "it: takes the pool's resources with it"


# --- Job lifecycle -------------------------------------------------------

def test_job_lifecycle():
    fresh_database()
    line_id, version_id = make_line()
    make_operation(version_id, 1, "Scan")

    # describe: starting a job with no work units
    empty = make_job(line_id)
    with pytest.raises(Blocked):
        start_job(ADMIN, empty)

    # describe: starting a job whose line has no operations
    bare_line_id, bare_version_id = make_line("Empty line")
    bare = make_job(bare_line_id)
    make_work_units(bare, 1)
    with pytest.raises(Blocked):
        start_job(ADMIN, bare)

    # describe: starting
    job_id = make_job(line_id)
    units = make_work_units(job_id, 2)
    start_job(ADMIN, job_id)
    assert state_of("jobs", job_id, "active") == 1
    assert state_of("jobs", job_id, "version_id") == version_id

    # describe: stopping with operators on lines
    line = make_job_line(job_id)
    result = stop_job(ADMIN, job_id)
    assert state_of("jobs", job_id, "active") == 0
    assert result["operatorsPaused"] == 1
    assert state_of("job_lines", line, "state") == "paused"
    assert state_of("job_lines", line, "pause_origin") == "admin"

    # describe: starting again
    start_job(ADMIN, job_id)
    assert state_of("job_lines", line, "state") == "working", \
        "it: clears the pause the manager raised"

    # describe: an operator's own pause survives a restart
    set_line_state(OPERATOR, line, "paused", "operator")
    stop_job(ADMIN, job_id)
    start_job(ADMIN, job_id)
    assert state_of("job_lines", line, "state") == "paused", \
        "it: leaves an operator who chose to break on break"

    # describe: the last unit resolves
    db.update("UPDATE work_units SET state = 'complete' WHERE job_id = ?", (job_id,))
    assert maybe_deactivate_job(job_id) is True
    assert state_of("jobs", job_id, "active") == 0

    # describe: failures count as resolved
    db.update("UPDATE jobs SET active = 1 WHERE id = ?", (job_id,))
    db.update("UPDATE work_units SET state = 'failed' WHERE id = ?", (units[0],))
    assert maybe_deactivate_job(job_id) is True, \
        "it: finishes a job whose remaining units all failed"

    # describe: deleting a job that has completed units
    with pytest.raises(Blocked):
        lib.delete_job(ADMIN, job_id)

    # describe: deleting an untouched job
    lib.delete_job(ADMIN, empty)
    assert db.select("SELECT COUNT(*) c FROM jobs WHERE id = ?", (empty,))[0]["c"] == 0

    # describe: a completion date before the start date
    with pytest.raises(ValidationError):
        lib.save_job(ADMIN, None, "Backwards", line_id, "2026-08-14", "2026-07-06")


def test_line_state():
    fresh_database()
    pool_id = make_pool()
    line_id, version_id = make_line(pool_ids=[pool_id])
    make_operation(version_id, 1, "Scan")
    job_id = make_job(line_id, version_id, active=1)
    make_work_units(job_id, 2)
    resource = db.select("SELECT id FROM pool_resources WHERE pool_id = ?", (pool_id,))[0]["id"]

    # describe: joining
    line = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": resource}])["lineId"]
    assert state_of("job_lines", line, "state") == "working"
    assert db.select("SELECT COUNT(*) c FROM line_events WHERE line_id = ? AND event_type = 'join'",
                     (line,))[0]["c"] == 1

    # describe: joining a second job while holding a line
    other_job = make_job(line_id, version_id, "Second run", active=1)
    make_work_units(other_job, 1)
    with pytest.raises(Blocked):
        join_line(OPERATOR, other_job, [])

    # describe: an operator raising the andon
    set_line_state(OPERATOR, line, "stopped", "operator", "Reader will not power on")
    assert state_of("job_lines", line, "state") == "stopped"
    assert state_of("job_lines", line, "stop_origin") == "operator"
    assert state_of("job_lines", line, "stop_reason") == "Reader will not power on"
    open_events = db.select("SELECT * FROM line_events WHERE line_id = ? AND event_type = 'stop'"
                            " AND ended_at IS NULL", (line,))
    assert len(open_events) == 1, "it: opens an interval so blocked time can be measured"

    # describe: the operator clearing their own andon
    set_line_state(OPERATOR, line, "working", "operator")
    assert state_of("job_lines", line, "state") == "working"
    assert db.select("SELECT COUNT(*) c FROM line_events WHERE line_id = ?"
                     " AND event_type = 'stop' AND ended_at IS NULL", (line,))[0]["c"] == 0, \
        "it: closes the interval"

    # describe: an operator clearing a manager's stop
    set_line_state(ADMIN, line, "stopped", "admin")
    with pytest.raises(Blocked):
        set_line_state(OPERATOR, line, "working", "operator")

    # describe: the manager clearing it
    set_line_state(ADMIN, line, "working", "admin")
    assert state_of("job_lines", line, "state") == "working"

    # describe: closing the window
    set_line_state(OPERATOR, line, "paused", "window")
    assert state_of("job_lines", line, "pause_origin") == "window"
    assert state_of("pool_resources", resource, "held_by_line_id") == line, \
        "it: keeps the resources so the operator resumes where they left off"

    # describe: rejoining after leaving
    leave_line(OPERATOR, line)
    rejoined = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": resource}])
    assert rejoined["lineId"] == line, "it: reuses the same permanent line record"


# --- Throughput and export -----------------------------------------------

def test_throughput():
    fresh_database()
    line_id, version_id = make_line()
    job_id = make_job(line_id, version_id, active=1)
    units = make_work_units(job_id, 4)

    # describe: nothing completed in the window
    result = job_throughput(job_id, window_minutes=60)
    assert result["unitsPerHour"] is None
    assert result["avgCycleSeconds"] is None

    # describe: units inside and outside the window
    db.update("UPDATE work_units SET state = 'complete', started_at = datetime('now', '-70 minutes'),"
              " completed_at = datetime('now', '-65 minutes') WHERE id = ?", (units[0],))
    for unit in units[1:3]:
        db.update("UPDATE work_units SET state = 'complete',"
                  " started_at = datetime('now', '-20 minutes'),"
                  " completed_at = datetime('now', '-10 minutes') WHERE id = ?", (unit,))
    result = job_throughput(job_id, window_minutes=60)
    assert result["unitsInWindow"] == 2, "it: counts only what completed inside the window"

    # describe: scaling to the hour
    assert result["unitsPerHour"] == pytest.approx(2.0, abs=0.01)
    assert job_throughput(job_id, window_minutes=30)["unitsPerHour"] == pytest.approx(4.0, abs=0.01)

    # describe: cycle time
    assert result["avgCycleSeconds"] == pytest.approx(600, abs=5), \
        "it: averages completed_at minus started_at"

    # describe: a blocked interval overlapping a unit
    line = make_job_line(job_id)
    db.update("UPDATE work_units SET assigned_line_id = ? WHERE id = ?", (line, units[1]))
    db.insert("INSERT INTO line_events (line_id, event_type, started_at, ended_at)"
              " VALUES (?, 'pause', datetime('now', '-18 minutes'), datetime('now', '-13 minutes'))",
              (line,))
    blocked = job_throughput(job_id, window_minutes=60)
    assert blocked["avgCycleSeconds"] < result["avgCycleSeconds"], \
        "it: subtracts time the line was blocked"


def test_export():
    fresh_database()
    pool_id = make_pool()
    line_id, version_id = make_line(pool_ids=[pool_id])
    make_operation(version_id, 1, "Scan",
                   [{"type": "text", "name": "serial", "label": "Serial"}])
    job_id = make_job(line_id, version_id, active=1)

    # describe: a job with no work units
    csv = export.work_units_csv(job_id)
    assert len(csv.strip().splitlines()) == 1, "it: writes the header row and nothing else"

    # describe: headers
    unit = make_work_units(job_id, 1)[0]
    header = export.work_units_csv(job_id).splitlines()[0]
    for column in ("Location", "Group", "Asset", "state", "1.serial"):
        assert column in header, f"it: includes {column}"

    # describe: one row per work unit
    make_work_units(job_id, 2)
    assert len(export.work_units_csv(job_id).strip().splitlines()) == 4, \
        "it: writes a header and one row per unit"

    # describe: a failed unit
    db.update("UPDATE work_units SET state = 'failed', failed_step = 1 WHERE id = ?", (unit,))
    rows = [r for r in export.work_units_csv(job_id).splitlines() if "failed" in r]
    assert len(rows) == 1, "it: reports the state, leaving incomplete steps blank"
