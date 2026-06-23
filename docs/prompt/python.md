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

---

