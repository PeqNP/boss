# BOSS workspace — Implementation Plan

## Identity

- **Bundle ID:** `io.bithead.boss`
- **App name:** BOSS
- **Public app dir:** `public/boss/app/io.bithead.boss/`
- **Private service dir:** `private/app/io.bithead.boss/`
- **Test file:** `private/tests/test_boss.py`
- **Backend:** Python (FastAPI, SQLite). Database file: `<db_path>/workspace.sqlite3`. The database is named workspace. Defaults stay in `boss.dbm`.
- **What this plan covers:** the desktop and the dock. Fonts, heartbeat, defaults, and the account controllers stay as they are.
- **Client surfaces:** `UIContextMenu` in `public/boss/ui.js`, `public/boss/os.js`, `public/boss/ui-desktop.js`, the dock in `public/boss/ui.js`, and `public/boss/app/io.bithead.applications/controller/Applications.html`. No new controller is registered on `io.bithead.boss`.

Plan confirmed. Stage 3 is in review. Stage 4 is next. Stop after each stage.

## Roles & Access

The scope of a signed-in user is their own id, named in the path. `check_user` refuses a caller whose id is not that path id. User 1 is included in that refusal.

The guest is user id 2, the same id as `Global.guestUserId` in `server/bosslib` and `GUEST_USER_ID` in `os.js`. Their workspace is that user's rows. The client loads it with `GET /workspace/guest` and has no session on that route. The user routes refuse user id 2, so a guest session cannot rewrite the shared list.

| Actor | Told by | Scope | Reaches | Narrowed by |
|---|---|---|---|---|
| Signed-in user | `boss_user.id` on the session | their id, named in the path | their desktop list and their dock list | their own record |
| Guest | no session. The client's user id is 2 | the guest workspace, user id 2 | that desktop list | read only |

The boss service has no `Role` enum. The signed-in routes use `@require_user()` and `check_user`, the same guard the defaults routes use. They declare no ACL feature. The guest route declares none either.

### Who reaches each surface

There is no new window. These three surfaces are the slice.

| Surface | Audience | What opens it |
|---|---|---|
| Desktop | Guest, signed-in user | `loadWorkspace` when the OS starts, and again on sign-in and sign-out |
| Dock | Guest, signed-in user | the same load |
| Applications | Guest, signed-in user | OS menu → Applications |

A guest can open an icon. Add, Delete, and reorder are enabled for a signed-in user.

### Documents

None of these surfaces is a document. Each change commits as it happens, so a document Save would have nothing left to confirm.

| Surface | Kind | Controls beyond a plain close |
|---|---|---|
| Desktop | The OS desktop. Drag commits the new order. Right-click commits a delete. | Delete, on a `UIContextMenu` |
| Dock | The OS dock. Drag commits the new order. Right-click commits a delete. | Delete, on a `UIContextMenu` |
| Applications | A list of installed apps. The top group commits one app onto a surface. | Open, Add to Desktop, Add to Dock |

### Drafts

No surface creates a row on open. The guest rows are the schema seed. The first `GET` for any other user writes that user's starting list. That list is their workspace, not a draft.

## Stage 1 — UI/UX

Existing `GET` calls stay live. Add, reorder, and both deletes are backend calls. Stage 1 writes the client of each call. Until the route exists, that function edits the workspace in memory and does not touch the network, so the menu can be reviewed. Stage 5 replaces the body with the request below. The icon stays gone because the server removed the row.

| Action | Call Stage 5 sends |
|---|---|
| Add, or a drag | `PUT /api/io.bithead.boss/workspace/{userId}` |
| Delete on a desktop icon | `DELETE /api/io.bithead.boss/workspace/desktop/{userId}/{bundleId}` |
| Delete on a dock icon | `DELETE /api/io.bithead.boss/workspace/dock/{userId}/{bundleId}` |

`os` keeps the last `Workspace` it loaded and exposes it as `os.workspace()`. `loadWorkspace` stores the response before painting. Add and reorder change that object, repaint the surface that changed, then call `saveWorkspace`.

### UIContextMenu

`UIContextMenu` is a new component in `public/boss/ui.js`, beside `UIPopupMenu`. A right-click opens it. A desktop icon, a dock icon, and a table row are the same kind of caller: each hands it the items for that right-click. This plan wires the two icons. It does not wire a table.

