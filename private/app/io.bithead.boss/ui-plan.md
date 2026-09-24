# BOSS workspace — UI test coverage

`plan.md` is the implementation contract: what the desktop and the dock do, and what each route answers. This is the coverage contract: which flows are tested, in what order, and what each one has to prove.

They are separate because UI testing is long and interruptible. The table below is what lets it stop and resume — it says what is done, so nobody has to remember a conversation.

## What a flow is for

A UI test proves the **wiring**: that the desktop, the dock, and Applications call the right endpoint and paint the answer. Who may save, what a bad bundle id is refused with, and the guest seed itself are settled by the private suite. Asserting those again through a browser buys nothing.

So each flow below earns its place by catching what the private suite is blind to: a menu wired to nothing, a save that never leaves the browser, a reload that paints the wrong list.

Keep to happy paths. No assertion about pixels, widths, or colours.

## Order

The guest is first, because later flows sign in and the guest list is what sign-out has to return to. A new account is next, because add, delete, and drag start from that list. Sign-out is last, because it has to find a saved order still there.

## Flows

| # | Flow | Spec | Must prove | Status |
|---|---|---|---|---|
| 1 | Guest workspace | `boss-workspace-guest.spec.js` | A guest sees JSON Formatter, Tutorial, Lean Visualizer, and Wordy on the desktop, and no dock icons. Add to Desktop and Add to Dock are disabled. Right-click on a desktop icon does not open Delete | **Done** |
| 2 | A new account | `boss-workspace-first-load.spec.js` | The first load shows JSON Formatter, Tutorial, Scheduler, and Wordy on the desktop, and Scheduler in the dock | **Done** |
| 3 | Add an app | `boss-workspace-add.spec.js` | Add to Desktop puts Music on the desktop and then disables. Add to Dock puts Lean Visualizer in the dock and then disables | **Done** |
| 4 | Delete from the desktop | `boss-workspace-desktop-delete.spec.js` | Right-click Music and choose Delete. The request is `DELETE /workspace/desktop/{userId}/io.bithead.music`. The icon leaves. Reload. It is still gone, and Scheduler is still in the dock | **Done** |
| 5 | Delete from the dock | `boss-workspace-dock-delete.spec.js` | Right-click Lean Visualizer in the dock and choose Delete. The request is `DELETE /workspace/dock/{userId}/io.bithead.lean-visualizer`. The icon leaves. Reload. It is still gone, and Music is not on the desktop | **Done** |
| 6 | Desktop order | `boss-workspace-desktop-order.spec.js` | Dragging a desktop icon sends `PUT /workspace/{userId}`. Reload shows that order | **Done** |
| 7 | Dock order | `boss-workspace-dock-order.spec.js` | Dragging a dock icon sends `PUT /workspace/{userId}`. Reload shows that order | **Done** |
| 8 | Sign out and back | `boss-workspace-return.spec.js` | Sign out shows the guest desktop. Sign in again shows the order that was saved | **Done** |

## Findings

Defects and blockers UI testing turns up, so a later session can tell a gap in coverage from a gap in the app.

| Flow | Finding | Fixed |
|---|---|---|
| — | The full suite's `settings acl › show roles` expects one Employee row and finds two. The eight workspace specs passed in that same run. None of them grants a role | No |

## What every flow has to do

**Reset only this app's database.** `GET /api/debug/uitests/reset?bundle=io.bithead.boss` empties `workspace.sqlite3` and recreates the guest seed. It does not touch other apps, and it does not delete the BOSS account.

**Sign in before the page loads** for every flow except the guest. `workspace@bithead.io` is created from an admin session, then signed in. The first `GET` after a reset writes that account's starting list.

**Seed a list through `PUT /workspace/{userId}`** when the flow is about delete, drag, or coming back. Add is the exception: the buttons are what that flow proves.

**Wait until a desktop icon is on screen, then read it.** `os.isLoaded()` is true before `loadWorkspace` has painted. An id contains dots, so the locator is `[id="desktop-icon-…"]`.
