# Production App — Implementation Plan

## Identity

- **Bundle ID:** `io.bithead.production`
- **App name:** Production
- **Deep-link scheme:** `production`
- **Secure:** `true` (app closes on sign-out)
- **Main controller:** `Application`
- **Public app dir:** `public/boss/app/io.bithead.production/`
- **Private service dir:** `private/app/io.bithead.production/`
- **App stylesheet:** `public/boss/app/io.bithead.production/production.css` (loaded via `os.network.stylesheet()` in `applicationDidStart`)
- **Router prefix:** `/api/io.bithead.production`
- **Test file:** `private/tests/test_production.py`
- **Backend:** Python (FastAPI + SQLite)
- **Upload dir:** `public/upload/io.bithead.production/` (resolved via `get_boss_path()`)
- **Reference app for UI patterns:** `public/boss/app/io.bithead.lean/`, `public/boss/app/io.bithead.scheduler/`
- **Reference for test harness setup:** `private/tests/test_wordy.py` + `private/tests/libtest/`

### Registration

`public/boss/app/installed.json`:

```json
"io.bithead.production": {"name": "Production", "icon": "icon.svg", "scheme": "production"}
```

---

## Terminology

These terms are overloaded in conversation. The plan uses them precisely.

| Term | Meaning |
|---|---|
| **Production Line** | Admin-authored *template*: declared work unit columns, required pools, ordered operations. Versioned. |
| **Line** (or *manufacturing line*) | One operator's virtual line on one job. One permanent record per `(job, operator)`. Never deleted — it carries the operator's metrics. |
| **Job** | A run: a production line + a set of work units + an `active` flag. |
| **Work unit** | One CSV row and everything captured while processing it. |
| **Operation** | One step of a production line. Composed of ordered **sections**. |
| **Section** | A typed block within an operation: description, image, text, number, checkbox, or options. |
| **Pool / Resource** | Global supply (e.g. `Test card`) and its exclusive members (e.g. `Card 2` → `67890`). |

---

## Controller Naming Convention

Matches the Scheduler app: controller names match the model or concept, no verb suffixes. Context (configure with an ID = edit; `null` ID = create) makes the role clear. Lists are plural.

| Pattern | Example |
|---|---|
| Model list | `Jobs.html`, `ProductionLines.html`, `Pools.html` |
| Model form (create + edit) | `Job.html`, `ProductionLine.html`, `Operation.html`, `Pool.html` |
| Modal form | `Section.html`, `Resource.html`, `JoinLine.html` |
| Concept page | `JobDashboard.html`, `ActiveJobs.html`, `ManufacturingLine.html` |

---

## Roles & Access

Single tenant. Two roles.

| Role | How identified | Access |
|---|---|---|
| **Admin** | BOSS super user (`user.id == Global.superUserId`) | Jobs, Job form, Job Dashboard, Production Lines, Pools. May also join a job as an operator. |
| **Operator** | Any signed-in, enabled BOSS user | Active Jobs, Manufacturing Line. |

- Server: admin routes use `@require_admin()`; operator routes use `@require_user()`. Both inject `boss_user: User`.
- Client: `os.isSuperUser(os.user)` hides admin menu items and windows. This is a convenience only — the server is authoritative.
- `GET /api/io.bithead.production/me` returns the role plus the caller's currently-held line, so `Application.html` can route on launch.

---

## Deep-Link URL Routing

Handled by `Application.html` `openDeepLink(deepLink)`.

| URL | Opens |
|---|---|
| `production://` (no path) | `ActiveJobs` for an operator; `Jobs` for an admin |
| `production://jobs` | `ActiveJobs` |
| `production://line/{jobId}` | Joins or resumes the caller's line on `{jobId}` and opens `ManufacturingLine`. Intended for a floor terminal. |
| `production://job/{jobId}` | `JobDashboard` (admin only) |

---

## Stage 1 — UI/UX (Stubbed Backends)

Build every controller against stub endpoints that return fixture JSON from the Python service. No database. Goal: validate all flows, layouts, and state machines before writing backend logic.

**Stub convention:** each stub is decorated `@router.get(...)` / `@router.post(...)` and returns a hard-coded Pydantic model. Stage 4 replaces the body in place. No mocking inside JS — controllers call `os.network.*` exactly as they will in production.

### Stage 1 Deliverables

```
public/boss/app/io.bithead.production/
  application.json
  description.md
  icon.svg
  production.css
  controller/
    Application.html      About.html
    Jobs.html             Job.html              JobDashboard.html     WorkUnit.html
    ProductionLines.html  ProductionLine.html   ProductionLineHistory.html
    Operation.html        Section.html
    Pools.html            Pool.html             Resource.html
    ActiveJobs.html       JoinLine.html         ManufacturingLine.html
    LineBlocked.html      StopLine.html
```

### application.json

```json
{
  "boss": { "version": "1.0.0" },
  "application": {
    "bundleId": "io.bithead.production",
    "name": "Production",
    "version": "1.0.0",
    "icon": "icon.svg",
    "main": "Application",
    "secure": true,
    "scheme": "production",
    "author": "Eric Chamberlain",
    "copyright": "2026 Bithead LLC. All rights reserved."
  },
  "controllers": {
    "About": { "modal": true, "singleton": true },
    "Jobs": { "singleton": true },
    "Job": { "singleton": true },
    "JobDashboard": {},
    "WorkUnit": { "modal": true },
    "ProductionLines": { "singleton": true },
    "ProductionLine": { "singleton": true },
    "ProductionLineHistory": { "modal": true },
    "Operation": { "singleton": true },
    "Section": { "modal": true },
    "Pools": { "singleton": true },
    "Pool": { "singleton": true },
    "Resource": { "modal": true },
    "ActiveJobs": { "singleton": true },
    "JoinLine": { "modal": true },
    "ManufacturingLine": { "singleton": true },
    "LineBlocked": { "modal": true },
    "StopLine": { "modal": true }
  }
}
```

### UI/UX Patterns to Follow

Inherited from the Scheduler app's Stage 1; re-stated here because they are binding.

**Form spacing:** outer container between fieldsets `gap-20`; between fields `gap-10`. `.container` supplies padding — do not add more.

