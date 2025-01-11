/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * Bithead OS aka BOSS
 *
 * Provides system-level features
 * - Access to UI API
 * - Access to Network API
 * - Logging in and out
 * - Clock
 */
function OS() {

    // Displayed in OS menu, settings, etc.
    this.username = "";

    this.network = new Network(this);
    this.ui = new UI(this);

    // Indicates that the OS is loaded. Some facilities will not work until
    // the OS if fully loaded. Such as showing system modals, progress bars,
    // etc.
    let loaded = false;

    // TODO: Is there some sort of proxy I can create that will allow `loaded`
    // to be written privately but read-only public?
    function isLoaded() {
        return loaded;
    }
    this.isLoaded = isLoaded;

    // List of installed (registered) apps the OS is aware of.
    // object{bundleId:{name:icon:system:}}
    let apps = {};

    // Represents any app that was loaded. Loaded apps are considered
    // to be running, even if their application context is not active.
    // {bundleId:UIApplication}
    let loadedApps = {};

    // Defines the "active" application. When an application is "active", it
    // means the application has focus on the desktop. Only one non-system
    // application may be displayed at a time.
    let activeApplication = null;

    /**
     * Initialize the BOSS OS.
     *
     * Loads installed apps and opens the BOSS app.
     */
    async function init() {
        this.ui.init();
        startClock();

        // Load installed apps
        try {
            apps = await os.network.get("/boss/app/installed.json");
            await os.openApplication("io.bithead.boss");
            loaded = true;
        }
        catch (error) {
            console.log(error);
        }
    }
    this.init = init;

    /**
     * Log user out of system.
     */
    function logOut() {
        os.ui.showDeleteModal("Are you sure you want to log out?", null, async function() {
            os.network.redirect('/account/signout');
        });
    }
    this.logOut = logOut;

    /**
     * Sign user into system.
     *
     * @param {string} username - The username that is signed in
     */
    function signIn(username) {
        this.username = username;

        // Update the OS bar
        var option = document.getElementById("log-out-of-system");
        if (option === null) {
            console.warn("Signed in but not showing OS bar");
            return;
        }
        option.innerHTML = "Log out " + username + "...";
    }

    this.signIn = signIn;

    /**
     * Get the current time formatted in DDD MMM dd HH:MM AA.
     *
     * e.g. Fri Nov 15 9:24 PM
     *
     * @returns formatted string
     */
    function getCurrentFormattedTime() {
        const date = new Date();

        // Get parts of the date
        const day = date.toLocaleString('default', { weekday: 'short' });  // Short day name
        const month = date.toLocaleString('default', { month: 'short' });  // Short month name
        const dayOfMonth = date.getDate();
        const hours = date.getHours();
        const minutes = date.getMinutes();

        // Determine AM or PM
        const ampm = hours >= 12 ? 'PM' : 'AM';

        // Convert to 12-hour format
        let formattedHours = hours % 12 || 12;

        // 9:23 PM
        const time = `${formattedHours}:${minutes < 10 ? '0' + minutes : minutes} ${ampm}`;

        // e.g. Fri Nov 15 9:23 PM
        return `${day} ${month} ${dayOfMonth} ${time}`;
    }

    /**
     * Update the clock's time.
     */
    function updateClock() {
        var time = getCurrentFormattedTime(); // "Fri Nov 15 10:23 AM";
        var option = document.getElementById("clock");
        if (option === null) {
            console.warn("Attemping to update clock when OS bar is not visible.");
            return;
        }
        option.innerHTML = time;
    }

    /**
     * Start updating clock.
     */
    function startClock() {
        updateClock();
        setInterval(updateClock, 2000);
    }

    /**
     * Copy string `item` to clipboard.
     *
     * This temporarily changes the label of `button` for 2 seconds before
     * displaying the previous label again.
     *
     * @param {HTMLElement} button - The button invoking the copy action
     * @param {string} item - The string item to copy to clipboard
     */
    function copyToClipboard(button, item) {
        navigator.clipboard.writeText(item);
        let originalHTML = button.innerHTML;
        button.innerHTML = "Copied!";
        setInterval(function() {
            button.innerHTML = originalHTML;
        }, 2000);
    }
    this.copyToClipboard = copyToClipboard;

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
     * Register applications available to BOSS.
     *
     * This is designed to display apps that a user has access to. This
     * over-writes any registered applications, except system apps, that may
     * have been initialized or registered at a previous time.
     *
     * @param {object{bundleId:{name:system:icon:}}} apps - List of installed apps
     */
    function registerApplications(_apps) {
        let rapps = {};

        // Re-create app list. Include only system apps.
        for (bundleId in apps) {
            let app = apps[bundleId];
            if (app.system) {
                rapps[bundleId] = app;
            }
        }

        // Add apps to list
        for (bundleId in _apps) {
            if (bundleId in rapps) {
                console.log("You may not overwrite a system app");
                continue;
            }

            let app = _apps[bundleId];
            if (app.system) {
                console.log("System apps may not be registered");
                continue;
            }
            rapps[bundleId] = app;
        }

        apps = rapps;
    }
    this.registerApplications = registerApplications;

    /**
     * Open a BOSS application.
     *
     * TODO: Check if user has permission to access app.
     *
     * @param {string} bundleId - The Bundle ID of the application to open e.g. 'io.bithead.test-management'
     * @returns UIApplication
     * @throws
     */
    async function openApplication(bundleId, fn) {
        let loadedApp = loadedApps[bundleId];
        if (!isEmpty(loadedApp)) {
            // TODO: Switch app context, if not passive

            // Load/focus on the app's main controller
            if (!loadedApp.system && loadedApp.main != "Application") {
                let ctrl = await loadedApp.loadController(loadedApp.main);
                ctrl.ui.show();
            }
            return loadedApp;
        }

        if (!(bundleId in apps)) {
            throw new Error(`Application (${bundleId}) is not installed. Make sure to register the app with the OS before attempting to open.`);
        }

        let progressBar = await os.ui.showProgressBar(`Loading application ${apps[bundleId].name}...`);

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
        // When `true`, the app controller defines its own menu
        let hasAppMenu = false;

        // TODO: Load app delegate. If main is application, then AppDelegate manages windows

        let controller;
        if (hasAppController) {
            let html;
            try {
                html = await os.network.get(`/boss/app/${bundleId}/controller/Application.html`, null, "text");
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

            // Load app menu, if any
            let menus = div.querySelector(".ui-menus");
            if (!isEmpty(menus) && !app.system) {
                hasAppMenu = true;

                // Remove menu declaration from app
                menus.remove();
                menus.id = app.menuId;

                os.ui.styleUIMenus(menus);
                os.ui.addOSBarMenu(menus);
            }
        }

        // Create menu with only `Quit <app_name>` if app menu is not defined
        if (!hasAppMenu && !app.system) {
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

        // Application delegate will manage which controller is shown, if any
        if (config.application.main == "Application") {
            if (app.system) {
                app.applicationDidStart(controller);
            }
            else {
                if (!isEmpty(activeApplication)) {
                    activeApplication.applicationDidBlur();
                }

                // TODO: Switch application context

                activeApplication = app;

                app.applicationDidStart(controller);
                app.applicationDidFocus();
            }

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

        // TODO: Switch application context if app is not passive

        if (app.system) {
            app.applicationDidStart(controller);
            container.ui.show();
        }
        else {
            if (!isEmpty(activeApplication)) {
                activeApplication.applicationDidBlur();
            }

            activeApplication = app;
            app.applicationDidStart(controller);

            container.ui.show();

            app.applicationDidFocus();
        }

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

        app.applicationDidStop();

        delete closingApps[bundleId];
        delete loadedApps[bundleId];
    }
    this.closeApplication = closeApplication;

    /**
     * Switch to application context.
     *
     * The application must be loaded first.
     *
     * @param {string} bundleId
     */
    function switchApplication(bundleId) {
        let app = loadedApps[bundleId];
        if (isEmpty(app)) {
            os.ui.showAlert(`Application bundle (${bundleId}) is not loaded.`);
            return;
        }

        if (!isEmpty(activeApplication)) {
            activeApplication.applicationDidBlur();
        }

        activeApplication = app;

        app.applicationDidFocus();

        // TODO: Switch controllers being viewed
        // There's a lot that needs to be done here. For example, the controllers must be
        // associated to an application. They need to be managed by UI and the window.
        // Essentially, the window needs to store the state of an application before it is
        // switched. This function may even need to exist in UI.
    }

    /**
     * Returns all user-space installed applications.
     *
     * This is assumed to be used in a `UIListBox`. Therefore, `name` also
     * contains the application's icon.
     *
     * @returns [object{id:value:}]
     */
    function installedApplications() {
        let _apps = [];
        for (key in apps) {
            let app = apps[key];
            if (app.system !== true) {
                let name = null;
                if (isEmpty(app.icon)) {
                    name = app.name;
                }
                else {
                    name = `img:${app.icon},${app.name}`;
                }
                _apps.push({id: key, name: name});
            }
        }
        return _apps;
    }
    this.installedApplications = installedApplications;
}

/**
 * Provides network functions.
 */
function Network(os) {

    /**
     * Redirect to a page using a GET request.
     */
    function redirect(url, redirectTo) {
        // TODO: If `redirectTo` provided, URL encode the value and add it as a GET parameter to the URL
        window.location = url;
    }

    // @deprecated - Use `this.redirect`
    this.request = redirect;
    this.redirect = redirect;

    /**
     * Make a GET request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {function} fn(Result)? - Response function
     * @param {string} decoder - Response decoder. Supported: text | json. Default is `json`
     * @param {string} msg? - Show progress bar with message
     * @throws
     */
    async function get(url, msg, decoder) {
        let progressBar = null;
        if (!isEmpty(msg)) {
            progressBar = await os.ui.showProgressBar(msg);
        }
        if (isEmpty(decoder)) {
            decoder = "json";
        }
        return fetch(url, {
            method: "GET",
            // FIXME: Required when loading controller files. Failing to do this
            // will prevent controller JSON files from being loaded when changes
            // are made, as the older cached version will be served. How these
            // files are served (using Etag) could be smarter as it has more to
            // do with the backend (probably) then the front-end.
            cache: "no-cache"
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (!response.ok) {
                    throw new Error(`GET request (${url}) unexpectedly failed`);
                }
                else if (decoder === "json") {
                    return response.json();
                }
                else {
                    return response.text();
                }
            })
            .then(data => {
                // Typically the text decoder is only for HTML. With that
                // assumption, if the response looks like JSON it's because
                // there's an error.
                if (decoder === "text" && data.startsWith("{")) {
                    let obj = null;
                    try {
                        obj = JSON.parse(data);
                    }
                    catch (error) {
                        console.log("Attempting to decode JSON object that wasn't JSON.");
                    }

                    if (!isEmpty(obj?.error)) {
                        throw new Error(data.error.message);
                    }
                }

                if (isEmpty(data.error)) {
                    return data;
                }
                else {
                    throw new Error(data.error.message);
                }
            })
            .catch(error => {
                console.log(`failure: GET ${url}`);
                progressBar?.ui.close();
                throw error;
            })
            .then(data => {
                progressBar?.ui.close();
                return data;
            });
    }
    this.get = get;

    /**
     * Make a POST request with an object that can be converted into JSON.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {File} body - Object to pass as JSON
     * @param {string} msg? - Show progress bar with message
     * @throws
     */
    async function json(url, body, msg) {
        if (body === null || body.length < 1) {
            body = '{}';
        }
        else {
            body = JSON.stringify(body);
        }
        let progressBar = null;
        if (!isEmpty(msg)) {
            progressBar = await os.ui.showProgressBar(msg);
        }
        return fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: body
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is considered to be in error
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: POST ${url}`);
                progressBar?.ui.close();
                throw error;
            })
            .then(data => {
                progressBar?.ui.close();
                return data;
            });
    }

    // @deprecated - Use `post` instead
    this.json = json;
    this.post = json;

    /**
     * Upload a file.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {File} file - File object to upload
     * @param {string} msg? - Show progress bar with message
     * @throws
     */
    async function upload(url, file, msg) {
        let formData = new FormData();
        formData.append("file", file);

        let progressBar = null;
        if (!isEmpty(msg)) {
            progressBar = await os.ui.showProgressBar(msg);
        }

        return fetch(url, {
            method: "POST",
            body: formData
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is in error
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure upload: POST ${url}`);
                progressBar?.ui.close();
                throw error;
            })
            .then(data => {
                progressBar?.ui.close();
                return data;
            });
    }
    this.upload = upload;

    async function __delete(url, msg) {
        let progressBar = null;
        if (!isEmpty(msg)) {
            progressBar = await os.ui.showProgressBar(msg);
        }

        return fetch(url, {
            method: "DELETE"
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is considered to be in error
                if (data.error !== undefined) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: DELETE ${url}`);
                progressBar?.ui.close();
                throw error;
            })
            .then(data => {
                progressBar?.ui.close();
                return data;
            });
    }

    /**
     * Make a DELETE request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {object} body - request object to send as JSON to `url`
     * @param {function} fn? - Response function
     * @param {string} msg? - Show progress bar with message
     * @throws
     */
    async function _delete(url, msg, fn, dmsg) {
        if (msg === null) {
            let data = await __delete(url, dmsg);
            fn(data);
        }
        os.ui.showDeleteModal(msg, null, async function () {
            let data = await __delete(url, dmsg);
            fn(data);
        });
    }
    this.delete = _delete;

    /**
     * Make PATCH request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {object} body - request object to send as JSON to `url`
     * @param {function} fn? - Response function
     * @param {string} msg? - Show progress bar with message
     * @throws
     */
    async function patch(url, body, msg) {
        if (body === null || body.length < 1) {
            body = '{}';
        }
        else {
            body = JSON.stringify(body);
        }

        let progressBar = null;
        if (!isEmpty(msg)) {
            progressBar = await os.ui.showProgressBar(msg);
        }

        return fetch(url, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json"
            },
            body: body
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is considered to be in error
                if (data.error !== undefined) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: PATCH ${url}`);
                progressBar?.ui.close();
                throw error;
            })
            .then(data => {
                progressBar?.ui.close();
                return data;
            });
    }
    this.patch = patch;

    /**
     * Dynamically load stylesheet.
     */
    async function stylesheet(href) {
        return new Promise((resolve, reject) => {
            let link = document.createElement('link');
            link.rel = 'stylesheet';
            link.type = 'text/css';
            link.onload = resolve;
            link.onerror = reject;
            link.href = '/codemirror/lib/codemirror.css';
            document.head.appendChild(link);
        });
    }
    this.stylesheet = stylesheet;

    /**
     * Dynamically load javascript.
     */
    async function javascript(href) {
        return new Promise((resolve, reject) => {
            let script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = href;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    this.javascript = javascript;
}
