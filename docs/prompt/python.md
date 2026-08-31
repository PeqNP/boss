# BOSS Python Private Services Reference

Rules for private Python service files under `private/`.

---

## 15. Backend — Python Private Services

Private Python web services live in `/private/app/<bundle_id>/`.

### Endpoint pattern

```python
from fastapi import APIRouter, Request
from lib.model import User
from lib.server import require_user

router = APIRouter()

@router.get("/my-feature/items")
@require_user()
async def get_items(boss_user: User, request: Request):
    """ Return list of items. """
    # ... query logic
    return [{"id": 1, "name": "Item 1"}]

@router.post("/my-feature/item")
@require_user()
async def save_item(body: ItemBody, boss_user: User, request: Request):
    """ Create or update an item. """
    # ...
    return {}
```

**Rules:**
- Use `@require_user()`, with parentheses, when the request requires an authenticated `User`. Unprotected routes omit this decorator.
- **A route declaring a feature names the roles that reach it**, as members of the app's own `Role` enum — `@require_acl("employee.r", roles=[Role.OPERATOR, Role.EMPLOYEE])`. Members rather than strings, so a misspelling is an `AttributeError` when the module imports, and the value is the label Settings shows. `default` is what BOSS supplies to an app that has declared no roles; a route never names it. A route with no role that suits it declares no feature either — read-only platform data with nobody's records in it sits outside ACL.
- **A decorator carries an operation many routes share.** A check that one route needs — verifying a vendor's webhook signature, comparing an OAuth `state` — lives in that handler, where a reader finds it beside the thing it protects.
- Use `@require_admin()` for a route only whoever runs the platform may reach. Hiding the menu keeps the screen out of the way; the guard is what stops anyone signed in from typing the URL.
- **A path names the resource, not who may reach it.** `/businesses` and `/business/{id}`, whoever is calling — the decorator says who that is. Grouping routes under `/admin` or `/superadmin` puts the answer in the one place a caller controls, and leaves two names for one resource when both roles read it. `bin/check-routes` reports a handler that reached a guard in the last commit and reaches none now, which holds across a rename because it follows the function rather than the path.
- Parameter order: endpoint params (path/body) → `boss_user: User` → `request: Request`
- Import `from lib.model import User` if not present
- Return empty `{}` or use `Fragment.OK` equivalent for empty responses
- Keep module-local model names concise. Prefer `ModelResponse` over `VisualizerModelResponse`.

### Service startup and shutdown

Private app modules may expose `start()` and `shutdown()` functions. `private/api.py` calls `start()` when the service boots and before routes begin handling requests.

**Rules:**
- Perform one-time database initialization in `start()`.
- Create or verify the SQLite database file, tables, indexes, and similar storage prerequisites in `start()`.
- Store service database files under the shared `db_path` from `lib.get_config()`.
- **Close every database connection in a `finally`.** A statement that fails leaves its connection holding SQLite's write lock, and every later write in the process answers `database is locked` until the service restarts. A web server keeps the traceback of a failed request, the traceback keeps the frame, and the frame keeps the connection open — so the `finally` is what closes it in production, and the suite runs green either way.
- Keep request handlers focused on request work, with schema creation and bootstrap logic in `start()`.
- For small private services, a few database helper functions may stay in `__init__.py`; a separate `db.py` module is optional.
- `shutdown()` may remain empty until the service has actual teardown work.
- An app whose `db.py` exposes `get_db_path()`, `delete_database()`, and `start_database()` is automatically covered by the UI test endpoints in `private/debug.py` — reset, snapshot, and restore of its own database. Nothing to implement; those three already exist for the test suite's benefit.

---

## 16. Lessons Learned — Private Python App Hardening

These are practical guardrails learned while implementing and debugging `io.bithead.lean-visualizer`.

### Route and prefix conventions

- Define a bundle-scoped router prefix for private APIs, e.g. `router = APIRouter(prefix="/api/io.bithead.lean-visualizer")`.
- Keep route decorators relative to that prefix (e.g. `@router.get("/sync-jira")`).
- Keep endpoint names stable once frontend wiring depends on them.

