---
name: private-service-tests
description: Write or change tests for a BOSS private Python service (private/tests/test_<app>.py). Use when adding a Stage 3 test group, testing a lib.py rule, or when a test needs state it cannot reach through the interface.
---

# Testing a private service

The rules are in [`python.md` § Testing Private Services](../../../docs/prompt/python.md).
This is the order to do them in. The steps that catch mistakes come last, and
each one earns its place.

## 1. Write the test against `lib.py`

Build the situation with the same calls the client makes, and read the outcome
back the same way:

```python
business = create_business("Test Business", "UTC", "reserved")
set_operating_hours(business.id, 1, "09:00", "17:00")
job_type = create_job_type(business.id, "Lawn Mowing")
```

Two rules decide which layer a line uses:

1. **No `lib` call for what you need to seed or read? Use `db`.** That is the
   honest answer while the interface is still being built, and it beats
   inventing a function no rule has asked for.
2. **A `lib` call exists, or arrives later? Use it.** A call added for a route
   is the call the test wanted. Switching to it is how a test goes on
   describing what a user can do rather than what the tables hold.

Revisit rule 2 as `lib` grows: a group written early under rule 1 is worth a
second look. `bin/check-tests` lists the `db` calls.

Name each block with the situation and each assertion with the behaviour, so a
failure reads as a sentence:

```python
# describe: employee has a time-off window
assert "13:00" in times, "it: offers the time the window ends"
```

## 2. Write the implementation, then run

Write it complete — `db.py` queries, `model.py` shapes, `lib.py` rules — rather
than stubbing the functions and watching the group go red first.

```bash
source ~/.venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 private/run_tests.sh private/tests/test_<app>.py <test_name>
```

Name the test while writing it, and drop the name once the group is finished —
[`python.md` § How much to run](../../../docs/prompt/python.md#how-much-to-run)
has the scopes.

**A green first run says the implementation is not obviously broken.** Step 3
is what shows the assertions are capable of failing, and every gap found so far
was in a group that went green on its first run.

That is a deliberate trade. Stubbing first shows an assertion can fail;
mutation shows it fails *for the right reason*, which is the stronger claim — a
fixture that satisfies both the correct answer and a wrong one survives
red-green and dies under mutation.

**Read a first-run failure carefully before touching the implementation.** It
is about evenly split between a real bug and a wrong expectation in the test,
so read the test first.

## 3. Prove it has teeth

A test written after the code usually passes on the first run. Break each rule
the group covers and confirm a failure.

Write the breaks in a mutations file — one block per rule, indentation
preserved because it is part of the match:

```
@@ employee time off is ignored
--- old
    if any(overlaps(start, end, *window) for window in away[employee_id]):
        return False
--- new
    pass
```

```bash
source ~/.venv/bin/activate
bin/mutate private/app/<bundle>/lib.py private/tests/test_<app>.py \
           /tmp/rules.mut -k "<the group these rules are in>"
```

`-k` is what keeps this quick: the suite runs once per mutation, so a dozen
mutations against a whole file is minutes where one group is seconds. See
[`python.md` § How much to run](../../../docs/prompt/python.md#how-much-to-run).

It reports three outcomes, and the third is why it exists:

| | |
|---|---|
| `caught` | The rule is tested |
| `NOT CAUGHT` | The rule wants a test, or the mutation was equivalent — read the code and say which |
| `could not apply` | The target matched zero or several places. Narrow it and run again |

The tool holds the suite back on that last case, so a pass under the label
always means a mutation was live.

It also handles what is easy to forget: bytecode stays unwritten and
`__pycache__` is cleared between mutations, the file is restored in a `finally`,
and the run starts from a green suite. Afterwards it compares the file to its
pre-run bytes, catching anything else that wrote to it mid-run.

## 4. Check it stayed black box

```bash
bin/check-tests private/tests/test_<app>.py
```

`bin/check` runs this too. SQL in a test file is an error. A `db.*` call is a
warning, and a warning here is a prompt to look: whether a `lib` call could
replace it is a judgment for a reader. Read each one and apply the two rules
above. A `db` call earns its place by being the only way to reach the
situation.

## 5. Report the exceptions out loud

A few situations lie outside the interface: the passage of time, or a property
of the connection. Those take this shape — a banner naming why, a helper with
one job below it, and tests calling the helper:

The statement itself belongs in `db.py`, under a `# For tests` heading — not in
the test file. It ships with the app, and that is the trade: every statement
stays inside the one module, so moving off SQLite changes `db.py` and leaves
`private/tests` alone.

```python
# db.py
# =========================================================================
# For tests
#
# Statements that exist only so a test can reach a situation no interface can
# produce — the passage of time, so far.
# =========================================================================

def expire_session(session_token: str) -> int:
    """Move a hold's expiry into the past, as waiting would."""
    return update("UPDATE job_sessions SET expires_at = datetime('now', '-1 minutes')"
                  " WHERE session_token = ?", (session_token,))
```

```python
# the test file — a banner saying why, and the call by name
# --- The exceptions ------------------------------------------------------
#
# A session expiring is the passage of time, which no customer can perform.

db.expire_session(held.sessionToken)
```

The test for an exception is whether an interface call could do the same work.
Where a predictable fixture already tells the test what to expect, assert
against the fixture and let the read go.

Say in the summary that the exception exists and why, every time. An exception
nobody mentions becomes a precedent.

## 6. Report it

The `report` skill has the shape, and it applies to every response that
changed something. Two things this work owes it in
particular:

- **Say the exception exists and why**, every time one was needed — see step 5.
  An exception nobody mentions becomes a precedent.
- **The Tests section carries the mutation count** alongside the passing count.
  Mutation is what puts evidence behind a suite, and that section is where it
  shows.

## Where things go

| | |
|---|---|
| `db.py` | Every SQL statement, one named function each, returning row models spelled as the columns are |
| `model.py` | Domain and response models, camelCase |
| `lib.py` | The rules. The only module tests import for behaviour |
| `private/tests/test_<app>.py` | The tests |

Point the app at a test database and recreate it per group, so each run starts
from the schema and its seeds:

```python
def fresh_database():
    db.set_database_name("test-<app>.sqlite3")
    db.delete_database()
    db.start_database()
```

`test_production.py` is the reference for all of this.
