# BOSS spec

This provides the data structures necessary to create an app, and render windows, inside BOSS (Bithead Operating System).

## Terms

It is important to note that this documentation refers to `UIApplication`, `UIController`, `UIWindow`, etc. In Javascript, you will find corresponding classes that match these names. However, in CSS, you will find the respective classes `ui-application`, `ui-controller`, `ui-window`, respectively.

It is important to note that when I refer to a `UIWindow`, I may also be referring to its HTML source... where the `UIWindow` is defined in CSS as `<div class="ui-window">`.

## `UIApplication`

An application is the combination of base application configuration, controllers, and resources.

Below is the necessary configuration for an application, in YAML format.

> BOSS requires the configuration file, `application.json`, to be JSON. NOT YAML! YAML is used as it's easier to read.

```yaml
# The version of BOSS this application was designed for
boss:
  version: 1.0.0

application:
  bundleId: io.bithead.boss
  name: Test Management
  version: 1.0.0

  # Defines if this is a system application.
  #
  # System apps provide foundational level features such as modals,
  # dialogs, etc. They are NOT visible to the user in the list of
  # installed apps.
  #
  # Example 1
  # The io.bithead.boss app is a system level apps, which provides common
  # components that can be used by all apps as well as system-specific
  # modals, dialogs, and controls.
  #
  # Example 2
  # Apps like the Image Viewer are _not_ system apps, but are included
  # with the system.
  #
  # System apps work in all application contexts. Therefore, all system
  # apps are also `passive` apps. (Refer to `passive` description below).
  #
  # System apps may NOT have menus or app menus (used for switching
  # apps).
  system: false

  # Indicates that the app must be closed if the user signs out. Default: `false`
  secure: false

  # Logos must be SVG. They will be shown in the OS bar, desktop icon, etc.
  #
  # If the application bundle has an `image` directory, you may refer
  # to the logo inside that directory with the following. Otherwise, the logo
  # will be attempted to be found in root directory of the app's bundle at
  # /public/boss/app/<bundle_id>/logo.svg.
  icon: image/logo.svg

  # The application's main controller. This can be `Application` or the name
  # of a `UIController` in the `controller` folder, sans `.html`.
  # If a controller exists at `controller/Home.html`, you would simply put
  # `Home` as the value. e.g. `main: Home`
  #
  # Using `Application` provides:
  # - More control over how the app loads. Sometimes it is required to DL dependencies.
  # - An app menu. e.g. About, Settings, etc. Otherwise, a menu will not be shown.
  #
  # If using `Application`, you are responsible for showing the first view controller.
  # `controller/Application.html` must exist. This is a "special" controller in that
  # you do not need to declare the Application controller in `application.json`. It is
  # assumed to exist if you provide `Application`.
  #
  # Refer to `/public/boss/app/io.bithead.boss-code/` for a full example.
  #
  # Godot Web5 apps are also supported. To create a BOSS app, for your Godot
  # game, set `main` to `Godot`. Please refer to the `Godot application` section
  # for more information on how to configure your Godot app.
  main: TestHome

  # The controller to display when the app's button (in the OS bar when blurred)
  # is tapped. An app may either define a controller to display, a ui-menu
  # defined in the application controller, or have no menu at all. In which case
  # the app button is automatically created.
  menu: MyMenu
  author: Eric Chamberlain
  copyright: 2025 Bithead LLC. All rights reserved.

  # Automatically quit the application when all windows are closed.
  # Default: `false`
  quitAutomatically: false

  # Passive apps indicate that the app is context-agnostic. In other words
  # it will not switch context and live in the same context as the current
  # app. This is useful for OS and admin tools.
  #
  # Passive apps do not receive the `applicationDidFocus` or `applicationDidBlur`
  # delegate callbacks as they do not switch contexts.
  #
  # Passive apps may have a menu, but NOT have an app menu (for switching
  # app contexts).
  #
  # Default: `false`.
  passive: false

  # Kiosk mode hides the desktop icons, OS bar, and launch bar. Only the app
  # UI will be displayed. Users should not know that the app is a BOSS app.
  #
  # It is possible to toggle out of kiosk mode. To do this, the application
  # must make direct calls to the OS to switch, or close, the app that is in
  # kiosk mode. This is useful when wanting to switch between a customer
  # facing kiosk app, and the respective admin app. For an example, refer to
  # the Scheduler app (TBD) for reference on how to do this.
  #
  # Default: `false`
  kiosk: false
```

Some configuration, such as logos, will refer relatively to the resource inside its bundle directory. However, when downloaded to the client's browser, it will expand to something like `/boss/app/<bundle_id>/image/logo.svg`.

In all other contexts, such as controller logic, you may refer to any resource in your app's bundle by prepending `/boss/app/<bundle_id>/` to the HTTP resource path or interpolating the app's resource path using `$(app.resourcePath)` e.g. `<img src="$(app.resourcePath)/img/icon.png">`. There is an example of how this works in the `UIController` section.

