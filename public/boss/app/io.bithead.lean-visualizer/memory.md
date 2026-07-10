# Lean Visualizer Memory

## Current Architecture
Lean Multi-Track Production Simulator is a one-page app implemented entirely in [public/boss/app/io.bithead.lean-visualizer/index.html](public/boss/app/io.bithead.lean-visualizer/index.html).

- No framework and no build step.
- HTML, CSS, and JavaScript are colocated.
- Runtime state is in-memory and can be exported/imported as JSON.

## Latest Design Direction
- Keep the page as a single-screen operational workspace with table-based editing.
- Application controls live in the top "Application State" panel: Jira sync, export, import, clear-all.
- Schedule is a floating panel toggled by the fixed "Schedule" button.
- Releases are managed through a modal opened from the schedule panel.
- Backlog supports drag-and-drop ordering plus visual dividers.

## Private BOSS Service Integration
The page now communicates with a private BOSS service for Jira data.

- Endpoint: `GET /api/io.bithead.lean-visualizer/sync-jira`
- Caller: `syncJiraIssues()` in [public/boss/app/io.bithead.lean-visualizer/index.html](public/boss/app/io.bithead.lean-visualizer/index.html)
- Expected payload:
  - `issues`: array of Jira issue records
  - `jiraRootUrl`: optional Jira base URL used to render clickable issue links
- Sync behavior:
  - Updates existing features by `issueKey`
  - Adds missing Jira issues to backlog as new features
  - Re-renders forecasts after sync
  - Shows progress modal and user-visible success/failure alerts

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

## Editing Guidance
- Prefer targeted edits in [public/boss/app/io.bithead.lean-visualizer/index.html](public/boss/app/io.bithead.lean-visualizer/index.html); avoid introducing a framework.
- Preserve existing IDs, event bindings, and render flow unless a change explicitly requires rewiring.
- Keep export/import compatibility when adding state fields.
- Maintain existing desktop/mobile behavior and current visual language.

## Verification Checklist
- Sync Jira Issues loads data from private BOSS endpoint and updates existing rows by issue key.
- Jira key cells render links when `jiraRootUrl` is present.
- Export and import still round-trip state.
- Schedule panel toggle and releases modal still behave correctly.
- Backlog drag-drop and divider behavior still works.
