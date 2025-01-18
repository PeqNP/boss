/**
 * Provides application manager facilities.
 *
 * Purpose: To open, close, and manage application states.
 *
 * This creates application menus, mini application states (buttons displayed in
 * OS bar that switch applications), etc.
 */
function ApplicationManager(os) {
    // All BOSS apps. These apps can not be changed.
    // object{bundleId:{name:icon:system:}}
    let bossApps = {};

    // Registered apps that user has access to.
    // Same structure as `bossApps`.
    let registeredApps = {};

    // Represents any app that was loaded. Loaded apps are considered
    // to be running, even if their application context is not active.
    // {bundleId:UIApplication}
    let loadedApps = {};

    // The active application menu. This is the menu on the left (not the app menu
    // switch button). A passive and active application may live in the same context.
    // When switching between the two app types, the respective app menu needs
    // to be switched too.
    let activeAppMenu = null;

    // Defines the "active" application. When an application is "active", it
    // means the application has focus on the desktop. Active applications are
    // not system or passive apps.
    let activeApplication = null;

    // Stores application contexts. The HTMLElement is the container for all
    // of the application's windows.
    //
    // Object{bundleId:HTMLElement}
    let appContexts = {};

    function init(apps) {
        bossApps = apps;
        registeredApps = apps;
    }
    this.init = init;

    /**
     * Register applications available to BOSS.
     *
     * This helps display apps that a user has access to.
     *
     * This over-writes any previously registered applications.
     *
     * @param {object{bundleId:{name:system:icon:}}} apps - List of installed apps
     */
    function registerApplications(apps) {
        let rapps = {};

        // Re-create app list. Include only system apps.
        for (bundleId in bossApps) {
            let app = bossApps[bundleId];
            rapps[bundleId] = app;
        }

        // Add apps to list
        for (bundleId in apps) {
            if (bundleId in rapps) {
                console.log("You may not overwrite a system app");
                continue;
            }

            let app = apps[bundleId];
            if (app.system) {
                console.log("System apps may not be registered");
                continue;
            }
            rapps[bundleId] = app;
        }

        registeredApps = rapps;
    }
    this.registerApplications = registerApplications;

    /**
     * Returns all user-space installed applications.
     *
     * This is assumed to be used in a `UIListBox`. Therefore, `name` also
     * contains the application's icon.
     *
     * @returns [object{id:value:}]
     */
    function installedApplications() {
        let apps = [];
        for (key in registeredApps) {
            let app = registeredApps[key];
            if (app.system !== true) {
                let name = null;
                if (isEmpty(app.icon)) {
                    name = app.name;
                }
                else {
                    name = `img:/boss/app/${key}/${app.icon},${app.name}`;
                }
                apps.push({id: key, name: name});
            }
        }
        return apps;
    }
    this.installedApplications = installedApplications;

    /**
     * Returns bundle ID's application instance.
     *
     * @returns UIApplication?
     */
    function application(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            console.error(`Application (${bundleId}) is not loaded.`);
            return null;
        }
        return app;
    }
    this.application = application;

    /**
     * Open a BOSS application.
     *
     * TODO: Check if user has permission to access app.
     * TODO: Move this into an ApplicationManager.js - it's part of UI but does not need to live in there.
     *
     * @param {string} bundleId - The Bundle ID of the application to open e.g. 'io.bithead.test-management'
     * @returns UIApplication
     * @throws
     */
    async function openApplication(bundleId, fn) {
        let loadedApp = loadedApps[bundleId];
        if (!isEmpty(loadedApp)) {
            switchApplication(bundleId);
            return loadedApp;
        }

        if (!(bundleId in registeredApps)) {
            throw new Error(`Application (${bundleId}) is not installed. Make sure to register the app with the OS before attempting to open.`);
        }

        let progressBar = await os.ui.showProgressBar(`Loading application ${registeredApps[bundleId].name}...`);

        function showError(msg, error) {
            if (!isEmpty(error)) {
                console.error(error);
            }
            progressBar?.ui.close();
            throw new Error(msg);
        }

        let config;
        try {
            config = await os.network.get(`/boss/app/${bundleId}/application.json`);
        }
        catch (error) {
            showError(`Failed to load application bundle (${bundleId}) configuration.`, error);
        }

        let objectId = makeObjectId();
        let app = new UIApplication(objectId, config);
        loadedApps[bundleId] = app;

        // Application may contain app delegate and menus
        let hasAppController = Object.keys(config.controllers).includes("Application");
        // When `true`, the app controller defines its own menu. This
        // menu displays on left when app is focused.
        let hasMenu = false;
        // When `true`, app defines its own app menu. This menu displays
        // on the right of OS bar when app is blurred.
        let hasAppMenu = false;

        // Create container for all app windows
        let appContainer = document.createElement("div");
        appContainer.id = os.ui.appContainerId(bundleId);
        let desktop = document.getElementById("desktop");
        desktop.appendChild(appContainer);

        let controller;
        if (hasAppController) {
            let html;
            try {
                html = await os.network.get(`/boss/app/${bundleId}/controller/Application.html`, "text");
            }
            catch (error) {
                showError(`Failed to load UIApplication for application bundle (${bundleId}).`, error);
            }

            const attr = {
                "app": {
                    bundleId: bundleId
                },
                "this": {
                    id: app.scriptId,
                    controller: `os.application('${bundleId}').controller()`
                }
            }

            // Like, `UIController`s, the script must be re-attached
            // to the body as HTML5 does not parse or execute Javascript
            // set to `innerHTML`.
            let div = document.createElement("div");
            div.innerHTML = interpolate(html, attr);
            let script = div.querySelector("script");
            if (!isEmpty(script)) {
                let parentNode = script.parentNode;
                parentNode.removeChild(script);

                let sc = document.createElement("script");
                sc.id = app.scriptId; // Required to unload script later
                sc.setAttribute("type", "text/javascript");
                let inline = document.createTextNode(script.innerHTML + `\n//@ sourceURL=/application/${bundleId}`);
                sc.appendChild(inline);
                document.head.appendChild(sc);
                controller = new window[app.scriptId]();
            }

            // NOTE: System apps may not have a menu or app menu
            if (!app.system) {
                // Load app menu, if any
                let menus = div.querySelector(".ui-menus");
                if (!isEmpty(menus) && !app.system) {
                    hasMenu = true;

                    // Remove menu declaration from app
                    menus.remove();
                    menus.id = app.menuId;

                    os.ui.styleUIMenus(menus);
                    os.ui.addOSBarMenu(menus);
                }

                // Load app menus -- the menu that allows user to switch apps.
                // NOTE: Passive apps may not be switched
                let appMenu = div.querySelector(".ui-app-menu");
                let uiMenu = appMenu?.querySelector(".ui-menu");
                if (!isEmpty(uiMenu) && !app.passive) {
                    hasAppMenu = true;
                    appMenu.remove();
                    uiMenu.id = app.appMenuId;
                    os.ui.styleUIMenu(uiMenu);
                    os.ui.addOSBarApp(uiMenu);
                }
                if (!isEmpty(config.application.menu) && !app.passive) {
                    hasAppMenu = true;
                    let win = os.ui.makeAppButton(config);
                    win.id = app.appMenuId;
                    os.ui.addOSBarApp(win);
                }
            }
        }

        // Create menu with only `Quit <app_name>` if app menu is not defined
        if (!hasMenu && !app.system) {
            let menus = document.createElement("div");
            menus.classList.add("ui-menus");
            menus.id = app.menuId;
            let menu = document.createElement("div");
            menu.classList.add("ui-menu");
            menu.style.width = "180px";
            let select = document.createElement("select");
            let title = document.createElement("option");
            title.innerHTML = config.application.name;
            select.appendChild(title);
            let option = document.createElement("option");
            // TODO: Add Command + Q in future
            option.innerHTML = `Quit ${config.application.name}`;
            option.setAttribute("onclick", `os.closeApplication('${bundleId}');`);
            select.appendChild(option);
            menu.appendChild(select);
            menus.appendChild(menu);
            os.ui.styleUIMenus(menus);
            os.ui.addOSBarMenu(menus);
        }

        // Add default app menu to allow user to switch to app
        // NOTE: System and passive apps may not be switched
        if (!hasAppMenu && !app.system && !app.passive) {
            let win = os.ui.makeAppButton(config);
            win.id = app.appMenuId;
            os.ui.addOSBarApp(win);
        }

        // Application delegate will manage which controller is shown, if any
        if (config.application.main == "Application") {
            app.applicationDidStart(controller);
            switchApplication(bundleId);

            progressBar?.ui.close();

            return app;
        }

        progressBar?.setProgress(50, "Loading controller...");

        let container;
        try {
            container = await app.loadController(config.application.main);
        }
        catch (error) {
            showError(`Failed to load application (${bundleId}) main controller (${config.application.main})`, error);
        }

        app.applicationDidStart(controller);
        switchApplication(bundleId);

        // Order matters here. The application must be switched before showing controller.
        container.ui.show();

        progressBar?.ui.close();

        return app;
    }
    this.openApplication = openApplication;

    // Tracks the state of closing apps. Sometimes multiple signals may be
    // sent to close an application.
    let closingApps = {};

    /**
     * Close an application.
     */
    function closeApplication(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            console.warn(`Attempting to close application (${bundleId}) that is not loaded.`);
            return;
        }

        // In the process of closing app
        if (bundleId in closingApps) {
            return;
        }
        closingApps[bundleId] = true;

        // Remove application menu
        let div = document.getElementById(app.menuId);
        div?.remove(); // NOTE: System apps do not have menus

        // TODO: If this is focused application, show empty desktop?
        // Show a window that lists all open applications to switch to?

        let script = document.getElementById(app.scriptId);
        if (!isEmpty(script)) {
            script.remove();
        }

        let appMenu = document.getElementById(app.appMenuId);
        if (!isEmpty(appMenu)) {
            appMenu.remove();
        }

        app.applicationDidStop();

        // Remove container. All windows should be hidden at this point.
        let container = document.getElementById(os.ui.appContainerId(bundleId));
        if (!isEmpty(container)) {
            container.remove();
        }

        delete closingApps[bundleId];
        delete loadedApps[bundleId];
    }
    this.closeApplication = closeApplication;

    function blurActiveApplication() {
        if (isEmpty(activeApplication)) {
            return;
        }

        activeApplication.applicationDidBlur();

        // Hide application popup menu
        let menu = document.getElementById(activeApplication.menuId);
        if (!isEmpty(menu)) {
            menu.style.display = "none";
        }

        // Display app's icon on right side of OS bar
        let appMenu = document.getElementById(activeApplication.appMenuId);
        if (!isEmpty(appMenu)) {
            appMenu.style.display = null;
        }

        // Hide all app windows
        let windows = document.getElementById(os.ui.appContainerId(activeApplication.bundleId));
        if (!isEmpty(windows)) {
            windows.style.display = "none";
        }

        activeApplication = null;
    }

    /**
     * Switch which application app menu is displayed.
     *
     * Returns true:
     * - App menu is switched between combinatino of passive or active apps
     * - App menu is already displayed
     *
     * Returns false:
     * - App is not loaded
     * - App is inactive
     *
     * @param {string} bundleId - The bundle ID of the app to switch to
     * @returns `true` if the application menu was switched
     */
    function switchApplicationMenu(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            console.warn(`Attempting to switch active app menu for bundle (${bundleId}) that is not loaded.`);
            return false;
        }

        // Do not switch menu if this is not the active app
        if (!app.passive && !isEmpty(activeApplication) && activeApplication?.bundleId !== bundleId) {
            return false;
        }

        // Already active
        if (app.menuId == activeAppMenu?.id) {
            return true;
        }

        // Hide previous app menu
        if (!isEmpty(activeAppMenu)) {
            activeAppMenu.style.display = "none";
        }

        // Show current app menu
        activeAppMenu = document.getElementById(app.menuId);
        if (!isEmpty(activeAppMenu)) {
            activeAppMenu.style.display = null;
        }

        return true;
    }
    this.switchApplicationMenu = switchApplicationMenu;

    /**
     * Focus on the top-most app window within an app container group.
     *
     * @param {Array<HTMLElement>} windows - Windows that belong to app container group
     */
    function focusTopMostAppWindow(windows) {
        if (isEmpty(windows)) {
            console.warn("Attempting to focus on an app container group that does not exist");
            return;
        }

        windows.style.display = null;

        // Focus on the top-most window
        let highestWindow = null;
        let highestZIndex = 0;
        for (let i = 0; i < windows.childNodes.length; i++) {
            let win = windows.childNodes[i];
            let zIndex = parseInt(win.style.zIndex);
            if (zIndex > highestZIndex) {
                highestZIndex = zIndex;
                highestWindow = win;
            }
        }
        if (!isEmpty(highestWindow)) {
            os.ui.focusWindow(highestWindow);
        }
    }

    /**
     * Switch to a different application context.
     *
     * This caches windows from a previous app's session which allows them
     * to be restored upon being switched.
     */
    function switchApplication(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            os.ui.showAlert(`Application bundle (${bundleId}) is not loaded.`);
            return;
        }
        if (app.system) {
            return;
        }

        let windows = document.getElementById(os.ui.appContainerId(app.bundleId));

        // For passive apps, simply focus on the top-most window in its window group
        if (app.passive) {
            focusTopMostAppWindow(windows);
            return;
        }

        blurActiveApplication();

        activeApplication = app;

        // Show application menu
        let menu = document.getElementById(app.menuId);
        if (!isEmpty(menu)) {
            menu.style.display = null;
        }

        // Hide the application button
        let appMenu = document.getElementById(app.appMenuId);
        if (!isEmpty(appMenu)) {
            appMenu.style.display = "none";
        }

        // Focus on top-most app in window group
        focusTopMostAppWindow(windows);

        app.applicationDidFocus();
    }
    this.switchApplication = switchApplication;
}