### Config and failure handling

- Keep app-local config in `private/app/<bundle_id>/config.json` and validate required keys at runtime.
- Raise `HTTPException` with actionable context (failed URL, status, and short reason).
- Treat external dependencies (Jira, BOSS ACL registration, nginx proxy) as first-class failure domains.

### Validation workflow before runtime debugging

- First run module syntax validation directly before launching services:

```bash
python3 private/app/<bundle_id>/__init__.py
```

- Use consistent 4-space indentation in Python service files.
- Keep `from __future__ import annotations` at the top of the module (after optional module docstring), before other imports.

---

## 19. Module Layout and Layering

Once a private service has business rules worth testing, split it into four modules. A service that is only a few queries behind a couple of routes may keep them in `__init__.py` (§15).

```
private/app/<bundle_id>/
  __init__.py   FastAPI routes. Auth decorators, request bodies, calls into lib.
  model.py      Pydantic models. The shapes both lib and the client speak.
  lib.py        Business rules. The only module tests import for behaviour.
  db.py         Schema, migrations, and every SQL statement the app issues.
```

**Rules:**

- **Import a whole layer with `*` when the layer above uses all of it.** `lib.py` does `from .model import *`; routes do `from .lib import *`. An explicit list has to be edited every time a model or rule is added, and that edit is pure overhead — the layer below exists to be used entirely by the layer above. Keep named imports where only a piece is wanted, such as `from lib.server import send_events`.
- **Still import a module you call directly.** `from .lib import *` also re-exports the modules `lib` imported, so `db.get_job(...)` may resolve without `from . import db` and break the moment `lib` stops importing it. Name what you use.
- Put every SQL statement in `db.py`, one function per query, named for what it means — `get_active_jobs()`, `claim_next_work_unit()`. The whole data surface of the app then reads in one place.
- Verify with `grep -nE "SELECT |INSERT |UPDATE |DELETE " <bundle_id>/{lib,export,...}.py`, which should return nothing.
- Keep business rules in `lib.py` taking and returning values. Tests call them directly.
- Emit notifications from routes, not from rules. `lib.server.send_events` needs the request to carry the caller's credentials, so the route calls its rule and then announces the result.
- Raise domain exceptions from rules — `RecordNotFound`, a `Blocked` that names what stands in the way, a `ValidationError` carrying a message meant for the user. Routes translate them into `HTTPException`. Rules stay free of HTTP.

### Indexes

Indexes are created with the table, as part of creating the database.

Three kinds of column get one.

**1. Every id that references another record**, whether or not a `REFERENCES`
clause says so. The test is what the column *means*: it holds the id of a row
somewhere. `user_id` is the shape to have in mind — BOSS users live in another
service's database, so the constraint lives outside SQLite while the lookup
lives here.

**2. Anything a query looks a row up by** — `email` and `phone` on a customer,
which is how an existing record is found.

**3. The trailing columns of a composite primary key.** A single-column primary
key arrives with its own index — `INTEGER PRIMARY KEY` is the rowid, and
anything else gets an implicit one. A composite key gets *one* implicit index,
sorted by its columns in order, which serves a lookup by the leading column and
by the whole key:

```sql
CREATE TABLE job_employees (
    job_id      INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    PRIMARY KEY (job_id, employee_id)
)
```

`WHERE job_id = ?` uses the implicit index. Both sides of a join table are
looked up by, so `employee_id` gets one of its own.

`PRAGMA table_info` gives the key position, so the rule is one comparison:

```python
for row in cursor.execute(f"PRAGMA table_info({table})"):
    column, pk_position = row[1], row[5]
    # 0 = not part of the key; otherwise its 1-based place in it. Position 1
    # is what the implicit index is sorted by, and the only one already served.
    if pk_position == 1:
        continue
    if column.endswith("_id") or (table, column) in BY_VALUE:
        ...
```

`UNIQUE` columns already have one, and keep it.

Derive the list from the schema itself, so a column added to a table is indexed
by having been added.

