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
- Save state is visible in two places:
  - Persistent badge in the top Application State panel
  - Floating top-center status pill that auto-hides after a few seconds
- Avoid browser alerts for app workflows; use in-app dialogs instead.

## Private BOSS Service Integration
The page communicates with a private BOSS service for both model persistence and Jira sync.

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

## Verification Checklist
- Initial model load should not imply a save; status should settle to `Ready` until a real mutation occurs.
- Save badge and floating save-status pill should reflect load/save/error state correctly.
- Result/failure flows should use the in-app OK-only status dialog instead of alerts.
- Jira sync success dialog should show statistics as key/value rows.
- Sync Jira Issues loads data from private BOSS endpoint and updates existing rows by issue key.
- Jira key cells render links when `jiraRootUrl` is present.
- Export and import still round-trip state.
- Autosave persists only canonical state fields: operators, tracks, backlog, releases.
- Manual Est. Weeks override should win over computed values and turn red when units also exist.
- Clearing Est. Weeks should return to computed behavior, or `∞` when there is no computable estimate.
- Schedule panel toggle and releases modal still behave correctly.
- Backlog drag-drop and divider behavior still works.
