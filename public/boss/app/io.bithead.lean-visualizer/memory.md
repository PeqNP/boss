# Lean Visualizer Memory

Lean Multi-Track Production Simulator: a release-forecasting board backed by Jira.
Shipped and in daily use. The spec is [description.md](description.md). The built
contract is [01-plan.md](../../../../private/app/io.bithead.lean-visualizer/plans/01-plan.md).
The open feature plan is [02-c-level-reporting.md](../../../../private/app/io.bithead.lean-visualizer/plans/02-c-level-reporting.md).
Stage 1 is built: the Report material-changes section and the Blockage document,
Stage 5 points Save Snapshot and the report at `POST /snapshots` and
`GET /material-log`. Stage 2 is done:
migration `1.1.0` creates the priority snapshot tables. The model schema
version stays `1`. Stage 3 is done: `test_snapshot` covers the diff, and
`take_snapshot` implements it. Stage 4 is done: `GET /report` no longer
returns the fourteen-day change list. Next is Stage 6, confirming the
snapshot rules stay in `lib/snapshot.py`. Every route
requires a role. The routes are live and the board, schedule, report, and
checkpoint call them. The rate, the schedule, pillars, the board save, the
fourteen-day change, who may call a route, and checkpoint credits are tested.
A checkpoint save pulls the issues the weekly sync would count for that
release window. Tasks and Finished Work call their routes.
Stage 7 is complete. The private service is a package: `model.py` for the
shapes, `db.py` for the database and every SQL statement, and `lib/` for the
rules. Routes stay in `__init__.py`. No two models share a field set.
`PillarFinished` stays apart from `PillarOpen`, and `SaveModelRequest` stays
apart from `ModelResponse`. Step 8 is complete. All five flows in `ui-plan.md` have a spec.
A spec must not reset the live board and must not add `create_schema`.
Flows that replace the board write the previous state back with
`PUT /model`. Finished work in a spec names the fixture `finished-work-empty`
through `PUT /api/debug/uitests/jira/{bundle}`, cleared when the spec ends.
An Employee granted from Settings is refused until the app is on their
session. This slice has no OS work.

`index.html` is the old page. Stage 1 deletes it. It is not a client, and no route
stays open so that it can keep calling. The plan decides the windows and the routes.

## Architecture

The BOSS app is this bundle: `application.json`, sign-in, and ACL. Board,
Schedule, Report, Checkpoint, and Task Metrics call the live routes. Task Metrics
is a line per operator, five weeks at a time, from `GET /metrics-window`. The
schedule chart places each feature by its start and finish, and a release in
that horizon is a vertical line across the rows. Unpinned backlog items are
dealt in list order across the enabled tracks. A track that any feature pins
itself to, such as DevOps, only receives features pinned to it. Tasks lists the stored issues for the week under inspection. Finished Work lists
the year's completed epics from Jira, one operator at a time.

### Public half

- The product UI is the controllers named in the plan. A feature keeps its own color.
  The rest of the chrome is the BOSS desktop.
- Board opens fullscreen: `ui-window fullscreen`, with a zoom button. The OS moves that class onto the window container and fills the desktop.
- Server calls go through `os.network` with the signed-in session.
- A value edited inside the operators, tracks, or backlog table is an `.edit-label` in `lean.css`: a dotted underline, a tap turns it into a text field, and a commit turns it back into a label. Fields outside those tables stay text fields. Feature names, total units, and completed units come from Jira and are not edited. A feature name on a track or in the backlog clips at 30 characters. The cell is the issue key, as a link, then the name. An operator row shows that person's eight-week rate, planned plus unplanned, to two decimal places. Remaining weeks is computed when the board draws; a feature from Jira does not carry that field. A Jira key is an `a.jira-key`.
- Releases is on the board's File menu, not a fieldset on the board and not on Dashboards. The modal lists the next 20 releases dated today or later and scrolls after five rows. Releases outside that 20 stay stored. Dashboards is Board and Capacity report for an Admin. An Employee sees Board, Capacity report, and Schedule, and the board is read-only: File keeps Finished work and Schedule, the report hides Save Checkpoint, and the schedule hides Manage Releases.


### Private half

- Routes live in [`private/app/io.bithead.lean-visualizer/__init__.py`](../../../../private/app/io.bithead.lean-visualizer/__init__.py),
  exposing `router = APIRouter(prefix="/api/io.bithead.lean-visualizer")`, auto-discovered
  by `private/api.py`, served on 8082, proxied by nginx `location /api`.
  Shapes are `model.py`. Statements are `db.py`. Rules are `lib/`.
- Tests set `MODEL_DB_NAME` on the app module. `get_model_db_connection` reads
  that attribute. A copy on `db` sends the suite at the live database.
