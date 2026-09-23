# Lean Visualizer — Implementation Plan

## Identity

- **Bundle ID:** `io.bithead.lean-visualizer`
- **App name:** Lean Visualizer
- **Deep-link scheme:** `lean`
- **Public app dir:** `public/boss/app/io.bithead.lean-visualizer/`
- **Private service dir:** `private/app/io.bithead.lean-visualizer/`
- **Test file:** `private/tests/test_lean_visualizer.py`
- **Backend:** Python (FastAPI, SQLite). Jira is the only outside service. Database file: `<db_path>/lean-visualizer.sqlite3`.
- **Reference for UI components:** `public/boss/app/io.bithead.tutorial/controller/Example.html`
- **Reference for roles:** `io.bithead.scheduler` — `Role` enum, `require_acl`, `grant_role`
- **Retired:** `index.html`. Stage 1 deletes it. No route stays open for it.
- **What is left:** every stage below. None of them has started.

## Controllers

Every controller is `public/boss/app/io.bithead.lean-visualizer/controller/<Name>.html` and is registered in `application.json`.

| Group | Windows | Modals |
|---|---|---|
| Entry | `Application` | |
| Board | `Board`, `Schedule` | `Notes`, `VirtualFeature`, `Checkpoint`, `TaskMetrics`, `Tasks`, `FinishedWork`, `PrepareRelease`, `Releases` |
| Report | `Report` | |

### Documents

None of these windows is a document. `bin/validate-app` would expect `this.document` on a controls row whose Save writes a record. The rows below are why each window is the other kind. No control is labeled Cancel, Delete, or Save as a document action.

| Window | Kind | Controls beyond a plain close |
|---|---|---|
| `Board` | Control panel. Every committed edit saves, so a document Save would have nothing left to confirm. The File menu is written by hand: Sync Feature Requests, Finished work, Prepare Release, Save Checkpoint, Schedule. The board has no `controls` row, so the OS does not generate that menu. | The controls of the old board, apart from the up and down row buttons. Order is a grab handle on the row. |
| `Schedule` | View of the forecast | — |
| `Report` | Report | Save Checkpoint, and only for an Admin |
| `Checkpoint` | Modal. Pick a release and store it. | Cancel, Save Checkpoint. Save Checkpoint is this action, not a document Save. |
| `Notes` | Modal over one week of the board. Save writes that week into the board and the board save runs. | Cancel, Save |
| `VirtualFeature` | Modal over one backlog item. Save writes it into the board and the board save runs. | Cancel, Save |

### Drafts

No document creates a row on open. `Notes` and `VirtualFeature` edit the board payload and persist through `PUT /model`.

## Roles & Access

One board. The scope is that board, and it is not a segment of the path. The token's role is the check.

| Actor | Told by | Scope | Reaches | Narrowed by |
|---|---|---|---|---|
| Admin | BOSS role `Admin` | the one board | the editor, the syncs, the checkpoint, the schedule, the report | — |
| Employee | BOSS role `Employee` | the one board | the schedule and the report | read only |

Roles are registered by `require_acl` and granted in BOSS Settings. This app does not grant them itself. There is no row in this database that links a BOSS account to an operator.

```python
class Role(str, Enum):
    ADMIN = "Admin"
    EMPLOYEE = "Employee"
```

### Who reaches each page

**Admin** — the token role is `Admin`.

| Page | Reached by |
|---|---|
| `Board` | the app opening on `Admin` |
| `Notes` | the board |
| `VirtualFeature` | the board |
| `Checkpoint` | the board, or the report |
| `Releases` | Go |

**Employee** — the token role is `Employee`.

| Page | Reached by |
|---|---|
| `Report` | the app opening on `Employee` |
| `Schedule` | the report |

**Shared** — one page, one read, both roles.

| Page | Audiences | The caller may reach |
|---|---|---|
| `Schedule` | Admin, Employee | the forecast of the one board |
| `Report` | Admin, Employee | the capacity report of the one board |

An Employee deep link to `Board`, `Notes`, `VirtualFeature`, or `Checkpoint` opens `Report`.

## Deep-link routing

Scheme `lean`. No `configure()` payload on the windows. `Checkpoint`, `Notes`, and `VirtualFeature` are opened by their parent with the arguments in the Stage 1 sections, not by a URL.

