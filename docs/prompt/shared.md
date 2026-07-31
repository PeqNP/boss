# BOSS Shared Reference

Cross-cutting conventions used by all BOSS subsystems.

---

## 1. What is BOSS

BOSS (Bithead OS) is a web OS that makes web apps look and behave like classic 2-bit Mac OS (System 7 era) native applications. UI patterns are inspired by Apple's Macintosh Human Interface Guidelines (1992 edition) and iOS UIKit (delegation, view lifecycle events).

**Design principles to follow:**
- Direct manipulation, desktop metaphor
- Consistent menu commands (File, Edit, View, Help)
- Modal dialogs only when necessary
- Forgiving actions with undo where possible
- Standard controls: radio buttons, checkboxes, scroll arrows, list boxes, pop-up menus
- Black-and-white / 1-bit aesthetic — no Aqua/flat/modern elements

---

## 2. Project Layout

```
/docs/                  Human-readable documentation
/docs/prompt/           AI agent guidance documents (this directory)
/public/                Client-side assets served by the web server
  /public/boss/         BOSS OS JavaScript and CSS
    /public/boss/app/   All BOSS application bundles live here
      installed.json    Registry of all installed apps
  /public/upload/       Per-app user-uploaded content
/private/               Python private web services (per-app)
/server/web/            Swift+Vapor primary web server
/server/bosslib/        Shared Swift library used by the web server
/test/                  Selenium UI test framework
```

**Key OS JavaScript files** (read JSDoc comments before using any function):

| File | Purpose |
|---|---|
| `/public/boss/foundation.js` | Utility functions: `isEmpty()`, `Result`, `coalesce()`, etc. |
| `/public/boss/os.js` | OS-level APIs: sign-in, deep links, clipboard |
| `/public/boss/ui.js` | UI system: `UIWindow`, `UIApplication`, all UI component classes |
| `/public/boss/network.js` | Network calls: `get`, `post`, `put`, `patch`, `json` (deprecated), `upload`, `_delete` |
| `/public/boss/notification-manager.js` | Event/notification dispatch |
| `/public/boss/application-manager.js` | Application lifecycle management |
| `/public/boss/ui-desktop.js` | Desktop icon management |
| `/public/boss/ui-notification.js` | In-OS notification display |

---

## 3. App Bundle Structure

All BOSS app bundles live under `/public/boss/app/<bundle_id>/`.

```
/public/boss/app/io.bithead.my-app/
  application.json      Required. App config and controller registry.
  description.md        Required. Contains high-level description of application and motivation for the app.
  icon.svg              App icon (SVG required).
  controller/           Folder containing all UIController HTML files.
    Home.html
    Settings.html
  image/                Optional. Images referenced in controllers.
  memory.md             Optional. AI agent context for this app (see §16).
```

Every new app must also be registered in `/public/boss/app/installed.json`:
```json
{
  "io.bithead.my-app": { "name": "My App", "icon": "icon.svg" }
}
```

Reference controllers for patterns:
- **All UI components**: `/public/boss/app/io.bithead.tutorial/controller/Example.html`
- **Application controller**: `/public/boss/app/io.bithead.tutorial/controller/Application.html`

---

## 4. application.json

Minimum required fields:

```json
{
  "boss": { "version": "1.0.0" },
  "application": {
    "bundleId": "io.bithead.my-app",
    "name": "My App",
    "version": "1.0.0",
    "icon": "icon.svg",
    "main": "Home",
    "author": "Your Name",
    "copyright": "2026 Bithead LLC. All rights reserved."
  },
  "controllers": {
    "Home": {},
    "Settings": { "modal": true },
    "Detail": { "singleton": true }
  }
}
```

**Key `application` properties:**

| Property | Default | Description |
|---|---|---|
| `main` | required | Controller name to load on launch, or `"Application"` to use `Application.html` with menus |
| `system` | `false` | System apps are hidden from users; they work in all contexts |
| `secure` | `false` | Close app on user sign-out |
| `passive` | `false` | App does not switch context; does not receive focus/blur events |
| `quitAutomatically` | `false` | Quit when all windows are closed |
| `kiosk` | `false` | Hides OS chrome; app fills entire screen |
| `scheme` | `null` | Custom URL scheme for deep links (e.g. `"settings"`) |
| `menu` | `null` | Controller name to show when app icon is tapped in OS bar |

