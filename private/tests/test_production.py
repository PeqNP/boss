#!/usr/bin/env python3
#
# Production — business rule tests
#
# Black box. A test builds its situation and checks its outcome through the
# same interface the client uses: it starts jobs, joins lines, pulls units and
# completes steps, then reads back the same shapes the screens read. No test
# knows how anything is stored.
#
# That is deliberate. A test written against columns passes when the data is
# right, which is not the same as passing when the *user's* action works — and
# it breaks whenever the schema moves, even though nothing a user can see has
# changed. Written this way, a passing test is evidence that an operator can
# do the thing, and the implementation stays free to change underneath.
#
# The single exception is the pair of time-travel helpers below.
#

import pytest

from lib import configure_logging
from libtest import *

get_app_module("io.bithead.production")
from io.bithead.production import db, tokens, csvimport, export
from io.bithead.production.lib import *
from io.bithead.production import lib

ADMIN = 1
OPERATOR = 4
OTHER_OPERATOR = 5
THIRD_OPERATOR = 6


def fresh_database():
    """A database containing only the schema.

    The one thing a test may know about storage is that there *is* some, and
    that it can be emptied. It never looks inside.
    """
    db.set_database_name("test-production.sqlite3")
    db.delete_database()
    db.start_database()


# --- The exception -------------------------------------------------------
#
# Throughput is a claim about the past: units finished 65 minutes ago, a line
# blocked between two earlier moments. Nothing in the interface can make a
# past — an operator can only work now — so `test_throughput` reaches into
# storage to move recorded times backwards.
#
# These two functions are the only place in this file that knows how anything
# is stored. They exist so the rules that depend on elapsed time can be tested
# at all, and nothing else uses them.

def backdate_work_unit(work_unit_id, started, completed):
    """Move a finished unit's timestamps that many minutes into the past."""
    db.update("UPDATE work_units SET started_at = datetime('now', ?),"
              " completed_at = datetime('now', ?) WHERE id = ?",
              (f"-{started} minutes", f"-{completed} minutes", work_unit_id))


def backdate_block(line_id, started, ended):
    """Record a past interval during which a line could not work."""
    db.insert("INSERT INTO line_events (line_id, event_type, started_at, ended_at)"
              " VALUES (?, 'pause', datetime('now', ?), datetime('now', ?))",
              (line_id, f"-{started} minutes", f"-{ended} minutes"))


# --- Building a situation ------------------------------------------------
#
# Everything below goes through the same calls the admin screens make, so a
# test reads as the situation it describes.

def text(name, label="Value", required=False):
    return {"type": "text", "name": name, "label": label, "required": required}


def checkbox(name, label="Confirm", required=False):
    return {"type": "checkbox", "name": name, "label": label, "required": required}


def a_pool(name="Test card", resources=(("Card 1", "12345"),)):
    pool_id = save_pool(ADMIN, None, name).poolId
    for resource_name, value in resources:
        save_resource(ADMIN, pool_id, None, resource_name, value)
    return pool_id


def a_production_line(name="CR-One Reader", columns=("Location", "Group", "Asset"),
                      pools=(), operations=(("Scan reader", ()),)):
    line_id = save_production_line(ADMIN, None, name, list(columns), list(pools)).lineId
    for operation_name, sections in operations:
        operation_id = add_operation(ADMIN, line_id, operation_name).operationId
        for section in sections:
            add_section(ADMIN, operation_id, section["type"], name=section.get("name"),
                        label=section.get("label"), required=section.get("required", False),
                        body=section.get("body"))
    return line_id


def a_job(line_id, name="July CR-One Run", units=2):
    job_id = save_job(ADMIN, None, name, line_id, "2026-07-06", "2026-08-14").jobId
    if units:
        add_work_units(job_id, units)
    return job_id


def add_work_units(job_id, count=3):
    """Import work units the way an admin does: preview a CSV, then commit it."""
    columns = get_job_detail(job_id).contract.columns
    lines = [",".join(columns)]
    for row in range(1, count + 1):
        lines.append(",".join(f"{column} {row}" for column in columns))

    preview = csvimport.preview(job_id, ("\n".join(lines) + "\n").encode(), columns)
    assert preview.errors == [], preview.errors
    csvimport.commit(job_id, preview.uploadId)
    return [unit.id for unit in list_work_units(job_id)]