> The server may choose to limit which applications a user sees. Therefore, even if an app is installed on the server, a user may not have access to it.

### `Application.html` example

The `Application.html` provides a way to configure the app's menu, accept app delegate events from the OS, and define a mini version of the app when a user taps the application's icon when the app is not in focus.

```html
<div class="ui-application">
  <script language="javascript">
    function $(this.id)(view) {
      function showAbout() {
        // ... show about controller
      }
      this.showAbout = showAbout;

      // ... other functions omitted

      // Application life-cycle methods
      function applicationDidStart() {
        // Make network calls here...
        let ctrl = os.ui.makeController("TestHome");
        ctrl.show();
      }
      this.applicationDidStart = applicationDidStart;
    }
  </script>
  <div class="ui-menus">
    <div class="ui-menu" style="width: 180px;">
      <select>
        <option>Test Management</option>
        <option onclick="$(this.controller).showAbout();">About</option>
        <option class="group"></option>
        <option onclick="$(this.controller).showSettings();">Settings</option>
        <option class="group"></option>
        <option onclick="$(this.controller).quit();">Quit Test Management</option>
      </select>
    </div>
  </div>
  <div class="ui-app-menu">
    <div class="ui-menu" style="width: 180px;">
      <select>
        <option>img:$(app.resourcePath)/icon.svg</option>
        <option onclick="os.switchApplication('$(app.bundleId)');">Switch application</option>
      </select>
    </div>
  </div>
  <!-- Alternatively, you can have a window that displays in-place of a
       drop-down menu. This would be defined in the application's bundle. -->
</div>
```

`ui-application` objects are not visible. They are simply a container for application specific configuration. However, they follow the same pattern as `UIController`s, in that they require their function name to be provided by OS, and HTML elements may refer to the window's controller instance using `$(this.controller)`.

### `UIApplication` Lifecycle Events

The application will call these lifecycle events in this order

- `applicationDidStart`
- `userDidSignOut` - Called when user signs out of the OS
- `userDidSignIn` - Called when user signs in to the OS
- `applicationDidStop`

## `UIController`

Controllers provide the necessary metadata for the window being rendered, what is being rendered in the window (the `view`), and the respective controller code for the window (the `source`).

Please refer to the [UIControllerConfig](/boss/public/boss/ui.js) for a list of all controller configuration options.

There are two types of controllers:
- Local: The `UIWindow` is contained in the app's respective public `controller` folder e.g. `/public/boss/app/io.bithead.boss-code/controller/Editor.html`
- Remote: The `UIWindow` is rendered by a server-side call e.g. `https://www.example.com/api/user-info`

These are explained in more detail below

### `UIController` Lifecycle Events

- `viewDidLoad`: Called before view is rendered
- `userDidSignOut`: Called when user signs out of the OS
- `userDidSignIn`: Called when user signs in to the OS
- `viewWillUnload`: Called before removing the completely

> When a user signs out, system application (currently only the BOSS app) `UIController`s will _not_ be closed. However, they will recieve the `userDidSignOut` event. In this context, the system `UIController` can choose if it wishes to close itself or not.

### Local Controller

Local controller content is stored at `/boss/app/<bundle_id>/controller/<controller_name>.html`.

### Remote Controller

Controllers may be bundled with the app _or_ rendered server-side. Set the `path` variable of the controller config to have the OS request your controller from the server.

If `remote` is set, the consumer displaying the controller _must_ provide a remote path to the resource when loading the controller or an error will ber shown to the user.

```javascript
// Note: The second parameter to loadController is the resource path to
// the controller, rendered server-side.
let win = await $(app.controller).loadController("TestSuite", `/test/test-suite/${testSuiteId}`);
```

Setting the `remote` flag ensures the consumer is aware of this requirement.

The main controller, set by `application.main`, must _not_ have the `remote` flag set. The behavior for this state is currently undefined.

Lastly, setting the `remote` flag makes it clear in the `application.json` that the controller's path will be provided at run-time.

### Working with `UIController`s

Technically, when you load a controller, you're provided with the controller's container. I will refer to the controller's container as simply the "window."  Indeed, the object you receive from `loadController` is the top-level `.ui-window` element which contains the script (controller) and window contents.

After loading the window, you will have access to both the UI related functions (showing, hiding, etc.) as well as the window's controller.

To configure and show a window:
```javascript
// Load the controller's window container
let win = await $(app.controller).loadController("SearchResults");

// Show the window and configure the controller once it is loaded in DOM
win.ui.show(function (ctrl) {
  ctrl.configure([{id: "TC-1", name: "TC-1: My test case"}]);
});
```

### Embedded `UICcontroller`s

A `UIController` may be embedded in the root `UIWindow`. Such that, you may have multiple `UIController`s in a single `UIWindow`. This is great for apps that need to switch their content within a single view. Refer to the Wordy app `/public/boss/app/io.bithead.wordy` for an example.

