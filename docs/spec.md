# BOSS application spec


When an application is bundled, all of its controllers, configuration, and resources are bundled in a `<bundle-id>.zip` file. This `zip` file is extracted on the server and presented as an "installed app" on the user's desktop.

An application may also be associated to users. Therefore, even if an app is installed on the server, a user may not have access to it.

Some configuration, such as logos, will refer relatively to the resource inside its bundle directory. However, when downloaded to client browser it will expand to something like `/app/<bundle-id>/image/logo.svg`.

In all other contexts, such as controller logic, you may refer to any resource in your app's bundle by prepending `/app/<bundle-id>/` to the HTTP resource path or interpolating the app's resource path using `${app.resourcePath}` e.g. `<img src="${app.resourcePath}/img/icon.png">`.

```yaml
file: application.yaml

application:
  bundle-id: io.bithead.boss
  name: Test Management
  version: 1.0.0
  # Logos must be SVG. They will be shown in the OS bar, desktop icon, etc.
  #
  # If the application bundle has an `image` directory, you may refer
  # to the logo inside that directory with the following:
  icon: image/logo.svg
```

Controllers may be bundled with the app _or_ rendered server-side and provided in the following structure. In this way, BOSS provides ultimate flexbility in how you want to render your app and reduces the amount of data stored on the client.

> Singletons are not enforced if controller is fully rendered server-side.

If the controller _is_ bundled with the app they may be instantiated via `os.ui.makeController("name")`. This will look in the application's controller registery and instantiate the respective controller.

After a controller is created, you must show it. Call `show`. This will start the chain events to load, and display, the controller.

```yaml
file: application.yaml

controllers:
  #
  # This is an example of a fully client-side rendered controller. The instance
  # ID is created by the OS. To reference a function in the window's respective
  # controller, provide `window.controller` in every context where a function
  # is called. e.g. `${window.controller}.edit();` expands to
  # `os.ui.controller.<window_instance_id>.edit();`.
  #
  # The controller `function` controller _must_ interpolate the value of the
  # window's instance ID. This is done with `function ${window.id}(view)`.
  #

  # Name must be unique across all other controllers in the app. This is how
  # singletons are enforced.
  - name: TestHome
    # Bundling view and source is `true` by default
    bundle-view: true
    bundle-source: true
    title-bar:
      title: Test Home
      show-close-button: true
      show-zoom-button: true
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
    # A controller's view. This is HTML source. Perhaps in the future BOSS
    # will support something like [clay](https://github.com/nicbarker/clay).
    view: |
<h1>Test Management</h1>

<div class="hbox gap-10">
  <div class="list-box" style="width: 300px; height: 400px;">
    <select name="project-tree">
      <option value="TS-1">TS-1: Account</option>
      <option value="TC-5" class="child">TC-5: Sign in</option>
    </select>
</div>
<div class="vbox separated" style="width: 140px;">
  <!-- Example showing how you can reference an image inside the app bundle's resource path -->
  <img src="${app.resourcePath}/img/app-image.png">

  <div class="vbox gap-10">
    <button class="primary" onclick="${window.controller}.addSuite();">Add Suite</button>
    <button class="primary" onclick="${window.controller}.delete();">Delete</button>
  </div>
  <div class="vbox gap-10">
    <button name="edit" class="default" onclick="${window.controller}.edit();">Edit name</button>
    <button name="show-editor" class="primary" onclick="${window.controller}.showEditor();">Editor</button>
    <button name="copy-all" class="primary" onclick="${window.controller}.copyAllToPasteboard(this);">Copy</button>
    <button name="copy-link" class="primary" onclick="${window.controller}.copyLinkToPasteboard(this);">Copy Link</button>
  </div>
</div>
    # A view's controller logic. This is Javascript source. A controller is
    # assigned a unique instance ID to avoid ambiguity of a window of the
    # same type.
    source: |
function ${window.id}(view) {
  let editButton;
  let tree;
  let projectID;

  function addSuite() {
    os.network.request('/test/test-suite?projectID=${projectID}');
  }

  function edit() {
    // ...
    os.network.request(`/test/test-suite/${_id}`);
  }
  this.edit = edit;

  function _delete() {
    // ...
    os.network.delete(`/test/test-suite/${_id}`, "Are you sure you want to delete this test suite? This will delete all test cases. This is action is not recoverable.", function() {
      os.network.request("/test/test-suites/${projectID}");
    });
  }
  this.delete = _delete;

  function showEditor() {
    // ...
  }
  this.showEditor = showEditor;

  function copyLinkToPasteboard(button) {
    // ...
    os.copyToClipboard(button, url);
  }
  this.copyLinkToPasteboard = copyLinkToPasteboard;

  function copyAllToPasteboard(button) {
    let option = tree.ui.selectedOption();
    os.copyToClipboard(button, option.innerHTML);
  }
  this.copyAllToPasteboard = copyAllToPasteboard;

  function viewDidLoad() {
    editButton = view.ui.input("show-editor");
    tree = view.ui.input("project-tree");
  }
  this.viewDidLoad = viewDidLoad;

  // This can be called by controllers who create an instance of the controller.
  // This can be called before the controller is displayed.
  function configure(_projectID) {
    projectID = _projectID;
  }
  this.configure = configure;
}
    menus:
      - name: File
        options:
          # Names are HTML, allowing a menu item to display in any way you like
          - name: Add suite
            source: ${window.controller}.addSuite();
            # Displayed to the far right of menu. This will activate menu item
            # when combination pressed. WIP: I'm not sure if this will be
            # supported.
            hot-key: &#x2318; + N
          # Used to create dividers between options. If `type` isn't provided,
          # an option defaults to `standard`.
          - type: divider
          - name: Close
            source: ${window.controller}.close();
            # Checked will show the checkmark next to an option in the menu.
            # It's not relavant in this context. It's only here to show that
            # it exists.
            checked: true
            disabled: true
    # Optional stylesheets to load before VC is shown. If stylesheet was
    # loaded by another controller, this will use the cached version.
    # The path to the resource is relative to the `/app/<bundle-id/` path.
    stylesheets:
      - /test/styles.css
      - /editor/styles.css
    # Optional Javascript sources to load before VC is shown. Similar to
    # stylesheets, these are cached.
    sources:
      - /test/main.js
      - /editor/editor.js
    # These are buttons displayed in the scrollbar. WIP: Not sure if this will
    # be supported.
    scroll-bar:
      # Displayed on the left of the horizontal scroll bar
      - horizontal:
        - icon: /img/edit.svg
          source: ${window.controller}.edit();
      # Displayed on the top of the vertical scroll bar
      - vertical:
        - icon: /img/edit.svg
          source: ${window.controller}.edit();
```

To get all the benefits of the OS, you can bundle a controller that provides the structure of the controller, but not its `view`. To load a window's view, a controller may implement the `initialize` delegate callback. This is an `async function` that queries a server for the controller's view contents before the window is loaded. Below shows how this can be accomplished.

> The server may optionally render the `source` as well.

```yaml
file: application.yaml

  - name: TestProjects
    title-bar:
      title: Projects
      show-close-button: true
      show-zoom-button: true
    size:
      width: 400
      height: 500
    singleton: true
    # In the future, this boolean will be used by BossCode to avoid bundling
    # the controller's view into the application.
    bundle-view: false
    # A controller's source may also not be bundled. When this happens, only
    # the `initialize` function is bundled with the source.
    bundle-source: false
    view:
    source:
function ${window.id}(view) {
  async function intialize() {
    // Call server to render HTML and/or source.
    return {
        view: "html contents",
        source: "source contents"
    }
  }
}
```
