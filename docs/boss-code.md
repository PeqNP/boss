# BOSSCode

BOSSCode is an IDE that allows you to develop BOSS apps.

It provides:

- A simple UI, and project structure, to develop BOSS apps
- Directly preview controllers w/o needing to open the app or navigate to where the controller is within the app
- Works great with other dev environments. You can modify the files locally on disk and the IDE will auto-load the contents of the file before previewing the app.

BOSSCode apps are stored in `public/boss/app`. You will find all BOSS apps including BOSS core, Test Manager, BOSSCode, etc. apps in this directory.

TODO: Export and install your BOSS apps on a remote server.

## Developing Apps

My dev environment:

- macOS
- `vim`
- `Warp`
- Opera web browser (I also use Arc and Safari for testing)

I currently run the BOSS system on my local machine to develop apps. You can use the editor in BOSSCode, but I use `vim` to modify the files directly on disk. BOSSCode is smart enough to reload the controller from disk before previewing it. Therefore, it's perfectly fine to work on controllers outside of BOSSCode.

Where BOSSCode truly shines is being able to preview a controller w/o having to navigate through an entire app flow. You can also configure how your controller is previewed! For example, you can make a network request to fetch a data model, and then display your controller.

To debug your apps, use the built-in `Developer Tools` that come included with your browser.

## Sources Structure

BOSS works with "controllers" (similar to `UIController`s in iOS). There are three types of controllers:

- Application controllers (Combines `UIApplication` and `AppDelegate`) - This is an optional controller an app may have to provide resources for injection, global application menus, mini apps (when the app is not focused), and receives OS system calls. e.g `applicationDidStart`, `applicationDidStop`, etc.
- Window - The primary BOSS controller -- the controller you will most likely use the most.
- Modal - A special type of window that prevents touches from outside the modal, until the modal is dismissed.

Now we can talk about how BOSS groups these controllers in the Chromium Developer Tools. Open the Developer Tools > `Sources`. There you will see BOSS resources grouped by their type including:

- `application` - BOSS Application controllers
- `boss` - public HTML directory
- `io.bithead.*` - Each folder represents an app's group of controllers e.g. `io.bithead.boss-code` will contain all BOSSCode window and modal controllers
- `index.html` - boot loader

## Debugging & Interacting with Controllers

When a window is loaded, it is assigned a unique ID by the OS. This is necessary to disambiguate it from other controllers of the same type.

Imagine you open the `BOSSCode` app and open the `Test Manager` app to show the `BOSSCode`'s `Editor` controller. You may see the following folder structure in the `Sources` tab:

```
- io.bithead.boss-code
 - Editor/Window_000009
   - 0
 - Splash/Window_000008
   - 0
```

The `Editor/Window_000009` is the instance of the respective `Editor` controller. If you want to interact with the instance of the controller, enter the following into the console:

```javascript
os.ui.controller.Window_000009.preview();
```

This will call the method `preview` on the `Editor` controller. This is a quick way to debug and inspect logic, with the aid of break points, for a given controller.

If you open another `Editor` instance, you will see the following in `Sources`:

```
- io.bithead.boss-code
 - Editor
   - Window_000009
   - Window_000010
 - Splash/Window_000008
```

Notice a new instance of the `Editor` is created and referenced with `Window_000010`.
