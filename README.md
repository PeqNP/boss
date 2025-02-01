# Bithead OS aka BOSS

Coming soon...

## What is Bithead OS?

A system to make web apps look like a native Mac System 2bit OS applications.

- Launch apps from the `Applications` menu
- Uses familiar UI language that customers can easily understand and use
  - It is designed to be pixel perfect with Mac System 2 UI components. Refer to the HIG to make apps that behave ubiquitously.
- Easily install apps on your server from `Applications`
  - If there's interest, I may add a `Web App Store`

Signalling patterns are inspired by iOS's `UIKit`. It's a suprisingly good pattern for web apps (delegation and full view lifecycle events).

## How can I see the OS?

You can test the OS from [bithead.io](https://bithead.io).

To see available components, visit [bithead.io](https://bithead.io/boss/components.html).

Newer components may be in development. To see latest features, clone this repository, and run a python server from the root directory:

```bash
$ python3 -m http.server 8080
```

Then access the resources from

- `http://localhost:8080/boss/components.html` for all supported components
- `http://localhost:8080/boss/window.html` for windows and modals
- `http://localhost:8080/boss/fullscreen.html` for fullscreen windows

## Documentation

A [working spec](docs/spec.md) shows the data structures required to create an app and its controllers.

This is a work in progress. Updates, and tutorials, will be shared on [X.com](https://x.com/bitheadrl).

## Tests

This comes with a Selenium Python testing library with an abstraction layer to easily interact with BOSS components. We use this library to test our own apps.

> The script to run tests is not currently functional. This is due to tests being in a different repository. Tests will eventually move into the proper repository.

## Install

Please refer to [Installation](/docs/install.sh).
