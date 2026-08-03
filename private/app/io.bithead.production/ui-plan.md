# Production — UI Test Plan

The order in which this app's screens get covered, and how far that has got.

`plan.md` is the implementation contract; this is the coverage contract. It
exists so UI testing can stop and resume: the status table says what is done,
each flow says what it must prove, and neither depends on remembering a
conversation.

## How to use it

1. Read the status table. Take the first flow that is not `done`.
2. Write it as one spec file under `uitest/tests/`, named for the flow.
3. Update the flow's status and the table in the same commit as the spec.
4. A flow that turns up a defect gets a line under **Findings**, so the next
   session can tell a gap in coverage from a gap in the app.

## Scope

UI tests prove **wiring** — that a screen calls the right endpoint and renders
the answer where it belongs. The rules behind those endpoints are settled by
`private/tests/test_production.py`. See "When to Write Tests" in
`docs/prompt/process.md`.

So: assert that the list filled, the field shows what was saved, the modal
closed and its parent refreshed. Do not assert that a requeue jumps the queue.

## Prerequisites

Both solved; see "Signing in" and "Seeding data" in `uitest/README.md`.

- **Admin session** — `GET /debug/sign-in` before `page.goto("/")`. Guest is
  user 2 and cannot see an admin screen, let alone call one.
- **Seed data** — through this app's API, with names unique to the run. Nothing
  resets this app's database between runs.

## Status

| # | Flow | Screens | Status |
|---|---|---|---|
| F0 | App shell and role gating | Application, About | **done** — `production-shell.spec.js` |
| F1 | Pools and resources | Pools, Pool, Resource | **done** — `production-pools.spec.js` |
| F2 | Authoring a production line | ProductionLines, ProductionLine, Operation, Section | **done** — `production-line-authoring.spec.js` |
| F3 | Versions and fork-on-edit | ProductionLineHistory, ProductionLine | not started |
| F4 | Creating a job and importing work units | Jobs, Job | not started |
| F5 | Starting and stopping a job | JobDashboard | not started |
| F6 | Monitoring: work units, detail, requeue, export | JobDashboard, WorkUnit | not started |
| F7 | Line control from the dashboard | JobDashboard | not started |
| F8 | Joining a line | ActiveJobs, JoinLine, ManufacturingLine | not started |
| F9 | Working a unit through to completion | ManufacturingLine | not started |
| F10 | Failing a unit | ManufacturingLine | not started |
| F11 | Revisiting a completed step | ManufacturingLine | not started |
| F12 | Andon: stop, block, clear | StopLine, LineBlocked, ManufacturingLine | not started |
| F13 | Leaving a line | ManufacturingLine | not started |
| F14 | Deep links | Application | not started |

Every registered controller appears at least once. **F1–F7 are admin and need
the super-user session; F8–F13 are operator flows** and are the ones a second
signed-in user would exercise.

---

## F0 — App shell and role gating — done

**Spec:** `uitest/tests/production-shell.spec.js` · 3 tests, passing.

**Proves:** the app launches, `GET /me` decides which menu items exist, and the
About modal opens.

1. Sign in as admin, launch the app.
2. The application menu lists Jobs, Production Lines, and Pools.
3. About opens from the menu.

**Endpoints:** `GET /me`

**Harness added while writing it**, all in `uitest/lib/boss.js`:

- `signInAsAdmin(page)` — takes a super-user session from `/debug/sign-in`
  before the page loads.
- `clickMenuItem(page, menuName, label)` — opens an OS bar menu and clicks an
  item. `styleUIMenu` replaces each `<option>` with a `.ui-popup-choice` div
  and hides them until the label is clicked, so a test cannot click an
  `<option>` directly.
- `windowByTitle` now matches `.ui-modal` as well as `.ui-window`, and finds
  the title by class alone — a window nests it in `.top > .title > span` while
  a modal declares a bare `.title`. It previously missed every modal.

---

## F1 — Pools and resources — done

**Spec:** `uitest/tests/production-pools.spec.js` · 4 tests, passing.

**Proves:** the create/edit round trip, and that a modal's save refreshes the
list behind it.

1. Application menu → Pools. The list renders.
2. `Add` opens Pool. Enter a name, Save. Pools lists it.
3. Reopen it, `Add` under Resources opens Resource. Enter name and value, Save.
   The resource appears in Pool's list without a reload.
4. Rename the pool. The new name shows in Pools.

**Endpoints:** `GET /pools`, `POST /pool`, `PUT /pool/{id}`, `GET /pool/{id}`,
`POST /pool/{id}/resource`, `PUT /resource/{id}`

**Edge worth covering, not yet written:** deleting a pool a production line
requires — the 409 reaches the user as a message naming what blocks it, rather
than a silent failure.

**Harness fixed while writing it:** `windowByTitle` matched a title as a
*substring*, so asking for `Pool` also returned `Pools` — and both are open at
once. It now anchors the match. This app alone has three such pairs
(Pool/Pools, Job/Jobs, ProductionLine/ProductionLines), so it would have hit
most of the flows below.

---

## F2 — Authoring a production line — done