def unit_ids(job_id):
    return [unit.id for unit in list_work_units(job_id)]


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
    line_id = a_production_line(
        operations=[("Scan reader", [text("serial", "Serial", required=True)])])
    original = get_production_line_detail(line_id)

    # describe: the version has never been started
    assert original.frozen is False
    assert save_production_line(ADMIN, line_id, "CR-One Reader",
                                ["Location", "Group", "Asset"], []).forked is False, \
        "it: edits in place"

    # describe: a job starts against the version
    job_id = a_job(line_id, units=1)
    start_job(ADMIN, job_id)
    assert get_production_line_detail(line_id).frozen is True, \
        "it: freezes the version the job pinned"
    assert get_job_detail(job_id).versionId == original.versionId

    # describe: editing a frozen version
    edited = save_production_line(ADMIN, line_id, "CR-One Reader",
                                  ["Location", "Group", "Asset"], [])
    assert edited.forked is True, "it: forks rather than mutating"
    forked = get_production_line_detail(line_id)
    assert forked.version == 2
    assert forked.versionId != original.versionId
    assert forked.frozen is False, "it: leaves the new version editable"

    # describe: the fork is a deep copy
    assert [column.name for column in forked.columns] == \
           [column.name for column in original.columns], \
        "it: carries the declared columns forward"
    assert len(forked.operations) == len(original.operations)
    assert {operation.id for operation in forked.operations}.isdisjoint(
           {operation.id for operation in original.operations}), \
        "it: gives the copies new ids, so a stale client must reload"

    # describe: the started job keeps what it pinned
    assert get_job_detail(job_id).versionId == original.versionId, \
        "it: leaves a running job on the version it started with"

    # describe: deleting a line a job references
    with pytest.raises(Blocked):
        delete_production_line(ADMIN, line_id)


# --- CSV import ----------------------------------------------------------

def test_csv_import():
    fresh_database()
    line_id = a_production_line()
    job_id = a_job(line_id, units=0)
    columns = ["Location", "Group", "Asset"]

    valid = b"Location,Group,Asset\nBay 1,Group A,AST-9901\nBay 2,Group B,AST-9902\n"

    # describe: a valid file
    result = csvimport.preview(job_id, valid, columns)
    assert result.errors == []
    assert result.rowCount == 2
    assert list_work_units(job_id) == [], "it: writes nothing until the upload is committed"

    # describe: committing
    assert csvimport.commit(job_id, result.uploadId) == 2
    units = list_work_units(job_id)
    assert [unit.rowOrder for unit in units] == [1, 2], "it: keeps the file's row order"
    assert units[0].input["Location"] == "Bay 1"

    # describe: a column the line did not declare
    extra = b"Location,Group,Asset,PO Number\nBay 1,Group A,AST-9901,PO-2231\n"
    result = csvimport.preview(job_id, extra, columns)
    assert result.errors == [], "it: accepts columns beyond the contract"
    csvimport.commit(job_id, result.uploadId)
    assert list_work_units(job_id)[0].input["PO Number"] == "PO-2231", \
        "it: keeps them for the export"

    # describe: a missing declared column
    result = csvimport.preview(job_id, b"Location,Group\nBay 1,Group A\n", columns)
    assert any("Asset" in error.message for error in result.errors), \
        "it: names the missing column"

    # describe: an empty value in a declared column
    result = csvimport.preview(job_id, b"Location,Group,Asset\nBay 1,,AST-9901\n", columns)
    assert len(result.errors) == 1
    assert result.errors[0].line == 2, "it: names the offending line"

    # describe: duplicate rows
    dupes = b"Location,Group,Asset\nBay 1,Group A,AST-9901\nBay 1,Group A,AST-9901\n"
    assert len(csvimport.preview(job_id, dupes, columns).errors) >= 1

    # describe: a header-only file
    assert len(csvimport.preview(job_id, b"Location,Group,Asset\n", columns).errors) >= 1

    # describe: the job has already started
    start_job(ADMIN, job_id)
    with pytest.raises((Blocked, ValidationError)):
        csvimport.commit(job_id, csvimport.preview(job_id, valid, columns).uploadId)


# --- The work unit queue -------------------------------------------------

