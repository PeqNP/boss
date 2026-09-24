# Session Memory — BOSS

Stage 5 is built and waiting for a look at the desktop and the dock. Stage 6, grouping, is next after that. `lib.py` is already one subject.

## Watch out for

- Add, drag, and Delete send `PUT` or `DELETE` and paint the workspace the server returns. A failure shows the error and loads the workspace again.
- `os.network.delete` returns the response body when it is not asking for confirmation. Callers that ignore the return are unchanged.
- A guest still sees the seed, and a right-click still does not open Delete.
- The first read for a signed-in user writes JSON Formatter, Tutorial, Scheduler, and Wordy, with Scheduler in the dock.
- `db.links` is how a test sees the guest rows are user id 2, and that a second read did not insert more rows.
- `check_user` refuses a caller whose id is not the id in the path, including user 1.
- A desktop icon id contains dots, so match it with `[id="..."]`.

## Open

1. Look at Stage 5. Stage 6 waits on that.
