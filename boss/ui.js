/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * Provides access to UI library.
 */
function UI(os) {
    // Modal z-index is defined to be above all other windows. Therefore, the max
    // number of windows that can be displayed is ~1998.
    const MODAL_ZINDEX = 1999;

    // Starting z-index for windows
    const WINDOW_START_ZINDEX = 10;

    // List of "open" window controllers.
    let controllers = {};

    // Contains a list of displayed windows. The index of the array is the window's
    // respective z-index + WINDOW_START_ZINDEX.
    let windowIndices = [];

    // Provides a way to access an instance of a controller and call a function
    // on the instance.
    //
    // e.g. `os.ui.controller.ActiveTestRun_0000.fn()`
    //
    // The reason this was done, was to avoid creating a `controller()` function
    // which required the ID to be passed in a string. The quotes would be escaped
    // when interpolated by Vapor/Leaf backend renderer. Luckily, this provides a
    // more succint, and clean, way to get access to controller instance.
    //
    // Furthermore, this still ensures the `controller`s variable is not being
    // leaked.
    const controller = {};
    const handler = {
        // `prop` is the `id` of the `ui-window`
        get: function(obj, prop) {
            return controllers[prop];
        },
        set: function(obj, prop, value) {
            console.warn(`It is not possible to assign ${value} to ${prop}`);
            return false; // Not supported
        }
    };
    this.controller = new Proxy(controller, handler);

    function init() {
        // TODO: Some of these should go away and be performed only in `makeWindow`.
        stylePopupMenus();
        styleFolders();

        // Style hard-coded system menus
        styleUIMenus(document.getElementById("os-bar"));

        /**
         * Close all menus when user clicks outside of `select`.
         */
        document.addEventListener("click", closeAllMenus);
    }
    this.init = init;

    function addController(id, ctrl) {
        controllers[id] = ctrl;
    }
    this.addController = addController;

    function removeController(id) {
        delete controllers[id];
    }
    this.removeController = removeController;

    /**
     * Drag window.
     */
    function dragWindow(container) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

        function dragElement(e) {
            e = e || window.event;
            e.preventDefault();

            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;

            // Prevent window from going past the OS bar
            let topPos = container.offsetTop - pos2;
            if (topPos < 28) {
                topPos = 28;
            }
            container.style.top = topPos + "px";
            container.style.left = (container.offsetLeft - pos1) + "px";
        }

        function stopDraggingElement() {
            document.onmouseup = null;
            document.onmousemove = null;
            container.onmousedown = null;
        }

        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;

            // Register global drag events on document
            document.onmousemove = dragElement;
            // Unregister global drag events
            document.onmouseup = stopDraggingElement;
        }

        container.onmousedown = dragMouseDown;
    }
    this.dragWindow = dragWindow;

    /**
     * Adds and registers a window container z-index.
     *
     * @param {HTMLElement} container - The window's container `div`
     */
    function addWindow(container) {
        // The z-index is the same as the position in the indices array
        let zIndex = windowIndices.length + WINDOW_START_ZINDEX;
        container.style.zIndex = `${zIndex}`;

        windowIndices.push(container);
    }

    /**
     * Unregister a window container.
     *
     * @param {HTMLElement} container - The window's container
     */
    function removeWindow(container) {
        if (isEmpty(container.style.zIndex)) {
            return; // New window
        }
        let index = parseInt(container.style.zIndex) - WINDOW_START_ZINDEX;
        if (index < 0) {
            console.warn(`Invalid zIndex (${container.style.zIndex}) on container (${container.id})`);
            return;
        }
        windowIndices.splice(index, 1);

        // Repair window indices
        for (let i = index; i < windowIndices.length; i++) {
            let ctrl = windowIndices[i];
            let zIndex = i + WINDOW_START_ZINDEX;
            ctrl.style.zIndex = `${zIndex}`;
        }
    }
    this.removeWindow = removeWindow;

    /**
     * Focus on the window container.
     *
     * This moves the window to the front of all other windows and updates the
     * state of the window's title.
     *
     * @param {HTMLElement} container - The window's container
     */
    function focusWindow(container) {
        let topZIndex = windowIndices.length - 1 + WINDOW_START_ZINDEX;

        // Already the top window
        if (parseInt(container.style.zIndex) === topZIndex) {
            return;
        }

        let topWindow = windowIndices[windowIndices.length - 1];

        if (!isEmpty(topWindow)) {
            topWindow.ui.didBlurWindow();
        }

        removeWindow(container);
        addWindow(container);

        container.ui.didFocusWindow();
    }
    this.focusWindow = focusWindow;

    /**
     * Focus the top-most window in the window index.
     *
     * This is called directly after a window is removed.
     */
    function focusTopWindow() {
        // No windows to focus
        if (windowIndices.length === 0) {
            return;
        }

        let topWindow = windowIndices[windowIndices.length - 1];
        topWindow.ui.didFocusWindow();
    }
    this.focusTopWindow = focusTopWindow;

    function makeWindowId() {
        let objectId = makeObjectId();
        return `Window_${objectId}`;
    }

    /**
     * Create window attributes.
     *
     * Window attributes provide a way for a `.ui-window` to reference:
     * - Their controller's instance
     * - Respective app instance
     * - OS information
     *
     * An ID may be provided if the window is pre-rendered.
     *
     * @param {string} bundleId - The application bundle ID
     * @param {string?} id - The ID of the window instance
     */
    function makeWindowAttributes(bundleId, id) {
        if (isEmpty(id)) {
            // FIXME: This assumes the object ID always exists.
            id = makeWindowId();
        }

        const attr = {
            app: {
                // TODO: How do I get the app's information in this context?
                // Attributes may need to be created in the `UIApplication` context.
                resourcePath: "",
                controller: `os.application('${bundleId}')`
            },
            os: {
                email: "bitheadRL AT proton.me",
                // Too much spam. For clients that have the OS installed locally,
                // set this to the correct value.
                phone: "bitheadRL AT proton.me"
            },
            "this": {
                id: id,
                controller: `os.ui.controller.${id}`
            },
        };

        return attr;
    }

    /**
     * Creates temporary element that parses HTML and re-attached Javascript to
     * work-around HTML5 preventing untrusted scripts from parsing when setting
     * innerHTML w/ dynamic content.
     *
     * @param {Object} attr - Attributes to assign to window
     * @param {string} html - HTML to add to window container
     * @returns `div` that contains parsed HTML and re-attached Javascript
     */
    function parseHTML(attr, html) {
        // You must re-attach any scripts that are part of the HTML. Since HTML5
        // javascript is not parsed or ran when assigning values to innerHTML.
        let div = document.createElement("div");
        div.innerHTML = interpolate(html, attr);
        let script = div.querySelector("script");

        // Attach script, if any
        if (!isEmpty(script)) {
            let parentNode = script.parentNode;
            parentNode.removeChild(script);

            let sc = document.createElement("script");
            sc.setAttribute("type", "text/javascript");
            let inline = document.createTextNode(script.innerHTML + `\n//@ sourceURL=/window/${attr.this.id}`);
            sc.appendChild(inline);
            parentNode.append(sc);
        }

        return div;
    }

    /**
     * Creates an instance of a `UIWindow` from an HTML string.
     *
     * This is designed to work with:
     * - `OS` facilities to launch an application
     * - Create new windows from `UI.makeController(name:)`
     *
     * @param {string} bundleId: App bundle ID creating window
     * @param {string} html: Window HTML to render
     * @returns `UIWindow`
     */
    function makeWindow(bundleId, html) {
        const attr = makeWindowAttributes(bundleId);

        let div = parseHTML(attr, html);

        let container = document.createElement("div");
        container.appendChild(div.firstChild);
        container.style.position = "absolute";
        // TODO: Stagger position where windows appear. Each new window should
        // be 10-20 px from top and left. When intial position is > 1/3 of page
        // viewport size, reset back to 40/20.
        container.style.top = "40px";
        container.style.left = "20px";

        container.ui = new UIWindow(attr.this.id, container, false);
        return container;
    }
    this.makeWindow = makeWindow;

    /**
     * Create modal window.
     *
     * Modals are displayed above all other content. Elements behind the modal
     * may not be interacted with until the modal is dismissed.
     *
     * @param {string} bundleId: App bundle ID creating window
     * @param {string} html: Modal HTML to render
     * @returns `UIWindow`
     */
    function makeModal(bundleId, html) {
        const attr = makeWindowAttributes(bundleId);

        let div = parseHTML(attr, html);

        // Wrap modal in an overlay to prevent taps from outside the modal
        let overlay = document.createElement("div");
        overlay.classList.add("ui-modal-overlay");

        // Container is used for positioning
        let container = document.createElement("div");
        container.classList.add("ui-modal-container");
        container.appendChild(div.firstChild);
        overlay.appendChild(container);

        overlay.ui = new UIWindow(attr.this.id, overlay, true);
        return overlay;
    }
    this.makeModal = makeModal;

    /**
     * Make a modal from an HTML fragment.
     *
     * Designed only to be used for pre-rendered pages. Modals should be
     * loaded from an application's respective controller registry.
     *
     * @param {string} bundleId: App bundle ID creating window
     * @param {string} fragmentId - The id of the HTML fragment
     * @returns `UIWindow`
     */
    function makeModalFromFragment(bundleId, fragmentId) {
        let fragment = document.getElementById(fragmentId);
        return makeModal(bundleId, fragment.innerHTML);
    }

    /**
     * Register all windows with the OS.
     *
     * This allows for window menus to be displayed in the OS bar.
     *
     * NOTE: This is temporary until all windows are creqated by the OS
     * and not pre-rendered before the OS starts.
     */
    function registerWindows() {
        let windows = document.getElementsByClassName("ui-window");
        for (let i = 0; i < windows.length; i++) {
            let win = windows[i];
            // Do not style windows in fragments
            // TODO: This is temporary. This exists only because windows may
            // be rendered in the document w/o intervention from OS.
            let p = win.parentNode;
            let inFragment = false;
            while (true) {
                if (isEmpty(p)) {
                    break;
                }
                else if (p.tagName == "FRAGMENT") {
                    inFragment = true;
                    break;
                }
                p = p.parentNode;
            }
            if (!inFragment) {
                registerWindow(win);
            }
        }
    }
    this.registerWindows = registerWindows;

    /**
     * Register a window with the OS.
     *
     * This allows the OS to display the window's menus in the OS bar.
     *
     * NOTE: This is temporary solution until all windows are created by the OS
     * and not pre-rendered before the OS starts.
     *
     * Window attributes are not interpolated on pre-rendered windows.
     */
    function registerWindow(win) {
        // Register window for life-cycle events if it has a controller
        let id = win.getAttribute("id");

        if (isEmpty(id)) {
            console.error("Pre-rendered windows must have an ID");
        }

        // When windows are pre-rendered, `show` is not called. Therefore, parts
        // of the view life-cycle methods must be managed here.
        win.ui = new UIWindow(id, win, false);
        win.ui.init(true);
    }

    /**
     * Register all controllers on the page.
     *
     * Controllers are embedded elements inside a UIWindow. A good example of
     * this is a "Search" component which may be used in several `UIWindow`s.
     *
     * Controllers may reference their respective Javascript model the same
     * way as `UIWindow`s. e.g. `os.ui.controller.ControllerName`.
     */
    function registerControllers() {
        let controllers = document.getElementsByClassName("ui-controller");
        for (let i = 0; i < controllers.length; i++) {
            registerController(controllers[i]);
        }
    }
    this.registerControllers = registerControllers;

    /**
     * Register a controller with the OS.
     *
     * NOTE: Similar to `UIWindow`s, this logic may be temporary until the OS
     * creates the windows, rather than the controller being pre-rendered.
     *
     * TODO: Once the OS renders `UIWindow`s, this may need to be updated.
     */
    function registerController(component) {
        let id = component.getAttribute("id");
        if (isEmpty(id)) {
            console.error("Controller has no ID");
            return;
        }

        let code = `new window.${id}(component);`;
        let ctrl = eval(code);
        if (!isEmpty(ctrl)) {
            if (!isEmpty(ctrl.viewDidLoad)) {
                ctrl.viewDidLoad();
            }
            addController(id, ctrl);
        }
    }

    /**
     * Add single, or multiple, menus in the OS bar.
     */
    function addOSBarMenu(menu) {
        var p = document.getElementById("os-bar-menus");
        if (isEmpty(p)) {
            console.error("The OS Bar element, `os-bar-menus`, is not in DOM.");
            return;
        }
        p.appendChild(menu);
    }
    this.addOSBarMenu = addOSBarMenu

    /**
     * Shows the user settings application.
     */
    async function openSettings() {
        await os.openApplication("io.bithead.settings");
    }
    this.openSettings = openSettings;

    /**
     * Show Bithead OS About menu.
     *
     * FIXME: This needs to use the latest patterns to instantiate, show,
     * and hide windows/modals.
     */
    async function showAboutModal() {
        let app = await os.openApplication("io.bithead.boss");
        let ctrl = await app.loadController("About");
        ctrl.ui.show();
    }
    this.showAboutModal = showAboutModal;

    /**
     * Show installed applications.
     *
     * FIXME: This needs to use the latest patterns to instantiate, show,
     * and hide windows/modals.
     */
    async function showInstalledApplications() {
        await os.openApplication("io.bithead.applications");
    }
    this.showInstalledApplications = showInstalledApplications;

    /**
     * Show an error modal above all other content.
     *
     * FIXME: Needs to be updated to use the latest patterns.
     */
    async function showErrorModal(error) {
        if (!os.isLoaded()) {
            return console.error(error);
        }
        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("Error");
        modal.querySelector("p.message").innerHTML = error;
        modal.ui.show();
    }
    this.showErrorModal = showErrorModal;

    /**
     * Show a delete modal.
     *
     * Ask user if they want to delete a model. This can be used in all contexts
     * where a destructive action can take place.
     *
     * @param {string} msg - The (question) message to display.
     * @param {async function} cancel - A function that is called when user presses `Cancel`
     * @param {async function} ok - A function that is called when user presses `OK`
     * @throws
     */
    async function showDeleteModal(msg, cancel, ok) {
        if (!isEmpty(cancel) && !isAsyncFunction(cancel)) {
            throw new Error(`Cancel function for msg (${msg}) is not async function`);
        }
        if (!isEmpty(ok) && !isAsyncFunction(ok)) {
            throw new Error(`OK function for msg (${msg}) is not async function`);
        }
        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("Delete");
        modal.querySelector("p.message").innerHTML = msg;
        modal.ui.show(function(controller) {
            controller.configure(cancel, ok);
        });
    }
    this.showDeleteModal = showDeleteModal;

    /**
     * Show a generic alert modal with `OK` button.
     *
     * If the OS is not loaded, this logs the alert to console.
     *
     * @param {string} msg - Message to display to user.
     */
    async function showAlert(msg) {
        if (!os.isLoaded()) {
            console.error(msg);
            return;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("Alert");
        modal.querySelector("p.message").innerHTML = msg;
        modal.ui.show();
    }
    this.showAlert = showAlert;

    /**
     * Show a cancellable progress bar modal.
     *
     * Use this when performing long running actions that may be cancelled.
     *
     * When the `Stop` button is tapped, regardless if `fn` is set, the button
     * will become disabled. This visual feedback informs user that the operation
     * can only be performed once.
     *
     * @param {string} msg - Message to show in progress bar
     * @param {async function} fn - The async function to call when the `Stop` button is pressed.
     * @param {bool} indeterminate - If `true`, this will show an indeterminate progress bar. Default is `false`.
     * @returns UIProgressBar if OS is loaded. Otherwise, returns `null`.
     * @throws
     */
    async function showProgressBar(msg, fn, indeterminate) {
        if (!os.isLoaded()) {
            return null;
        }
        if (!isEmpty(fn) && !isAsyncFunction(fn)) {
            throw new Error(`Callback function for progress bar (${msg}) is not async function`);
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("ProgressBar");

        if (isEmpty(indeterminate)) {
            indeteriminate = false;
        }

        let message = modal.querySelector("div.title");
        message.innerHTML = msg;

        let title = modal.querySelector("div.title");
        title.innerHTML = msg;

        let progressBar = null;
        if (indeterminate) {
            let bar = modal.querySelector(".progress-bar");
            if (!bar.classList.contains("indeterminate")) {
                bar.classList.add("indeterminate");
            }
        }
        else {
            progressBar = modal.querySelector("div.progress");
            progressBar.style.width = "0%";
        }

        modal.querySelector("button.stop").addEventListener("click", async function() {
            this.disabled = true;
            if (isEmpty(fn)) {
                return;
            }
            message.innerHTML = "Stopping"
            await fn().then((result) => {
                console.log("Stopped")
                modal.ui.close();
            });
        });

        /**
         * Set the progress of the bar.
         *
         * `amount` is ignored if progress bar is "Indeterminate"
         *
         * @param {integer} amount - A value from 0-100, where the number represents the percent complete = `75` = 75% complete.
         * @param {string?} title - Title displayed directly above the progress bar.
         */
        function setProgress(amount, msg) {
            if (!isEmpty(msg)) {
                title.innerHTML = msg;
            }
            if (!indeterminate) {
                progressBar.style.width = `${amount}%`;
            }
        }
        modal.setProgress = setProgress;

        modal.ui.show();

        return modal;
    }
    this.showProgressBar = showProgressBar;
}

/**
 * Represents a BOSS application.
 *
 * This is provided to a user's application instance.
 *
 * @param {UI} ui - Instance of UI
 * @param {object} cfg - Contains all of the applications configuration
 */
function UIApplication(config) {

    readOnly(this, "bundleId", config.application.bundleId);
    readOnly(this, "icon", config.application.icon);
    readOnly(this, "name", config.application.name);
    readOnly(this, "system", config.application.sytem);
    readOnly(this, "version", config.application.version);

    // Application function
    let main = null;

    // (Down)Loaded controllers
    let controllers = {};

    // Visible windows object[windowId:UIController]
    let launchedControllers = {};

    function makeController(def, html) {
        // Modals are above everything. Therefore, there is no way apps can
        // be switched in this context w/o the window being closed first.
        if (def.modal) {
            return os.ui.makeModal(config.application.bundleId, html);
        }

        let container = os.ui.makeWindow(config.application.bundleId, html);

        launchedControllers[container.ui.id] = container;

        // Do not attach this to the controller:
        // - This should not be accessible publicly
        // - Avoids polluting (over-writing) user code
        // - Controller is not shown at this point. Therefore, `UIController`
        //   will be `undefined` at this point.
        container.ui.viewDidUnload = function() {
            // Order matters. This prevents circular loop if last visible
            // controller and app needs to be shut down. When an app is
            // shut down, all windows are closed.
            delete launchedControllers[container.ui.id];

            if (isEmpty(launchedControllers) && config.application.quitAutomatically === true) {
                os.closeApplication(config.application.bundleId);
            }
        }

        return container;
    }

    /**
     * Load and return new instance of controller.
     *
     * If controller is a singleton, and is visible, the singleton is returned.
     *
     * If a controller is not found in the application's controller list, or could
     * not be created, the callback function is _not_ called.
     *
     * If error_fn is defined, the Error is returned instead of showing an alert.
     *
     * @param {string} name - Name of controller
     * @returns HTMLElement window container
     * @throws
     */
    async function loadController(name) {
        let def = config.controllers[name];
        if (isEmpty(def)) {
            throw new Error(`Controller (${name}) does not exist in application's (${config.application.bundleId}) controller list.`);
        }

        let launched = launchedControllers[name];
        if (!isEmpty(launched) && def.singleton) {
            return launched;
        }

        // FIXME: When loading controller from cache, the renderer may need to
        // be factord in.

        // Return cached controller
        let html = controllers[name];
        if (!isEmpty(html)) {
            return makeController(def, html);
        }

        if (!isEmpty(def.renderer) && def.renderer !== "html") {
            throw new Error(`Unsupported renderer (${def.renderer}) for controller (${def.name}).`);
        }
        else if (isEmpty(def.renderer)) {
            def.renderer = "html";
        }

        // Download and cache controller
        try {
            // FIXME: If renderer requires Object, this may need to change
            // the decoder to JSON. For now, all controllers are HTML.
            html = await os.network.get(`/boss/app/${config.application.bundleId}/controller/${name}.${def.renderer}`, null, "text");
        }
        catch (error) {
            console.log(error);
            throw new Error(`Failed to load application bundle (${config.application.bundleId}) controller (${name}).`);
        }

        controllers[name] = html;

        return makeController(def, html);
    }
    this.loadController = loadController;

    /** Delegate Callbacks **/

    /**
     * Called after the application's configuration has been loaded.
     *
     * If `main` is a `UIController`, this is called directly before the
     * controller is displayed.
     *
     * If `main` is a `UIApplication`, then the app is responsible for showing
     * the controller. e.g. This is where the app can show a splash screen,
     * load assets, making network requests for app data, etc.
     */
    function applicationDidStart(m) {
        main = m;
        if (!isEmpty(main?.applicationDidStart)) {
            main.applicationDidStart();
        }
    }
    this.applicationDidStart = applicationDidStart;

    /**
     * Called before the application is removed from the OS's cache.
     *
     * Perform any necessary cleanup steps. In most cases, this is not
     * necessary as any memory used by your application will be cleaned
     * automatically.
     */
    function applicationDidStop() {
        // Close all windows
        // TODO: Not sure if this works
        for (windowId in launchedControllers) {
            launchedControllers[windowId].ui.close();
        }

        if (!isEmpty(main?.applicationDidStop)) {
            main.applicationDidStop();
        }
    }
    this.applicationDidStop = applicationDidStop;

    /** NOTICE
     *
     * System applications will not recieve `applicationDidFocus` or
     * `applicationDidBlur` signals.
     *
     */

    /**
     * Application became the focused application.
     *
     * This is not called when the application starts. Only when switching
     * contexts.
     */
    function applicationDidFocus() {
        if (!isEmpty(main?.applicationDidFocus)) {
            main.applicationDidFocus();
        }
    }
    this.applicationDidFocus = applicationDidFocus;

    /**
     * Application went out of focus.
     *
     * This happens when a user changes the app they want to work with. Your
     * app is not removed from memory and may work in the background.
     * However, none of your UI interfaces will be shown to the user.
     *
     * Please be cognizant of what operations you perform in the background
     * as the user expects your app to be mostly dormant while they are
     * working in the other app.
     *
     * Perform any necessary save actions.
     */
    function applicationDidBlur() {
        if (!isEmpty(main?.applicationDidBlur)) {
            main.applicationDidBlur();
        }
    }
    this.applicationDidBlur = applicationDidBlur;
}

/**
 * Provides abstraction for a window.
 *
 * FIXME: You may not close and re-open a window. The window is not
 * re-registered when shown subsequent times.
 *
 * NOTE: A window controller will not be available until the window
 * has been shown. The reason is, if the controller is added, but the window
 * is never shown, controller will not unregister at the end of the `UIWindow`'s
 * life-cycle. It's possible that this could be fixed if an unload delegate
 * method existed. Also, the controller can't even be loaded until the view is
 * added to the DOM.
 *
 * tl;dr to access the window's controller, first call `show()`.
 *
 * @param {UI} ui - Instance of UI
 * @param {HTMLElement} container - `.ui-window` container
 */
function UIWindow(id, container, isModal) {

    readOnly(this, "id", id);

    let controller = null;

    // Reference to the element that contains this window's `UIMenu`s that
    // are showno in the OS bar. This is necessary when a window wishes to
    // make changes to the menu after the view is loaded.
    let menus = null;

    /**
     * Prepare the window for display, load controller source, etc.
     *
     * This returns a `UIController` to support pre-rendered windows. Even though
     * this function is "public" it should be visible only to UI. Do not call this
     * method directly.
     *
     * @param {bool} isPreRendered - Window is already rendered to desktop and
     *      not managed by OS.
     * @param {function?} fn - Callback function that will be called before view is loaded
     */
    function init(isPreRendered, fn) {
        styleListBoxes(container);
        styleUIMenus(container);

        // Add window controller, if it exists.
        if (typeof window[id] === 'function') {
            controller = new window[id](container);
            os.ui.addController(id, controller);

            if (!isEmpty(fn)) {
                fn(controller);
            }
        }

        // TODO: Register embedded controllers

        if (!isModal && !isPreRendered) {
            // Register buttons, if they exist
            let closeButton = container.querySelector(".close-button");
            if (!isEmpty(closeButton)) {
                closeButton.addEventListener("click", function (e) {
                    e.stopPropagation();
                    close();
                });
            }
            let zoomButton = container.querySelector(".zoom-button");
            if (!isEmpty(zoomButton)) {
                zoomButton.addEventListener("click", function (e) {
                    e.stopPropagation();
                    zoom();
                });
            }

            // NOTE: didViewBlur signal is triggered via focusWindow >
            // didBlurWindow > controller?.didViewBlur

            // Register window drag event
            container.querySelector(".top").onmousedown = function(e) {
                os.ui.focusWindow(container);
                os.ui.dragWindow(container);
            };
        }
        else if (isPreRendered) {
            // Allows co-existence of pre-rendered windows with OS managed windows.
            // The pre-rendered window will still show blurred state, etc.
            // This also ensures the correct menus are displayed.
            os.ui.focusWindow(container);
        }

        // There should only be one ui-menus
        let uiMenus = container.querySelector(".ui-menus");
        if (!isEmpty(uiMenus)) {
            // Remove menu declaration from window
            uiMenus.remove();

            menus = uiMenus;
            os.ui.addOSBarMenu(menus);
        }

        if (!isModal && !isPreRendered) {
            // Prepare window to be displayed -- assigns z-index.
            os.ui.focusWindow(container);
        }

        if (!isEmpty(controller?.viewDidLoad)) {
            controller.viewDidLoad();
        }
    }
    this.init = init;

    /**
     * Show the window.
     *
     * @param {function} fn - The function to call directly before the view is loaded
     */
    function show(fn) {
        // NOTE: `container` must be added to DOM before controller can be
        // instantiated.
        let desktop = document.getElementById("desktop");
        desktop.appendChild(container);

        // Allow time for parsing. I'm honestly not sure this is required.
        init(false, fn);

        // TODO: Allow the controller to load its view.
        // Typically used when providing server-side rendered window container.
        if (!isEmpty(controller?.init)) {
            // TODO: This is an async function. The functions below shall not
            // be called until the view is loaded from the server.
        }
        else {
        }
    }
    this.show = show;

    /**
     * Toggle fullscreen window.
     */
    function zoom() {
        console.log("zoom() not yet implemented");
    }

    /**
     * Close the window.
     */
    function close() {
        if (!isEmpty(controller?.viewWillUnload)) {
            controller.viewWillUnload();
        }

        os.ui.removeController(id);

        menus?.remove();

        let desktop = document.getElementById("desktop");
        desktop.removeChild(container);

        if (!isModal) {
            os.ui.removeWindow(container);
            os.ui.focusTopWindow();
        }

        if (!isEmpty(container?.ui.viewDidUnload)) {
            container.ui.viewDidUnload();
        }
    }
    this.close = close;

    function didFocusWindow() {
        if (container.classList.contains("blurred")) {
            container.classList.remove("blurred");
        }

        if (!isEmpty(menus)) {
            // NOTE: Setting this to `block` aligns items vertically.
            menus.style.display = null;
        }

        if (!isEmpty(controller?.viewDidFocus)) {
            controller.viewDidFocus();
        }
    }
    this.didFocusWindow = didFocusWindow;

    function didBlurWindow() {
        if (!container.classList.contains("blurred")) {
            container.classList.add("blurred");
        }

        if (!isEmpty(controller?.viewDidBlur)) {
            controller.viewDidBlur();
        }

        if (!isEmpty(menus)) {
            menus.style.display = "none";
        }
    }
    this.didBlurWindow = didBlurWindow;

    /** Helpers **/

    /**
     * Returns `button` `HTMLElement` with given name.
     *
     * @param {string} name - Name of button element
     * @returns HTMLElement?
     */
    function button(name) {
        return container.querySelector(`button[name='${name}']`)
    }
    this.button = button;

    /**
     * Returns the respective `input` `HTMLElement` given name.
     *
     * @param {string} name - Name of input element
     * @returns HTMLElement?
     */
    function input(name) {
        return container.querySelector(`input[name='${name}']`)
    }
    this.input = input;

    /**
     * Returns `select` `HTMLElement` with given name.
     *
     * @param {string} name - Name of select element
     */
    function select(name) {
        return container.querySelector(`select[name='${name}']`)
    }
    this.select = select;

    /**
     * Returns the respective `UIMenu` element.
     *
     * @param {string} name - Name of `UIMenu` `select` element
     * @returns {UIMenu}
     */
    function menu(name) {
        let menu = menus?.querySelector(`select[name='${name}']`);
        if (isEmpty(menu)) {
            console.warn(`Failed to find UIMenu select with name (${name})`);
            return null;
        }
        return menu.ui;
    }
    this.menu = menu;

    /**
     * Returns the value of the input and displays error message if the value
     * is empty.
     *
     * @param {string} name - Name of input element
     * @param {string?} msg - If not `null`, message will be displayed if the value is empty
     * @returns {string?}
     */
    function inputValue(name, msg) {
        let _input = input(name);
        if (isEmpty(_input)) {
            console.error(`An input with name (${name}) does not exist in window`);
            return;
        }
        let value = _input.value.trim()
        if (!isEmpty(msg) && isEmpty(value)) {
          os.ui.showAlert(msg);
          throw new Error(msg);
        }
        return value;
    }
    this.inputValue = inputValue;
}

/**
 * Provides protocol definition for a `UIWindow` controller.
 *
 * A `UIController` allows a `div.ui-window` to receive life-cycle events from the OS.
 *
 * All functions are optional. Therefore, implement only the functions needed.
 *
 * A pre-rendered `UIController` is defined on a `div.ui-window` with the `id` attribute.
 *
 * When the `id` attribute exists, it is assumed there is a `script` tag inside the `div.ui-window`.
 * The `script` tag must have a function with the same name as its `id`.
 * ```
 * <div class="ui-window" id="my_controller">
 *   <script type="text/javascript">
 *     function my_controller(view) { ... }
 *   </script>
 * </div>
 * ```
 *
 * An OS rendered `UIController` requires the window fragment to interpolate an OS provided
 * window instance ID. e.g.
 * ```
 * <div class="ui-window">
 *   <script type="text/javascript">
 *     function $(window.id)(view) { ... }
 *   </script>
 * </div>
 * ```
 */
function UIController() {
    /**
     * Initialize the controller's contents.
     *
     * Use this to load the controller's view content. Do not implement this
     * function if you do not intend to load server-side rendered view.
     *
     * @returns {object[view:source?:]} HTML view and optionally the source
     */
    async function init() { }

    /**
     * Called directly after the window is added to DOM.
     */
    function viewDidLoad() { }

    /**
     * Called directly before window is removed from DOM.
     */
    function viewWillUnload() { }

    /**
     * TODO: Called when controller becomes focused.
     */
    function viewDidFocus() { }

    /**
     * TODO: Called when controller goes out of focus.
     */
    function viewDidBlur() { }
}

function styleFolders() {
    let folders = document.getElementsByClassName("ui-folder");
    for (let i = 0; i < folders.length; i++) {
        let folder = new UIFolder(folders[i]);
    }
}

/**
 * Represents a metadata column title.
 */
function UIFolderMetadata(name, style) {
    this.name = name;
    this.style = style;
    return this;
}

function closeMenuType(className) {
    let parentClassName = className + "-container";
    var containers = document.getElementsByClassName(parentClassName);
    for (var j = 0; j < containers.length; j++) {
        let container = containers[j];
        if (container.classList.contains("popup-inactive")) {
            continue;
        }
        container.classList.remove("popup-active");
        container.classList.add("popup-inactive");
        // Reset arrow
        let choicesLabel = container.querySelector("." + className + "-label");
        choicesLabel.classList.remove("popup-arrow-active");
    }
}

/**
 * Close all popup menus.
 */
function closeAllMenus() {
    closeMenuType("ui-menu");
    closeMenuType("popup");
}

/**
 * Extract metadata column name, and style info, from list of `li`s.
 *
 * @param [li] - List of `li`s to parse that provides metadata column title information
 * @returns UIFolderMetadata
 */
function getFolderMetadata(lis) {
    let metadata = Array();
    for (let i = 0; i < lis.length; i++) {
        let name = lis[i].innerHTML;
        let style = lis[i].style;
        let m = new UIFolderMetadata(name, style);
        metadata.push(m);
    }
    return metadata;
}

/**
 * Provides folder behavior.
 *
 * @note Represents a `ul.folder` element.
 * @note To provide collapsing behavior, place a `details` element within a `ul li`
 * element.
 *
 * FIXME: Does this cause a memory leak? The `folder` instantiated outside of
 * this function may or may not be held on to.
 * @param [ul.folder] - List of `ul.folder` elements
 * @returns UIFolder | null if error
 */
function UIFolder(folder) {
    // Previously selected file
    var selectedFile = null;

    this.numFolders = 0;

    var files = folder.getElementsByTagName("li");
    // Used to determine the first "real" file within the folder. The folder tree
    // will be displayed in the first folder's row.
    for (var i = 0; i < files.length; i++) {
        var file = files[i];
        // We need to ignore the `li`s associated to metadata
        if (file.parentNode.classList.contains("metadata-title") || file.parentNode.classList.contains("metadata")) {
            // console.log("Ignoring metadata(-title) li");
            continue;
        }
        if (file.id === "") {
            console.warn("File (" + file.innerHTML  +") must have an ID");
        }

        this.numFolders = this.numFolders + 1;

        // Wrap content in a span. This allows only the text to be highlighted
        // when selected.
        var span = document.createElement("span");
        // - Parent
        if (file.firstElementChild !== null && file.firstElementChild.nodeName == "DETAILS") {
            // Get only the first summary.
            // FIXME: Should the click be on span?
            var summary = file.firstElementChild.getElementsByTagName("summary")[0];
            span.innerHTML = summary.innerHTML;
            summary.innerHTML = "";
            summary.appendChild(span);
        }
        // - Child
        else if (file.firstChild !== null && file.firstChild.nodeName == "#text") {
            var li = file;
            span.innerHTML = li.innerHTML;
            li.innerHTML = ""
            li.appendChild(span);
        }

        // Change selected li
        span.addEventListener("click", function(e) {
            e.stopPropagation();
            if (selectedFile === e.target) {
                return;
            }
            if (selectedFile !== null) {
                selectedFile.classList.remove("active");
            }
            selectedFile = e.target;
            e.target.classList.add("active");
        });
    }

    return this;
}

/**
 * Represents a Pop-up menu.
 *
 * Provides extensions to a `.popup-menu select`.
 *
 * The first option in the `select` provides information about what
 * is in the drop-down. This option is unfortunately necessary if
 * no options exist in the `select`. Otherwise, the height of the
 * drop-down will be 0, causing the `.popup-menu` to collapse.
 */
function UIPopupMenu(select) {

    // Represents the parent view container (div.popup-menu)
    let node = select.parentNode;

    function updateSelectedOptionLabel() {
        let label = select.parentNode.querySelector(".popup-label");
        label.innerHTML = select.options[select.selectedIndex].innerHTML;
    }

    function selectValue(value) {
        for (let idx = 0; idx < select.options.length; idx++) {
            if (select.options[idx].value == value) {
                selectOption(idx);
                return;
            }
        }
    }
    this.selectValue = selectValue;

    function selectOption(index) {
        select.selectedIndex = index;
        updateSelectedOptionLabel();
    }
    this.selectOption = selectOption;

    /**
     * Disable an option.
     *
     * @param {integer} index - The option's index
     */
    function disableOption(index) {
    }
    this.disableOption = disableOption;

    /**
     * Enable an option.
     *
     * @param {integer} index - The option's index
     */
    function enableOption(index) {
    }
    this.enableOption = enableOption;

    /**
     * Returns the selected option.
     */
    function selectedOption(disabled) {
        // Disabled selects are not allowed to have a selected value
        if (disabled !== true && select.disabled) {
            return null;
        }
        // The option label is not a selectable value
        if (select.selectedIndex == 0) {
            return null;
        }
        let idx = select.selectedIndex;
        return select.options[idx]
    }
    this.selectedOption = selectedOption;

    /**
     * Returns the selected option's value.
     */
    function selectedValue(disabled) {
        // Disabled selects are not allowed to have a selected value
        if (disabled !== true && select.disabled) {
            return null;
        }
        // The option label is not a selectable value
        if (select.selectedIndex == 0) {
            return null;
        }
        let idx = select.selectedIndex;
        let value = select.options[idx].value;
        return value;
    }
    this.selectedValue = selectedValue;

    function _removeAllOptions() {
        let container = select.parentNode.querySelector(".popup-choices");
        // Remove all options from the select, and facade, except first option
        for (;select.options.length > 1;) {
            select.removeChild(select.lastElementChild);
            container.removeChild(container.lastElementChild);
        }
    }

    /**
     * Remove all `option`s from `select`.
     */
    function removeAllOptions() {
        _removeAllOptions();
        styleOptions();
        updateSelectedOptionLabel();
    }

    this.removeAllOptions = removeAllOptions;

    /**
     * Add new choices into pop-up menu.
     *
     * - Parameter select: The `select` `HTMLElement`
     * - Parameter choices: Array of dictionaries, where each dictionary has an `id` and `name`.
     */
    function addNewOptions(options) {
        _removeAllOptions();

        for (let i = 0; i < options.length; i++) {
          var option = document.createElement('option');
          var opt = options[i];
          option.value = opt["id"];
          option.text = opt["name"];
          select.appendChild(option);
        }
        select.selectedIndex = 0;
        styleOptions();
        updateSelectedOptionLabel();
    }

    this.addNewOptions = addNewOptions;

    /**
     * Enable a pop-up menu.
     */
    function enable() {
        select.disabled = false;
        if (node.classList.contains("disabled")) {
            node.classList.remove("disabled");
        }
    }

    this.enable = enable;

    /**
     * Disable a pop-up meu.
     */
    function disable() {
        select.disabled = true;
        if (!node.classList.contains("disabled")) {
            node.classList.add("disabled");
        }
    }

    this.disable = disable;

    /**
     * Adds, and styles, all choices within the `select` element into the
     * `div.popup-choices`.
     */
    function styleOptions() {
        // Find the container for the popup-menu
        let container = node.querySelector(".popup-choices");
        if (container === undefined || container === null) {
            console.error("Could not find .popup-choices in select " + select);
            return;
        }

        // Create choices - ignore first choice
        for (let j = 1; j < select.length; j++) {
            let option = select.options[j];
            if (option.classList.contains("group")) {
                let group = document.createElement("div");
                group.setAttribute("class", "popup-choice-group");
                container.appendChild(group);
                continue;
            }
            let choice = document.createElement("div");
            choice.setAttribute("class", "popup-choice");
            if (option.disabled) {
                choice.classList.add("disabled");
            }
            choice.innerHTML = option.innerHTML;

            // Select a choice
            choice.addEventListener("click", function(e) {
                if (option.disabled) {
                    return;
                }
                let selectedLabel = this.parentNode.parentNode.previousSibling;
                select.selectedIndex = j;
                selectedLabel.innerHTML = this.innerHTML;
                if (select.onchange !== null) {
                    select.onchange();
                }
            });
            container.appendChild(choice);
        }
    }

    this.styleOptions = styleOptions;
}

/**
 * Style all popup menu elements.
 */
function stylePopupMenus() {
    // FIX: Does not select respective select menu. Probably because it has to be reselected.
    let menus = document.getElementsByClassName("popup-menu");
    for (let i = 0; i < menus.length; i++) {
        let selectElement = menus[i].getElementsByTagName("select")[0];
        selectElement.ui = new UIPopupMenu(selectElement);

        // The container is positioned absolute so that when a selection is made it overlays
        // the content instead of pushing it down.
        let container = document.createElement("div");
        container.setAttribute("class", "popup-container popup-inactive");
        // Inherit the parent's width (style)
        container.setAttribute("style", menus[i].getAttribute("style"));
        menus[i].removeAttribute("style");
        menus[i].appendChild(container);

        // Displays the selected option when the pop-up is inactive
        let choicesLabel = document.createElement("div");
        choicesLabel.setAttribute("class", "popup-label");
        // Display the selected default option
        choicesLabel.innerHTML = selectElement.options[selectElement.selectedIndex].innerHTML;
        container.appendChild(choicesLabel);

        // Container for all choices
        let choices = document.createElement("div");
        choices.setAttribute("class", "popup-choices");

        // Disable drop-down if select element is disabled
        if (selectElement.disabled) {
            menus[i].classList.add("disabled");
        }

        let subContainer = document.createElement("div");
        subContainer.setAttribute("class", "sub-container");
        subContainer.appendChild(choices);
        container.appendChild(subContainer);

        selectElement.ui.styleOptions(selectElement);

        /**
         * Toggle the popup-menu's state.
         *
         * If the state is inactive, the menu will be displayed. If active,
         * the menu will become hidden.
         *
         * NOTE: Only the first div in the container should have the click
         * event associated to the toggle state.
         */
        choicesLabel.addEventListener("click", function(e) {
            let popupMenu = this.parentNode.parentNode;
            if (!popupMenu.classList.contains("popup-menu")) {
                console.error("Expected parent to be a popup-menu")
                return;
            }
            // Do nothing if the control is disabled
            if (popupMenu.classList.contains("disabled")) {
                return;
            }
            let container = popupMenu.querySelector(".popup-container");
            let isActive = container.classList.contains("popup-active");
            e.stopPropagation();
            closeAllMenus();
            // Show menu
            if (!isActive) {
                container.classList.remove("popup-inactive");
                container.classList.add("popup-active");
                this.classList.add("popup-arrow-active");
            }
            // User tapped on pop-up menu when it was active. This means they wish to collapse
            // (toggle) the menu's activate state.
            else {
                container.classList.remove("popup-active");
                container.classList.add("popup-inactive");
                this.classList.remove("popup-arrow-active");
            }
        });
    }
}

/**
 * UI menu displayed in OS bar.
 *
 * @param {HTMLElement} select - The `select` backing store
 * @param {HTMLElement} container - The menu container
 */
function UIMenu(select, container) {

    /**
     * Remove option from menu.
     *
     * @param {mixed} value - The value of the option to remove
     */
    function removeOption(value) {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                select.remove(i);
                option.ui.remove();
                break;
            }
        }
    }
    this.removeOption = removeOption;

    /**
     * Disable a menu option.
     *
     * @param {mixed} value - The value of the option to disable
     */
    function disableOption(value) {
        // TODO: Not tested
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                option.disabled = true;
                if (!option.ui.classList.contains("disabled")) {
                    option.ui.classList.add("disabled");
                }
                break;
            }
        }
    }
    this.disableOption = disableOption;
}