def test_work_unit_queue():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", ())])
    job_id = a_job(line_id, units=3)
    start_job(ADMIN, job_id)
    units = unit_ids(job_id)
    mine = join_line(OPERATOR, job_id, []).lineId

    # describe: the first pull
    assert pull_work_unit(OPERATOR, mine).id == units[0], "it: takes the lowest row order"
    held = get_work_unit_detail(units[0])
    assert held.state == "in_progress"
    assert held.startedAt is not None
    assert held.lineId == mine

    # describe: two operators pulling
    theirs = join_line(OTHER_OPERATOR, job_id, []).lineId
    assert pull_work_unit(OTHER_OPERATOR, theirs).id == units[1], \
        "it: never hands the same unit to two lines"

    # describe: a released partial outranks an untouched unit
    leave_line(OPERATOR, mine)
    mine = join_line(OPERATOR, job_id, []).lineId
    assert pull_work_unit(OPERATOR, mine).id == units[0], \
        "it: hands back the partially-worked unit before a fresh one"

    # describe: a requeued unit outranks a partial
    fail_operation(OTHER_OPERATOR, units[1], 1, {}, "Reader will not power on")
    requeue_work_unit(ADMIN, units[1])
    leave_line(OPERATOR, mine)
    mine = join_line(OPERATOR, job_id, []).lineId
    assert pull_work_unit(OPERATOR, mine).id == units[1], "it: puts a requeue at the front"

    # describe: nothing left to hand out
    assert pull_work_unit(OTHER_OPERATOR, theirs).id == units[0]
    third = join_line(THIRD_OPERATOR, job_id, []).lineId
    assert pull_work_unit(THIRD_OPERATOR, third).id == units[2]
    assert pull_work_unit(THIRD_OPERATOR, third) is None, \
        "it: returns nothing rather than raising"

    # describe: the job is not running
    stop_job(ADMIN, job_id)
    with pytest.raises(Blocked):
        pull_work_unit(OPERATOR, mine)


# --- Completing an operation ---------------------------------------------

def test_operation_completion():
    fresh_database()
    pool_id = a_pool()
    line_id = a_production_line(pools=[pool_id], operations=[
        ("Scan", [text("serial", "Serial", required=True)]),
        ("Check", [checkbox("led_ok", "LED", required=True)]),
    ])
    job_id = a_job(line_id, units=1)
    start_job(ADMIN, job_id)
    card = get_pool_detail(pool_id).resources[0].id
    line = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card}]).lineId
    unit = pull_work_unit(OPERATOR, line).id

    # describe: a required text section left blank
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 1, {"serial": ""}, "")

    # describe: every required section present
    result = complete_operation(OPERATOR, unit, 1, {"serial": "CR1-00042"}, "Second attempt")
    assert result.nextStep == 2
    assert result.unitComplete is False
    assert get_work_unit_detail(unit).currentStep == 2

    # describe: what was captured
    step_one = get_work_unit_detail(unit).operations[0]
    assert step_one.values["serial"] == "CR1-00042", "it: records the value under its name"
    assert step_one.state == "complete"
    assert step_one.completedBy == OPERATOR
    assert step_one.completedAt is not None
    assert step_one.notes == "Second attempt"

    # describe: a required checkbox left unticked
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 2, {"led_ok": False}, "")

    # describe: completing out of order
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 1, {"serial": "X"}, "")

    # describe: the last step
    result = complete_operation(OPERATOR, unit, 2, {"led_ok": True}, "")
    assert result.unitComplete is True
    finished = get_work_unit_detail(unit)
    assert finished.state == "complete"
    assert finished.completedAt is not None
    assert get_line_detail(line).unitsCompleted == 1
    assert [(r.pool, r.resource, r.value) for r in finished.resources] == \
        [("Test card", "Card 1", "12345")], \
        "it: snapshots what the line held, copied so a later edit cannot rewrite history"


def test_operation_edit():
    fresh_database()
    line_id = a_production_line(operations=[
        (f"Step {step}", [text(f"v{step}")]) for step in range(1, 6)])
    job_id = a_job(line_id, units=1)
    start_job(ADMIN, job_id)
    line = join_line(OPERATOR, job_id, []).lineId
    unit = pull_work_unit(OPERATOR, line).id
    for step in range(1, 5):
        complete_operation(OPERATOR, unit, step, {f"v{step}": "original"}, "")

    # describe: editing step 2 of the four that are done
    assert edit_operation(OPERATOR, unit, 2, {"v2": "corrected"}, "").stepsReset == 2, \
        "it: resets every later step"
    detail = get_work_unit_detail(unit)
    assert [operation.state for operation in detail.operations] == \
        ["complete", "complete", "pending", "pending", "pending"]
    assert detail.currentStep == 3, \
        "it: returns the operator to the first step that is now incomplete"

    # describe: the correction is recorded
    edit = detail.edits[0]
    assert edit.oldValue == "original"
    assert edit.newValue == "corrected"
    assert edit.editedBy == OPERATOR
    assert edit.stepsReset == 2

    # describe: values already captured downstream
    assert detail.operations[3].values["v4"] == "original", \
        "it: keeps what was captured, so re-completing shows the previous entry"

    # describe: editing when nothing later has been done
    assert edit_operation(OPERATOR, unit, 2, {"v2": "again"}, "").stepsReset == 0, \
        "it: resets nothing"

    # describe: editing a unit that is finished
    for step in range(3, 6):
        complete_operation(OPERATOR, unit, step, {f"v{step}": "x"}, "")
    assert get_work_unit_detail(unit).state == "complete"
    with pytest.raises(Blocked):
        edit_operation(OPERATOR, unit, 1, {"v1": "y"}, "")


