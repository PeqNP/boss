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
  <media_path>/         Per-app files, outside the repo — see python.md § Storing a file
/private/               Python private web services (per-app)
/server/web/            Swift+Vapor primary web server
/server/bosslib/        Shared Swift library used by the web server
/uitest/                Playwright UI tests
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
| `licensed` | `false` | Somebody must hold a license to open the app. Absent means no, so requiring one is a deliberate act rather than something every app inherits. Only a licensed app appears in the App Store, and Settings disables its **Issue license** checkbox for an app that requires none. See [`io.bithead.app-store/plan.md`](/private/app/io.bithead.app-store/plan.md). |

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

### Prose describes what to do

Documentation, comments, and rules read as description. A rule states the shape
that is wanted, and the reader follows it:

```
Every internal id is indexed.
Quote the plan's Open Decision verbatim — the wording is the question.
The developer commits. Write the message and hand it over.
```

### A rule stands on its own

The reasoning that produced a rule shapes its wording. The rule is what gets
written.

A discussion may arrive with its justification attached — the bug that prompted
it, the argument that settled it, the alternative that was weighed. That
material does its work while the rule is being decided, and the finished rule
carries the result:

```
Both sides of a join table are looked up by, so each gets an index.
```

Mechanism the reader needs in order to apply a rule belongs with it. The test
is whether the sentence changes what somebody does:

```
A composite key gets one implicit index, sorted by its columns in order, which
serves a lookup by the leading column and by the whole key.
```

### Examples carry the rule

A code example showing the correct usage stands on its own. Where two patterns
look alike enough that the distinction stays ambiguous in prose, a second block
shows the alternate form, and the prose around it names the difference:

```javascript
// The list box reports every tap, so each one is an action.
delegate.didSelectListBoxOption(option);
```

Reach for a paired example once the prose has been tried. A rule that reads
clearly carries itself.

**When an instruction produces the wrong outcome, strengthen it positively.**
Two moves, chosen case by case: add the further instruction that would have
produced the right result, or pair the examples so the two forms sit side by
side.

**Ask when a case is ambiguous.** A guess written into these documents is
repeated in every generation that follows, so an unclear rule is worth one
question before it is worth one edit.


### Template literals over concatenation

A string built from values uses a template literal — backticks, with each value
in a `${...}` substitution:

```javascript
// ✓ correct
win.span("name").textContent = `${c.firstName} ${c.lastName}`;
const url = `/api/io.bithead.scheduler/admin/job/${jobId}/payment`;

// ✗ wrong
win.span("name").textContent = c.firstName + " " + c.lastName;
const url = "/api/io.bithead.scheduler/admin/job/" + jobId + "/payment";
```

The whole string reads in one piece, spacing included, and the values sit where
they land rather than between quotes.

A URL is the case with a second reason. `bin/validate-app` matches a call
against the route it reaches, and it reads the string the call opens with — a
concatenated URL hands it a prefix, which matches no route, so every field the
screen reads off that response goes unchecked. A template literal carries the
whole path in one string, and the check can see it.

Use `+` where there is nothing to interpolate: joining two strings a line apart,
or appending inside a loop.

### `if` statements span multiple lines

Always expand an `if` to multiple lines, even for a single-statement body:

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

Introduce a client-side model class when it adds behavior, validation, computed properties, or methods of its own.

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

`addNewOptions` calls `removeAllOptions` first, so it replaces a list in one call.

Read through `selectedValue()`. It is the documented interface, and it keeps read and write symmetric.

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
- `configure` **only assigns** values to private variables. The view arrives later, so DOM access and network calls belong in `viewDidLoad`, `save`, and the rest, which read those variables.
- Call `parseInt` inside `configure` (or inside the Config constructor) for every ID parameter
- For controllers using an Object config (≥3 params), define a `<ControllerName>Config` **function** (e.g. `SupplyFieldConfig`) — the controller script is re-evaluated on every load, and a function redeclares cleanly where a `class` raises. Use `property(this, "key", value)` inside the function. Declare a single `let config = null;` variable. The `configure` method accepts `@param {<ControllerName>Config} config`. In `viewDidLoad`, guard with `if (isEmpty(config)) { throw new Error("..."); }`. Callers may pass a plain object matching the Config shape.

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

