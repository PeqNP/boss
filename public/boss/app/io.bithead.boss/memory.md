# Session Memory — BOSS

Stage 8 is done. Every flow in `ui-plan.md` has a spec, and the eight specs passed. The workspace plan has no further stage.

## Watch out for

- A UI spec resets only `io.bithead.boss` and signs in as `workspace@bithead.io`. The account survives. The workspace database does not.
- `os.isLoaded()` is true before the desktop is painted. Wait for `.desktop-icon`.
- An icon id contains dots. Match it with `[id="desktop-icon-…"]`.
- Applications covers the desktop icons. Close it before a right-click.
- Sign out shows the guest list immediately. Wait for the saved first icon after Sign in, not for any desktop icon.
- A workspace response is copied into `AppLink`. The fields are `bundleId`, `name`, and `icon`.
- `db.links` is how a private test sees the guest rows are user id 2.

## Open

1. None. The eight stages are done.
