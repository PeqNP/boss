# Structure

```
docs - documentation
sandbox - BOSS sandbox for applications
web/app - BOSS web services
web/selenium - UI testing framework
```

## BOSS Applications

The `public` folder is expected to have the following structure:

```
public
  - boss
    - app
      - installed.json
  - codemirror
  - swagger
  - index.html
```

BOSS applications are stored in `public/boss/app`. e.g. BOSSCode is stored at `public/boss/app/io.bithead.boss-code`.

`public/boss/app/installed.json` defines which applications are installed. If your app is not in this file, it can not be opened from within the desktop, even if the application is in its respective app bundle ID folder.

The BOSS Installer manages this file for you if you install from the OS.

## BOSS Web Services

Web services are stored in `web/app`. e.g. The BOSSCode web server is stored in `web/app/io.bithead.boss-code`.

In order to run web services, you must first [Install BOSS](/docs/install.md).

The installation process will eventually be automated. For now, make sure to update the `nginx.conf` to point to the resource path and port of your web server. More info on `nginx` can be found in [Install BOSS](/docs/install.md) doc).

This folder also contains:

- scripts to start, stop, and restart the web services.
- Selenium UI testing library - refer to [Test Boss UI](/docs/testing.md) for more information on testing

## Application Sandbox

Applications, such as BOSSCode, may write long-term data to disk via their respective web service. This data is stored in `sandbox`. e.g. BOSSCode's data is stored in `sandbox/io.bithead.boss-code`.
