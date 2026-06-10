# Debugging BOSS apps

## Debugging in the browser

BOSS defines the source URL for all window controllers. This allows you to debug your controllers in the Chromium developer `Sources` tab. For example, when you load the `public/boss/app/io.bithead.tutorial/controller/Example.html` window, its respective Javascript controller source will be referenced in `Sources` by the application's bundle ID, controller name, and its instance ID -- e.g. `io.bithead.tutorial/Example/Controller_000002/0`.

Godot controllers are slightly different. They are grouped under their respective `boss/app/<bundleId>` folder. For example, when loading the Godot controller, which is located at `public/boss/app/io.bithead.tutorial/controller/Godot.js`, you will find the source file at `boss/app/io.bithead.tutorial/controller/Godot.js` in the `Sources` tab.
