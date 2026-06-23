# BOSS JavaScript Frontend Reference

Rules and patterns for BOSS app controller HTML files and OS APIs.

---

## 5. Controller Pattern

A controller is an HTML file at `/public/boss/app/<bundle_id>/controller/<Name>.html`.

### Window vs Modal

Controllers come in two root element variants:

| Root element | When to use |
|---|---|
| `<div class="ui-window">` | Full controller with title bar, close/zoom buttons, and optional File menu. Used for most controllers. |
| `<div class="ui-modal">` | Lightweight overlay with no title bar chrome. Use for simple confirmation or single-field prompts that are triggered from within another controller (e.g. "Create line", "Clear hold"). |

A `ui-modal` uses a plain `<div class="title">` instead of the `<div class="top">` bar:

```html
<div class="ui-modal">
  <script type="text/javascript">
    function $(this.id)(view) {
      // ...
    }
  </script>
  <div class="title">Modal title</div>
  <div class="container vbox gap-20" style="width: 360px;">
    <!-- fields -->
    <div class="controls">
      <button class="primary" onclick="$(this.controller).cancel();">Cancel</button>
      <button class="default" onclick="$(this.controller).save();">Save</button>
    </div>
  </div>
</div>
```

Register `ui-modal` controllers in `application.json` with `"modal": true`:

```json
"MyModal": { "modal": true }
```

---

### Window width

Set the controller width on `div.container`, not on `div.ui-window`:

```html
<div class="ui-window">
  ...
  <div class="container vbox gap-10" style="width: 480px;">
```

The container's content is what stretches the window chrome — the chrome wraps the container, not the other way around. Never set `width` on `div.ui-window` for the purpose of sizing the window.

### Minimal skeleton

