# BOSS Agent Reference

This is the primary reference document for AI agents building BOSS applications. It consolidates all critical information inline so you do not need to follow chains of links to get started. Links to deeper detail are provided where useful.

---

## Table of Contents

1. [What is BOSS](#1-what-is-boss)
2. [Project Layout](#2-project-layout)
3. [App Bundle Structure](#3-app-bundle-structure)
4. [application.json](#4-applicationjson)
5. [Controller Pattern](#5-controller-pattern)
6. [Application Controller Pattern](#6-application-controller-pattern)
7. [Embedded Controllers](#7-embedded-controllers)
8. [Element Accessor APIs](#8-element-accessor-apis)
9. [UI Components — HTML Markup](#9-ui-components--html-markup)
10. [UI Components — JavaScript Access](#10-ui-components--javascript-access)
11. [OS APIs](#11-os-apis)
12. [Notifications and Events](#12-notifications-and-events)
13. [Backend — Swift Web Layer](#13-backend--swift-web-layer)
14. [Backend — Swift Private API (bosslib)](#14-backend--swift-private-api-bosslib)
15. [Backend — Python Private Services](#15-backend--python-private-services)
16. [Coding Rules and Conventions](#16-coding-rules-and-conventions)
17. [App memory.md Files](#17-app-memorymd-files)

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
| `/public/boss/network.js` | Network calls: `get`, `post`, `json`, `upload`, `_delete`, `patch` |
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
- **Application controller**: `/public/boss/app/io.bithead.boss-code/controller/Application.html`

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

> **Every new controller file MUST be registered in `application.json` under `"controllers"`.**

---

## 5. Controller Pattern

A controller is an HTML file at `/public/boss/app/<bundle_id>/controller/<Name>.html`.

### Minimal skeleton

```html
<div class="ui-window" style="width: 480px;">
  <script type="text/javascript">
    function $(this.id)(view) {

      // --- Private state ---
      let itemId = null;

      // --- Public API ---

      /**
       * Configure this controller before display.
       *
       * @param {number} _itemId - ID of the item to display
       */
      function configure(_itemId) {
        itemId = _itemId;
      }
      this.configure = configure;

      /**
       * Called before the view is rendered. Load data here.
       */
      function viewDidLoad() {
        // Load data from server, populate UI
      }
      this.viewDidLoad = viewDidLoad;

      /**
       * Called after the view is visible. Set focus here.
       */
      function viewDidAppear() {
        view.ui.input("name").focus();
      }
      this.viewDidAppear = viewDidAppear;

      /**
       * Called before the view is removed.
       */
      function viewWillUnload() {
        // Clean up timers, subscriptions, etc.
      }
      this.viewWillUnload = viewWillUnload;

      function save() {
        const name = view.ui.inputValue("name", "Please provide a name.");
        if (isEmpty(name)) { return; }
        // POST to server
        os.network.post("/my-app/item", { itemId, name });
        view.ui.close();
      }
      this.save = save;

      function cancel() {
        view.ui.close();
      }
      this.cancel = cancel;

      // Wire Enter key to the default action
      this.didHitEnter = save;

      // Optional: listen to all key presses
      this.didHitKey = function(key) { };

      // Optional: listen to OS events
      this.events = {
        "io.bithead.my-app.some-event": async function(ev) {
          console.log(ev.data);
        }
      };

      // Optional: sign-in/sign-out callbacks
      this.userDidSignIn = function(user) { };
      this.userDidSignOut = function() { };
    }
  </script>

  <!-- Window menus (shown in OS bar when this window is focused) -->
  <div class="ui-menus">
    <div class="ui-menu" style="width: 140px;">
      <select name="file-menu">
        <option>File</option>
        <option onclick="$(this.controller).save();">Save</option>
        <option onclick="$(this.controller).cancel();">Cancel</option>
      </select>
    </div>
  </div>

  <div class="top">
    <div class="close-button"></div>
    <div class="title"><span>My Window</span></div>
  </div>

  <div class="container vbox gap-10">
    <div class="text-field">
      <label for="name">Name</label>
      <input type="text" name="name" autocomplete="new-password">
    </div>
    <div class="controls">
      <button class="primary" onclick="$(this.controller).cancel();">Cancel</button>
      <button class="default" onclick="$(this.controller).save();">Save</button>
    </div>
  </div>
</div>
```

### Lifecycle event order

```
configure(...)       ← Called by the opener before show()
viewDidLoad          ← Before rendered; load data here
viewDidAppear        ← After visible; set focus here
  [user interaction]
viewWillUnload       ← Before close; clean up here
```

> Load data from the server in `viewDidLoad`, **not** `configure` — the view is not yet in the DOM during `configure`.

### Loading and showing a controller

```javascript
// Load the controller window
const win = await $(app.controller).loadController("Settings");

// Show it and configure once in DOM
win.ui.show(function(ctrl) {
  ctrl.configure(itemId);
});

// Remote (server-rendered) controller
const win = await $(app.controller).loadController("Detail", `/api/item/${itemId}`);
```

### Referencing app resources in HTML

Use `$(app.resourcePath)` as a template variable in HTML for images or other bundle assets:

```html
<img src="$(app.resourcePath)/image/logo.svg">
```

At runtime this expands to `/boss/app/<bundle_id>/image/logo.svg`.

---

## 6. Application Controller Pattern

When `main` is set to `"Application"` in `application.json`, the file `controller/Application.html` is the entry point. It provides:
- The app's menu bar (shown in the OS bar)
- The app mini-menu (shown when the app icon is tapped while blurred)
- Application lifecycle callbacks

```html
<div class="ui-application">
  <script language="javascript">
    function $(this.id)(view) {

      async function applicationDidStart() {
        // Called after configuration is loaded. Open first controller here.
        const ctrl = os.ui.makeController("Home");
        ctrl.show();
      }
      this.applicationDidStart = applicationDidStart;

      function applicationDidStop() { }
      this.applicationDidStop = applicationDidStop;

      function userDidSignIn(user) { }
      this.userDidSignIn = userDidSignIn;

      function userDidSignOut() { }
      this.userDidSignOut = userDidSignOut;

      // Listen to OS/app events
      this.events = {
        "io.bithead.my-app.some-event": async function(ev) {
          console.log(ev.data);
        }
      };

      // Handle deep links
      this.openDeepLink = async function(deepLink) {
        if (deepLink.path == "/settings") {
          // Open settings controller
        }
      };
    }
  </script>

  <!-- App menu (shown in OS bar when app is focused) -->
  <div class="ui-menus">
    <div class="ui-menu" style="width: 180px;">
      <select>
        <option>My App</option>
        <option onclick="$(this.controller).showAbout();">About</option>
        <option class="group"></option>
        <option onclick="$(this.controller).quit();">Quit My App</option>
      </select>
    </div>
  </div>

  <!-- App icon mini-menu (shown when app is blurred and icon is tapped) -->
  <div class="ui-app-menu">
    <div class="ui-menu" style="width: 180px;">
      <select>
        <option>img:$(app.resourcePath)/icon.svg</option>
        <option onclick="os.switchApplication('$(app.bundleId)');">Switch application</option>
      </select>
    </div>
  </div>
</div>
```

**Application lifecycle order:**

```
applicationDidStart
  userDidSignIn  (if user is already signed in)
  userDidSignOut (when user signs out)
applicationDidStop
```

---

## 7. Embedded Controllers

A `UIWindow` can host multiple embedded `UIController`s. This allows switching content without opening new windows.

```html
<div class="container vbox">
  <div class="ui-controller" id="splash">
    <script type="text/javascript">
      function splash(view) {
        function showSignIn() { ... }
        this.showSignIn = showSignIn;
      }
    </script>
    <p>Welcome! Please sign in.</p>
    <div class="controls">
      <button class="default" onclick="%(splash).showSignIn();">Sign In</button>
    </div>
  </div>
</div>
```

Rules:
- Every embedded controller **must** have an `id`
- The root function name **must** match the `id` (no kebab-case; use camelCase)
- Use `%(controllerName)` as a template command in HTML to reference the controller instance at runtime (expands to `os.ui.controller.controllerName`)
- Embedded controllers receive lifecycle events
- Embedded controllers may only be nested **one level deep**

---

## 8. Element Accessor APIs

Both `UIWindow` (via `view.ui`) and `_UIController` (via `view.ui` on embedded controllers) expose these element accessors. All return `HTMLElement|null`.

```javascript
view.ui.button("name")          // <button name="name">
view.ui.divByName("name")       // <div name="name">
view.ui.div("className")        // <div class="className">
view.ui.element("id")           // document.getElementById("id")
view.ui.input("name")           // <input name="name">
view.ui.pByName("name")         // <p name="name">
view.ui.p("className")          // <p class="className">
view.ui.fieldset("name")        // <fieldset name="name">
view.ui.select("name")          // <select name="name">
view.ui.pre("name")             // <pre name="name">
view.ui.radio("name", "value")  // <input type="radio" name="name" value="value">
view.ui.span("name")            // <span name="name">
view.ui.table("name")           // <table name="name">
view.ui.td("name")              // <td name="name">
view.ui.textarea("name")        // <textarea name="name">
view.ui.iframe("name")          // <iframe name="name">
view.ui.fragment("id")          // Clone of first child of <template id="id">
view.ui.menu("name")            // UIMenu instance for <select name="name"> in ui-menus
```

**Additional window-only helpers:**

```javascript
view.ui.close()                   // Close the window
view.ui.show(fn)                  // Show the window; fn(ctrl) called when ready
view.ui.setTitle("New Title")     // Update window title bar text

// Read a required text input value; returns null and shows error if empty
view.ui.inputValue("name", "Error message if empty")
```

---

## 9. UI Components — HTML Markup

Copy these patterns exactly. The CSS classes drive all visual behavior.

### Field type selection

When mapping a data model property to a form field:

| Data type / context | HTML pattern | Notes |
|---|---|---|
| Primary key / internal ID (`Int`) | `<input type="hidden" name="id">` | Never displayed to user |
| Editable string | `<div class="text-field">` | See text field pattern below |
| FK ID displayed as a label, or any read-only value | `<div class="read-only"><span name="...">` | Populate via `view.ui.span("field").textContent = value` |

### Text field (single line)
```html
<div class="text-field">
  <label for="name">Name</label>
  <input type="text" name="name" autocomplete="new-password">
</div>
```

### Textarea (multi-line)
```html
<div class="textarea-field">
  <label for="description">Description</label>
  <textarea name="description"></textarea>
</div>
```

### Read-only display field
```html
<div class="read-only">
  <label>Owner</label>
  <span name="owner-name"></span>
</div>
```
Populate with: `view.ui.span("owner-name").textContent = value;`

### Hidden field (for IDs)
```html
<input type="hidden" name="id">
```

### Control buttons (bottom of forms)
```html
<div class="controls">
  <!-- Order: secondary → primary → default. Only one default allowed. -->
  <button class="secondary" onclick="$(this.controller).doSecondary();">Secondary</button>
  <button class="primary"   onclick="$(this.controller).cancel();">Cancel</button>
  <button class="default"   onclick="$(this.controller).save();">Save</button>
</div>
```

### Error / info messages
```html
<div class="error-message">This is an error message.</div>
<div class="info-message">This is an informational message.</div>
```

### UIListBox — single select
```html
<div class="ui-list-box" style="width: 200px;">
  <select name="my-list">
    <option value="1">Option 1</option>
    <option value="2" disabled>Option 2 (disabled)</option>
  </select>
</div>
```

### UIListBox — multi select
```html
<div class="ui-list-box" style="width: 200px;">
  <select name="my-list" multiple>
    <option value="1">Option 1</option>
    <option value="2">Option 2</option>
  </select>
</div>
```

### UIListBox — buttons mode
```html
<div class="ui-list-box buttons" style="width: 200px;">
  <select name="my-buttons" multiple>
    <option value="a" onclick="$(this.controller).doA();">Action A</option>
    <option value="b" onclick="$(this.controller).doB();">Action B</option>
  </select>
</div>
```

### UIPopupMenu (drop-down)
```html
<div class="ui-popup-menu" style="width: 160px;">
  <label for="status">Status</label>
  <select name="status">
    <option value="">Select one</option>
    <option value="active">Active</option>
    <option value="inactive">Inactive</option>
  </select>
</div>
```

### UITabs
```html
<div class="ui-tabs">
  <select name="my-tabs">
    <option>Tab One</option>
    <option>Tab Two</option>
    <option class="close-button">Closeable Tab</option>
  </select>
</div>
```

### UISlider (horizontal)
```html
<!-- Parent element defines width -->
<div style="width: 300px;">
  <div class="ui-slider horizontal">
    <select name="my-slider">
      <option>0</option>
      <option selected>50</option>
      <option>100</option>
    </select>
  </div>
</div>
```

### UISlider (vertical)
```html
<!-- Parent element defines height -->
<div style="height: 200px;">
  <div class="ui-slider vertical">
    <select name="my-slider-v">
      <option>0</option>
      <option>50</option>
      <option>100</option>
    </select>
  </div>
</div>
```
Add `hide-values` class to `ui-slider` to hide tick labels.

### UIProgressBar (determinate)
```html
<div id="my-progress" class="ui-progress-bar" style="width: 200px;">
  <div class="title">Processing...</div>
  <div class="ui-progress-container">
    <div class="ui-progress">0</div>
  </div>
</div>
```

### UIProgressBar (indeterminate)
```html
<div class="ui-progress-bar indeterminate" style="width: 200px;">
  <div class="title">Please wait...</div>
  <div class="ui-progress-container">
    <div class="ui-progress"></div>
  </div>
</div>
```

### UIMenu (OS bar menu, in UIWindow)
```html
<div class="ui-menus">
  <div class="ui-menu" style="width: 140px;">
    <select name="file-menu">
      <option>File</option>
      <option onclick="$(this.controller).save();">Save</option>
      <option class="group"></option>
      <option onclick="$(this.controller).cancel();">Cancel</option>
    </select>
  </div>
</div>
```

### Layout helpers
```html
<div class="hbox gap-10">...</div>     <!-- horizontal flex, 10px gap -->
<div class="vbox gap-10">...</div>     <!-- vertical flex, 10px gap -->
<div class="hbox align-center">...</div>
<div class="container vbox gap-20" style="height: 400px;">...</div>

<!-- group: no padding, 1px dividers between children -->
<div class="container group">...</div>
```

### Window chrome
```html
<div class="top">
  <div class="close-button"></div>         <!-- adds × button -->
  <div class="title"><span>Title</span></div>
  <div class="zoom-button"></div>          <!-- adds fullscreen button -->
</div>
```

---

## 10. UI Components — JavaScript Access

Always interact with UI components via their class APIs, not direct DOM manipulation.

### UIListBox

```javascript
// Get the UIListBox instance
const listBox = view.ui.select("my-list").ui;

// Set up delegate BEFORE loading data (critical for first-select callback)
listBox.delegate = {
  didSelectListBoxOption: function(option) {
    console.log(option.value);
  },
  didDeselectListBoxOption: function(option) { },
  didRemoveAllOptions: function() { }
};

// Populate
listBox.addNewOptions([{ id: "1", name: "Option 1" }, { id: "2", name: "Option 2" }]);

// Query
const opt = listBox.selectedOption();   // HTMLOptionElement | null
const val = listBox.selectedValue();    // string | null

// Navigate
listBox.selectValue("2");
listBox.selectOption(0);  // by index

// Disable/enable
listBox.setDefaultAction(fn);  // called on double-click (single-select only)
```

### UIPopupMenu

```javascript
const menu = view.ui.select("status").ui;

// Populate
menu.addNewOptions([{ id: "active", name: "Active" }, { id: "inactive", name: "Inactive" }]);

// Query
const opt = menu.selectedOption();    // HTMLOptionElement | null
const val = menu.selectedValue();     // string | null

// Navigate
menu.selectValue("active");
menu.selectOption(1);

// Enable/disable the whole menu
menu.enable();
menu.disable();
```

### UITabs

```javascript
const tabs = view.ui.select("my-tabs").ui;

tabs.delegate = {
  didSelectTab: function(option) { console.log(option.value); },
  didCloseTab: function(option) { }
};

tabs.addOption(new UITabChoice("tab-id", "Tab Label"));
tabs.selectTab("tab-id");
tabs.removeTab("tab-id");
tabs.removeTabIndex(0);
const opt = tabs.selectedTab();     // HTMLOptionElement | null
const val = tabs.selectedValue();   // any | null
```

### UIProgressBar

```javascript
const bar = document.getElementById("my-progress").ui;
bar.setProgress(50, "50%");   // amount (0-100), optional display value
```

### UIMenu (in UIWindow's OS bar)

```javascript
const fileMenu = view.ui.menu("file-menu");
fileMenu.addOption({ id: "new-item", name: "New Item" });
fileMenu.removeOption("new-item");
fileMenu.enableOption("new-item");
fileMenu.disableOption("new-item");
```

---

## 11. OS APIs

Always read the JSDoc in the respective `.js` file before using any function.

### `os` — OS-level operations

```javascript
os.ui.close()                         // Close the current app
os.ui.focusWindow(container)          // Focus a window
os.ui.makeController("Name")          // Create a controller (does not show it)
os.ui.showAlert("Message")            // Show an alert modal
os.ui.showError("Error message")      // Show an error modal
await os.ui.showInfo("Info message")  // Show info modal; awaitable until dismissed
os.ui.showDelete("Are you sure?", cancelFn, okFn)  // Confirmation delete modal
os.ui.showProgressBar("Title", stopFn, indeterminate)  // Progress bar modal
os.ui.showBusy()                      // Show spinner
os.ui.hideBusy()                      // Hide spinner
os.ui.showImageViewer([url1, url2])   // Open image viewer

os.switchApplication("io.bithead.my-app")  // Switch to another app
os.openDeepLink("settings://friends")      // Open a deep link
os.getLaunchUrl("io.bithead.my-app")       // Get the launch URL for an app
os.isSuperUser(user)                        // Boolean: is current user a super user?
os.isGuestUser(user)                        // Boolean: is current user a guest?
```

### `os.network` — Network calls

All network functions are async. Always `await` them unless fire-and-forget is intentional.

```javascript
// GET with JSON response
const result = await os.network.get("/api/items");
if (result.error) { os.ui.showError(result.error); return; }
const items = result.value;

// POST with JSON body
const result = await os.network.post("/api/item", { name, status });

// DELETE
const result = await os.network._delete("/api/item", { id });

// PATCH
const result = await os.network.patch("/api/item", { id, name });

// File upload
const result = await os.network.upload("/api/upload", formData);

// Load external CSS/JS into the page (loaded only once)
await os.network.stylesheet("$(app.resourcePath)/my-styles.css");
await os.network.javascript("$(app.resourcePath)/my-script.js");

// Redirect
os.network.redirect("/login", "/return-to");
```

### `os.notification` — Sending OS events

```javascript
// Send an event to registered listeners within the OS
os.notification.sendAppNotification("io.bithead.my-app.some-event", { key: "value" });
```

---

## 12. Notifications and Events

BOSS has two concepts:
- **Notification**: Temporary message displayed to the user immediately (like a push notification banner)
- **Event**: Opaque payload sent from backend to frontend; consumed by a controller to update state

### Receiving events in a controller or application

```javascript
this.events = {
  "io.bithead.my-app.item-updated": async function(ev) {
    // ev.data is an Object<String, String>
    console.log(ev.data);
    // Re-load data, update UI, etc.
  }
};
```

### Sending events from the backend (Python)

```python
from lib.server import send_events, send_notifications

@router.post("/flip-switch")
@require_user()
async def flip_switch(boss_user: User, request: Request):
    friend_ids = [...]
    event_data = { "userId": str(boss_user.userId), "state": "on" }

    # Send event (updates app UI in real-time)
    send_events(request, "io.bithead.my-app.switch", data=event_data, user_ids=friend_ids)

    # Send notification (shows banner to user)
    send_notifications(request, user_ids=friend_ids, title="Switch", body="The switch was flipped")
```

---

## 13. Backend — Swift Web Layer

The Swift+Vapor web layer lives in `/server/web/Sources/App/Routes/`.

### Route file pattern

```swift
// Routes/<Feature>/<Feature>Route.swift
import Vapor

struct MyFeatureRoute {
    func boot(routes: RoutesBuilder) throws {
        let r = routes.grouped("my-feature")
        r.get("items", use: getItems).addScope(.user)
        r.post("item", use: saveItem).addScope(.user)
        r.delete("item", ":itemId", use: deleteItem).addScope(.user)
    }

    func getItems(req: Request) async throws -> [MyFeatureFragment.List.Item] {
        let _ = try req.authUser
        return try await MyFeatureAPI.getItems(req.db)
    }

    func saveItem(req: Request) async throws -> Fragment.OK {
        let _ = try req.authUser
        let form = try req.content.decode(MyFeatureForm.Item.self)
        if let id = form.itemId {
            try await MyFeatureAPI.updateItem(req.db, id: id, name: form.name)
        } else {
            try await MyFeatureAPI.createItem(req.db, name: form.name)
        }
        return Fragment.OK()
    }

    func deleteItem(req: Request) async throws -> Fragment.OK {
        let _ = try req.authUser
        let id = try req.parameters.require("itemId", as: Int.self)
        try await MyFeatureAPI.deleteItem(req.db, id: id)
        return Fragment.OK()
    }
}
```

### Forms and Fragments

```swift
// Routes/<Feature>/<Feature>+Forms.swift
enum MyFeatureForm {
    struct Item: Content {
        let itemId: Int?
        let name: String
    }
}

// Routes/<Feature>/<Feature>+Fragments.swift
enum MyFeatureFragment {
    enum List {
        struct Item: Content {
            let id: Int
            let name: String
        }
        typealias Items = [Item]
    }
    struct Item: Content {
        let id: Int
        let name: String
        let status: String
    }
}
```

**Rules:**
- Auth check: `let _ = try req.authUser` (or `let authUser = try req.authUser` if needed)
- Empty response: `return Fragment.OK()` — **not** `Response(status: .ok)` (causes JSON parse error)
- All routes require `.addScope(.user)` after the handler
- Use path params for IDs: `GET /my-feature/items/:companyId`
- Path param extraction: `let id = try req.parameters.require("companyId", as: Int.self)`
- Route naming: single `POST` for create and update — route decides based on null ID
- List fragments use lightweight `id` + `name` structs; detail fragments use all fields
- Do not suffix fragment names with `Detail` (e.g. `MyFragment.Item` not `MyFragment.ItemDetail`)
- POST payload: include only editable fields — omit read-only display fields
- Always include the model's own ID in the payload (`null` when creating)
- `save()` always posts to the same endpoint — never branch on ID to choose a different URL
- Validation logic belongs in `XxxService`, not routes or API layer

---

## 14. Backend — Swift Private API (bosslib)

The Swift private API lives in `/server/bosslib/Sources/bosslib/`.

### Architecture — 3-file pattern per domain

| File | Purpose |
|---|---|
| `xxx+api.swift` | `XxxProvider` protocol (interface) + `XxxAPI` final public class (no logic, delegates to provider) |
| `xxx+service.swift` | `XxxService` struct implementing `XxxProvider`; all business logic lives here |
| `xxx+errors.swift` | Domain-specific `BOSSError` subclasses |

Registration on `api`:
```swift
public nonisolated(unsafe) internal(set) static var lean = LeanAPI(provider: LeanService())
```

### Implementation discipline
- Write **only** the logic needed to pass the current test. No speculative code.
- Stub unimplemented DB paths with `fatalError("not implemented")` until a test drives them.
- Never put business logic in `XxxAPI` — it belongs in `XxxService`.

### Validation errors
- **Required field** (nil, empty string, whitespace-only): `throw api.error.RequiredParameter("fieldName")`
- **Invalid value** (wrong format, out-of-range, etc.): `throw api.error.InvalidParameter(name: "fieldName")`
- Do **not** define a custom `BOSSError` subclass when `RequiredParameter` or `InvalidParameter` covers the case.
- Custom `BOSSError` subclasses (in `xxx+errors.swift`) are only for domain-specific conditions — e.g. `FriendIsSelf`, `AlreadyFriends`.

### Validation pattern in service
```swift
guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
    throw api.error.RequiredParameter("name")
}
```

### Provider protocol signature
Accept `String?` (not `String`) in the provider protocol when the caller may pass nil — validation happens inside the service.

### DB insert pattern
```swift
let rows = try await conn.sql().insert(into: "table_name")
    .columns("id", "col1", "col2")
    .values(SQLLiteral.null, SQLBind(value1), SQLBind(value2))
    .returning("id")
    .all()
let id = try rows[0].decode(column: "id", as: ModelType.ID.self)
```
- Always use `SQLLiteral.null` for the auto-increment `id` column.
- Always use `.returning("id").all()` to retrieve the inserted row's ID.
- Decode the returned ID immediately; do not re-query the database.

### DB select (list query) pattern
```swift
let rows = try await conn.select()
    .column("*")
    .from("table_name")
    .where("foreign_key_col", .equal, someId)
    .all()
return try rows.map { row in
    ModelType(
        id: try row.decode(column: "id", as: ModelType.ID.self),
        name: try row.decode(column: "name", as: String.self)
    )
}
```
- Use `conn.select()` (shorthand), not `conn.sql().select()`.
- Name list query functions with the **plural model name**: `companies(user:)`, `factories(companyId:)` — not `getCompanies` or `listCompanies`.

### DB update pattern
```swift
try await conn.sql().update("table_name")
    .set("column_name", to: SQLBind(value))
    .where("id", .equal, SQLBind(id))
    .run()
```
- Use `conn.sql().update(...)` (note: `sql()` is required here, unlike select).
- Use `.run()` when no return value is needed.
- Chain multiple `.set(...)` calls to update several columns at once.
- Update functions that return nothing should have a `Void` (implicit) return type — do not return `Fragment.OK()` from the service layer.

### Schema conventions
- Every FK column must have a corresponding index.
- Integer discriminators for enums: stored as `Int` raw values (e.g. `line_type`: 0=model, 1=replica, 2=subAssembly).
- Default new records to safe zero values for numeric columns (`view_x=0`, `view_y=0`, `view_locked=0`, `in_stock=0`, `reorder_point=0`).

### Returning a model from create
- Construct and return the model struct **directly from the inserted values** — do not query the DB again.
- Set all child collection properties (e.g. `intakeQueues`, `stations`, `managers`) to `[]` on creation.
- Set all optional properties (`theme`, `output`, `flowMetrics`) to `nil` on creation.

### Model hierarchy and dependent records
- Create models in dependency order: parent before child (e.g. `Company` → `Factory` → `Line`).
- When creating a child record, always use the actual ID returned from inserting the parent — never assume a hardcoded ID.
- Some models require **sibling records** on creation (additional rows in related tables inserted in the same service method). Check the app's `memory.md` for the specific sibling records required by that app's domain.

### Swift Tests (XCTest)

#### Test function setup
```swift
try await boss.start(storage: .memory)
```
This is always the first line of every test function.

#### Actors
- `superUser().user` — admin/super user
- `guestUser().user` — unauthenticated/guest user

#### Asserting errors
```swift
await XCTAssertError(
    try await api.lean.someMethod(...),
    api.error.RequiredParameter("fieldName")
)
```

#### Comment structure
```swift
// describe: [feature or model being tested]

// when: [condition]
// it: [expected outcome]
```

#### Test order
- Always test **negative/validation cases before** the happy path.
- Test `nil` before empty string; test empty string before valid values.

#### What not to assert
- Do **not** assert that a primary key `> 0` (e.g. `XCTAssertGreaterThan(model.id, 0)`). A valid ID is an assumed postcondition of a successful insert; asserting it adds noise without catching real bugs.

#### Cascade testing for dependent models
- Create parent models first and use their returned IDs for child records.
- A single test function can cover the full hierarchy (e.g. Company → Factory → Line) to avoid boilerplate setup across tests.
- Validate `model.parentId == parent.id` to confirm the FK was stored correctly.

---

## 15. Backend — Python Private Services

Private Python web services live in `/private/app/<bundle_id>/`.

### Endpoint pattern

```python
from fastapi import APIRouter, Request
from lib.model import User
from lib.server import require_user

router = APIRouter()

@router.get("/my-feature/items")
@require_user()
async def get_items(boss_user: User, request: Request):
    """ Return list of items. """
    # ... query logic
    return [{"id": 1, "name": "Item 1"}]

@router.post("/my-feature/item")
@require_user()
async def save_item(body: ItemBody, boss_user: User, request: Request):
    """ Create or update an item. """
    # ...
    return {}
```

**Rules:**
- Use `@require_user()`, with parentheses, when the request requires an authenticted `User`. Unprotected routes don't need this.
- Parameter order: endpoint params (path/body) → `boss_user: User` → `request: Request`
- Import `from lib.model import User` if not present
- Return empty `{}` or use `Fragment.OK` equivalent for empty responses

---

## 16. Coding Rules and Conventions

### Emptiness checks

**Always** use `isEmpty()` from `foundation.js`. Never use `=== null`, `=== undefined`, `length === 0`, etc.

```javascript
if (isEmpty(value)) { return; }      // ✓ correct
if (value === null) { return; }      // ✗ wrong
if (!value) { return; }              // ✗ wrong
```

### Early returns over nesting

```javascript
// ✓ correct
if (isEmpty(id)) { return; }
doSomething(id);

// ✗ wrong
if (!isEmpty(id)) {
  doSomething(id);
}
```

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

```javascript
// ✓ two params
function configure(_companyId, _factoryId) {
  companyId = _companyId;
  factoryId = _factoryId;
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

## Quick Reference

| Task | Where to look |
|---|---|
| All UI components (live examples) | `/public/boss/app/io.bithead.tutorial/controller/Example.html` |
| Application with menus | `/public/boss/app/io.bithead.boss-code/controller/Application.html` |
| OS/UI/Network API signatures | `/public/boss/foundation.js`, `os.js`, `ui.js`, `network.js` (read JSDoc) |
| app-structure.md (full spec) | `/docs/app-structure.md` |
| API overview | `/docs/api.md` |
| Coding style guide | `/docs/coding-style.md` |
| Lean app conventions (reference impl) | `/public/boss/app/io.bithead.lean/memory.md` |
| bosslib architecture and XCTest patterns | §14 of this document |
