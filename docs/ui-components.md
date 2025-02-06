# UI Components

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
- `UIRadio` WIP
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

## OS Modals

The OS comes with several convenient modal types.

- `Alert` via `os.ui.showAlert(msg: str)`: Display an alert to a user
- `Delete` via `os.ui.showDelete(msg: str, cancel: function, ok: function)`: Display a modal that asks the user if they want to delete something
- `Error` via `os.ui.showError(msg: str)`: Display an error message
- `Info` via `os.ui.showInfo(msg: str)`: Display an alert to a user. This has the option of being `await`ed until dismissed.
- `ProgressBar` via `os.ui.showProgressBar(title: str, fn: function, indeterminate: bool=false)`: Display a progress bar with an optional `fn` that is called when the `Stop` button is pressed.

## OS Miscellaneous

- `Loading` via `os.ui.showBusy()`: Shows a watch until you call `os.ui.hideBusy()`. This API may change in the future.
