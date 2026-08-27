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

`/public/boss/app/installed.json` defines which applications are installed. The desktop opens what it lists, so add a new app's information here alongside its bundle ID folder.

The BOSS Installer manages this file for you if you install from the OS.

Files an app stores — uploaded or otherwise — live under the `media_path` from
`~/.boss/config`, outside the repository, in two directories per app:

```
<media_path>/io.bithead.tutorial/public     served by nginx at /media/io.bithead.tutorial/public/<file>
<media_path>/io.bithead.tutorial/private    reached through the app that owns it
```

The visibility is a directory rather than a flag, so a file cannot be in the
wrong one: nginx has no route into `private`. See
[`docs/prompt/python.md`](/docs/prompt/python.md) for the library that resolves
these paths and serves a private file once an app has authorised it.

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

A public BOSS app (e.g. `/public/boss/app/io.bithead.tutorial`) stands on its own, and so does a private BOSS web service -- although a service with no app in front of it is still looking for its first use case.

In order to run web services, you must first [Install BOSS](/docs/install-instructions.md).

The installation process will eventually be automated. For now, make sure to update the `nginx.conf` to point to the resource path and port of your web server. More info on `nginx` can be found in [Install BOSS](/docs/install-instructions.md) doc).

## BOSS UI Testing

UI tests use Playwright and live in `uitest/`. They drive a running BOSS server rather than starting one, so bring the stack up with `private/start` first. Refer to [`uitest/README.md`](/uitest/README.md) for setup and for how to add a test.

## BOSS Sandbox

Some apps may want to store long-term data. This may include user preferences, etc. In order to facilitate this, a `sandbox` directory is provided per app. The path to the sandbox is defined in `~/.boss/config`. e.g. If the sandbox lives in `~/tmp/sandbox`, Wordy's sandbox will be located in `~/tmp/sandbox/io.bithead.wordy`.
