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

Tap on the BOSS OS menu (top left icon) and then tap `Show tutorial`. This will open the Tutorial application, which shows all BOSS UI components and several examples showing how to interact with various parts of the BOSS system.

## Documentation

- [Development Installation Instructions](/docs/install-instructions.md) Includes GitHub CLI and GH-AXI setup required before development work
- [Server Installation Instructions](/docs/server.md) Use this to install BOSS on a Raspberry Pi, multipass VM instance, or AWS arm64 server
- [BOSS Project Structure](docs/structure.md) describes the project structure of this repository
- [App Structure](docs/app-structure.md) explains the structure of a BOSS app
- [BOSS API](docs/api.md) lists all BOSS APIs including OS, UI, and Notification APIs

## Testing

UI tests run in a real browser with [Playwright](https://playwright.dev). They live in [`uitest/`](/uitest), along with a small helper layer for booting the OS and locating windows.

Every UI component is demonstrated in the Tutorial app's `Example` controller, so the component library can be exercised in a single pass. See [`uitest/README.md`](/uitest/README.md) to get set up.
