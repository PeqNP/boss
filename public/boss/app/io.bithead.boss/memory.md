# Session Memory — BOSS

Stage 2 is built and waiting for a look at the database. Stage 3, the private tests, is next after that.

## Watch out for

- `~/.boss/db/workspace.sqlite3` holds the guest desktop for user id 2: JSON Formatter, Tutorial, Lean Visualizer, Wordy. The dock has no guest rows.
- `GET /workspace/guest` and `GET /workspace/{user_id}` still return the lists hardcoded in the routes. They start reading this database in Stage 4, after the tests.
- Add, drag, and Delete still update the workspace in memory. `saveWorkspace`, `deleteDesktopApp`, and `deleteDockApp` are the stubs Stage 5 points at the network.
- `UIContextMenu` is in `ui.js`. A table row can hand it items. Stage 1 wired the desktop icon and the dock icon.
- A desktop icon's id is `desktop-icon-<bundleId>`. The bundle id contains dots, so a CSS `#id` selector does not match it. Use `[id="..."]`.
- `boss.dbm` has no keys. Nothing writes `desktop/{user_id}`. There is nothing to migrate.
- `check_user` refuses a caller whose id is not the id in the path, including user 1.
- User id 2 is the guest, in `os.js` and in `Global.guestUserId`. A new account starts from a different list than the guest seed.

## Open

1. Look at Stage 2. Stage 3 waits on that.