**Controller options:**

| Option | Description |
|---|---|
| `{}` | Standard window controller |
| `{ "modal": true }` | Modal controller (blocks interaction behind it) |
| `{ "singleton": true }` | Only one instance allowed |
| `{ "remote": true }` | Path is provided at runtime (server-rendered) |
| `{ "module": true }` | View and controller are split: the HTML holds no `<script>`, and the controller lives in a sibling `<Name>.js` ES module. See "Module controllers" in [`js.md`](js.md). |

> **Every new controller file MUST be registered in `application.json` under `"controllers"`.**

---

## 16. Coding Rules and Conventions

### No single-line `if` statements

Always expand `if` statements to multiple lines, even for a single-statement body:

```javascript
// ✓ correct
if (isEmpty(id)) {
  return;
}

// ✗ wrong
if (isEmpty(id)) { return; }
```

This applies to every statement in the body — early returns, guard clauses, assignments, and function calls.

### Emptiness checks

Use `isEmpty()` from `foundation.js` for all emptiness checks:

```javascript
if (isEmpty(value)) {               // ✓ correct
  return;
}
if (value === null) { return; }     // ✗ wrong (condition and format)
if (value != null) { ... }          // ✗ wrong (condition and format)
if (!value) { return; }             // ✗ wrong (condition and format)
```

`isEmpty` is for nullable/undefined values. Use boolean values directly:

```javascript
if (initialize) { ... }              // ✓ correct
if (!initialize) { ... }             // ✓ correct
if (isEmpty(initialize)) { ... }     // ✗ wrong — booleans are never "empty"
```

This applies after `await` too — once a Promise is awaited, the result is a plain value, not a Promise, so `isEmpty` applies normally.

```javascript
let results = await delegate.didFocusSearchBar(!initialized);
if (!isEmpty(results)) {  // ✓ correct
  cachedOptions = results;
}
```

### Conditional ordering

When a conditional has an `if/else`, put the **empty / absent / error** case first. This keeps the happy path in the `else` and reduces cognitive overload from negated conditions.

```javascript
if (isEmpty(metrics)) {          // ✓ correct — empty case first
  showPlaceholder();
} else {
  renderMetrics(metrics);
}

if (!isEmpty(metrics)) {         // ✗ wrong — positive check with else forces reader to negate
  renderMetrics(metrics);
} else {
  showPlaceholder();
}
```

For guard clauses with no `else` (early returns), `!isEmpty` is fine:

```javascript
if (!isEmpty(results)) {  // ✓ correct — guard, no else
  cachedOptions = results;
}
```

### Numeric checks

Use `isNumeric()` from `foundation.js` to check whether a value is a valid finite number. It handles `null`, `undefined`, empty strings, `NaN`, and `Infinity` correctly.

```javascript
const id = parseInt(segments[0]);
if (!isNumeric(id)) {    // ✓ correct
  return;
}

if (isNaN(id)) {         // ✗ wrong — use isNumeric instead
  return;
}
```

### Server responses vs. local model classes

When a server response already matches the shape needed by the UI or controller (e.g. `{ id, url }`), use the response object directly.

Introduce a client-side model class when it adds behavior, validation, computed properties, or methods that the plain response object does not provide.

### Early returns over nesting

```javascript
// ✓ correct
if (isEmpty(id)) {
  return;
}
doSomething(id);

// ✗ wrong
if (!isEmpty(id)) {
  doSomething(id);
}
```

### Work through `.ui`, never the `select` directly

Every `<select>` inside a `ui-popup-menu`, `ui-list-box`, or `ui-menu` is backed by a component reachable at `select.ui`. The component owns the rendered markup — the visible label, the styled option rows — so changing the `select` element directly leaves what the user sees stale.

```javascript
// ✓ correct — replaces every option and re-renders
view.ui.select("status").ui.addNewOptions([{ id: "1", name: "Active" }]);

// ✓ correct — clears every option
view.ui.select("status").ui.removeAllOptions();

// ✓ correct — selects by the option's value, and updates the visible label
view.ui.select("status").ui.selectValue("1");

// ✓ correct — reads the selection
const value = view.ui.select("status").ui.selectedValue();

// ✗ wrong — the rendered options are not rebuilt
select.options.length = 0;
select.add(new Option("Active", "1"));

// ✗ wrong — the visible label still shows the previous choice
select.value = "1";
```