State auto-saves (e.g., checkbox toggles) whose answer nobody reads can omit `await`:

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

A comment says what the code does. It does not say why.

The reason belongs in the commit message, in the app's plan, or nowhere. A
comment that argues is where the writing slips: the sentence stops describing
and starts explaining, the subject drops out of it, and the point ends up in a
clause hung off the end. Removing the reason removes all three.

```python
# ✓
# Checked before the request is sent.

# ✗ the same comment, explaining itself
# Checked here so the operator is told what is missing. The server refuses a
# payment with no method, but its answer only says the payment failed.
```

`bin/check-comments` reports a comment that carries a reason.

Describe *what* the code does, in the fewest words that say it.

```javascript
// ✓ correct
// Set the selected value without user interaction.

// ✗ wrong
// Programmatically set the selected value.
```

A docstring opens with what the function decides, then shows one instance
using real names.

```python
# ✓ correct
"""True when a removed route was added back under a prefix.

`/dashboard` removed and `/business/{business_id}/dashboard` added is the
same route in a new place.
"""

# ✗ wrong
"""Whether this name went somewhere else rather than away.

A route moved under a prefix is one route in a new place. Naming every one
of those turns a bulk move into a list nobody reads, where the message
wants to name the prefix once.
"""
```

Shapes to write out of a comment:

```python
# ✗ no subject, only making sense as a continuation of something else
# Asked for the same way the amount is. Without it the body carries no
# method, the route refuses it, and the screen says only that something
# failed.
# ✓
# Checked here so the operator is told what is missing. The server refuses
# a payment with no method, but its answer only says the payment failed.

# ✗ a metaphor standing in for the fact
# The lock shuts the customer's door, not this one.
# ✓
# `locked` means the customer failed too many verification codes and can no
# longer change this appointment themselves. An operator still can.

# ✗ a trailing clause carrying the point
# ...a `default` role holding every feature, which is what an app uses
# before it has roles of its own.
# ✓
# An app that declares no roles receives a `default` role holding every
# feature.

# ✗ `where` meaning `whereas`
# ...a list nobody reads, where the message names the prefix once.
# ✓
# The message names the prefix once.

# ✗ giving a thing intentions
# The check refuses a route the app did not mean to open.
# ✓
# The check reports a route that names a feature and no role.
```

A comment in a test follows the same rule. It does not continue the test's
name, and it is worth writing only when it says something the assertion below
it does not — why the test is built this way, or why a weaker assertion would
pass. Delete a comment that restates its assertion.

```javascript
// ✗ continues the test name, and restates the assertion
test("reject empty payment", async ({ page }) => {
  // it: is asked for rather than sent
  await expect(alert).toBeVisible();

// ✓
test("reject empty payment", async ({ page }) => {
  // The alert is the assertion. The server refuses a zero payment too, so an
  // empty transaction list passes even with the screen's own check deleted.
  await expect(alert).toBeVisible();
```

### Agent self-verification after multi-file edits

After making simultaneous edits to multiple files (e.g. via a multi-replace operation), verify each affected file to confirm no stray characters, extra braces, or truncated lines were introduced by boundary errors in the replacement strings.

---

## 17. App memory.md Files

An app bundle may include an optional `memory.md` file at the root of its bundle directory:

```
/public/boss/app/io.bithead.my-app/memory.md
```

**Purpose:** orientation for a session that starts cold. It answers three questions and nothing else: where is this app now, what is next, and what would I waste time rediscovering?

**When to read it:** at the start of any session working on the app, before making changes.

**When to update it:** when the answer to one of those three questions changes. Deleting a line that has stopped being true matters more than adding one.

**Keep it short.** Every line must change what the next session does. A line that only records what a past session did is dead prompt context, carried into every future run.

**What belongs elsewhere:**

| Content | Where it belongs |
|---|---|
| A rule that would apply to any app | `docs/prompt/` — promote it, then point at it |
| The design: schema, endpoints, controller layouts | the app's `plan.md`, which is the contract |
| What a past session did, and why | nowhere. The code and its comments are the record |
| Rationale for a decision already implemented | a comment where the decision lives |