**Model list pattern (`controls-right separated`):** list box left; `Add` top-right always enabled; action buttons bottom-right, `default` class on the primary action, disabled until a row is selected. Delete lives in the model's form, not the list. Wire `didSelectListBoxOption` / `didRemoveAllOptions` to enable/disable.

**Button ordering:** `secondary` → `primary` → `default`, left to right. One `default` per window. `didHitEnter` and the `default` button reference the same function.

**Icon buttons:** `button.primary.up-arrow`, `button.primary.down-arrow`, `button.primary.delete` — 24×24, icon in a `::before` pseudo-element.

**Reordering:** operations use the BOSS sortable list box (`ui-list-box sortable`, see `io.bithead.tutorial/controller/Example.html`) with an async accept function so the server commits the order before the row moves. Sections use up/down icon buttons.

**Popup menus:** every `<select>` in a `ui-popup-menu` needs a `name` and at least one `<option>` at parse time. Seed dynamic menus with a placeholder.

**Labels:** text only, no trailing colons. `wider-labels` on a wrapper for 120px labels.

**File menu:** every window with Save/Cancel/Delete mirrors them in a `File` menu.

### 1.0 Shared: token interpolation

A single client-side helper, defined in `Application.html` and exposed as `$(app.controller).interpolate(text, context)`, is used by `ManufacturingLine` (operator rendering) and `Operation` (admin preview).

```
{work_unit.<column>}          -> context.workUnit[column]
{operation.<step>.<name>}     -> context.operations[step][name]
{pool.<pool name>}            -> context.pools[poolName]
```

- Pool and column names are matched case-insensitively; pool names may contain spaces.
- Render rules: checkbox → `Yes` / `No`; options → the selected option label; text/number → as entered; unset → empty string.
- An unresolved token renders literally. Server-side validation on production line save is what prevents this from reaching an operator.

The same rules are implemented server-side in `tokens.py` for validation and CSV export. Both implementations are covered by Stage 3 tests.

---

### 1.1 App Shell

#### `Application` (`controller/Application.html`)

Application menu (`Production`): About Production · — · Active Jobs · — · Jobs, Production Lines, Pools *(super user only)* · — · Quit Production.

`applicationDidStart`:
1. `os.network.stylesheet("$(app.resourcePath)/production.css")`
2. `GET /me`
3. Hide admin menu options when `isAdmin` is false.
4. Open `ActiveJobs` (operator) or `Jobs` (admin) unless a deep link says otherwise.

Registers all four notification events (§1.10) and forwards them to open controllers.

**Stub endpoints:**
- `GET /api/io.bithead.production/me` → `{ isAdmin, userId, fullName, activeLine: { lineId, jobId, jobName } | null }`

#### `About` (`controller/About.html`)

Standard modal: icon, name, version, copyright.

---

### 1.2 Admin — Jobs

#### `Jobs` (`controller/Jobs.html`)

List box of jobs: name, product (production line name), scheduled dates, active state. Ordered by scheduled start, then completion date.