| URL | `configure()` | Opens |
|---|---|---|
| `lean:` | none | `Board` for an Admin, `Report` for an Employee |
| `lean:board` | none | `Board`, or `Report` when the caller is an Employee |
| `lean:schedule` | none | `Schedule` |
| `lean:report` | none | `Report` |

## Routes

Every route requires a role. A path that already exists keeps that path. A route is added only when nothing today serves the call: `/me`, `/schedule`, `/report`, `/checkpoints`.

Prefix: `/api/io.bithead.lean-visualizer`.

| Method | Path | ACL | Who |
|---|---|---|---|
| `GET` | `/model` | `board.r` | Admin |
| `PUT` | `/model` | `board.w` | Admin |
| `GET` | `/sync-jira` | `board.w` | Admin |
| `POST` | `/sync-task-metrics` | `board.w` | Admin |
| `GET` | `/metrics` | `board.r` | Admin |
| `GET` | `/metrics-tasks` | `board.r` | Admin |
| `GET` | `/release-options` | `board.r` | Admin. The next 3 releases on or after today, date ascending. |
| `GET` | `/metrics-window` | `report.r` | Admin, Employee |
| `GET` | `/metrics-release-work-units` | `report.r` | Admin, Employee |
| `GET` | `/finished-work` | `report.r` | Admin, Employee |
| `GET` | `/me` | the role list | Admin, Employee |
| `GET` | `/schedule` | `schedule.r` | Admin, Employee |
| `GET` | `/report` | `report.r` | Admin, Employee |
| `PUT` | `/checkpoints/{releaseId}` | `checkpoint.w` | Admin |

## Stage 1 — UI/UX

BOSS chrome. A feature's dot and its bar on the schedule use `feature.color`. A committed edit saves. Typing in a field does not. A load is not a save. Results and failures use the OS message with an OK button.

The forecast comes from `GET /schedule`. Schedule draws it. The board opens that window from the File menu.

Menu, Admin: **Board**, then **Report**. Board is the model the report hangs off. Menu, Employee: **Report**, then **Schedule**.

### `Application`

Audience: anyone who can open the app. A caller with neither role sees the OS sign-in failure and no window.

On start, `GET /me`. `Admin` opens `Board`. `Employee` opens `Report`. Sign out returns to the desktop.

```
GET /me -> Me
    acl:   (none — the role list is the guard)
    who:   Admin, Employee
    scope: the role on the token
```

### `Board`

Audience: Admin.

One window. It opens fullscreen. Operators, the week under inspection, tracks, and the backlog. Releases is a Go menu item. File opens Schedule for the 180-day chart.

Operators, tracks, and the backlog are tables. A row is reordered by its grab handle. BOSS drag-reorder is the sortable list box, and that control is one label per row, so it is not the board table. The up and down buttons are not on the board.

Operators: name, units, planned, unplanned, waste, the eight-week rate of planned plus unplanned, track, and Remove. The rate and its total show two decimal places. A value edited inside the operators, tracks, or backlog table is an `.edit-label`: dotted underline, a tap turns it into a text field, and a commit turns it back into a label. A field outside those tables stays a text field. Feature names come from Jira and are not edited. The color circle sits on the same line as the name. A Jira key links to `config.jiraRootUrl` plus `/browse/` and the key. Track, the backlog's pinned track, Move To Track, and Add To Track are pop-up menus. A column name stays on one line and shows the full name on hover. A feature name on a track or in the backlog clips at 30 characters and shows the full name on hover. The feature cell is `issueKey: name` when the feature has a key, and the key is the link. Sync Task Metrics and Copy Jira Query sit on their own row. The week controls sit under that row. Add Operator, View Task Metrics, View Tasks, and Notes sit under the week controls. The last row of the operator table is the totals, with a black line above it, and it stays last when an operator is added. Total enabled capacity sits under that table. The week under inspection moves to the previous complete week and stops at the current week.

Tracks: the name is edited in the row. Enabled, the feature, its key, units, completed units, the rate, remaining weeks, est. weeks, and the date. Units and completed units come from Jira and are read-only. Est. weeks is an `.edit-label` override. Backlog → and Delete act on the feature. Add Track appends one.

