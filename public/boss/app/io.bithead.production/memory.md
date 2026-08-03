# Session Memory — Production

Stages 1–5 are complete. 56 routes wired to `lib`, every one carrying `@require_admin()` or `@require_user()` and translating a rule's refusal into 409/400. 22 test groups pass.

Stage 5's client reconciliation is done and enforced by `bin/validate-app` (`[models]`).

**Next: exercise it against a running service.** Nothing here has been run through nginx or a browser — the routes are proven only by a smoke test that mounts the router over ASGI, and no screen has been drawn against real data.

The design lives in `private/app/io.bithead.production/plan.md`. The layering, model, and testing rules are general and live in `docs/prompt/python.md` §19–20 and `docs/prompt/process.md`. Neither is repeated here.

This app is the reference implementation for future generations. Where it disagrees with a document, one of them is wrong — say which.

## Where things are

```
private/app/io.bithead.production/
  __init__.py   56 routes: auth, call a rule, return what it gives back
  db.py         schema + every SQL statement + row models
  model.py      domain models: Records, Screens, Input models
  lib.py        row→domain converters, then the rules
  tokens.py csvimport.py events.py export.py
private/tests/test_production.py
public/boss/app/io.bithead.production/controller/*.html   19 controllers
```

## Watch out for

- **`addNewOptions` auto-selects option 0** and fires `didSelectListBoxOption`. Set the delegate before loading data, and expect a transient render of option 0 before an explicit `selectOption(...)`.
- **Removing a menu option requires a `value` attribute** on the `<option>`. File menus use `value="save|delete|cancel"` so create-mode can drop Delete.
- **A section's image uploads only after the section exists.** `Section.html` holds the file in `pendingFile` and uploads once the create call returns an id.
- **The dashboard's operator table is a `<table>`, not a `ui-list-box`** — a list box option is plain text and cannot carry a status dot plus six columns.
- **Tokens are rendered server-side only.** The client holds no interpolation code; `ManufacturingLine` gets rendered sections and `Operation`'s preview calls `GET /operation/{id}/preview`. An absent key renders the token literally, a key holding nothing renders empty, and that distinction is the whole design.
- **A frozen version forks on edit**, so operation and section ids change. Every mutating production-line call returns `forked`; when it is true the controller reloads the whole form.
- **`/line/{id}/pause·resume·stop·resume-line·leave` serve both the dashboard and the floor.** The caller decides the origin, which is what makes "only the origin that raised a block may clear it" work without separate routes.
- **Run the mutation check with `PYTHONDONTWRITEBYTECODE=1`.** Python invalidates a `.pyc` on mtime and size, both coarse, so an equal-length edit inside one second leaves stale bytecode that silently keeps running the mutation. Symptom: a test fails consistently while the file on disk is provably correct.

## Open

1. `POST /section/{id}/image` has never been run. `store_section_image` creates `public/upload/io.bithead.production/` on first use.
2. `delete_pool()`'s checked-out-resource guard is unreachable through the interface — a resource can only be held from a pool some version requires, and that reference blocks the delete first. Kept as a safety net, labelled in place.
