# Code Generation Guidelines

Refer to the [Tutorial application](/public/boss/app/io.bithead.tutorial), specifically the [Example controller](/public/boss/app/io.bithead.tutorial/controller/Example.html) to understand how to generate a window, register for OS events/callbacks, and BOSS UI components (buttons, control groups, list boxes, et al).

When generating code that interacts with UI or API functions (e.g., in `ui.js`, `os.js`, `foundation.js`, backend libraries, etc.), always read the relevant function comments to ensure accurate usage of parameters, return types, and behaviors. Add a comment, where a behavior should be, over assumptions if there's ambiguity as to which OS function to use.

When generating forms or windows with user actions (e.g., Save, Cancel, OK), include corresponding buttons in a `<div class='controls'>` container at the bottom of the form body. Use `default` class for main actions (e.g., Save, Submit), `primary` for neutral/secondary actions (e.g., Cancel, Close), and `secondary` for less common options. Also, add these actions as options in the window's 'File' menu for keyboard accessibility. Buttons are orderd from left to right where `secondary` comes first, then `primary`, then `default`. There may only be one `default` action.

When implementing private API endpoints that require user authentication, always apply the decorator as `@require_user()` (with parentheses), and include `boss_user: User` as a parameter after any endpoint-specific parameters (e.g., body models or path/query params) but before `request: Request`. Ensure `from lib.model import User` is imported if not already present.

When defining controller methods that are invoked from HTML event handlers (e.g., onclick), the public property name assigned to `this` must exactly match the function name used in the HTML. For instance, if HTML calls `$(this.controller).closeWindow()`, define the function as `function closeWindow() { ... }` and assign it as `this.closeWindow = closeWindow;`. Avoid mismatched names like `this.close = closeWindow;`.

When determining if a value is an empty array, empty string, `null`, `undefined`, etc. use the `foundation.js` function `isEmpty()` to test for "emptiness." Do not compare values like `myVar === null`, etc.

Controllers (windows or modals) should not set `didHitCancel` as the default action to "Cancel" or "Close" the controller.

When passing configuration to a controller, that is about to be shown
- Pass in individual configuration variables.
- Only pass in an `Object` if there are three or more parameters used to configure the controller.
  - If an `Object` is created, the structure should be documented in the comments of the `configure` method.
- Regardless of how parameters are passed, always add comments to the `configure` method using jsdoc.
- Because the name of variables will most likely conflict with internal variables, prepend parameters passed to the `configure` method with an underscore. e.g. `_intakeQueueId`.
- When adding new configuration IDs, to the controller, the ID variables should be placed near the top of the main function.

When returning a response from the server, back to the client, and the response is empty, return the `Fragment.OK` response.

When a `UIListBox` may have its data dynamically generated, such as loading factories in `viewDidLoad`, the initialization of the `select`'s `delegate` must be done before loading the respective data. This ensures the delegate callback for the first selected option is called after the data is loaded.