def test_fail_and_requeue():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", ())])
    job_id = a_job(line_id, units=2)
    start_job(ADMIN, job_id)
    units = unit_ids(job_id)
    line = join_line(OPERATOR, job_id, []).lineId
    pull_work_unit(OPERATOR, line)

    # describe: failing without notes
    with pytest.raises(ValidationError):
        fail_operation(OPERATOR, units[0], 1, {}, "")

    # describe: failing with notes
    fail_operation(OPERATOR, units[0], 1, {}, "Reader will not power on")
    failed = get_work_unit_detail(units[0])
    assert failed.state == "failed"
    assert failed.failedStep == 1
    assert failed.failedAt is not None
    assert get_line_detail(line).unitsFailed == 1

    # describe: a failed unit leaves the queue
    assert pull_work_unit(OPERATOR, line).id == units[1], \
        "it: is never handed to another operator"

    # describe: requeueing
    requeue_work_unit(ADMIN, units[0])
    requeued = get_work_unit_detail(units[0])
    assert requeued.state == "pending"
    assert requeued.requeuedAt is not None
    assert requeued.failedAt is None
    assert all(operation.state == "pending" for operation in requeued.operations), \
        "it: clears the progress it had"

    # describe: requeueing onto a finished job
    complete_operation(OPERATOR, units[1], 1, {}, "")
    pull_work_unit(OPERATOR, line)
    fail_operation(OPERATOR, units[0], 1, {}, "Still will not power on")
    assert get_job_detail(job_id).active is False, \
        "it: deactivates once every unit is resolved"
    assert requeue_work_unit(ADMIN, units[0]).jobReactivated is True
    assert get_job_detail(job_id).active is True

    # describe: requeueing a unit that has not failed
    with pytest.raises(Blocked):
        requeue_work_unit(ADMIN, units[1])


# --- Pools ---------------------------------------------------------------

def test_pool_checkout():
    fresh_database()
    pool_id = a_pool(resources=[("Card 1", "12345"), ("Card 2", "67890")])
    line_id = a_production_line(pools=[pool_id], operations=[("Scan", ())])
    job_id = a_job(line_id, units=2)
    start_job(ADMIN, job_id)
    card1, card2 = [resource.id for resource in get_pool_detail(pool_id).resources]

    # describe: joining with a required pool
    line = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card1}]).lineId
    assert get_pool_detail(pool_id).resources[0].heldBy.lineId == line
    assert [(r.pool, r.resource, r.value) for r in get_line_detail(line).resources] == \
        [("Test card", "Card 1", "12345")]

    # describe: a resource another line already holds
    with pytest.raises(Blocked):
        join_line(OTHER_OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card1}])

    # describe: a resource that is out of service
    save_resource(ADMIN, pool_id, card2, "Card 2", "67890", in_service=False)
    with pytest.raises(Blocked):
        join_line(OTHER_OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card2}])
    save_resource(ADMIN, pool_id, card2, "Card 2", "67890", in_service=True)

    # describe: a required pool left unchosen
    with pytest.raises((Blocked, ValidationError)):
        join_line(OTHER_OPERATOR, job_id, [])

    # describe: leaving the line
    leave_line(OPERATOR, line)
    assert get_pool_detail(pool_id).resources[0].heldBy is None, \
        "it: returns every resource the line held"
    assert get_line_detail(line).state == "left"
    assert get_line_detail(line).unitsCompleted == 0, \
        "it: keeps the line record, which carries the operator's metrics"

    # describe: forcing a resource back
    other = join_line(OTHER_OPERATOR, job_id,
                      [{"poolId": pool_id, "resourceId": card2}]).lineId
    return_resource(ADMIN, card2)
    assert get_pool_detail(pool_id).resources[1].heldBy is None
    assert get_line_detail(other).state != "left", \
        "it: frees the resource without ending the line"


