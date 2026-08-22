# BOSS JavaScript Frontend Reference

Rules and patterns for BOSS app controller HTML files and OS APIs.

---

## 5. Controller Pattern

A controller is an HTML file at `/public/boss/app/<bundle_id>/controller/<Name>.html`.

### Controller naming

Controller names match the model or concept they represent. A controller for editing a job is named `Job`, not `JobEdit`. A controller for creating or listing employees is named `Employee` or `Employees`. Verb suffixes like `Edit`, `Create`, or `Detail` are omitted — the context (`configure(id)` for edit, no configure for create) makes the role clear.

```
Job.html          ✓ — edit/create a job
JobEdit.html      ✗ — unnecessary verb suffix
Employee.html     ✓
EmployeeEdit.html ✗
JobType.html      ✓
JobTypes.html     ✓ — list of job types
```

List controllers use the plural model name: `Jobs.html`, `Employees.html`, `JobTypes.html`.

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

The container's content is what stretches the window chrome — the chrome wraps the container, not the other way around. Set `width` on `div.container`, not `div.ui-window`.

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

### Module controllers (view / controller separation)

A controller registered with `"module": true` splits the view from the controller. The HTML file contains **no `<script>` block at all**; the controller lives in a sibling ES module named after the controller.

```json
"controllers": {
    "Example": { "module": true }
}
```

```
controller/Example.html    view only — markup, no <script>
controller/Example.js      controller — default-exported function
```

`Example.js` default-exports a function with the same shape as an inline controller, and uses the **same `this.x = x` convention**:

```javascript
export default function Example(view, app) {
    function save() {
        // ...
    }
    this.save = save;

    function viewDidLoad() {
        // ...
    }
    this.viewDidLoad = viewDidLoad;

    this.didHitEnter = save;
}
```

The view wires handlers exactly as it would for an inline controller — `$(this.controller).save()` resolves to the module's `this.save`:

```html
<button class="default" onclick="$(this.controller).save();">Save</button>
```

Things to note:
- The module receives `(view, app)` — `app` is the `UIApplication`, so app-level helpers are reachable without `$(app.controller)`.
- Lifecycle events, `configure()`, `delegate`, `events`, `didHitEnter` all work identically.
- The exported function's name matches the controller name.
- The view's handlers are wired by the sibling `.js`. To trace one, check `application.json` for `"module": true` and read `<Name>.js`.

`io.bithead.tutorial` uses this for `Example` and `Kiosk`.

### Model controller — full CRUD skeleton

