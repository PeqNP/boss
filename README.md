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

- Signalling patterns are inspired by iOS's `UIKit`
  - It's a surprisingly good pattern for web apps (delegation and full view lifecycle events)
- Any backend can be used to render and send content to the OS. I use Swift + Vapor.

## How do I test it?

You can find the examples on [bithead.io](https://bithead.io/boss/components.html).

If you want the most up-to-date features, run a simple python server from the root directory:

```bash
$ python3 -m http.server 8080
```

- `http://localhost:8080/boss/components.html` for all supported components
- `http://localhost:8080/boss/window.html` for windows and modals
- `http://localhost:8080/boss/fullscreen.html` for fullscreen windows

## How does it work?

There is a [working spec](docs/spec.md) that shows the data structures required to create an app and its controllers.

This is a work in progress. Updates, and tutorials, will be shared on [X.com](https://x.com/bitheadrl).

## Tests

This also comes with a testing layer that provides an abstraction layer around Selenium. This library is what I use to test UI pages made with BOSS.

### Usage

WIP

### Install

> The script to run tests is not currently functional.

```bash
$ brew install python3 openssl
```

> Note: Installing openssl _before_ creating a virtual environment ensures `python3` links to `openssl` instead of using the sysystem-install `libressl`, which is incompatible with `urllib3`.

This will install a version of Python where packages may not be installed except through a virtual env.

```bash
$ python3 -m venv create ~/.venv
$ source ~/.venv/bin/activate
$ pip3 install --upgrade pip
$ pip3 install -r requirements.txt
```

Run tests

```bash
$ ./run_tests
```
