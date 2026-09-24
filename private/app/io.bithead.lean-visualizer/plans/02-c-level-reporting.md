# 02 — C-level reporting

Status: confirmed. Stage 1 is the current stage.

This plan tells a reader why a tracked feature's place in the pipeline changed. It does not amend [01-plan.md](01-plan.md). The built app stays as that plan describes it, including the fourteen-day material change, until this plan ships.

Existing routes stay live. `POST /snapshots` and `GET /material-log` are stubbed in the client until Stage 5.

## Out of scope

- A log entry for every save of the board while the order is still being arranged
- A material-change row for a feature request that is finished, or for one that stays below the sync line
- Inferring a blockage from the dates. An admin writes the span
- Changing a log entry after the snapshot that recorded it, except the end date of a blockage that was still open
- Sprint commitments, and calling a release a sprint

## Stage 1 — UI/UX

`Blockage` is a document. `Report` stays a report. No draft is created on open.

### `Blockage`

Audience: Admin. Document window. Opened from a tracked feature on the board. `configure({ featureId, blockageId })`. An Employee has no control that opens it. The board save is the existing `PUT /model`.

One span: begin date, end date, note. An empty end date means the feature is still blocked. Begin defaults to today on a new span. Cancel closes without a save. Delete removes that span from the feature. Save writes the span onto the feature and the board save runs. A tracked feature with an open span shows Blocked and opens that span. Add blocked span starts a new one. Spans already ended are listed in the window so a note can be corrected before the next snapshot. A feature below the sync line has no Blocked control.

### `Report`

Section 3 is the priority log from `GET /material-log`.

The section is empty until two snapshots exist, and the empty text says a snapshot is the baseline. After that it lists each still-open tracked feature that has one or more entries. The feature cell is the issue key, as a link to Jira, then a colon, then the description. The description is one line and ellipsizes at the column edge. Log opens `MaterialLog`. The report does not list finished features.

An Admin sees Save Snapshot beside Save Checkpoint. It sends `POST /snapshots` and reloads the log. Save Checkpoint reloads the log as well, because that save also writes a snapshot. An Employee sees neither button. The other two sections of the report are unchanged and keep calling `GET /report`.

```
GET /material-log -> Report
    acl:   report.r
    who:   Admin, Employee
    scope: the one board
    returns: MaterialLog
```

```
POST /snapshots -> Report, Board
    acl:   checkpoint.w
    who:   Admin
    scope: the one board
    returns: MaterialLog
           403 for an Employee.
```

Until Stage 5 the client stubs both calls. The stub log has one feature with more than five entries, including a blockage, so the modal can be judged. The stub posts nothing.

### `MaterialLog`

Audience: Admin and Employee. Modal. Opened from Log on the report. `configure({ name, entries })`. Read only. Close.

The table shows five rows. Further rows scroll, and the header stays put. Columns: Date, End when any entry is a blockage, Note, Days. Date is the day the entry was written, which is also the day the change started. End is an em dash except on a blockage. A blockage with no end date shows TBD. Note is one line, ellipsized, and a balloon from the bottom left shows the rest. Days is the impact of that entry. Rows are newest first. The last row stays put, separated by a 1px line, and reads Total impacted days. It is the sum of the Days column.

### `Board`

File gains Save Snapshot for an Admin, the same `POST /snapshots` as the report. An Employee's File menu does not list it. The Blocked control is on a tracked feature only, and only for an Admin.

## Stage 2 — Data Model

A blockage span lives on the feature inside `state_json`, not in its own table. The field is `blockages`: a list of `id`, `beganOn`, `endedOn`, `note`. `endedOn` is empty while the span is open. `PUT /model` stores the board as it does today. The model schema version stays `1`.

The `versions` table is at `1.0.0`. Migration `1.1.0` creates the four tables below and inserts `1.1.0`. Live database stays. Tests use `test-lean-visualizer.sqlite3` and create it themselves. Nothing in this plan deletes the live file.

```sql
CREATE TABLE IF NOT EXISTS priority_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saved_at TEXT NOT NULL,              -- ISO local time
    source TEXT NOT NULL                 -- snapshot | checkpoint
);
```

```sql
CREATE TABLE IF NOT EXISTS priority_snapshot_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    feature_id TEXT NOT NULL,
    issue_key TEXT,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    placement TEXT NOT NULL,             -- track | backlog | below
    track_id TEXT,
    track_name TEXT,
    position INTEGER NOT NULL,           -- index in that placement's order
    ahead_feature_id TEXT,               -- empty when this feature is first
    ahead_name TEXT,
    remaining_units INTEGER NOT NULL,
    finish_on TEXT,                      -- empty when the date is blank
    weekly_rate REAL NOT NULL,
    UNIQUE(snapshot_id, feature_id)
);
```

```sql
CREATE TABLE IF NOT EXISTS priority_log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,        -- the snapshot that produced the diff
    feature_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- entered | sequence | units | blockage | rate
    ahead_feature_id TEXT,
    ahead_name TEXT,
    units_added INTEGER,
    blockage_id TEXT,
    began_on TEXT,
    ended_on TEXT,
    note TEXT,
    days INTEGER,
    previous_rate REAL,
    rate REAL
);
```

```sql
CREATE TABLE IF NOT EXISTS priority_snapshot_finished (
    snapshot_id INTEGER NOT NULL,
    feature_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, feature_id)
);
```

`placement = below` is stored so the next diff can tell a feature that dropped under the sync line from one that left the board. It is not a log row.

### Rules the columns exist for

**Tracked set.** A feature on a lane, or a backlog feature above the system divider `system-sync-divider`. Dividers are not features. A feature with `done` true is not tracked. A feature Jira no longer returns as open is removed by the existing sync before the snapshot reads the board. Completed statuses are Done, Deployed - Prod, Released to Public, Won't Do, and Duplicate.

