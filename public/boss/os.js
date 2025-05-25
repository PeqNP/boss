/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * OS Security has two measures
 * 1. Check if the user session is still active. If it is not, immediately
 *    sign out.
 * 2. User performs activity w/in TTL. If no activity after after TTL,
 *    immediately sign out.
 *
 * (1) exists as the timer is paused when the tab loses focus. Therefore, it is
 * possible for the session to timeout by the time the user switches back to
 * the tab, but the inactive time will not yet have triggered. (2) exists in the
 * event that the user leaves their computer w/o locking their account, while
 * the tab is still open,
 *
 * TBD: These will be put in WebThreads to automatically trigger sign out, even if
 * the tab loses focus.
 *
 * The OS is trying to prevent unauthorized reads. There is no risk of unauthorized
 * writes as the backend is configured to automatically terminate sessions after N minutes.
 *
 * All of this is a best effort as there really are no guarantees when running security
 * routines client-side.
 *
 * NOTE:
 * - Any application that considers itself confidential will be immediately closed upon
 *   the session expiring. An application may set its `confidential` bit in its respective
 *   configuration.
 */

/**
 * When opening an app, this allows you to override the application config's
 * main controller.
 *
 * This is designed to be used for debugging only!
 */
function MainController(name, endpoint, configure_fn) {
    readOnly(this, "name", name);
    readOnly(this, "endpoint", endpoint);
    readOnly(this, "configure_fn", configure_fn);
}

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

    // Amount of time to wait before checking if the user's session is active.
    // TODO: Make this 5 minutes
    // TODO: Use WebThread
    const CHECK_SESSION_TIME = 50000;

    // Amount of time to automatically sign the user out if no activity has
    // been made by the user.
    //
    // When this time has elapsed, a modal is displayed to the user to provide
    // feedback in order to extend their session. Because the backend will
    // automatically terminate a user's session sign the user out.
    //
    // TODO: Make this use WebThread
    const INACTIVITY_TIME = 100000;

    // Displayed in OS menu, settings, etc.
    let user;
    property(this, "user", function() { return user }, function(value) { });

    this.network = new Network(this);
    this.ui = new UI(this);

    // Indicates that the OS is loaded. Some facilities will not work until
    // the OS if fully loaded. Such as showing system modals, progress bars,
    // etc.
    let loaded = false;

    // The last time user activity was detected by the OS. The OS does its
    // best to identify activity by both keystroke and mouse movement.
    let lastActivityDetectedTime = 0;

    // TODO: Is there some sort of proxy I can create that will allow `loaded`
    // to be written privately but read-only public?
    function isLoaded() {
        return loaded;
    }
    this.isLoaded = isLoaded;

    // Responsible for opening, closing, and switching applications
    let app = new ApplicationManager(this);

    let delegate = protocol(
        "OSDelegate", this, "delegate",
        // Called when a user's session expires. This can be used to show the sign-in page
        // if a user's session expires.
        ["didExpireUserSession"]
    );

    // Tracks whether the user is signed in or not. This flag is used to
    // determine if apps can be switched, based on the sign in status.
    // Ideally, we only show an app's state if the user is signed in.
    // Otherwise, the sign in app is shown, to conceal any previous state.
    var isSignedIn = false;

    /**
     * Initialize the BOSS OS.
     *
     * Loads installed apps and opens the BOSS app.
     */
    async function init() {
        this.ui.init();
        startClock();
        startHeartbeat();

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
     * Load current user's workspace.
     */
    async function loadWorkspace() {
        if (isEmpty(user)) {
            console.warn("Attempting to load workspace when no user is signed in");
            return;
        }

        let workspace;
        try {
            workspace = await os.network.get(`/api/io.bithead.boss/workspace/${user.id}`);
        }
        catch (exc) {
            console.error(exc);
            console.error("Is the /os service started?");
            return;
        }

        os.ui.desktop.addApps(workspace.desktop);

        if (workspace.dock.length) {
            os.ui.showDock();
            os.ui.addAppsToDock(workspace.dock);
        }
        else {
            os.ui.hideDock();
        }
    }

    // Original reference to console.log
    let originalLogger;
    // Wraps and calls the patched callback fn as well as the original logger
    let currentLogger;

    /**
     * Patches `console.log` function so that logs may be observed from OS.
     *
     * Only one function may patch the system logger at a time. When finished,
     * please call `unpatchSystemLogger`.
     *
     * @param {function} fn - The function to call when `console.log` is called
     */
    function patchSystemLogger(fn) {
        if (isEmpty(originalLogger)) {
            originalLogger = console.log;
        }
        currentLogger = function (value) {
            fn(value);
            originalLogger(value);
        }
        console.log = currentLogger;
    }
    this.patchSystemLogger = patchSystemLogger;

    /**
     * Unpatch (reset) the `console.log` function.
     */
    function unpatchSystemLogger() {
        if (isEmpty(originalLogger)) {
            return;
        }
        console.log = originalLogger;
        currentLogger = null;
        originalLogger = null;
    }
    this.unpatchSystemLogger = unpatchSystemLogger;

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
     * @param {Object} user - The signed in user
     */
    async function signIn(_user) {
        // NOTE: The expiration date of the session is not checked here. It is
        // assumed that the user has signed in at this point. It doesn't matter
        // if the session is valid or not. It will be invalidated as soon as it
        // is checked against a backend call.
        //
        // That being said, there is still a chance to trick the OS into showing
        // the previous app's state by calling this method directly and then
        // switching apps. This OS does _not_ advertise that it is the most secure
        // client OS ever. It simply makes a best effort to conceal the previous
        // client's state until they sign back in.
        isSignedIn = true;

        // Prime the last time user activity was detected. (default value is 0)
        lastActivityDetectedTime = Date.now();

        user = _user;

        // Update the OS bar
        var option = document.getElementById("log-out-of-system");
        if (option === null) {
            console.warn("Signed in but not showing OS bar");
            return;
        }
        option.innerHTML = `Log out ${user.email}...`;

        await loadWorkspace();
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

    async function updateServerStatus() {
        // Check if user has performed any activity within TTL.
        const currentTime = Date.now();
        let elapsedTime = currentTime - lastActivityDetectedTime;
        if (elapsedTime < INACTIVITY_TIME) {
            console.warn("No user activity detected after TTL. Signing out.");
            // TODO: Show user modal to extend their session by clicking a modal.
            // This does _not_ extend their backend session. Only prevents the OS
            // from signing the user out. Really, what ought to be done, is that
            // the backend has 15m sessions and the OS prevents the backend from
            // automatically timing out. This is much safer. Do this instead.
            // TODO: Shutdown apps

            // Temporary until modal is displayed
            if (isSignedIn) {
                isSignedIn = false;
                delegate.didExpireUserSession();
            }

            return os.ui.updateServerStatus(false, "User session has expired.");
        }


        let info;
        try {
            info = await os.network.get("/api/io.bithead.boss/heartbeat");
        }
        // TODO: Create SessionExpiredError
        // TODO: Display different message if session has expired
        catch {
            return os.ui.updateServerStatus(false, "OS service down.");
        }

        if (!info.isSignedIn && isSignedIn) {
            isSignedIn = false;
            app.closeConfidentialApplications();
            delegate.didExpireUserSession();
        }

        os.ui.updateServerStatus(true, `<b>Server (</b>${info.env} ${info.host}<b>)</b><br>All services operational.`);
    }

    /**
     * Start monitoring the connection status of the server(s).
     */
    function startHeartbeat() {
        updateServerStatus();

        // Update the server status on an interval. The interval session is not
        // stored in memory in order to prevent the session from being cancelled.
        // If the session is cancelled, it is possible to prevent the OS from
        // closing apps. With Javascript running client-side, there is no guarantee
        // that data will never be seen my a malicious user who knows what they're
        // doing.
        // TODO: It's not called a "session". What is the term for the value returned
        // by setInterval that would allow you to cancel it?
        setInterval(updateServerStatus, CHECK_SESSION_TIME);
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
        os.ui.flickerButton(button, "Copied!");
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
     * If `MainController` is provided, it will show the controller regardless
     * of what value is set to `application.json:main`.
     *
     * @param {string} bundleId - The Bundle ID of the application to open e.g. 'io.bithead.test-management'
     * @param {MainController?} mainController - Overrides `application.json:main` controller
     * @returns UIApplication
     * @throws
     */
    async function openApplication(bundleId, mainController) {
        return await app.openApplication(bundleId, mainController);
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
     * - App menu is switched between combination of passive or active apps
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