Backlog: features, virtual features, dividers, and the system divider `system-sync-divider`. A feature's color is a circle. Units and completed units are read-only. Est. weeks is an `.edit-label` and shows in the danger color when it overrides a feature that has units. Pin a track, or choose Move To Track. Add divider is here. A virtual feature opens `VirtualFeature`.

Releases is not on this window. Go opens `Releases`. Nothing here creates a checkpoint.

Sync Feature Requests reads `GET /sync-jira`, merges the issues into the board, keeps `jiraIssueType`, and saves. The sync stores pillars beside the board. They are not fields on the feature in the board JSON.

Save Checkpoint opens `Checkpoint`. Finished work opens `FinishedWork`. Prepare Release opens `PrepareRelease`. View Task Metrics opens `TaskMetrics`. View Tasks opens `Tasks`. Schedule opens `Schedule`.

Notes opens `Notes` for the week under inspection. A virtual feature row opens `VirtualFeature`.

State: load board, the week, and the schedule. A committed edit sends `PUT /model` with `schemaVersion` and `revision`. A `409` reloads the board and tells the admin it was saved somewhere else. Sync Feature Requests is `GET /sync-jira`, then merge, then `PUT /model`. Sync Task Metrics is `POST /sync-task-metrics`, then the week and the schedule reload.

```
GET /model -> Board
    acl:   board.r
    who:   Admin
    scope: the one board

PUT /model -> Board
    acl:   board.w
    who:   Admin
    scope: the one board. Body carries schemaVersion, revision, and state.
           409 when revision does not match.

GET /sync-jira -> FeatureSync
    acl:   board.w
    who:   Admin
    scope: the one board. Stores pillars beside the board. Does not write the board.

POST /sync-task-metrics -> TaskMetrics
    acl:   board.w
    who:   Admin
    scope: the one board. Body or query: weekStart. Replaces that week.

GET /metrics -> TaskMetrics
    acl:   board.r
    who:   Admin
    scope: the one board. Query: weekStart.

GET /metrics-tasks -> TaskMetricTasks
    acl:   board.r
    who:   Admin
    scope: the one board. Query: weekStart. jiraQuery is the string Copy Jira Query uses.

GET /schedule -> Schedule
    acl:   schedule.r
    who:   Admin, Employee
    scope: the one board
```

### `Schedule`

Audience: Admin and Employee.

The 180-day chart from `GET /schedule` is drawn above the track table. One row per track. A bar is positioned by its start and finish, in `feature.color`. Unpinned backlog items are taken in array order, which is their priority, and dealt in turn across the enabled tracks. A track that any feature pins itself to is left out of that deal and receives only the features pinned to it. A release inside the horizon is a vertical line across every row, labeled on the axis. The table under the chart names the track, its rate, and the feature on it. Manage Releases opens `Releases`. `didChangeReleases` redraws the chart.

State: load, show. A release added in the modal updates the chart.

```
GET /schedule -> Schedule
    acl:   schedule.r
    who:   Admin, Employee
    scope: the one board
```

### `Report`

Audience: Admin and Employee. Read only, except the Admin's Save Checkpoint.

Four sections, in this order:

1. Planned versus unplanned, per operator, for the last eight complete weeks, and for every stored week from 28 December 2025.
2. Allocation by strategic pillar. Open remaining units. Every pillar is a row, including a pillar with nothing open: Growth / Acquisition, New Features / Retention, Tech Debt / Stability, Process Efficiency / Cost Savings, and Unassigned. A feature with two pillars counts in each. Virtual features are not in this section. Finished feature requests are the Finished Work window.
3. Tracks and available capacity: the track's rate, the feature on it, the date it frees, the features waiting.
4. Material changes since the last checkpoint: features whose forecasted finish moved by fourteen days or more. Empty until a checkpoint exists.

Save Checkpoint opens `Checkpoint`. After it saves, the report reloads.

```
GET /report -> Report
    acl:   report.r
    who:   Admin, Employee
    scope: the one board
```

### `Checkpoint`

Audience: Admin. Modal. Parent passes the releases from `Board`.

Lists releases whose date is today or earlier. A later release is not listed. Save sends that release id. The server refuses a future date with `409` even if the client listed it. Success closes the modal. The report reloads through `didSaveCheckpoint`.

