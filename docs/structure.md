# Structure

Root directory

```
docs - documentation
public - BOSS public apps (JavaScript)
private - BOSS app web services (Python)
swift - Swift+Vapor app for authentication and Test Manager service
test - UI testing framework
```

## BOSS Applications

The `public` folder is expected to have the following structure:

```
public
  - boss
    - app
      - installed.json
      - *BOSS apps live here* An app groups its files by its bundle ID
  - upload
  - codemirror
  - swagger
  - index.html
```

BOSS applications are stored in `public/boss/app`. e.g. BOSSCode is stored at `public/boss/app/io.bithead.boss-code`.

`public/boss/app/installed.json` defines which applications are installed. If your app is not in this file, it can not be opened from within the desktop, even if the application is in its respective app bundle ID folder.

The BOSS Installer manages this file for you if you install from the OS.

`public/boss/upload` is an area where apps may store uploaded user content. For example, Test Manager needs to upload files that are associated to test suites. This data is stored in `/upload/io.bithead.boss-code/media`.

## BOSS Web Services

Web services are stored in `private/app`. e.g. The BOSSCode web server is stored in `private/app/io.bithead.boss-code`.

```
private
  - app
    - *Boss servics live here* An app groups its fils by its bundle ID
  - api.py - Loads all app service modules
  - start - Start services
  - stop - Stop services
  - restart - Restart services
```

In order to run web services, you must first [Install BOSS](/docs/development.md).

The installation process will eventually be automated. For now, make sure to update the `nginx.conf` to point to the resource path and port of your web server. More info on `nginx` can be found in [Install BOSS](/docs/development.md) doc).

## BOSS Selenium UI Testing

Selenium UI tests are in `test/`. Refer to [Test Boss UI](/docs/testing.md) for more information on testing

## BOSS Sandbox

Some apps may want to store long-term data. This may include user preferences, etc. In order to facilitate this, a `sandbox` directory is provided per app. The path to the sandbox is defined in `~/.boss/config`. e.g. If the sandbox lives in `~/tmp/sandbox`, BOSSCode's sandbox will be located in `~/tmp/sandbox/io.bithead.boss-code`.
