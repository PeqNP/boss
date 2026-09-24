# Session Memory — BOSS

Stage 7 is done. The screen and the server share `AppLink` and `Workspace`. Stage 8, the UI tests, is next. Write `ui-plan.md` first.

## Watch out for

- A workspace response is copied into `AppLink` by `adoptWorkspace`. The fields are `bundleId`, `name`, and `icon`. `desktop` and `dock` are the lists.
- `SystemFont` and `SystemFonts` live in `model.py`. `fonts.py` still holds Chicago and Geneva. The font picker reads `catalog.fonts`.
- `LinkRow` stays in `db.py`. It is `user_id`, `surface`, `position`, and `bundle_id`. That is the stored row, not the link the screen paints.
- Add, drag, and Delete send `PUT` or `DELETE` and paint the workspace the server returns.
- A guest sees the seed. A right-click does not open Delete.
- `db.links` is how a test sees the guest rows are user id 2, and that a second read did not insert more rows.
- A desktop icon id contains dots, so match it with `[id="..."]`.

## Open

1. Look at Stage 7. Stage 8 waits on that.