def test_pool_rules():
    fresh_database()
    unused = a_pool("Printer", [("Printer 1", "PR-1")])
    used = a_pool("Test card")
    line_id = a_production_line(pools=[used], operations=[("Scan", ())])

    # describe: renaming a pool nothing references
    rename_pool(ADMIN, unused, "Label printer")
    assert get_pool_detail(unused).name == "Label printer"

    # describe: renaming a pool the current version requires
    with pytest.raises(Blocked) as raised:
        rename_pool(ADMIN, used, "Cards")
    assert raised.value.blockers, "it: names what stands in the way"

    # describe: renaming a pool only a historical version requires
    job_id = a_job(line_id, units=1)
    start_job(ADMIN, job_id)
    save_production_line(ADMIN, line_id, "CR-One Reader", ["Location", "Group", "Asset"], [])
    assert get_production_line_detail(line_id).pools == [], \
        "it: forks, and the new version no longer requires the pool"
    with pytest.raises(Blocked):
        rename_pool(ADMIN, used, "Cards")   # it: keeps history renderable by refusing

    # describe: a duplicate name, differing only by case
    with pytest.raises((Blocked, ValidationError)):
        rename_pool(ADMIN, unused, "test card")

    # describe: deleting a pool a production line requires
    with pytest.raises(Blocked):
        delete_pool(ADMIN, used)

    # describe: deleting a pool nothing references
    delete_pool(ADMIN, unused)
    assert [pool.id for pool in list_pools()] == [used], "it: is gone, with its resources"


# --- Job lifecycle -------------------------------------------------------

def test_job_lifecycle():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", ())])

    # describe: starting a job with no work units
    empty = a_job(line_id, name="Empty run", units=0)
    with pytest.raises(Blocked):
        start_job(ADMIN, empty)

    # describe: starting a job whose line has no operations
    bare = a_job(a_production_line("Empty line", operations=()), name="Bare run", units=1)
    with pytest.raises(Blocked):
        start_job(ADMIN, bare)

    # describe: starting
    job_id = a_job(line_id, units=2)
    start_job(ADMIN, job_id)
    assert get_job_detail(job_id).active is True
    assert get_job_detail(job_id).versionId == \
        get_production_line_detail(line_id).versionId

    # describe: stopping with operators on lines
    line = join_line(OPERATOR, job_id, []).lineId
    assert stop_job(ADMIN, job_id).operatorsPaused == 1
    assert get_job_detail(job_id).active is False
    paused = get_line_detail(line)
    assert paused.state == "paused"
    assert paused.pauseOrigin == "admin"

    # describe: starting again
    start_job(ADMIN, job_id)
    assert get_line_detail(line).state == "working", \
        "it: clears the pause the manager raised"

    # describe: an operator's own pause survives a restart
    set_line_state(OPERATOR, line, "paused", "operator")
    stop_job(ADMIN, job_id)
    start_job(ADMIN, job_id)
    assert get_line_detail(line).state == "paused", \
        "it: leaves an operator who chose to break on break"

    # describe: the last unit resolves
    set_line_state(OPERATOR, line, "working", "operator")
    for _ in range(2):
        unit = pull_work_unit(OPERATOR, line)
        complete_operation(OPERATOR, unit.id, 1, {}, "")
    assert get_job_detail(job_id).active is False, \
        "it: finishes once every unit is resolved"

    # describe: failures count as resolved
    leave_line(OPERATOR, line)
    failing = a_job(line_id, name="All failed", units=1)
    start_job(ADMIN, failing)
    failing_line = join_line(OPERATOR, failing, []).lineId
    unit = pull_work_unit(OPERATOR, failing_line)
    fail_operation(OPERATOR, unit.id, 1, {}, "Dead on arrival")
    assert get_job_detail(failing).active is False, \
        "it: finishes a job whose remaining units all failed"

    # describe: deleting a job that has been worked
    with pytest.raises(Blocked):
        delete_job(ADMIN, job_id)

    # describe: deleting an untouched job
    delete_job(ADMIN, empty)
    with pytest.raises(ValidationError):
        get_job_detail(empty)

    # describe: a completion date before the start date
    with pytest.raises(ValidationError):
        save_job(ADMIN, None, "Backwards", line_id, "2026-08-14", "2026-07-06")