**A lookup whose `WHERE` clause is an expression needs an index on that same
expression.** SQLite matches an index to a query by the expression written, so
`WHERE LOWER(email) = ?` is served by an index on `LOWER(email)`. Generate the
query fragment and the index from one function, so the two stay identical:

```python
def _phone_expression(column: str = "phone") -> str:
    stripped = column
    for character in (" ", "-", "(", ")", ".", "+"):
        stripped = f"REPLACE({stripped}, '{character}', '')"
    return f"SUBSTR({stripped}, -10)"
```

`EXPLAIN QUERY PLAN` confirms it, reporting `SEARCH … USING INDEX` for a lookup
the index serves.

### A route that returns a file

A route handing back a `Response`, `FileResponse`, or `StreamingResponse` is
carrying a file rather than a shape, and declares no `response_model`. The
return says so, and `bin/check-services` reads it — such a route is left out of
the count of what is still to be wired.

```python
@router.get("/admin/reports/financial/export")
@handled
async def export_financial_report(request: Request, year: int):
    csv = lib.export_financial_report(_operator_business(request), year)
    return Response(
        content=csv, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=report.csv"}
    )
```

### Building one model from another

Pydantic builds one model from another. Reach for it in place of copying a
field at a time.

Every model in `model.py` inherits a base carrying
`model_config = ConfigDict(from_attributes=True)`, which is what makes the
three mechanisms below work:

**At the top of a route, do nothing.** `response_model=` validates whatever the
handler returns and keeps only the fields it declares, so a route may return a
*wider* model and get the narrow one on the wire:

```python
@router.post("/admin/employee/{employee_id}/schedule", response_model=WorkingDay)
async def create_employee_schedule(employee_id: int, body: WorkingDayBody):
    # Returns EmployeeSchedule, which is WorkingDay plus `employeeId`.
    return lib.add_working_day(employee_id, body.dayOfWeek, body.startTime,
                               body.endTime)
```

**Nested in an envelope, assign the list.** A field typed `List[Narrow]` accepts
`Wide` instances and narrows each:

```python
return AdminEmployeeTimeOff(timeOff=lib.get_time_off(employee_id))
```

**Anywhere else, validate from the object:**

```python
day = WorkingDay.model_validate(schedule, from_attributes=True)
```

Copy fields by hand where the shapes genuinely differ — a flat model feeding a
nested one, a value the route computes, a name the screen spells differently.
Say why in a comment when you do.

### Naming a model

A model is named for the record it carries. Where one record has two shapes —
a row in a list, and everything the record holds — the short one takes the
plain name and the full one takes `Detail`:

```python
class Job(Model):        # a row in the list a screen picks from
class JobDetail(Model):  # everything about the one that was picked
```

A model with no short form takes the plain name: `Dashboard`, `Icons`,
`ScheduleDay`.

**Name it for what the app holds, not for who reaches it.** A record is a thing
the system has; a role is a thing a person is. The two change independently,
and the record outlasts every rearrangement of who may open it.

| Named for | Becomes |
|---|---|
| `AdminJob` — an audience | `JobDetail` — the fuller shape of a job |
| `SuperadminBusinesses` — an access level | `PlatformBusinesses` — every business the platform has |
| `SuperadminTimeout` — who sets it | `ScheduleTimeout` — how long a hold lasts |
| `SuperadminHolidays` — who reads it | `SystemHolidays` — the `system_holidays` table |

Each of those was accurate when written and wrong within a release: `AdminJob`
gained an employee, `SuperadminBusinesses` gained an operator reading its own
row. The thing being carried never moved.

The test is whether the name survives somebody new being allowed in. `JobDetail`
does; `AdminJob` needed renaming the day an employee could open one.

### Models that share a shape

Two models with the same fields are usually one model that was written twice —
most often because a `POST` and a `PUT` return the same thing and each got a
name from its route. Sometimes they are genuinely two ideas that happen to
coincide, and the name is the only thing keeping them apart. `ContactValue` and
`AttributeValue` are both `{fieldId, value}`; nothing is gained by merging a
customer's phone number with an answer to "how many bedrooms".

