The below specification provides a way to translate BOSS UI/UX, backend system, and middleware patterns into the respective code.

## App Specification

An app may be specified with the following specification:

```
Application: (Name of app)
	- Bundle ID: (Bundle ID)
	- Main: (Name of controller to first load)
	- Icon: (Icon path or `null`)
	- Author: (Author's name)
	- Copyright: (Copyright)
```

This, along with window and modal specs, are saved in the `application.json`. Refer to `/public/boss/app/io.bithead.boss/application.json` for an example structure.

## Window Specification

Use the following spec when building windows. Each of the element types are declared by name. All element types are listed in the `Example` controller at `/public/boss/app/io.bithead.boss/controller/Example.html`. Each element is identified using the format `(ID: <Element Name>)`. Such that `(ID: Popup)` references an element that defines the necessary structure of HTML elements, classes, etc. for the `ui-pop-up` element (which is also referred to in the BOSS UI library as `UIPopup`).

```
# The name of the window's controller. This name is an ID. If
# another controller requests to show the respective window, it shall provide
# this window's name. The `Application.Main` may also refer to
# this controller by name. Because the name of the controller is an ID,
# the name will always be a proper Javascript, camelcased, name. It's
# the only value you do not need to generate a name.
Window: (Window name)
	- Title: (Title name)
	# This is an optional attribute, that, when set, will show the button
	# to resize the window.
	- Zoom
	# Menus displayed when the window is in focus
	- Menus
	  - Menu: (Menu name)
		- (Option name): (Action will be defined here)
		# Adds a visual separator
		- Group
	# The body contains all of the elements and is wrapped in a `container`.
	- Body
		# Styles to apply to body. Anytime a `Style` attribute is seen, it
		# should use from the available styles in `/public/boss/styles.css`.
		- Style: (comma separated list of CSS class names or a "named" style)
		- Info Message: (Message to display)
		    # Any element may declare that they are initially hidden by
		    # providing the `Hidden` attribute. When `Hidden` attribute is
		    # declared, hide element in `viewDidLoad`. By default, do not hide.
			- Hidden
		- Error Message: (Message to display)
		- Message: (Message to display)
		- Text: (Field name)
		# Please note that only the first comma is significant. If a comma is
		# in the text displayed next to the checkbox, simply display it as-is.
		- Checkbox: (Field name), (Text displayed next to checkbox)
		# A list box attempts to make all options visible. A list box may
		# have styles applied. Alternatively, `Options` may be provided at
		# run-time. The `Field name` will be used when targeting the list box
		# for options to be added.
		- ListBox: (Field name)
		    - Style: (comma separated list of CSS class names)
		    - Options
				- (Option 1)
					- (Optionally add action here)
		# Popup menu may have N options. No options need to be provided.
		- Popup
			- (Option 1)
				- (Optionally add action here)
			- (Option 2)
			- (Option 3)
		- Hidden: (Field name)
		# List of buttons to display. They are displayed in the order
		# they are listed.
		- Controls
			- Default: (Name)
				- (Action will be defined here)
			- Primary: (Name)
				- (Action will be defined here)
			- Secondary: (Name)
				- (Action will be defined here)
	# Refer to `configure` for an example to see how a VC is configured
	# before loading is finished.
	- Configure
		- Parameters
			- (Type) (Name): (Description)
		- Action
			- (Action defined here)
	# Called when the view is loaded via OS signal `viewDidLoad`. The actions
	# defined here will always happen after elements are hidden.
	- Loaded
		- (Action defined here)
	# Action to perform when enter/return key is triggered
	- Enter: (Action defined here)
```

When rendering the window, the elements provided must be rendered in the order they are displayed in the body.

When creating HTML field names, use kebab format. Such that `Text: Name` field would be converted to `name` and `Hidden: Person ID` would be `person-id`.

When creating Javascript function names, variable names, etc. please use the standard (insert standard here - This may already be defined elsewhere).

By default, all windows have a close button. Therefore, it is not necessary to call it out. There is also no attribute for the close button.

### Actions

Actions must always be converted to a function that live in the respective controller code. The name of the function should be inferred based on what the action does. The function should be called when the respective action type (e.g. `onclick`) is invoked.

When referring actions to field names, the specification will either select the field type or the name of the field. The field name always supersedes the field type. The below examples shows how to select the field, by it's name:

```
Window: MyWindow
	- Title: Hello, World
	- Body
		- Style: Form
		- Text: Email
		- Text: Test
		- Controls
			- Default: OK
				# Shows how tapping OK sets the Email field with the value
				# of the field of Test.
				- Set the `Email` field value with the value provided in `Test`
```

This is an example showing the OK button action unhiding the `Info Message` field type to and displaying the message "Invalid password."

```
Window: MyWindow
	- Title: Hello, World
	- Body
		- Style: Form
		- Info Message:
			- Hidden
		- Controls
			- Default: OK
				# Shows how tapping OK shows the `Info Message` and sets
				# value to "Invalid password."
				- Unhide the `Info Message` and set its value to "Invalid password."
```

### Named Styles

In `Window.Body.Style`, this can be a list of CSS styles or reference a "named" style which represents a comma delimited list of styles that are commonly used together. When a named style is provided, the respective styles will be applied.

- Form: vbox, gap-10
- Dialog: hbox, gap-10


| Name   | Description                                                |
| ------ | ---------------------------------------------------------- |
| Form   | Used for form based windows and modals.                    |
| Dialog | Used for "Open" dialogs. Almost always contains a list of  |


Such that, if `Style: Form` is applied, `vbox gap-10` would be the classes assigned to the body of `div.class`. Refer to example.

### Example Specification