def test_line_state():
    fresh_database()
    pool_id = a_pool()
    line_id = a_production_line(pools=[pool_id], operations=[("Scan", ())])
    job_id = a_job(line_id, units=2)
    start_job(ADMIN, job_id)
    card = get_pool_detail(pool_id).resources[0].id

    # describe: joining
    line = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card}]).lineId
    assert get_line_detail(line).state == "working"

    # describe: joining a second job while holding a line
    second = a_job(line_id, name="Second run", units=1)
    start_job(ADMIN, second)
    with pytest.raises(Blocked):
        join_line(OPERATOR, second, [])

    # describe: an operator raising the andon
    set_line_state(OPERATOR, line, "stopped", "operator", "Reader will not power on")
    stopped = get_line_detail(line)
    assert stopped.state == "stopped"
    assert stopped.blocked.kind == "stopped"
    assert stopped.blocked.origin == "operator"
    assert stopped.blocked.reason == "Reader will not power on"

    # describe: the operator clearing their own andon
    # How long the line was blocked is measured while it is stopped; that the
    # measurement is right is `test_throughput`'s job, not this one's.
    set_line_state(OPERATOR, line, "working", "operator")
    assert get_line_detail(line).state == "working"
    assert get_line_detail(line).blocked is None

    # describe: an operator clearing a manager's stop
    set_line_state(ADMIN, line, "stopped", "admin")
    with pytest.raises(Blocked):
        set_line_state(OPERATOR, line, "working", "operator")

    # describe: the manager clearing it
    set_line_state(ADMIN, line, "working", "admin")
    assert get_line_detail(line).state == "working"

    # describe: closing the window
    set_line_state(OPERATOR, line, "paused", "window")
    windowed = get_line_detail(line)
    assert windowed.pauseOrigin == "window"
    assert [(r.pool, r.resource, r.value) for r in windowed.resources] == \
        [("Test card", "Card 1", "12345")], \
        "it: keeps the resources so the operator resumes where they left off"

    # describe: rejoining after leaving
    leave_line(OPERATOR, line)
    rejoined = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card}])
    assert rejoined.lineId == line, "it: reuses the same permanent line record"


# --- Throughput and export -----------------------------------------------

def test_throughput():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", ())])
    job_id = a_job(line_id, units=4)
    start_job(ADMIN, job_id)
    line = join_line(OPERATOR, job_id, []).lineId
    units = unit_ids(job_id)

    # describe: nothing completed in the window
    empty = job_throughput(job_id, window_minutes=60)
    assert empty.unitsPerHour is None
    assert empty.avgCycleSeconds is None

    # Three units are worked, then moved into the past: one before the window
    # opens, two inside it, each having taken ten minutes.
    for unit_id in units[:3]:
        pull_work_unit(OPERATOR, line)
        complete_operation(OPERATOR, unit_id, 1, {}, "")
    backdate_work_unit(units[0], started=70, completed=65)
    backdate_work_unit(units[1], started=20, completed=10)
    backdate_work_unit(units[2], started=20, completed=10)

    # describe: units inside and outside the window
    result = job_throughput(job_id, window_minutes=60)
    assert result.unitsInWindow == 2, "it: counts only what completed inside the window"

    # describe: scaling to the hour
    assert result.unitsPerHour == pytest.approx(2.0, abs=0.01)
    assert job_throughput(job_id, window_minutes=30).unitsPerHour == \
        pytest.approx(4.0, abs=0.01)

    # describe: cycle time
    assert result.avgCycleSeconds == pytest.approx(600, abs=5), \
        "it: averages the time each unit took"

    # describe: a blocked interval overlapping a unit
    backdate_block(line, started=18, ended=13)
    blocked = job_throughput(job_id, window_minutes=60)
    assert blocked.avgCycleSeconds < result.avgCycleSeconds, \
        "it: subtracts time the line was blocked"


def test_export():
    fresh_database()
    pool_id = a_pool()
    line_id = a_production_line(pools=[pool_id],
                                operations=[("Scan", [text("serial", "Serial")])])
    job_id = a_job(line_id, units=0)

    # describe: a job with no work units
    assert len(export.work_units_csv(job_id).strip().splitlines()) == 1, \
        "it: writes the header row and nothing else"

    # describe: headers
    add_work_units(job_id, 3)
    header = export.work_units_csv(job_id).splitlines()[0]
    for column in ("Location", "Group", "Asset", "state", "1.serial"):
        assert column in header, f"it: includes {column}"

    # describe: one row per work unit
    assert len(export.work_units_csv(job_id).strip().splitlines()) == 4, \
        "it: writes a header and one row per unit"

    # describe: a failed unit
    start_job(ADMIN, job_id)
    card = get_pool_detail(pool_id).resources[0].id
    line = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card}]).lineId
    unit = pull_work_unit(OPERATOR, line)
    fail_operation(OPERATOR, unit.id, 1, {"serial": "CR1-00042"}, "Will not power on")
    rows = [row for row in export.work_units_csv(job_id).splitlines() if "failed" in row]
    assert len(rows) == 1, "it: reports the state, leaving incomplete steps blank"


# --- Authoring a production line -----------------------------------------

