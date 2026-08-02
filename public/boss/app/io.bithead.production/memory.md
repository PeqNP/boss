# Session Memory — Production

## Last updated: 2026-08-02

Stages 1 (UI/UX), 2 (data model), and 3 (tests) are complete. Stage 4 (implementation) is next.

## Key files

- Plan (the contract for every stage): `private/app/io.bithead.production/plan.md`
- Controllers: `public/boss/app/io.bithead.production/controller/*.html` (19 files)
- Stylesheet: `public/boss/app/io.bithead.production/production.css`
- Stub API: `private/app/io.bithead.production/__init__.py` (router prefix `/api/io.bithead.production`)
- Schema: `private/app/io.bithead.production/db.py` — 18 tables, created by `start()` on service load
- Tests: `private/tests/test_production.py` — 14 groups, red until Stage 4
- Stage 4 modules, signatures only: `lib.py`, `tokens.py`, `csvimport.py`, `events.py`, `export.py`
- Registered in: `public/boss/app/installed.json`

## Model hierarchy

```
Pool (global) ──< PoolResource                    exclusive; one holder at a time
ProductionLine ──< ProductionLineVersion ──< Operation ──< Section ──< Option
                        │                                    (6 types)
                        ├──< declared work unit columns
                        └──< required pools ──> Pool
Job ──> ProductionLine, pinned ProductionLineVersion (pinned at Start)
Job ──< WorkUnit ──< WorkUnitOperation ──< WorkUnitValue
Job ──< JobLine (one permanent row per job+operator) ──< LineEvent
```

## Conventions established

- **Admin = BOSS super user only.** Client gates on `os.isSuperUser(os.user)`; `GET /me` returns `isAdmin`. Server uses `@require_admin()` (which is `user.id == 1`).
- **`configure()` parameter order**: parent ID before child ID. Controllers with ≥3 params use a `<Name>Config` *function* (not class) — `OperationConfig`, `SectionConfig`, `ResourceConfig`, `LineBlockedConfig`.
- **Terminology**: *Production Line* = the versioned template. *line* = one operator's virtual line on one job (`job_lines`, one permanent row per job+operator, never deleted — it carries metrics).
- **Versioning**: editing a frozen version forks a new one server-side. Every mutating production-line endpoint returns `versionId` and `forked`; when `forked` is true the controller must **reload the whole form**, because operation and section IDs changed.
- **Interpolation** lives in `Application.html` as `interpolate(text, context)` / `parseTokens(text)` / `renderValue(value)`, reachable from any controller via `$(app.controller).interpolate(...)` (the app proxy falls through to the `Application.html` instance). `tokens.py` must mirror it exactly.
  - Namespaces: `{work_unit.Col}`, `{operation.N.name}`, `{pool.Pool Name}`.
  - Column and pool names match case-insensitively and may contain spaces; section names are strict identifiers.
  - **Absent key renders the token literally; a key that exists with no value renders empty.** The helper distinguishes these with `value === undefined`, deliberately *not* `isEmpty` — this is an absence check, not an emptiness check.
  - Backward references only; validated on production line save.

## Gotchas discovered

- **Disabled list box options.** `UIListBox` gained `disableOption` / `enableOption`, and `addNewOptions` honours a `disabled` field on the model. `ManufacturingLine` uses that field to grey out steps beyond the one being worked: a disabled option cannot be selected, so its description cannot be opened, and no guard code is needed.
- **`addNewOptions` auto-selects the first option** and fires `didSelectListBoxOption`. Set the delegate before loading data, and expect a transient render of option 0 before an explicit `selectOption(...)`.
- **The dashboard's operator table is a `<table>`, not a `ui-list-box`.** A list box option is plain text and cannot carry a blinking status dot plus six columns. The table uses `class="prod-selectable"` with row `onclick` for selection and keeps the visual model-table layout (rows left, `controls-right separated` on the right).
- **Removing a menu option requires a `value` attribute** on the `<option>`. All File menus give their options `value="save|delete|cancel"` so create-mode can drop Delete.
- Images upload only after the section exists (`POST /section/{id}/image`), so `Section.html` holds the chosen file in `pendingFile` and uploads it after the create/update call returns an ID.
- `os.network.upload(url, file, body)` posts multipart with the field name `file`.

## Stage 2 notes

- The schema follows `plan.md` exactly; no drift was found between it and what Stage 1 built.
- `get_conn()` sets `PRAGMA foreign_keys = ON` per connection. SQLite defaults it **off**, and the schema depends on `ON DELETE CASCADE` — deleting a job must take its work units, lines, and logs.
- Two deliberate FK cycles: `pool_resources.held_by_line_id` → `job_lines`, and `production_lines.current_version_id` → `production_line_versions`. SQLite resolves FK targets at statement time, so creation order does not matter.
- `update()` returns the rows changed rather than raising on zero. Claiming a work unit another operator already took is an outcome, not an error — Stage 4's atomic claim depends on this.
- Verified on creation: case-insensitive pool-name uniqueness, one line per job+operator, FK enforcement, the queue ordering expression (requeued → partial → CSV order), and job deletion cascading to units/lines/logs.

## Stage 3 notes

- Run with `private/run_tests.sh private/tests/test_production.py` after `source ~/.venv/bin/activate`.
- All 14 groups fail with `NotImplementedError`. That is the expected state until Stage 4 — a failure for any other reason is a real problem.
- Tests build state with `db.insert` through small builders (`make_pool`, `make_line`, `make_job`, …) rather than through `lib`, so each test exercises one rule against a known database instead of depending on rules that are themselves unwritten.
- `db.set_database_name("test-production.sqlite3")` then `delete_database()` / `start_database()` isolates every group; the real database is never touched.
- The signatures in `lib.py` are the contract the tests were written against. Changing one means changing its tests — treat the pair as one edit.
- `test_capacity_planner.py` fails for an unrelated reason: it references an app bundle that does not exist. That predates this work.

## How to validate this app

```bash
bin/validate-app io.bithead.production      # registration, syntax, handlers, API, routes
source ~/.venv/bin/activate                 # then exercise the private service
```

The one-off scripts written during Stage 1 were folded into `bin/validate-app`; do not re-improvise them. Look up BOSS methods in `docs/prompt/js-api.md` (grouped by component) rather than grepping `ui.js`.

## Stage 1 verification performed

- Controllers on disk ↔ `application.json` — exact match, 19 controllers.
- All controller `<script>` bodies pass `node --check` after resolving `$(...)` template commands.
- All 65 `os.network.*` calls resolve to a declared stub route (the two "unmatched" are `${action}` template calls covering pause/resume/stop/resume-line).
- All 26 distinct BOSS API methods called exist in `ui.js` / `network.js` / `os.js` / `foundation.js`.
- Fixture data in `__init__.py` self-validates: input sections all carry token names, description/image sections carry none, and every token in the fixtures resolves against the declared contract with no forward references.
- `interpolate()` unit-tested against 19 cases (namespaces, case-insensitivity, checkbox rendering, empty vs. absent, multi-token, multiline).

## Open items carried into Stage 2+

1. Auth decorators are **not** applied to the stub routes yet — see the `SECURITY TODO(Stage 4)` banner in `__init__.py` and the Stage 5 checklist.
2. CSV upload preview storage/TTL (in-process dict vs. table).
3. Shared floor-terminal operator identity (sign-out/sign-in as the hand-off).
4. Closing stale open `line_events` intervals after a service restart.