The open list matches `UIPopupMenu`. The component builds a `div.ui-popup-choices` of `div.ui-popup-choice` rows, inside a `div.sub-container`, on a `div.ui-menu-container.ui-popup-active`. The frame, the white row, and the black hover are the rules already in `styles.css`. A caller does not build those nodes.

```javascript
function UIContextMenu(items) { }

// items: [{ name: "Delete", action: function() { } }]
menu.show(event);
```

`show` prevents the browser menu, closes any menu already open, and places the menu's top-left corner at the pointer. `closeAllMenus` closes a context menu too. If the menu would sit outside the viewport, `show` shifts it back inside. The node is appended to `#desktop` at `os.ui.POPOVER_ZINDEX`, above a window, so a row inside a window still draws the menu on top of that window. One context menu is open at a time.

Choosing an item closes the menu, then runs that item's `action`. A click anywhere else closes it and runs nothing. `close` removes the node.

Stage 1 ends with `bin/boss-api`, so `docs/prompt/js-api.md` lists `UIContextMenu`.

### Desktop

Audience: guest and signed-in user. File: `public/boss/ui-desktop.js`.

The icons are already painted from `workspace.desktop`, in array order, and a drag already moves an icon in the DOM. On drop, a signed-in user's new DOM order is written back onto `workspace.desktop` and `saveWorkspace` runs. A guest's icons do not drag.

Right-click on a signed-in user's icon opens a `UIContextMenu` at the pointer. A guest's right-click does not open one. The only item is Delete. Its action calls `os.deleteDesktopApp(bundleId)`, the client of `DELETE /workspace/desktop/{userId}/{bundleId}`. Stage 1 removes the icon in memory. Stage 5 sends the request and paints the workspace it returns.

### Dock

Audience: guest and signed-in user. File: `public/boss/ui.js`, the dock helpers.

The dock gains the same drag the desktop has: drop rewrites `workspace.dock` from the DOM order and saves. A guest's dock icons do not drag. The dock stays visible when the list is empty, including after the last icon is deleted. `loadWorkspace` keeps calling `showDock` after `addAppsToDock`.

Right-click on a signed-in user's dock icon opens a `UIContextMenu` the same way. A guest's right-click does not open one. The only item is Delete. Its action calls `os.deleteDockApp(bundleId)`, the client of `DELETE /workspace/dock/{userId}/{bundleId}`. Stage 1 removes the icon in memory. Stage 5 sends the request and paints the workspace it returns. Deleting the desktop copy of an app leaves the dock copy where it is, and the reverse.

### Applications

Audience: guest and signed-in user. File: `public/boss/app/io.bithead.applications/controller/Applications.html`.

The window is the list-model layout in `js.md`: the list on the left, `controls-right separated` on the right. The top group does not wait at the bottom of the column. It is the two adds, together:

```html
<div class="controls-right separated">
  <div class="vbox gap-10">
    <button name="add-desktop" class="primary" disabled onclick="$(this.controller).addToDesktop();">Add to Desktop</button>
    <button name="add-dock" class="primary" disabled onclick="$(this.controller).addToDock();">Add to Dock</button>
  </div>
  <div class="vbox gap-10">
    <button name="open" class="default" disabled onclick="$(this.controller).open();">Open</button>
  </div>
</div>
```

Open stays the default button and `didHitEnter`. The window widens enough for the two labels. The list keeps the size it has. `controls-right thin` is replaced by this group.

`didSelectListBoxOption` and `didDeselectListBoxOption` set the buttons from the selection and `os.workspace()`:

- No selection: all three disabled.
- A guest, with a selection: Open enabled. Both adds stay disabled.
- A signed-in user: Open enabled. Add to Desktop is disabled when that bundle is already on the desktop, and enabled when it is not. Add to Dock follows the dock the same way.

`UIListBox` selects the first row on its own, so `viewDidLoad` sets the buttons once after `addNewOptions`.

Add appends an `AppLink` built from the catalog entry (`bundleId`, `name`, `icon`), repaints that surface, and calls `saveWorkspace`.

`ApplicationManager` gains `installedApplication(bundleId)`, returning `{name, icon, system}` from the registered catalog, or `null`. The buttons use it. System apps are already absent from `installedApplications()`.