def test_operation_authoring():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", [text("serial", "Serial")]),
                                            ("Check", ()),
                                            ("Pack", ())])

    # describe: the steps an operation gets
    steps = [(o.step, o.name) for o in get_production_line_detail(line_id).operations]
    assert steps == [(1, "Scan"), (2, "Check"), (3, "Pack")], "it: appends at the end"

    # describe: renaming an operation
    operations = get_production_line_detail(line_id).operations
    save_operation(ADMIN, operations[1].id, "Inspect")
    assert get_operation_detail(operations[1].id).name == "Inspect"

    # describe: reordering
    reordered = [operations[2].id, operations[0].id, operations[1].id]
    reorder_operations(ADMIN, line_id, reordered)
    assert [(o.step, o.name) for o in get_production_line_detail(line_id).operations] == \
        [(1, "Pack"), (2, "Scan"), (3, "Inspect")], "it: renumbers the steps to match"

    # describe: deleting an operation from the middle
    middle = get_production_line_detail(line_id).operations[1]
    delete_operation(ADMIN, middle.id)
    assert [(o.step, o.name) for o in get_production_line_detail(line_id).operations] == \
        [(1, "Pack"), (2, "Inspect")], "it: closes the gap rather than leaving a hole"

    # describe: editing once a job has frozen the version
    a_job(line_id, units=1)
    start_job(ADMIN, unit_ids_job(line_id))
    before = get_production_line_detail(line_id)
    result = save_operation(ADMIN, before.operations[0].id, "Pack and label")
    assert result.forked is True, "it: forks rather than rewriting history"
    after = get_production_line_detail(line_id)
    assert after.version == before.version + 1
    assert [o.name for o in after.operations] == ["Pack and label", "Inspect"]
    assert get_operation_detail(before.operations[0].id).name == "Pack", \
        "it: leaves the frozen version exactly as its operators saw it"


def unit_ids_job(line_id):
    """The most recently created job on a production line."""
    return [job.id for job in list_jobs() if job.productionLineId == line_id][-1]


def test_section_authoring():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", ())])
    operation_id = get_production_line_detail(line_id).operations[0].id

    # describe: adding sections
    add_section(ADMIN, operation_id, "description", body="Scan the {work_unit.Asset}")
    add_section(ADMIN, operation_id, "text", name="serial", label="Serial", required=True)
    sections = get_operation_detail(operation_id).sections
    assert [s.type for s in sections] == ["description", "text"], "it: appends in order"
    assert sections[1].required is True

    # describe: an input section with no name
    with pytest.raises(ValidationError):
        add_section(ADMIN, operation_id, "text", label="Nameless")

    # describe: a kind of section that does not exist
    with pytest.raises(ValidationError):
        add_section(ADMIN, operation_id, "hologram", name="x")

    # describe: editing a section
    save_section(ADMIN, sections[1].id, "text", name="serial", label="Serial number",
                 required=False)
    edited = get_operation_detail(operation_id).sections[1]
    assert edited.label == "Serial number"
    assert edited.required is False

    # describe: reordering
    reorder_sections(ADMIN, operation_id, [sections[1].id, sections[0].id])
    assert [s.type for s in get_operation_detail(operation_id).sections] == \
        ["text", "description"]

    # describe: deleting
    delete_section(ADMIN, sections[0].id)
    assert [s.type for s in get_operation_detail(operation_id).sections] == ["text"]

    # describe: a section carrying options
    options_id = add_section(ADMIN, operation_id, "options", name="result", label="Result",
                             options=["Pass", "Fail"]).sectionId
    stored = [s for s in get_operation_detail(operation_id).sections if s.id == options_id][0]
    assert stored.options == ["Pass", "Fail"]


def test_version_history():
    fresh_database()
    line_id = a_production_line(operations=[("Scan", ())])
    first = get_production_line_detail(line_id)

    # describe: a line that has never run
    versions = list_versions(line_id)
    assert len(versions) == 1
    assert versions[0].frozen is False
    assert versions[0].jobCount == 0

    # describe: after a job starts and the line is edited
    job_id = a_job(line_id, units=1)
    start_job(ADMIN, job_id)
    save_operation(ADMIN, first.operations[0].id, "Scan reader")

    versions = list_versions(line_id)
    assert [v.version for v in versions] == [2, 1], "it: lists the newest first"
    assert versions[1].frozen is True
    assert versions[1].jobCount == 1, "it: says how many jobs pinned each version"
    assert versions[0].frozen is False

    # describe: reading a historical version
    old = get_version_detail(first.versionId)
    assert old.version == 1
    assert old.frozen is True
    assert [o.name for o in old.operations] == ["Scan"], \
        "it: shows what that version held, not what the line holds now"