`addNewOptions` calls `removeAllOptions` first, so use it directly to replace a list; there is no need to clear beforehand.

Reading `select.value` happens to return the right string, because the component keeps `selectedIndex` in sync. Prefer `selectedValue()` anyway: it is the documented interface, and it keeps read and write symmetric.

Component APIs are indexed per component in [`js-api.md`](js-api.md).

### JavaScript class syntax

All **new** JavaScript classes (OS components, UI components, model structs, etc.) use the `class` keyword:

```javascript
// ✓ correct — new types use class syntax
class UIWindow {
  constructor(containerEl) {
    this.containerEl = containerEl;
  }

  close() { ... }
}

// ✗ wrong — function constructor style (legacy only; do not create new ones)
function UIWindow(containerEl) {
  this.containerEl = containerEl;
  function close() { ... }
  this.close = close;
}
```

Existing function-constructor types (e.g. `UIWindow`, `UIListBox`) are **not** required to be migrated — leave them as-is unless you are rewriting them for another reason.

### Controller method naming

The `this` property name **must exactly match** the function name. HTML `onclick` must use the same name.

```javascript
// ✓ correct
function closeWindow() { ... }
this.closeWindow = closeWindow;
// HTML: onclick="$(this.controller).closeWindow();"

// ✗ wrong
function closeWindow() { ... }
this.close = closeWindow;
// HTML: onclick="$(this.controller).close();"  — mismatch
```

### `configure` method rules

- Parameters ≤ 2: pass individually with `_` prefix
- Parameters ≥ 3: pass an `Object` (document its shape in JSDoc)
- Always add JSDoc to `configure`
- Place ID variables near the top of the controller function
- `configure` **only assigns** values to private variables — no DOM access, no network calls. The view does not exist yet. Use those variables in `viewDidLoad`, `save`, etc.
- Call `parseInt` inside `configure` (or inside the Config constructor) for every ID parameter
- For controllers using an Object config (≥3 params), define a `<ControllerName>Config` function (e.g. `SupplyFieldConfig`) — **not** a `class` — because the controller script is re-evaluated on every load and would cause a redeclaration error. Use `property(this, "key", value)` inside the function. Declare a single `let config = null;` variable. The `configure` method accepts `@param {<ControllerName>Config} config`. In `viewDidLoad`, guard with `if (isEmpty(config)) { throw new Error("..."); }`. Callers may pass a plain object matching the Config shape; an explicit instance is not required when such an object already exists.

### Configure guard position

The ID guard (or config guard) is the first conditional in `viewDidLoad`:

```javascript
// ✓ guard is first
async function viewDidLoad() {
  if (isEmpty(stationId)) {
    throw new Error("Station: stationId is required");
  }
  const menu = view.ui.select("queue").ui;
  menu.delegate = { ... };
  // ...
}

// ✗ logic before guard
async function viewDidLoad() {
  const menu = view.ui.select("queue").ui;
  menu.delegate = { ... };
  if (isEmpty(stationId)) {  // too late
    throw new Error("Station: stationId is required");
  }
}
```

Guards must **throw** — not silently `return`. A missing required ID is a programming error, not a normal code path. The only exception is a null ID that represents a deliberate create mode (e.g. `workUnitId = null` to create a new work unit).

For Config-object controllers (≥3 params), check all required fields once at the top of `viewDidLoad` using optional chaining:

```javascript
// ✓ single guard covers all required fields
async function viewDidLoad() {
  if (isEmpty(config?.companyId) || isEmpty(config?.stationId) || isEmpty(config?.operationId)) {
    throw new Error("Operation: companyId, stationId, and operationId are required");
  }
  const agentMenu = view.ui.select("agent").ui;
  agentMenu.delegate = {
    didFocusSearchMenu: async function(initialize) {
      if (!initialize) { return null; }
      return os.network.get(`/lean/suggested-agents/${config.companyId}`);
    },
    // ...
  };
}

// ✗ redundant per-callback guards
async function viewDidLoad() {
  if (isEmpty(config?.companyId)) { throw new Error("..."); }
  agentMenu.delegate = {
    didFocusSearchMenu: async function(initialize) {
      if (!initialize) { return null; }
      if (isEmpty(config.companyId)) { return []; } // unnecessary — already guarded above
      return os.network.get(`/lean/suggested-agents/${config.companyId}`);
    }
  };
}
```

