/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * Bithead OS aka BOSS
 *
 * Provides system-level features
 * - Running applications
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

    // Responsible for opening, closing, and switching applications
    let app = new ApplicationManager(this);

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
            app.init(apps);
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
            os.network.get('/account/signout');
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
        return app.application(bundleId);
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
    function registerApplications(apps) {
        app.registerApplications(apps);
    }
    this.registerApplications = registerApplications;

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
        return await app.openApplication(bundleId, fn);
    }
    this.openApplication = openApplication;

    /**
     * Close an application.
     */
    function closeApplication(bundleId) {
        app.closeApplication(bundleId);
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
        app.switchApplication(bundleId);
    }
    this.switchApplication = switchApplication;

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
        return app.switchApplicationMenu(bundleId);
    }
    this.switchApplicationMenu = switchApplicationMenu;

    /**
     * Returns all user-space installed applications.
     *
     * This is assumed to be used in a `UIListBox`. Therefore, `name` also
     * contains the application's icon.
     *
     * @returns [object{id:value:}]
     */
    function installedApplications() {
        return app.installedApplications();
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
     * @param {string} msg? - Show progress bar with message
     * @param {string} decoder - Response decoder. Supported: text | json. Default is `json`
     * @throws
     */
    async function get(url, decoder) {
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
                        throw new Error(obj.error.message);
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
                throw error;
            })
            .then(data => {
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
     * @throws
     */
    async function json(url, body) {
        if (isEmpty(body) || body.length < 1) {
            body = '{}';
        }
        else {
            body = JSON.stringify(body);
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
                throw error;
            })
            .then(data => {
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
     * @throws
     */
    async function upload(url, file) {
        let formData = new FormData();
        formData.append("file", file);

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
                throw error;
            })
            .then(data => {
                return data;
            });
    }
    this.upload = upload;

    async function __delete(url) {
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
                throw error;
            })
            .then(data => {
                return data;
            });
    }

    /**
     * Make a DELETE request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {string?} msg - Message to display before deleting
     * @param {function?} fn - Response function
     * @throws
     */
    async function _delete(url, msg, fn) {
        if (msg === null) {
            let data = await __delete(url);
            fn(data);
        }
        os.ui.showDeleteModal(msg, null, async function () {
            let data = await __delete(url);
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
                throw error;
            })
            .then(data => {
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