Review each group. Before finishing a stage that added models, list every group
sharing a field set and decide it:

| Models | Fields | Suggested name | Replace |
|---|---|---|---|
| `AdminJobTypeSize`, `AdminJobTypeSizePut`, `JobTypeSizeDetail` | id, name, durationMinutes, cost, sortOrder | `JobTypeSizeDetail` | yes |
| `ContactValue`, `AttributeValue` | fieldId, value | — | no — one is a contact detail, the other an answer, and no name covers both |

**Replace when one name covers both honestly.** Keep them apart when the names
carry the distinction and no single name would.

A model whose fields are a *subset* of another's is a different question, and
usually stays: consolidate only when the larger costs nothing extra to
populate and discloses nothing. `KioskSlot` is smaller than `Slot` on purpose —
`Slot` carries `employeeIds`, and sending that to a kiosk tells a customer who
is free at every time they did not pick.

`bin/check-services` reports identical field sets as a warning, so the groups
surface on every check.

### Storing a file

Files live under the `media_path` from `~/.boss/config`, outside the
repository — a working tree is one `git clean -xdf` from empty, and gitignored
files are exactly what that removes. Each app has two directories:

```
<media_path>/<bundle>/public      nginx serves these at /media/<bundle>/public/<file>
<media_path>/<bundle>/private     reached through the app that owns it
```

The visibility is a directory rather than a flag, so a file cannot be in the
wrong one. nginx's public location is anchored on `/public/`, which makes it an
allowlist: a request naming any other directory matches no location and is
never served.

`private/lib/media.py` resolves the paths, creates them, and writes:

```python
from lib import media

stored = media.store_public(bundle, file.filename, await file.read())
return Icon(id=..., url=stored.url)      # /media/<bundle>/public/<name>
```

`store_public` and `store_private` are separate calls rather than one taking a
visibility, so a call site says which it is and a wrong constant has nowhere to
be passed. `store_private` hands back no URL.

The stored name is generated rather than reused: two people upload `logo.png`
and both are wanted, and the name that arrived never becomes a path.

**A private file is served by nginx once the app has authorised it.** The app
decides, `X-Accel-Redirect` hands the file over, and the bytes never pass
through Python:

```python
@router.get("/media/{name}")
@require_user()
@handled
async def get_document(name: str, boss_user: User, request: Request):
    if not lib.may_read(boss_user.id, name):
        raise HTTPException(status_code=404, detail="No such file.")
    return media.serve_private(BUNDLE, name)
```

Authorising is the app's: only it knows a document belongs to one customer and
their operator. That header is honoured by nginx alone, so private media is
exercised through `https://localhost` rather than against port 8082.

**SVG is served with `Content-Security-Policy: sandbox`.** An SVG is XML the
browser executes: inside `<img>` its scripts never run, and opened directly at
its URL they run on this origin. The header, set on the public location, keeps
the second case inert while an icon still draws.

### Parent before child

A function taking more than one id names them outermost first —
`get_employee(business_id, employee_id)`, `update_note(business_id,
customer_id, note_id)`.

Position then carries the hierarchy. Reading a signature says where the record
sits without opening the schema, and a call site reads as a path from the root
down to the thing being asked for.

```python
def get_employee(business_id: int, employee_id: int) -> Optional[EmployeeRow]:
    ...
```

The scope comes first for the same reason it is a parameter at all: a query
against a scoped table takes its scope, so a record belonging to somewhere else
is absent rather than refused.

### Schema drift

A version records which migrations have run. A schema still being written keeps
changing under a version that stays put: `create_version_1_0_0` grows a table,
the version it writes is still 1.0.0, and a database made yesterday matches on
version while lacking today's tables. Comparing the objects is what sees it.

An app takes part by giving its `db` module two names:

```python
def create_schema(conn):
    """Bring a connection up to the current schema, whatever version it is at."""
    version = get_db_version(conn)
    create_version_1_0_0(conn, version)


def get_db_path() -> str:
    ...
```