```
PUT /checkpoints/{releaseId} -> Checkpoint
    acl:   checkpoint.w
    who:   Admin
    scope: the one board. The release id is the path.
           409 when the date has not arrived, or the release is not on the board.
           Saving the same release again replaces that checkpoint.
```

### `Notes`

Audience: Admin. Modal. `configure({ weekStart })`.

One text for that week. Cancel closes without a save. Save sets `weeklyNotes[weekStart]` and `PUT /model`.

```
PUT /model -> Board
    acl:   board.w
    who:   Admin
    scope: the one board
```

### `VirtualFeature`

Audience: Admin. Modal. `configure({ id })` edits. No id creates.

Fields: name, JQL. Cancel closes without a save. Save writes the backlog item and `PUT /model`.

```
PUT /model -> Board
    acl:   board.w
    who:   Admin
    scope: the one board
```

### `TaskMetrics`

Audience: Admin. Modal. Close. A line for each operator, weeks across and completed tasks up. Previous 5 Weeks and Next 5 Weeks move that window. Next does not pass the current week.

```
GET /metrics-window -> MetricsWindow
    acl:   report.r
    who:   Admin, Employee
    scope: the one board
```

### `Tasks`

Audience: Admin. Modal. Close. One tab per operator for the week under inspection. The task table shows five rows and scrolls.

```
GET /metrics-tasks -> TaskMetricTasks
    acl:   board.r
    who:   Admin
    scope: the one board. Query: weekStart.
```

### `FinishedWork`

Audience: Admin. Modal. Close. A year, then one tab per operator.

```
GET /finished-work -> FinishedWork
    acl:   report.r
    who:   Admin, Employee
    scope: the one board
```

### `PrepareRelease`

Audience: Admin. Modal. Close. A release is chosen, then its completed issues are listed.

```
GET /release-options -> ReleaseOptions
    acl:   board.r
    who:   Admin
    scope: the one board

GET /metrics-release-work-units -> ReleaseWorkUnits
    acl:   report.r
    who:   Admin, Employee
    scope: the one board. Query: releaseVersion.
```

### `Releases`

Audience: Admin. Opened from Go. Modal. Close. Version and date are edited here. Delete removes one. The table lists the next 20 releases dated today or later, and scrolls after five rows. A release outside that 20 stays stored and is not listed. This is the board's release list, saved with `PUT /model`. It is not a checkpoint.

## Stage 2 — Data Model

Live database stays. Migration `1.1.0` adds the three tables below. `1.0.0` and its four tables stay: `versions`, `visualizer_models`, `visualizer_operator_metrics`, `visualizer_operator_metric_tasks`. Tests use `test-lean-visualizer.sqlite3` and create it themselves. Nothing in this slice deletes the live file.

`visualizer_models.state_json` remains the board. Canonical keys: `operators`, `tracks`, `backlog`, `releases`, `weeklyNotes`. A pillar is not one of them.

```sql
CREATE TABLE IF NOT EXISTS feature_pillars (
    issue_key TEXT PRIMARY KEY,          -- FR issue key, the parent of the work
    pillars_json TEXT NOT NULL,          -- JSON array of Strategic Pillar option values
    synced_at TEXT NOT NULL
);
```

```sql
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id TEXT NOT NULL,            -- id from the board's releases
    release_version TEXT NOT NULL,
    release_date TEXT NOT NULL,          -- YYYY-MM-DD
    window_start TEXT NOT NULL,          -- inclusive
    window_end TEXT NOT NULL,            -- inclusive, the release date
    saved_at TEXT NOT NULL,
    rate_json TEXT NOT NULL,             -- JSON array of RateOperator at save time
    UNIQUE(release_id)
);
```

```sql
CREATE TABLE IF NOT EXISTS checkpoint_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id INTEGER NOT NULL,
    operator_name TEXT NOT NULL,
    issue_key TEXT NOT NULL,
    issue_description TEXT,
    parent_task TEXT,                    -- parent issue key, when the issue has one
    planned INTEGER NOT NULL,            -- 1 when parent_task is set
    UNIQUE(checkpoint_id, operator_name, issue_key)
);
```