**Spec:** `uitest/tests/production-line-authoring.spec.js` · 4 tests, passing.

**Proves:** the deepest nesting in the app — line → operation → section — and
that the server-rendered preview draws.

1. Production Lines → `Add`. Name it, declare three columns, require the pool
   from F1. Save.
2. `Add` under Operations opens Operation. Name it, Save.
3. `Add` under Sections opens Section. Add a description whose body carries
   `{work_unit.<column>}` and `{pool.<pool>}`. Save.
4. Add a required text section named `serial`.
5. The preview panel shows the description with tokens resolved to `«Column»`
   placeholders — proving `GET /operation/{id}/preview` is what draws it.
6. Reorder the two sections; the order persists after reopening.

**Endpoints:** `GET /production-lines`, `POST /production-line`,
`GET /production-line/{id}`, `POST /production-line/{id}/operation`,
`GET /operation/{id}`, `POST /operation/{id}/section`,
`GET /operation/{id}/preview`

**Not yet covered:** reordering sections (step 6 above).

**Harness added while writing it:** `action(win, fn)` finds a button by the
controller function its `onclick` names — several buttons per window read
`Add`, so the label alone is ambiguous. `selectPopupOption` drives a pop-up the
way a user does, centring the control first: these forms are long, the choices
open beside their control, and a menu near the bottom opens its list past the
fold.

---

## F3 — Versions and fork-on-edit

**Proves:** the reload-on-`forked` contract. Editing a frozen version returns
new operation and section ids, and a screen holding the old ones must reload
rather than write to something that no longer exists.

1. With a job started against the line (F4/F5), reopen the production line.
2. Rename an operation and Save. The response carries `forked: true`.
3. The form reloads: the operation list shows the new ids and version 2.
4. History shows two versions; version 1 is marked frozen and its detail is
   read-only.

**Endpoints:** `PUT /operation/{id}`, `GET /production-line/{id}/versions`,
`GET /production-line-version/{versionId}`

---

## F4 — Creating a job and importing work units

**Proves:** the only file upload in the app, and the preview-then-commit
handshake.

1. Jobs → `Add`. Name it, choose the production line, set the dates. Save.
2. Choose a CSV. The preview shows the row count and no errors.
3. Commit. The job shows its work unit count.
4. A CSV missing a declared column shows the error naming that column, and
   commit stays unavailable.

**Endpoints:** `GET /jobs`, `POST /job`, `GET /production-lines`,
`POST /job/{id}/work-units/preview`, `POST /job/{id}/work-units/commit`

---

## F5 — Starting and stopping a job

**Proves:** lifecycle buttons, and that the dashboard redraws from the result.

1. Open the job's dashboard. Start. Stats show the units pending, job active.
2. Stop. The job reads inactive.
3. Starting a job with no work units surfaces the refusal as a message.

**Endpoints:** `GET /job/{id}/dashboard`, `POST /job/{id}/start`,
`POST /job/{id}/stop`

---

## F6 — Monitoring: work units, detail, requeue, export

**Proves:** the list filter, the read-only modal, and a real file download.

1. The work unit list renders one row per unit, showing state and operator.
2. Filter by state; the list narrows.
3. Selecting a unit opens WorkUnit: its input columns, per-operation log, and
   captured values.
4. Requeue is available only for a failed unit, and the list reflects the
   change afterwards.
5. `Export CSV` downloads a file — assert the download, not the bytes.

**Endpoints:** `GET /job/{id}/work-units?state=`, `GET /work-unit/{id}`,
`POST /work-unit/{id}/requeue`, `GET /job/{id}/export`

---

## F7 — Line control from the dashboard

**Proves:** the five shared line routes carry an **admin** origin when called
from here, which is what makes "only the origin that raised a block may clear
it" observable.

1. With an operator on a line (F8), pause it from the dashboard. The row shows
   paused, origin admin.
2. The operator's own screen cannot resume it — the refusal reaches them.
3. Resume from the dashboard. The row returns to working.
4. Leave, from the dashboard, ends that operator's line.

**Endpoints:** `POST /line/{id}/pause` · `/resume` · `/stop` · `/resume-line` ·
`/leave`

---

## F8 — Joining a line

**Proves:** the operator's entry path, and that a required pool forces a choice.

1. Active Jobs lists the running job with its units remaining.
2. Join opens JoinLine, listing the required pool and its free resources.
3. Choosing a resource and joining opens ManufacturingLine.
4. A job whose only resource is already taken shows the reason and offers no
   join.

**Endpoints:** `GET /active-jobs`, `GET /job/{id}/join-info`,
`POST /job/{id}/join`, `GET /line/{id}/state`

---

## F9 — Working a unit through to completion

**Proves:** the core operator loop, and that sections arrive already rendered.

1. Pull. The unit's label and the first operation appear.
2. The description shows real values — no `{` remains in the text.
3. The required field is empty, so Complete is unavailable.
4. Fill it, Complete. The next step is shown.
5. Complete the last step. The unit reads complete and the queue offers the
   next one.

**Endpoints:** `POST /line/{id}/pull`,
`POST /work-unit/{id}/operation/{step}/complete`

