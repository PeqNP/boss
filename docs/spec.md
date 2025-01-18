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
    titleBar:
      title: Test Home
      showCloseButton: true
      showZoomButton: true
    # Controller should be treated as a modal. If controller is a modal,
    # several attributes are ignored : `size`, `singleton`, `menus`, `stylesheets`,
    # `sources`, and `scrollBar`. Default is `false`.
    modal: false
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
    # `name` is how this is enforced.
    singleton: true
    # Defines how the content should be rendered. Default is `html`. This is
    # also used to build the path of where the controller is located. Future
    # versions may support Clay.
    renderer: html
    menus:
      - name: File
        options:
          # Names are HTML, allowing a menu item to be displayed in any way you like
          - name: Add suite
            source: $(this.controller).addSuite();
            # Displayed to the far right of menu. This will activate menu item
            # when combination pressed. WIP: I'm not sure if this will be
            # supported.
            hotKey: &#x2318; + N
          # Used to create dividers between options. If `type` isn't provided,
          # an option defaults to `standard`.
          - type: divider
          - name: Close
            source: $(this.controller).close();
            # Checked will show the checkmark next to an option in the menu.
            # It's not relavant in this context. It's only here to show that
            # it exists.
            checked: true
            disabled: true
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

The controller's content is stored in `/boss/app/<bundle_id>/controller/<controller_name>.html`.

If the controller is bundled with the app they may be instantiated via `os.ui.makeController("name")`. This will look in the application's controller registery and instantiate the respective controller.

After a controller is created, you must show it. Call `show`. This will start the chain events to load, and display, the controller.

Controllers may be bundled with the app _or_ rendered server-side. In this way, BOSS provides ultimate flexbility in how you want to render your app and reduces the amount of data stored on the client.

> Singletons are not enforced if controller is fully rendered server-side.

You can access the `UIApplication'`s controller using `$(app.controller)`.

### Server-side rendered `UIController` view

To ensure the OS has full control over windows, you can bundle a controller that provides the structure of the controller, but not its `view`. To load a window's view, a controller may implement the `init` delegate callback. This is an `async function` that queries a server for the controller's view contents before the window is loaded. Below shows how this can be accomplished.

> The server may optionally render the `source` as well.

```yaml
file: application.yaml

  - name: TestProjects
    titleBar:
      title: Projects
      showCloseButton: true
      showZoomButton: true
    size:
      width: 400
      height: 500
    singleton: true
    # In the future, this boolean will be used by BossCode to avoid bundling
    # the controller's view into the application.
    bundle:
      view: false
      # A controller's source may also not be bundled. When this happens, only
      # the `init` function is bundled with the source.
      source: false
    view:
    source:
function $(this.id)(view) {
  async function intialize() {
    // Call server to render HTML and/or source.
    return {
        view: "html contents",
        source: "source contents"
    }
  }
}
```

This allows you to render complex views with a tool that's better suited for the job. For example, I use [Leaf](https://docs.vapor.codes/leaf/overview/).

## Application OS bar view

By default, tapping an application in the OS bar will switch the desktop context to the respective app immediately. However, an application may instead show a menu view when clicked. This view can display anything. It can be a menu or a miniaturized view of the app. e.g. a "mini player" for a music app.

```yaml
os-bar:
  view: |
<div>
  <button class="primary" onclick="$(this.controller).didTapSwitch();">Switch</button>
</div>
  source: |
function $(this.id)(view, context) {
    function didTapSwitch() {
        context.didSwitchApplication();
    }
    this.didTapSwitch = didTapSwitch;
}
```

> The OS bar view is a controller.

## Bundle contents

When an application is bundled, all of its controllers, configuration, and resources are bundled in a `<bundle_id>.zip` file. This `zip` file is extracted on the server and presented as an "installed app" on the user's desktop.

There is only one required file for an application bundle, `application.yaml`, and must live in the root of the folder.

All other files may be placed in any location that best fits your needs.

## Installing an application

TBD: There will be a way to either install an app via the Boss Store or from an external URL.
