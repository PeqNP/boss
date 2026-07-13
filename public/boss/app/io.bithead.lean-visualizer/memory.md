# Lean Visualizer Memory

## Current Architecture
Lean Multi-Track Production Simulator is a one-page app implemented entirely in [public/boss/app/io.bithead.lean-visualizer/index.html](public/boss/app/io.bithead.lean-visualizer/index.html).

- No framework and no build step.
- HTML, CSS, and JavaScript are colocated.
- Runtime state is loaded from and saved to a private BOSS SQLite-backed document API.
- State can still be exported/imported as JSON.

## Latest Design Direction
- Keep the page as a single-screen operational workspace with table-based editing.
- Application controls live in the top "Application State" panel: Jira sync, export, import, clear-all.
- Schedule is a floating panel toggled by the fixed "Schedule" button.
- Releases are managed through a modal opened from the schedule panel.
- Backlog supports drag-and-drop ordering plus visual dividers.
- Save state is visible in two places: panel badge and floating status pill.

## Private BOSS Service Integration
The page communicates with a private BOSS service for both model persistence, Jira sync, and task metrics sync.

- Model endpoints:
  - `GET /api/io.bithead.lean-visualizer/model`
  - `PUT /api/io.bithead.lean-visualizer/model`
- Persistence design:
  - Single SQLite document row
  - Stored under shared private-service `db_path`, not alongside source files
  - Includes schema version and revision for model evolution and write coordination
- Autosave behavior:
  - Save on committed model changes only
  - Do not save while typing into inline editors
  - Import and Jira sync also trigger persistence after model mutation
- Task metrics endpoints:
  - `GET /api/io.bithead.lean-visualizer/metrics`
  - `GET /api/io.bithead.lean-visualizer/metrics-window`
  - `POST /api/io.bithead.lean-visualizer/sync-task-metrics`
- Task metrics design:
  - Stored in a separate SQLite table in the same private-service database file
  - Keyed by operator name, metric year, and metric week number
  - Sync writes one row per operator per selected week
  - `week_start` selects viewed and synced week
  - Default metrics week is the previous full week
  - Task metrics update the read-only operator metrics table and are not saved in the main model

- Endpoint: `GET /api/io.bithead.lean-visualizer/sync-jira`
- Caller: `syncJiraIssues()` in [public/boss/app/io.bithead.lean-visualizer/index.html](public/boss/app/io.bithead.lean-visualizer/index.html)
- Expected payload:
  - `issues`: array of Jira issue records
  - `jiraRootUrl`: optional Jira base URL used to render clickable issue links
- Sync behavior:
  - Updates existing features by `issueKey`
  - Adds missing Jira issues to backlog as new features
  - Re-renders forecasts after sync
  - Shows progress modal while working
  - Shows success/failure results in an OK-only status dialog, not alerts

## Data Notes
Primary app state:
- `operators`
- `tracks`
- `backlog`
- `releases`

Jira-linked work item fields in use:
- `issueKey`
- `jiraIssueType`
- `units` (total)
- `completedUnits`

Estimate-related behavior:
- `manualEstWeeks` is an override, not just a fallback.
- If `manualEstWeeks > 0`, it takes precedence over computed estimate weeks even when `units > 0`.
- If `manualEstWeeks > 0` and `units > 0`, the Est. Weeks display turns red to indicate a discrepancy.
- Setting Est. Weeks to `0` or clearing it removes the override.
- If there are no units and no manual override, Est. Weeks displays `∞`.
- Infinite durations must not produce invalid dates; estimated dates should render as absent (`—`) in that case.

Operator metrics behavior:
- Units / Week, Planned Work, and Unplanned Work are read-only and come from task metrics.
- Planned Work is derived as `Units / Week - Unplanned Work`.
- Track capacity and completion forecasting use previous full-week metrics as the planning baseline.
- The operator section shows the viewed week label as a Sunday-Saturday range.
- Previous Week and Next Week navigate the viewed week.
- Next Week is disabled when advancing would exceed the current calendar week.
- Track-association labels use shortened operator names: first name plus the first character of the second name part.

Task Metrics graph behavior:
- View Task Metrics opens a modal graph window.
- The graph uses X axis as weeks and Y axis as Units / Week.
- One line is rendered per operator.
- Window size is 5 weeks.
- Default graph window is the last 5 weeks ending at current week.
- Historical segments are blue.
- If current week is included, only the segment from previous week to current week is green (live).
- Previous 5 Weeks and Next 5 Weeks shift the graph window by 5.
- Next 5 Weeks is disabled when there are no weeks beyond current week.

Status dialog behavior:
- Use the in-app status dialog for results and failures instead of `alert()`.
- Dialog content can include a key/value metrics table.
- Dialog is intentionally non-dismissible except for the OK button.

## Editing Guidance
- Prefer targeted edits in [public/boss/app/io.bithead.lean-visualizer/index.html](public/boss/app/io.bithead.lean-visualizer/index.html); avoid introducing a framework.
- Preserve existing IDs, event bindings, and render flow unless a change explicitly requires rewiring.
- Keep export/import compatibility when adding state fields.
- Maintain existing desktop/mobile behavior and current visual language.
- For small private services, keeping lightweight DB helpers in `__init__.py` is acceptable; a separate `db.py` is not required.
- Before writing code in public or private app locations, first run the relevant code path to confirm there are no compilation/runtime issues.
- For the private Lean Visualizer service, test it by activating the venv with `source ~/.venv/bin/activate` and then running `python3 /Users/ericchamberlain/source/boss/private/app/io.bithead.lean-visualizer/__init__.py`.

## Verification Checklist
- Initial model load should not imply a save; status should settle to `Ready` until a real mutation occurs.
- Save badge and floating save-status pill should reflect load/save/error state correctly.
- Result/failure flows should use the in-app OK-only status dialog.
- Jira sync success dialog should show statistics as key/value rows.
- Task metrics sync should populate the read-only operator metrics table and current-week label.
- Sync Jira Issues loads data from private BOSS endpoint and updates existing rows by issue key.
- Jira key cells render links when `jiraRootUrl` is present.
- Metrics load should default to previous full week.
- Next Week navigation should advance to the next adjacent week and update label/table.
- `POST /sync-task-metrics?week_start=YYYY-MM-DD` should succeed for valid Sunday week starts.
- Task Metrics modal should open, show 5-week windows, and page by 5-week windows.
- Export and import still round-trip state.
- Autosave persists only canonical state fields: operators, tracks, backlog, releases.
- Manual Est. Weeks override should win over computed values and turn red when units also exist.
- Clearing Est. Weeks should return to computed behavior, or `∞` when there is no computable estimate.
- Schedule panel toggle and releases modal still behave correctly.
- Backlog drag-drop and divider behavior still works.

## Context Window Hygiene
- Keep this memory file concise and current; remove stale behavior notes when architecture changes.
- Prefer one canonical bullet per behavior instead of repeating details across sections.
- Store week-selection rules once and reference them, rather than re-describing them in every feature note.
- When implementing iterative UI features, validate with narrow endpoint checks first to avoid long trial-and-error loops.
- In chats, summarize deltas only (what changed since last step) to limit repeated context.
- Batch related validation checks and report one consolidated result.
- Use short stable labels for repeated decisions instead of restating full rules each turn.
- Restate architecture only when it changes.
- Keep interim progress updates to one sentence unless blocked.
- Already-consumed in-thread context cannot be reduced retroactively.
- If immediate context reduction is needed, start a fresh chat and reference this memory file.
