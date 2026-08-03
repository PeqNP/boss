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
- Parameter order: endpoint params (path/body) → `boss_user: User` → `request: Request`
- Import `from lib.model import User` if not present
- Return empty `{}` or use `Fragment.OK` equivalent for empty responses
- Keep module-local model names concise. Prefer `ModelResponse` over `VisualizerModelResponse`.

### Service startup and shutdown

Private app modules may expose `start()` and `shutdown()` functions. `private/api.py` calls `start()` when the service boots and before routes begin handling requests.

**Rules:**
- Perform one-time database initialization in `start()`.
- Create or verify the SQLite database file, tables, indexes, and similar storage prerequisites in `start()`, not lazily inside request handlers.
- Store service database files under the shared `db_path` from `lib.get_config()`, not alongside the Python source files.
- **Close every database connection in a `finally`.** A statement that fails leaves its connection holding SQLite's write lock; if it is never closed, every later write in the process fails with `database is locked`, and one rejected request bricks the service until it restarts. This cannot be caught by a test — CPython closes the connection when the frame dies — but a web server retains the traceback of a failed request, the traceback holds the frame, and the frame holds the connection. The `finally` is load-bearing in production and invisible in the suite.
- Keep request handlers focused on request work. Place schema creation and bootstrap logic outside route handlers.
- For small private services, keeping a few database helper functions in `__init__.py` is acceptable; a separate `db.py` module is optional, not required.
- `shutdown()` may remain empty until the service has actual teardown work.

---

## 16. Lessons Learned — Private Python App Hardening

These are practical guardrails learned while implementing and debugging `io.bithead.lean-visualizer`.

### Route and prefix conventions

- Define a bundle-scoped router prefix for private APIs, e.g. `router = APIRouter(prefix="/api/io.bithead.lean-visualizer")`.
- Keep route decorators relative to that prefix (e.g. `@router.get("/sync-jira")`) to avoid duplicate or mismatched paths.
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
- Put every SQL statement in `db.py`, one function per query, named for what it means rather than what it selects — `get_active_jobs()`, `claim_next_work_unit()`. The whole data surface of the app then reads in one place, which is also the surface a security review has to check.
- Verify with `grep -nE "SELECT |INSERT |UPDATE |DELETE " <bundle_id>/{lib,export,...}.py`, which should return nothing.
- Keep business rules in `lib.py` taking and returning values. A rule that accepts a `Request` cannot be called from a test.
- Emit notifications from routes, not from rules. `lib.server.send_events` needs the request to carry the caller's credentials, so the route calls its rule and then announces the result.
- Raise domain exceptions from rules — `RecordNotFound`, a `Blocked` that names what stands in the way, a `ValidationError` carrying a message meant for the user. Routes translate them into `HTTPException`. Rules stay free of HTTP.

### Models

Both families are Pydantic `BaseModel`s, in the two places described in `process.md` — *Network and Domain Models*. `db.py` declares its own row models and never imports `model.py`; `lib.py` imports both and converts.

```python
# db.py — network. One per query shape, spelled as the columns are.
class JobRow(BaseModel):
    id: int
    name: str
    production_line_id: int
    active: int                 # SQLite has no boolean

def get_job(job_id: int) -> Optional[JobRow]:
    rows = select("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return JobRow(**rows[0]) if rows else None


# model.py — domain. camelCase, shaped by whoever reads it.
class Job(BaseModel):
    id: int
    name: str
    productionLineId: int
    active: bool

class JobDetail(Job):           # the detail screen reads more than a rule does
    workUnitCount: int
    contract: JobContract


# lib.py — the app layer owns the conversion, once per concept.
def _job(row: db.JobRow) -> Job:
    return Job(id=row.id, name=row.name, productionLineId=row.production_line_id,
               active=bool(row.active))
```

**Rules:**
- Declare a row model's fields as the columns are spelled, so `JobRow(**rows[0])` is the whole conversion from storage. A row model needing field-by-field assignment is misdeclared.
- Write one converter per concept in `lib.py`. Rules then work in attributes, and a mistyped column fails inside the converter rather than as a `KeyError` three calls later.
- A query returning one column returns `List[int]` or `List[str]`. Do not wrap a scalar in a model.
- Return the domain model itself from a route, declared as `response_model=`. Calling `model_dump()` first discards the validation the declaration bought.
- Group request bodies in `model.py` under an `# --- Input models ---` heading. They are domain models: the client dictates their shape as surely as it dictates a response's.

---

## 20. Testing Private Services

Tests are the consumer. They define the interface, and the implementation answers whether it can supply that output from that input. When it cannot, the interface grows a call — never a peek at storage.

**Rules:**

- Write tests against `lib.py` and the response models, black box. A test builds its situation and checks its outcome through the same calls the client makes.
- Build state the way a user does. Import work through the import path, create records through the save calls, put an item in progress by claiming it. A row inserted directly can describe a situation the app cannot reach, and a test that asserts against one proves nothing.
- Read state through response models. When a test needs something it cannot see, add the read model that the screen showing it would need. That model is required by the client eventually, so writing it now costs nothing and finishes the interface early.
- Keep SQL out of the test file. Verify with `grep -n "SELECT \|INSERT \|db\.select\|db\.update" private/tests/test_<app>.py`.
- Name each block with the situation and each assertion with the behaviour, so a failure reads as a sentence:

```python
    # describe: a required field left blank
    with pytest.raises(ValidationError):
        complete_operation(OPERATOR, unit, 1, {"serial": ""}, "")

    # describe: the last step
    assert complete_operation(OPERATOR, unit, 2, {"led_ok": True}, "")["unitComplete"] is True
    assert get_line_detail(line)["unitsCompleted"] == 1, "it: credits the operator"
```

- Point the app at a test database (`db.set_database_name("test-<app>.sqlite3")`) and recreate it per group, so a run never touches real data.

### Exceptions

A rule about elapsed time is the usual one: throughput over a trailing window needs records already in the past, and no interface call can manufacture a past. Where an exception is genuinely required:

- Put the storage-aware helper in the test file under a banner comment naming why it exists.
- Give it one job and use it from the one test that needs it.
- Say so when reporting the work, so the exception stays visible rather than becoming a precedent.

### Confirming the tests have teeth

A black-box suite that passes on a broken implementation is worse than none. After the rules are written, break each one deliberately and confirm a test turns red:

```bash
export PYTHONDONTWRITEBYTECODE=1                              # see the warning below
cp lib.py lib.py.orig
perl -pi -e "s/if not _is_true\(value\):/if False:/" lib.py   # required field no longer enforced
private/run_tests.sh private/tests/test_<app>.py              # expect a failure
mv lib.py.orig lib.py
```

**Set `PYTHONDONTWRITEBYTECODE=1`, or clear `__pycache__` afterwards.** Python invalidates a `.pyc` on the source's modification time *and size*, both coarse: mtime is whole seconds, and a mutation like `THEN 0` → `THEN 9` does not change the length. A mutate-run-restore cycle finishing inside one second therefore leaves bytecode compiled from the mutated source looking valid, and every later run silently executes the mutation. The symptom is a test that fails consistently while the file on disk is provably correct.

Restore with a file copy. `git checkout <file>` reverts to the last commit, which discards uncommitted work in that file — including the implementation being tested.