```javascript
// ✓ two params
function configure(_companyId, _factoryId) {
  companyId = _companyId;
  factoryId = _factoryId;
}

// ✓ use the values once the view exists
function viewDidLoad() {
  loadData(companyId, factoryId);
}

// ✓ three+ params: use an Object
/**
 * @param {object} cfg
 * @param {number} cfg.companyId
 * @param {number} cfg.factoryId
 * @param {string} cfg.mode
 */
function configure(cfg) { ... }
```

### Button ordering

Left to right: `secondary` → `primary` → `default`. Only one `default` per window.

```html
<div class="controls">
  <button class="secondary">Less common</button>
  <button class="primary">Cancel</button>
  <button class="default">Save</button>
</div>
```

### `didHitEnter` and default button

The `didHitEnter` callback and the `default` button **must** reference the same function.

```javascript
function save() { ... }
this.save = save;
this.didHitEnter = save;   // same function
```

`didHitCancel` must **not** be set as the cancel/close default action.

### Delegate wiring rule

Applies to **all** delegates (UIListBox, UITabs, UISlider, controller delegates, etc.):

- **≤ 2 operations** → inline the function directly in the delegate object.
- **≥ 3 operations** → create a private controller function matching the delegate callback signature and reference it by name.

```javascript
// Inline (≤ 2 operations)
listBox.delegate = {
  didSelectListBoxOption: function(opt) { loadDetail(opt.value); }
};

// Private function (≥ 3 operations)
listBox.delegate = {
  didSelectListBoxOption: didSelectListBoxOption
};

async function didSelectListBoxOption(opt) {
  // operation 1 ...
  // operation 2 ...
  // operation 3 ...
}
this.didSelectListBoxOption = didSelectListBoxOption;
```

### Delegate method comments

Every method listed in a `protocol()` declaration must have a JSDoc comment immediately above the string literal. Methods that receive a model use `@param`; methods with no parameters use a single-line description.

```javascript
let delegate = protocol(
  "SupplyDelegate", this, "delegate",
  [
    /**
     * @param {Supply} supply - The saved supply.
     */
    "didSaveSupply",
    /**
     * Called when the supply was deleted.
     */
    "didDeleteSupply"
  ]
);
```

### Save returns the full server response

The `save()` function assigns the server response to a variable and passes it directly to the delegate:

```javascript
// ✓ correct — pass the full server response
let response;
try {
  response = await os.network.put(`/lean/supply/${supplyId}`, { name, theme, amount });
}
catch {
  os.ui.showError("Failed to save supply. Please try again later.");
  return;
}
delegate.didSaveSupply(response);

// ✗ wrong — local object construction
try {
  await os.network.put(`/lean/supply/${supplyId}`, { name, theme, amount });
}
catch { ... }
delegate.didSaveSupply({ id: supplyId.toString(), name });
```

### UIListBox delegate initialization order

Set the delegate **before** loading data, so the first auto-selected item triggers the callback:

```javascript
function viewDidLoad() {
  // 1. Set delegate first
  view.ui.select("my-list").ui.delegate = {
    didSelectListBoxOption: function(opt) { loadDetail(opt.value); }
  };
  // 2. Then load data
  loadItems();
}
```

### `configure` parameter order

Parent ID before child ID: `configure(companyId, factoryId)` not `configure(factoryId, companyId)`.
When creating a new child record, pass `null` for the child ID: `ctrl.configure(companyId, null)`.

### Application menu vs. File menu

The **application menu** (named after the app, e.g. `Lean`) is for app-level navigation and commands — items that apply globally regardless of which window is open (e.g. "Show companies", "About", "Close/Quit").

The **`File` menu** mirrors the current window's primary actions (Save, Delete, Cancel) for keyboard accessibility. App-level navigation belongs in the application menu.

