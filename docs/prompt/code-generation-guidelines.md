# Code Generation Guidelines

Refer to [Example.html](/public/boss/Example.html) to understand how to generate a window, register for OS events / callbacks, and all the possible elements that can be used.

When generating code that interacts with UI or API functions (e.g., in ui.js, os.js, or backend libraries), always read the relevant function comments and implementation details from the codebase to ensure accurate usage of parameters, return types, and behaviors. Prioritize comments over assumptions if there's ambiguity.

When generating forms or windows with user actions (e.g., Save, Cancel, OK), include corresponding buttons in a `<div class='controls'>` container at the bottom of the form body. Use `default` class for main actions (e.g., Save, Submit), `primary` for neutral/secondary actions (e.g., Cancel, Close), and `secondary` for less common options. Also, add these actions as options in the window's 'File' menu for keyboard accessibility. Buttons are orderd from left to right where `secondary` comes first, then `primary`, then `default`. There may only be one `default` action.

When implementing private API endpoints that require user authentication, always apply the decorator as `@require_user()` (with parentheses), and include `boss_user: User` as a parameter after any endpoint-specific parameters (e.g., body models or path/query params) but before `request: Request`. Ensure `from lib.model import User` is imported if not already present.

When defining controller methods that are invoked from HTML event handlers (e.g., onclick), the public property name assigned to `this` must exactly match the function name used in the HTML. For instance, if HTML calls `$(this.controller).closeWindow()`, define the function as `function closeWindow() { ... }` and assign it as `this.closeWindow = closeWindow;`. Avoid mismatched names like `this.close = closeWindow;`.