/**
 * Style menus displayed in the OS bar.
 */
function styleUIMenus(target) {
    if (isEmpty(target)) {
        console.warn("Attempting to style UI menus in null target.");
        return;
    }

    // FIX: Does not select respective select menu. Probably because it has to be reselected.
    let menus = target.getElementsByClassName("ui-menu");
    for (let i = 0; i < menus.length; i++) {
        let selectElement = menus[i].getElementsByTagName("select")[0];

        // The container is positioned absolute so that when a selection is made it overlays
        // the content instead of pushing it down.
        let container = document.createElement("div");
        container.setAttribute("class", "ui-menu-container popup-inactive");
        menus[i].appendChild(container);

        selectElement.ui = new UIMenu(selectElement, container);

        // The first option is the label for the menu
        let menuLabel = document.createElement("div");
        menuLabel.setAttribute("class", "ui-menu-label");
        let label = selectElement.options[0].innerHTML;
        if (label.startsWith("img:")) {
            let img = document.createElement("img");
            img.src = label.split(":")[1];
            menuLabel.appendChild(img);
        }
        else {
            menuLabel.innerHTML = label;
        }
        container.appendChild(menuLabel);

        // Container for all choices
        let choices = document.createElement("div");
        choices.setAttribute("class", "popup-choices");

        // Create choices
        // NOTE: This skips the first choice (menu label)
        for (let j = 1; j < selectElement.length; j++) {
            let option = selectElement.options[j];
            if (option.classList.contains("group")) {
                let group = document.createElement("div");
                group.setAttribute("class", "popup-choice-group");
                choices.appendChild(group);
                continue;
            }
            let choice = document.createElement("div");
            choice.setAttribute("class", "popup-choice");
            if (option.disabled) {
                choice.classList.add("disabled");
            }
            // Adopt ID
            let optionID = option.getAttribute("id");
            if (!isEmpty(optionID)) {
                choice.setAttribute("id", option.getAttribute("id"));
                option.setAttribute("id", "");
            }
            choice.innerHTML = option.innerHTML;
            choice.addEventListener("click", function() {
                if (option.disabled) {
                    return;
                }
                if (option.onclick !== null) {
                    option.onclick();
                }
            });
            choices.appendChild(choice);
            option.ui = choice;
        }
        // Required to display border around options
        let subContainer = document.createElement("div");
        subContainer.setAttribute("class", "sub-container");
        // Inherit the parent's width (style)
        subContainer.setAttribute("style", menus[i].getAttribute("style"));
        menus[i].removeAttribute("style");
        subContainer.appendChild(choices);
        container.appendChild(subContainer);

        /**
         * Toggle the menu's state.
         *
         * If the state is inactive, the menu will be displayed. If active,
         * the menu will become hidden.
         *
         * NOTE: Only the first div in the container should have the click
         * event associated to the toggle state.
         */
        menuLabel.addEventListener("click", function(e) {
            var container = this.parentNode; // ui-menu-container
            var isActive = container.classList.contains("popup-active");
            e.stopPropagation();
            closeAllMenus();
            // User tapped on pop-up menu when it was active. This means they wish to collapse
            // (toggle) the menu's activate state.
            if (!isActive) {
                container.classList.remove("popup-inactive");
                container.classList.add("popup-active");
                this.classList.add("popup-arrow-active");
            }
            else {
                container.classList.remove("popup-active");
                container.classList.add("popup-inactive");
                this.classList.remove("popup-arrow-active");
            }
        });
    }
}