Use this template when a controller edits an **existing model** (load, save, delete, cancel) and notifies a parent list controller to refresh. It combines all patterns in this section:
- [Function declaration order](#function-declaration-order)
- [Delegate pattern (`protocol`)](#delegate-pattern-protocol)
- [Control buttons (bottom of forms)](#control-buttons-bottom-of-forms) — Cancel → Delete → Save button order
- [configure method rules](shared.md#configure-method-rules)
- [Lifecycle events](#lifecycle-event-order) — `viewDidLoad` loads data, `viewDidAppear` sets focus
- [File menu accessibility](shared.md#file-menu-accessibility) — Save / Delete / Cancel mirrored in the File menu

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

1. **Controller functions** — the actions the screen offers (`save`, `delete`, `cancel`, etc.), excluding `configure`. Not business rules: those belong to the Private API, per [`process.md`](process.md#the-tactile-surface-decides-nothing)
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

### A form that owns a list creates its model up front

A child belongs to a parent that exists. A form holding a list of children —
an operation's sections, a pool's resources, a job type's sizes — therefore has
nothing to add them to until its own model has an ID, and the obvious way out
is to refuse: *save this first, then reopen it to add the rest*. That is the
wrong trade. It makes the user save something they have not finished, and it
splits one task into two visits to the same window.

Create the model as the form opens instead. `viewDidLoad` posts a draft, holds
the ID it gets back, and the Add buttons work from the first moment:

```javascript
// `null` until `create` makes one. A pool exists from the moment this form
// opens, so resources can be added to it before anything is saved.
let poolId = null;

// This form created the pool, and nothing has been saved over it yet.
// Cancelling or closing discards it; a pool reopened later does not.
let isNew = false;

// What a pool is called before anyone names it.
const DRAFT_NAME = "Untitled";

async function create() {
  let response;
  try {
    response = await os.network.post("/api/my-app/pool", { name: DRAFT_NAME });
  }
  catch {
    // Deliberately not awaited. `viewDidLoad` cannot close its own window —
    // the lifecycle has to finish first — so the close is hung off the alert
    // and runs once the user has read it.
    os.ui.showAlert("Failed to create the pool. Please try again later.")
         .then(function() { view.ui.close(); });
    return;
  }
  poolId = response.id;
  isNew = true;
  await reload();
}

async function viewDidLoad() {
  // Wired before the branch below: a new pool gains its resources after
  // `create`, and `viewDidLoad` does not run again.
  view.ui.select("resources").ui.setDefaultAction(editResource);
  if (isEmpty(poolId)) {
    await create();
    return;
  }
  await reload();
}
```

What the draft costs is a row that exists before anyone meant to keep it, so
the form owns it until it is saved over:

```javascript
async function save() {
  // ...
  await os.network.put(`/api/my-app/pool/${poolId}`, { name });
  // Saved, so it is no longer this form's to discard.
  isNew = false;
  delegate.didSavePool(response);
  view.ui.close();
}

function _delete() {
  let msg = isNew ? "Discard this pool's draft?"
                  : "Delete this pool and all of its resources?";
  os.ui.showDelete(msg, null, async function() {
    await os.network.delete(`/api/my-app/pool/${poolId}`);
    // The list never learned about a draft, so it has nothing to update.
    if (!isNew) {
      delegate.didDeletePool(poolId);
    }
    view.ui.close();
  });
}

async function cancel() {
  // A draft belongs to this window, so leaving discards it. `_delete` asks
  // first and closes the window itself once confirmed.
  if (isNew) {
    _delete();
    return;
  }
  view.ui.close();
}
this.cancel = cancel;

// Closing is leaving, which is what Cancel means.
this.windowShouldClose = cancel;
```

Rules:
- The POST creates the model with a placeholder name and nothing else. Every
  other field is sent by `save`.
- Children go through their own routes (`POST /pool/{id}/resource`) and the
  parent reloads on the child's delegate callback. A parent form never
  serialises its children into its own payload.
- The delegate stays quiet about a draft: a list that never heard of a row has
  nothing to refresh when it disappears.
- Use it when the form owns children. A form with only its own fields has
  nothing to create early and should not.

### `windowShouldClose` — refusing the close button

A controller that answers `windowShouldClose` is asked before its close button
takes effect, and the window closes only on `true`. It may await — the user is
asked, and the answer is waited for:

```javascript
this.windowShouldClose = cancel;      // closing is leaving, same as Cancel
```

```javascript
async function windowShouldClose() {
  if (!isDirty()) {
    return true;
  }
  // `showDelete` answers through callbacks, so the answer is what this
  // promise resolves to.
  return new Promise(function(resolve) {
    os.ui.showDelete(
      "Discard your changes?",
      async function() { resolve(false); },
      async function() { resolve(true); }
    );
  });
}
this.windowShouldClose = windowShouldClose;
```

A check that throws leaves the window open and shows an error — closing on a
failed check would discard whatever the check was protecting.

### The window is busy while `viewDidLoad` runs

Nothing to write: the OS does this. A window is on screen before its controller
loads, so while an `async viewDidLoad` is settling the content dims and stops
taking input, and the watch cursor shows. `viewDidAppear` waits for the same
moment, which is why focus belongs there — focusing a field that is about to be
overwritten by a response is the same bug as letting the user type into it.

Two things follow for a controller author. An `async viewDidLoad` that throws
surfaces in the window's own error modal, so a load failure needs no special
handling beyond the `catch` that reports it. And a `viewDidLoad` that fires a
request without awaiting it opts out of all of this — the window reads as ready
while its own data is still in flight.

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

### Building components at run-time

The styling pass that attaches each component's `ui` interface runs **once**, when a window renders. A component whose markup is inserted afterwards — one field per required pool, one input per section returned by the server — never receives that interface, so `view.ui.select("name").ui` is `undefined` and the control renders as a bare `<select>`.

Use the factory for the component you need. Each fills in a template, styles it, and returns an element that is ready to append:

```javascript
os.ui.makePopupMenu(name, label, firstOptionLabel, choices, config)  // config: {width, classes}
os.ui.makeListBox(name, choices, config)                             // config: {width, height, classes}
os.ui.makeTextField(name, label, config)                             // config: {type, classes}
os.ui.makeCheckbox(name, label, config)                              // config: {classes}
```

```javascript
const choices = resources.map(function(r) {
  return { id: String(r.id), name: r.name };
});
container.appendChild(
  os.ui.makePopupMenu("test-card", "Test card", "Select a test card", choices,
                      { classes: "stacked" })
);
```

**`firstOptionLabel` is required.** A pop-up menu's first option is its prompt — the text shown until a choice is made. `addNewOptions` deliberately preserves that option and appends after it, and the selected option's text is copied into `.ui-popup-label`, which has no height of its own. A blank first option therefore collapses the menu to its 1px borders until something is selected, so `makePopupMenu` throws rather than accepting one. Name the data the menu holds: `Select one`, `Choose model`, `Select a test card`.

The same reasoning applies to a menu declared in HTML — see the seeded-placeholder rule under UIPopupMenu.

Templates live in `/public/boss/app/io.bithead.boss/controller/Application.html`. To support a new component, add a template there and a factory beside the others in `ui.js`.

**Observing changes.** Use the component's delegate — `UIListBox`, `UITabs`, `UISlider`, `UISearchMenu`, and `UITokenMenu` all have one, and it is the idiom for every event-driven action:

```javascript
view.ui.select("steps").ui.delegate = {
  didSelectListBoxOption: function(option) { render(option.data); }
};
```

`UIPopupMenu` is the exception: it has no delegate and reports a selection by calling `select.onchange()` directly. Nothing is dispatched, so a listener on an ancestor never fires — assign the handler to the `select` itself:

```javascript
view.ui.select("test-card").onchange = didChangeCard;   // ✓
container.onchange = didChangeCard;                     // ✗ never fires for a popup menu
```

Native inputs (text, number, checkbox) do bubble, so one listener on a container covers those.

### Template command resolution

Every `$(...)` and `%(...)` command is substituted by `makeWindowAttributes` in `ui.js` **before** the controller script is evaluated. Knowing what each becomes explains what is legal to call on it.

| Command | Resolves to | Notes |
|---|---|---|
| `$(this.id)` | A generated controller ID | Only valid as `function $(this.id)(view)` |
| `$(this.controller)` | `os.ui.controller.<generatedId>` | This controller's own instance |
| `$(app.controller)` | `os.application('<bundleId>').proxy` | The `UIApplication`, **not** this controller |
| `$(app.bundleId)` | The bundle ID string | |
| `$(app.resourcePath)` | `/boss/app/<bundle_id>` | |
| `%(name)` | `os.ui.controller.<embeddedId>` | Embedded controller reference |
| `function %(name)` | `function <embeddedId>` | Must be substituted before other `%(...)` |
| `EmbedController(Name)` | The `<template id="Name">` innerHTML from `Application.html` | Injected before interpolation |

**The application proxy falls through to `Application.html`.** `$(app.controller)` is a `Proxy` over the `UIApplication` whose handler checks the application first and then the `main` (i.e. `Application.html`) controller instance. So both of these work from any controller in the app:

```javascript
// UIApplication's own method
const win = await $(app.controller).loadController("Detail");

// A function defined in Application.html — reached through the fall-through
const text = $(app.controller).interpolate(template, context);
```

This is the mechanism for **app-wide shared helpers**: define the function once in `Application.html`, expose it with `this.myHelper = myHelper`, and call it from every controller as `$(app.controller).myHelper(...)`.

### Delegate pattern (`protocol`)

Controllers that expose a callback interface declare a **delegate** using the `protocol()` function from `foundation.js`. This validates that the caller only provides methods the protocol knows about, avoids `null`-checking in call sites, and removes all boilerplate.

```javascript
function $(this.id)(view) {

  // Declare delegate as a private variable.
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
- `protocol()` is always a **private `let`**
- Fire the delegate **before** `view.ui.close()` — the delegate handler runs synchronously before the window closes
- Name delegate methods after the event, not the action: `didSaveCompany` not `saveCompany`; `didDeleteCompany` not `deleteCompany`
- Only add `async` to a function when it contains an `await` expression
- Mark a method **required** by passing a `DelegateMethod` object instead of a plain string: `DelegateMethod("didSelectItem", true)`

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

      // `userDidSignIn` and `userDidSignOut` do NOT belong here. The OS sends
      // them to launched windows and modals, never to the application
      // controller — see "Signing in and out" below.

      // Listen to OS/app events
      this.events = {
        "io.bithead.my-app.some-event": async function(ev) {
          console.log(ev.data);
        }
      };

      // Handle deep links (custom URL scheme, e.g. settings://friends)
      this.openDeepLink = async function(deepLink) {
        if (deepLink.path == "/settings") {
          // Open settings controller
        }
      };

      // Handle universal links (https://bithead.io/a/<scheme>/...)
      // Called when BOSS is launched from a universal link URL.
      // link.scheme identifies the app; link.path and link.params carry the payload.
      this.openUniversalLink = async function(link) {
        // e.g. https://bithead.io/a/tutorial/556?tab=detail
        // link.scheme = "tutorial", link.path = "/556", link.params = { tab: "detail" }
        const id = link.path.split('/').filter(Boolean)[0];
        if (!isEmpty(id)) {
          const ctrl = os.ui.makeController("Detail");
          ctrl.show(function(c) { c.configure(id); });
        }
      };
    }
  </script>

  <!-- App menu (shown in OS bar when app is focused) -->
  <div class="ui-menus">
    <div class="ui-menu" style="width: 180px;">
      <select name="application-menu">
        <option>My App</option>
        <option onclick="$(this.controller).showAbout();">About</option>
        <option class="group"></option>
        <option onclick="$(this.controller).quit();">Quit My App</option>
      </select>
    </div>
  </div>

  <!-- App icon mini-menu (shown when app is blurred and icon is tapped).
       IMPORTANT: Do NOT put a div.ui-menu inside ui-app-menu.
       Use plain buttons or omit the block entirely for default switch behavior. -->
  <div class="ui-app-menu">
    <div class="vbox gap-10">
      <div class="controls">
        <button class="primary" onclick="$(this.controller).openRecent();">Recent</button>
      </div>
      <div class="controls">
        <button class="default" onclick="os.switchApplication('$(app.bundleId)');">Switch</button>
      </div>
    </div>
  </div>
</div>
```

#### `ui-app-menu` rules

- Placing a `div.ui-menu` (with a `<select>`) inside `ui-app-menu` causes BOSS to promote the `ui-menu` directly into the OS bar as a standalone menu, skipping creation of the `AppWindowButton_` element. This causes `hideAppMenu` to crash. Use plain buttons and layout divs inside `ui-app-menu` instead (see example above).
- Omitting the `ui-app-menu` block entirely causes BOSS to create a default app icon button that switches to the app on click.
- Every `<select>` inside `div.ui-menus` must have a `name` attribute; BOSS throws `"UIPopupMenu select must have name"` if any select is unnamed.

**Application lifecycle order:**

```
applicationDidStart
applicationDidStop
```

### Secure menus

An app marked `"secure": true` hides the OS bar menus that a guest has no
business seeing. Each `ui-menu` in `Application.html` declares who it is for:

```html
<div class="ui-menus">
  <!-- No class: always shown. The guest reading a welcome screen needs a way
       to leave, so About and Quit stay reachable. -->
  <div class="ui-menu" style="width: 180px;">
    <select name="scheduler-menu">…</select>
  </div>

  <!-- Shown to a signed-in user, hidden from a guest. -->
  <div class="ui-menu secure" style="width: 160px;">
    <select name="schedule-menu">…</select>
  </div>

  <!-- Shown to the BOSS super user and nobody else. Implies `secure`: a super
       user is signed in by definition, so do not declare both. -->
  <div class="ui-menu super-user" style="width: 160px;">
    <select name="superadmin-menu">…</select>
  </div>
</div>
```

`UIApplication.applyMenuVisibility()` applies it when the app opens and again
when a user signs in. Both moments are needed: the menus are built when the app
opens, which is *after* whatever sign-in already happened, so an app opened by a
guest would otherwise show everything until the next sign-in.

There is no sign-out pass. A secure app is closed when the user signs out, and
its menus close with it.

Rules:
- The classes are read **only** in a secure app. An app that keeps working
  signed out has no signed-out state to conceal, and the classes are ignored
  there rather than hiding menus it means to offer.
- Only the app's own menus are evaluated. A window's `ui-menus` is appended to
  the same OS bar container but is the window's business — a window in a secure
  app is open because someone signed in.
- `super-user` means `os.isSuperUser(os.user)`, which is the BOSS super user
  account — not an app's own notion of an administrator. A role the app defines
  is the app's to check, and the menu is a convenience either way: the server
  still enforces the rule.
- `bin/validate-app` warns when a secure app has an OS bar menu declaring
  neither class. The first menu — the app's own — is exempt.

### Signing in and out

`userDidSignIn(user)` and `userDidSignOut()` are **window** callbacks.
`applicationWillSignIn` walks the app's launched windows and its modals and
calls each one; the application controller is not in either list, so a handler
written there never runs. A screen that has to react to a sign-in implements it
on itself.

`userDidSignIn` is not sent for the guest user, so it means "somebody real just
arrived" and nothing else.

A window that greets a guest and steps aside once they sign in — a welcome
screen — is the usual reason to want this:

```javascript
async function userDidSignIn(user) {
  // The next window is opened before this one closes: the desktop never
  // flashes empty, and the OS finishes handing the signal to every window
  // before this one leaves the list it is walking.
  await $(app.controller).showMainWindow();
  view.ui.close();
}
this.userDidSignIn = userDidSignIn;
```

An app marked `"secure": true` in `application.json` is closed by BOSS when the
user signs out, so it has nothing to do in `userDidSignOut`. Reach for that
callback only in an app that stays open across a sign-out.

Decide what a guest sees with `os.isGuestUser(os.user)` in `applicationDidStart`.
A guest is nobody yet, so an app whose routes require a session should ask this
before it calls any of them rather than showing a screen full of failures.

### Universal links

A universal link is an `https://bithead.io/a/<scheme>/...` URL that opens BOSS and routes directly to a specific app and view. BOSS calls `openUniversalLink(link)` on the app whose `scheme` in `installed.json` matches the URL segment after `/a/`.

**`UniversalLink` properties:**

| Property | Description | Example |
|---|---|---|
| `scheme` | App scheme from the URL | `"tutorial"` |
| `path` | Everything after the scheme segment | `"/556/detail"` |
| `params` | Query-string key/value pairs | `{ tab: "notes" }` |

**Register the scheme in `installed.json`:**

```json
"io.bithead.scheduler": { "name": "Scheduler", "icon": "icon.svg", "scheme": "scheduler" }
```

**Implement `openUniversalLink` on the Application controller:**

```javascript
// Single-segment path: https://bithead.io/a/scheduler/2241
this.openUniversalLink = async function(link) {
    const id = link.path.split('/').filter(Boolean)[0];
    if (!isEmpty(id)) {
        const ctrl = os.ui.makeController("Detail");
        ctrl.show(function(c) { c.configure(parseInt(id)); });
    }
};

// Path with query params: https://bithead.io/a/tutorial/556?tab=detail
this.openUniversalLink = async function(link) {
    // link.path = "/556", link.params = { tab: "detail" }
    const id = link.path.split('/').filter(Boolean)[0];
    const tab = link.params.tab;
    if (!isEmpty(id)) {
        const ctrl = os.ui.makeController("Detail");
        ctrl.show(function(c) { c.configure(parseInt(id), tab); });
    }
};
```

When a single app handles multiple URL shapes, parse the path segments and branch by type:

```javascript
// Multi-segment routing:
//   /a/scheduler/{businessId}           → SchedulerKiosk
//   /a/scheduler/appointment/{id}       → AppointmentModify
this.openUniversalLink = async function(link) {
    const segments = link.path.split('/').filter(Boolean);
    if (segments.length === 0) {
        return;
    }
    if (segments[0] === "appointment" && segments.length >= 2) {
        const win = await $(this.controller).loadController("AppointmentModify");
        win.ui.show(function(ctrl) { ctrl.configure(segments[1]); });
        return;
    }
    // Default: first segment is a numeric ID
    const id = parseInt(segments[0]);
    if (!isNumeric(id)) {
        return;
    }
    const win = await $(this.controller).loadController("SchedulerKiosk");
    win.ui.show(function(ctrl) { ctrl.configure(id); });
};
```

Rules:
- The scheme in `installed.json` is the identifier BOSS matches against `link.scheme`; a bundle ID may also serve as the scheme if no `scheme` field is set
- `openUniversalLink` is optional — omit it if the app does not support universal links
- The app is opened automatically if not already running; sign-in state is the application's responsibility
- Both deep links (`settings://`) and universal links (`https://bithead.io/a/`) use the same `scheme` field in `installed.json`

---

## 7. UIKiosk Controllers

A `UIKiosk` controller fills the entire viewport — no window chrome, no title bar, no close button. When a kiosk window opens, the OS hides the menu bar and dock. When it closes, they are restored. Use kiosk controllers to build full-screen experiences that do not look like BOSS apps.

### HTML structure

The root element is `div.ui-kiosk` instead of `div.ui-window`. An optional `div.title` child sets the browser page title at runtime and is hidden from view.

```html
<div class="ui-kiosk">
  <!-- Optional: sets the browser tab/window title; hidden automatically. -->
  <div class="title">My Kiosk App</div>
  <div>
    <!-- Kiosk content here -->
    <div class="controls">
      <button class="default" onclick="$(this.controller).close();">Close</button>
    </div>
  </div>
</div>
```

### JS controller

The JS module follows the same pattern as a regular controller. There is no window chrome, so the user cannot dismiss the window — provide a programmatic close path via `view.ui.close()`.

```javascript
export default function Kiosk(view, app) {
    let businessId;

    function close() {
        view.ui.close();
    }
    this.close = close;

    function configure(_businessId) {
        businessId = _businessId;
    }
    this.configure = configure;

    function viewDidLoad() {
        if (isEmpty(businessId)) {
            return os.ui.showError("Kiosk must be configured.");
        }
        // Populate content using businessId
    }
    this.viewDidLoad = viewDidLoad;
}
```

### application.json registration

Register a kiosk controller the same way as any module controller — no special key is needed:

```json
"controllers": {
    "Kiosk": {
        "module": true
    }
}
```

### Rules

- Root element is `div.ui-kiosk`
- The optional `div.title` (direct child of `div.ui-kiosk`) sets `document.title` — it is hidden automatically and contains no interactive content
- The OS hides the menu bar and dock on open and restores them on close
- Kiosk windows have no user-visible close affordance; expose a programmatic close path (`view.ui.close()`)
- `configure()` is called before `viewDidLoad()` — store parameters in `configure` and act on them in `viewDidLoad`

---

## 8. Embedded Controllers

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

Embedded controllers are rendered as part of the parent's DOM, so their lifecycle mirrors the parent's. The parent's `viewDidLoad` runs first; the embedded controller's `viewDidLoad` runs after.

Wire `%(embedded).configure()` and `%(embedded).delegate` from the **parent's `viewDidLoad`** — the embedded controller's DOM exists by that point.

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

## 9. Element Accessor APIs

Both `UIWindow` (via `view.ui`) and `_UIController` (via `view.ui` on embedded controllers) expose these element accessors. All return `HTMLElement|null`.

Use these accessors to query named elements on the view. They work for both static and dynamically-created elements. For dynamically-created elements, assign a `name` that incorporates the record's ID so the accessor can target it unambiguously (e.g. `name="comment-text-3"` accessed via `view.ui.textarea("comment-text-3")`).

```javascript
view.ui.button("name")          // <button name="name">
view.ui.details("name")         // <details name="name">
view.ui.div("name")             // <div name="name">
view.ui.divByClassName("name")  // <div class="name">
view.ui.element("id")           // document.getElementById("id")
view.ui.input("name")           // <input name="name">
view.ui.p("name")               // <p name="name">
view.ui.pByClassName("name")    // <p class="name">
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

## 10. UI Components — HTML Markup

Copy these patterns exactly. The CSS classes drive all visual behavior.

### Field type selection

When mapping a data model property to a form field:

| Data type / context | HTML pattern | Notes |
|---|---|---|
| Primary key / internal ID (`Int`) | `<input type="hidden" name="id">` | Not displayed to user |
| Editable string | `<div class="text-field">` | See text field pattern below |
| FK ID displayed as a label, or any read-only value | `<div class="read-only"><span name="...">` | Populate via `view.ui.span("field").textContent = value` |
| Single-select dropdown (compact, in a form or filter bar) | `<div class="ui-popup-menu" style="width: 160px;">` | See UIPopupMenu below |
| Scrollable list of selectable items | `<div class="ui-list-box">` | See UIListBox below |
| Multi-select list | `<div class="ui-list-box">` with `<select multiple>` | |

> **`text-field` is for text inputs only.** Use `ui-popup-menu` or `ui-list-box` for `<select>` elements.

### Inputs in table cells (inline editable tables)

When a table row contains editable fields (e.g. a schedule template or line-item list), place `<input>` and `<select>` elements directly in `<td>` cells without any wrapper div. The `text-field` and `ui-popup-menu` wrappers exist for form layout (label + field in a flex row) — in a table, the column `<th>` header serves as the label and the cell provides the layout.

```html
<table name="schedule-table">
  <thead>
    <tr><th>Day</th><th>Start</th><th>End</th><th></th></tr>
  </thead>
  <tbody>
    <!-- Rows built dynamically in JS — bare inputs in td are correct here -->
  </tbody>
</table>
```

Dynamic row builder (JS):
```javascript
function buildScheduleRow(day) {
  const tr = document.createElement("tr");
  tr.innerHTML =
    "<td>" + DAY_NAMES[day.dayOfWeek] + "</td>" +
    "<td><input type='time' value='" + day.startTime + "'></td>" +
    "<td><input type='time' value='" + day.endTime + "'></td>" +
    "<td><button onclick='...'>✕</button></td>";
  return tr;
}
```

Rules:
- `<input>` and `<select>` in `<td>` do **not** require `text-field` or `ui-popup-menu` wrappers.
- If a `<select>` in a table cell needs BOSS popup styling, wrap it in `<div class="ui-popup-menu">` — but accept that this may affect cell sizing and test accordingly.
- Do **not** use `view.ui.input()` to query inputs built dynamically in table rows — query by the `<tr>` element directly (`row.querySelectorAll("input")`).

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

Use `div.read-only` to display a label alongside a read-only value (e.g. an ID, a name fetched from the server, or a computed reference).

```html
<div class="read-only">
  <label>Owner</label>
  <span name="owner-name"></span>
</div>
```
Populate in `viewDidLoad`: `view.ui.span("owner-name").textContent = value;`

The `<label>` text is the human-readable field name. The `<span name="...">` holds the value and is queried via `view.ui.span(name)`.

#### Wider labels

By default, `read-only` and `text-field` labels are 90px wide. When a group contains a long label (e.g. "Payment Status") that wraps, add `wider-labels` to the **wrapper div** to widen all labels in that group uniformly to 120px:

```html
<div class="vbox gap-20 wider-labels">
  <div class="read-only">
    <label>Job Code</label>
    <span name="job-code"></span>
  </div>
  <div class="read-only">
    <label>Payment Status</label>
    <span name="payment-status"></span>
  </div>
</div>
```

`wider-labels` affects `div.read-only label` and `.text-field label` inside the container. Use it whenever any label in the group would otherwise wrap to two lines. For a single one-off override, add `class="wider"` directly to the `<label>` element instead.

### Hidden field (for IDs)
```html
<input type="hidden" name="id">
```

### Control buttons (bottom of forms)

The form submission `div.controls` block (Save / Cancel / Delete) is always the **last direct child of the `div.container`** — never inside a fieldset, `vbox`, or any other wrapper. No fields, fieldsets, or tables may appear after it.

```html
<div class="container vbox gap-20" style="width: 480px;">

  <fieldset>
    <legend>Details</legend>
    <div class="vbox gap-10">
      <!-- fields here -->
    </div>
  </fieldset>

  <!-- controls is a direct child of container, after all fieldsets -->
  <div class="controls">
    <button class="primary" onclick="$(this.controller).cancel();">Cancel</button>
    <button class="default" onclick="$(this.controller).save();">Save</button>
  </div>

</div>
```

Button order: **secondary → primary → default**. Only one `default` per window. When a form supports deleting the model: **Cancel → Delete → Save**.

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

After loading, set the button state directly — `UIListBox` auto-selects the first item, so a non-empty list arrives with a selection already made:

```javascript
async function loadItems() {
  const response = await os.network.get("/api/my-app/items");
  view.ui.select("items").ui.addNewOptions(response.items);
  view.ui.button("edit").disabled = response.items.length === 0;
}
```

Double-click is the same action as Edit, and is wired once in `viewDidLoad`:

```javascript
view.ui.select("items").ui.setDefaultAction(edit);
```

Rules:
- Add opens the model form with no `configure()` call; Edit opens it with `configure(id)` and the selection's value
- The Delete button lives inside the model's form, not in the list window
- The Edit button uses `class="default"` — it is the primary action in this context
- Model-specific buttons (`Open`, `Edit`, etc.) are always `disabled` by default. The list box delegate is responsible for enabling them.
- Use `hasSelectedOption()` on both `didSelectListBoxOption` and `didDeselectListBoxOption` to toggle button state.
- A **Remove** button paired with a list box must be disabled when the list is empty — both on initial load and after every removal. If a `refreshList` private function manages the list contents, set `button.disabled = items.length === 0` at the end of that function. Also implement `didRemoveAllOptions` in the list box delegate to disable the button when `removeAllOptions` is called externally.
- Omit the top `<div class="vbox gap-10">` (and its buttons) if there are no model-agnostic actions; in that case also drop `separated` from `controls-right` and place the model-specific buttons directly inside — they will flex to the bottom automatically
- Omit the bottom group if every action requires no selection
- The `separated` class on `controls-right` creates a visual divider between the two groups; omit it when there is only one group

A list of children *inside* a form follows this same layout — one `fieldset` per
list, each with its own Add and Edit. What differs is where the model comes
from: see [A form that owns a list creates its model up front](#a-form-that-owns-a-list-creates-its-model-up-front).

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
- When an accordion starts `closed` and its content is data-driven, open it in `viewDidLoad` if the server returns data. Delegate callbacks (e.g. after save/delete) only refresh list content.

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

Toggle the `metrics-none` / `metrics` divs in `viewDidLoad` based on whether the server returned a metrics object. `*FlowMetrics` fields are server-computed and read-only; omit them from save payloads.

### UIListBox — single select
```html
<div class="ui-list-box" style="width: 200px;">
  <select name="my-list">
    <option value="1">Option 1</option>
    <option value="2" disabled>Option 2 (disabled)</option>
  </select>
</div>
```

**`selectOption(index)` takes a 0-based index; `selectValue(value)` takes the option's value.** Reach for `selectValue` whenever the list is keyed by a model ID or any other value — `selectValue` looks the value up and calls `selectOption` with the index it finds. Passing a value to `selectOption` selects the wrong row, or none at all when the value exceeds the option count.

**Disabled options.** `UIListBox` honors `option.disabled`: a disabled option cannot be selected and fires no delegate callback. There are three ways to set it, depending on where the state comes from.

Static markup, when availability is fixed:

```html
<option value="2" disabled>Option 2</option>
```

A `disabled` field on the model, when availability arrives with the data. This is the usual case for a list built from a server response:

```javascript
view.ui.select("my-list").ui.addNewOptions([
  { id: "a", name: "Available" },
  { id: "b", name: "Unavailable", disabled: true }
]);
```

`disableOption(value)` / `enableOption(value)`, when availability changes after the list is built:

```javascript
view.ui.select("my-list").ui.disableOption("b");
view.ui.select("my-list").ui.enableOption("b");
```

All three set both the behaviour and the appearance. Auto-selection skips leading disabled options, so a list whose first rows are unavailable still lands on something the consumer can act on — and when every option is disabled, nothing is selected and no callback fires.

> **`UIPopupMenu` supports only the first of the three.** A disabled option is greyed and cannot be chosen there — `styleOptions` applies the `disabled` class and the click handler ignores it — but `<option disabled>` in the HTML is the only way to set the flag. Its `addNewOptions` reads `id`, `name`, and `data` only, and it has no `disableOption` / `enableOption`. Give a popup menu its options already in the state you need them.

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
`buttons` mode treats each option as a clickable button. Use it with a single-select `<select>` only.
```html
<div class="ui-list-box buttons" style="width: 200px;">
  <select name="my-buttons">
    <option value="a" onclick="$(this.controller).doA();">Action A</option>
    <option value="b" onclick="$(this.controller).doB();">Action B</option>
  </select>
</div>
```

### UIListBox — populating from server data

The backend returns list items as `Fragment.Option` (`{ id: String, name: String }`). Pass the array directly to `addNewOptions`:

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

**`Fragment.Option` is for list UI** — `Fragment.Option` (`{ id, name }`) is for lightweight list items (e.g. `UIListBox`, `UISearchMenu`, pop-up menus, token fields). For operator, reporter, or other rich entity fields on detail fragments, use the corresponding domain fragment (e.g. `LeanFragment.Operator`).

### No transformation of server response models

When the server response shape matches what the UI or controller needs, pass it directly — to UI component APIs and back in the save body.

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

**Return the Promise.** The `UIListBox` owns the `await` and uses the result to decide whether to commit or cancel the visual move. Use `return os.network.patch(...)`, not `await os.network.patch(...)`.

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

**Width comes from CSS, not markup.** `.ui-popup-menu` declares `--popup-width: 160px` — the standard. Declare nothing for a standard menu; set `--popup-width` only when a menu genuinely needs another size:

```html
<!-- Standard: nothing to declare -->
<div class="ui-popup-menu">

<!-- Wider, because the content needs it -->
<div class="ui-popup-menu stacked" style="--popup-width: 260px;">

<!-- Fills its parent -->
<div class="ui-popup-menu" style="--popup-width: 100%;">
```

The variable sizes the **drop-down control**, not the row: a horizontal label sits beside it, so the menu is wider than the control. `.ui-popup-container` consumes the variable and is `border-box`, so its 1px borders sit inside that width — with `content-box` a control sized `100%` renders 2px wider than its parent and scrolls the view sideways.

A class can size a menu, because nothing in `ui.js` reads the inline style:

```css
.ui-popup-menu.date-range { --popup-width: 120px; }
```

By default the label appears to the **left** of the drop-down (horizontal layout). When mixing a popup menu in a row with `text-field` elements (where the label is above), add the `stacked` modifier so the label sits on top and row heights align:

```html
<!-- Default: label left -->
<div class="ui-popup-menu" style="width: 160px;">
  <label for="status">Status</label>
  <select name="status">
    <option value="">Select one</option>
    <option value="active">Active</option>
  </select>
</div>

<!-- Stacked: label on top (use when mixed with text-field in the same row) -->
<div class="ui-popup-menu stacked" style="width: 160px;">
  <label for="status">Status</label>
  <select name="status">
    <option value="">Select one</option>
    <option value="active">Active</option>
  </select>
</div>
```

**Rule:** Use `stacked` any time a `ui-popup-menu` appears alongside `text-field` or `textarea-field` elements in the same flex row — otherwise the left-label layout makes the popup taller than its siblings. The `stacked` variant matches the `text-field` label-above pattern. `align-self: flex-start` is set on `ui-popup-menu` by default to prevent height stretching.

**A pop-up menu paired with a button is one unit — use `intrinsic` and keep them on one line.** When a menu and a button act together (filter, add, apply), the label, control, and button should read as a single row:

```html
<!-- ✓ correct -->
<div class="hbox gap-10">
  <div class="ui-popup-menu intrinsic">
    <label for="pool-picker">Pool</label>
    <select name="pool-picker"><option value="">Choose one</option></select>
  </div>
  <button class="primary" onclick="$(this.controller).addPool();">Add</button>
</div>
```

Without `intrinsic` the label sits in the fixed 90px label column, leaving a gap between a short label and its control that reads as two separate things. `intrinsic` gives the label its content width and 10px of separation, so the three elements are flush.

Use `stacked` instead when the menu is one of several form fields whose labels must line up in a column — that is a different situation, and the two modifiers should not be combined. `bin/validate-app` warns when a popup/button row is missing `intrinsic`.

**A `text-field` paired with a button takes `intrinsic` for the same reason.** Its label sits above the input by default, which makes the field a label taller than the button beside it and leaves the two standing on different lines:

```html
<!-- ✓ correct -->
<div class="hbox gap-10">
  <div class="text-field intrinsic">
    <label for="new-column">Column</label>
    <input type="text" name="new-column">
  </div>
  <button class="primary" onclick="$(this.controller).addColumn();">Add</button>
</div>
```

`intrinsic` moves the label to the left of the input with 10px of separation, and sizes the input to its content rather than to the row — so the label, the input, and the button are flush. Keep the default when the field is one of several stacked fields whose labels line up in a column.

**Every `<select>` in a `ui-popup-menu` or `ui-menu` declares a prompt as its first option, and that prompt carries no value.** This holds whether the menu is filled at runtime or written out in full — the first slot belongs to the menu's label in both cases.

Two things follow from it. An empty `<select>` has `selectedIndex = -1`, which crashes BOSS during controller init — before `viewDidLoad` runs, so no amount of JavaScript can rescue it. And `styleOptions` renders choices from index 1 while `selectedValue()` returns `null` whenever `selectedIndex` is 0, so a real choice written into that slot can be displayed as a default and then never selected or read again:

```html
<!-- ✓ correct: the prompt occupies the label slot -->
<select name="section-type">
  <option>Choose a type</option>
  <option value="description">Description</option>
  <option value="image">Image</option>
</select>

<!-- ✗ wrong: `Description` shows as the default and can never be chosen -->
<select name="section-type">
  <option value="description">Description</option>
  <option value="image">Image</option>
</select>
```

Reading the raw `select.value` returns the first option where `selectedValue()` gives `null`, so a menu written the wrong way can look correct until someone follows the convention and goes through `.ui`. Reset to the prompt with `selectOption(0)` — the one place selecting by index is right.

**A prompt names the choice to be made; it is not a default.** `Select filter` is a prompt. `All` is a choice, even when it happens to mean "no filter" — so give it a value and let the user pick it. A screen waits on its prompt: it queries nothing and lists nothing until a choice is made, which keeps every menu in the app behaving the same way regardless of whether one of its choices could have served as a default.

```html
<!-- ✓ the prompt asks; every option below it is chosen -->
<option>Select filter</option>
<option value="all">All</option>
<option value="pending">Pending</option>
```

A choice whose meaning is "no constraint" is still a value the client maps — `state === "all"` sending no query parameter — rather than an empty string standing in for an unmade choice. Empty means unchosen, and only that.

Seed a menu you populate at runtime the same way:

```html
<!-- Correct: placeholder present at parse time -->
<div class="ui-popup-menu stacked" style="width: 220px;">
  <label for="production-line">Production line</label>
  <select name="production-line">
    <option value="">Choose one</option>
  </select>
</div>
```

That first option is the menu's **prompt**, not a throwaway. `addNewOptions` deliberately preserves it and appends after it, and its text is what `.ui-popup-label` displays until a choice is made — so give it meaningful text and **do not repeat it** in the options you add:

```javascript
// ✓ correct — the HTML's "Choose one" is still option 0
view.ui.select("production-line").ui.addNewOptions(
  lines.map(function(l) { return { id: String(l.id), name: l.name }; })
);

// ✗ wrong — renders "Choose one" twice
view.ui.select("production-line").ui.addNewOptions(
  [{ id: "", name: "Choose one" }].concat(...)
);
```

`bin/validate-app` checks that the placeholder is present.

A menu built at run-time with `os.ui.makePopupMenu` needs no placeholder — its template carries one.

### Date and time fields

Use bare `<input type="date">` and `<input type="time">` directly inside `text-field` wrappers. The BOSS input style (border, height, font) applies automatically. Do not wrap them in custom component divs.

```html
<div class="text-field">
  <label for="scheduled-date">Date</label>
  <input type="date" name="scheduled-date">
</div>

<div class="text-field">
  <label for="scheduled-time">Time</label>
  <input type="time" name="scheduled-time">
</div>
```

Access values via `view.ui.input("name").value`. Date returns `"YYYY-MM-DD"`, time returns `"HH:MM"`.

In `<td>` cells of dynamically-built table rows, bare inputs are also correct — no wrapper needed (see §10 "Inputs in table cells").

### Icon button classes

Three icon classes can be combined with `button.primary`. The CSS adds the icon via `background-image` — leave the button element empty in HTML.

| Class | Icon | Use |
|---|---|---|
| `up-arrow` | `group-open.svg` flipped vertically | Move a row up |
| `down-arrow` | `group-open.svg` | Move a row down |
| `delete` | `trash-small.svg` | Remove/delete a row or record |

All three are 16×16px.

```javascript
// In a dynamic row builder:
"<td>" +
"<button class='primary up-arrow' onclick='$(this.controller).moveUp(id);'></button> " +
"<button class='primary down-arrow' onclick='$(this.controller).moveDown(id);'></button> " +
"<button class='primary delete' onclick='$(this.controller).removeRow(this);'></button>" +
"</td>"
```

```html
<!-- Static HTML -->
<button class="primary delete" onclick="$(this.controller).delete();"></button>
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

**Auto-save pattern (full list):** when `didAddToken` and `didRemoveToken` need to persist the current set, read all selected options from the backing `<select>` and send the complete list. This avoids ordering and race-condition issues:

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

### Form and fieldset spacing

**Gap rules:**

| Context | Gap |
|---|---|
| Between fieldsets (outer container or tab) | `gap-20` |
| Between fields inside a fieldset or flat section | `gap-10` |
| When a tab mixes a loose field group and fieldsets | outer `gap-20`; inner field group `gap-10` |

BOSS's `.container` provides internal padding automatically. Do not add extra `padding` on inner content divs.

```html
<!-- Standard: fieldsets with field groups inside each -->
<div class="container vbox gap-20" style="width: 480px;">

  <fieldset>
    <legend>Schedule</legend>
    <div class="vbox gap-10">
      <div class="text-field">
        <label for="date">Date</label>
        <input type="date" name="date">
      </div>
      <div class="text-field">
        <label for="time">Time</label>
        <input type="time" name="time">
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Details</legend>
    <div class="vbox gap-10">
      <div class="read-only">
        <label>Status</label>
        <span name="status"></span>
      </div>
    </div>
  </fieldset>

</div>

<!-- Mixed tab: loose fields then fieldsets -->
<div name="tab-schedule">
  <div class="vbox gap-20">
    <!-- Loose input fields at gap-10 -->
    <div class="vbox gap-10">
      <div class="ui-popup-menu stacked" style="width: 160px;">
        <label for="interval">Slot Interval</label>
        <select name="interval">...</select>
      </div>
      <div class="text-field">
        <label for="cutoff">Cutoff (days)</label>
        <input type="number" name="cutoff">
      </div>
    </div>
    <!-- Fieldsets at gap-20 from the field group above -->
    <fieldset>
      <legend>Options</legend>
      <div class="vbox gap-10">
        <div class="hbox gap-10">
          <input type="checkbox" name="opt">
          <label>Enable option</label>
        </div>
      </div>
    </fieldset>
    <div class="controls">
      <button class="default" onclick="...">Save</button>
    </div>
  </div>
</div>
```

### Left-side navigation (settings-style windows)

When a window has multiple named sections, use a `ui-list-box` on the left with static `<option>` items. Wire its `didSelectListBoxOption` delegate to show/hide content panels. The container uses `hbox gap-10`; no extra padding on the content div.

```html
<div class="container hbox gap-10" style="width: 720px; min-height: 460px;">

  <div class="ui-list-box" style="flex: 0 0 200px; align-self: stretch;">
    <select name="settings-nav">
      <option>General</option>
      <option>Schedule</option>
    </select>
  </div>

  <div style="flex: 1; overflow-y: auto;">
    <div name="tab-general">...</div>
    <div name="tab-schedule" style="display: none;">...</div>
  </div>

</div>
```

```javascript
async function viewDidLoad() {
  const TAB_NAMES = ["general", "schedule"];

  function showTab(name) {
    for (const t of TAB_NAMES) {
      view.ui.div("tab-" + t).style.display = t === name ? "" : "none";
    }
  }

  view.ui.select("settings-nav").ui.delegate = {
    didSelectListBoxOption: function(opt) {
      showTab(TAB_NAMES[opt.index]);
    }
  };
  view.ui.select("settings-nav").ui.selectOption(0);
  showTab("general");
}
```

Note: `flex: 0 0 200px` is required on the `ui-list-box` because `.ui-list-box` has `flex: 1` which overrides `width`. Use `flex: 0 0 Npx` to give it a fixed size inside a flex row.

#### When the content scrolls

Content long enough to scroll needs the `settings` layout, or the scrollbar
appears *inside* the container's 10px padding — floating in a gutter instead of
sitting against the window edge:

```html
<div class="container settings" style="width: 720px; height: 460px;">

  <div class="ui-list-box settings-nav" style="flex: 0 0 200px;">
    <select name="settings-nav">
      <option>General</option>
      <option>Schedule</option>
    </select>
  </div>

  <div class="settings-content">
    <div name="tab-general">…</div>
    <div name="tab-schedule" style="display: none;">…</div>
  </div>

</div>
```

`settings` drops the container's padding so the pane can reach the window's
edges, and hands the spacing back as margins on the two children — `10px`
around the nav, and `10px` top, bottom and right on each direct child of
`settings-content`. That is the same 10px the container's padding would have
given, so the window keeps BOSS's spacing; what changes is that the scrollbar
now sits outside it, flush with the window on three sides.

Rules:
- Give the container a **`height`**, not a `min-height`. The pane scrolls only
  if the container is bounded.
- Every tab is a **direct child** of `settings-content` — the margin is applied
  to direct children, so a tab wrapped in another div loses it.
- The container is `overflow: hidden`: the pane owns the scrolling. Two nested
  scroll areas give two scrollbars, and the outer one is the gutter this exists
  to remove.

When a row mixes a `text-field`, a `UIPopupMenu`, and action buttons, use `hbox gap-10` on the row. Add `stacked` to any `ui-popup-menu` in the row so its label sits on top (matching `text-field`). Stack buttons vertically with `vbox gap-10` aligned to `flex-end` so they sit flush with the bottom of the fields:

```html
<div class="hbox gap-10" style="align-items: flex-end;">
  <div class="text-field">
    <label for="amount">Amount ($)</label>
    <input type="number" name="amount">
  </div>
  <div class="ui-popup-menu stacked" style="width: 120px;">
    <label>Method</label>
    <select name="method">
      <option value="cash">Cash</option>
    </select>
  </div>
  <div class="vbox gap-10" style="align-self: flex-end;">
    <button class="primary" onclick="...">Action A</button>
    <button class="primary" onclick="...">Action B</button>
  </div>
</div>
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

## 11. UI Components — JavaScript Access

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

## 12. OS APIs

Always read the JSDoc in the respective `.js` file before using any function.

### Never use native browser dialogs

`alert()`, `confirm()`, and `prompt()` are browser chrome. They block the whole page, cannot be styled, and break the 2-bit Mac OS look the rest of the system maintains. Use the BOSS equivalents:

| Native | Use instead |
|---|---|
| `alert(msg)` | `os.ui.showAlert(msg)` |
| `confirm(msg)` | `os.ui.showDelete(msg, cancelFn, okFn)` — both callbacks must be `async` or `null` |
| `prompt(msg)` | A modal `UIController`. There is no OS prompt API; collect input in a form with `Cancel` / `Save` and return the value through a delegate. |

`bin/validate-app` warns on all three.

### Verify Core OS Object Shapes

Before accessing properties on `os.user`, `os.network`, or other framework globals, explicitly confirm the shape by checking [`js-api.md`](js-api.md) or searching for existing usage in the codebase.

### `os` — OS-level operations

```javascript
os.ui.close()                         // Close the current app
os.ui.focusWindow(container)          // Focus a window
os.ui.makeController("Name")          // Create a controller (does not show it)
os.ui.showAlert("Message")            // Show an alert modal
os.ui.showError("Error message")      // Show an error modal
await os.ui.showInfo("Info message")  // Show info modal; awaitable until dismissed
os.ui.showDelete("Are you sure?", cancelFn, okFn)  // Confirmation delete modal
os.ui.hideBusy()                      // Hide spinner
os.ui.showImageViewer([url1, url2])   // Open image viewer
os.ui.showColorPicker(fn)             // Show color picker modal; fn(hexColor) called on selection
os.ui.showEmbeddedControllers(app)    // Show list of shared embedded controllers for an app
os.ui.showEmbeddedControllerDetail(bundleId, name)  // Open live embedded controller detail window

os.switchApplication("io.bithead.my-app")  // Switch to another app
os.openDeepLink("settings://friends")      // Open a deep link
os.openUniversalLink(window.location.href) // Open a universal link from the current URL
os.getLaunchUrl("io.bithead.my-app")       // Get the launch URL for an app
os.isSuperUser(user)                        // Boolean: is current user a super user?
os.isGuestUser(user)                        // Boolean: is current user a guest?
```

### `os.network` — Network calls

### `os.ui.showDelete` — Confirmation modal

Shows a two-button confirmation dialog. Both the `cancel` and `ok` callbacks **must be `async` functions** — BOSS validates this at call time and throws if they are not.

```javascript
// Standard pattern — cancel is null (default dismiss), ok is async
os.ui.showDelete("Are you sure you want to delete this item?", null, async function() {
  try {
    await os.network.delete(`/my-app/item/${itemId}`);
  }
  catch {
    os.ui.showError("Failed to delete. Please try again.");
    return;
  }
  delegate.didDeleteMyItem();
  view.ui.close();
});

// With a custom cancel callback (also async)
os.ui.showDelete("Continue?", async function() {
  // user tapped Cancel
}, async function() {
  // user tapped OK
  await doWork();
});
```

Signature: `os.ui.showDelete(message, cancelFn, okFn)`

| Argument | Type | Description |
|---|---|---|
| `message` | `string` | The question shown in the dialog |
| `cancelFn` | `async function \| null` | Called when the user taps Cancel. Pass `null` for default dismiss behavior. |
| `okFn` | `async function \| null` | Called when the user taps OK/Confirm. Pass `null` to show a non-actionable prompt. |

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

A form that holds a list of children has no branch here: the model already
exists by the time `save` runs, so `save` is always a `PUT`. See
[A form that owns a list creates its model up front](#a-form-that-owns-a-list-creates-its-model-up-front).

**Error handling rules:**
- When a network call throws, display `error.message` — the server returns structured error messages that should be shown verbatim. `error.message` is always present on network errors.
```javascript
try {
  response = await os.network.get(`/lean/intake-queue/${intakeQueueId}`);
}
catch (error) {
  os.ui.showError(error.message);
  return;
}
```
- Once a route is fully implemented and wired up, remove any `// TODO: <METHOD> /path` comment that was marking it as pending. A TODO in a network call means the route is not yet integrated; no TODO means it is live.
- Pattern:

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

## 13. Notifications and Events

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

A controller that hosts a Godot game requires a `godot` key. Use any controller name other than `"Godot"` — that name is reserved by the system.

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
    // Set contentWindow.boss in onload so the assignment targets the loaded context.
    container.onload = function() {
        container.contentWindow.boss = controller;
    };
    container.src = `/boss/app/${app.bundleId}/${config.godot.main}`;
}
```

`ctrl.configure()` inside `win.ui.show()` is automatically forwarded to `GodotController.configure()`.

---

### GodotController protocol

`GodotController` is a JS ES module export with the following interface:

| Member | Direction | Required | Description |
|--------|-----------|----------|-------------|
| `id` | — | Yes | Mutable property set by BOSS after instantiation. Use `property(this, "id", getter, setter)`. |
| `configure(...)` | BOSS → GodotController | Optional | Called from `win.ui.show(ctrl => ctrl.configure(...))` to pass app-specific data before Godot loads. |
| `ready()` | Godot → BOSS | **Required** | Called by GDScript after the bridge is established. Use to send the initial command(s) to Godot via `self.send(...)`. |
| `receive(ev)` | Godot → BOSS | **Required** | Called by GDScript to send an event to BOSS. Handle all incoming Godot events here. |
| `send(cmd)` | BOSS → Godot | Injected | Overwritten by Godot at startup with a `JavaScriptBridge` callback. Call it to send commands to Godot. |
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
| `Dictionary` | `undefined` | Convert to `JavaScriptObject` via `create_object("Object")` |
| `JavaScriptObject` | JS object | The correct type for all structured data |
| `JavaScriptObject` (callback) | JS function | Use `create_callback(method)` |

- Declare callback variables as `var foo: JavaScriptObject` (not `:=`) to avoid the "Variant inferred" warning-as-error.
- Keep a member variable holding every callback to prevent GC.

---