`create_schema` is the one definition of the current schema, used by
`start_database` and by the comparison alike — the check builds it into an
empty database and diffs the live file against it.

The diff is by definition, not by name. Three ways to be behind, and the report
names which: an object that is absent, an object present declaring something
else — a column that gained `UNIQUE`, a default that changed — and a seeded
table holding fewer rows than the seed puts there. Layout and comments are
reduced away first, so re-indenting a table is not drift.

```bash
bin/check-db          # report
bin/check-db --fix    # rebuild whatever has fallen behind
```

`private/restart` runs `--fix` before starting anything, so a development
database is current by the time a route can be called. `bin/check-services`
reports drift read-only, which is how `bin/check` surfaces it.

`--fix` discards every row, and
[`private/lib/schema.py`](../../private/lib/schema.py) refuses it on a machine
whose config says anything other than `env: dev`. `bin/update` calls
`private/start`, and that path stays clear of this.

### Changing the schema

**A new plan is what calls for a migration.** Until one exists, the schema is
still being worked out: `CURRENT_VERSION` stays where it is, the DDL for that
version keeps changing, and the development database is deleted and created
again whenever it falls behind. It holds nothing anyone needs, and versioning a
schema that moves daily buys nothing but ceremony.

Once a plan is written for a new feature — the developer says so explicitly —
the schema it lands on is the one people have. From then on a change is a
`create_version_<next>` function added to the chain in `start_database`, and the
version is bumped.

Drift is ordinary in the meantime and surfaces badly: a 500 from whichever route
touches the missing table, which points away from itself. `db.schema_drift()`
names what is missing, `start_database` logs it, and `bin/check-services`
reports it. The answer is always to delete the database and restart.

### Models

Both families are Pydantic `BaseModel`s, in the two places described in `process.md` — *Network and Domain Models*. `db.py` declares its own row models; `lib.py` imports both families and converts.

```python
# db.py — network. One per query shape, spelled as the columns are.
class JobRow(BaseModel):
    id: int
    name: str
    job_type_id: int
    active: int                 # SQLite has no boolean

def get_job(job_id: int) -> Optional[JobRow]:
    rows = select("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return JobRow(**rows[0]) if rows else None


# model.py — domain. camelCase, shaped by whoever reads it.
class Job(BaseModel):
    id: int
    name: str
    jobTypeId: int
    active: bool

class JobDetail(Job):           # the detail screen reads more than a rule does
    workUnitCount: int
    contract: JobContract


# lib.py — the app layer owns the conversion, once per concept.
def _job(row: db.JobRow) -> Job:
    return Job(id=row.id, name=row.name, jobTypeId=row.job_type_id,
               active=bool(row.active))
```

**Rules:**
- Declare a row model's fields as the columns are spelled, so `JobRow(**rows[0])` is the whole conversion from storage. A row model needing field-by-field assignment is misdeclared.
- Write one converter per concept in `lib.py`. Rules then work in attributes, and a mistyped column fails inside the converter.
- A query returning one column returns `List[int]` or `List[str]`.
- Return the domain model itself from a route, declared as `response_model=`. Calling `model_dump()` first discards the validation the declaration bought.
- Group request bodies in `model.py` under an `# --- Input models ---` heading. They are domain models: the client dictates their shape as surely as it dictates a response's.
- **A user is a BOSS user, so name the column `user_id` and the field `userId`.** It is the one kind an app references. Qualify by *role* where a table names more than one — `created_by_user_id`, `collected_by_user_id`. The OS spells it this way itself: `Friend.userId` in `private/lib/model.py`.

  The injected `boss_user: User` parameter keeps its prefix. It is the handle the OS hands the route, and the name says so, leaving `user` free for whatever the route is working on.

---

## 20. Testing Private Services

Tests are the consumer. They define the interface, and the implementation answers whether it can supply that output from that input. When it cannot, the interface grows a call.

Tests are written first, and the implementation is written complete rather than stubbed, so the first run is usually green. `bin/mutate` is what supplies the evidence that the tests work. See `.claude/skills/private-service-tests/SKILL.md`.

