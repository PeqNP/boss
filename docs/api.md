# BOSS API

The public BOSS API is located at `/public/boss/`. Any application may interact with OS features using:

- `os`: Provides OS-level functions such as sign in, clipboard functions, or launching a deeplink
- `os.network`: Provides API to make network calls to backend services
- `os.notification`: Forwards app/system events and notifications to the OS
- `os.ui`: Provides access to OS UI features
- `os.ui.desktop`: Provides API to interact with desktop
- `os.ui.notification`: Provides API to display notifications from the BOSS system or an app

## UI Components

The following is a list of UI components you can use in your apps.

> To see all components in action, please visit [UI Components](https://bithead.io/boss/components.html).

- `UIButton` including `default`, `primary`, and `secondary` actions
- `UICheckbox` WIP
- `UIFolder` WIP displays a file-system navigator
- `UIListBox` - Provides a flat list of options that a user may select. Supports:
  - selecting multiple options
  - selecting a single option
  - treating options like buttons
- `UILittleControls` a group of small up and down arrows
- `UIMenu` display menu options in the OS bar (e.g. `File`, `View`, `Help`)
- `UIModal` a composition of UI components. Touches are prevented outside of the modal until the modal is dismissed.
- `UIPopup` displays drop-down of selections
- TBD: `UIRadio`
- `UITabs` provides a horiztonal list of file-like tabs
- `UITextField` displays text field
- `UIWindow` is a composition of UI components
  - Optionally allows a close button
  - Optionally allows a fullscreen button
  - `ui-window container.group`: Show `UIWindow` container w/ no padding and a 1px border between components
- A comprehensive library of CSS selector for layout
  - `hbox`, `vbox`, `gap-*`, `align-*`: A horizontal and vertical box model w/ several gap and alignment options
  - `controls`: Standardized way of grouping `UIButton`s to the right
  - `UITextField` helpers include `read-only`, `text-field`, `text-area`

### OS Modals

The OS comes with several convenient UI modals including:

- `Alert` via `os.ui.showAlert(msg: str)`: Display an alert to a user
- `Delete` via `os.ui.showDelete(msg: str, cancel: function, ok: function)`: Display a modal that asks the user if they want to delete something
- `Error` via `os.ui.showError(msg: str)`: Display an error message
- `Info` via `os.ui.showInfo(msg: str)`: Display an alert to a user. This has the option of being `await`ed until dismissed.
- `ProgressBar` via `os.ui.showProgressBar(title: str, fn: function, indeterminate: bool=false)`: Display a progress bar with an optional `fn` that is called when the `Stop` button is pressed.

### OS Miscellaneous

- `Loading` via `os.ui.showBusy()`: Shows a watch until you call `os.ui.hideBusy()`. This API may change in the future.

## Notifications & Events

Notifications are (currently) temporary backend app/system information that are communicated to the end-user immediately.

Events are opaque messages sent from a backend app/system, which are designed to be consumed by a front-end app, or BOSS system, to perform a state change in the app.

For example, Wordy sends an event, and notification, when one of your friends makes a guess on a puzzle. The notification lets you know a friend has made a move. The event is used to update the UI within the Wordy app.

The (App structure)[/docs/app-structure.md] shows how to register your controller to recieve events.

### Sending Notifictaions & Events

To send a notification, or event, from your backend app do the following

```python
from lib.server import get_friends, send_events

@router.post("/flip-switch")
@require_user()
async def _guess(boss_user: User, request: Request):
    """ Contrived example showing how to send an event and
    notification. """
    # Query for a list of friends to send message to
    user, friends = await get_friends(request)
    friend_ids = [f.userId for f in friends]
    # Create the event you want to send
    event = {
        "user": user.model_dump_json(),
        "flip_switch": True
    }
    # Send event that the front-end app will consume to update its state.
    #
    # NOTE: The request is required to send messages to Swift notification
    # system, as it contains the session cookie for this user.
    send_events(request, "io.bithead.my-app.switch", data=event, user_ids=friend_ids)
    # Send a notification. This is displayed to every user, so long as
    # they are signed in and BOSS is loaded.
    send_notifications(request, user_ids=friend_ids, title="Switch state", body="The switch was flipped")
```
