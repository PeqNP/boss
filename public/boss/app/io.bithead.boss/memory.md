# Session Memory — BOSS

Stage 4 is built and waiting for a look at the routes. Stage 5, pointing the desktop and dock at those routes, is next after that.

## Watch out for

- `GET /workspace/guest` reads the seed: JSON Formatter, Tutorial, Lean Visualizer, Wordy, and an empty dock.
- `GET /workspace/{user_id}` writes the starting list on the first read. User id 2 is answered 400. Another user's id is answered 403.
- `PUT /workspace/{user_id}` replaces both lists. `DELETE` on the desktop or the dock removes one icon. A refusal is HTTP 400 and the message from `ValidationError`.
- `GET /workspace/desktop/...` and `GET /workspace/dock/...` are gone. They added an icon and checked nobody.
- The screen still saves in memory. `saveWorkspace`, `deleteDesktopApp`, and `deleteDockApp` are the stubs Stage 5 points at the network.
- `db.links` is how a test sees the guest rows are user id 2, and that a second read did not insert more rows.
- `check_user` refuses a caller whose id is not the id in the path, including user 1.
- A desktop icon id contains dots, so match it with `[id="..."]`.

## Open

1. Look at Stage 4. Stage 5 waits on that.