> `UIController`s may only be embedded one level deep! In other words, you may not have an embbedded `UIController` in another embbedded `UIController`.

```html
  <div class="container vbox gap-10">
    <div class="ui-controller" id="wordySplash">
      <script type="text/javascript">
        function wordySplash(view) {
          function showSignIn() { ... }
          this.showSignIn = showSignIn;

          function showCreateAccount() { ... }
          this.showCreateAccount = showCreateAccount;
        }
      </script>
      <p>Welcome to Wordy! Please sign in.</p>
      <div class="controls">
        <button class="default" onclick="%(wordySplash).showCreateAccount();">Create account</button>
        <button class="default" onclick="%(wordySplash).showSignIn();">Sign in</button>
      </div>
    </div>
  </div>
```

For convenience, the view may reference its respective embedded `UIController`. This is done using the controller reference command, `%(controllerName)`. For example, `%(wordySplash)` will be replaced with `os.ui.controller.wordySplash` -- the OS's way of referencing the instance of the `wordySplash` controller.

Things to note
- Every embedded controller must have an `id`. This is different than the root controller, where the ID is auto-generated.
- The root function name of the `UIController` must match the name of the `id`. Because it must be valid Javascript, you can not use kebab-style names.
- Use the convenience controller reference command to reference the instance of the controller w/in the respective view
- Embedded controllers receive life-cycle events

### Load an OS controller

There are special OS controllers for showing warnings, errors, etc. They can be loaded using `os.ui.show<ControllerName>` where `ControllerName` is the name of the BOSS controller in `/public/boss/app/io.bithead.boss/controllers/<ControllerName>.html`. e.g. `os.ui.showAlert("My alert message");` will show a BOSS alert modal with the text `My alert message` as the body of the modal.

## Application OS bar view

By default, tapping an application in the OS bar will switch the application context to the respective app immediately. However, an application may instead show a mini app when clicked. This view can display anything. It can be a menu or a miniaturized view of the app. e.g. a "mini player" for a music app.

> TODO: Add `ui-menu` to `Application.html` to show menu
> TODO: Add `ui-app-menu` to `Application.html` to show app menu

## Bundle contents

When an application is bundled, all of its controllers, configuration, and resources are bundled in a `<bundle_id>.zip` file. This `zip` file is extracted on the server and installed in the system. For now, it can be accessed via the OS system menu > Applications.

### Bundle Taxonomy

root
- application.json (App and controller configuration)
- controller (Folder that contains all controller HTML)
- icon.svg (App icon. The icon live anywhere in the bundle. This is just an example.)

Please refer to this respository's folder `/public/boss/app` for examples of the application structure.

## Installing an application

TBD: There will be a way to either install an app via the Boss Store or from an external URL.

## Godot Applications

Godot is an open source game engine that allows you to export your games to multiple platforms, including the web.

To create an app that can be used in BOSS, follow these steps

> This tutorial usees the the open source project GodSVG for all examples. Please replace any GodSVG specific configuration with your own app's configuration.

- Export your game to Web5 w/ in Godot
- Create a directory in `boss/public/boss/app/<your_bundle_id>` e.g. `boss/public/boss/app/com.mygame.web`
- Copy the exported contents to the app folder you just created
```
File contents should look something like the following
- com.mygame.web
  - MyGame.appl...ouch-icon.png
  - MyGame.audio.worklet.js
  - MyGame.html
  - etc.
```
- Create file `application.json`, within `com.mygame.web` app folder, with the following configuration. Please replace your application's bundle ID, version, author, and other information to match your game's description.
```javascript
{
    "boss": {
        "version": "1.0.0"
    },
    "application": {
        "bundleId": "com.mygame.web",
        "name": "MyGame",
        "version": "1.0-alpha7",
        "icon": "MyGame.icon.png",
        "main": "Godot",
        "author": "Your name",
        "copyright": "Copyright (c) 2023 Company Name",
        "quitAutomatically": true
    },
    "controllers": {
        "Godot": {
            "main": "MyGame.html"
        }
    }
}
```
- Godot games have a special BOSS controller called `Godot`, as seen above.
  - The `application.main` property must be set to `Godot`
  - The `controllers.Godot.main` property must be set to the HTML file used to run your game. e.g. `MyGame.html`
- Add your app to the list of installed BOSS apps. Go up one directory and edit the `boss/public/app/installed.json` file. Add your app's information in the list of installed apps:
```javascript
{
    ...
    "com.mygame.web": {"name": "MyGame", "icon": "MyGame.icon.png"},
    ...
}
```

Open your browser, refresh BOSS and your app will now be visible in the `Applications` app.

### Godot Technical Details

Godot apps are displayed in an `iframe` so that their resources may be completely removed from the BOSS context when closed.