# --- The operator's screens ----------------------------------------------

def test_operator_screens():
    fresh_database()
    pool_id = a_pool(resources=[("Card 1", "12345")])
    line_id = a_production_line(pools=[pool_id], operations=[
        ("Scan", [{"type": "description", "body": "Scan {work_unit.Asset} with {pool.Test card}"},
                  text("serial", "Serial", required=True)])])
    job_id = a_job(line_id, units=2)
    card = get_pool_detail(pool_id).resources[0].id

    # describe: a job that has not started
    assert "This job is not running." in get_join_info(OPERATOR, job_id).blocked

    # describe: a job ready to join
    start_job(ADMIN, job_id)
    info = get_join_info(OPERATOR, job_id)
    assert info.blocked == []
    assert info.product == "CR-One Reader"
    assert [r.name for r in info.pools[0].resources] == ["Card 1"]

    # describe: the only resource is taken
    line = join_line(OPERATOR, job_id, [{"poolId": pool_id, "resourceId": card}]).lineId
    other = get_join_info(OTHER_OPERATOR, job_id)
    assert any("taken or out of service" in reason for reason in other.blocked), \
        "it: says why, rather than offering a choice that cannot be made"

    # describe: the operator who holds it may still choose it
    assert get_join_info(OPERATOR, job_id).blocked == []

    # describe: holding a line elsewhere
    second = a_job(line_id, name="Second run", units=1)
    start_job(ADMIN, second)
    assert any("already on a line" in reason
               for reason in get_join_info(OPERATOR, second).blocked)

    # describe: what the operator sees before pulling
    state = get_line_state(line)
    assert state.state == "working"
    assert state.workUnit is None, "it: shows no work until they ask for some"
    assert [o.name for o in state.operations] == ["Scan"]

    # describe: pulling work
    pulled = pull_work(OPERATOR, line)
    assert pulled.empty is False
    assert pulled.workUnit.state == "in_progress"
    assert pulled.resources == [UsedResource(pool="Test card", resource="Card 1", value="12345")]

    # describe: the instructions the operator reads
    body = pulled.operations[0].sections[0].body
    assert "{" not in body, "it: resolves every token before the operator sees it"
    assert "12345" in body, "it: renders the resource they checked out"
    assert pulled.workUnit.input["Asset"] in body

    # describe: the queue running dry
    complete_operation(OPERATOR, pulled.workUnit.id, 1, {"serial": "A"}, "")
    second_unit = pull_work(OPERATOR, line)
    complete_operation(OPERATOR, second_unit.workUnit.id, 1, {"serial": "B"}, "")
    assert get_job_detail(job_id).active is False, "it: finishes the job"

    # describe: what the operator is offered
    leave_line(OPERATOR, line)
    active = list_active_jobs(OPERATOR)
    assert active.heldLine is None
    assert [j.jobId for j in active.jobs] == [second], "it: lists only running jobs"
    assert active.jobs[0].unitsRemaining == 1

    # describe: who the caller is
    assert get_me(ADMIN).isAdmin is True
    assert get_me(OPERATOR).isAdmin is False


# --- Routes --------------------------------------------------------------
#
# The integration layer is thin: it authenticates, calls a rule, and returns
# what comes back. There is nothing here worth asserting about behaviour —
# that is what every test above is for. This checks only that the wiring holds.

def test_routes_are_wired():
    fresh_database()
    production = get_app_module("io.bithead.production")

    import asyncio, httpx
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(production.router)

    routes = [(sorted(route.methods - {"HEAD"})[0], route.path) for route in app.routes
              if getattr(route, "methods", None) and "io.bithead.production" in route.path]
    assert routes, "it: mounts the router"

    sample = {"{pool_id}": "1", "{resource_id}": "1", "{line_id}": "1", "{version_id}": "1",
              "{operation_id}": "1", "{section_id}": "1", "{job_id}": "1",
              "{work_unit_id}": "1", "{step}": "1"}

    async def call_them_all():
        broken = []
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as client:
            for method, path in routes:
                for token, value in sample.items():
                    path = path.replace(token, value)
                response = await client.request(method, path, json={})
                # Anything under 500 is the app answering: auth, a missing body,
                # or a rule refusing. A 5xx is the route itself being broken.
                if response.status_code >= 500:
                    broken.append((method, path, response.status_code, response.text[:200]))
        return broken

    assert asyncio.run(call_them_all()) == [], \
        f"it: all {len(routes)} routes answer rather than erroring"
