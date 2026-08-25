---
name: private-service-tests
description: Write or change tests for a BOSS private Python service (private/tests/test_<app>.py). Use when adding a Stage 3 test group, testing a lib.py rule, or when a test needs state it cannot reach through the interface.
---

# Testing a private service

The rules are in [`python.md` § Testing Private Services](../../../docs/prompt/python.md).
This is the order to do them in, because the steps that catch mistakes are the
ones easiest to skip.

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

Rule 2 is the one that needs revisiting: a group written early under rule 1
should be looked at again once `lib` grows. `bin/check-tests` lists the `db`
calls so that list is in front of you.

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
PYTHONDONTWRITEBYTECODE=1 private/run_tests.sh private/tests/test_<app>.py
```

**A green first run proves nothing about the tests.** It says nothing is
obviously broken. It does not say a single assertion is capable of failing,
because none of them ever has. Step 3 is what supplies that evidence, and under
this process it is the only thing that does — skip it and the group is a green
suite with no proof behind it. Every gap found so far was in a group that went
green on its first run.

That is a deliberate trade. Stubbing first proves an assertion can fail;
mutation proves it fails *for the right reason*, which is the stronger claim
and catches things red-green cannot — a fixture that satisfies both the correct
answer and a wrong one passes red-green and dies under mutation.

**Read a first-run failure carefully before touching the implementation.** It
is about evenly split between a real bug and a wrong expectation in the test.
Reaching for the implementation first is a coin flip.

## 3. Prove it has teeth

A test that passes on a broken implementation is worse than none, and a test
written after the code usually passes for the wrong reason. Break each rule the
group covers and confirm a failure.

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
bin/mutate private/app/<bundle>/lib.py private/tests/test_<app>.py /tmp/rules.mut
```

It reports three outcomes, and the third is why it exists:

| | |
|---|---|
| `caught` | The rule is tested |
| `NOT CAUGHT` | The rule is not tested, or the mutation was equivalent — read the code and say which |
| `could not apply` | The target matched zero or several places. **Not a result.** Narrow it and run again |

Done by hand, that last case runs the suite against an unmodified file and
prints a pass under the label, which is indistinguishable from a rule with no
teeth. The tool never runs the suite in that case.

It also handles what is easy to forget: bytecode is never written and
`__pycache__` is cleared between mutations, the file is restored in a `finally`,
and the run refuses to start if the suite is already red. Afterwards it compares
the file to its pre-run bytes, so anything else writing to it mid-run is caught.

## 4. Check it stayed black box

```bash
bin/check-tests private/tests/test_<app>.py
```

`bin/check` runs this too. SQL in a test file is an error. A `db.*` call is a
warning, and a warning here is a prompt to look rather than a verdict: whether
a `lib` call could replace it is a judgment no tool can make. Read each one and
apply the two rules above. Wrapping a `db` call in a helper is the same code
behind a new name and changes nothing.

## 5. Report the exceptions out loud

A few rules cannot be reached through the interface at all: the passage of
time, or a property of the connection rather than of any rule. Those take this
shape — a banner naming why, a helper with one job below it, and tests calling
the helper:

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

The test for the exception is whether an interface call could do the same
work — not whether the code can be given a nicer name. Wrapping a storage read
in a helper produces the same code behind a new name and buys nothing. If a
predictable fixture already tells the test what to expect, assert against the
fixture and drop the read entirely.

Say in the summary that the exception exists and why, every time. An exception
nobody mentions becomes a precedent.

## 6. Report it in this shape

Three sections, in this order. Paths first, because that is what was asked
for; what you learned comes after.

**What was tested** — one bullet per path, each reading *situation → outcome*.
Happy paths and exception paths sit in the same list, grouped by feature.
Name the exception raised:

```
**Sending a verification code to get back into a booking**
- Customer gave a phone number → code sent by SMS
- Customer gave neither a phone nor an email → `NoContactChannel`, nothing sent
- Job code matches no appointment → `JobNotFound`, nothing sent
```

**Tests** — the total, and that they pass. Say that each rule was broken
deliberately and a test caught it. Do not list the individual breaks: a table
of things that failed on purpose reads as a report of failures, and says
nothing about the state they were left in. Everything passes before moving on.

**What I found along the way** — mistakes made, surprises, anything left
without a consumer. A wrong assertion, a check that did not run, a counter
nothing reads yet.

**What I need from you** — only when something is genuinely the developer's to
decide. Five short parts, in this order, and the last two matter most:

- *The context.* Where the decision bites, in plain language.
- *What the source says.* Quote the plan's Open Decision, or the rule, verbatim.
  Not a paraphrase — they wrote it, and the wording is the question.
- *Why it is a tradeoff.* Each option with its real consequence. Say which
  consequences are mild, because that is usually what decides it.
- *What is actually needed.* The question on its own, in a sentence.
- *What changes when they answer.* Which file, and what does **not** change.
  Saying the tests and rules already stand tells them the work is not stalled
  and the decision is cheap to make.

Recommend an option. A decision presented as a menu asks them to do the
thinking twice.

## Where things go

| | |
|---|---|
| `db.py` | Every SQL statement, one named function each, returning row models spelled as the columns are |
| `model.py` | Domain and response models, camelCase |
| `lib.py` | The rules. The only module tests import for behaviour |
| `private/tests/test_<app>.py` | The tests |

Point the app at a test database and recreate it per group, so a run never
touches real data:

```python
def fresh_database():
    db.set_database_name("test-<app>.sqlite3")
    db.delete_database()
    db.start_database()
```

`test_production.py` is the reference for all of this.
