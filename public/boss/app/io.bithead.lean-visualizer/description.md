# Lean Visualizer

A signed-in engineering board that forecasts feature delivery from Jira issues and operator performance, and a capacity report an admin opens with leadership.

## Who

| Actor | What they do |
|---|---|
| Admin | Edit the board, sync Jira, save a release checkpoint, read the report. The first admin is the person who runs the board today. |
| Employee | Read the schedule and the capacity report. |

An admin or an employee is a BOSS account granted that role, the way Scheduler grants a role. Leadership, product, and anyone without one of those roles do not sign in. An admin opens the report with leadership.

## What happens

Someone signs in and the app opens on the role. An admin lands on the board: operators, tracks, a backlog of feature requests, and a schedule with release dates drawn on it. Releases fall about every two weeks. Sync pulls open feature requests from Jira. Each feature keeps the color of its dot. The new app uses the BOSS desktop.

A work unit is one Jira issue, meant to be one or two days. An operator's rate is the average of their planned issues per week over the last eight complete weeks. Unplanned issues in that same window sit beside the rate and stay out of it. A feature with a manual estimate in weeks uses that estimate. Otherwise its duration is its remaining issues divided by the rate of the track it is on. A track's capacity is the sum of the rates of the operators on it. An operator with no synced week has a rate of zero. An operator with fewer than eight weeks is averaged across the weeks they have.

The weekly sync stays. It is what feeds that eight-week rate. The history already stored runs from the week of 28 December 2025.

The capacity report is a view in the same app. An employee opens on the report and the schedule. An admin opens the report from the board. It shows:

- Planned versus unplanned work, per operator, for the last eight complete weeks and for the stored history.
- Allocation by strategic pillar. The pillars are Growth / Acquisition, New Features / Retention, Tech Debt / Stability, and Process Efficiency / Cost Savings, read from the Strategic Pillar field on the feature request. A feature with no pillar is Unassigned and stays on the report. A feature with more than one pillar counts in each. Process Efficiency / Cost Savings is the work that saves time or reduces operational effort. New Features / Retention and Growth / Acquisition are the work that improves the client experience. Tech Debt / Stability is capacity spent keeping the product working.
- Material changes since the last release checkpoint: forecasted finishes that moved by two weeks or more.

The look back covers the stored weekly throughput and the feature requests finished over that stretch, grouped by pillar. Forecast accuracy starts with the first checkpoint.

When a release date is today or earlier, an admin can save a checkpoint for it. The window is the day after the previous release through this release's date. The first release uses the fourteen days ending on its date. The save records the issues completed in that window, by the same rules as the weekly sync, and it records each open feature's forecasted finish and the eight-week rate as they stood then.

The checkpoint, the pillars, and the rates are stored with the board. Every route requires a signed-in Admin or Employee. The old single page is not a client of this app.

Feature-request review asks how a feature will be validated in the full customer workflow.

## Out of scope

- A login for leadership or product
- Recording the validation question, or the other customer questions, on a feature
- Choosing a strategic pillar inside this app
- A forecast for a release that was never checkpointed
- A checkpoint for a release date that has not arrived
- A checkpoint that saves itself while nobody is here
- Keeping the old single page working. `index.html` is not a client
- Sprint commitments, and calling a release a sprint
- Removing the weekly sync