- `Add` top-right → `Job` with `jobId = null`.
- Bottom-right: `Start` / `Stop` (one button; label follows the selected job's `active` flag), `Show progress` (enabled only when the selected job is active or has been started), `Edit` (`default`, disabled when the selected job is active).
- `Start` validates server-side: a production line must be set and at least one work unit must exist. Failure shows the reason.
- `Stop` warns how many operators are on lines before confirming.

**Stub endpoints:**
- `GET /jobs` → `[{ id, name, productionLineId, productionLineName, scheduledStart, scheduledCompletion, active, hasStarted, workUnitCount }]`
- `POST /job/{jobId}/start` → `{ ok, versionId, version }` | `409 { reason, blockers: [string] }`
- `POST /job/{jobId}/stop` → `{ ok, operatorsPaused }`

#### `Job` (`controller/Job.html`)

`configure(jobId)` — `null` creates.

Fields: name, scheduled start date, completion date, production line (popup menu), work units section.

- The production line menu must be chosen before the CSV upload control is enabled.
- Below the menu, a read-only summary of the chosen line's contract: required columns and required pools. This is what the CSV must satisfy.
- Work units section: current count, `Upload CSV` button, and a table preview of the first rows once uploaded.
- Upload is two-step: the file is posted to a preview endpoint which parses and validates without persisting; the admin sees column mapping, row count, and any errors, then confirms to commit.
- Changing the production line after work units exist warns that work units will be revalidated against the new contract.
- Uploading to a job that has started, or that has any complete or failed work unit, is refused.
- Buttons: `Cancel` and `Save` always; `Delete` when `jobId` is set. Delete is refused for an active job or one with complete/failed units, naming the blocker.
- Delegate: `didSaveJob(job)`, `didDeleteJob(jobId)` so `Jobs` refreshes.

**Stub endpoints:**
- `GET /job/{jobId}` → `{ id, name, productionLineId, scheduledStart, scheduledCompletion, active, hasStarted, workUnitCount, contract: { columns: [string], pools: [string] } }`
- `POST /job` → `{ name, productionLineId, scheduledStart, scheduledCompletion }` → job
- `PUT /job/{jobId}` → same body → job
- `DELETE /job/{jobId}` → `{ ok }` | `409 { reason, blockers }`
- `POST /job/{jobId}/work-units/preview` *(multipart: `file`)* → `{ uploadId, columns: [string], rowCount, rows: [object], errors: [{ line, column, message }] }`
- `POST /job/{jobId}/work-units/commit` → `{ uploadId }` → `{ workUnitCount }`

#### `JobDashboard` (`controller/JobDashboard.html`)

`configure(jobId)`. Live for active jobs; doubles as job history for inactive ones.

**Header:** job name, product and pinned version, scheduled dates, active state with the `Stop` / `Start` control.

**Stats fieldset:** work unit counts (total / pending / in progress / complete / failed); operator count with how many are stopped and how many paused; throughput over a **trailing 60-minute window** — units per hour and average cycle time per unit, both computed only from units completed inside the window, so the figures track the floor as it is now rather than being dragged toward the job's lifetime average. When no units completed in the window, both read `—`.

**Lines table** — the model table pattern: lines (operators) on the left, options bottom-right.

Row: status dot, operator name, current work unit and step (`AST-9910 · 3 of 6`), resources held, units completed. Status dot — **green** working, **yellow** paused (reason: operator break / admin pause / window closed), **blinking red** stopped (with the operator's optional reason), **grey** left.

- `Join` top-right — the admin joins as an operator, following the same flow (`JoinLine` → `ManufacturingLine`).
- Bottom-right: `Leave line`, `Pause` / `Resume`, `Stop line` / `Resume line`. Labels follow the selected row's state. `Leave line` confirms, then releases the operator's work unit (progress retained), returns their resources, ends their line, and closes their Manufacturing Line window.

**Work units fieldset:** filter popup (all / pending / in progress / complete / failed) and a list. Selecting a unit opens `WorkUnit`. Buttons: `Export CSV`, and `Requeue` (enabled only for a failed unit — clears its progress, returns it to the front of the queue, and reactivates the job if it had auto-deactivated).

Updates live from all four notification events.

**Stub endpoints:**
- `GET /job/{jobId}/dashboard` → `{ job: {...}, stats: { total, pending, inProgress, complete, failed, operators, stopped, paused, windowMinutes, unitsInWindow, unitsPerHour, avgCycleSeconds }, lines: [{ lineId, userId, fullName, state, pauseOrigin, stopOrigin, stopReason, workUnitLabel, step, stepCount, resources: [{ pool, resource, value }], unitsCompleted }] }`
- `GET /job/{jobId}/work-units?state=` → `[{ id, label, state, operator, startedAt, completedAt }]`
- `POST /work-unit/{workUnitId}/requeue` → `{ ok, jobReactivated }`
- `GET /job/{jobId}/export` → `text/csv`
- `POST /line/{lineId}/pause` · `/resume` · `/stop` · `/resume-line` · `/leave` → `{ ok }` *(admin origin)*

#### `WorkUnit` (`controller/WorkUnit.html`)

Modal, read-only. `configure(workUnitId)`. Shows the unit's input columns, state, resources used, and a per-operation log: step, name, state, operator, started/completed, captured values, notes, and any recorded edits.

**Stub endpoints:**
- `GET /work-unit/{workUnitId}` → `{ id, label, state, input: object, resources: [...], operations: [{ step, name, state, notes, startedAt, completedAt, completedBy, values: [{ name, label, value }] }], edits: [{ step, name, oldValue, newValue, editedBy, editedAt, stepsReset }] }`

---

### 1.3 Admin — Production Lines

#### `ProductionLines` (`controller/ProductionLines.html`)

List box: name, current version, operation count, and whether any job references it. `Add` top-right; `Edit` (`default`) bottom-right.

**Stub endpoints:**
- `GET /production-lines` → `[{ id, name, version, operationCount, inUse }]`

#### `ProductionLine` (`controller/ProductionLine.html`)

`configure(productionLineId)` — `null` creates.

Fields:
- Name (the product produced, e.g. `CR-One Reader`).
- Read-only version indicator plus a `History` button opening `ProductionLineHistory`.
- **Required work unit columns** — an editable list (add / rename / delete / reorder). These are the CSV headers a job must supply and the valid `{work_unit.*}` keys.
- **Required pools** — a list of global pools chosen from a picker. Pool names become the valid `{pool.*}` keys.
- **Operations** — a sortable list box (BOSS reorder feature) showing `step. name`. `Add` opens `Operation`; selecting and tapping `Edit` opens it for editing.

Buttons: `Cancel` and `Save` when new; `Delete`, `Cancel`, `Save` when existing. Delete is refused while any job references the line.

**Token validation runs on save.** Every `{...}` token in every description section is checked against the declared columns, the required pools, and the section names of *preceding* operations. Forward and self references are rejected. On failure the save is refused and the form lists each offending operation with its bad tokens and the reason.

**Versioning behaviour.** Any mutation to a frozen version (one a job has started against) forks a new version server-side. Every mutating endpoint returns `versionId` and `forked`; when `forked` is true the controller reloads the whole form from `GET /production-line/{id}` because the operation and section IDs have changed.

Delegate: `didSaveProductionLine(line)`, `didDeleteProductionLine(id)`.

**Stub endpoints:**
- `GET /production-line/{id}` → `{ id, name, versionId, version, frozen, inUse, columns: [{ id, name }], pools: [{ id, name }], operations: [{ id, step, name, sectionCount }] }`
- `POST /production-line` → `{ name, columns: [string], poolIds: [int] }` → line
- `PUT /production-line/{id}` → same body → `{ ...line, forked }`
- `DELETE /production-line/{id}` → `{ ok }` | `409 { reason, blockers }`
- `POST /production-line/{id}/validate` → `{ valid, errors: [{ step, operationName, token, reason }] }`
- `GET /production-line/{id}/versions` → `[{ versionId, version, frozen, createdAt, jobCount }]`
- `GET /production-line-version/{versionId}` → same shape as `GET /production-line/{id}`, read-only
- `POST /production-line/{id}/operation` → `{ name }` → `{ id, step, versionId, forked }`
- `POST /production-line/{id}/operations/order` → `{ operationIds: [int] }` → `{ operations, versionId, forked }`
- `GET /pools/picker` → `[{ id, name, resourceCount }]`

#### `ProductionLineHistory` (`controller/ProductionLineHistory.html`)

Modal. List of versions with created date and how many jobs pinned each. Selecting one opens a read-only `ProductionLine` view of that version.

#### `Operation` (`controller/Operation.html`)

`configure({ productionLineId, operationId })` — `operationId` `null` creates. Uses an `OperationConfig` function per the ≥3-parameter rule if a third field is added.

Fields: name; a sections table with `Add section` above and up / down / delete icon buttons per row. Each row shows the section type and its name or a truncated summary. Selecting a row and tapping `Edit`, or adding, opens `Section`.

A `Preview` disclosure renders the operation as the operator will see it, with tokens interpolated against sample values, so the admin can check layout and token spelling before saving.

Buttons: `Cancel`, `Save` when new; `Delete`, `Cancel`, `Save` when existing.

**Stub endpoints:**
- `GET /operation/{operationId}` → `{ id, step, name, versionId, sections: [{ id, type, sortOrder, name, label, required, body, imagePath, options: [string] }] }`
- `PUT /operation/{operationId}` → `{ name }` → `{ ...operation, forked }`
- `DELETE /operation/{operationId}` → `{ ok, versionId, forked }`
- `POST /operation/{operationId}/sections/order` → `{ sectionIds: [int] }` → `{ sections, versionId, forked }`

#### `Section` (`controller/Section.html`)

Modal. `configure({ operationId, sectionId })`. A type popup menu drives which fields are shown:

| Type | Fields |
|---|---|
| `description` | Multi-line body. Tokens allowed. Rendered to the operator as a read-only label. |
| `image` | Upload control and a thumbnail. The file belongs to the section; deleting the section deletes it. |
| `text` | Name, label, required |
| `number` | Name, label, required. No min/max in v1 — any number is valid. |
| `checkbox` | Name, label, required (required = must be ticked) |
| `options` | Name, label, required, and an options table (add / reorder / delete). Rendered to the operator as a drop-down. |

`name` is the token key, must be a simple identifier, and must be unique within the operation. Validated on save.

Buttons: `Cancel`, `Save`; `Delete` when editing. Delegate: `didSaveSection(section)`, `didDeleteSection(id)`.

**Stub endpoints:**
- `POST /operation/{operationId}/section` → `{ type, name, label, required, body, options: [string] }` → `{ ...section, versionId, forked }`
- `PUT /section/{sectionId}` → same body → `{ ...section, versionId, forked }`
- `DELETE /section/{sectionId}` → `{ ok, versionId, forked }`
- `POST /section/{sectionId}/image` *(multipart: `file`)* → `{ imagePath }`

---

### 1.4 Admin — Pools

#### `Pools` (`controller/Pools.html`)

List box: pool name, resource count, available count. `Add` top-right; `Edit` bottom-right.

**Stub endpoints:**
- `GET /pools` → `[{ id, name, resourceCount, availableCount }]`

#### `Pool` (`controller/Pool.html`)

`configure(poolId)` — `null` creates.

Fields: name (this is the `{pool.<name>}` key), and a resources table: name, value, in service, current holder (operator and job, when checked out). Buttons under the table: `Add`, `Edit`, `Return` (force-return a checked-out resource, enabled only when the selected row is held).

Renaming or deleting a pool referenced by **any** production line version — current or historical — is refused, listing the lines that block it. Deleting is also refused while any resource is checked out.

Buttons: `Cancel`, `Save`; `Delete` when existing.

**Stub endpoints:**
- `GET /pool/{poolId}` → `{ id, name, resources: [{ id, name, value, inService, heldBy: { lineId, userId, fullName, jobId, jobName } | null }] }`
- `POST /pool` → `{ name }` → pool
- `PUT /pool/{poolId}` → `{ name }` → pool | `409 { reason, blockers }`
- `DELETE /pool/{poolId}` → `{ ok }` | `409 { reason, blockers }`
- `POST /resource/{resourceId}/return` → `{ ok }`

#### `Resource` (`controller/Resource.html`)

Modal. `configure({ poolId, resourceId })`. Fields: name, value, in service. Buttons: `Cancel`, `Save`; `Delete` when editing (refused while held).

**Stub endpoints:**
- `POST /pool/{poolId}/resource` → `{ name, value, inService }` → resource
- `PUT /resource/{resourceId}` → same body → resource
- `DELETE /resource/{resourceId}` → `{ ok }` | `409 { reason }`

---

### 1.5 Operator — Joining

#### `ActiveJobs` (`controller/ActiveJobs.html`)

List of active jobs: name, product, units remaining. One button per row: `Resume` when the caller already holds a line on that job, otherwise `Join`.

While the caller holds a line on any job, every other row's `Join` is disabled with a note naming the job they are on — a user may hold only one line at a time.

`Resume` restores the caller's line without a resource pick. `Join` opens `JoinLine`.

**Stub endpoints:**
- `GET /active-jobs` → `{ heldLine: { lineId, jobId, jobName } | null, jobs: [{ jobId, name, product, unitsRemaining, joined }] }`

#### `JoinLine` (`controller/JoinLine.html`)

Modal. `configure(jobId)`.

For each pool the job's pinned production line requires, a popup menu of that pool's available resources (in service, not checked out) showing name and value. Buttons `Cancel` and `Join`.

If any required pool has zero available resources, the modal instead shows *"No `<pool>` available. Ask your line manager to add resources to `<pool>`."* and offers only `Cancel`.

If the line requires no pools, `Join` on `ActiveJobs` skips this modal entirely.

On success, opens `ManufacturingLine`.

**Stub endpoints:**
- `GET /job/{jobId}/join-info` → `{ jobName, product, pools: [{ poolId, name, resources: [{ id, name, value }] }], blocked: [string] }`
- `POST /job/{jobId}/join` → `{ resources: [{ poolId, resourceId }] }` → `{ lineId }` | `409 { reason }`

---

### 1.6 Operator — Manufacturing Line

#### `ManufacturingLine` (`controller/ManufacturingLine.html`)

`configure(lineId)`. Fullscreen window; OS chrome stays visible.

```
+---------------------------------------------------+
| Bay 4 - Group A - AST-9910 [Leave][Pause][Stop]   |
+----------------+----------------------------------+
| v 1 Scan       |  Assign to Bay 4                 |
| v 2 Configure  |  [image]                         |
| > 3 Verify     |  Serial number [___________]     |
|   4 Package    |  Test result   [Pass        v]   |
|                |  [x] LED is green                |
|                |                                  |
|                |  Notes [____________________]    |
|                |                [Fail] [Complete] |
+----------------+----------------------------------+
```

**Header:** work unit identity on the left — the declared column values joined by `·`. Buttons on the right, in order: `Leave line`, `Pause`, `Stop line`.

**Left:** `ui-list-box` of operations, `step. name`, with a checkmark on completed steps and the current step selected.

**Right:** the current operation's sections rendered in order, tokens interpolated. Below them, a notes field, then `Fail` and `Complete` bottom-right.

**State machine:**

1. `viewDidLoad` → `GET /line/{lineId}/state`.
2. No work unit assigned → `POST /line/{lineId}/pull`.
   - A unit is claimed → render at its first incomplete operation (a released unit resumes mid-way).
   - Nothing available → the terminal screen: *"No more work units remaining in the queue."*, a list of the resources to return, and `Leave line`. Shown whether or not other operators still hold units.
3. Operator works forward. `Complete` is disabled until every required section on the step has a value (checkbox: ticked).
4. `Complete` → records values, notes, operator, timestamp; checkmarks the step; advances. On the last step the unit is completed, the line resets and pulls the next unit.
5. `Fail` → notes are required; the unit is marked failed with the failing step; the line resets and pulls the next unit. Resources stay held.
6. Navigating back to a completed step shows it fully editable. Saving an edit resets **every** later step to incomplete, after a confirmation stating how many will be reset. The edit is recorded (who, when, old → new).
7. `Stop line` → `StopLine` modal for an optional reason → line state `stopped`, `LineBlocked` modal shown, admins notified.
8. `Pause` → line state `paused` (origin `operator`), `LineBlocked` modal shown.
9. Closing the window → line state `paused`, origin `window`. No prompt. Unit and resources retained. Resuming from `ActiveJobs` restores the exact state.
10. `Leave line` → confirmation listing the resources to return and warning the current unit will be released with progress retained → releases unit and resources, ends the line, closes the page.

Registers for `line-status` and `job-status` events so admin-raised pause/stop and job stop appear immediately.

**Stub endpoints:**
- `GET /line/{lineId}/state` → `{ lineId, jobId, jobName, state, blocked: { kind, origin, reason } | null, workUnit: { id, label, input: object, currentStep } | null, operations: [{ step, name, state, notes, sections: [...], values: object }], context: { workUnit: object, pools: object, operations: object } }`
- `POST /line/{lineId}/pull` → `{ workUnit, operations, context }` | `{ empty: true, resources: [{ pool, resource, value }] }`
- `POST /work-unit/{workUnitId}/operation/{step}/complete` → `{ values: object, notes }` → `{ nextStep, unitComplete }`
- `POST /work-unit/{workUnitId}/operation/{step}/fail` → `{ values: object, notes }` → `{ ok }`
- `POST /work-unit/{workUnitId}/operation/{step}/edit` → `{ values: object, notes }` → `{ stepsReset }`
- `POST /line/{lineId}/stop` → `{ reason }` → `{ ok }` *(operator origin)*
- `POST /line/{lineId}/resume-line` → `{ ok }` | `403` when the andon was admin-raised
- `POST /line/{lineId}/pause` · `/resume` → `{ ok }` | `403` when the pause was admin-raised
- `POST /line/{lineId}/leave` → `{ ok, resources: [{ pool, resource, value }] }`

#### `StopLine` (`controller/StopLine.html`)

Modal. Optional multi-line reason, `Cancel` and `Stop line`.

#### `LineBlocked` (`controller/LineBlocked.html`)

Modal covering the Manufacturing Line. `configure({ kind, origin, reason })`.

| Kind | Origin | Body | Button |
|---|---|---|---|
| stop | operator | "Line stopped. Your line manager has been notified." + reason | `Resume line` |
| stop | admin | "Line stopped by your line manager." | none |
| pause | operator | "On break." | `Back to work` |
| pause | admin | "Paused by your line manager." | none |

Shown and hidden by `line-status` and `job-status` events, so an admin clearing the state releases the operator without any action on their part.

---

### 1.7 Notification Events

| Event | Payload | Recipients |
|---|---|---|
| `io.bithead.production.line-status` | `{ jobId, lineId, userId, state, pauseOrigin, stopOrigin, reason }` | Admins; plus the affected operator |
| `io.bithead.production.work-unit` | `{ jobId, workUnitId, state }` | Admins |
| `io.bithead.production.job-status` | `{ jobId, active }` | Admins and every operator with a line on the job |
| `io.bithead.production.operation` | `{ jobId, lineId, workUnitId, step, stepCount }` | Admins |

---

## Stage 2 — Data Model (SQLite Schema)

All timestamps are ISO 8601 UTC strings. The client renders local time.

```sql
-- ---------------------------------------------------------------------------
-- Pools (global)
-- ---------------------------------------------------------------------------

CREATE TABLE pools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- token key: {pool.<name>}; may contain spaces
    created_at TEXT NOT NULL,
    created_by INTEGER NOT NULL         -- BOSS user id
);
CREATE UNIQUE INDEX idx_pools_name ON pools(name COLLATE NOCASE);

CREATE TABLE pool_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                 -- e.g. "Card 2"
    value TEXT NOT NULL,                -- interpolated value, e.g. "67890"
    in_service INTEGER NOT NULL DEFAULT 1,
    held_by_line_id INTEGER REFERENCES job_lines(id),  -- NULL = available
    sort_order INTEGER NOT NULL
);
CREATE INDEX idx_pool_resources_pool ON pool_resources(pool_id);

-- ---------------------------------------------------------------------------
-- Production lines (templates, versioned)
-- ---------------------------------------------------------------------------

CREATE TABLE production_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- the product produced, e.g. "CR-One Reader"
    current_version_id INTEGER,         -- FK to production_line_versions; set after first version
    created_at TEXT NOT NULL,
    created_by INTEGER NOT NULL
);

CREATE TABLE production_line_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_line_id INTEGER NOT NULL REFERENCES production_lines(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,           -- 1-based, monotonic per line
    -- Set to 1 the first time a job starts against this version. A frozen
    -- version is immutable; the next edit deep-copies it into version + 1.
    frozen INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(production_line_id, version)
);

CREATE TABLE production_line_columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL REFERENCES production_line_versions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                 -- CSV header; token key {work_unit.<name>}
    sort_order INTEGER NOT NULL
);

CREATE TABLE production_line_pools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL REFERENCES production_line_versions(id) ON DELETE CASCADE,
    pool_id INTEGER NOT NULL REFERENCES pools(id),
    -- Denormalized so a historical version stays readable and its tokens stay
    -- resolvable. Pool renames are blocked while any version references the
    -- pool, so this can never drift.
    pool_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL REFERENCES production_line_versions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    step INTEGER NOT NULL,              -- 1-based; token key {operation.<step>.<name>}
    UNIQUE(version_id, step)
);

CREATE TABLE operation_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    section_type TEXT NOT NULL,         -- description | image | text | number | checkbox | options
    sort_order INTEGER NOT NULL,
    name TEXT,                          -- input sections: token key, unique within the operation
    label TEXT,                         -- input sections: shown to the operator
    required INTEGER NOT NULL DEFAULT 0,-- input sections: gates Complete
    body TEXT,                          -- description sections: text containing tokens
    -- Image sections: /upload/io.bithead.production/<file>. Each row owns its
    -- file outright — forking a frozen version copies the file as well as the
    -- row, so deleting a section can always delete its file unconditionally.
    image_path TEXT
);
CREATE INDEX idx_sections_operation ON operation_sections(operation_id);

CREATE TABLE operation_section_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL REFERENCES operation_sections(id) ON DELETE CASCADE,
    label TEXT NOT NULL,                -- also the stored value when selected
    sort_order INTEGER NOT NULL
);

-- ---------------------------------------------------------------------------
-- Jobs and work units
-- ---------------------------------------------------------------------------

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    production_line_id INTEGER NOT NULL REFERENCES production_lines(id),
    -- Pinned when the admin taps Start. NULL until then, which is also how
    -- "has never started" is determined.
    version_id INTEGER REFERENCES production_line_versions(id),
    scheduled_start TEXT NOT NULL,      -- YYYY-MM-DD
    scheduled_completion TEXT NOT NULL, -- YYYY-MM-DD, >= scheduled_start
    active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    created_by INTEGER NOT NULL         -- admin who created the job
);

CREATE TABLE work_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    row_order INTEGER NOT NULL,         -- CSV row order; primary queue key
    -- {header: value} for every column in the CSV, including columns the
    -- production line did not declare. Undeclared columns are exported but
    -- are not interpolatable.
    input_json TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',  -- pending | in_progress | complete | failed
    assigned_line_id INTEGER REFERENCES job_lines(id),  -- NULL = unassigned
    current_step INTEGER NOT NULL DEFAULT 1,
    started_at TEXT,                    -- first time the unit was pulled
    completed_at TEXT,
    failed_at TEXT,
    failed_step INTEGER,
    requeued_at TEXT                    -- set by an admin requeue; sorts to the queue front
);
CREATE INDEX idx_work_units_queue ON work_units(job_id, state, assigned_line_id, row_order);

-- Queue order:
--   ORDER BY CASE WHEN requeued_at IS NOT NULL THEN 0
--                 WHEN started_at  IS NOT NULL THEN 1
--                 ELSE 2 END,
--            row_order
-- i.e. requeued first, then partially-worked units, then untouched CSV order.

-- ---------------------------------------------------------------------------
-- Lines (one permanent record per job + operator)
-- ---------------------------------------------------------------------------

CREATE TABLE job_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,           -- BOSS user id
    state TEXT NOT NULL,                -- working | paused | stopped | left
    pause_origin TEXT,                  -- operator | admin | window   (state = paused)
    stop_origin TEXT,                   -- operator | admin            (state = stopped)
    stop_reason TEXT,                   -- optional operator-supplied andon reason
    units_completed INTEGER NOT NULL DEFAULT 0,
    units_failed INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL,
    last_active_at TEXT,
    UNIQUE(job_id, user_id)             -- rejoining reuses the same record
);

CREATE TABLE job_line_resources (
    line_id INTEGER NOT NULL REFERENCES job_lines(id) ON DELETE CASCADE,
    pool_id INTEGER NOT NULL REFERENCES pools(id),
    resource_id INTEGER NOT NULL REFERENCES pool_resources(id),
    PRIMARY KEY (line_id, pool_id)      -- exactly one resource per required pool
);

-- ---------------------------------------------------------------------------
-- Work unit progress and logs
-- ---------------------------------------------------------------------------

CREATE TABLE work_unit_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
    step INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',  -- pending | complete
    notes TEXT,
    started_at TEXT,                    -- first time the step was shown
    completed_at TEXT,
    completed_by INTEGER,               -- BOSS user id
    UNIQUE(work_unit_id, step)
);

CREATE TABLE work_unit_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
    step INTEGER NOT NULL,
    name TEXT NOT NULL,                 -- section name; {operation.<step>.<name>}
    -- text/number: as entered. checkbox: '1' | '0'. options: the option label.
    value TEXT,
    UNIQUE(work_unit_id, step, name)
);

CREATE TABLE work_unit_resources (
    work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
    pool_name TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    resource_value TEXT NOT NULL,       -- copied so the record survives resource edits
    PRIMARY KEY (work_unit_id, pool_name)
);

CREATE TABLE work_unit_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_unit_id INTEGER NOT NULL REFERENCES work_units(id) ON DELETE CASCADE,
    step INTEGER NOT NULL,
    name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    edited_by INTEGER NOT NULL,
    edited_at TEXT NOT NULL,
    steps_reset INTEGER NOT NULL        -- how many later operations were invalidated
);

CREATE TABLE line_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id INTEGER NOT NULL REFERENCES job_lines(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,           -- join | leave | pause | stop
    origin TEXT,                        -- operator | admin | window
    reason TEXT,
    actor_id INTEGER,                   -- BOSS user id who caused it
    started_at TEXT NOT NULL,
    ended_at TEXT                       -- NULL while a pause/stop interval is open
);
CREATE INDEX idx_line_events_line ON line_events(line_id, event_type, ended_at);
```

**Blocked-time accounting.** `line_events` rows of type `pause` and `stop` are intervals. Throughput subtracts open and closed blocked intervals from wall-clock time.

**Throughput window.** Both dashboard throughput figures are computed over a trailing 60-minute window: `units per hour` counts `work_units.completed_at` inside the window and scales to the hour; `average cycle time` averages `completed_at - started_at` for those same units, minus any blocked intervals overlapping them. Nothing is stored — the window is a query parameter, so it can be widened later without a migration.

---

## Stage 3 — TDD (Tests Before Implementation)

File: `private/tests/test_production.py`. Setup mirrors `test_wordy.py`.

```python
get_app_module("io.bithead.production")
from io.bithead.production.lib import *
from io.bithead.production import db, tokens, csvimport
```

Each `describe` comment groups related `it:` assertions in one test function. Error paths use `pytest.raises`.

#### `test_token_parse_and_render()`
- `describe: work unit token` → `{work_unit.Location}` renders the unit's column value
- `describe: operation token` → `{operation.1.serial}` renders step 1's captured value
- `describe: pool token with spaces` → `{pool.Test card}` renders the held resource's value
- `describe: case-insensitive match` → `{pool.test CARD}` and `{work_unit.location}` both resolve
- `describe: checkbox value` → renders `Yes` / `No`, not `1` / `0`
- `describe: options value` → renders the selected option's label
- `describe: unset value` → renders an empty string
- `describe: unknown token` → renders literally, does not raise

#### `test_line_validation()`
- `describe: all tokens resolve` → valid, no errors
- `describe: undeclared work unit column` → error naming the operation, token, and reason
- `describe: undeclared pool` → error
- `describe: forward reference` → `{operation.3.x}` inside step 2 is rejected
- `describe: self reference` → `{operation.2.x}` inside step 2 is rejected
- `describe: backward reference` → `{operation.1.x}` inside step 2 is accepted
- `describe: unknown section name on a valid step` → error
- `describe: duplicate section name within an operation` → raises on save
- `describe: non-identifier section name` → raises on save

#### `test_versioning()`
- `describe: edit an unfrozen version` → edits in place, version number unchanged
- `describe: job starts against a version` → version becomes frozen
- `describe: edit a frozen version` → forks version + 1 with a deep copy of columns, pools, operations, sections, and options
- `describe: forked ids differ` → operation and section ids in the new version are new rows
- `describe: fork copies image files` → an image section's file is duplicated, and the new row's `image_path` differs from the frozen row's
- `describe: delete a forked section` → its file is removed and the frozen version's file is untouched
- `describe: started job keeps its pinned version` → job's `version_id` still points at the frozen version
- `describe: delete a line referenced by a job` → raises with blockers
- `describe: delete an unreferenced line` → cascades versions, operations, sections

#### `test_csv_import()`
- `describe: valid CSV` → one work unit per row, `row_order` follows file order
- `describe: missing declared column` → raises naming the column
- `describe: extra undeclared column` → accepted, stored in `input_json`, not interpolatable
- `describe: empty value in a declared column` → raises naming line and column
- `describe: duplicate rows` → raises naming both line numbers
- `describe: header-only file` → raises
- `describe: preview does not persist` → no work units written until commit
- `describe: commit replaces existing units` → prior units removed, new count correct
- `describe: job has started` → raises
- `describe: job has a completed unit` → raises

#### `test_work_unit_queue()`
- `describe: first pull` → lowest `row_order` unassigned unit, state `in_progress`, `started_at` set
- `describe: released partial outranks untouched` → the partially-worked unit is handed out first
- `describe: requeued unit outranks a partial` → requeued unit comes first
- `describe: concurrent pulls` → two lines never receive the same unit
- `describe: no unassigned units` → returns empty, does not raise
- `describe: job inactive` → raises; no unit is handed out

#### `test_operation_completion()`
- `describe: required text missing` → raises
- `describe: required checkbox unticked` → raises
- `describe: all required present` → step marked complete with operator and timestamp, `current_step` advances
- `describe: values persisted` → `work_unit_values` holds one row per named section
- `describe: notes persisted` → stored on `work_unit_operations`
- `describe: last step` → unit state `complete`, `completed_at` set, resources snapshotted to `work_unit_resources`, line `units_completed` incremented
- `describe: completing out of order` → raises

#### `test_operation_edit()`
- `describe: edit step 2 of 5 with 3–5 complete` → steps 3, 4, 5 reset to pending, `steps_reset` = 3
- `describe: edit recorded` → `work_unit_edits` row holds old and new values, editor, timestamp
- `describe: downstream values retained` → resetting a step does not delete its captured values
- `describe: edit the last completed step` → no steps reset
- `describe: edit a step on a completed unit` → raises

#### `test_fail_and_requeue()`
- `describe: fail without notes` → raises
- `describe: fail with notes` → unit state `failed`, `failed_step` and `failed_at` set, resources snapshotted, line `units_failed` incremented
- `describe: failed unit leaves the queue` → the next pull does not return it
- `describe: requeue` → progress cleared, state `pending`, `requeued_at` set, unit sorts to the front
- `describe: requeue on an inactive job` → job `active` returns to 1
- `describe: requeue a non-failed unit` → raises

#### `test_pool_checkout()`
- `describe: join with one required pool` → resource `held_by_line_id` set, `job_line_resources` row created
- `describe: resource already held` → raises
- `describe: out-of-service resource` → not offered, and raises if requested
- `describe: pool exhausted` → join-info reports the pool as blocked
- `describe: missing a required pool in the request` → raises
- `describe: leave line` → all resources returned, `held_by_line_id` cleared
- `describe: force return` → resource freed even though the line is still live

#### `test_pool_rules()`
- `describe: rename an unreferenced pool` → succeeds
- `describe: rename a pool referenced by the current version` → raises with blockers
- `describe: rename a pool referenced only by a historical version` → raises with blockers
- `describe: delete a pool with a checked-out resource` → raises
- `describe: delete an unreferenced pool` → cascades resources
- `describe: duplicate pool name, different case` → raises

#### `test_job_lifecycle()`
- `describe: start with no work units` → raises
- `describe: start with no production line operations` → raises
- `describe: start` → `active` = 1, version pinned and frozen
- `describe: stop with operators on lines` → `active` = 0, every live line paused with origin `admin`
- `describe: restart` → `active` = 1, admin-origin pauses cleared, operator-origin pauses retained
- `describe: last unit resolved` → `active` auto-set to 0
- `describe: failed units count as resolved` → a job with only failures still deactivates
- `describe: delete a job with completed units` → raises
- `describe: delete an inactive untouched job` → cascades work units and lines
- `describe: completion date before start date` → raises

#### `test_line_state()`
- `describe: join` → line created, state `working`, `line_events` join row
- `describe: rejoin after leaving` → same line row reused, counters retained, new resources picked
- `describe: join a second job while holding a line` → raises
- `describe: operator stop with reason` → state `stopped`, origin `operator`, reason stored, open `line_events` interval
- `describe: operator resumes an operator-raised stop` → state `working`, interval closed
- `describe: operator resumes an admin-raised stop` → raises
- `describe: admin clears an operator-raised stop` → succeeds
- `describe: window close` → state `paused`, origin `window`, unit and resources retained
- `describe: leave line` → unit released with progress retained, resources returned, state `left`, row not deleted

#### `test_export()`
- `describe: headers` → declared columns, undeclared columns, state, operators, timestamps, one column per required pool, `<step>.<name>` per input section, `<step>.notes` per operation
- `describe: one row per work unit` → row count equals unit count
- `describe: failed unit` → state column reads `failed`, incomplete steps are blank
- `describe: no work units` → header row only, no exception

---

## Stage 4 — Backend Implementation

### File Layout

```
private/app/io.bithead.production/
  __init__.py       FastAPI router. Thin — auth decorators, request/response models, calls into lib.
  db.py             Schema creation, migrations, all SQL. No business rules.
  lib.py            Business rules. The only module tests import for behaviour.
  tokens.py         Token parse, validate, render. Shared by lib and export.
  csvimport.py      CSV parse and validation; preview cache keyed by uploadId.
  events.py         Builds and sends BOSS notification events.
  export.py         Work unit CSV export.
```

### `db.py` Responsibilities

- `start()` creates the schema if absent and applies migrations.
- One function per query; every function takes and returns plain dicts or primitives.
- `claim_next_work_unit(job_id, line_id)` performs the atomic claim in a single transaction: `UPDATE work_units SET assigned_line_id = ?, state = 'in_progress' WHERE id = (SELECT id FROM work_units WHERE ... ORDER BY <queue order> LIMIT 1) AND assigned_line_id IS NULL` and returns the row or `None`.
- `checkout_resource(resource_id, line_id)` uses `WHERE held_by_line_id IS NULL AND in_service = 1` so a concurrent join cannot double-book.

### `lib.py` Responsibilities

Key signatures:

```python
# Roles
def is_admin(user: User) -> bool

# Production lines
def editable_version(production_line_id: int) -> int
    """Return the version id to write to, forking the current version first
    if it is frozen. Callers report `forked` to the client so it reloads."""
def validate_line(version_id: int) -> list[TokenError]
def save_production_line(user, line_id, name, columns, pool_ids) -> dict
def delete_production_line(user, line_id) -> None   # raises Blocked

# Pools
def rename_pool(user, pool_id, name) -> dict        # raises Blocked if referenced
def delete_pool(user, pool_id) -> None              # raises Blocked
def return_resource(user, resource_id) -> None

# Jobs
def start_job(user, job_id) -> dict                 # pins + freezes the version
def stop_job(user, job_id) -> dict                  # pauses every live line, origin admin
def maybe_deactivate_job(job_id) -> bool            # called after each unit resolves
def requeue_work_unit(user, work_unit_id) -> dict

# Lines
def join_line(user, job_id, resources) -> dict
def leave_line(actor, line_id) -> dict              # actor may be the operator or an admin
def set_line_state(actor, line_id, state, origin, reason) -> dict

# Work
def pull_work_unit(user, line_id) -> dict | None
def complete_operation(user, work_unit_id, step, values, notes) -> dict
def fail_operation(user, work_unit_id, step, values, notes) -> dict
def edit_operation(user, work_unit_id, step, values, notes) -> dict
def build_context(work_unit_id, line_id) -> dict    # work_unit, operations, pools
```

Every state-changing function emits its event through `events.py` before returning.

### `tokens.py` Responsibilities

- `parse(text) -> list[Token]` — extracts `{namespace.key}` occurrences.
- `validate(text, step, columns, pools, prior_sections) -> list[TokenError]` — enforces the namespaces and the backward-reference rule.
- `render(text, context) -> str` — mirrors the client helper exactly; the same fixtures drive both test suites.

### `csvimport.py` Responsibilities

- `preview(job_id, file_bytes, columns) -> Preview` — parses, validates headers, empty declared values, and duplicate rows; returns the parsed rows and errors without writing. Stores the parsed result under an `uploadId` with a short TTL.
- `commit(job_id, upload_id) -> int` — replaces the job's work units in one transaction.

### `events.py` Responsibilities

- `send(name, data, user_ids)` wraps `lib.server.send_events`.
- `admins()` resolves the recipient list for admin-facing events.
- `line_recipients(job_id)` resolves every operator with a live line on a job.

---

## Stage 5 — Integration

Done when every stub is replaced by real logic and all Stage 3 tests pass against a real database.

### Checklist (per endpoint group)

- [ ] `GET /me` — real role resolution from the BOSS session
- [ ] Pools — list, detail, create, rename (with block rules), delete (with block rules)
- [ ] Resources — create, update, delete, force return
- [ ] Production lines — list, detail, create, update, delete, validate
- [ ] Production line versions — history list, read-only version detail, fork-on-edit
- [ ] Operations — create, update, delete, reorder
- [ ] Sections — create, update, delete, reorder, image upload
- [ ] Jobs — list, detail, create, update, delete
- [ ] Work units — CSV preview, CSV commit
- [ ] Job lifecycle — start (pin + freeze), stop (pause all lines), auto-deactivate
- [ ] Dashboard — stats, lines, work unit list, throughput
- [ ] Work unit detail and requeue
- [ ] Export CSV
- [ ] Active jobs — list, join info, join
- [ ] Line state — state, pull, complete, fail, edit
- [ ] Line control — pause, resume, stop, resume line, leave (operator and admin origins)
- [ ] Events — all four emitted and consumed by the dashboard and the blocking modal
- [ ] Remove every `TODO:` stub comment from `__init__.py`

---

## Open Decisions (revisit before Stage 4)

1. **Upload preview TTL and storage.** `csvimport.preview` holds parsed rows keyed by `uploadId`. In-process dict (simple, lost on restart) vs. a `work_unit_uploads` table (durable, one more table). Leaning in-process with a 15-minute TTL.
2. **Section image cleanup.** Deleting a section deletes its file, but forking a frozen version copies the section row and therefore shares the file path. The fork must either copy the file or reference-count it. Leaning: copy the file on fork so deletion stays simple.
3. **Throughput window.** Units per hour over the life of the job, or a trailing window (e.g. last hour)? A trailing window is more useful on a live floor; the lifetime figure is easier to explain. Needs a decision before the dashboard stats query is written.
4. **Operator identity on a shared terminal.** A floor terminal opened via `production://line/{jobId}` runs as whichever BOSS user is signed in. If terminals are shared between shifts, sign-out/sign-in is the hand-off mechanism. Confirm that is acceptable rather than an in-app operator switch.
5. **Line event interval closure on restart.** If the service restarts while a pause interval is open, `ended_at` stays `NULL` indefinitely and inflates blocked time. Consider closing stale intervals on `start()` using `last_active_at`.