- Every route requires an Admin or an Employee. Paths that already exist keep their paths.
  Added routes are `GET /me`, `GET /schedule`, `GET /report`, and `PUT /checkpoints/{releaseId}`.
- Storage: SQLite at `<db_path>/lean-visualizer.sqlite3`, where `db_path` comes from
  `~/boss/config` — never alongside the source. Tables: `versions`, `visualizer_models`
  (one row, `MODEL_ID = "default"`, carrying `schema_version` and `revision`),
  `visualizer_operator_metrics`, `visualizer_operator_metric_tasks`.
- Secrets live in `config.json` beside the module (gitignored; see `config.json.example`):
  Jira URL, account email, API key, `fr_board_id`, `planned_board_names`,
  `unplanned_board_names`.
- `require_acl` is the guard, the same mechanism Scheduler uses. A caller with no role
  is refused. The module must not postpone annotations. `require_acl` matches
  `boss_user: User` by the class, and a postponed annotation is the string
  `"User"`, so FastAPI asks for a body and `GET /me` answers 422.

### Contract between the halves

- Model persistence: `GET /model` returns state plus `revision`; `PUT /model` sends
  `schemaVersion` and the last `revision` for write coordination. Canonical keys are
  `operators`, `tracks`, `backlog`, `releases`, and `weeklyNotes`. Pillars are not one of them.
- Autosave fires on committed mutations only — never while typing in an inline editor —
  and after Jira sync mutates the model. A load must not look like a save; status settles
  to `Ready`.
- Task metrics are a separate store, keyed by operator name + metric year + week number.
  They feed the read-only operator metrics table and forecasting; they are not part of
  the saved model.
- Jira query construction is backend-owned. "Copy Jira Query" reuses the exact JQL string
  the backend built for the sync; the frontend must never rebuild it.
- Weeks are Sunday–Saturday. The default viewed/synced week is the previous full week;
  navigation forward stops at the current calendar week.

## Watch out for

- Schema DDL is written twice: `migrate_to_1_0_0()` (called from `start()`) and the
  `ensure_*_table()` helpers. Change both or the two drift.
- Weekly metric sync is non-additive: it DELETEs the target week's rows before INSERT, so
  re-running after an algorithm change is safe and never accumulates stale rows.
- `release_version` holds at most one value per task row — the single `N.N.N` semver from
  Jira `fixVersions`. Zero or multiple semver matches store `''`; non-semver values
  (e.g. `Spike`) are ignored.
- `manualEstWeeks` is an override, not a fallback: `> 0` wins over the computed estimate
  even when `units > 0`, and the Est. Weeks cell turns red to flag the discrepancy.
  Clearing it or setting `0` restores computed behavior; no units and no override shows `∞`.
  Infinite durations must render dates as `—`, never as an invalid date.
- The backlog carries a system divider row (`system-sync-divider`); tasks below it are
  excluded from work-unit queries. Preserve it when touching backlog order.
- A board save must round-trip `jiraIssueType`. The old page rebuilt each feature from a
  fixed field list and dropped that field, so completed FRs stopped being retired. The
  new board has to keep every feature field the sync writes.
- FR retirement is therefore decided by Jira project membership — a feature whose issue
  key belongs to a project this sync just read, and that Jira did not return as open, is
  removed. An empty Jira result removes nothing, on purpose.
- Results and failures use the OS message with an OK button.
- Planned vs unplanned classification is by parent task presence, not board routing:
  parent present → planned, parent null → unplanned.
- Task metrics are attributed by Jira's `Developers` field only — never `assignee`. One
  issue may credit several operators, one unit each. The field must be requested by its
  custom field **id** (resolved at runtime through `/rest/api/3/field`); Jira silently
  drops a custom field named by its display name in the REST `fields` parameter, returns
  200, and the omission looks exactly like "nobody was set". The JQL clause is the
  opposite — there the quoted display name `Developers[User Picker (multiple users)]` is
  what works.

## Open

1. Schema changes need their own migration patch plus a DB version bump. Do not delete or
   recreate the database to apply one.
2. `PUT /checkpoints/{releaseId}` calls `fetch_checkpoint_issues`, the same Jira query
   as the weekly sync, for the release window. The test substitutes that function.
   Do not call Jira from a test.

## Running it

- Python is `bin/restart` when `private/**` changed or 8082 is quiet. Never stand
  up a substitute. See `shared.md` § Running and Validating Locally.
- Syntax-check the private module before asking for a restart:
  `source ~/.venv/bin/activate && python3 private/app/io.bithead.lean-visualizer/__init__.py`.
- `index.html` is retired. Do not add a path, a flag, or an open route so that it keeps working.