### Endpoints

```
PUT /api/io.bithead.boss/workspace/{userId} -> Workspace
    body:  Workspace
    acl:   none
    who:   Signed-in user
    scope: check_user(userId, boss_user)

DELETE /api/io.bithead.boss/workspace/desktop/{userId}/{bundleId} -> Workspace
    acl:   none
    who:   Signed-in user
    scope: check_user(userId, boss_user)

DELETE /api/io.bithead.boss/workspace/dock/{userId}/{bundleId} -> Workspace
    acl:   none
    who:   Signed-in user
    scope: check_user(userId, boss_user)
```

`AppLink` is `{bundleId, name, icon}`. `Workspace` is `{desktop: AppLink[], dock: AppLink[]}`. A `PUT` sends both arrays, in order. A save that changes the desktop still sends the dock, and the reverse. Each `DELETE` removes one icon from that surface and returns the workspace that remains, with the other surface intact.

Stage 1's functions ignore `userId` and edit the in-memory workspace. They are the same functions Stage 5 points at the network. On a guest, `saveWorkspace` returns without doing anything, and neither Delete menu opens.

## Stage 2 — Data Model

One table. A row is one icon on one surface. The array order is `position`, starting at 0. Name and icon are not stored. A read fills them from `installed.json`, so a renamed app shows its current name.

The catalog file is `<boss_path>/public/boss/app/installed.json`.

```sql
CREATE TABLE versions (
    version TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

-- One icon on one surface, for one BOSS user.
-- The account itself lives in the other service. user_id is that id.
-- User id 2 is the guest.
CREATE TABLE link (
    user_id   INTEGER NOT NULL,
    surface   TEXT NOT NULL CHECK (surface IN ('desktop', 'dock')),
    position  INTEGER NOT NULL, -- 0-based order within the surface
    bundle_id TEXT NOT NULL,
    PRIMARY KEY (user_id, surface, bundle_id),
    UNIQUE (user_id, surface, position)
);

-- bundle_id is a trailing primary-key column that names another record.
CREATE INDEX idx_link_bundle_id ON link (bundle_id);
```

`create_schema` seeds the guest workspace, user id 2, and nothing else. The dock has no guest rows. `boss.dbm` has no `desktop/{user_id}` keys, and nothing writes them. `GET` stops reading the dbm.

| position | bundle id | name | icon |
|---|---|---|---|
| 0 | `io.bithead.json-formatter` | JSON Formatter | `icon.svg` |
| 1 | `io.bithead.tutorial` | Tutorial | `icon.svg` |
| 2 | `io.bithead.lean-visualizer` | Lean Visualizer | `icon.svg` |
| 3 | `io.bithead.wordy` | Wordy | `icon.svg` |

A signed-in user's first read inserts `USER_WORKSPACE`. It is not a seed. Every new account starts from it, and it is a different list from the guest's.

| Surface | bundle id | name | icon |
|---|---|---|---|
| desktop | `io.bithead.json-formatter` | JSON Formatter | `icon.svg` |
| desktop | `io.bithead.tutorial` | Tutorial | `icon.svg` |
| desktop | `io.bithead.scheduler` | Scheduler | `icon.svg` |
| desktop | `io.bithead.wordy` | Wordy | `icon.svg` |
| dock | `io.bithead.scheduler` | Scheduler | `icon.svg` |

### Network models

`AppLink` and `Workspace` already exist on the routes. They move to `model.py`. `Default` and `ServerInfo` stay in `__init__.py`.

```python
class AppLink(BaseModel):
    bundleId: str
    name: str
    icon: str

class Workspace(BaseModel):
    desktop: List[AppLink]
    dock: List[AppLink]
```

`GET`, `PUT`, and `DELETE` return `Workspace`. The names and icons in that body are the catalog's.

## Stage 3 — TDD

Tests live in `private/tests/test_boss.py` and call `lib`. The file already holds `test_system_fonts`; that stays. Point the database at `test-workspace.sqlite3` and recreate it for each test function.

`test_guest_workspace`

- describe: the guest workspace
- it: returns JSON Formatter, Tutorial, Lean Visualizer, and Wordy on the desktop, in that order
- it: returns an empty dock
- it: the rows are user id 2
- it: a second read returns those same rows