**What to put in it:**
- Current stage, and the next step
- Open decisions still unresolved, and anything knowingly left undone
- Non-obvious behaviour specific to this app that cost time to learn and is written down nowhere else
- Pointers to the files that matter — paths, not copies of their contents

A rule lives in the document that owns it, and every other mention is a link.

```markdown
# Session Memory — <App>

Stage 4 complete. Stage 5 (wiring routes to `lib`) is next.

## Watch out for
- `addNewOptions` auto-selects option 0 and fires `didSelectListBoxOption`.
  Set the delegate before loading data.

## Open
1. Auth decorators are not applied yet — see the banner in `__init__.py`.
2. Shared floor-terminal identity is still undecided.
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
bin/services      # what holds each port
```

It asks who holds the socket. Counting processes with `ps | grep` answers a
different question and gets it wrong — the shell running the grep carries the
pattern on its own command line, so one service reads as two. Several PIDs on
a port is nginx's ordinary shape: a master forks workers that inherit the
socket. Unrelated listeners on one port is the fault, and `bin/services` is
what tells them apart.

Restart the service whose source you changed, tracking your own edits — see
*After changing code* below for which change reaches which service.

These three are the only way a service starts. A substitute — a static file
server, a stub backend, a side harness — answers with something other than the
code under test, so a service that stays unreachable is worth saying so and
stopping.

```bash
private/start
private/restart
private/stop
```

### Reading a service's log

A 500 from a private service says nothing useful in the response. The
traceback is in the log:

```bash
tail -200 "$(grep '^log_path' ~/.boss/config | cut -d' ' -f2)/boss"
```

The path comes from the **live** config at `~/.boss/config`. `private/config`
and `private/dev-config` are deployment templates, naming directories a
development machine has yet to create. The file is named for the service
(`boss`), with no extension.

Read it first when a 500 arrives — it names the line.

### Exercising a new private service without a browser

Mount the router on a real FastAPI app and drive it over ASGI. It runs in
process, leaving whatever is running untouched, and it validates route
signatures, `response_model`s, and body params:

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

### After changing code

What was changed decides whether anything needs restarting:

| Changed | What to do |
|---|---|
| `public/**` — OS JavaScript, CSS, controllers | Nothing. Reload the page, or just re-run the UI tests; each one loads the page fresh. |
| `private/**` — Python services | Restart Python. |
| `server/**` — Swift web server | Build and start Swift, then restart Python. |

Restart what the change touched, and leave the rest running — between tests,
between prompts, all session. The signal to restart is having edited the source
yourself. A service that answered a minute ago is serving the same code until
somebody changes it.

**Python** — also start it when 8082 is quiet. Activate the virtualenv first;
the start script calls `python3`:

```bash
source ~/.venv/bin/activate
./private/restart
```

`private/restart` finishes by running `bin/services`, which reports what holds
each port.

