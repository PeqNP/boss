# Structure

This document explains how the BOSS project is structured.

Root directory of repository:

```
docs - Documentation
public - BOSS public apps (JavaScript)
private - BOSS app web services (Python)
swift - Swift+Vapor app for authentication
test - UI testing framework
```

## BOSS Applications

The `public` folder has the following structure:

```
public
  - boss
    - app
      - installed.json
      - *BOSS apps live here*
  - upload
  - codemirror
  - swagger
  - index.html
```

BOSS applications are stored in `/public/boss/app` and all files related to a BOSS app must live in a folder that has the same name as its bundle ID. e.g. Tutorial is stored at `/public/boss/app/io.bithead.tutorial`.

`/public/boss/app/installed.json` defines which applications are installed. If your app is not in this file, it can not be opened from within the desktop, even if the application is in its respective app bundle ID folder. Therefore, when creating a new app, add your app information here.

The BOSS Installer manages this file for you if you install from the OS.

`/public/boss/upload` is an area where apps may store uploaded user content. For example, Test Manager (now deleted) uploaded files that are associated to test suites. This data is stored in `/public/boss/upload/io.bithead.tutorial/media`.

### BOSS Application

Using the Tutorial app for reference, its bundle ID is `io.bithead.tutorial`.

```
public/app/io.bithead.tutorial
  - application.json: Contains all controllers that are part of the app
  - controller: The folder that contains all controllers
  - icon.svg: The icon of the application
```

For more explanation on an application's directory structure, the specification for `application.json`, etc. please refer to `/docs/app-structure.md`.

## BOSS Private Web Services

Explanation of private web service directory structure:

```
private
  - app
    - *Boss application services live here*
  - api.py - Loads all app service modules
  - start - Start private services
  - stop - Stop private services
  - restart - Restart private services
```

BOSS private application web services are stored in `/private/app` and all files related to the app web service must live in a folder that has the same name as its bundle ID. e.g. The Wordy web server is stored in `/private/app/io.bithead.wordy`.

A public BOSS app (e.g. `/public/boss/app/io.bithead.tutorial`) does not require private web service. Similarly, a private BOSS web service does not require a public BOSS app -- although I have not see any use case for this.

In order to run web services, you must first [Install BOSS](/docs/install-instructions.md).

The installation process will eventually be automated. For now, make sure to update the `nginx.conf` to point to the resource path and port of your web server. More info on `nginx` can be found in [Install BOSS](/docs/install-instructions.md) doc).

## BOSS Selenium UI Testing

Selenium UI tests are in `test/`. Refer to [Test Boss UI](/docs/testing.md) for more information on testing

## BOSS Sandbox

Some apps may want to store long-term data. This may include user preferences, etc. In order to facilitate this, a `sandbox` directory is provided per app. The path to the sandbox is defined in `~/.boss/config`. e.g. If the sandbox lives in `~/tmp/sandbox`, Wordy's sandbox will be located in `~/tmp/sandbox/io.bithead.wordy`.