```html
<select name="application-menu">
  <option>Lean</option>
  <option onclick="$(this.controller).showAbout();">About Lean</option>
  <option class="group"></option>
  <option onclick="$(this.controller).showHome();">Show companies</option>  <!-- app-level nav -->
  <option class="group"></option>
  <option onclick="$(this.controller).close();">Close Lean</option>
</select>
```

### File menu accessibility

Every window with a Save/Cancel/Delete action should mirror those in a `File` menu for keyboard accessibility.

### Focus in `viewDidAppear`

Set focus to the first editable field in `viewDidAppear`, not `viewDidLoad`, so focus is applied after the view is visible:

```javascript
function viewDidAppear() {
  view.ui.input("name").focus();
}
```

### Remote controller pattern

```javascript
// The second argument is the server-rendered path
const win = await $(app.controller).loadController("Detail", `/api/item/${id}`);
win.ui.show(function(ctrl) { });
```

### Fire-and-forget saves

State auto-saves (e.g., checkbox toggles) that do not need a response can omit `await`:

```javascript
os.network.post("/my-feature/toggle", { id, enabled });  // no await, no error handling
```

### Optional fields in `save()`

When a form field is optional and `null` is a valid value, pass it directly in the network call body:

```javascript
// Correct — null is a valid value; pass as-is
await os.network.put(`/lean/station/${stationId}`, { name, assigneeAction, theme });

// Wrong — unnecessary conditional reconstruction
await os.network.put(`/lean/station/${stationId}`, {
  name,
  assigneeAction,
  theme: theme != null ? { id: theme.id, fill: theme.fill, stroke: theme.stroke } : null
});
```

### Comment wording

Describe *what* the code does. Avoid the word "programmatically" — it is superfluous in code comments.

```javascript
// ✓ correct
// Set the selected value without user interaction.

// ✗ wrong
// Programmatically set the selected value.
```

### Agent self-verification after multi-file edits

After making simultaneous edits to multiple files (e.g. via a multi-replace operation), verify each affected file to confirm no stray characters, extra braces, or truncated lines were introduced by boundary errors in the replacement strings.

---

## 17. App memory.md Files

An app bundle may include an optional `memory.md` file at the root of its bundle directory:

```
/public/boss/app/io.bithead.my-app/memory.md
```

**Purpose:** `memory.md` is a living reference document maintained by an AI agent. It captures app-specific conventions, data model hierarchy, file locations, form field mapping rules, known patterns, and any decisions made during development. It is the agent's persistent memory for that specific app — written to survive across separate sessions.

**When to read it:** At the start of any session working on an app, read `memory.md` before making any changes. It will tell you the current state of the app, conventions already established, and patterns that should be followed.

**When to update it:** After any significant session — new controllers added, new conventions decided, data model changes, or notable patterns discovered — update `memory.md` to reflect the current state.

**What to put in it:**
- Key file paths (controller files, CSS, route files, DB migrations)
- Data model hierarchy and relationships
- Established conventions specific to this app (route naming, fragment naming, parameter order)
- Form field mapping rules
- Known gotchas or non-obvious behaviors

**Example structure** (see `/public/boss/app/io.bithead.lean/memory.md` for a real example):

```markdown
# Session Memory

## Last updated: YYYY-MM-DD

## Key files
- Controller: `public/boss/app/<bundle_id>/controller/Home.html`
- Routes: `server/web/Sources/App/Routes/<Feature>/<Feature>Route.swift`

## Model hierarchy
Parent (1) → Child (many)

## Conventions
- configure() parameter order: parentId, childId
- Route: POST /my-feature/item (create + update)
- Empty response: Fragment.OK()
```

---

## Running and Validating Locally

### Python environment

The private services' dependencies (FastAPI, pydantic, uvicorn, pytest, httpx) are **not** on the system Python. Activate the shared virtualenv first — otherwise `import fastapi` fails and you will be tempted to hand-roll stubs:

```bash
source ~/.venv/bin/activate
```

### Services and ports

| Service | Port | Source |
|---|---|---|
| Swift + Vapor web server | 8081 | `server/web/` |
| Python private services | 8082 | `private/api.py` |
| nginx (fronts both, TLS) | 443 | `private/nginx.conf`, `private/dev-nginx.conf` |

