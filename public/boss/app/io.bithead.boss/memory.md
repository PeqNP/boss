# Session Memory — BOSS

Stage 1 is built and waiting for a look at the desktop, the dock, and Applications. Stage 2, the workspace database, is next after that.

## Watch out for

- The live `GET` still returns today's guest list. JSON Formatter, Tutorial, Lean Visualizer, and Wordy arrive with the database in Stage 2.
- Add, drag, and Delete update the workspace in memory. `saveWorkspace`, `deleteDesktopApp`, and `deleteDockApp` are the stubs Stage 5 points at the network.
- `UIContextMenu` is in `ui.js`. A table row can hand it items. This stage wires the desktop icon and the dock icon.
- A desktop icon's id is `desktop-icon-<bundleId>`. The bundle id contains dots, so a CSS `#id` selector does not match it. Use `[id="..."]`.
- `boss.dbm` has no keys. Nothing writes `desktop/{user_id}`. There is nothing to migrate.
- `check_user` refuses a caller whose id is not the id in the path, including user 1.
- User id 2 is the guest, in `os.js` and in `Global.guestUserId`. The guest workspace is that user's rows, and a new account starts from a different list. The client loads the guest with `GET /workspace/guest`.

## Open

1. Look at Stage 1. Stage 2 waits on that.
