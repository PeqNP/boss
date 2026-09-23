# BOSS workspace

The desktop and the dock are lists of installed apps, kept in order in a database named workspace. A guest has one. A signed-in user has their own.

## Who

| Actor | What they do |
|---|---|
| Guest | Sees the guest workspace: JSON Formatter, Tutorial, Lean Visualizer, and Wordy. Nothing they do is saved. |
| Signed-in user | Starts from their own list, adds apps to the desktop or the dock, deletes an icon from either, and reorders either list. |

## What happens

Opening BOSS loads a workspace.

A guest sees JSON Formatter, Tutorial, Lean Visualizer, and Wordy on the desktop. The dock is empty. That workspace is the guest's, and it is the same for every guest.

A signed-in user, the first time, sees JSON Formatter, Tutorial, Scheduler, and Wordy on the desktop, and Scheduler in the dock. After that, their copy is what loads.

They open Applications from the OS menu. Add to Desktop and Add to Dock sit together at the top right of the list. Choosing one places the selected app on that surface. They drag an icon to reorder the desktop or the dock. They right-click a desktop icon or a dock icon, choose Delete, and that call removes the icon from that surface. An app can sit on both. Installing an app does not place an icon. The dock stays on screen when it has no icons.

## Out of scope

- Files, folders, open windows, and a position for each icon on the grid.
- A setting that hides the dock.
- Editing the guest workspace, or a super admin editing someone else's.
- Placing an icon because an app was installed.
- Defaults, fonts, heartbeat, and the account windows. Those stay as they are.