```bash
private/start      # start services
private/restart    # restart after a change
private/stop
```

### Exercising a new private service without a browser

Mount the router on a real FastAPI app and drive it over ASGI. This validates route signatures, `response_model`s, and body params — things a syntax check cannot:

```python
import importlib.util, sys, asyncio, httpx
from fastapi import FastAPI

spec = importlib.util.spec_from_file_location("io.bithead.my-app", "app/io.bithead.my-app/__init__.py")
m = importlib.util.module_from_spec(spec); sys.modules["io.bithead.my-app"] = m
spec.loader.exec_module(m)

app = FastAPI(); app.include_router(m.router)

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/io.bithead.my-app/me")
        print(r.status_code, r.json())

asyncio.run(main())
```

> `starlette.testclient.TestClient` is incompatible with the installed httpx version. Use `httpx.ASGITransport` as above.

### Tests

```bash
source ~/.venv/bin/activate
private/run_tests.sh private/tests/test_<app>.py            # whole file
private/run_tests.sh private/tests/test_<app>.py <test_fn>  # one test
```

Test harness helpers live in `private/tests/libtest/`; `private/tests/test_wordy.py` is the reference for `get_app_module(...)` setup.

### Validating an app bundle

```bash
bin/validate-app io.bithead.my-app   # one bundle
bin/validate-app --all               # every bundle
```

Checks controller ↔ `application.json` ↔ `installed.json` registration, JavaScript syntax (after template-command resolution), that every `onclick` resolves to an exported `this.*`, that every BOSS API method called actually exists, that no `<select>` in a menu is empty, that every `os.network.*` call maps to a route in the app's private service, and warns on native `alert()` / `confirm()` / `prompt()` and single-line `if` statements.

Module controllers (`"module": true`), shared embedded controllers (`EmbedController(Name)`), and Godot controllers are all resolved correctly; generated bundles are skipped.

Run this before saying a bundle is complete. It catches the failures that otherwise only appear in a browser.

**Adding a check:**
- Validate it against every existing bundle (`--all`) before keeping it. A false positive is a missing piece of your model of the system, not noise to suppress.
- "Technically true" is not "worth reporting." Before emitting an error, ask what breaks for the developer if it is ignored. If nothing breaks, it is a warning or it is silence.

### Looking up a BOSS API method

```bash
bin/boss-api             # regenerate docs/prompt/js-api.md
bin/boss-api --check     # fail if the committed index is stale
```

[`js-api.md`](js-api.md) lists every public method **grouped by the component that defines it**. Several components define the same name (`selectOption` is on four), so grepping `ui.js` proves only that a name exists somewhere — not that it exists on the object you are holding. Check the component's own entry.

---

## Quick Reference

| Task | Where to look |
|---|---|
| BOSS API surface by component | `/docs/prompt/js-api.md` (generated by `bin/boss-api`) |
| Validate an app bundle | `bin/validate-app <bundle_id>` |
| All UI components (live examples) | `/public/boss/app/io.bithead.tutorial/controller/Example.html` |
| Application with menus | `/public/boss/app/io.bithead.tutorial/controller/Application.html` |
| OS/UI/Network API signatures | `/public/boss/foundation.js`, `os.js`, `ui.js`, `network.js` (read JSDoc) |
| app-structure.md (full spec) | `/docs/app-structure.md` |
| API overview | `/docs/api.md` |
| Coding style guide | `/docs/coding-style.md` |
| Development workflow | `/docs/prompt/process.md` |
| Software engineering best practices | `/docs/prompt/tetsuo.md` |
| Lean app conventions (reference impl) | `/public/boss/app/io.bithead.lean/memory.md` |
| bosslib architecture and XCTest patterns | §14 of this document |

---

## Development Order

Follow this order when building a new feature:

1. **UI/UX first** — build the controller HTML and create stubbed backend routes + fixtures at the same time (even if they return static data).
2. **BOSS OS changes** — only if the feature requires a new OS-level API or UI component. Ask the developer before making changes here.
3. **Public API routes** — replace stubs with real network calls; implement the Swift route handlers.
4. **Write tests** — private API (bosslib service) only, when the method has 3 or more distinct behaviours.
5. **Write implementation** — write only the logic needed to make the current tests pass. No speculative code.