---

## F10 — Failing a unit

**Proves:** notes are enforced by the screen, not only by the server.

1. Fail without notes — refused, with the reason shown.
2. Fail with notes. The unit leaves the line and the dashboard shows it failed.

**Endpoints:** `POST /work-unit/{id}/operation/{step}/fail`

---

## F11 — Revisiting a completed step

**Proves:** the edit path and its warning, which is the one place the UI must
tell the operator that saving costs them work.

1. Navigate back to a completed step. The revisit banner appears and the
   primary button reads `Save changes`.
2. Change the value and save. Later steps reset, and the operator lands on the
   first step that is now incomplete.

**Endpoints:** `POST /work-unit/{id}/operation/{step}/edit`

---

## F12 — Andon: stop, block, clear

**Proves:** the blocking modal opens on a stop and closes when the block is
cleared elsewhere — the one flow driven by a notification rather than a click.

1. Raise the andon from the line, giving a reason. StopLine takes it.
2. The line reads stopped and LineBlocked covers the screen.
3. An admin clearing it from the dashboard closes the modal without the
   operator touching anything.

**Endpoints:** `POST /line/{id}/stop`, `POST /line/{id}/resume-line`,
event `io.bithead.production.line-status`

---

## F13 — Leaving a line

**Proves:** the resources come back and the held unit returns to the queue.

1. Leave. The line closes.
2. The pool's resource is available again.
3. The unit that was in hand is pending, and the next pull hands it back.

**Endpoints:** `POST /line/{id}/leave`

---

## F14 — Deep links

**Proves:** the four routes in `plan.md` open the right screen for the right
role.

| Link | Opens |
|---|---|
| `production://` | Active Jobs for an operator, Jobs for an admin |
| `production://jobs` | Active Jobs |
| `production://line/{jobId}` | Joins or resumes, then Manufacturing Line |
| `production://job/{jobId}` | Job Dashboard, admin only |

---

## Findings

Defects UI testing turned up, as opposed to gaps in coverage.

### 1. Envelope reads survived the Stage 5 reconciliation

`Jobs.html`, `Pools.html`, and `ProductionLine.html` each still unwrapped a
list from an envelope — `response.jobs`, `response.pools` — against routes that
return a bare array. Silent: the call succeeds and the screen renders nothing.

The `models` check could not see them, because `pools` and `jobs` are real
fields on *other* models, so the names resolved. `bin/validate-app` gained a
second check for exactly this: a route whose `response_model` is `List[...]`
must be read as an array. Fixed and enforced.

### 2. A pop-up menu's first option is its label, never a choice

`UIPopupMenu.selectedValue()` returns `null` when index 0 is selected — "the
option label is not a selectable value" — and `styleOptions` renders choices
from index 1, so option 0 never appears in the list. A real choice placed there
can be shown as a default and then never selected again.

Two controllers had done it:

- **`Section.html`** declared `Description` as option 0. `applyType()` read
  `null` and hid *every* field group, so `Add section` rendered an empty form —
  nothing but the type menu. Fixed: option 0 is now a `Choose a type` prompt,
  and `save()` refuses until a type is chosen.
- **`JobDashboard.html`**'s work unit filter declared `All` as option 0. Two
  bugs: the list loaded with `?state=null`, which matches no state, so the
  default view was empty; and once a state was chosen the user could never
  return to All. Fixed: option 0 is a `Filter` label, `All` is a real choice,
  and an absent filter sends no `state` at all.

The correct form is `<option value="">Choose one</option>` — `Job.html` and
`ProductionLine.html` already had it right.

**Eight more live in `io.bithead.scheduler`** and are untouched, since that app
is mid-flight: `BusinessConfig` (timezone, slot-increment), `Employee` and
`EmployeeProfile` (add-day-select), `FinancialReport` (period, quarter),
`Job` (payment-method), `SuperAdminBusiness` (timezone). Each has a real value
on option 0 and will behave the same way.

### 3. Two Production tests live in the tutorial spec, and are stale

`uitest/tests/tutorial-example.spec.js` holds two tests that drive **Production**
rather than the Tutorial. Both were failing; they were written against Stage 1
fixture data and hard-code it.

- `stays anchored inside a modal @popup-anchor` — **flaky.** It passed once
  after the first-option fix in Finding 2, and fails again: the Section modal
  now renders correctly (its label reads `Choose a type`) but the click is
  intercepted. The test opens the modal directly with
  `configure({ operationId: 1 })` instead of going through the app, so whatever
  else is on the desktop decides whether it works. It was reporting a real
  defect all along, in a file where nobody would look for it.
- `does not make its parent scroll sideways @popup-width` — **still fails.** It
  calls `configure(1)` for a line id and clicks an operation named `Configure`
  in `.mfg-steps`. That fixture is gone.

Both guard real regressions — modal pop-up anchoring, and the horizontal scroll
on the manufacturing screen — so the assertions are worth keeping. Fold them
into **F2** (Section, in a modal) and **F9** (ManufacturingLine) against seeded
data, then delete them from the tutorial spec, which should only cover the
component library.