**Order.** On a lane, order is the schedule's bar order for that lane. In the backlog, order is the array order above the divider. `ahead_feature_id` is the previous feature in that same order.

**Diff.** Compare the new photograph to the previous snapshot. No previous snapshot means the log and the finished list are empty. The photograph is still stored.

**Entered.** In the tracked set now, and not in it on the previous snapshot. One `entered` entry. No sequence entry on that same snapshot.

**Sequence.** Still tracked, and `ahead_feature_id` changed. The note says it was reprioritized and names the feature now in front. `days` is 0. The date on the row is the snapshot that recorded the new order. A feature now first in line has an empty `ahead_feature_id`. The moved finish stays on the board and is not added into Total impacted days.

**Units.** `remaining_units` grew. `units_added` is the growth. `days` uses the same rate and rounding. A drop in remaining units is completed work and writes no entry.

**Blockage.** Each span on the feature. The first snapshot that sees the span writes one `blockage` entry with `beganOn`, `endedOn`, `note`, and `days`. `days` is `endedOn - beganOn` when the end is set, otherwise snapshot date minus `beganOn`. A later snapshot does not write a second entry for that `blockage_id`. If the first entry had an empty `endedOn` and this snapshot has the end date, that entry's `endedOn` and `days` are filled in. The note and the begin date stay as first written.

**Rate.** The finish date changed, and this feature received no entered, sequence, units, or blockage entry from this snapshot. `previous_rate` and `rate` are the weekly rates. `days` is the change in the finish date. A blank finish on either side writes no rate entry.

**Below the line.** A feature below the line in both photographs writes nothing. A feature that was tracked and is now below the line writes nothing and is not finished.

**Finished.** A feature in the previous tracked set that is not on the board at all in the new photograph. One row in `priority_snapshot_finished`. Not a log entry. The name and color come from the previous photograph.

**Who writes a snapshot.** `POST /snapshots` with `source = snapshot`. A successful `PUT /checkpoints/{releaseId}` writes one snapshot with `source = checkpoint` after the checkpoint rows are stored. Replacing a checkpoint appends another snapshot. It does not delete the earlier photograph.

### Network models

`MaterialLogEntry`: `kind`, `featureId`, `name`, `color`, `issueKey`, `aheadFeatureId`, `aheadName`, `unitsAdded`, `blockageId`, `createdOn`, `endedOn`, `note`, `days`, `previousRate`, `rate`. `createdOn` is the day the entry was written and the day the change started. `endedOn` is set only for a blockage. `note` is the sentence shown in the log. `issueKey` is on the feature, and the report links it to Jira. Fields that do not apply to the kind are empty.

`MaterialLogFeature`: `featureId`, `name`, `color`, `entries` in the order entered, sequence, units, blockage, rate.

`FinishedFeature`: `featureId`, `name`, `color`.

`MaterialLog`: `savedAt`, `previousSavedAt`, `features`, `finished`. `previousSavedAt` is empty on the baseline snapshot. `features` omits a tracked feature with no entries.

## Stage 3 — TDD

`test_snapshot`

- describe: no snapshot exists. it: the photograph is stored and the log is empty.
- describe: a second snapshot finds no difference. it: the log and the finished list are empty.
- describe: a feature stays below the sync line. it: it has no log entry.
- describe: a feature was below the line and is now above it. it: one `entered` entry, and no sequence entry.
- describe: a feature was below the line and is now on a lane. it: one `entered` entry.
- describe: the feature in front changed. it: a `sequence` entry names that feature.
- describe: remaining units grew. it: a `units` entry carries the growth.
- describe: remaining units fell. it: no `units` entry.
- describe: a blockage span is new. it: one `blockage` entry. it: the next snapshot does not write a second entry for that span.
- describe: the span was open and now has an end date. it: the existing entry gains the end date and the days.
- describe: the finish date moved and the order, the units, and the spans did not. it: a `rate` entry.
- describe: the finish date moved and the order also changed. it: a sequence entry and no rate entry.
- describe: a tracked feature is gone from the board. it: it is in the finished list and not in the log.
- describe: a tracked feature moved below the sync line. it: it is in neither list.
- describe: the caller is an Employee. it: `POST /snapshots` is refused.

## Stage 4 — Backend Implementation

`lib/snapshot.py` holds the tracked set, the photograph, and the diff. `save_checkpoint` calls it after its own rows are stored. `db.py` gains the four tables and their statements. `model.py` gains the log models. `report.py` stops computing the fourteen-day list. `GET /report` no longer returns it.

- `lib.snapshot.take_snapshot(source) -> MaterialLog`
- `lib.snapshot.latest_log() -> MaterialLog`

## Stage 5 — Integration

| Endpoint | Controller | Private |
|---|---|---|
| `POST /snapshots` | `Board`, `Report` | `lib.snapshot.take_snapshot` |
| `GET /material-log` | `Report` | `lib.snapshot.latest_log` |
| `PUT /checkpoints/{releaseId}` | `Checkpoint` | the checkpoint, then `take_snapshot` |

Done when `test_snapshot` passes against a real database. The client stops using the stub.

## Stage 6 — Grouping

`lib/snapshot.py` is the module. It may call `lib/schedule.py` for order and finish dates, and `lib/rate.py` for the lane rate. `lib/checkpoint.py` calls `take_snapshot` and does not own the diff.

## Stage 8

Amend `ui-plan.md`. The report flow must prove an Admin sees Save Snapshot and a feature's log, and an Employee sees the log and no Save Snapshot. The board flow must prove Blocked opens the document for a tracked feature and is absent below the sync line. No new flow file.

## Open Decisions

None that block Stage 4.