`private/restart` runs `bin/check-db --fix` before anything starts, so a
database that has fallen behind its schema is rebuilt while nothing is serving
from it. It says which databases it rebuilt and what they were missing. See
[`python.md` § Schema drift](python.md#schema-drift).

**Swift** — also start it when nothing is listening on 8081. Build from
`server/web`, and run from there too: Vapor resolves `Resources/` and
`Public/` against the working directory.

```bash
cd server/web
swift build
nohup .build/debug/boss serve > /tmp/boss-vapor.log 2>&1 &
cd ../.. && ./bin/services           # confirm it is up
tail /tmp/boss-vapor.log             # "Server started on http://0.0.0.0:8081"
```

Skip the build when no `.swift` file is newer than the binary:

```bash
find server -name "*.swift" -newer server/web/.build/debug/boss
```

**Restarting Swift means restarting Python too**, because the Python service
registers itself with Swift as it starts. Restarting Python alone leaves Swift
untouched.

The ports: nginx serves 443 and 8080, proxying `/api` to Python on 8082 and
everything else to Vapor on 8081. A 502 from `https://localhost` means Vapor is
down; `/api` failing while pages load means Python is.

Most work touches only `public/`, which reloads with the page. A restart is
what puts the code under review in front of the test.

**A private service that will not import is skipped, not fatal.** `api.py`
catches the failure per app, logs it, and carries on — so the service starts,
binds its port, and answers every request for that app with FastAPI's own 404.
The one record of it is a log line going to `/dev/null`, so the symptom reads
as a routing mistake. `bin/check-services` catches it, and `bin/check` runs
it.

**Confirm the restart took before reading any result.** Ask the changed
endpoint for the thing that changed, and check it answers the new way:

```bash
curl -sk "https://localhost/api/<bundle>/<route>" | head -c 200
```

Each reload wants its own confirmation — a stale answer reads exactly like a
bug in the client.

### Naming a test

A test is named for the behaviour it covers: a verb and the thing it acts on, in
the words the project already uses for them.

**Each platform keeps its own convention.** The name is the same idea in each;
only the spelling changes.

| Platform | Convention | Examples |
|---|---|---|
| Python | `test_` prefix, `snake_case` | `test_register_acl` · `test_book_appointment` |
| Swift | `test_` prefix, `camelCase` | `test_registerAcl` · `test_bookAppointment` |
| Playwright | the string a `test(...)` takes: a plain phrase, no prefix | `"inject BOSS user"` · `"whoami without a business"` · `"book appointment"` |

A UI spec takes no prefix because Playwright supplies one — the file name and
the `describe` are printed with it, and they already say which app and which
area. So the name carries the behaviour and nothing else.

Two or three words. The name appears in a failure line, in `swift test
--filter`, and in `run_tests.sh <file> <test_name>`, so it is read far more
often than it is written — and what it has to answer, on its own, is which
feature broke.

Terms the project uses are what make that work. A name assembled from ordinary
English describes the test to whoever wrote it and leaves everyone else to open
the file: `keepUnregisteredAcl` names a thing the codebase talks about, where
`registrationSpeaksOnlyForTheAppsItCarries` is a sentence that has to be read
twice and still sends you to the source.

The same trap catches a UI spec, where a plain phrase invites a sentence. "The
month marks the day something was booked on" says nothing a reader can act on;
`schedule month` names the thing that broke.

Detail belongs in the cases. `describe:` and `it:` carry what varies, and the
docstring carries why — the function name stays the feature.

### Tests

One run at a time. `private/run_tests.sh` takes a lock and `bin/mutate` holds
it across its whole run, so a suite started beside either is refused with a
message rather than sharing a database with it — two runs create and drop the
same tables under each other, and it surfaces as `no such table` across most
of the run.

```bash
source ~/.venv/bin/activate
private/run_tests.sh private/tests/test_<app>.py            # whole file
private/run_tests.sh private/tests/test_<app>.py <test_fn>  # one test
```

Test harness helpers live in `private/tests/libtest/`; `private/tests/test_wordy.py` is the reference for `get_app_module(...)` setup.

### UI tests

Playwright tests in `uitest/` drive BOSS in a real browser against a server the
developer is running. Commands, failure triage, locator rules, and how to add a
test all live in [`uitest/README.md`](../../uitest/README.md) — read it before
writing or debugging one.

**Run them when the work is finished, or when fixing a visual bug.** A layout
or markup change is faster for the developer to see in the browser, so ordinary
UI work goes to them. Ask first where a run seems warranted outside those two
cases.

Two things worth knowing without opening it:

- Adding a component to the OS means adding it to `io.bithead.tutorial`'s
  `Example` controller too, so the component library stays exercisable in a
  single pass.
- A change under `public/**` is picked up by the next run.

### Validating an app bundle

```bash
bin/validate-app io.bithead.my-app   # one bundle
bin/validate-app --all               # every bundle
```

```bash
bin/validate-app --rules   # what it enforces, and where each rule is written
```

Errors are things that break at runtime. Warnings are coding rules from §16 that
a static check can decide.

**The rules stay in this document; the checks detect.** This document gives the
correct form before you write it, and a check reports on what was written. For
the list of checks, run `--rules`, which reads it from the checks themselves.

A check enforces a rule through a skipped document and a summarized context
alike. Where a rule can be checked, add the check.

Module controllers (`"module": true`), shared embedded controllers (`EmbedController(Name)`), and Godot controllers are all resolved correctly; generated bundles are skipped.

Run this before saying a bundle is complete. It catches the failures that would otherwise wait for a browser.

**Adding a check:** run it against every existing bundle (`--all`) before
keeping it. The bars every check meets are in
[`process.md` § What a check has to be](process.md#what-a-check-has-to-be).

### Checking a service still serves what it did

```bash
bin/check-routes                 # every app, against HEAD
bin/check-routes --against <ref>
```

Replacing a span of a route file between two markers takes whatever else was
between them. This compares the routes a service has against the routes it had,
and fails closed: a run that cannot read either side says so rather than
reporting every route as lost.

`bin/check` runs it.

### Hooks

`.claude/settings.json` wires two, and `.claude/hooks/` holds them.

| Hook | Event | What it does |
|---|---|---|
| `commit-message.py` | `Stop` | Blocks a reply that leaves the tree dirty and carries no commit message. Blocking a `Stop` hands the reason back, so the message is written before the turn ends. |
| `scoped-work.py` | `PreToolUse` on `Bash` | Refuses `npx playwright test` with no file, and refuses starting Swift without `bin/restart`. |

Each rule in `scoped-work.py` names a command and the cheaper form to use
instead. Add one when a command is found to cost more than the work it does.

Test a hook by feeding it a payload:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"npx playwright test"}}' \
  | .claude/hooks/scoped-work.py
