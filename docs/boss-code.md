# BOSSCode

BOSSCode is an IDE that allows you to create new BOSS apps.

It provides:

- A simple UI, and project structure, to develop BOSS apps
- Directly preview controllers w/o needing to open the app or navigate to where the controller is within the app
- Works great with other dev environments. You can modify the files locally on disk and the IDE will auto-load the contents of the file before previewing the app.

BOSSCode apps are stored in `sandbox/io.bithead.boss-code`. You will find the BOSS core, test manager, and BOSSCode apps.

This is the _development_ location for apps. To install BOSS apps, you must copy them to the `public/boss/apps`. This allows you to develop your apps in the sandbox and then push your changes publicly when they're ready to deploy.