```
Window: MyWindow
	- Title: Hello, World
	- Zoom
	- Menus
		- Menu: File
			- OK: Close the window
			- Group
			- Show info: Show the Info message
	- Body
		- Style: Form
		- Info Message: This demonstrates how to build a window using the spec.
			- Hidden
		- Text: Email
		- Controls
			- Primary: Show info
				- Show the Info Message
			- Default: OK
				- Close the window
	- Configure
		- Parameters
			- String Message: Initial message to display to the user
		- Action
			- Set `Info message` value to the value of `Message` parameter.
	- Loaded
		- Write a console log with a string value of `Loaded`
	- Enter: Close the window
```

This will create a `MyWindow` controller within the respective app and add the controller within the `application.json` list of `controllers`.

Here is an example of the window controller being created.

```html
<div class="ui-window">
  <script type="text/javascript">
    function $(this.id)(view) {
      function closeWindow() {
        view.ui.close();
      }
      this.close = close;

	  /**
	   * @param {string} message - Initial message to display to the user
	   */
      function configure(message) {
        view.querySelector(".info .message").innerHTML = message;
      }
      this.configure = configure;

      function showInfoMessage() {
	      view.ui.div("info").style.display = null;
      }
      this.showInfoMessage = showInfoMessage;

      function viewDidLoad() {
	      view.ui.div("info").style.display = "none";
	      console.log("Loaded");
      }
      this.viewDidLoad = viewDidLoad;

      this.didHitEnter = close;
    }
  </script>
  <div class="ui-menus">
    <div class="ui-menu" style="width: 180px;">
      <select name="user-menu">
        <option>File</option>
        <option onclick="$(this.controller).closeWindow();">OK</option>
        <option class="group"></option>
        <option onclick="$(this.controller).showInfoMessage();">Show info</option>
      </select>
    </div>
  </div>

  <div class="top">
    <div class="close-button"></div>
    <div class="title">Title</div>
    <div class="zoom-button"></div>
  </div>
  <div class="container vbox gap-10">
    <div class="info">
      <p class="message">This demonstrates how to build a window using the spec.</p>
    </div>
    <div class="controls">
      <button class="primary" onclick="$(this.controller).showInfoMessage();">Show info</button>
      <button class="default" onclick="$(this.controller).closeWindow();">OK</button>
    </div>
  </div>
</div>
```

## Modal Specification

Modals use the same specification except as windows, except they use the `ui-modal` style, and follow a slightly different convention when displaying a title. Please refer to `/public/boss/app/io.bithead.boss/controller/Error.html` for an example of a modal's structure.

> Modals can not have the attribute `Zoom`.

## API Calls

A front end may also communicate with an application "private" backend. Refer to `/private/app/io.bithead.boss` for how private apps, and API calls, are structured. When creating an API, the documentation will indicate the request type and path to API. For example, `GET /api/io.bithead.boss/heartbeat` would reference the `@router.get("/heartbeat")` Python route in `/private/app/io.bithead.boss`.

An API spec will start with the following:

```
API: /api/io.bithead.boss
```

This indicates the root path of the API for this application (e.g. `/api/.io.bithead.boss`). Any reference to a backend call, that does not start with a `/api/`, should append the relative path to the respective application's root path. Using the heartbeat call earlier, if I used `GET /heartbeat`, it must refer to `/api/io.bithead.boss/heartbeat`.

Within the spec, you can also define individual API calls:

```
GET /heartbeat
	- name: GetHeartbeat
```

You can also associate parameters to an API call.

```
API: /api/io.bithead.boss

GET /heartbeat
	# You can refer to the API with a "name"
	- name: GetHeartbeat

GET /defaults
	- name: GetDefaults
	- description: (A description can be added here)
	# You can also pass values to the "name"
	- parameters
		# An example of a parameter that has a description
		- bundle_id: Bundle ID of the application
		# A parameter that has no description
		- user_id
		- key

GET /workspace
	- name: GetWorkspace
```

If I wanted to get the defaults I could use `GetDefaults("io.bithead.boss", 1, "my-key")`. Similarly, I could also pass in field values. e.g. If there is a `Text: Bundle ID`, a `Hidden: User ID`, and a `Text: Key` field, I can get the values using the following `GetDefaults(Field.Bundle ID.value, Field.User ID.value, Field.Key.value)`. The respective field values would be added as parameters, respectively.

I may also want to display the results of a response. Use the following full spec for reference:

When `GetWorkspace()` is called, it returns a dictionary of `desktop` and `dock` arrays. If I want to show all `desktop` apps in a `ListBox: My Field`, I might prompt, "Add options to `ListBox.My Field` from `GetWorkspace().desktop`". I expect the values to be transformed in a way that they will be listed in the list box. Here's an example:

```javascript
// Using the prompt "Display GetWorkspace().desktop in ListBox.My Field" it
// would produce something like the following:
let response = await os.network.get(`/workspace`);
let options = response.desktop.map(app => ({
	id: app.bundleId,
	name: app.name
	// icon: app.icon, ← add if/when you need it later
}));
view.ui.select("my-field").ui.addNewOptions(options);
```

## Code Generation Rules

If at any time a specification fails to follow the rules defined in this spec, do _not_ generate any code. Instead, please identify the exact discrepancy so that it can be fixed, along with a suggestion on how to fix it.

For example, if there is a `Modal` that contains the attribute `Zoom`, return an error telling the exact modal controller that has the discrepancy and a message such as "Modals may not have a Zoom attribute. Please remove it before continuing."

All controller code (HTML and Javascript) should be tabbed with two spaces.

If at any time you are unsure how to proceed with the given logic, put a placeholder in the code.

In Javascript with using the following format:

```javascript
// AI: Unable to determine how to do X (where X is the request in the spec)
```

In HTML:

```html
<!-- AI: Unable to determine how to do X (where X is the request in the spec) -->
```