`test_first_workspace`

- describe: a signed-in user with no rows
- it: returns JSON Formatter, Tutorial, Scheduler, and Wordy on the desktop, and Scheduler in the dock
- it: the second read returns that list without inserting it again
- it: user id 2 is refused

`test_two_users`

- describe: two signed-in users
- it: saving one user's desktop leaves the other's list as they saved it
- it: leaves the guest rows as they were

`test_save_workspace`

- describe: a full replacement
- it: the desktop and the dock come back in the order they were sent
- it: a desktop-only change, sent with the current dock, keeps the dock
- it: an empty dock is saved and comes back empty
- it: an empty desktop is saved and comes back empty
- it: Wordy on the desktop and in the dock is saved as both
- it: a client name of "Nope" for Wordy comes back as "Wordy", with `icon.svg`
- it: user id 2 is refused, and the guest rows stay

`test_remove_desktop`

- describe: Delete on a desktop icon
- it: removes that bundle from the desktop and leaves the dock
- it: the remaining desktop icons keep their order, with positions closed up
- it: a bundle that is not on the desktop leaves the workspace as it was
- it: removing Scheduler from the desktop leaves Scheduler in the dock
- it: user id 2 is refused, and the guest desktop stays

`test_remove_dock`

- describe: Delete on a dock icon
- it: removes that bundle from the dock and leaves the desktop
- it: the remaining dock icons keep their order, with positions closed up
- it: a bundle that is not on the dock leaves the workspace as it was
- it: removing Scheduler from the dock leaves Scheduler on the desktop
- it: deleting the last dock icon returns an empty dock
- it: user id 2 is refused, and the guest rows stay

`test_save_rejects`

- describe: a list the catalog will not hold
- it: a bundle id that is not installed is rejected, and the stored list is unchanged
- it: `io.bithead.settings` is rejected
- it: the same bundle twice on the desktop is rejected
- it: a blank bundle id is rejected

## Stage 4 — Backend Implementation

```
private/app/io.bithead.boss/
  __init__.py   routes. Workspace routes call lib. Defaults, heartbeat, and fonts stay.
  fonts.py      unchanged
  model.py      AppLink, Workspace
  lib.py        guest_workspace, get_workspace, save_workspace, remove_desktop, remove_dock
  db.py         schema, the guest seed, SQL, get_db_path, delete_database, start_database
```

`db.py` exposes `create_schema(conn)` and `get_db_path()` so `bin/check-db` sees the file. `__init__.py` does `from . import db` and grows a `start()` that calls `db.start_database()`. `set_database_name` points tests at `test-workspace.sqlite3`.

```python
GUEST_USER_ID = 2

def guest_workspace() -> Workspace: ...

def get_workspace(user_id: int) -> Workspace: ...

def save_workspace(user_id: int, workspace: Workspace) -> Workspace: ...

def remove_desktop(user_id: int, bundle_id: str) -> Workspace: ...

def remove_dock(user_id: int, bundle_id: str) -> Workspace: ...
```

`guest_workspace` reads user id 2 and fills names from the catalog. `get_workspace` refuses user id 2, and for anyone else inserts `USER_WORKSPACE` when that user has no rows. `save_workspace` refuses user id 2, checks the catalog, then replaces both surfaces in one transaction. `remove_desktop` and `remove_dock` each refuse user id 2, delete that one row on that surface, and renumber the positions that remain. The other surface is left as it was. A bundle that is not on the surface returns the workspace unchanged. A failed check raises `ValidationError` and leaves the rows as they were. The route maps that to HTTP 400 with the message.

Catalog rules, applied to each list on a save:

- `bundleId` is present in `installed.json` and `system` is not true
- `icon` in the catalog is a non-empty string
- a bundle id appears once in that list

The same bundle on the desktop and the dock is allowed. A new account ships Scheduler that way.

Routes:

```
GET /workspace/guest -> Workspace
    who:   anyone
    scope: the guest workspace
    calls: guest_workspace()

GET /workspace/{user_id} -> Workspace
    who:   Signed-in user
    scope: check_user(user_id, boss_user)
    calls: get_workspace(user_id)

PUT /workspace/{user_id} -> Workspace
    body:  Workspace
    who:   Signed-in user
    scope: check_user(user_id, boss_user)
    calls: save_workspace(user_id, body)

DELETE /workspace/desktop/{user_id}/{bundle_id} -> Workspace
    who:   Signed-in user
    scope: check_user(user_id, boss_user)
    calls: remove_desktop(user_id, bundle_id)

DELETE /workspace/dock/{user_id}/{bundle_id} -> Workspace
    who:   Signed-in user
    scope: check_user(user_id, boss_user)
    calls: remove_dock(user_id, bundle_id)
```

The handlers are named `get_guest_workspace`, `get_workspace`, `save_workspace`, `remove_desktop`, and `remove_dock`. The module currently defines `get_default` three times; the two workspace reads take their own names.

These two routes are removed. Both are `GET`, and neither checks the caller. The client has never called them.

- `GET /workspace/desktop/{user_id}/{bundle_id}`
- `GET /workspace/dock/{user_id}/{bundle_id}`

Both `DELETE` routes stay. Each gains `@require_user()` and `check_user`. The desktop Delete menu calls the desktop route. The dock Delete menu calls the dock route.

## Stage 5 — Integration

Stage 1 left these three stubbed. Replace the three function bodies with the requests. Each stores the response on `os.workspace()` and repaints from it, so the painted names are the catalog's. On failure the call shows `os.ui.showError` and runs `loadWorkspace`, which puts the icon back.

| Call | Replaces |
|---|---|
| `PUT /api/io.bithead.boss/workspace/{userId}` | `saveWorkspace`, used by Add and by drag |
| `DELETE /api/io.bithead.boss/workspace/desktop/{userId}/{bundleId}` | `deleteDesktopApp`, used by the desktop Delete menu |
| `DELETE /api/io.bithead.boss/workspace/dock/{userId}/{bundleId}` | `deleteDockApp`, used by the dock Delete menu |

`GET /workspace/guest` and `GET /workspace/{userId}` are already live. Their bodies start reading the database in this stage. A signed-in user's first load writes `USER_WORKSPACE`. The guest load reads the seed.

## Stage 6 — Grouping

`lib.py` for this slice is one subject, the workspace. It stays one module. Fonts stay in `fonts.py`. Defaults and heartbeat stay in `__init__.py`.

| Module | Layer | What it holds |
|---|---|---|
| `model.py` | network | `AppLink`, `Workspace` |
| `db.py` | storage | `link`, the guest seed. The catalog read is not SQL |
| `lib.py` | rules | the guest read, the first-read insert, the replacement, the desktop delete, the dock delete |

## Stage 7 — Reconcile

One shape. The client and the routes already speak it.

| Models | Fields | Suggested name | Replace |
|---|---|---|---|
| The `Workspace` painted by `loadWorkspace`, the `PUT` body, and every workspace response | `desktop`, `dock`, each an `AppLink` of `bundleId`, `name`, `icon` | `Workspace` | One model. Stage 1's in-memory object is that shape, and Stage 5 stores the response over it. |

## Stage 8 — UI tests

Write `private/app/io.bithead.boss/ui-plan.md` first. One spec, `uitest/tests/boss-workspace.spec.js`, with these flows in this order:

1. A guest sees JSON Formatter, Tutorial, Lean Visualizer, and Wordy on the desktop, and an empty dock. Add to Desktop and Add to Dock are disabled. Right-click on a desktop icon or a dock icon does not open Delete.
2. A new signed-in user sees JSON Formatter, Tutorial, Scheduler, and Wordy on the desktop, and Scheduler in the dock.
3. Add Music to the desktop and Lean Visualizer to the dock. Both paint. Add to Desktop is disabled for Music, and Add to Dock is disabled for Lean Visualizer.
4. Right-click Music and choose Delete. The request is `DELETE /workspace/desktop/{userId}/io.bithead.music`. The icon leaves. Reload. It is still gone, and Scheduler is still in the dock.
5. Right-click Lean Visualizer in the dock and choose Delete. The request is `DELETE /workspace/dock/{userId}/io.bithead.lean-visualizer`. The icon leaves. Reload. It is still gone, and Music is still off the desktop.
6. Drag the desktop into another order. Reload. The order remains.
7. Drag the dock into another order. Reload. The order remains.
8. Sign out to the guest. The guest desktop is back. Sign in again. The saved order is back.