```sql
CREATE TABLE IF NOT EXISTS checkpoint_forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id INTEGER NOT NULL,
    feature_id TEXT NOT NULL,
    issue_key TEXT,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    track_id TEXT,
    track_name TEXT,
    finish_on TEXT,                      -- YYYY-MM-DD, empty when the duration is infinite
    finish_weeks REAL,
    remaining_units INTEGER NOT NULL,
    manual_est_weeks REAL NOT NULL DEFAULT 0,
    UNIQUE(checkpoint_id, feature_id)
);
```

`checkpoint_issues` has no pillar column. The report joins `parent_task` to `feature_pillars` when it groups a checkpoint. A parent with no row is Unassigned.

### Rules the columns exist for

**Rate.** An operator's rate is the mean of `planned` over the last eight complete weeks, where `planned = units_week - unplanned_work_week`. A complete week is Sunday through Saturday, and the newest one is the previous complete week. A week with a stored row counts, including a zero. Weeks before that operator's first stored row are absent, not zero. Fewer than eight stored weeks uses the weeks that exist. No stored week is a rate of zero. Unplanned is reported beside the rate and is not added into it.

**Duration.** `manual_est_weeks > 0` is the duration. Otherwise remaining units divided by the track's rate. Remaining units are `units - completedUnits`. The track's rate is the sum of the rates of the operators whose `trackId` is that track. A rate of zero, or remaining units with no rate and no manual estimate, is infinite. The date is then blank.

**Divider.** The system divider is not a feature. Items below it are still scheduled. Feature-request sync does not refresh their unit counts.

**Checkpoint window.** The previous release is the one with the greatest date strictly before this release. The window starts the day after that date and ends on this release's date. The first release uses the fourteen days ending on its date. The release date is compared to the server's local today, the same clock as the weekly sync. A date after today is refused. Saving again deletes that release's checkpoint rows and writes them again.

**Checkpoint contents.** Issues are those the weekly sync would count: a transition into a completed status inside the window, credited by the Jira Developers field, planned when the issue has a parent. The forecast rows are the open features' finishes from the schedule at that moment, plus the rate JSON.

**Material change.** Compare the live schedule's `finishOn` to the newest checkpoint's `finish_on` for the same `feature_id`. A move of fourteen days or more is a change. A feature in only one of the two lists is a change. No checkpoint means an empty change list.

**Pillars.** Field `customfield_10316`, options Growth / Acquisition, New Features / Retention, Tech Debt / Stability, Process Efficiency / Cost Savings. Sync replaces `feature_pillars` for the issue keys it read. A key it did not read keeps its row. `PUT /model` does not write this table. Open allocation groups backlog and track features that have an `issueKey`. Finished allocation is Jira epics resolved on or after 2025-12-28, grouped by the same field, plus Unassigned.

### Network models

`Me`

| Field | Type |
|---|---|
| role | string, `Admin` or `Employee` |

`Board`

| Field | Type |
|---|---|
| schemaVersion | int |
| revision | int |
| jiraRootUrl | string |
| state | object, the canonical five keys |

`state.operators[]`: `id`, `name`, `trackId`. `state.tracks[]`: `id`, `name`, `enabled`, `feature`. `state.releases[]`: `id`, `version`, `date`. `state.weeklyNotes`: object of week-start to text. A feature: `kind`, `id`, `issueKey`, `name`, `units`, `completedUnits`, `manualEstWeeks`, `done`, `releaseVersion`, `pinnedTrackId`, `color`, `jiraIssueType`. A virtual feature adds `jql` and its `kind` is `virtual`. A divider: `kind`, `id`, `name`, `color`.

`FeatureSync`

| Field | Type |
|---|---|
| issues | array of `issueKey`, `name`, `totalUnits`, `completedUnits`, `issueType`, `releaseVersion`, `pillars` |
| virtualFeaturesUpdated | int |

`TaskMetrics`

| Field | Type |
|---|---|
| weekStart | string |
| weekEnd | string |
| operators | array of `operatorName`, `unitsWeek`, `unplannedWorkWeek`, `plannedWorkWeek` |

`TaskMetricTasks`

| Field | Type |
|---|---|
| weekStart | string |
| weekEnd | string |
| jiraRootUrl | string |
| jiraQuery | string |
| operators | array of `operatorName`, `tasks` |

