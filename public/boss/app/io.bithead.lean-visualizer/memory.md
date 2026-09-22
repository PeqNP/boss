# Lean Visualizer Memory

Lean Multi-Track Production Simulator: a release-forecasting board backed by Jira.
Shipped and in daily use. The spec is [description.md](description.md). The contract
is [plan.md](../../../../private/app/io.bithead.lean-visualizer/plan.md). Every route
requires a role. Stage 1 screens match the plan and are waiting on a look.
`index.html` is gone. Next, after that look, is Stage 3, the routes. This slice
has no OS work.

`index.html` is the old page. Stage 1 deletes it. It is not a client, and no route
stays open so that it can keep calling. The plan decides the windows and the routes.

## Architecture

The BOSS app is this bundle: `application.json`, sign-in, and ACL. The windows
load stub data. The routes they name are not wired yet.

### Public half

- The product UI is the controllers named in the plan. A feature keeps its own color.
  The rest of the chrome is the BOSS desktop.
- Server calls go through `os.network` with the signed-in session.
- A value edited inside the operators, tracks, or backlog table is an `.edit-label` in `lean.css`: a dotted underline, a tap turns it into a text field, and a commit turns it back into a label. Fields outside those tables stay text fields. Feature names, total units, and completed units come from Jira and are not edited. A Jira key is an `a.jira-key`.

### Private half

- One module: [`private/app/io.bithead.lean-visualizer/__init__.py`](../../../../private/app/io.bithead.lean-visualizer/__init__.py),
  exposing `router = APIRouter(prefix="/api/io.bithead.lean-visualizer")`, auto-discovered
  by `private/api.py`, served on 8082, proxied by nginx `location /api`.
- The module is one file today. The plan splits it into `model.py`, `lib.py`, and `db.py`
  when the rules are written.
- Every route requires an Admin or an Employee. Paths that already exist keep their paths.
  Added routes are `GET /me`, `GET /schedule`, `GET /report`, and `POST /checkpoints`.
- Storage: SQLite at `<db_path>/lean-visualizer.sqlite3`, where `db_path` comes from
  `~/boss/config` — never alongside the source. Tables: `versions`, `visualizer_models`
  (one row, `MODEL_ID = "default"`, carrying `schema_version` and `revision`),
  `visualizer_operator_metrics`, `visualizer_operator_metric_tasks`.
- Secrets live in `config.json` beside the module (gitignored; see `config.json.example`):
  Jira URL, account email, API key, `fr_board_id`, `planned_board_names`,
  `unplanned_board_names`.
- `require_acl` is the guard, the same mechanism Scheduler uses. A caller with no role
  is refused.

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

## Running it

- Python is `bin/restart` when `private/**` changed or 8082 is quiet. Never stand
  up a substitute. See `shared.md` § Running and Validating Locally.
- Syntax-check the private module before asking for a restart:
  `source ~/.venv/bin/activate && python3 private/app/io.bithead.lean-visualizer/__init__.py`.
- `index.html` is retired. Do not add a path, a flag, or an open route so that it keeps working.
