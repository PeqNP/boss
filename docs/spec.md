# BOSS spec

This provides the data structures necessary to create an app, and render windows, inside BOSS (Bithead Operating System).

## `UIApplication`

An application is the combination of base application configuration, controllers, and resources.

Below is the necessary configuration for an application.

```yaml
file: application.yaml

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
  # dialogs, etc. They are NOT visible to the user. They are not
  # shown in the list of installed apps.
  #
  # System level apps are like the BOSS app, which provides common
  # components that can be used by all apps as well as system-specific
  # modals, dialogs, and controls.
  #
  # Apps like the Image Viewer are _not_ system apps, but are included
  # with the system.
  #
  # System apps work in all application contexts. Therefore, all system
  # apps are also `passive` apps. (Refer to `passive` description below).
  #
  # System apps may NOT have menus or app menus (used for switching
  # apps).
  system: false
  # Logos must be SVG. They will be shown in the OS bar, desktop icon, etc.
  #
  # If the application bundle has an `image` directory, you may refer
  # to the logo inside that directory with the following:
  icon: image/logo.svg
  # This can be `application.html` or the name of a `UIController`.
  #
  # Using a `UIApplication` provides:
  # - More control over how the app loads.
  # - App menu. e.g. About, Settings, etc. Otherwise no menu shows.
  #
  # If using `application.html`, you are responsible for showing the first
  # view controller.
  #
  # Godot Web5 apps are also supported. To create a BOSS app, for your Godot
  # game, set `main` to `Godot`. Please refer to the `Godot application` section
  # for more information on how to configure the app.
  main: TestHome
  # The controller to display when the app's button (in the OS bar when blurred)
  # is tapped. An app may either define a controller to display, a ui-menu
  # defined in the application controller, or have no menu at all. In which case
  # the app button is automatically created.
  menu: MyMenu
  author: Eric Chamberlain
  copyright: 2025 Bithead LLC. All rights reserved.
  # Automatically quit the application when all windows are closed.
  # Default is `false`
  quitAutomatically: false
  # Passive apps indicate that the app is context-agnostic. In other words
  # it will not switch context and live in the same context as the current
  # app. This is useful for OS and admin tools.
  #
  # Passive apps do not receive the `applicationDidFocus` or `applicationDidBlur`
  # as they do not switch contexts.
  #
  # Passive apps may have a menu, but NOT have an app menu (for switching
  # app contexts).
  #
  # Default is `false`.
  passive: false
  # Defines the app as a system-level app. System apps are designed to provide
  # features used by all apps and can show windows in any app context. For 3rd
  # party apps that can be visible in any app context, make your app `passive`.
  system: false
```

Some configuration, such as logos, will refer relatively to the resource inside its bundle directory. However, when downloaded to the client's browser, it will expand to something like `/boss/app/<bundle_id>/image/logo.svg`.

In all other contexts, such as controller logic, you may refer to any resource in your app's bundle by prepending `/boss/app/<bundle_id>/` to the HTTP resource path or interpolating the app's resource path using `$(app.resourcePath)` e.g. `<img src="$(app.resourcePath)/img/icon.png">`. There is an example of how this works in the `UIController` section.

> The server may choose to limit which applications a user sees. Therefore, even if an app is installed on the server, a user may not have access to it.

Once an application is installed, the `application.yaml` file's data structure will be transformed into JSON for easy consumption by the client.

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

`ui-application` objects are not visible. They are simply a container for application specific configuration. However, they follow the same pattern as `UIController`s, in that they require their function name to be provided by OS and HTML elements may refer to the window's controller instance using `$(this.controller)`.

## `UIController`

Controllers provide the necessary metadata for the window being rendered, what is being rendered in the window (the `view`), and the respective controller code for the window (the `source`).