**Rules:**

- Write tests against `lib.py` and the response models, black box. A test builds its situation and checks its outcome through the same calls the client makes.
- Build state the way a user does, wherever `lib` offers the call. Import work through the import path, create records through the save calls, put an item in progress by claiming it. A situation built that way is one the app can actually reach, which is what makes the assertion mean something.
- **Where `lib` has no call for what a test needs to seed or read, use `db`.** That is the honest answer while the interface is still being built, and it keeps a test group from waiting on functions no rule has asked for yet.
- **Move to the `lib` call once there is one.** A call added later for a route is the call the test wanted; switching to it keeps the test describing what a user can do. `bin/check-tests` warns on each `db` call, as a reminder to look.
- Read state through response models where one exists. When a test needs something no screen shows, add the read model the screen would need — it is required by the client eventually, so writing it now finishes the interface early.
- Keep SQL out of the test file. A statement a test needs — moving a timestamp into the past, writing a child against a missing parent — becomes a named function in `db.py`, under a `# For tests` heading. It ships with the app, which is the trade: every statement stays inside the one module, so moving off SQLite changes `db.py` and nothing under `private/tests`. `bin/check-tests` reports SQL in a test file as an error, and `bin/check` runs it.
- Name each block with the situation and each assertion with the behaviour, so a failure reads as a sentence:

```python
    # describe: a required field left blank
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 1, {"serial": ""}, "")

    # describe: the last step
    assert complete_operation(OPERATOR, unit, 2, {"led_ok": True}, "")["unitComplete"] is True
    assert get_line_detail(line)["unitsCompleted"] == 1, "it: credits the operator"
```

- Point the app at a test database (`db.set_database_name("test-<app>.sqlite3")`) and recreate it per group, so each run starts from the schema and its seeds.

### Exceptions

A rule about elapsed time is the usual one: throughput over a trailing window needs records already in the past, and no interface call can manufacture a past. Where an exception is genuinely required:

- Put the storage-aware helper in the test file under a banner comment naming why it exists.
- Give it one job and use it from the one test that needs it.
- Say so when reporting the work, so the exception stays visible.

### How much to run

Run the tests for the behaviour being written, and widen only when the work
widens:

| While | Run |
|---|---|
| Writing a rule, or chasing a failure | The test function — `run_tests.sh <file> <test_name>` |
| The feature is finished | The app's own file |
| Shared code changed — `private/lib/`, `libtest`, `bin/` | Every file |

The numbers are what settle it: one test function is under a second, an app's
file is a few seconds, and every file is a second more than that. The other
apps are cheap; running the whole file over and over is what costs.

`bin/mutate` runs the suite **once per mutation**, so it is the one that
rewards narrowing most — a dozen mutations against a whole file is minutes
where one group is seconds. Pass `-k`:

```bash
bin/mutate private/app/<bundle>/lib.py private/tests/test_<app>.py \
           /tmp/rules.mut -k "contact_field"
```

Narrowing there is safe in the direction that matters. It can report a gap
another group would have covered — a test written twice, and cheap. It cannot
report a rule as caught when nothing caught it.

### Confirming the tests have teeth

A black-box suite earns its trust by turning red on a broken implementation.
After the rules are written, break each one deliberately and confirm a test
does. `bin/mutate` does this — see
`.claude/skills/private-service-tests/SKILL.md` for the mutations-file format:

```bash
source ~/.venv/bin/activate
bin/mutate private/app/<bundle>/lib.py private/tests/test_<app>.py /tmp/rules.mut
```

It reports `caught`, `NOT CAUGHT`, or `could not apply` — the last meaning the
target string matched zero or several places, so nothing ran. Narrow the target
and run it again.

The tool handles two traps. A target has to match exactly once to be replaced
unambiguously. And Python invalidates a `.pyc` on the source's mtime and size,
both coarse enough that an equal-length edit inside one second leaves a stale
one behind, so the tool clears bytecode between mutations and writes none.

