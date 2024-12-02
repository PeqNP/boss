# Bithead OS aka BOSS

Coming soon...

## What is Bithead OS?

A small library to make web apps that look like a native Mac System 2 OS application.

- Launch "apps" from your "desktop"
  - Each service you provide can be an "app" a customer launches from their desktop
- Use a familiar UI language that both you and your customers can easily use and understand
  - It is designed to be pixel perfect with Mac System 2 UI components. Refer to the HIG to make apps that behave ubiquitously.
- Easy to "install" apps on your server. Point to a library's "app" URL and the OS will install the app.
  - If there's interest, I may even add a WebApp Store

**Technical:**

- Signalling patterns are heavily inspired by `UIKit`
  - It's a surprisingly good pattern for web apps (delegation and full view lifecycle events)
- Any backend can be used to render and send content to the OS. I use Swift + Vapor.

## How do I test it?

Run a simple python server from the root directory:

```bash
$ python3 -m http.server 8080
```

Point to `http://localhost:8080/boss/components.html` for all supported components. To see supported and window and modals, `http://localhost:8080/boss/window.html`.

I don't have time to fix all of the examples.

## How does it work?

I'm still working out the details. This is the current structure of a DOM element that provides a basic window with content.

```html
<!-- The `.window` `id` and `function` name must be the same.
     If you expect multiple instances of the same window, the `id` must be unique. -->
<div class="window" id="MyController">
  <script language="javascript">
    function MyController(view) {
      function save() {
        let name = view.querySelector("input[name='name']");
        let request = {
          id: 1,
          name: name.value
        };
        // Make a POST request that saves a Project with an ID of 1 and the name
        // derived from the form field. A JSON object is always returned.
        os.network.post('/test/project', request, function(response) {
          // Redirect back to the home page
          os.network.redirect('/test/');
        });
      }
      this.save = save;

      function cancel() {
        os.network.redirect('/test/');
      }
      this.cancel = cancel;

      function _delete() {
        // Like POST, you can also DELETE. There is also support for GET (obv), PUT,
        // uploading files, loading stylesheet and Javascript libraries when needed, etc.
        os.network.delete('/test/project/1', function(data) {
          os.network.redirect('/test/');
        });
      }
      this.delete = _delete;
    }
  </script>
  <div class="os-menus">
    <!-- Define which menus are shown in the top OS bar -->
    <div class="os-menu" style="width: 180px;">
      <select>
        <option>File</option>
        <!-- Make requests to your controller via `os.ui.controller.<ControllerName>.<function>();` -->
        <option onclick="os.ui.controller.MyController.save();">Save Project</option>
        <option class="group"></option>
        <option onclick="os.ui.controller.MyController.cancel();">Close Project</option>
      </select>
    </div>
  </div>
  <!-- The "minimize" and "close" title bar buttons exist, but not used in this context. -->
  <div class="top"><div class="title"><span>Project</span></div></div>
  <div class="container">
    <div class="text-field">
      <label for="name">Name</label>
      <input type="text" name="name" value="#(name)">
    </div>

    <div class="controls">
      <button class="primary" onclick="os.ui.controller.MyController.delete();">Delete</button>
      <button class="primary" onclick="os.ui.controller.MyController.cancel();">Cancel</button>
      <button class="default" onclick="os.ui.controller.MyController.save();">Save</button>
    </div>
  </div>
</div>
```

Here is what the above will render:
![Example window](docs/window-example.png)

This is a work in progress. I should have something more interesting to show in the coming weeks. When that happens, expect tutorials showing you how to configure every aspect of your app.

Have questions? <a href="https://x.com/bitheadrl">Contact me on X</a>.