/**
 * Finds the next sibling given a class name.
 */
function findNextSiblingWithClass(element, className) {
    let sibling = element.nextElementSibling;

    while (sibling) {
        if (sibling.classList && sibling.classList.contains(className)) {
            return sibling;
        }
        sibling = sibling.nextElementSibling;
    }
    return null;
}

function UIImageViewer() {

    let element = {};

    /**
     * Close a (modal) window.
     *
     * Removes the window from the view hierarchy.
     *
     * - Parameter win: The window to close.
     */
    function closeWindow(win) {
        const parent = win.parentNode;
        parent.removeChild(win);
    }

    function showImage(href) {
        let img = element.querySelector("img");
        img.src = href;
        let desktop = document.getElementById("desktop");
        desktop.appendChild(element);
    }

    this.showImage = showImage;

    function make() {
        var fragment = document.getElementById("image-viewer-fragment");
        var modal = fragment.querySelector(".ui-modal").cloneNode(true);
        var button = modal.querySelector("button.default");
        button.addEventListener("click", function() {
            closeWindow(modal);
        });
        modal.classList.add("center-control");
        return modal;
    }

    element = make();
}

/** List Boxes **/

function UIListBox(select, container) {

    let delegate = null;
    function setDelegate(d) {
        delegate = d;
    }
    this.setDelegate = setDelegate;

    /**
     * Select an option by its value.
     *
     * @param {string} value - Value of option to select
     */
    function selectValue(value) {
        for (let idx = 0; idx < select.options.length; idx++) {
            if (select.options[idx].value == value) {
                selectOption(idx);
                return;
            }
        }
    }
    this.selectValue = selectValue;

    /**
     * Select an option by its index.
     *
     * @param {int} index - Index of option to select
     */
    function selectOption(index) {
        select.selectedIndex = index;
        for (let i = 0; i < select.options.length; i++) {
            let opt = select.options[i];
            opt.ui.classList.remove("selected");
            if (opt.selected) {
                opt.ui.classList.add("selected");
                didSelectListBoxOption(opt);
            }
        }
    }
    this.selectOption = selectOption;

    function removeAllOptions() {
        // Remove all options from the select and facade
        for (;select.options.length > 0;) {
            select.removeChild(select.lastElementChild);
            container.removeChild(container.lastElementChild);
        }
    }

    /**
     * This is useful only for multiple list boxes. This will always
     * return true if not `multiple`.
     *
     * @returns {bool} `true` when there is at least one option selected.
     */
    function hasSelectedOption() {
        if (select.mutiple) {
            return true;
        }
        return select.selectedOptions.length > 0;
    }
    this.hasSelectedOption = hasSelectedOption;

    /**
     * Add all new options to the list box.
     *
     * This will remove all existing options.
     *
     * @param {[object[id:name:]]} Options to add.
     */
    function addNewOptions(options) {
        removeAllOptions();

        for (let i = 0; i < options.length; i++) {
            let option = document.createElement("option");
            let opt = options[i];
            option.value = opt.id;
            option.text = opt.name;
            select.appendChild(option);
        }

        if (!select.multiple) {
            select.selectedIndex = 0;
        }
        styleOptions();
    }
    this.addNewOptions = addNewOptions;

    /**
     * Add option to end of list.
     *
     * @param {object[id:name:]} model - Option to add to list
     */
    function addOption(model) {
        let option = new Option(model.name, model.id);
        select.add(option, undefined); // Append to end of list
        styleOption(option);
    }
    this.addOption = addOption;

    /**
     * Remove option from list by its value.
     *
     * @param {string} value - Value of option to remove
     */
    function removeOption(value) {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                select.remove(i);
                container.removeChild(option.ui)
                break;
            }
        }
    }
    this.removeOption = removeOption;

    /**
     * Return the selected option.
     *
     * Use this only for single option select lists.
     *
     * @returns {HTMLOption?} The selected option. `null` if `select` is disabled.
     */
    function selectedOption() {
        if (select.disabled) {
            return null;
        }
        let idx = select.selectedIndex;
        return select.options[idx]
    }
    this.selectedOption = selectedOption;

    /**
     * Returns the value of the selected option, if any.
     *
     * @returns {any?}
     */
    function selectedValue() {
        let opt = selectedOption();
        return opt?.value;
    }
    this.selectedValue = selectedValue;

    /**
     * Returns list of selected options.
     *
     * Use this only for multiple option select lists.
     *
     * @returns {[HTMLOption]} The selected options
     */
    function selectedOptions() {
        if (select.disabled) {
            return [];
        }
        return select.selectedOptions;
    }
    this.selectedOptions = selectedOptions;

    function styleOption(option) {
        let elem = document.createElement("div");
        let label = option.innerHTML;
        let labels = label.split(",");

        // Label has an image
        if (labels.length == 2) {
            let imgLabel = labels[0].trim();
            if (!imgLabel.startsWith("img:")) {
                console.warn("The first label item must be an image");
                elem.innerHTML = label;
            }
            else {
                let img = document.createElement("img");
                img.src = imgLabel.split(":")[1];
                elem.appendChild(img);
                let span = document.createElement("span");
                span.innerHTML = labels[1];
                elem.append(span);
            }
        }
        else {
            elem.innerHTML = label;
        }

        elem.classList.add("option");
        if (option.disabled) {
            elem.classList.add("disabled");
        }
        // When `select` is not `multiple`, selected index is always 0. This causes
        // the first option to always be selected. There's no way around this.
        if (option.selected) {
            elem.classList.add("selected");
        }
        for (let j = 0; j < option.classList.length; j++) {
            elem.classList.add(option.classList[j]);
        }
        option.ui = elem;

        container.appendChild(elem);
        elem.addEventListener("mouseup", function(obj) {
            if (select.multiple) {
                option.selected = !option.selected;
                elem.classList.remove("selected");
                if (option.selected) {
                    elem.classList.add("selected");
                }
                if (option.selected) {
                    didSelectListBoxOption(option);
                }
                else {
                    didDeselectListBoxOption(option);
                }
            }
            else {
                selectValue(option.value);
            }
        });
    }

    function styleOptions() {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            styleOption(option);
        }
    }

    function didSelectListBoxOption(option) {
        if (isEmpty(delegate?.didSelectListBoxOption)) {
            return;
        }
        delegate.didSelectListBoxOption(option);
    }
    function didDeselectListBoxOption(option) {
        if (isEmpty(delegate?.didDeselectListBoxOption)) {
            return;
        }
        delegate.didDeselectListBoxOption(option);
    }

    styleOptions();
}

function styleListBox(list) {
    let container = document.createElement("div");
    container.classList.add("container");
    for (let prop in list.style) {
        if (list.style[prop] !== '') {
            container.style[prop] = list.style[prop];
        }
    }
    list.style = null;
    list.appendChild(container);

    let select = list.querySelector("select");
    let box = new UIListBox(select, container);
    select.ui = box;
}

function styleListBoxes(elem) {
    let lists = elem.getElementsByClassName("ui-list-box");
    for (let i = 0; i < lists.length; i++) {
        let list = lists[i];
        styleListBox(list);
    }
}