```yaml
file: application.yaml

controllers:
  #
  # This is an example of a fully client-side rendered controller. The instance
  # ID is created by the OS. To reference a function in the window's respective
  # controller, provide `this.controller` in every context where a function
  # is called. e.g. `$(this.controller).edit();` expands to
  # `os.ui.controller.<window_instance_id>.edit();`.
  #
  # The controller `function` _must_ interpolate the value of the window's
  # instance ID. This is done with `function $(this.id)(view)`.
  #

  # Name must be unique across all other controllers in the app. This is how
  # singletons are enforced.
  - name: TestHome
    # Bundling view and source is `true` by default. Bundling are future topics.
    # An IDE, called BossCode, will allow you to bundle in the view and source
    # inside the configuration, or omit it and be provided by the server when
    # needed.
    bundle:
      view: true
      source: true
    # This is optional. If this is null, the size of the window becomes the
    # intrinsic size of its content view.
    size:
      # Initial size of the window.
      width: 500
      height: 500
      # Optional maximum size. If not provied, OS defaults are used.
      max:
        width: 700
        height: 900
      # Optional minimum size. If not provided, OS defaults are used.
      min:
        width: 100
        height: 100
    # Only one instance of this type of window may be created. The controller's
    # `name` is how this is enforced. Default is `false`.
    singleton: true
    # Defines the controller as a modal window. Modals may not be moved and
    # will block all interaction with other windows until modal is dismissed.
    modal: false
    # Defines how the content should be rendered. Default is `html`. This is
    # also used to build the path of where the controller is located. Future
    # versions may support Clay.
    renderer: html
    # Server path where controller is rendered. By default this is `null`.
    # If path is not specified, the controller is located at
    # `/boss/app/<bundle_id>/controller/<controller_name>.html`.
    path: null
    # Indicates that the controller must be rendered server-side by a path
    # provided by consumer at the time of loading the controller. Default is
    # `false`. This supercedes `path` config.
    remote: false
    # Optional stylesheets to load before VC is shown. If stylesheet was
    # loaded by another controller, this will use the cached version.
    # The path to the resource is relative to the `/boss/app/<bundle_id>` path.
    stylesheets:
      - /test/styles.css
      - /editor/styles.css
    # Optional Javascript sources to load before VC is shown. Similar to
    # stylesheets, these are cached.
    sources:
      - /test/main.js
      - /editor/editor.js
    # Scrollbar button configuration.
    # Please note: To display scrollbars, your `div.ui-window` must have the
    # `resizable` class
    # TBD: These may be defined within the window's HTML, similar to the `ui-menus`.
    scrollbar:
      # Buttons displayed on the left of the horizontal scroll bar
      horizontal:
        - icon: /img/edit.svg
          source: $(this.controller).edit();
      # Buttons displayed on the top of the vertical scroll bar
      vertical:
        - icon: /img/edit.svg
          source: $(this.controller).edit();
```

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

### Working with Controllers

Technically, when you load a controller you're provided with the controller's container. I will refer to the controller's container as simply the "window."  Indeed, the object you receive from `loadController` is the top-level `.ui-window` element which contains the script (controller) and window contents.

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

## Application OS bar view

By default, tapping an application in the OS bar will switch the application context to the respective app immediately. However, an application may instead show a mini app when clicked. This view can display anything. It can be a menu or a miniaturized view of the app. e.g. a "mini player" for a music app.

TODO: Add `ui-menu` to `Application.html` to show menu
TODO: Add `ui-app-menu` to `Application.html` to show app menu

## Bundle contents

When an application is bundled, all of its controllers, configuration, and resources are bundled in a `<bundle_id>.zip` file. This `zip` file is extracted on the server and installed in the system. For now, it can be accessed via the OS system menu > Applications.

### Bundle Taxonomy

root
- application.json (App and controller configuration)
- controller (Folder that contains all controller HTML)
- icon.svg (App icon. The icon live anywhere in the bundle. This is just an example.)

Please refer to this respository's folder `boss/app` for examples of the application structure.

## Installing an application

TBD: There will be a way to either install an app via the Boss Store or from an external URL.

## Godot Applications

Godot is an open source game engine that allows you to export your games to multiple platforms, including the web.

To create an app that can be used in BOSS, follow these steps

> This tutorial usees the the open source project GodSVG for all examples. Please replace any GodSVG specific configuration with your own app's configuration.

- Export your game to Web5 w/ in Godot
- Create a directory in `boss/public/boss/app/<your_bundle_id>` e.g. `boss/public/boss/app/com.godsvg.web`
- Copy the exported contents to the app folder you just created
```
File contents should look something like the following
- com.godsvg.web
  - GodSVG.appl...ouch-icon.png
  - GodSVG.audio.worklet.js
  - GodSVG.html
  - etc.
```
- Create file `application.json`, within `com.godsvg.web` app folder, with the following configuration. Please replace your application's bundle ID, version, author, and other information to match your game's description.
```javascript
{
    "boss": {
        "version": "1.0.0"
    },
    "application": {
        "bundleId": "com.godsvg.web",
        "name": "GodSVG",
        "version": "1.0-alpha7",
        "icon": "GodSVG.icon.png",
        "main": "Godot",
        "author": "Mew Pur Pur",
        "copyright": "Copyright (c) 2023 MewPurPur",
        "quitAutomatically": true
    },
    "controllers": {
        "Godot": {
            "main": "GodSVG.html"
        }
    }
}
```
- Godot games have a special BOSS controller called `Godot`, as seen above.
  - The `application.main` property must be set to `Godot`
  - The `controllers.Godot.main` property must be set to the HTML file used to run your game. e.g. `GodSVG.html`
- Add your app to the list of installed BOSS apps. Go up one directory and edit the `boss/public/app/installed.json` file. Add your app's information in the list of installed apps:
```javascript
{
    ...
    "com.godsvg.web": {"name": "GodSVG", "icon": "GodSVG.icon.png"},
    ...
}
```

Open your browser, refresh BOSS and your app will now be visible in the `Applications` app.

### Godot Technical Details

Godot apps are displayed in an `iframe` so that their resources may be completely removed from the BOSS context when closed.
