# Bithead OS aka BOSS

BOSS allows you to make web apps look like a native 2bit Mac OS applications.

![BOSS Desktop](/docs/img/desktop.png)

- Launch apps from the `Applications` menu
- Uses familiar UI language
- Easily install apps on your server from `Applications`
  - If there's interest, I may add a `Web App Store`

Signalling patterns are inspired by iOS's `UIKit`. It's a suprisingly good pattern for web apps (delegation and full view lifecycle events).

> This is a work in progress. Updates, and tutorials, will be shared on [X.com](https://x.com/bitheadrl).

## How can I test the OS?

You can test the OS by visiting [bithead.io](https://bithead.io).

To see available components, visit [bithead.io/components](https://bithead.io/boss/components.html).

Newer components may be in development. To see latest features, clone this repository, and run a python server from the `public` directory:

```bash
cd public
python3 -m http.server 8080
```

Then access the resources from:

- `http://localhost:8080/boss/components.html` for all supported components
- `http://localhost:8080/boss/window.html` for windows and modals
- `http://localhost:8080/boss/fullscreen.html` for fullscreen windows

> This is _NOT_ how you run an instance of BOSS! This is a simple way to see features w/o running BOSS web services.

## Documentation

- [Development Installation Instructions](/docs/development.md)
- [Server Installation Instructions](/docs/server.md) Use this to install BOSS on a Raspberry Pi, multipass VM instance, or AWS arm64 server
- [Supported UI Components](/docs/ui-components.md)
- [Project Structure](docs/project-structure.md) explains the project structure of this repository
- [App Structure](docs/app-structure.md) explains structure of a BOSS app including `UIApplication`, `UIController`, et al

## Testing

This comes with a Selenium Python testing library with an abstraction layer to easily interact with BOSS components. We use this library to test our own apps.

Please find Selenium tests in `test`. Refer to [Installation](/docs/install.md) for more direction.
