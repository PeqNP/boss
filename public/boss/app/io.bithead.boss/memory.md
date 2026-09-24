# Session Memory — BOSS

Stage 3 is built and waiting for a look at the tests. Stage 4, wiring the routes to `lib`, is next after that.

## Watch out for

- `guest_workspace`, `get_workspace`, `save_workspace`, `remove_desktop`, and `remove_dock` are in `lib.py`. The routes still return the lists hardcoded in `__init__.py`.
- `db.links` is how a test sees that the guest rows are user id 2, and that a second read did not insert more rows. `Workspace` does not carry the user id or a row count.
- An installed app with no icon cannot be saved. Every system app is refused first, and every other installed app has an icon, so that check has no catalog row that reaches it.
- `~/.boss/db/workspace.sqlite3` holds the guest desktop for user id 2. Tests use `test-workspace.sqlite3`.
- Add, drag, and Delete on screen still update the workspace in memory. Stage 5 points those stubs at the network.
- `UIContextMenu` is in `ui.js`. A desktop icon id contains dots, so match it with `[id="..."]`.
- `check_user` refuses a caller whose id is not the id in the path, including user 1.

## Open

1. Look at Stage 3. Stage 4 waits on that.
