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
    // Object<BundleId: UIApplication>
    let loadedApps = {};

    // Defines the "active" application. When an application is "active", it
    // means the application has focus on the desktop. Active applications are
    // not passive (system) apps.
    let activeApplication = null;
    property(this, "activeApplication",
        function() { return activeApplication; },
        function(ignore) { /* read-only */ }
    );

    // Stores application contexts. The HTMLElement is the container for all
    // of the application's windows.
    //
    // Object{bundleId:HTMLElement}
    let appContexts = {};

    /**
     * Initialize the application manager with BOSS system apps.
     *
     * @param {object} apps - Map of bundle IDs to app metadata `{bundleId: {name, icon, system}}`
     */
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
        for (const bundleId in registeredApps) {
            let app = registeredApps[bundleId];
            if (app.system !== true) {
                let name = null;
                if (isEmpty(app.icon)) {
                    name = app.name;
                }
                else {
                    name = `img:/boss/app/${bundleId}/${app.icon},${app.name}`;
                }
                apps.push({id: bundleId, name: name});
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
     * Let all applications know a user has signed in.
     *
     * This will not get signed in if Guest user.
     *
     * @param {User} user
     */
    function signInAllApplications(user) {
        for (const bundleId in loadedApps) {
            let app = loadedApps[bundleId];
            app.applicationWillSignIn(user);
        }
    }
    this.signInAllApplications = signInAllApplications;

    /**
     * Sign out of all applications.
     */
    function signOutAllApplications() {
        for (const bundleId in loadedApps) {
            let app = loadedApps[bundleId];
            app.applicationWillSignOut();
        }
    }
    this.signOutAllApplications = signOutAllApplications;

    /**
     * Close all "secure" apps.
     *
     * NOTE: Secure apps require themselves to be automatically closed if a user
     * is signed out.
     */
    function closeSecureApplications() {
        for (const bundleId in loadedApps) {
            let app = loadedApps[bundleId];
            if (app.system || !app.secure) {
                continue;
            }
            closeApplication(bundleId);
        }
    }
    this.closeSecureApplications = closeSecureApplications;

    /**
     * Open a BOSS application.
     *
     * TODO: Check if user has permission to access app.
     *
     * If `MainController` is provided, it will show the controller regardless
     * of what value is set to `application.json:main`.
     *
     * @param {string} bundleId - The Bundle ID of the application to open
     *  e.g. 'io.bithead.test-management'
     * @param {MainController?} mainController - Overrides `application.json:main` controller
     * @returns UIApplication
     * @throws
     */
    async function openApplication(bundleId, mainController) {
        let progressBar;

        function showError(msg, error) {
            if (!isEmpty(error)) {
                console.error(error);
            }

            progressBar?.ui.close();

            // If the OS is loaded, this will show an error
            os.ui.showError(msg);

            throw new Error(msg);
        }

        async function hasLicenseToUseApp() {
            let license;
            try {
                license = await os.network.post("/account/app-license", {bundleId: bundleId});
            }
            catch (error) {
                showError(`Failed to load license for application (${bundleId}). Please try again later.`, error);
            }
            if (!license.valid) {
                showError(`You do not have a license to use this application (${bundleId}).`);
            }
            return true;
        }

        let loadedApp = loadedApps[bundleId];
        if (!isEmpty(loadedApp)) {
            /** This isn't necessary as we've already validated. Keeping here is a reminder.
            if (!await hasLicenseToUseApp()) {
                return;
            }
             */

            switchApplication(bundleId);
            return loadedApp;
        }

        if (!(bundleId in registeredApps)) {
            throw new Error(`Application (${bundleId}) is not installed. Make sure to register the app with the OS before attempting to open.`);
        }

        progressBar = await os.ui.showProgressBar(`Loading application ${registeredApps[bundleId].name}...`);

        if (!await hasLicenseToUseApp()) {
            return;
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

        // FIXME: The app should not be added to `loadedApps` unless it
        // successfully loads.
        loadedApps[bundleId] = app;

        // Application has custom controller that will be responsible for
        // showing the first controller, showing menus, etc.
        let hasAppController = config.application.main == "Application";
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

        // Instance of the application controller.
        let controller;

        function addDebugMenu(menus) {
            let debugMenu = document.createElement("div");
            debugMenu.classList.add("ui-menu");
            debugMenu.style.width = "200px";
            let debugSelect = document.createElement("select");
            debugSelect.name = `debug-menu`;
            let debugTitle = document.createElement("option");
            debugTitle.innerHTML = "Debug";
            debugSelect.appendChild(debugTitle);

            let controllersOpt = document.createElement("option");
            controllersOpt.innerHTML = "Controllers";
            controllersOpt.addEventListener("click", function() {
                os.ui.showControllers(app);
            });
            debugSelect.appendChild(controllersOpt);

            let embeddedOpt = document.createElement("option");
            embeddedOpt.innerHTML = "Embedded controllers";
            embeddedOpt.addEventListener("click", function() {
                os.ui.showEmbeddedControllers(app);
            });
            debugSelect.appendChild(embeddedOpt);

            debugMenu.appendChild(debugSelect);
            menus.appendChild(debugMenu);
        }

        if (hasAppController) {
            // The application controller is added to the controller list after the
            // fact. This ensures the logic to load controllers is the same, regardless
            // whether it is an app controller or `UIController`.
            app.registerController("Application", {});

            let html;
            try {
                html = await os.network.get(`/boss/app/${bundleId}/controller/Application.html`, "text");
            }
            catch (error) {
                showError(`Failed to load UIApplication for application bundle (${bundleId}).`, error);
            }

            const attr = {
                "app": {
                    bundleId: bundleId,
                    resourcePath: `/boss/app/${bundleId}`
                },
                "this": {
                    id: app.scriptId,
                    controller: `os.application('${bundleId}').proxy`
                }
            }

            // Like, `UIController`s, the application controller script must be
            // re-attached to the body as HTML5 does not parse or execute Javascript
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

            // Load app menu, if any
            let menus = div.querySelector(".ui-menus");
            if (!isEmpty(menus)) {
                hasMenu = true;

                // Remove menu declaration from app
                menus.remove();
                menus.id = app.menuId;

                // Add Debug menu to the end of app menus
                if (os.environment.dev) {
                    addDebugMenu(menus);
                }

                os.ui.styleUIMenus(menus);
                os.ui.addOSBarMenu(menus);
            }

            // Load app menus -- An app menu may either have a single
            // `ui-menu` OR have a custom view.
            //
            // A mini app provides visibility into the blurred app's state.
            // NOTE: Passive apps may not be switched
            let appMenu = div.querySelector(".ui-app-menu");
            let uiMenu = appMenu?.querySelector(".ui-menu");
            appMenu?.remove();
            hasAppMenu = true;

            // `ui-menu` takes precedence over custom app menus
            if (!isEmpty(uiMenu)) {
                uiMenu.id = app.appMenuId;
                os.ui.styleUIMenu(uiMenu);
                os.ui.addOSBarApp(uiMenu);
            }
            // Passive (system) apps are not switched.
            else if (!app.passive) {
                let container = os.ui.makeAppButton(config, appMenu);
                container.id = app.appMenuId;
                os.ui.addOSBarApp(container);
            }

            // Attach any shared embedded controller templates, from Application.html,
            // to the app container so they can be injected by controllers within the
            // respective app via `EmbedController(NameOfController)`.
            let templates = div.querySelectorAll("template");
            if (templates.length > 0) {
                let sharedGroup = document.createElement("div");
                sharedGroup.setAttribute("name", "shared-embedded-controllers");
                for (let i = 0; i < templates.length; i++) {
                    sharedGroup.appendChild(templates[i]);
                }
                appContainer.appendChild(sharedGroup);
            }
        }

        // Create menu with only `Quit <app_name>` if app menu is not defined
        // NOTE: System apps can _not_ have menus.
        if (!app.system && !hasMenu) {
            let menus = document.createElement("div");
            menus.classList.add("ui-menus");
            menus.id = app.menuId;
            let menu = document.createElement("div");
            menu.classList.add("ui-menu");
            menu.style.width = "180px";
            let select = document.createElement("select");
            select.name = `${bundleId}-menu`;
            let title = document.createElement("option");
            title.innerHTML = config.application.name;
            select.appendChild(title);

            // If there is an `About` controller, add it
            if (!isEmpty(config.application.about)) {
                let option = document.createElement("option");
                option.innerHTML = `About ${config.application.name}`;
                option.addEventListener("click", async function(e) {
                    let win = await app.loadController(config.application.about);
                    win.ui.show();
                });
                select.appendChild(option);

                // If this isn't a system app, `Quit` will be the next option
                if (!app.system) {
                    let divider = document.createElement("option");
                    divider.classList.add("divider");
                    select.appendChild(divider);
                }
            }

            let option = document.createElement("option");
            // TODO: Add Command + Q in future
            option.innerHTML = `Quit ${config.application.name}`;
            option.setAttribute("onclick", `os.closeApplication('${bundleId}');`);
            select.appendChild(option);

            menu.appendChild(select);
            menus.appendChild(menu);

            // Add Debug menu to the end of other app windows
            if (os.environment.dev) {
                addDebugMenu(menus);
            }

            os.ui.styleUIMenus(menus);
            os.ui.addOSBarMenu(menus);
        }

        // Add default app menu to allow user to switch to app.
        // NOTE: Passive (and system) apps may not be switched.
        if (!hasAppMenu && !app.passive) {
            let container = os.ui.makeAppButton(config, null);
            container.id = app.appMenuId;
            os.ui.addOSBarApp(container);
        }

        // Application delegate will manage which controller is shown, if any.
        // If a controller override is provided, do not return early.
        if (hasAppController && isEmpty(mainController)) {
            app.applicationDidStart(controller);
            switchApplication(bundleId);
            progressBar?.ui.close();
            return app; // io.bithead.boss stops here
        }

        progressBar?.setProgress(50, "Loading controller...");

        let main;
        let endpoint;

        // Load configured main controller defined in config
        let configure_fn;
        if (isEmpty(mainController?.name)) {
            main = config.application.main;
            endpoint = config.application.endpoint;
        }
        // Load MainController provided (this overrides config)
        else {
            main = mainController.name;
            endpoint = mainController.endpoint;
            configure_fn = mainController.configure_fn;
        }

        let container;
        try {
            container = await app.loadController(main, endpoint);
        }
        catch (error) {
            showError(`Failed to load application (${bundleId}) main controller (${main})`, error);
        }

        app.applicationDidStart(controller);
        switchApplication(bundleId);

        // Order matters here. The application must be switched before showing controller.
        container.ui.show(configure_fn);

        progressBar?.ui.close();

        return app;
    }
    this.openApplication = openApplication;

    // Tracks the state of closing apps. Sometimes multiple signals may be
    // sent to close an application.
    let closingApps = {};

    /**
     * Close an application.
     *
     * @param {string} bundleId - The bundle ID of the application to close
     */
    function closeApplication(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            console.warn(`Attempting to close application (${bundleId}) that is not loaded.`);
            return;
        }

        // System apps can not be closed.
        if (app.system) {
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

        // NOTE: This may be a passive app. That means, there may be no active
        // app at this point.
        if (activeApplication?.bundleId == bundleId) {
            activeApplication = null;
        }

        // In some cases, the app being closed has no windows open. If this is
        // the case, we want to focus the top-most window.
        if (!os.ui.focusTopWindow() && !isEmpty(activeApplication)) {
            // If there are no windows, show the active application's menu
            switchApplication(activeApplication.bundleId);
        }
    }
    this.closeApplication = closeApplication;

    /**
     * Blur the currently active application.
     *
     * Hides the active application's menu and windows, and clears the
     * active application reference.
     */
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
     * - App menu is switched between passive and active app
     * - App menu is already displayed
     *
     * Returns false:
     * - App is not loaded
     * - App is inactive
     *
     * @param {string} bundleId - The bundle ID of the app to switch to
     */
    function switchApplicationMenu(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            console.warn(`Attempting to switch active app menu for bundle (${bundleId}) that is not loaded.`);
            return;
        }

        // Sytem apps have no menus.
        if (app.system) {
            return;
        }

        // Do not switch menu if this is not the active app.
        //
        // Passive apps do not trigger this condition as they live in the same
        // context as the active app.
        if (!app.passive && activeApplication?.bundleId !== bundleId) {
            return;
        }

        // Show only this application's menu
        let menus = document.querySelectorAll("#os-bar-menus > .ui-menus");
        for (let i = 0; i < menus.length; i++) {
            const menu = menus[i];
            if (app.menuId == menu.id) {
                menu.style.display = null;
            }
            // Hide any previously visible menus
            else {
                menu.style.display = "none";
            }
        }

        // Show all app windows. It may be `null` if this is the first time
        // the system is switching an application.
        if (!isEmpty(activeApplication)) {
            let windows = document.getElementById(os.ui.appContainerId(activeApplication.bundleId));
            if (!isEmpty(windows)) {
                windows.style.display = null;
            }
        }
    }
    this.switchApplicationMenu = switchApplicationMenu;

    /**
     * Focus on the top-most app window within an app container group.
     *
     * @param {Array<HTMLElement>} container - Contains windows, and shared
     * controllers, for the respective app.
     */
    function focusTopMostAppWindow(container) {
        if (isEmpty(container)) {
            console.warn("Attempting to focus on an app container group that does not exist");
            return;
        }

        container.style.display = null;

        let windows = getApplicationWindows(container);

        // Focus on the top-most window
        let highestWindow = null;
        let highestZIndex = 0;
        for (let i = 0; i < windows.length; i++) {
            let win = windows[i];
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

    function getApplicationWindows(container) {
        return container.querySelectorAll(".ui-container");
    }

    /**
     * Switch to a different application context.
     *
     * This caches windows from a previous app's session which allows them
     * to be restored upon being switched.
     *
     * @param {string} bundleId - The bundle ID of the application to switch to
     */
    function switchApplication(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            os.ui.showAlert(`Application bundle (${bundleId}) is not loaded.`);
            return;
        }

        // It's not possible to switch to a system application
        if (app.system) {
            return;
        }

        // Hide any (custom) visible app menu and de-select button, if necessary.
        os.ui.hideAppMenu(bundleId);

        // Reference to the bundle's container of windows, as well as any template
        // shared controllers.
        let windows = document.getElementById(os.ui.appContainerId(app.bundleId));

        // For passive apps, simply focus on the top-most window in
        // its window group.
        if (app.passive) {
            focusTopMostAppWindow(windows);
            switchApplicationMenu(bundleId);
            return;
        }

        // This app may still be the "focused app" but w/ no windows open.
        if (bundleId !== activeApplication?.bundleId) {
            blurActiveApplication();
        }

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

        // Blur top-most window. This avoids two app menus showing at the same
        // time.
        if (getApplicationWindows(windows).length === 0) {
            os.ui.blurTopWindow();
            // This is usually called by the window that is focused. But there
            // is no window. Therefore, it must be switched here.
            switchApplicationMenu(bundleId);
        }
        else {
            // Focus on top-most app in window group
            focusTopMostAppWindow(windows);
        }

        app.applicationDidFocus();
    }
    this.switchApplication = switchApplication;

    /**
     * Send events to all loaded applications.
     *
     * @param {BOSSEvent[]} events - Events to dispatch to all loaded applications
     */
    function sendEventsToApplications(events) {
        for (const bundleId in loadedApps) {
            let app = loadedApps[bundleId];
            app.sendEvents(events);
        }
    }
    this.sendEventsToApplications = sendEventsToApplications;

    /**
     * Open an application deep link.
     *
     * @param {DeepLink} deepLink - The deep link to open
     */
    async function openDeepLink(deepLink) {
        for (const bundleId in registeredApps) {
            var app = registeredApps[bundleId];
            if (app.scheme != deepLink.scheme) {
                continue;
            }
            app = loadedApps[bundleId];
            if (isEmpty(app)) {
                app = await openApplication(bundleId);
            }
            await app.openDeepLink(deepLink);
        }
    }
    this.openDeepLink = openDeepLink;
}
