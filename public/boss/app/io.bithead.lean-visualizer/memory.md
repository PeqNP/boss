# Lean Visualizer Memory

Lean Multi-Track Production Simulator: a release-forecasting board backed by Jira.
Shipped and in daily use; work is incremental. Read this before touching either half —
almost every BOSS app rule assumes a structure this app does not have.

## Architecture

**This is the only app in `public/boss/app/` without an `application.json`, and that is
deliberate.** It is a standalone single-page app that does not run inside the BOSS
frontend, but it does own a BOSS private (Python) backend.

### Public half

- The entire frontend is [index.html](index.html) — HTML, CSS, and JS colocated in one
  file. No framework, no build step, no imports.
- Nothing BOSS is loaded: no `<script src>` at all, so no `ui.js`, `os.js`, or
  `network.js`. Server calls use bare `fetch`, not `os.network`.
- The bundle has only `index.html` and this file. No `application.json`, no
  `controller/`, no `icon.svg`, no `description.md`, no `scheme`, and no entry in
  `public/boss/app/installed.json`. It is never launched by the OS, has no window,
  no menu bar, and no BOSS sign-in.
- Reached directly at `/boss/app/io.bithead.lean-visualizer/index.html`. nginx serves it
  off disk (`location /` → `try_files $uri`, [dev-nginx.conf](../../../../private/dev-nginx.conf#L107));
  Vapor never sees the request and no Swift route or `bosslib` code exists for this bundle.
- Its visual language (warm paper background, orange accent, rounded cards) is
  intentional and is *not* the 1-bit System 7 aesthetic. Do not "correct" it toward BOSS UI.
- Consequences for agents: `bin/validate-app io.bithead.lean-visualizer` reports
  `application.json is missing` and always will — that error is expected, not a task.
  The app-bundle and controller rules in `docs/prompt/shared.md` §3–4 and
  `docs/prompt/js.md` do not apply to this app.

### Private half

- One module: [`private/app/io.bithead.lean-visualizer/__init__.py`](../../../../private/app/io.bithead.lean-visualizer/__init__.py),
  exposing `router = APIRouter(prefix="/api/io.bithead.lean-visualizer")`, auto-discovered
  by `private/api.py`, served on 8082, proxied by nginx `location /api`.
- Single-file layout is intentional (`docs/prompt/python.md` §15); do not split it into
  `model.py`/`lib.py`/`db.py` without a reason.
- Endpoints: `GET|PUT /model`, `GET /metrics`, `GET /metrics-window`,
  `GET /metrics-tasks`, `GET /metrics-release-work-units`, `GET /release-options`,
  `POST /sync-task-metrics`, `GET /sync-jira`, `GET /finished-work`.
- Storage: SQLite at `<db_path>/lean-visualizer.sqlite3`, where `db_path` comes from
  `~/boss/config` — never alongside the source. Tables: `versions`, `visualizer_models`
  (one row, `MODEL_ID = "default"`, carrying `schema_version` and `revision`),
  `visualizer_operator_metrics`, `visualizer_operator_metric_tasks`.
- Secrets live in `config.json` beside the module (gitignored; see `config.json.example`):
  Jira URL, account email, API key, `fr_board_id`, `planned_board_names`,
  `unplanned_board_names`.
- No authentication or ACL. `require_acl` exists in `private/lib/server.py` but is unused
  repo-wide, so anything that can reach `/api` can read and rewrite the model. See Open.

### Contract between the halves

- Model persistence: `GET /model` returns state plus `revision`; `PUT /model` sends
  `schemaVersion` and the last `revision` for write coordination. Only `operators`,
  `tracks`, `backlog`, and `releases` are canonical persisted state.
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
- Results and failures use the in-app OK-only status dialog, never `alert()`.
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

1. The private API is unauthenticated — undecided whether to adopt `require_acl` or leave
   it to network placement.
2. Schema changes need their own migration patch plus a DB version bump. Do not delete or
   recreate the database to apply one.

## Running it

- Services are started by the developer (`private/start`, `private/restart`); never start
  them yourself, and never stand up a substitute static server or stub backend.
- Syntax-check the private module before asking for a restart:
  `source ~/.venv/bin/activate && python3 private/app/io.bithead.lean-visualizer/__init__.py`.
- If backend/frontend ownership of a change is ambiguous, stop and ask.
