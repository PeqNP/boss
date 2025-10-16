/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * OS Security
 *
 * When a user becomes inactive, after a period of time, the system will show
 * a modal asking the user to become active before signing them out. The reset
 * interval is reset when any mouse or keystroke event occurs.
 *
 * Additionally, if any network request is made, and the user's session has expired
 * on the backend, the user will be shown the sign in page.
 *
 * The OS is trying to prevent unauthorized reads. There is no risk of unauthorized
 * writes as the backend is configured to automatically terminate sessions after N minutes.
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

    // A special user that is not considered to be signed in.
    const GUEST_USER_ID = 2;

    // Interval to refresh clock time
    const CLOCK_INTERVAL = 2 * 1000; // 2 seconds

    // Ping server every N seconds to determine server status.
    const HEARTBEAT_INTERVAL = 2 * 60 * 1000; // 2 minutes

    // Amount of time to show the user that their session is about to expire.
    const INACTIVE_TIME = 13.5 * 60 * 1000; // 13.5 minutes

    // Server configured max inactive time. This is used to determine how many
    // seconds are remaining before the user is automatically signed out.
    const MAX_INACTIVE_TIME = 15 * 60 * 1000; // 15 minutes

    // The amount of time to debounce user input events before attempting to
    // refresh the user's session.
    const DEBOUNCE_TIME = 5 * 1000; // 5 seconds

    // The last time user activity was detected by the OS. The OS does its
    // best to identify activity by both keystroke and mouse movement.
    let lastActivityDetectedDate = 0;

    // Displayed in OS menu, settings, etc.
    let user;
    property(this, "user", function() { return user }, function(value) { });

    // Automatically sign out user when security is enabled.
    //
    // By default this value is on. If you don't want this feature, or you're
    // testing an app where security gets in the way, disable it.
    let isSecurityEnabled = true;
    property(this, "isSecurityEnabled",
        function() { return user },
        function(isEnabled) {
            isSecurityEnabled = isEnabled;
            if (isEnabled) {
                startHeartbeat();
                resumeMonitoringUserEvents();
            }
            else {
                stopHeartbeat();
                pauseMonitoringUserEvents();
            }
        }
    );

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

    let delegate = protocol(
        "OSDelegate", this, "delegate",
        // Called when a user's session expires or user signs out. This can be
        // used to show the sign-in page if a user's session expires.
        ["userDidSignOut"]
    );

    // Tracks whether the user is signed in or not. This flag is used to
    // determine if apps can be switched, based on the sign in status.
    // Ideally, we only show an app's state if the user is signed in.
    // Otherwise, the sign in app is shown, to conceal any previous state.
    //
    // To test if a user is signed in, you can access `os.user`, and call
    // `os.isGuestUser(os.user)`

    let isSignedIn = false;

    /**
     * Initialize the BOSS OS.
     *
     * Loads installed apps and opens the BOSS app.
     */
    async function init() {
        this.ui.init();
        startClock();
        startHeartbeat();
        startMonitoringUserEvents();

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

    function isGuestUser(user) {
        if (isEmpty(user) || user.id == GUEST_USER_ID) {
            return true;
        }
        return false;
    }
    this.isGuestUser = isGuestUser;

    /**
     * Load current user's workspace.
     */
    async function loadWorkspace() {
        // Reset desktop and dock state. Necessary when signed in as a Guest.
        os.ui.desktop.removeAllApps();
        os.ui.closeDock();

        if (isGuestUser(user)) {
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
        os.ui.addAppsToDock(workspace.dock);
        // TODO: Only show dock if dock is enabled. This requires a backend change
        // to provide a boolean. For now, the dock is shown, even if it's empty.
        // Also, this requires the Settings app to add a `Show Dock` bit.
        os.ui.showDock();
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
     * Ask user if they want to log out of the system.
     *
     * Does nothing if user is not signed in.
     */
    function logOut() {
        if (!isSignedIn) {
            os.ui.showSignIn();
            return;
        }

        os.ui.showDeleteModal("Are you sure you want to log out?", null, async function() {
            forceLogOut();
        });
    }
    this.logOut = logOut;

    /**
     * Sign in as a guest user.
     */
    async function signInAsGuest() {
        await signIn({
            id: GUEST_USER_ID,
            fullName: "Guest",
            email: "Guest",
            verified: true,
            enabled: true
        });
    }
    this.signInAsGuest = signInAsGuest;

    /**
     * Logs user out immediately.
     *
     * Does nothing if user is logged out.
     */
    function forceLogOut() {
        if (!isSignedIn) {
            return;
        }

        try {
            os.network.get('/account/signout');
        }
        catch {
            console.error("Failed to signout");
        }

        isSignedIn = false;
        app.signOutAllApplications();
        app.closeSecureApplications();
        os.ui.desktop.removeAllApps();
        os.ui.hideDock();
        signInAsGuest();

        delegate.userDidSignOut();
    }
    this.forceLogOut = forceLogOut;

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
        if (user?.id !== _user.id) {
            isSignedIn = false;
        }

        // Guest users are not considered to be signed in. Indeed, the client and
        // backend would be out of sync. Failing to do this will cause the "Sign in"
        // app to show when attempting to refresh the user's session.
        if (!isGuestUser(_user)) {
            isSignedIn = true;
        }

        // Prime the last time user activity was detected. (default value is 0)
        lastActivityDetectedDate = Date.now();

        // Reset timer used to track inactivity. Failing to do this will
        // cause the inactivity modal to show sooner than it should be after
        // signing in again.
        inactiveFn();

        user = _user;

        // Update the OS bar
        let option = document.getElementById("log-out-of-system");
        if (option === null) {
            console.warn("Signed in but not showing OS bar");
            return;
        }
        if (isSignedIn) {
            option.innerHTML = `Log out ${user.email}...`;
        }
        else {
            option.innerHTML = `Sign in`;
        }

        // Inform all apps that a user has signed in
        if (isSignedIn) {
            app.signInAllApplications(user);
        }

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
        let time = getCurrentFormattedTime(); // "Fri Nov 15 10:23 AM";
        let option = document.getElementById("clock");
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
        setInterval(updateClock, CLOCK_INTERVAL);
    }

    /**
     * Show the inactive modal.
     *
     * This must be called more than a minute before the server automatically signs
     * out the user to stay in sync.
     *
     * This does nothing if the user is not signed in.
     */
    function showInactivityModal() {
        if (!isSecurityEnabled) {
            return;
        }
        if (!isSignedIn) {
            return;
        }

        os.ui.showInactivity();
    }

    // If monitoring user events, refreshSession will be called by the OS
    // automatically on an interval. If false, another process (such as the
    // Inactive modal) has taken over the process of refreshing the user's
    // session. When that happens, all events are ignored to allow the
    // contoroller to manage refreshing the user's session.
    let isMonitoringUserEvents = false;

    // Function used to show the inactive modal.
    const inactiveFn = debounce(showInactivityModal, INACTIVE_TIME);

    /**
     * Refresh user's session.
     *
     * This will extend the user's session by the server configured time
     * (e.g. 15 minutes).
     *
     * This will automatically close the inactivity modal if an event
     * was captured and the call to refresh was successful.
     *
     * - This does nothing if the user is not signed in.
     * - This does nothing if user event monitoring has been turned off.
     * - This will automatically sign the user out if the last use event date
     *   is greater than the max inactive time.
     */
    async function refreshSession() {
        if (!isSecurityEnabled) {
            return;
        }
        if (!isSignedIn) {
            return;
        }
        if (!isMonitoringUserEvents) {
            return;
        }

        inactiveFn.cancel();

        // This should happen directly after the OS becomes visible and the
        // amount of time has elapsed.
        let currentDate = Date.now();
        let elapsedTime = currentDate - lastActivityDetectedDate;
        if (elapsedTime > MAX_INACTIVE_TIME) {
            forceLogOut();
            return;
        }
        else if (elapsedTime > INACTIVE_TIME) {
            showInactivityModal();
            return;
        }

        try {
            await os.network.get("/account/refresh");
        }
        catch {
            console.log("User's session has expired");
            forceLogOut();
            return;
        }

        lastActivityDetectedDate = Date.now();

        inactiveFn();
    }
    this.refreshSession = refreshSession;

    // Ensures monitoring user events may only be done once.
    let didStartMonitoringUserEvents = false;

    /**
     * Start listening to user events.
     *
     * This has the side-effect of refreshing the user's session after the user
     * has performed an activity.
     */
    function startMonitoringUserEvents() {
        if (!isSecurityEnabled) {
            console.log("Security disabled. Will not monitor user events.");
            return;
        }
        if (didStartMonitoringUserEvents) {
            console.warn("Monitoring events can only be started once");
            return;
        }

        didStartMonitoringUserEvents = true;
        isMonitoringUserEvents = true;

        const refreshFn = debounce(refreshSession, DEBOUNCE_TIME);

        // Listen to all user events and refresh after debounce time
        ["click", "mousemove", "keypress"].forEach(eventName => {
            document.addEventListener(eventName, refreshFn);
        });

        // If page becomes visible again, refresh session immediately.
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                refreshSession();
            }
        });

        // Start tracking inactivity
        inactiveFn();
    }

    function pauseMonitoringUserEvents() {
        console.log("Pausing user event monitoring");
        isMonitoringUserEvents = false;
    }
    this.pauseMonitoringUserEvents = pauseMonitoringUserEvents;

    function resumeMonitoringUserEvents() {
        console.log("Resuming user event monitoring");
        isMonitoringUserEvents = true;
    }
    this.resumeMonitoringUserEvents = resumeMonitoringUserEvents;

    /**
     * Peforms heartbeat to server.
     *
     * This has the side-effect of getting the current user and server's status.
     *
     * This does NOT extend a user's session.
     */
    async function heartbeat() {
        let info;
        try {
            // NOTE: Calling BOSS's API has the effect of making calls to
            // all other BOSS subsystems. That's why `/heartbeat` is not
            // called directly.
            info = await os.network.get("/api/io.bithead.boss/heartbeat");
        }
        catch (error) {
            // Only show this error if OS failed to connect to the server
            if (error instanceof NetworkError) {
                return os.ui.updateServerStatus(false, "OS service down.");
            }
        }

        if (!info.isSignedIn && isSignedIn) {
            forceLogOut();
        }

        os.ui.updateServerStatus(true, `<b>Server (</b>${info.env} ${info.host}<b>)</b><br>All services operational.`);
    }

    // Keeps track of the interval used by the heartbeat
    let heartbeatIntervalId;

    /**
     * Start monitoring the connection status of the server(s).
     *
     * This has the effect of refreshing the user's session if activity is
     * made on the server.
     */
    function startHeartbeat() {
        if (!isSecurityEnabled) {
            console.log("Security disabled. Heartbeat will not start.");
            return;
        }
        if (!isEmpty(heartbeatIntervalId)) {
            console.warn("Will not start heartbeat, as it is already active.");
            return;
        }

        heartbeatIntervalId = setInterval(heartbeat, HEARTBEAT_INTERVAL);
        heartbeat();
    }

    function stopHeartbeat() {
        if (isEmpty(heartbeatIntervalId)) {
            console.warn("Will not stop heartbeat, as it is not active.");
            return;
        }
        clearInterval(heartbeatIntervalId);
        heartbeatIntervalId = null;
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
