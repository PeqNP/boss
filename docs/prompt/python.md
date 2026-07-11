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
- Use `@require_user()`, with parentheses, when the request requires an authenticted `User`. Unprotected routes don't need this.
- Parameter order: endpoint params (path/body) → `boss_user: User` → `request: Request`
- Import `from lib.model import User` if not present
- Return empty `{}` or use `Fragment.OK` equivalent for empty responses
- Keep module-local model names concise. Do not namespace model class names with redundant app/module prefixes (for example, prefer `ModelResponse` over `VisualizerModelResponse`).

### Service startup and shutdown

Private app modules may expose `start()` and `shutdown()` functions. `private/api.py` calls `start()` when the service boots and before routes begin handling requests.

**Rules:**
- Perform one-time database initialization in `start()`.
- Create or verify the SQLite database file, tables, indexes, and similar storage prerequisites in `start()`, not lazily inside request handlers.
- Store service database files under the shared `db_path` from `lib.get_config()`, not alongside the Python source files.
- Keep request handlers focused on request work; do not hide schema creation or bootstrap logic in route code.
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