A task: `issueKey`, `description`, `parentTask`, `planned`, `releaseVersion`, `operatorName`. `operatorName` is set on a release's tasks.

`Schedule`

| Field | Type |
|---|---|
| horizonDays | int, 180 |
| tracks | array of `id`, `name`, `enabled`, `capacity`, `bars` |
| queue | array of `featureId`, `name`, `color`, `trackId`, `trackName`, `startOn`, `finishOn`, `weeks` |
| releases | array of `id`, `version`, `date` |

A bar: `featureId`, `issueKey`, `name`, `color`, `startOn`, `finishOn`. `issueKey` is empty when the feature has none. `finishOn` is empty when the duration is infinite. The chart balloon reads `issueKey: name`.

`Report`

| Field | Type |
|---|---|
| asOf | string |
| rates | `windowStart`, `windowEnd`, `operators`, `history` |
| pillars | `open`, `finished` |
| tracks | the schedule's track rows plus the waiting features |
| changes | array of `featureId`, `name`, `color`, `previousFinishOn`, `finishOn`, `movedDays` |

A rate operator: `operatorName`, `plannedTotal`, `unplannedTotal`, `plannedPerWeek`, `unplannedPerWeek`, `weeksCounted`. The totals are the tasks in the weeks that make the average. A history row: `weekStart`, `weekEnd`, `operators` of `operatorName`, `planned`, `unplanned`. A pillar row: `pillar`, `remainingUnits`, `featureCount`. A finished pillar row: `pillar`, `featureCount`.

`Checkpoint`

| Field | Type |
|---|---|
| releaseId | string |
| releaseVersion | string |
| releaseDate | string |
| windowStart | string |
| windowEnd | string |
| savedAt | string |
| issueCount | int |

`PUT /model` body: `schemaVersion`, `revision`, `state`. `PUT /checkpoints/{releaseId}` has no body. `POST /sync-task-metrics` body: `weekStart`.

## Stage 3 — TDD

File: `private/tests/test_lean_visualizer.py`. Each group builds through `lib` and reads back through `lib`. `db` is for a situation `lib` cannot make. The live database is not that situation. Jira is not called. A test that needs a Jira payload hands `lib` the issues.

`test_access`

- describe: caller has no role. it: `GET /me` is refused. it: `GET /model` is refused.
- describe: caller is an Employee. it: `PUT /model` is refused. it: `GET /model` is refused. it: `PUT /checkpoints/{releaseId}` is refused. it: `GET /schedule` returns the forecast. it: `GET /report` returns the report.
- describe: caller is an Admin. it: `PUT /model` is allowed.

`test_board`

- describe: the board is saved with a matching revision. it: the revision advances and the five keys round-trip.
- describe: the revision is stale. it: the save is refused and the stored board is unchanged.
- describe: the payload carries a pillar on a feature. it: the saved state does not contain it, and `feature_pillars` is unchanged.
- describe: a feature has `jiraIssueType`. it: a later save still has it.

`test_rate`

- describe: eight complete weeks are stored. it: the rate is their mean planned count.
- describe: the newest row is the current, unfinished week. it: that row is outside the eight.
- describe: three weeks are stored. it: the rate is the mean of those three.
- describe: no week is stored. it: the rate is zero.
- describe: a week is zero planned and some unplanned. it: the zero counts in the mean, and the unplanned is reported beside it.

`test_schedule`

- describe: a feature has remaining units and the track has a rate. it: the duration is remaining divided by the rate.
- describe: `manualEstWeeks` is set and units are set. it: the manual estimate is the duration.
- describe: the track's rate is zero and there is no manual estimate. it: the finish date is empty.
- describe: the backlog has the system divider. it: the divider has no bar, and a feature below it is scheduled.
- describe: a feature has a color. it: the schedule bar uses that color.

`test_pillar`

- describe: a sync returns two pillars on one feature and none on another. it: the first counts in both groups, and the second is Unassigned.
- describe: a second sync does not mention an older issue key. it: that key keeps its pillars.
- describe: the board is saved. it: pillars stay.

`test_checkpoint`