> For a complete CRUD controller (save + delete + cancel + delegate), see [Model controller — full CRUD skeleton](#model-controller--full-crud-skeleton).

```html
<div class="ui-window">
  <script type="text/javascript">
    function $(this.id)(view) {

      // --- Private state ---
      let itemId = null;

      // --- Private helpers ---
      // Declare private helpers *before* public controller functions.

      function formatName(n) {
        return n.trim();
      }

      // --- Controller functions ---

      async function save() {
        const name = formatName(view.ui.inputValue("name", "Please provide a name."));
        try {
          await os.network.post("/my-app/item", { itemId, name });
        }
        catch {
          os.ui.showError("Failed to save. Please try again later.");
          return;
        }
        view.ui.close();
      }
      this.save = save;

      function cancel() {
        view.ui.close();
      }
      this.cancel = cancel;

      // --- Configure ---

      /**
       * Configure this controller before display.
       *
       * @param {number} _itemId - ID of the item to display
       */
      function configure(_itemId) {
        itemId = _itemId;
      }
      this.configure = configure;

      // --- Lifecycle ---

      /**
       * Called before the view is rendered. Load data here.
       */
      async function viewDidLoad() {
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

      // --- OS listeners ---

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

  <div class="container vbox gap-10" style="width: 480px;">
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

### Model controller — full CRUD skeleton

Use this template when a controller edits an **existing model** (load, save, delete, cancel) and notifies a parent list controller to refresh. It combines all patterns in this section:
- [Function declaration order](#function-declaration-order)
- [Delegate pattern (`protocol`)](#delegate-pattern-protocol)
- [Control buttons (bottom of forms)](#control-buttons-bottom-of-forms) — Cancel → Delete → Save button order
- [configure method rules](#configure-method-rules)
- [Lifecycle events](#lifecycle-event-order) — `viewDidLoad` loads data, `viewDidAppear` sets focus
- [File menu accessibility](#file-menu-accessibility) — Save / Delete / Cancel mirrored in the File menu

```html
<div class="ui-window">
  <script type="text/javascript">
    function $(this.id)(view) {
      let itemId = null;

      // --- Delegate ---

      // MyItemDelegate
      let delegate = protocol(
        "MyItemDelegate", this, "delegate",
        [
          "didSaveMyItem",
          "didDeleteMyItem"
        ]
      );

      // --- Controller functions ---

      async function save() {
        const name = view.ui.inputValue("name", "Please provide a name.");
        try {
          if (itemId) {
            await os.network.put(`/my-app/item/${itemId}`, { name });
          } else {
            await os.network.post("/my-app/item", { name });
          }
        }
        catch {
          os.ui.showError("Failed to save. Please try again later.");
          return;
        }
        delegate.didSaveMyItem();
        view.ui.close();
      }
      this.save = save;

      function _delete() {
        os.ui.showDelete("Are you sure you want to delete this item?", null, async function() {
          try {
            await os.network.delete(`/my-app/item/${itemId}`);
          }
          catch {
            os.ui.showError("Failed to delete. Please try again later.");
            return;
          }
          delegate.didDeleteMyItem();
          view.ui.close();
        });
      }
      this.delete = _delete;

      function cancel() {
        view.ui.close();
      }
      this.cancel = cancel;

      // --- Configure ---

      /**
       * @param {number|null} _itemId - ID of the item to edit, or null to create
       */
      function configure(_itemId) {
        itemId = _itemId;
      }
      this.configure = configure;

      // --- Lifecycle ---

      async function viewDidLoad() {
        if (isEmpty(itemId)) { return; }
        let response;
        try {
          response = await os.network.get(`/my-app/item/${itemId}`);
        }
        catch {
          os.ui.showError("Failed to load item. Please try again later.");
          return;
        }
        view.ui.input("name").value = response.name;
      }
      this.viewDidLoad = viewDidLoad;

      function viewDidAppear() {
        view.ui.input("name").focus();
      }
      this.viewDidAppear = viewDidAppear;

      // --- OS listeners ---

      this.didHitEnter = save;
    }
  </script>

  <!-- File menu: mirrors Save / Delete / Cancel for keyboard accessibility. See §16 "File menu accessibility". -->
  <div class="ui-menus">
    <div class="ui-menu" style="width: 140px;">
      <select name="file-menu">
        <option>File</option>
        <option onclick="$(this.controller).save();">Save</option>
        <option onclick="$(this.controller).delete();">Delete</option>
        <option onclick="$(this.controller).cancel();">Cancel</option>
      </select>
    </div>
  </div>

  <div class="top">
    <div class="close-button"></div>
    <div class="title"><span>My Item</span></div>
    <div class="zoom-button"></div>
  </div>
  <div class="container vbox gap-10" style="width: 420px">
    <div class="text-field">
      <label for="name">Name</label>
      <input type="text" name="name" autocomplete="new-password">
    </div>
    <!-- Cancel → Delete → Save. See §9 "Control buttons". -->
    <div class="controls">
      <button class="primary" onclick="$(this.controller).cancel();">Cancel</button>
      <button class="primary" onclick="$(this.controller).delete();">Delete</button>
      <button class="default" onclick="$(this.controller).save();">Save</button>
    </div>
  </div>
</div>
```

The list controller that opens this model controller uses a shared delegate object (see [Shared delegate object](#shared-delegate-object)):

```javascript
// MyItemDelegate
let itemDelegate = {
  didSaveMyItem: loadItems,
  didDeleteMyItem: loadItems
};

async function addItem() {
  const win = await $(app.controller).loadController("MyItem");
  win.ui.show(function(ctrl) {
    ctrl.delegate = itemDelegate;
  });
}

async function editItem() {
  const value = view.ui.select("items").ui.selectedValue();
  if (isEmpty(value)) { return; }
  const win = await $(app.controller).loadController("MyItem");
  win.ui.show(function(ctrl) {
    ctrl.configure(parseInt(value));
    ctrl.delegate = itemDelegate;
  });
}
```

### `set` vs `add` naming convention

In BOSS UI component APIs, `set` and `add` have distinct semantics:

- **`set`** — replaces all existing content. Clears the current state before applying the new value(s). Use when the caller owns the full desired state.
- **`add`** — appends to the existing content without clearing. Use when the caller is extending the current state incrementally.

Examples: `setTokens` clears all pills then adds the new set; a hypothetical `addToken` would append a single token to the existing ones.

Follow this convention for any new public API added to a UI component.

### UI component declaration order

Functions and variables inside a UI component (e.g. `UITokenMenu`, `UISearchMenu`) must be declared in this order:

1. **Private constants** — `const` values set once at construction (e.g. `DEBOUNCE_DELAY`)
2. **Private vars** — `let` mutable state
3. **`protocol`** — delegate declaration
4. **Public API** — functions and values exposed via `this.xxx = ...`
5. **`// Private API`** comment, followed by private helper functions

Only the `// Private API` comment is needed — everything before it (protocol, public API) is implicitly public. Do **not** add a `// Public API` comment.

```javascript
function UIMyComponent(containerEl, select) {

    // private constants
    const DEBOUNCE_DELAY = 333;

    // private vars
    let cachedOptions = [];

    // protocol
    let delegate = protocol("UIMyComponentDelegate", this, "delegate", [...]);

    // public API
    function setValue(v) { ... }
    this.setValue = setValue;

    // Private API

    function renderOptions(options) { ... }
}
```

### Function declaration order

Functions inside a controller must be declared in this order:

1. **Controller functions** — business logic (`save`, `delete`, `cancel`, etc.), excluding `configure`
2. **`configure`** — assigns passed values to private variables; no DOM access
3. **Lifecycle events** — `viewDidLoad`, `viewDidAppear`, `viewWillUnload`, etc.
4. **OS listeners** — `didHitEnter`, `didHitKey`, `events`, `userDidSignIn`, `userDidSignOut`

### Lifecycle event order

```
configure(...)       ← Called by the opener before show()
viewDidLoad          ← Before rendered; load data here
viewDidAppear        ← After visible; set focus here
  [user interaction]
viewWillUnload       ← Before close; clean up here
```

> Load data from the server in `viewDidLoad`, **not** `configure` — the view is not yet in the DOM during `configure`.

> **Form init — single route:** When a form needs multiple pieces of read-only data to pre-populate (e.g. the name of a related entity, the current user, a company id), define a dedicated `GET /<feature>/create-<entity>/:id` route and a matching `<FeatureFragment>.Create<Entity>` response struct. Call this single route in `viewDidLoad` instead of making multiple network calls. The route name mirrors the controller name (`CreateWorkUnit` ↔ `GET /lean/create-work-unit/:id`). This keeps `configure()` minimal (only the id the controller actually owns) and makes the init path easy to follow.
>
> Example: `GET /lean/create-work-unit/:intakeQueueId` → `LeanFragment.CreateWorkUnit { intakeQueueName, companyId, operator }`.

### Loading and showing a controller

Always use `async/await` when calling `loadController`. Never use `.then()`.

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

### Delegate pattern (`protocol`)

Controllers that expose a callback interface declare a **delegate** using the `protocol()` function from `foundation.js`. This validates that the caller only provides methods the protocol knows about, avoids `null`-checking in call sites, and removes all boilerplate.

```javascript
function $(this.id)(view) {

  // Declare delegate as a private variable — never assign `let self = this`.
  // Methods listed as plain strings are optional by default.
  let delegate = protocol(
    "MyControllerDelegate", this, "delegate",
    [
      "didSelectItem",   // optional
      "didCancel"        // optional
    ]
  );

  function select(item) {
    delegate.didSelectItem(item);   // safe to call even if not implemented
    view.ui.close();
  }
  this.select = select;
}
```

Calling controller wires up the delegate after `show()`:

```javascript
win.ui.show(function(ctrl) {
  ctrl.delegate = {
    didSelectItem: function(item) {
      console.log("Selected:", item);
    }
  };
});
```

When the controller also requires `configure()`, call both inside the same `show()` callback — `configure()` first, then assign the delegate:

```javascript
const win = await $(app.controller).loadController("Company");
win.ui.show(function(ctrl) {
  ctrl.configure(companyId);        // set state first
  ctrl.delegate = companyDelegate;
});
```

When opening a controller for **creating** a new record (no ID to configure), still assign the delegate:

```javascript
const win = await $(app.controller).loadController("Company");
win.ui.show(function(ctrl) {
  ctrl.delegate = companyDelegate;
});
```

#### Shared delegate object

When the same delegate logic is used in more than one `show()` call within the same controller, extract it into a **private `let`** at the top of the controller function. Add the protocol name as a comment on the line above.

```javascript
function %(leanCompanies)(view) {

  // CompanyDelegate
  let companyDelegate = {
    didSaveCompany: loadCompanies,
    didDeleteCompany: loadCompanies
  };

  async function addCompany() {
    const win = await $(app.controller).loadController("Company");
    win.ui.show(function(ctrl) {
      ctrl.delegate = companyDelegate;
    });
  }

  async function editCompany() {
    ...
    win.ui.show(function(ctrl) {
      ctrl.configure(parseInt(value));
      ctrl.delegate = companyDelegate;
    });
  }
}
```

- Reference functions directly by name (e.g. `didSaveCompany: loadCompanies`) rather than wrapping in an anonymous function (`didSaveCompany: function() { loadCompanies(); }`) when the callback has no extra arguments or logic.
- Place the shared delegate object **before** the first function that uses it.

#### Delegate with a reload function

When a parent controller needs to reload its data after a child controller saves, extract the load logic into a private function and reference it in the delegate. Do **not** inline a `network.get` call inside the delegate object.

```javascript
// ✓ correct — extracted load function
async function loadItems() {
  let response = await os.network.get("/my-feature/items");
  view.ui.select("items").ui.addNewOptions(response.items);
}

// MyItemDelegate
let itemDelegate = {
  didSaveItem: loadItems
};
```

#### Inline delegate for one-off cases

When a delegate is only set in a single place and the callback is one operation, an inline object is acceptable — no need to extract a shared `let`:

```javascript
win.ui.show(function(ctrl) {
  ctrl.configure(child.id);
  ctrl.delegate = { didSaveItem: loadItems };
});
```

Rules:
- `protocol()` is always a **private `let`** — never `this.delegate` directly
- Never assign `let self = this`; the `protocol()` setter handles the indirection
- Only list methods the protocol actually defines; assigning an unknown method throws at runtime
- Mark a method **required** by passing a `DelegateMethod` object instead of a plain string: `DelegateMethod("didSelectItem", true)`
- Only add `async` to a function when it contains an `await` expression
- Always fire the delegate **before** `view.ui.close()` — the delegate handler runs synchronously before the window closes
- Name delegate methods after the event, not the action: `didSaveCompany` not `saveCompany`; `didDeleteCompany` not `deleteCompany`

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
  <div class="ui-controller" name="splash">
    <script type="text/javascript">
      function %(splash)(view) {
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
- Every embedded controller **must** have a `name` attribute (no kebab-case; use camelCase)
- The root function declaration **must** wrap the name in `%(name)` — e.g. `function %(splash)(view)`. This is the template command syntax; the OS resolves it to the controller name at parse time
- Use `%(controllerName)` in HTML `onclick` handlers to reference the controller instance at runtime (expands to `os.ui.controller.controllerName`)
- Embedded controllers receive lifecycle events
- Embedded controllers may only be nested **one level deep**

### Shared Embedded Controllers

An embedded controller defined in `Application.html` can be reused across all controllers within the same app. Define the shared embedded controller as a `<template>` element in `Application.html`, then reference it in any controller using the `EmbedController(Name)` marker. The marker is replaced with the template's innerHTML before the controller is rendered.

**`Application.html`** — declare each shared controller inside a `<template>`:

```html
<template id="ColorPicker">
  <div class="ui-controller" name="colorPicker">
    <script type="text/javascript">
      function colorPicker(view) {
        function color() {
          return { fill: view.ui.input("color-fill").value, border: view.ui.input("color-border").value };
        }
        this.color = color;
      }
    </script>
    <div class="text-field"><label>Fill</label><input type="text" name="color-fill"></div>
    <div class="text-field"><label>Border</label><input type="text" name="color-border"></div>
  </div>
</template>
```

**Any controller** — place the marker where the shared controller should be injected:

```html
<div class="container vbox gap-10">
  EmbedController(ColorPicker)
  <div class="controls">
    <button class="primary" onclick="$(this.controller).save();">Save</button>
  </div>
</div>
```

Rules:
- The `<template id="Name">` in `Application.html` is the source of truth; `EmbedController(Name)` references it by that `id`
- The same shared embedded controller may only be injected **once per controller**
- Injection happens before interpolation, so `$(app)` inside a shared controller resolves correctly
- **The `%()` reference name is the `name` attribute on the `div.ui-controller` inside the template — not the template's `id`.** These are often different. For example, `<template id="ThemeController">` contains `<div class="ui-controller" name="theme">`, so the JS reference is `%(theme)`, not `%(ThemeController)`. Always check the template's inner `div` to find the correct name.

### Wiring an embedded controller from a parent

Embedded controllers are rendered as part of the parent's DOM, so their lifecycle mirrors the parent's. The parent's `viewDidLoad` runs first; the embedded controller's `viewDidLoad` runs after. This means:

- Wire `%(embedded).configure()` and `%(embedded).delegate` from the **parent's `viewDidLoad`** — the embedded controller's DOM exists by that point.
- Never wire them from the parent's `configure` — neither the parent's nor the embedded controller's DOM exists yet at that stage.

```javascript
async function viewDidLoad() {
  // ... populate other fields from response ...

  %(theme).configure(response.theme);  // pass server value directly — no transformation needed
  %(theme).delegate = {
    didSelectTheme: function(_theme) {
      theme = _theme;  // capture changes back into parent's local state
    }
  };
}
```

The embedded controller name (`theme`) is the `name` attribute on its `div.ui-controller`.

### Embedded controller `configure()` null guard

When the embedded controller's model field is optional, guard against `null` and return early to preserve the controller's default pre-configured state:

```javascript
function configure(_theme) {
  if (isEmpty(_theme)) { return; }  // keep default — do not overwrite with null
  theme = _theme;
  setTheme();
}
```

---

## 8. Element Accessor APIs

Both `UIWindow` (via `view.ui`) and `_UIController` (via `view.ui` on embedded controllers) expose these element accessors. All return `HTMLElement|null`.

> **Rule:** Always use these accessors to query named elements on the view. Never use `container.querySelector` or `document.querySelector` directly when an accessor is available.
>
> This applies even to dynamically-created elements (e.g. in `renderComment`). Assign a `name` that incorporates the record's ID so the accessor can target it unambiguously. For example, a textarea for comment 3 gets `name="comment-text-3"` and is accessed via `view.ui.textarea("comment-text-3")`.

```javascript
view.ui.button("name")          // <button name="name">
view.ui.details("name")         // <details name="name">
view.ui.div("name")             // <div name="name">
view.ui.divByClassName("name")  // <div class="name">
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

**Note on checkboxes:** Checkboxes (`<input type="checkbox">`) are accessed via `view.ui.input(name)`. There is no separate `checkbox()` method. Use `.checked` to read or write the checked state.

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

Use `div.read-only` to display a label alongside a read-only value (e.g. an ID, a name fetched from the server, or a computed reference). Do **not** use `<input readonly>` for this pattern.

```html
<div class="read-only">
  <label>Owner</label>
  <span name="owner-name"></span>
</div>
```
Populate in `viewDidLoad`: `view.ui.span("owner-name").textContent = value;`

The `<label>` text is the human-readable field name. The `<span name="...">` holds the value and is queried via `view.ui.span(name)`.

### Hidden field (for IDs)
```html
<input type="hidden" name="id">
```

### Control buttons (bottom of forms)

The `div.controls` block must always be the **last element** inside the form container. No fields, fieldsets, or tables may appear after it.
```html
<div class="controls">
  <!-- Order: secondary → primary → default. Only one default allowed. -->
  <button class="secondary" onclick="$(this.controller).doSecondary();">Secondary</button>
  <button class="primary"   onclick="$(this.controller).cancel();">Cancel</button>
  <button class="default"   onclick="$(this.controller).save();">Save</button>
</div>
```

When a form supports deleting the model, the button order is always: **Cancel → Delete → Save**. `Delete` uses the `primary` class.

```html
<div class="controls">
  <button class="primary" onclick="$(this.controller).cancel();">Cancel</button>
  <button class="primary" onclick="$(this.controller).delete();">Delete</button>
  <button class="default" onclick="$(this.controller).save();">Save</button>
</div>
```

The delete function is always named `_delete` privately and exposed as `this.delete = _delete`, so callers invoke `$(this.controller).delete()`. It fires the delegate **before** closing (see [Delegate pattern](#delegate-pattern-protocol)).

```javascript
function _delete() {
  os.ui.showDelete("Are you sure?", null, async function() {
    try {
      await os.network.delete(`/my-app/item/${itemId}`);
    }
    catch {
      os.ui.showError("Failed to delete. Please try again later.");
      return;
    }
    delegate.didDeleteMyItem();
    view.ui.close();
  });
}
this.delete = _delete;
```

### List-model window pattern

Use this layout whenever a window displays a list of models and provides actions on them. The list sits on the left; model-agnostic actions (e.g. "Add") go at the top-right, and model-specific actions (e.g. "Edit", "Open") go at the bottom-right in a `separated` group. Model-specific buttons start `disabled` and are enabled only when a row is selected.

```html
<div class="container vbox gap-10" style="width: 420px">
  <div class="hbox gap-10">
    <div class="ui-list-box" style="width: 300px; height: 220px;">
      <select name="items"></select>
    </div>
    <div class="controls-right separated">
      <!-- Top group: actions that do not require a selection -->
      <div class="vbox gap-10">
        <button class="primary" onclick="$(this.controller).add();">Add</button>
      </div>
      <!-- Bottom group: actions that require a selection -->
      <div class="vbox gap-10">
        <button name="edit" class="primary" disabled onclick="$(this.controller).edit();">Edit</button>
        <button name="open" class="default" disabled onclick="$(this.controller).open();">Open</button>
      </div>
    </div>
  </div>
</div>
```

Wire the list box delegate in `viewDidLoad` to enable/disable the selection-dependent buttons:

```javascript
function viewDidLoad() {
  view.ui.select("items").ui.delegate = {
    didSelectListBoxOption: function(opt) {
      view.ui.button("edit").disabled = false;
      view.ui.button("open").disabled = false;
    },
    didRemoveAllOptions: function() {
      view.ui.button("edit").disabled = true;
      view.ui.button("open").disabled = true;
    }
  };
}
```

Rules:
- Omit the top `<div class="vbox gap-10">` (and its buttons) if there are no model-agnostic actions; in that case also drop `separated` from `controls-right` and place the model-specific buttons directly inside — they will flex to the bottom automatically
- Omit the bottom group if every action requires no selection
- The `separated` class on `controls-right` creates a visual divider between the two groups; omit it when there is only one group
- Model-specific buttons (`Open`, `Edit`, etc.) are always `disabled` by default. The list box delegate is responsible for enabling them.
- Use `hasSelectedOption()` on both `didSelectListBoxOption` and `didDeselectListBoxOption` to toggle button state.
- A **Remove** button paired with a list box must be disabled when the list is empty — both on initial load and after every removal. If a `refreshList` private function manages the list contents, set `button.disabled = items.length === 0` at the end of that function. Also implement `didRemoveAllOptions` in the list box delegate to disable the button when `removeAllOptions` is called externally.

### Error / info messages
```html
<div class="error-message">This is an error message.</div>
<div class="info-message">This is an informational message.</div>
```

### Accordion (`ui-accordion`)

Use `<details class="ui-accordion">` to group a collapsible section. The `<summary>` is the clickable header. Use the `open` attribute to start expanded, or `closed` to start collapsed.

```html
<details class="ui-accordion" open>
  <summary>Section Title</summary>
  <!-- content -->
</details>
```

**Initial state rules:**
- Default to `open` for primary content (e.g. a list of items the user is expected to interact with).
- Default to `closed` for optional or secondary content (e.g. metrics, notification triggers).
- When an accordion starts `closed` and its content is data-driven, open it programmatically in `viewDidLoad` if the server returns data. Never open it in response to delegate callbacks (e.g. after save/delete) — those only refresh list content.

```javascript
// In viewDidLoad only:
if (response.fields.length > 0) {
  view.ui.details("fields-accordion").open = true;
}
```

For read-only metrics or any large set of key/value pairs, render the content as a two-column `<table>` with `<th>` (label) on the left and `<td>` (value) on the right. Always start the accordion `closed` for optional/secondary information:

```html
<details class="ui-accordion" closed>
  <summary>Metrics</summary>
  <div name="metrics-none" class="info-message">No metrics computed.</div>
  <div name="metrics" style="display: none;">
    <table>
      <tr><th>Lead time</th><td><span name="metrics-lead-time"></span></td></tr>
      <tr><th>Value</th><td><span name="metrics-value"></span></td></tr>
    </table>
  </div>
</details>
```

Toggle the `metrics-none` / `metrics` divs in `viewDidLoad` based on whether the server returned a metrics object. Never use `*FlowMetrics` fields in save payloads — they are server-computed and read-only.

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
`buttons` mode treats each option as a clickable button. Do **not** combine `buttons` with a `multiple` select — this is unsupported.
```html
<div class="ui-list-box buttons" style="width: 200px;">
  <select name="my-buttons">
    <option value="a" onclick="$(this.controller).doA();">Action A</option>
    <option value="b" onclick="$(this.controller).doB();">Action B</option>
  </select>
</div>
```

### UIListBox — populating from server data

The backend must always return list items as `Fragment.Option` (`{ id: String, name: String }`). Pass the array directly to `addNewOptions` — never map it client-side:

```javascript
// Correct — server returns Fragment.Option[]
listBox.addNewOptions(response.items);

// Wrong — do not remap what the server already provides
listBox.addNewOptions(response.items.map(i => ({ id: i.id, name: i.name })));
```

### Fragment.Option fixtures — id must be a string

When writing a JSON fixture that is decoded as `Fragment.Option` (or `[Fragment.Option]`), the `id` field **must be a JSON string**, not a number — even when the underlying model ID is an integer.

```json
// Correct
[{ "id": "1", "name": "Assign version number" }]

// Wrong — id is a number, will fail to decode as Fragment.Option
[{ "id": 1, "name": "Assign version number" }]
```

### Fragment.Option ↔ UIChoice equivalence

Server-side `Fragment.Option` (`{ id: String, name: String }`) is structurally identical to the JS `UIChoice`. Any UI component API that accepts a `UIChoice` can receive a `Fragment.Option` directly from the server response — no wrapping in `new UIChoice(...)` needed.

```javascript
// Correct — pass the server object directly
reporterMenu.selectOption(response.reporter);

// Wrong — unnecessary wrapping
reporterMenu.selectOption(new UIChoice(response.reporter.id, response.reporter.name));
```

This applies to any API that accepts `{id, name}`: `selectOption`, `addNewOptions`, delegates that return options, etc.

**`Fragment.Option` is only for list UI** — `Fragment.Option` (`{ id, name }`) should only be used for lightweight list items (e.g. `UIListBox`, `UISearchMenu`, pop-up menus, token fields). Never use it for operator, reporter, or other rich entity fields on detail fragments. Use the corresponding domain fragment (e.g. `LeanFragment.Operator`) instead.

### No transformation of server response models

Do not reconstruct a client-side object from a server response when the shapes are identical. Pass the response object as-is — both to UI component APIs and back in the save body.

```javascript
// Correct — pass the server object directly
theme = response.theme;
%(theme).configure(theme);

// Wrong — unnecessary reconstruction
const t = response.theme;
theme = new Theme(t?.id ?? null, t?.fill ?? "white", t?.stroke ?? "black");
%(theme).configure(theme);
```

If the client and server shapes differ (different property names, missing fields, etc.) raise the discrepancy with the developer rather than silently patching it on the client.

### UIListBox — sortable mode
Items can be dragged to reorder. Add the `sortable` class.

**Multi-select drag**: if one or more options are selected and the user drags from any selected option, all selected options move together. If only one option is selected (or the dragged option is not selected), only that option moves. A drag to the same position is a no-op.

The delegate callback is `didChangePositionOfListBoxOptions(options, newPosition)` — always plural. `options` is an array of `HTMLOptionElement`. If the method returns a `Promise`, the visual move is deferred until it resolves; rejecting cancels the move.

**Return the Promise — do not `await` it.** The `UIListBox` owns the `await` and uses the result to decide whether to commit or cancel the visual move. Use `return os.network.patch(...)`, not `await os.network.patch(...)`.

**Delegate wiring rule** (applies to all delegates — see above):

```html
<div class="ui-list-box sortable" style="width: 380px; height: 200px;">
  <select name="work-units"></select>
</div>
```

```javascript
// Inline (≤ 2 operations) — return the Promise, do not await
const listBox = view.ui.select("work-units").ui;
listBox.delegate = {
  didSelectListBoxOption: function(option) { },
  didRemoveAllOptions: function() { },
  didChangePositionOfListBoxOptions: async function(options, newPosition) {
    return os.network.patch("/lean/work-unit-position", {
      position: newPosition,
      workUnitIds: options.map(function(o) { return parseInt(o.value); })
    });
  }
};
listBox.addNewOptions(response.items);

// Private function (≥ 3 operations) — return the Promise, do not await
const listBox = view.ui.select("work-units").ui;
listBox.delegate = {
  didSelectListBoxOption: function(option) { },
  didRemoveAllOptions: function() { },
  didChangePositionOfListBoxOptions: didChangePositionOfListBoxOptions
};
listBox.addNewOptions(response.items);

async function didChangePositionOfListBoxOptions(options, newPosition) {
  // multiple operations...
  return os.network.patch(...);  // return, do not await
}
this.didChangePositionOfListBoxOptions = didChangePositionOfListBoxOptions;
```

### Radio group with associated fields

When a radio option has one or more associated fields, place those fields **inside the `<fieldset>`** as siblings of the `<ul>`, not outside the fieldset. Use `style="display: none;"` (toggled by the `onchange` handler) to show/hide each field group.

```html
<fieldset class="vbox gap-10">
  <legend>Supply request</legend>
  <ul class="simple-list">
    <li><label class="radio"><input type="radio" name="supply-request-type" value="none"      onchange="$(this.controller).supplyRequestTypeChanged(this.value);" checked> None</label></li>
    <li><label class="radio"><input type="radio" name="supply-request-type" value="inventory" onchange="$(this.controller).supplyRequestTypeChanged(this.value);"> Inventory</label></li>
    <li><label class="radio"><input type="radio" name="supply-request-type" value="supply"    onchange="$(this.controller).supplyRequestTypeChanged(this.value);"> Supply</label></li>
  </ul>
  <!-- Fields for each option live INSIDE the fieldset, toggled via display:none -->
  <div name="inventory-fields" style="display: none;" class="vbox gap-10">
    <div class="ui-search-menu">
      <label for="inventory">Inventory</label>
      <select name="inventory"><option>Search inventory…</option></select>
    </div>
    <div class="text-field">
      <label for="amount">Amount</label>
      <input type="number" name="amount" min="1" value="1">
    </div>
  </div>
  <div name="supply-fields" style="display: none;" class="vbox gap-10">
    <div class="ui-search-menu">
      <label for="supply">Supply</label>
      <select name="supply"><option>Search supplies…</option></select>
    </div>
    <button class="primary" onclick="$(this.controller).addSupply();">Add supply</button>
  </div>
</fieldset>
```

Controller JavaScript:
```javascript
function supplyRequestTypeChanged(value) {
  supplyRequestType = value === "none" ? null : value;
  view.ui.div("inventory-fields").style.display = value === "inventory" ? "" : "none";
  view.ui.div("supply-fields").style.display    = value === "supply"    ? "" : "none";
}
this.supplyRequestTypeChanged = supplyRequestTypeChanged;
```

In `viewDidLoad`, restore the selected option and toggle field visibility:
```javascript
if (!isEmpty(response.supplyRequest)) {
  supplyRequestType = response.supplyRequest.type;
  view.ui.radio("supply-request-type", supplyRequestType).checked = true;
  supplyRequestTypeChanged(supplyRequestType);
}
```

### UIPopupMenu (drop-down)

Default width is `160px`. Always set `style="width: 160px;"` on new popup menus unless a different width is explicitly required.

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

### UISearchMenu

A search input backed by a `<select>`. The first `<option>` is used as the placeholder text and removed at init (avoiding index off-by-ones). Delegate methods fire on focus and on typing.

```html
<div class="ui-search-menu">
  <select name="companies">
    <option>Search companies…</option>   <!-- placeholder; removed at init -->
  </select>
</div>
```

**Delegate protocol: `UISearchMenuDelegate`**

| Method | Parameter | Returns | When called |
|---|---|---|---|
| `didFocusSearchMenu` | `initialize: bool` | `Promise<[{id,name}]\|null>` | On every focus; `initialize` is `true` the first time only |
| `didSearchForTerm` | `term: string` | `Promise<[{id,name}]>` | ~333 ms after the user stops typing (debounced) |
| `didSelectOption` | `option: HTMLOptionElement` | — | When the user picks an option from the drop-down |
| `didDeselectOption` | — | — | When the user clears the selection |

> **`didSelectOption` passes an `HTMLOptionElement`**, not a `Fragment.Option`. Use `option.value` for the ID and `option.text` for the name. To add the selection to a list, transform it: `{ id: option.value, name: option.text }`.

> **Clear after selection**: when an operator or similar item is added to a local list via `didSelectOption`, call `menu.clearSelectedValue()` immediately after so the user can search again without manual clearing.

> **`suggested-*` / `find-*` route naming**: always use the **plural** form of the model name — e.g. `suggested-operators`, not `suggested-operator`. Reuse existing routes where they exist rather than creating model-specific variants.

**`selectOption(choice)`** — programmatically set the selected value without user interaction. Accepts any `{id, name}` object (e.g., a `Fragment.Option` from the server). Does **not** fire `didSelectOption`. Updates the display and shows the clear button.

```javascript
// Populate the field from server data on load
if (!isEmpty(response.reporter)) {
  reporterMenu.selectOption(response.reporter);
}
```

**Caching rule:** if `didFocusSearchBar` resolves to `null`, the control shows the previously cached results. Return `null` on subsequent calls when the initial list does not change.

**Typing rule:** an empty search field cancels the debounce and re-renders the cached list. Use `didSearchForTerm` only for server-filtered results.

```javascript
async function viewDidLoad() {
  const searchBar = view.ui.select("companies").ui;

  // Set delegate BEFORE calling any data-loading methods
  searchBar.delegate = {
    didFocusSearchMenu: async function(initialize) {
      if (!initialize) { return null; }  // use cached results on re-focus
      return os.network.get("/lean/companies");
    },
    didSearchForTerm: async function(term) {
      return os.network.get(`/lean/companies?q=${encodeURIComponent(term)}`);
    },
    didSelectOption: function(option) {
      companyId = parseInt(option.value);
    },
    didDeselectOption: function() {
      companyId = null;
    }
  };
}
```

### UITokenMenu

A multi-token field backed by a `<select multiple>`. Each committed token is added as a pill inside the field and as a `<selected option>` in the backing `<select>`. Supports typing to search via a delegate.

```html
<div class="ui-token-menu" style="width: 300px;">
  <label for="assignees">Assignees</label>
  <select name="assignees"></select>
</div>
```

**Access:** `view.ui.select("assignees").ui`

**Delegate protocol: `UITokenMenuDelegate`**

| Method | Parameter | Returns | When called |
|---|---|---|---|
| `didFocusTokenMenu` | — | `Promise<[{id,name}]>` | Each time the input is focused; return suggested options |
| `didSearchForTerm` | `term: string` | `Promise<[{id,name}]>` | ~333 ms after the user stops typing (debounced) |
| `didAddToken` | `option: HTMLOptionElement` | `Promise` | Before a token is committed; **reject** to abort |
| `didRemoveToken` | `option: HTMLOptionElement` | `Promise` | Before a token is removed; **reject** to abort |

**Rules:**
- Set `delegate` before the control is focused (typically at the top of `viewDidLoad`).
- `didAddToken` / `didRemoveToken` are awaited; throw to prevent the change.
- Arrow keys navigate the drop-down; Enter commits the highlighted (or first) option; Escape closes without committing.
- Backspace on an empty input removes the last token.

**`setTokens(choices)`** — programmatically replace all tokens without firing delegate callbacks. Clears all existing pills and backing `<option>` elements first, then adds the new set. Accepts any array of `{id, name}` objects (e.g. `Fragment.Option[]` from the server).

```javascript
// Populate from server data on load
if (!isEmpty(response.assignees)) {
  assigneesMenu.setTokens(response.assignees);
}
```

**Auto-save pattern (full list):** when `didAddToken` and `didRemoveToken` need to persist the current set, read all selected options from the backing `<select>` and send the complete list — never a delta. This avoids ordering and race-condition issues:

```javascript
async function viewDidLoad() {
  const tokenMenu = view.ui.select("assignees").ui;

  tokenMenu.delegate = {
    didFocusTokenMenu: async function() {
      return os.network.get("/lean/suggested-operators");
    },
    didSearchForTerm: async function(term) {
      return os.network.get(`/lean/operator/${encodeURIComponent(term)}`);
    },
    didAddToken: async function(option) {
      if (isEmpty(workUnitId)) { return; }  // guard: no-op during create
      const ids = Array.from(view.ui.select("assignees").selectedOptions).map(o => parseInt(o.value));
      await os.network.put(`/lean/work-unit/assignees/${workUnitId}`, { operatorIds: ids });
    },
    didRemoveToken: async function(option) {
      if (isEmpty(workUnitId)) { return; }  // guard: no-op during create
      const ids = Array.from(view.ui.select("assignees").selectedOptions).map(o => parseInt(o.value));
      await os.network.put(`/lean/work-unit/assignees/${workUnitId}`, { operatorIds: ids });
    }
  };
}
```

**Rules:**
- Read `selectedOptions` **after** the token has been added or removed — the backing `<select>` is already updated when the delegate fires.
- Guard with `if (isEmpty(resourceId)) { return; }` so nothing is sent while a new record has not yet been created.

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

### Verify Core OS Object Shapes

Before accessing properties on `os.user`, `os.network`, or other framework globals:
- Explicitly state what shape you believe the object has.
- If the shape is not documented in `boss-reference.md` §11 (OS APIs), search the codebase for existing usage of that object before writing new code.
- Never assume nested properties (e.g., `os.user.operator.id`) exist unless you have seen them used elsewhere in the same app.

If you are uncertain about the shape, ask before writing code that depends on it.

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
os.ui.showColorPicker(fn)             // Show color picker modal; fn(hexColor) called on selection
os.ui.showEmbeddedControllers(app)    // Show list of shared embedded controllers for an app
os.ui.showEmbeddedControllerDetail(bundleId, name)  // Open live embedded controller detail window

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

// POST — create a new resource
const result = await os.network.post("/api/item", { name, status });

// PUT — full model update; ID belongs in the URL, not the body
const result = await os.network.put(`/api/item/${itemId}`, { name, status });

// PATCH — partial update (subset of fields)
const result = await os.network.patch(`/api/item/${itemId}`, { name });
```

**HTTP method semantics:**
- `POST /resource` — create a new resource. ID is absent from the URL and the body.
- `PUT /resource/:id` — replace all editable fields of an existing resource. ID goes in the URL; omit it from the body.
- `PATCH /resource/:id` — update a subset of fields. ID goes in the URL; omit it from the body.
- `DELETE /resource/:id` — delete the resource.

**Controller `save()` branching pattern** — when a controller handles both create and update, branch on the private ID variable:
```javascript
async function save() {
  const name = view.ui.inputValue("name", "Please provide a name.");
  try {
    if (itemId) {
      await os.network.put(`/my-app/item/${itemId}`, { name });
    } else {
      await os.network.post("/my-app/item", { name });
    }
  }
  catch (error) {
    os.ui.showError(error.message);
    return;
  }
  delegate.didSaveMyItem();
  view.ui.close();
}
this.save = save;
```

**Error handling rules:**
- When a network call throws (i.e. `try/catch`), display `error.message` rather than a hardcoded generic string. The server returns structured error messages that should be shown verbatim to the user. `error.message` is always present — do not use a ternary fallback.
- Once a route is fully implemented and wired up, remove any `// TODO: <METHOD> /path` comment that was marking it as pending. A TODO in a network call means the route is not yet integrated; no TODO means it is live.
- Pattern:
```javascript
try {
  response = await os.network.get(`/lean/intake-queue/${intakeQueueId}`);
}
catch (error) {
  os.ui.showError(error.message);
  return;
}
```
- `error.message` is always present on network errors — never use a ternary fallback (`error.message ?? "..."`).

```javascript
// DELETE
const result = await os.network._delete("/api/item", { id });

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

## 18. Godot Integration

BOSS can host Godot 4 web exports inside an `<iframe>`. Bi-directional communication between GDScript and JavaScript is handled through `JavaScriptBridge` (Web export only).

### Overview

```
BOSS JS (parent window)
  └── <iframe> (Godot HTML shell)
        └── Godot engine (GDScript)
```

- BOSS sets `window.boss` on the iframe's `contentWindow` **after** the iframe loads.
- GDScript reads `window.boss` to obtain the `GodotController` instance.
- GDScript overwrites `_delegate.send` with a `JavaScriptBridge` callback so BOSS can call into GDScript.
- GDScript calls `_delegate.receive(ev)` to send events up to BOSS.

---

### application.json — Godot controller config

A controller that hosts a Godot game requires a `godot` key. The controller name must not be `"Godot"` — that name is reserved by the system.

```json
"controllers": {
    "Game": {
        "godot": {
            "title": "Example game",
            "main": "Game.html"
        }
    }
}
```

- `title` — window title (falls back to `"<app name> v<version>"`)
- `main` — filename of the Godot HTML export, relative to the app bundle root

---

### BOSS controller HTML — `Godot.html`

The built-in `io.bithead.boss/controller/Godot.html` is the standard Godot host. It is used automatically by any app whose controller config has a `godot` key.

Key points:

```javascript
// Called by BOSS to inject app, config, and the GodotController instance.
function init(_app, _config, _controller) {
    app = _app;
    config = _config;
    controller = _controller;   // GodotController instance
    // Forwards optional lifecycle hooks from GodotController to this wrapper:
    self.events         = controller?.events;
    self.userDidSignIn  = controller?.userDidSignIn;
    self.userDidSignOut = controller?.userDidSignOut;
}

// Pass-thru: delegates to GodotController.configure(...args).
function configure(...args) {
    controller?.configure(...args);
}

function viewDidLoad() {
    const container = view.ui.iframe("godot-container");
    // boss MUST be set in onload — setting it before src replaces the context.
    container.onload = function() {
        container.contentWindow.boss = controller;
    };
    container.src = `/boss/app/${app.bundleId}/${config.godot.main}`;
}
```

- **Never** assign `contentWindow.boss` before setting `src`. The `about:blank` context is discarded when `src` loads; use `onload` instead.
- **Do not call `configure()` on the `Godot.html` controller directly** — use `ctrl.configure()` inside `win.ui.show()` as normal; it is automatically forwarded to `GodotController.configure()`.

---

### GodotController protocol

`GodotController` is a JS ES module export with the following interface:

| Member | Direction | Required | Description |
|--------|-----------|----------|-------------|
| `id` | — | Yes | Mutable property set by BOSS after instantiation. Use `property(this, "id", getter, setter)`. |
| `configure(...)` | BOSS → GodotController | Optional | Called from `win.ui.show(ctrl => ctrl.configure(...))` to pass app-specific data before Godot loads. |
| `ready()` | Godot → BOSS | **Required** | Called by GDScript after the bridge is established. Use to send the initial command(s) to Godot via `self.send(...)`. |
| `receive(ev)` | Godot → BOSS | **Required** | Called by GDScript to send an event to BOSS. Handle all incoming Godot events here. |
| `send(cmd)` | BOSS → Godot | Injected | Overwritten by Godot at startup with a `JavaScriptBridge` callback. Do not implement — call it. |
| `events` | — | Optional | Object mapping BOSS event names to handler functions. Forwarded to the wrapper by `Godot.html`. |

**Function declaration order:** `configure` → `ready` → `receive` — matching the order they are called by BOSS and Godot.

---

### App-side `<ControllerName>.js`

Each app that uses Godot must supply a `controller/<ControllerName>.js` file (e.g. `controller/Game.js` for a controller named `"Game"` in `application.json`). The file exports a `GodotController` function.

```javascript
// public/boss/app/<bundleId>/controller/Game.js
export function GodotController(app) {
    let id;
    property(this, "id",
        function () { return id; },
        function (_id) { id = _id; }
    );

    const self = this;

    // Store any values passed via ctrl.configure() in win.ui.show().
    let factoryId;

    /**
     * Called from Application.html via win.ui.show(ctrl => ctrl.configure(factoryId)).
     * Runs before the Godot iframe loads.
     */
    function configure(_factoryId) {
        factoryId = _factoryId;
    }
    this.configure = configure;

    /**
     * Called by GDScript after the bridge is established.
     * This is the correct place to send the first command into Godot.
     */
    function ready() {
        self.send({ name: "configure", data: { factoryId: String(factoryId) } });
    }
    this.ready = ready;

    /**
     * Called when Godot sends an event to BOSS.
     *
     * @param {GodotEvent} ev - { name: string, data: Object<string,string> }
     */
    function receive(ev) {
        console.log(`Received event from Godot: ${ev.name}`);
    }
    this.receive = receive;

    // Optional: handle BOSS system events (e.g. server push).
    // this.events = {
    //     "my-app.some-event": function(data) { self.send({ name: "some-event", data }); }
    // };
}
```

**Calling from `Application.html`:**

```javascript
async function openGame() {
    const win = await $(app.controller).loadController("Game");
    win.ui.show(function(ctrl) {
        // ctrl.configure() is forwarded to GodotController.configure().
        ctrl.configure(factoryId);
    });
}
```

**Data structures:**

```javascript
// BOSS → Godot (via self.send in ready() or elsewhere)
{ name: "command-name", data: { key: "value" } }

// Godot → BOSS (via _delegate.receive in GDScript)
{ name: "event-name", data: { key: "value" } }
```

---

### GDScript — `main.gd` pattern

All Godot apps hosted by BOSS follow this pattern:

```gdscript
extends Control

# GodotController instance from BOSS.
var _delegate: JavaScriptObject

# Strong reference — prevents the callback from being garbage-collected.
var _send_callback: JavaScriptObject

func _ready() -> void:
    if Engine.has_singleton("JavaScriptBridge"):
        # window.boss is set by BOSS after the iframe's onload fires.
        var window := JavaScriptBridge.get_interface("window")
        if window.boss:
            _delegate = window.boss
            # Replace the stub send() with a real GDScript callback.
            _send_callback = JavaScriptBridge.create_callback(_on_boss_send)
            _delegate.send = _send_callback
            # Signal to BOSS that Godot is fully initialised.
            # BOSS will call GodotController.ready(), which sends the first command.
            _delegate.ready()
        else:
            print("No BOSS controller configured for Godot event dispatch")


# Called by BOSS via controller.send(cmd).
# cmd shape: { name: String, data: Object<string:string> }
func _on_boss_send(args: Array) -> void:
    if args.is_empty():
        return
    var cmd: JavaScriptObject = args[0]
    print("BOSS → Godot: ", cmd["name"])


# Send an event from Godot to BOSS.
func _send_to_boss() -> void:
    if not _delegate:
        print("BOSS delegate not configured")
        return
    # GDScript Dictionaries arrive as undefined across the bridge.
    # Always build JS objects with create_object("Object").
    var data: JavaScriptObject = JavaScriptBridge.create_object("Object")
    data["key"] = "value"
    var ev: JavaScriptObject = JavaScriptBridge.create_object("Object")
    ev["name"] = "my-event"
    ev["data"] = data
    _delegate.receive(ev)
```

**Startup sequence:**

```
1. BOSS JS: win.ui.show(ctrl => ctrl.configure(factoryId))
   → GodotController.configure(factoryId) stores the value.
2. Godot.html: iframe onload → contentWindow.boss = controller
3. GDScript _ready(): reads window.boss, registers send callback,
   calls _delegate.ready()
4. GodotController.ready(): calls self.send({name: "configure", data: {...}})
   → GDScript _on_boss_send() receives it and starts work.
```

---

### JavaScriptBridge type rules

| GDScript type | Crosses bridge as | Notes |
|---------------|------------------|-------|
| `int`, `float`, `String`, `bool` | JS primitive | Safe to pass directly |
| `Dictionary` | `undefined` | **Never pass raw Dictionaries** — use `create_object("Object")` |
| `JavaScriptObject` | JS object | The correct type for all structured data |
| `JavaScriptObject` (callback) | JS function | Use `create_callback(method)` |

- Declare callback variables as `var foo: JavaScriptObject` (not `:=`) to avoid the "Variant inferred" warning-as-error.
- Keep a member variable holding every callback to prevent GC.

---