```

### Restarting a service

```bash
bin/restart            # Python
bin/restart --swift    # Swift, then Python
```

Python reads a session Swift minted. Restarting Swift alone leaves Python
rejecting every token Swift issues, and every route answers "Please sign in
before accessing this resource".

### Minting a session after granting a licence or a role

```
POST /account/session
```

A session carries the apps and roles it was minted with. An app that grants a
licence or a role to the user who is signed in changes nothing about that
user's current session, so every route guarded by the new role refuses them
until they sign in again. This route removes the session the request arrived
on, mints one naming what the caller now holds, and sets the cookie.

Call it after `grant_license` or `grant_role` and before opening any window
that depends on either.

`GET /account/refresh` is a different thing: it holds off the inactivity
timeout and mints nothing.

### Checking a rule that belongs to one app

```bash
bin/<bundle>/check.py            # e.g. bin/io.bithead.scheduler/check.py
```

The shared checkers run against every service, so they hold only rules that are
true of every service. A rule that names one app's own concepts goes in
`bin/<bundle>/check.py` instead. `bin/check` discovers these by path and runs
each one, so adding the file is all it takes to have it run; nothing lists the
apps by name.

Write one when a defect you just fixed has a shape a reader could repeat. The
Scheduler's says that a route naming a business in its path passes that business
to the `lib` call, because twenty-two functions took only the record's id and an
operator could reach another business's records with it.

### Checking documentation links

```bash
bin/check-docs
```

A rule lives in exactly one document; others point at it. That removes drift but
depends on the pointer staying valid, so this verifies every relative link
between Markdown files resolves. Run it after moving or renaming a document.

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
| Reference implementation (full stack) | `/public/boss/app/io.bithead.scheduler/`, `/private/app/io.bithead.scheduler/` (its `plan.md` is the worked example of a plan) |
| Reference implementation (OS patterns) | `/public/boss/app/io.bithead.settings/`, `/public/boss/app/io.bithead.tutorial/` |
| bosslib architecture and XCTest patterns | §14 of this document |

---

## Development Order

Follow this order when building a new feature:

1. **UI/UX first** — build the controller HTML and create stubbed backend routes + fixtures at the same time (even if they return static data).
2. **BOSS OS changes** — only if the feature requires a new OS-level API or UI component. Ask the developer before making changes here.
3. **Public API routes** — replace stubs with real network calls; implement the Swift route handlers.
4. **Write tests** — private API (bosslib service) only, when the method has 3 or more distinct behaviours.
5. **Write implementation** — write only the logic needed to make the current tests pass. No speculative code.