- describe: the release date is tomorrow. it: the save is refused and no checkpoint row exists.
- describe: a release has a previous release. it: the window starts the day after the previous date and ends on this date.
- describe: the release is the first. it: the window is the fourteen days ending on its date.
- describe: an issue transitioned to done inside the window and names a Developer who is an operator. it: that operator is credited, planned when the issue has a parent.
- describe: the same release is saved again. it: one checkpoint remains, with the later forecast.
- describe: a checkpoint is saved. it: `visualizer_models` is unchanged.
- describe: no checkpoint exists. it: the report's change list is empty.
- describe: the live finish is fourteen days after the checkpoint. it: the feature is in the change list.
- describe: the live finish is thirteen days after the checkpoint. it: the feature is not in the change list.

`test_report`

- describe: weeks are stored from 28 December 2025. it: history includes that week.
- describe: finished epics are handed to the grouping. it: they sum by pillar, and a missing pillar is Unassigned.
- describe: open features have remaining units. it: the open pillar rows sum those units.

## Stage 4 — Backend Implementation

`__init__.py` keeps the router. Every route calls `lib` and carries `require_acl`. No route is left open.

| File | Holds |
|---|---|
| `__init__.py` | Router, ACL, routes |
| `model.py` | `Role` and the network models in Stage 2 |
| `lib.py` | Rate, schedule, pillar, checkpoint, report, board normalize and revision |
| `db.py` | `get_db_path`, `delete_database`, `start_database`, migration `1.1.0`, every new SQL statement |

`start()` runs `migrate_to_1_1_0` after `1.0.0`. The `ensure_*` helpers for the new tables match that migration until Stage 6. Jira field id `customfield_10316` lives next to the existing Developers field constant.

Signatures:

- `lib.rate(operator_name, today) -> RateOperator`
- `lib.schedule(today) -> Schedule`
- `lib.save_board(revision, state) -> Board` raises on a stale revision
- `lib.store_pillars(issues) -> None`
- `lib.save_checkpoint(release_id, today) -> Checkpoint` raises when the date has not arrived or the release is missing
- `lib.report(today) -> Report`

## Stage 5 — Integration

Replace each stub. Done when the Stage 3 groups pass against `test-lean-visualizer.sqlite3`.

| Call | Controller | Becomes |
|---|---|---|
| `GET /me` | `Application` | the token's role |
| `GET /model`, `PUT /model` | `Board`, `Notes`, `VirtualFeature` | the live board |
| `GET /sync-jira` | `Board` | Jira, then `feature_pillars` |
| `POST /sync-task-metrics`, `GET /metrics`, `GET /metrics-tasks` | `Board` | the weekly sync |
| `GET /schedule` | `Board`, `Schedule` | `lib.schedule` |
| `GET /metrics-window` | `TaskMetrics` | the stored weeks |
| `GET /finished-work` | `FinishedWork` | finished features |
| `GET /release-options`, `GET /metrics-release-work-units` | `PrepareRelease` | a release and its issues |
| `GET /report` | `Report` | `lib.report` |
| `PUT /checkpoints/{releaseId}` | `Checkpoint` | `lib.save_checkpoint` |

`GET /metrics-window`, `GET /metrics-release-work-units`, `GET /release-options`, and `GET /finished-work` gain the guard in the route table. No window stubs them. A caller with no role is refused on each.

## Stage 6 — Grouping

`lib.py` is one file through Stage 5. Then it becomes a package. A subject moves in this order, because each one calls the ones above it.

| Module | Layer | Holds |
|---|---|---|
| `lib/board.py` | rules | normalize, revision, canonical keys |
| `lib/rate.py` | rules | the eight-week mean |
| `lib/schedule.py` | rules | duration, tracks, queue, the 180 days |
| `lib/pillar.py` | rules | store, open groups, finished groups |
| `lib/checkpoint.py` | rules | window, actuals, forecast snapshot, replace |
| `lib/report.py` | rules | the four sections and the fourteen-day change |
| `db.py` | SQL | migrations and statements |
| `model.py` | shapes | `Role` and the Stage 2 models |

Jira fetch and the weekly sync move into `lib/jira.py` and `lib/metrics.py` at the moment a new rule calls them. They are not moved ahead of that.

## Open Decisions

None that block Stage 4.
