# Session Memory — Production

## Last updated: 2026-07-31

Stage 1 (UI/UX with stubbed backends) is complete. Stages 2–5 have not started.

## Key files

- Plan (the contract for every stage): `private/app/io.bithead.production/plan.md`
- Controllers: `public/boss/app/io.bithead.production/controller/*.html` (19 files)
- Stylesheet: `public/boss/app/io.bithead.production/production.css`
- Stub API: `private/app/io.bithead.production/__init__.py` (router prefix `/api/io.bithead.production`)
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

- **`UIListBox` has no `disableOption`.** Only `UIMenu` and `UIPopupMenu` do. Worse, `UIListBox`'s single-select mouseup path ignores `option.disabled` entirely, so disabling would not prevent selection. `ManufacturingLine` enforces "no skipping ahead" by snapping the selection back in `didSelectListBoxOption`, guarded by a `snappingSelection` flag to avoid re-entering the delegate.
- **`addNewOptions` auto-selects the first option** and fires `didSelectListBoxOption`. Set the delegate before loading data, and expect a transient render of option 0 before an explicit `selectOption(...)`.
- **The dashboard's operator table is a `<table>`, not a `ui-list-box`.** A list box option is plain text and cannot carry a blinking status dot plus six columns. The table uses `class="prod-selectable"` with row `onclick` for selection and keeps the visual model-table layout (rows left, `controls-right separated` on the right).
- **Removing a menu option requires a `value` attribute** on the `<option>`. All File menus give their options `value="save|delete|cancel"` so create-mode can drop Delete.
- Images upload only after the section exists (`POST /section/{id}/image`), so `Section.html` holds the chosen file in `pendingFile` and uploads it after the create/update call returns an ID.
- `os.network.upload(url, file, body)` posts multipart with the field name `file`.

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
