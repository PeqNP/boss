# Lean Visualizer — UI test coverage

`plan.md` is the implementation contract: what each screen is and what each route answers. This is the coverage contract: which flows are tested, in what order, and what each one has to prove.

They are separate because UI testing is long and interruptible. The table below is what lets it stop and resume — it says what is done, so nobody has to remember a conversation.

## What a flow is for

A UI test proves the **wiring**: that a screen calls the right endpoint and puts the answer in the right place. The rules are settled by the private suite — the eight-week rate, the fourteen-day change, who a route allows, the checkpoint window. Asserting those again through a browser buys nothing.

So each flow below earns its place by catching what the private suite is blind to: a renamed field, a call sent to the wrong path, a response nobody reads, a menu item wired to nothing.

Keep to happy paths plus a little edge cover. See [`process.md` § When to Write Tests](../../../docs/prompt/process.md). No assertion about pixels, widths, or colours.

## Order

Dependency first.

1. **Who opens what** comes first. Later flows open a window by its menu, and that menu depends on the role.
2. **The board** next. The report, the schedule, and the other windows read what the board saved.
3. **The capacity report**, then **the schedule**. Both are views of that save.
4. **The windows the board opens** last: releases, checkpoint, tasks, finished work, notes, and a virtual feature.

## Flows

| # | Flow | Spec | Must prove | Status |
|---|---|---|---|---|
| 1 | Who opens what | `lean-visualizer-access.spec.js` | An admin opens on the Board. Dashboards lists Board and Capacity report, and not Schedule. Board File lists Sync Feature Requests, Finished work, Releases, Save Checkpoint, and Schedule. An employee opens on the Capacity report, with Save Checkpoint hidden. Dashboards lists Board, Capacity report, and Schedule. The board opens and offers no way to edit it: File lists Finished work and Schedule. The schedule hides Manage Releases | **Done** — 2 specs |
| 2 | The board saves and reads back | `lean-visualizer-board.spec.js` | An operator, a track, and a backlog feature saved with `PUT /model` show in those tables. The feature cell is the issue key, then the name. Renaming the operator and reopening the board shows the new name | **Done** — 2 specs |
| 3 | Capacity report | `lean-visualizer-report.spec.js` | Dashboards > Capacity report shows that operator. The rate row is Planned, Rate, Unplanned, Rate, Total Rate, and Weeks. The pillar table lists every pillar, including one with no features, with Open features and Distribution. An admin sees Save Checkpoint | **Done** — 1 spec |
| 4 | Schedule | `lean-visualizer-schedule.spec.js` | File > Schedule shows the track's name and the feature on it. A release dated inside the next 180 days shows its version on the chart. A release dated before today does not | **Done** — 1 spec |
| 5 | Windows the board opens | `lean-visualizer-windows.spec.js` | Releases lists a release dated today or later and leaves out one dated before today. Save Checkpoint lists a release dated today or earlier and is not saved. View Tasks shows the week it asked for. Finished work shows a year of 2026 or later. A note saves and reads back. A virtual feature saves onto the backlog and reads back | **Done** — 1 spec |

## Findings

Defects and blockers UI testing turns up, so a later session can tell a gap in coverage from a gap in the app.

| Flow | Finding | Fixed |
|---|---|---|
| — | `db.py` does not expose `get_db_path`, `delete_database`, and `start_database`, so `GET /api/debug/uitests/reset` skips this app. A spec run against the live file would replace the board the developer is using. Do not add `create_schema`. `bin/check-db --fix` deletes and rebuilds an app that has both `create_schema` and `get_db_path` | No |
| 1 | Settings grants Employee with the license left off, because this app does not declare `licensed`. Access still requires the app in the session, so that account is refused and `GET /me` answers 401. The spec issues the license itself | No |
| 3 | Weekly rates and pillar tags are written by the Jira sync. No route seeds either without calling Jira. Flow 3 proves the rows render, including zeros. The numbers themselves stay in the private suite | — |
| 5 | Saving a checkpoint calls Jira. The spec opens the modal and reads the release. It does not click Save. Finished work names the fixture `finished-work-empty` through `PUT /api/debug/uitests/jira/{bundle}` and clears it when the spec ends. While that fixture is loaded, every Jira call from this app on this machine uses it | — |

## What every flow has to do

**Sign in before the page loads.** `bootBOSS` alone is nobody, and every route answers 401. `GET /debug/sign-in` is the admin session. The employee half of flow 1 needs an account that holds the Employee role and is not the superuser. This app does not grant that role. BOSS Settings does.

**Seed through `PUT /model`.** That is the save the board itself makes. Do not write the SQLite file from a spec.

**Close what a test opens.** A window left open outlives the test. Close it with the screen's own Close.

**Wait until the loaded text is there, then read it.** The window is visible before `viewDidLoad` has filled it. Assert through `expect`, which retries.
