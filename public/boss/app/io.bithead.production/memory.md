# Session Memory — Production

Stages 1–4 are complete: 19 controllers, the schema, 14 black-box test groups, and the rules behind them. **Stage 5 — wiring `__init__.py`'s 56 stub routes to `lib` — is next.**

The design lives in `private/app/io.bithead.production/plan.md`. The layering, model, and testing rules are general and live in `docs/prompt/python.md` §19–20 and `docs/prompt/process.md`. Neither is repeated here.

This app is the reference implementation for future generations. Where it disagrees with a document, one of them is wrong — say which.

## Where things are

```
private/app/io.bithead.production/
  __init__.py   routes, still returning Stage 1 fixtures
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
- **`tokens.py` must mirror `Application.html`'s `interpolate()` exactly.** An absent key renders the token literally; a key that exists holding nothing renders empty. That distinction is the whole design, and both implementations are covered by tests.
- **A frozen version forks on edit**, so operation and section ids change. Every mutating production-line call returns `forked`; when it is true the controller reloads the whole form.
- **Run the mutation check with `PYTHONDONTWRITEBYTECODE=1`.** Python invalidates a `.pyc` on mtime and size, both coarse, so an equal-length edit inside one second leaves stale bytecode that silently keeps running the mutation. Symptom: a test fails consistently while the file on disk is provably correct.

## Open

1. **Auth decorators are not applied to any route.** See the security banner in `__init__.py` and the Stage 5 checklist. This is the largest outstanding item and blocks handling real data.
2. `delete_pool()`'s checked-out-resource guard is unreachable through the interface — a resource can only be held from a pool some version requires, and that reference blocks the delete first. Kept as a safety net, labelled in place.
3. Shared floor-terminal operator identity: sign-out/sign-in as the hand-off, still undecided.
4. Stale open `line_events` after a service restart. Until this is closed, a restart mid-pause leaves an interval that throughput subtracts right up to the present.
