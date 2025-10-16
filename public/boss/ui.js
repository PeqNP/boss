/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

function Point(x, y) {
    readOnly(this, "x", x);
    readOnly(this, "y", y);
}

// Represents an app link that is displayed in the Dock. Please note: `AppLink`s
// are probably being passed-thru from the server w/o being transformed i.e. (duck-typing)
function AppLink(bundleId, name, icon) {
    readOnly(this, "bundleId", bundleId);
    readOnly(this, "name", name);
    readOnly(this, "icon", icon);
}

/**
 * @param {string} id
 * @param {string} name
 * @param {mixed?} data - attach metadata to choice
 */
function UIPopupMenuChoice(id, name, data) {
    readOnly(this, "id", id);
    readOnly(this, "name", name);
    readOnly(this, "data", data);
}

/**
 * @param {string} id
 * @param {string} name
 * @param {bool?} child - show as a child option
 * @param {mixed?} data - attach metadata to choice
 */
function UIListBoxChoice(id, name, child, data) {
    readOnly(this, "id", id);
    readOnly(this, "name", name);
    readOnly(this, "child", child);
    readOnly(this, "data", data);
}

/**
 * @param {bool} setModelToData - Assign the respective model to the respective `.data` property on option
 */
function UIListBoxChoiceConfig(setModelToData) {
    readOnly(this, "setModelToData", setModelToData);
}

/**
 * @param {string} id
 * @param {string} name
 * @param {bool?} close - show close button
 * @param {mixed?} data - attach metadata to choice
 */
function UITabChoice(id, name, close) {
    readOnly(this, "id", id);
    readOnly(this, "name", name);
    readOnly(this, "close", close);
    readOnly(this, "data", data);
}

/**
 * Provides access to UI library.
 */
function UI(os) {
    // Modal z-index is defined to be above all other windows. Therefore, the max
    // number of windows that can be displayed is ~1998.
    const MODAL_START_ZINDEX = 1999;

    // Starting z-index for windows
    const WINDOW_START_ZINDEX = 10;

    // List of "open" window controllers.
    let controllers = {};

    // Contains a list of displayed windows. The index of the array is the window's
    // respective z-index + WINDOW_START_ZINDEX.
    let windowIndices = [];

    // Contains list of displayed modals.
    let modalIndices = [];

    // Tracks the number of stagger steps have been made when windows are opened.
    // When a new window is opened, it is staggered by 10px top & left from the
    // previously opened window.
    // When all windows are closed, this reverts to 0.
    let windowStaggerStep = 0;
    // The total number of times to stagger before resetting back to 0.
    const MAX_WINDOW_STAGGER_STEPS = 5;
    // Number of pixels to stagger from top & left in each step
    const WINDOW_STAGGER_STEP = 10;

    this.desktop = new Desktop(this);

    /**
     * Location within the Settings app that a user may
     * navigate to.
     */
    const SettingsLocation = {
        users: 0,
        friends: 1
    };
    readOnly(this, "SettingsLocation", SettingsLocation);

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
        // Pop-up menus are displayed even before windows are shown (e.g. OS bar)
        styleAllUIPopupMenus(document);

        // Style hard-coded system menus
        os.ui.styleUIMenus(document.getElementById("os-bar"));

        /**
         * Close all menus when user clicks outside of `select`.
         */
        document.addEventListener("click", closeAllMenus);

        document.addEventListener("keydown", function(e) {
            if (e.key == "Enter") {
                // This prevents the "Enter" key from activating the last tapped
                // (focused) button. When _any_ button is tapped, most browsers will
                // automatically make that button focused. This is huge problem if you
                // tapped something like `Delete`, cancelled, and then hit "Enter",
                // where the default action may be to cancel the operation.
                //
                // It would essentially fire both the `Delete` button's action _and_ whatever
                // the action is associated to the controllers `this.didHitEnter` function.
                //
                // What this does is prevent the browser's default behavior from triggering
                // when "Enter" is tapped on elements that may be triggered when the "Enter"
                // key is pressed.
                e.preventDefault();

                let topModal = modalIndices[modalIndices.length - 1];
                if (!isEmpty(topModal)) {
                    topModal.ui.didHitEnter();
                    return;
                }

                let topWindow = windowIndices[windowIndices.length - 1];
                if (!isEmpty(topWindow)) {
                    topWindow.ui.didHitEnter();
                    return;
                }
                return;
            }

            let topModal = modalIndices[modalIndices.length - 1];
            if (!isEmpty(topModal)) {
                topModal.ui.didHitKey(e.key);
                return;
            }

            let topWindow = windowIndices[windowIndices.length - 1];
            if (!isEmpty(topWindow)) {
                topWindow.ui.didHitKey(e.key);
                return;
            }
        });

        os.ui.desktop.init();
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
            let leftPos = container.offsetLeft - pos1;
            container.style.top = `${topPos}px`;
            container.style.left = `${leftPos}px`;
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
     * Please note
     *
     * Modals are expected to be added and removed in FILO order. A new modal
     * is displayed on top of all other windows, including other modals.
     * Therefore, the process in which they are removed should be FILO. This
     * also means the logic to assign the zIndex is simplified. The most recent
     * is always on top and the z-index will never get out of order.
     *
     * That being said, removeModal doesn't take chances. It still finds the
     * modal and removes it by ID. But it does not repair z-index, by matching
     * index to its respective position in modelIndices (like windows do), as
     * it should never happen.
     */

    /**
     * Assign modal (overlay) z-index and register as visible modal.
     *
     * @param {HTMLElement}
     */
    function addModal(container) {
        let zIndex = MODAL_START_ZINDEX + modalIndices.length;
        container.style.zIndex = `${zIndex}`;
        modalIndices.push(container);
    }

    /**
     * Remove modal (overlay) from visible modals.
     *
     * @param {HTMLElement}
     */
    function removeModal(container) {
        for (let i = 0; i < modalIndices.length; i++) {
            let modal = modalIndices[i];
            if (modal.id == container.id) {
                modalIndices.splice(i, 1);
                return;
            }
        }
        console.warn(`Attempting to remove modal (${container.id}) from modal stack that is not in stack`);
    }

    /**
     * Adds and registers a window container z-index.
     *
     * @param {HTMLElement} container - The window's container `div`
     */
    function addWindow(container) {
        if (container.ui.isModal) {
            return addModal(container);
        }

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
        if (container.ui.isModal) {
            return removeModal(container);
        }
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
        if (container.ui.isModal) {
            addModal(container);
            container.ui.didFocusWindow();
            return;
        }

        let topZIndex = windowIndices.length - 1 + WINDOW_START_ZINDEX;

        let isTopWindow = parseInt(container.style.zIndex) === topZIndex;

        // NOTE: The top-most window may be blurred as the previous top-most
        // window may have just been removed from the stack. When this happens
        // focus immediately.
        let isBlurred = container.classList.contains("blurred")
        if (isTopWindow && isBlurred) {
            os.switchApplicationMenu(container.ui.bundleId);
            container.ui.didFocusWindow();
            return;
        }
        // Already the top window. No-op.
        else if (isTopWindow) {
            return;
        }

        let topWindow = windowIndices[windowIndices.length - 1];

        if (!isEmpty(topWindow)) {
            topWindow.ui.didBlurWindow();
        }

        // Move container to the top of the window stack.
        removeWindow(container);
        addWindow(container);

        os.switchApplicationMenu(container.ui.bundleId);
        container.ui.didFocusWindow();
    }
    this.focusWindow = focusWindow;

    /**
     * Blur top-most window.
     *
     * This happens when switching applications.
     */
    function blurTopWindow() {
        // No windows to blur
        if (windowIndices.length === 0) {
            return;
        }
        let topWindow = windowIndices[windowIndices.length - 1];
        topWindow.ui.didBlurWindow();
    }
    this.blurTopWindow = blurTopWindow;

    /**
     * Focus the top-most window.
     *
     * This only focuses on passive and active windows.
     *
     * This is generally called directly after a window is removed from the
     * desktop.
     *
     * @returns `true` when a window is focused
     */
    function focusTopWindow() {
        // No windows to focus
        if (windowIndices.length === 0) {
            return false;
        }

        for (let i = windowIndices.length; i > 0; i--) {
            let topWindow = windowIndices[i - 1];
            if (os.switchApplicationMenu(topWindow.ui.bundleId)) {
                topWindow.ui.didFocusWindow();
                return true;
            }
        }

        return false; // Should never enter here
    }
    this.focusTopWindow = focusTopWindow;

    function appContainerId(bundleId) {
        return `app-container-${bundleId}`;
    }
    this.appContainerId = appContainerId;

    let windowNumber = 0;

    function makeWindowId() {
        // let objectId = makeObjectId();
        // return `Window_${windowNumber}_${objectId}`;

        // This is a much easier way to identify windows. When using the object ID
        // it's difficult to see which one is the newest one, as script that are
        // removed from the DOM are still in the list of scripts that can be
        // debugged.
        windowNumber += 1;
        let num = windowNumber.toString().padStart(6, "0");
        return `Window_${num}`;
    }

    /**
     * Create window attributes.
     *
     * Window attributes provide a way for a `.ui-window` to reference:
     * - Their controller's instance
     * - Respective app instance
     * - OS information
     *
     * @param {string} bundleId - The application bundle ID
     */
    function makeWindowAttributes(bundleId) {
        // FIXME: This assumes the object ID always exists.
        let id = makeWindowId();

        const attr = {
            app: {
                bundleId: bundleId,
                resourcePath: `/boss/app/${bundleId}`,
                controller: `os.application('${bundleId}').proxy`
            },
            os: {
                // dev|prod
                environment: os.environment,
                // Root HTTP path e.g. https://localhost or https://io.bithead
                host: os.host,
                email: "bitheadRL AT proton.me",
                // Getting too much spam. For clients that have the OS installed locally,
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
    this.makeWindowAttributes = makeWindowAttributes;

    /**
     * Parses all controller refrerences to controller instances.
     *
     * e.g. A value in HTML `%(myController)` will be replaced with
     * `os.ui.controller.myController`.
     *
     * This is designed to conveniently reference an embedded `UIController`'s
     * controller from within its respective view.
     *
     * @param {string} html - HTML that contains possible controller refs
     * @returns string
     */
    function interpolateControllerRefs(str) {
        return str.replace(/%\((.*?)\)/g, (x, id) => `os.ui.controller.${id}`);
    }

    /**
     * Creates temporary element that parses HTML and re-attached Javascript to
     * work-around HTML5 preventing untrusted scripts from parsing when setting
     * innerHTML w/ dynamic content.
     *
     * @param {string} bundleId - App bundle ID that window belongs to
     * @param {string} controllerName - Name of controller
     * @param {Object} attr - Attributes to assign to window
     * @param {string} html - HTML to add to window container
     * @returns `div` that contains parsed HTML and re-attached Javascript
     */
    function parseHTML(bundleId, controllerName, attr, html) {
        let div = document.createElement("div");
        // Interpolate `$(val)` to respective value from attributes
        var parsed = interpolate(html, attr);
        // Replace all instance of %(controllerName) w/ reference to controller
        // instance.
        parsed = interpolateControllerRefs(parsed);

        div.innerHTML = parsed;

        // You must re-attach any scripts that are part of the HTML. Since HTML5
        // JavaScript is not parsed or ran when assigning values to innerHTML.
        //
        // Attach scripts, if any.
        //
        // A window may have more than one script if there are embedded controllers.
        let scripts = div.querySelectorAll("script");
        for (let i = 0; i < scripts.length; i++) {
            let script = scripts[i];
            let parentNode = script.parentNode;
            parentNode.removeChild(script);

            let sc = document.createElement("script");
            sc.setAttribute("type", "text/javascript");
            let inline = document.createTextNode(script.innerHTML + `\n//@ sourceURL=/${bundleId}/${controllerName}/${attr.this.id}/${i}`);
            sc.appendChild(inline);
            parentNode.append(sc);
        }

        /**
         * Associate unique ID for field types.
         *
         * This is designed to create a relationship between a `label`
         * and its respective `input`.
         *
         * This only occurs for OS typed fields e.g. `text-field`, `textarea-field`, etc.
         */

        // Create relationship between label and input `text-field` types.
        let textFields = div.querySelectorAll(".text-field");
        for (let i = 0; i < textFields.length; i++) {
            let field = textFields[i];
            let label = field.querySelector("label");
            if (isEmpty(label)) {
                console.warn(`Text field in (${bundleId}) for (${controllerName}) has no label`);
                continue;
            }
            let input = field.querySelector("input");
            if (isEmpty(input)) {
                console.warn(`Text field in (${bundleId}) for (${controllerName}) has no input`);
                continue;
            }
            let _for = label.getAttribute("for");
            if (isEmpty(_for)) {
                console.warn(`Text field in (${bundleId}) for (${controllerName}) label has no 'for'`);
                continue;
            }
            // Sanity check. The `label.for` must be the same value as `input.name`
            if (_for !== input.name) {
                console.warn(`Text field in (${bundleId}) for (${controllerName}) label 'for' doees not match input 'name'`);
            }

            let fieldId = `${_for}-${generateUUID()}`
            label.setAttribute("for", fieldId);
            input.id = fieldId;
        }

        return div;
    }

    /**
     * Returns the next window's staggered position.
     *
     * @returns Point
     */
    function nextWindowStaggerPoint() {
        windowStaggerStep += 1;
        if (windowStaggerStep > MAX_WINDOW_STAGGER_STEPS) {
            windowStaggerStep = 1;
        }

        // The amount of space to offset the Y position due to the OS bar
        const TOP_OFFSET = 40;
        // Slight padding on left
        const LEFT_OFFSET = 10;

        let posTop = windowStaggerStep * WINDOW_STAGGER_STEP + TOP_OFFSET;
        let posLeft = windowStaggerStep * WINDOW_STAGGER_STEP + LEFT_OFFSET;

        return new Point(posTop, posLeft);
    }

    /**
     * Creates an instance of a `UIWindow` from an HTML string.
     *
     * This is designed to work with:
     * - `OS` facilities to launch an application
     * - Create new windows from `UI.makeController(name:)`
     *
     * @param {string} bundleId: App bundle ID creating window
     * @param {string} controllerName: Name of controller
     * @param {string} menuId: The app's menu ID
     * @param {string} html: Window HTML to render
     * @returns `UIWindow`
     */
    function makeWindow(bundleId, controllerName, menuId, html) {
        const attr = makeWindowAttributes(bundleId);

        let div = parseHTML(bundleId, controllerName, attr, html);

        let container = document.createElement("div");
        // The ID is not functionally necessary. This is for debugging.
        container.id = attr.this.id;
        container.classList.add("ui-container");
        container.appendChild(div.firstChild);
        let point = nextWindowStaggerPoint();
        container.style.top = `${point.x}px`;
        container.style.left = `${point.y}px`;

        container.ui = new UIWindow(bundleId, attr.this.id, container, false, menuId);
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
     * @param {string} controllerName: Name of controller
     * @param {string} html: Modal HTML to render
     * @returns `UIWindow`
     */
    function makeModal(bundleId, controllerName, html) {
        const attr = makeWindowAttributes(bundleId);

        let div = parseHTML(bundleId, controllerName, attr, html);

        // Wrap modal in an overlay to prevent taps from outside the modal
        let overlay = document.createElement("div");
        overlay.classList.add("ui-modal-overlay");

        // Container is used for positioning
        let container = document.createElement("div");
        container.classList.add("ui-modal-container");
        container.appendChild(div.firstChild);
        overlay.appendChild(container);

        overlay.ui = new UIWindow(bundleId, attr.this.id, overlay, true);
        overlay.id = attr.this.id; // Debugging
        return overlay;
    }
    this.makeModal = makeModal;

    /**
     * Register embedded controllers in `UIWindow`.
     *
     * Controllers are embedded elements inside a `UIWindow`. A good example of
     * this is a "Search" component which may be used in several `UIWindow`s.
     *
     * `UIController``s may reference their respective Javascript model the same
     * way as `UIWindow`s. e.g. `os.ui.controller.ControllerName`.
     */
    function registerEmbeddedControllers(container) {
        let controllers = container.getElementsByClassName("ui-controller");
        for (let i = 0; i < controllers.length; i++) {
            registerEmbeddedController(controllers[i]);
        }
    }
    this.registerEmbeddedControllers = registerEmbeddedControllers;

    /**
     * Register an embedded `UIController` with the OS.
     *
     * TODO: Disambiguate embedded controllers w/in containing `UIWindow`.
     * For now, embedded controllers must define their own ID and must not use
     * `$(this.x)`.
     */
    function registerEmbeddedController(component) {
        let id = component.getAttribute("id");
        if (isEmpty(id)) {
            console.error("Embedded UIController must have an ID. Loading stopped.");
            return;
        }

        if (typeof window[id] === "function") {
            let code = new window[id](component);
            component.ui = new _UIController(component);
            let ctrl = eval(code);
            if (!isEmpty(ctrl)) {
                if (!isEmpty(ctrl.viewDidLoad)) {
                    ctrl.viewDidLoad();
                }
                addController(id, ctrl);
            }
        }
        else {
            console.warn(`Expected embedded UIController (${id}) to have a script`);
        }
    }

    /**
     * Add single, or multiple, menus in the OS bar.
     *
     * @param {HTMLElement} menu - The menu to attach to the OS bar
     * @param {string?} menuId - The optional menu ID to attach to (required for app windows)
     */
    function addOSBarMenu(menu, menuId) {
        if (isEmpty(menuId)) {
            var p = document.getElementById("os-bar-menus");
            if (isEmpty(p)) {
                console.error("The OS Bar element, `os-bar-menus`, is not in DOM.");
                return;
            }
            p.appendChild(menu);
        }
        else {
            var div = document.getElementById(menuId);
            if (isEmpty(div)) {
                console.error(`The OS Bar element w/ ID (${menuId}) is not in DOM.`);
                return;
            }
            div.appendChild(menu);
        }
    }
    this.addOSBarMenu = addOSBarMenu

    /**
     * Add app menu to OS bar.
     *
     * An app menu is a `ui-menu` that can display a menu of options or a mini app.
     * These menus should be displayed only when the app is blurred.
     */
    function addOSBarApp(menu) {
        let div = document.getElementById("os-bar-apps");
        if (isEmpty(div)) {
            console.error("The OS Bar Apps element, `os-bar-apps`, is not in DOM.");
            return;
        }
        div.appendChild(menu);
    }
    this.addOSBarApp = addOSBarApp;

    /**
     * Shows the user settings application.
     *
     * @param {SettingsLocation?} loc - Location w/in settings to navigate to
     */
    async function openSettings(loc) {
        let app = await os.openApplication("io.bithead.settings");
        let win = await app.loadController("Home");
        win.ui.show(function(ctrl) {
            ctrl.configure(loc);
        });
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
        modal.ui.show(function(ctrl) {
            ctrl.configure(error);
        });
    }
    // @deprecated - use `showError` to follow naming convention
    this.showErrorModal = showErrorModal;
    this.showError = showErrorModal;

    /**
     * Show a delete modal.
     *
     * Ask user if they want to delete a model. This can be used in all contexts
     * where a destructive action can take place.
     *
     * @param {string} msg - The (question) message to display.
     * @param {async function} cancel - A function that is called when user presses `Cancel`
     * @param {async function} ok - A function that is called when user presses `OK`
     * @returns {Promise}
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
        let promise;
        modal.ui.show(function(controller) {
            promise = controller.configure(cancel, ok, msg);
        });
        return promise;
    }
    // @deprecated - use `showDelete` to follow naming convention
    this.showDeleteModal = showDeleteModal;
    this.showDelete = showDeleteModal;

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
        modal.ui.show(function (ctrl) {
            ctrl.configure(msg);
        });
    }
    this.showAlert = showAlert;

    /**
     * Show inactivity modal.
     *
     * The inactivity modal indiates to the user that they must perform some
     * type of action before they are logged out automatically.
     */
    async function showInactivity() {
        if (!os.isLoaded()) {
            console.error("OS is not loaded. Can not show inactivity.");
            return;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("Inactivity");
        modal.ui.show();
    }
    this.showInactivity = showInactivity;

    /**
     * Show the "Register MFA" challenge modal.
     *
     * @param {function} fn - Function will be called when user successfully registers MFA
     */
    async function showRegisterMFA(fn) {
        if (!os.isLoaded()) {
            console.error("OS is not loaded. Can not show MFA registration.");
            return;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("RegisterMFA");
        modal.ui.show(function (ctrl) {
            ctrl.delegate = {
                didRegisterMFA: fn
            }
        });
    }
    this.showRegisterMFA = showRegisterMFA;

    /**
     * Show a generic info modal with `OK` button.
     *
     * If you wish to wait for the user's input, `await` this function
     * and it will return after the user presses the `OK` button.
     *
     * If the OS is not loaded, this logs the message to console.
     *
     * @param {string} msg - Message to display to user.
     */
    async function showInfo(msg) {
        if (!os.isLoaded()) {
            console.warn(msg);
            return;
        }

        return new Promise(async function(resolve, reject) {
            let app = await os.openApplication("io.bithead.boss");
            let modal = await app.loadController("Info");
            modal.ui.show(function(ctrl) {
                ctrl.configure(msg, resolve);
            });
        });
    }
    this.showInfo = showInfo;

    /**
     * Show sign in page.
     */
    async function showSignIn() {
        if (!os.isLoaded()) {
            console.error("OS is not loaded. Can not sign in.");
            return;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("SignIn");
        modal.ui.show();
    }
    this.showSignIn = showSignIn;

    /**
     * Show create account.
     */
    async function showCreateAccount() {
        if (!os.isLoaded()) {
            console.error("OS is not loaded. Can not create an account.");
            return;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("CreateAccount");
        modal.ui.show();
    }
    this.showCreateAccount = showCreateAccount;

    /**
     * Show welcome page.
     */
    async function showWelcome() {
        if (!os.isLoaded()) {
            console.error("OS is not loaded. Can not show Welcome page.");
            return;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("Welcome");
        modal.ui.show();
    }
    this.showWelcome = showWelcome;

    /**
     * Show a cancellable progress bar modal.
     *
     * Use this when performing long running actions that may be cancelled.
     *
     * When the `Stop` button is tapped, regardless if `fn` is set, the button
     * will become disabled. This visual feedback informs user that the operation
     * can only be performed once.
     *
     * @param {string} title - Message to show in progress bar
     * @param {async function} fn - The async function to call when the `Stop` button is pressed.
     * @param {bool} indeterminate - If `true`, this will show an indeterminate progress bar. Default is `false`.
     * @returns UIProgressBar if OS is loaded. Otherwise, returns `null`.
     * @throws
     */
    async function showProgressBar(title, fn, indeterminate) {
        if (!os.isLoaded()) {
            return null;
        }
        if (!isEmpty(fn) && !isAsyncFunction(fn)) {
            throw new Error(`Callback function for progress bar (${title}) is not async function`);
        }

        if (isEmpty(indeterminate)) {
            indeteriminate = false;
        }

        let app = await os.openApplication("io.bithead.boss");
        let modal = await app.loadController("ProgressBar");
        modal.ui.show(function (ctrl) {
            ctrl.configure(title, fn, indeterminate);
            modal.setProgress = ctrl.setProgress;
        });

        return modal;
    }
    this.showProgressBar = showProgressBar;

    // Used by "busy" state to prevent touches from being made to UI
    let busyOverlay = null;

    let busyCounter = 0;

    /**
     * Show "busy" cursor.
     */
    function showBusy() {
        busyCounter += 1;

        document.body.style.cursor = "url('/boss/img/watch.png'), auto";

        busyOverlay = document.createElement("div");
        busyOverlay.classList.add("ui-modal-overlay");

        let desktop = document.getElementById("desktop");
        desktop.appendChild(busyOverlay);
    }
    this.showBusy = showBusy;

    /**
     * Hide "busy" state.
     */
    function hideBusy() {
        busyCounter -= 1;

        if (busyCounter < 1) {
            document.body.style.cursor = null;
            busyOverlay.remove();
            busyOverlay = null;
            busyCounter = 0;
        }
    }
    this.hideBusy = hideBusy;

    /**
     * Hides app menu, if it exists.
     *
     * Currently the only consumer is the OS when it needs to switch
     * applications. The act of switching the app should also close
     * any app menu.
     */
    function hideAppMenu(bundleId) {
        let id = `AppMenu_${bundleId}`;
        let container = document.getElementById(id);
        if (isEmpty(container)) {
            return;
        }

        let buttonId = `AppWindowButton_${bundleId}`;
        let button = document.getElementById(buttonId);
        button.classList.remove("active");

        let appMenu = container.querySelector(".ui-app-menu");
        if (!isEmpty(appMenu)) {
            appMenu.style.display = "none";
        }
    }
    this.hideAppMenu = hideAppMenu;

    /**
     * Create an app button used to switch to the application.
     *
     * The anatomy of an `ui-app-window` is similar to a `ui-window and `ui-modal.
     * They are all `UIWindow`s. An app window is displayed when its respective
     * app menu button is tapped in the OS bar. This creates the OS bar button and
     * the window.
     *
     * It is possible to make an app window with no window. In this context, the
     * app menu button simply switches the application when tapped, rather than
     * showing a window.
     *
     * @param {AppConfig} config - Application configuration
     * @param {HTMLElement} appMenu - Custom app menu to show when tapped
     */
    function makeAppButton(config, appMenu) {
        let bundleId = config.application.bundleId;
        let container = document.createElement("div");
        let div = document.createElement("div");
        container.appendChild(div);
        div.id = `AppWindowButton_${bundleId}`;
        div.classList.add("app-icon");
        let img = document.createElement("img");
        img.src = `/boss/app/${bundleId}/${config.application.icon}`;
        div.appendChild(img);

        // Button
        if (isEmpty(appMenu)) {
            div.addEventListener("click", function () {
                os.switchApplication(`${bundleId}`);
            });
        }
        // Custom app menu
        else {
            appMenu.style.position = "absolute";
            appMenu.style.display = "none";
            appMenu.style.top = "30";

            container.appendChild(appMenu);

            div.addEventListener("click", async function(e) {
                if (div.classList.contains("active")) {
                    div.classList.remove("active");

                    appMenu.style.display = "none";
                }
                else {
                    div.classList.add("active");
                    // Must be shown before positioning or rect will be zeroed
                    appMenu.style.display = "block";

                    const button = div.getBoundingClientRect();
                    const menu = appMenu.getBoundingClientRect();
                    // Positoin in the middle of the button
                    const left = button.left - (menu.width / 2) + (button.width / 2);

                    appMenu.style.left = left;
                }
            });
        }

        return container;
    }
    this.makeAppButton = makeAppButton;

    function styleUIMenu(menu) {
        let select = menu.getElementsByTagName("select")[0];

        if (isEmpty(select.name)) {
            throw new Error("UIPopupMenu select must have name");
        }
        // View ID used for automated testing
        menu.classList.add(`ui-menu-${select.name}`);

        // The container is positioned absolute so that when a selection is made it overlays
        // the content instead of pushing it down.
        let container = document.createElement("div");
        container.classList.add("ui-menu-container");
        container.classList.add("ui-popup-inactive");
        menu.appendChild(container);

        select.ui = new UIMenu(select, container);

        // The first option is the label for the menu
        let menuLabel = document.createElement("div");
        menuLabel.classList.add("ui-menu-label");
        let label = select.options[0].innerHTML;
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
        choices.setAttribute("class", "ui-popup-choices");

        // Create choices
        // NOTE: This skips the first choice (menu label)
        for (let j = 1; j < select.length; j++) {
            let option = select.options[j];
            // @deprecated `group` style. Please use `divider`
            if (option.classList.contains("group") || option.classList.contains("divider")) {
                let divider = document.createElement("div");
                divider.setAttribute("class", "ui-popup-choice-divider");
                choices.appendChild(divider);
                continue;
            }
            let choice = document.createElement("div");
            choice.setAttribute("class", "ui-popup-choice");
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
        subContainer.setAttribute("style", menu.getAttribute("style"));
        menu.removeAttribute("style");
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
            var isActive = container.classList.contains("ui-popup-active");
            e.stopPropagation();
            closeAllMenus();
            // User tapped on pop-up menu when it was active. This means they wish to collapse
            // (toggle) the menu's activate state.
            if (!isActive) {
                container.classList.remove("ui-popup-inactive");
                container.classList.add("ui-popup-active");
                this.classList.add("ui-popup-arrow-active");
            }
            else {
                container.classList.remove("ui-popup-active");
                container.classList.add("ui-popup-inactive");
                this.classList.remove("ui-popup-arrow-active");
            }
        });
    }
    this.styleUIMenu = styleUIMenu;

    /**
     * Style menus displayed in the OS bar.
     *
     * FIXME: The OS calls this, which is why it is here. I'm not sure it
     * should be here as none of the other styling methods are.
     */
    function styleUIMenus(target) {
        if (isEmpty(target)) {
            console.warn("Attempting to style UI menus in null target.");
            return;
        }

        // FIX: Does not select respective select menu. Probably because it has to be reselected.
        let menus = target.getElementsByClassName("ui-menu");
        for (let i = 0; i < menus.length; i++) {
            styleUIMenu(menus[i]);
        }
    }
    this.styleUIMenus = styleUIMenus;

    const FLICKER_BUTTON_ID = "data-boss-interval-id";
    const FLICKER_BUTTON_ORIG = "data-boss-interval-original";

    /**
     * Flicker a message on a button and then revert back to the button's
     * original label after 2 seconds.
     *
     * @param {HTMLElement} button - The button to change label for
     * @param {string} msg - The message to display for 2 seconds
     */
    function flickerButton(button, msg) {
        let intervalId = button.getAttribute(FLICKER_BUTTON_ID);
        // If an interval already exists, clear it, and extend the time
        if (!isEmpty(intervalId)) {
            clearInterval(parseInt(intervalId));
            button.removeAttribute(FLICKER_BUTTON_ID);
        }

        // Store the original message as an attribute. This ensures that subsequent
        // taps on the same button will set the original message back once the
        // timer has been reset.
        if (isEmpty(button.getAttribute(FLICKER_BUTTON_ORIG))) {
            button.setAttribute(FLICKER_BUTTON_ORIG, button.innerHTML);
        }

        button.innerHTML = msg;
        intervalId = setTimeout(function() {
            button.innerHTML = button.getAttribute(FLICKER_BUTTON_ORIG);
            button.removeAttribute(FLICKER_BUTTON_ID);
            button.removeAttribute(FLICKER_BUTTON_ORIG);
        }, 2000);
        button.setAttribute(FLICKER_BUTTON_ID, intervalId);
    }
    this.flickerButton = flickerButton;

    /**
     * Toggle visibility state of dock.
     */
    function toggleDock() {
        let dock = document.getElementById("os-dock");
        let apps = dock.querySelector(".apps");
        if (apps.style.display == "none") {
            showDock();
        }
        else {
            hideDock();
        }
    }
    this.toggleDock = toggleDock;

    /**
     * Show the dock.
     */
    function showDock() {
        let dock = document.getElementById("os-dock");
        dock.style.display = "flex";
    }
    this.showDock = showDock;

    /**
     * Remove all apps from the dock and hide it.
     */
    function closeDock() {
        let dock = document.getElementById("os-dock");
        let _apps = dock.querySelectorAll(".app-icon");
        for (let i = 0; i < _apps.length; i++) {
            _apps[i].remove();
        }
        hideDock();
    }
    this.closeDock = closeDock;

    /**
     * Hide the dock.
     */
    function hideDock() {
        let dock = document.getElementById("os-dock");
        dock.style.display = "none";
    }
    this.hideDock = hideDock;

    /**
     * Add application shortcut button to Dock.
     *
     * @param {AppLink} app
     */
    function addAppToDock(app) {
        let bundleId = app.bundleId;
        let div = document.createElement("div");
        div.id = `DockButton_${bundleId}`;
        div.classList.add("app-icon");
        let img = document.createElement("img");
        img.src = `/boss/app/${bundleId}/${app.icon}`;
        div.appendChild(img);
        let name = document.createElement("div");
        name.classList.add("app-name");
        name.innerHTML = app.name;
        div.appendChild(name);

        // `mouseenter` does NOT bubble, whereas `mouseover` does
        div.addEventListener("mouseenter", function() {
            name.style.display = "block";
        });
        div.addEventListener("mouseleave", function() {
            name.style.display = "none";
        });

        div.addEventListener("click", function() {
            os.openApplication(bundleId);
        });

        let dock = document.getElementById("os-dock");
        dock.querySelector(".apps").appendChild(div);
    }
    this.addAppToDock = addAppToDock;

    /**
     * Add application shortcut buttons to Dock.
     *
     * @param {[AppLink]} apps
     */
    function addAppsToDock(apps) {
        for (let i = 0; i < apps.length; i++) {
            addAppToDock(apps[i]);
        }
    }
    this.addAppsToDock = addAppsToDock;

    function removeAppFromDock(bundleId) {
        // TODO: If no apps exist in dock, hide it
    }
    this.removeAppFromDock = removeAppFromDock;


    /**
     * Create a new UIPopupMenu.
     *
     * @param {string} name - Name given to respective `select` element
     * @param {string} title - Describes the contents inside the menu
     * @param {[UIPopupMenuChoice]|function} choices - list of choices or fn that produces options
     * @returns {HTMLElement} div container for select element
     */
    function makePopupMenu(name, title, choices, config) {
        let menu = document.createElement("div");
        menu.classList.add("ui-popup-menu");

        let width = 160; // Standard width
        if (!isEmpty(config?.width)) {
            width = config.width;
        }
        menu.style.width = `${width}px`;

        let select = document.createElement("select");
        select.name = name;

        let option = new Option(title, null);
        select.add(option, undefined);

        if (!isFunction(choices)) {
            for (let i = 0; i < choices.length; i++) {
                let choice = choices[i];
                let option = new Option(choice.name, choice.id);
                option.data = choice.data;
                select.add(option, undefined); // Append to end of list
            }
        }

        menu.appendChild(select);
        styleUIPopupMenu(menu, select, isFunction(choices) ? choices : null);
        return menu;
    }
    this.makePopupMenu = makePopupMenu;

    let indicator, indicatorPopOver;

    /**
     * Updates UI to reflect current connection status to backend server(s).
     *
     * @param {bool} connected - `true` when connected
     * @param {string} message - Message displayed to user when hovering over connection status
     */
    function updateServerStatus(connected, message) {
        if (isEmpty(indicator)) {
            indicator = document.querySelector("#server-status .indicator");

            if (isEmpty(indicator)) {
                console.warn("Attemping to update server status when OS bar is not visible.");
                return;
            }

            // TODO: The location of the arrow could be determined in `show`
            indicatorPopOver = new UIPopOver(indicator, new UIPopOverSide("right", "below"));

            indicator.addEventListener("mouseenter", function(e) {
                indicatorPopOver.show();
            });
            indicator.addEventListener("mouseleave", function(e) {
                indicatorPopOver.hide();
            });
        }

        indicator.style.backgroundColor = connected ? "green" : "red";
        indicatorPopOver.setMessage(message);
    }
    this.updateServerStatus = updateServerStatus;
}

/**
 * Represents a BOSS application.
 *
 * This is provided to a user's application instance.
 *
 * @param {str} id - ID used for Application controller
 * @param {object} config - Contains all of the applications configuration
 */
function UIApplication(id, config) {
    let bundleId = config.application.bundleId;

    let menuId = `Menu_${bundleId}`;
    let appMenuId = `AppMenu_${bundleId}`;

    // Menu displayed on left, next to OS menus
    readOnly(this, "menuId", menuId);
    // Menu displayed on right of OS bar, next to clock
    readOnly(this, "appMenuId", appMenuId);
    // AppDelegate controller for this application
    readOnly(this, "scriptId", `AppScript_${id}`);

    // Secure applications are automatically closed when the user signs out
    let secure = isEmpty(config.application.secure) ? false : config.application.secure;
    // System apps aren't visible and are always available, if loaded
    let system = isEmpty(config.application.system) ? false : config.application.system;
    // Passive apps can live in the same context as other apps. It is not switched to its own context.
    let passive = isEmpty(config.application.passive) ? false : config.application.passive;

    // System apps are always passive
    if (system) {
        passive = true;
    }

    readOnly(this, "bundleId", bundleId);
    readOnly(this, "icon", config.application.icon);
    readOnly(this, "main", config.application.main);
    readOnly(this, "name", config.application.name);
    readOnly(this, "passive", passive);
    readOnly(this, "secure", secure);
    readOnly(this, "system", system);
    readOnly(this, "version", config.application.version);

    readOnly(this, "defaults", new Defaults(bundleId));

    // Application function
    let main = null;

    // (Down)Loaded controllers
    let controllers = {};

    // Visible windows object[windowId:UIController]
    let launchedControllers = {};

    // Set to `true` as soon as `applicationDidStop` is invoked. This is necessary to
    // prevent the `applicationDidCloseAllWindows` signal.
    let stopping = false;

    // This allows calls to be made on this `UIApplication` instance as well as
    // pass-thru calls to the `main` function.
    const proxy = new Proxy(this, {
        get: function(target, prop, receiver) {
            if (prop in target) {
                return Reflect.get(...arguments);
            }
            else if (!isEmpty(main) && prop in main) {
                return main[prop];
            }
            else {
                throw new Error(`Target (${target}) does not have property (${prop})`);
            }
        },
        // Allows properties to be set
        set: function(target, prop, value) {
            if (prop in target) {
                target[prop] = value;
            }
            else if (!isEmpty(main) && prop in main) {
                main[prop] = value;
            }
            else {
                throw new Error(`Target (${target}) does not have property (${prop})`);
            }
        }
    });
    this.proxy = proxy;

    /**
     * Adds a controller config to this application's list of controllers.
     *
     * This is an internal API that allows the OS to attach controllers to apps.
     *
     * The primary purpose is to support game viewport controllers (i.e. Godot).
     * This ensures the windows belong to this app, and not a system app, where
     * the controller is defined (e.g. io.bithead.boss/controllers/Godot.html).
     *
     * @param {string} name - Name of controller to add
     * @param {UIControllerConfig} config - Configuration of controller (application.json)
     */
    function addController(name, _config) {
        let controllers = Object.keys(config.controllers);
        if (controllers.includes(name)) {
            throw Error(`The controller (${name}) is already configured on application (${bundleId})`);
        }
        config.controllers[name] = _config;
    }
    this.addController = addController;

    /**
     * Get controller configuration.
     *
     * This is typically used in conjunction with `addController` when needing
     * to attach one app's controller config to another.
     *
     * @param {string} name - Name of controller
     * @returns {UIControllerConfig?}
     */
    function getController(name) {
        return config.controllers[name];
    }
    this.getController = getController;

    /**
     * Returns reference to application's menu group.
     */
    function menus() {
        let c = document.getElementById(menuId)
        c.ui = new UIMenus(c);
        return c;
    }
    this.menus = menus;

    function makeController(name, def, html) {
        // Modals are above everything. Therefore, there is no way apps can
        // be switched in this context w/o the window being closed first.
        if (def.modal) {
            return os.ui.makeModal(bundleId, name, html);
        }

        let container = os.ui.makeWindow(bundleId, name, menuId, html);

        // Using the controller name to reference the window simplifies logic to
        // find the respective window and enforce a singleton instance.
        let windowId = def.singleton ? name : container.ui.id;
        launchedControllers[windowId] = container;

        // Do not attach this to the controller:
        // - This should not be accessible publicly
        // - Avoids polluting (over-writing) user code
        // - Controller is not shown at this point. Therefore, `UIController`
        //   will be `undefined` at this point.
        container.ui.viewDidUnload = async function() {
            // Order matters. This prevents circular loop if last visible
            // controller and app needs to be shut down. When an app is
            // shut down, all windows are closed.
            delete launchedControllers[windowId];

            if (isEmpty(launchedControllers) && config.application.quitAutomatically === true) {
                os.closeApplication(bundleId);
            }

            // If all windows are closed, send signal to app
            if (!stopping && Object.keys(launchedControllers).length < 1) {
                if (!isEmpty(main?.applicationDidCloseAllWindows)) {
                    await main.applicationDidCloseAllWindows();
                }
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
     * When a window is loaded from an endpoint, it is expected that the window
     * is rendered server-side. The controller must still exist in the list of
     * application controllers.
     *
     * The `endpoint` overrides any `path` set in app controller config.
     *
     * If the controller config `remote` is `true`, and `endpoint` is not provided,
     * this will throw an Error.
     *
     * @param {string} name - Name of controller
     * @param {string} endpoint - Full path, or resource path, of server-side rendered window
     * @returns HTMLElement window container
     * @throws
     */
    async function loadController(name, endpoint) {
        let controllers = Object.keys(config.controllers);
        if (!controllers.includes(name)) {
            throw new Error(`Controller (${name}) does not exist in application's (${bundleId}) controller list.`);
        }
        let def = config.controllers[name];

        // Consumer must provide endpoint if this controller requires path to
        // resource that can only be defined at callsite (such as REST paths
        // that require IDs).
        if (def.remote === true && isEmpty(endpoint)) {
            throw new Error(`The endpoint parameter is required when loading controller (${name}). This is caused by the controller 'remote' flag being set to 'true'.`);
        }

        // By virtue of singleton windows using the controller name as the key
        // to the window instance, and not the auto-generated ID for the window
        // (e.g. `Window_xxxxxx`), a singleton instance can be enforced.
        let launched = launchedControllers[name];
        if (!isEmpty(launched)) {
            os.ui.focusWindow(launched);
            return launched;
        }

        // FIXME: When loading controller from cache, the renderer may need to
        // be factord in.

        // Return cached controller
        //
        // NOTE: Server-side rendered controllers are never cached as they may
        // need to be re-rendered.
        let html = controllers[name];
        if (isEmpty(def.path) && !isEmpty(html)) {
            return makeController(name, def, html);
        }

        if (!isEmpty(def.renderer) && def.renderer !== "html") {
            throw new Error(`Unsupported renderer (${def.renderer}) for controller (${def.name}).`);
        }
        else if (isEmpty(def.renderer)) {
            def.renderer = "html";
        }

        let path;
        if (!isEmpty(endpoint)) {
            path = endpoint
        }
        else if (isEmpty(def.path)) {
            path = `/boss/app/${bundleId}/controller/${name}.${def.renderer}`
        }
        else {
            // Server-side rendered window
            path = def.path
        }

        // Download and cache controller
        try {
            // FIXME: If renderer requires Object, this may need to change
            // the decoder to JSON. For now, all controllers are HTML.
            html = await os.network.get(path, "text");
        }
        catch (error) {
            console.error(error);
            throw new Error(`Failed to load application bundle (${bundleId}) controller (${name}).`);
        }

        controllers[name] = html;

        return makeController(name, def, html);
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
     *
     * @param {UIApplicationDelegate?} main
     */
    function applicationDidStart(_main) {
        main = _main;
        if (!isEmpty(main?.applicationDidStart)) {
            main.applicationDidStart();
        }
    }
    this.applicationDidStart = applicationDidStart;

    /**
     * Called after a user has signed in.
     *
     * This allows controllers to change their signed in state, based on the
     * user who signed in. This is not called if the Guest user is signed in.
     *
     * @param {User} user - The user who has signed in
     */
    function applicationWillSignIn(user) {
        for (windowId in launchedControllers) {
            launchedControllers[windowId].ui.userDidSignIn(user);
        }

        // Handle modals. Refer to applicationWillSignOut for context on this operation.
        let div = document.getElementById(`app-container-${bundleId}`);
        if (isEmpty(div)) {
            console.error("Failed to find the application container in document. Modals will not receive userDidSignIn signal.");
            return;
        }
        const modals = div.querySelectorAll(".ui-modal-overlay");
        modals.forEach(modal => {
            modal.ui.userDidSignIn();
        });
    }
    this.applicationWillSignIn = applicationWillSignIn;

    /**
     * Called before a user is signed out of the system.
     *
     * This gives controllers the chance to cleanup any state before
     * needing to close themselves.
     *
     * This is typically only used by system controllers. Some
     * controllers, like the `InactivityController`, need to
     * clear their timeouts and close themselves so that they do
     * not show when the user signs back in.
     */
    function applicationWillSignOut() {
        for (windowId in launchedControllers) {
            launchedControllers[windowId].ui.userDidSignOut();
        }

        // Modals are not in launchedControllers (maybe they should be). Because
        // of this, they need to be selected from within this application's
        // container, iterated over (ui-modal-overlay), and sent the signal.
        // This is adding a lot of complexity. But it's necessary to remove timers.
        // If I could simply remove the view, that wouldn't remove timers and keep
        // a reference of the windows around, even though they're not in the DOM.
        let div = document.getElementById(`app-container-${bundleId}`);
        if (isEmpty(div)) {
            console.error("Failed to find the application container in document. Modals will not receive userDidSignOut signal.");
            return;
        }
        const modals = div.querySelectorAll(".ui-modal-overlay");
        modals.forEach(modal => {
            modal.ui.userDidSignOut();
        });
    }
    this.applicationWillSignOut = applicationWillSignOut;

    /**
     * Called before the application is removed from the OS's cache.
     *
     * Perform any necessary cleanup steps. In most cases, this is not
     * necessary as any memory used by your application will be cleaned
     * automatically.
     */
    function applicationDidStop() {
        stopping = true;

        // Close all windows
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
        // Only focus if application is not passive. The focus/blur
        // are called when app context changes. The context doesn't change
        // for passive apps.
        if (config.application.passive) {
            return;
        }
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
        // Like above, only blur if application is not passive.
        if (config.application.passive) {
            return;
        }
        if (!isEmpty(main?.applicationDidBlur)) {
            main.applicationDidBlur();
        }
    }
    this.applicationDidBlur = applicationDidBlur;

    /**
     * Sent to `main` controller if all controllers closed.
     *
     * This is not called when the application stops and all controllers are
     * closed.
     *
     * This behavior is managed internally to UIApplication. Therefore, it is
     * not exposed. This provides the definition of the delegate callback a
     * UIApplication controller may implement.
     */
    async function applicationDidCloseAllWindows() { }
}

/**
 * The primary container for displayable content. A window has chrome, viewable
 * content, and a controller.
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
 * A window may contain embedded `UIController`s (`.ui-controller`)
 *
 * @param {UI} ui - Instance of UI
 * @param {HTMLElement} container - `.ui-window` container
 * @param {bool} isModal - `true`, if modal
 * @param {string} menuId - The menu ID to attach window menus to
 */
function UIWindow(bundleId, id, container, isModal, menuId) {

    readOnly(this, "id", id);
    readOnly(this, "bundleId", bundleId);
    readOnly(this, "isModal", isModal);

    let controller = null;

    // A controller instance may attempt to be shown more than once. This
    // gates initialization logic from being called twice.
    let loaded = false;

    // Reference to the element that contains this window's `UIMenu`s that
    // are shown in the OS bar. This is necessary when a window wishes to
    // make changes to the menu after the view is loaded.
    let menus = null;

    let isFullScreen = false;
    let isFocused = false;

    // When a window zooms in (becomes fullscreen), store the original positions
    // and restore them if zooming out.
    let topPosition = null;
    let leftPosition = null;

    /**
     * Prepare the window for display, load controller source, etc.
     *
     * @param {function?} fn - Callback function that will be called before view is loaded
     */
    function init(fn) {
        styleAllUIPopupMenus(container);
        styleAllUIListBoxes(container);
        styleAllUITabs(container);
        styleAllUIProgressBars(container);
        os.ui.styleUIMenus(container);

        // Add window controller, if it exists.
        if (typeof window[id] === 'function') {
            controller = new window[id](container);
            os.ui.addController(id, controller);

            if (!isEmpty(fn)) {
                fn(controller);
            }
        }

        // TODO: If embedded controllers are registered before parent, it should be possible
        // to inject attributes.

        // Register embedded controllers
        os.ui.registerEmbeddedControllers(container);

        if (!isModal) {
            let win = container.querySelector(".ui-window");
            if (isEmpty(win)) {
                throw new Error("Attempting to initialize a UIWindow, but none was found. Is this a modal? If so, please configure this as a modal in application.json");
            }
            isFullScreen = win.classList.contains("fullscreen");
            if (isFullScreen) {
                // Will get added to `ui-container` later
                win.classList.remove("fullscreen");
            }

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
                if (isFullScreen) {
                    return;
                }
                os.ui.focusWindow(container);
                os.ui.dragWindow(container);
            };
            container.addEventListener("mousedown", function(e) {
                // Future me: `isFocused` is already `true` at this point if the
                // `.top` mousedown event is triggered. Therefore, this signal is
                // ignored as `isFocused` is set before the event signal is sent
                // to this listener. Test this by uncommenting below log. The reason
                // the log statement is left here is to debug possible issues that
                // may occur with different JS engines. This logic may need to
                // change.
                if (!isFullScreen && !isFocused) {
                    // console.log("focusing"); Uncomment this to ensure correct behavior
                    os.ui.focusWindow(container);
                }
            });
        }

        // There should only be one ui-menus
        let uiMenus = container.querySelector(".ui-menus");
        if (!isEmpty(uiMenus)) {
            // Remove menu declaration from window
            uiMenus.remove();

            menus = uiMenus;
            os.ui.addOSBarMenu(menus, menuId);
        }

        // Prepare window to be displayed -- assigns z-index.
        os.ui.focusWindow(container);

        // TODO: Untested fullscreen on init
        // NOTE: `zoom` doesn't use `isFullScreen` to determine if window
        // is zoomed. It checks if the class exists. The class will not
        // exist by default, therefore, the window will be zoomed.
        if (!isModal && isFullScreen) {
            zoom();
        }

        if (!isEmpty(controller?.viewDidLoad)) {
            controller.viewDidLoad();
        }
    }
    this.init = init;

    function setTitle(title) {
        let span = container.querySelector(".top .title span");
        if (isEmpty(span)) {
            console.warn("The UIWindow does not have a title");
            return;
        }
        span.innerHTML = title;
    }
    this.setTitle = setTitle;

    /**
     * Show the window.
     *
     * @param {function} fn - The function to call directly before the view is loaded
     */
    function show(fn) {
        if (loaded) {
            fn(controller);
            return;
        }

        // NOTE: `container` must be added to DOM before controller can be
        // instantiated.
        let context = document.getElementById(os.ui.appContainerId(bundleId));
        context.appendChild(container);

        // Allow time for parsing. This is required to work. But I'm not sure why.
        try {
            init(fn);
        }
        catch (error) {
            // Show in window, and console, so that the error is obvious and can be
            // be better inspected.
            console.error(error);
            os.ui.showAlert(`Failed to initialize window. Controller raised error (${error}).`);
        }

        loaded = true;
    }
    this.show = show;

    /**
     * Zoom (fullscreen) in window.
     */
    function zoom() {
        if (container.classList.contains("fullscreen")) {
            container.classList.remove("fullscreen");

            // Restore previous window position
            container.style.top = topPosition;
            container.style.left = leftPosition;

            isFullScreen = false;
        }
        else {
            os.ui.focusWindow(container);

            topPosition = container.style.top;
            leftPosition = container.style.left;

            // NOTE: top/left is defined in stylesheet. This is done so top/left
            // position config, and for fullscreen config, are managed in one place.
            // The positions may eventually move here.
            container.style.top = null;
            container.style.left = null;

            container.classList.add("fullscreen");

            isFullScreen = true;
        }
    }

    /**
     * Close the window.
     */
    async function close() {
        if (!loaded) {
            console.warn(`Attempting to close window (${id}) which is not loaded.`);
            return;
        }

        if (!isEmpty(controller?.viewWillUnload)) {
            controller.viewWillUnload();
        }

        os.ui.removeController(id);

        menus?.remove();

        container.remove();

        os.ui.removeWindow(container);
        os.ui.focusTopWindow();

        if (!isEmpty(container?.ui.viewDidUnload)) {
            await container.ui.viewDidUnload();
        }

        loaded = false;
    }
    this.close = close;

    function didFocusWindow() {
        if (isFocused) {
            return;
        }

        isFocused = true;

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
        if (!isFocused) {
            return;
        }

        isFocused = false;

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

    function didHitKey(key) {
        if (!isFocused) {
            return;
        }

        if (!isEmpty(controller?.didHitKey)) {
            controller.didHitKey(key);
        }
    }
    this.didHitKey = didHitKey;

    function didHitEnter() {
        if (!isFocused) {
            return;
        }

        if (!isEmpty(controller?.didHitEnter)) {
            controller.didHitEnter();
        }
    }
    this.didHitEnter = didHitEnter;

    function userDidSignIn(user) {
        const fn = controller?.userDidSignIn;
        if (!isEmpty(fn)) {
            fn(user);
        }
    }
    this.userDidSignIn = userDidSignIn;

    function userDidSignOut() {
        const fn = controller?.userDidSignOut;
        if (!isEmpty(fn)) {
            fn();
        }
    }
    this.userDidSignOut = userDidSignOut;

    /** Helpers **/

    /**
     * Returns `button` `HTMLElement` with given name.
     *
     * @param {string} name - Name of button element
     * @returns HTMLElement?
     */
    function button(name) {
        return container.querySelector(`button[name='${name}']`);
    }
    this.button = button;

    /**
     * Returns `div` `HTMLElement` with given class name.
     *
     * @param {string} name - Class name of div element
     */
    function div(name) {
        return container.querySelector(`div.${name}`);
    }
    this.div = div;

    /**
     * Returns `HTMLElement` with given ID.
     *
     * @param {string} id - ID of element.
     */
    function element(id) {
        return document.getElementById(id);
    }
    this.element = element;

    /**
     * Returns `p` `HTMLElement` with given class name.
     *
     * @param {string} name - Class name of p element
     */
    function p(name) {
        return container.querySelector(`p.${name}`);
    }
    this.p = p;

    /**
     * Get an `iframe` `HTMLElement` w/in controller's view.
     *
     * @param {string} name - Name of `iframe` element
     * @returns HTMLElement?
     */
    function iframe(name) {
        return container.querySelector(`iframe[name='${name}']`);
    }
    this.iframe = iframe;

    /**
     * Returns the respective `input` `HTMLElement` given name.
     *
     * @param {string} name - Name of input element
     * @returns HTMLElement?
     */
    function input(name) {
        return container.querySelector(`input[name='${name}']`);
    }
    this.input = input;

    /**
     * Returns `select` `HTMLElement` with given name.
     *
     * @param {string} name - Name of select element
     */
    function select(name) {
        return container.querySelector(`select[name='${name}']`);
    }
    this.select = select;

    /**
     * Returns `pre` `HTMLElement` with given `name`.
     *
     * @param {string} name - Name of pre element
     */
    function pre(name) {
        return container.querySelector(`pre[name='${name}']`);
    }
    this.pre = pre;

    /**
     * Returns `radio` `HTMLElement` with given name and value.
     *
     * @param {string} name - Name of radio element
     * @param {string} value - Value of radio element
     */
    function radio(name, value) {
        return container.querySelector(`input[name='${name}'][value='${value}']`);
    }
    this.radio = radio;

    /**
     * Returns `span` `HTMLElement` with given name.
     *
     * @param {string} name - Name of span element
     */
    function span(name) {
        return container.querySelector(`span[name='${name}']`);
    }
    this.span = span;

    /**
     * Returns `table` `HTMLElement` with given name.
     *
     * @param {string} name - Name of table element
     */
    function table(name) {
        return container.querySelector(`table[name='${name}']`);
    }
    this.table = table;

    /**
     * Returns `td` `HTMLElement` with given name.
     *
     * @param {string} name - Name of td element
     */
    function td(name) {
        return container.querySelector(`td[name='${name}']`);
    }
    this.td = td;

    /**
     * Returns `textarea` `HTMLElement` with given name.
     *
     * @param {string} name - Name of textarea element
     */
    function textarea(name) {
        return container.querySelector(`textarea[name='${name}']`);
    }
    this.textarea = textarea;

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
 * Provides protocol definition for `UIWindow`, and `UIController`, controllers.
 *
 * A `UIController` allows a `div.ui-window`, and `div.ui-controller`, to receive
 * life-cycle events from the OS.
 *
 * All functions are optional. Therefore, implement only the functions needed.
 *
 * The anatomy of an embedded controller:
 * ```
 * <div class="container">
 *   <div class="ui-controller" id="<unique_name_here>">
 *     <!-- script -->
 *     <!-- viewable content -->
 *   </div>
 * </div>
 * ```
 */
function UIController() {
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

    /**
     * Called if window is focused and user presses a key.
     *
     * Note: This provides every key _but_ the `Enter` key. Use didHitEnter
     * to capture Enter key.
     */
    function didHitKey() { }

    /**
     * Called if window is focused and user presses the `Enter` key.
     */
    function didHitEnter() { }

    /**
     * Called after a user has signed in.
     */
    function userDidSignIn() { }

    /**
     * Called before the system user is signed out.
     */
    function userDidSignOut() { }
}

function _UIController(container) {
    // This is duplicated in UIWindow

    /** Helpers **/

    /**
     * Returns `button` `HTMLElement` with given name.
     *
     * @param {string} name - Name of button element
     * @returns HTMLElement?
     */
    function button(name) {
        return container.querySelector(`button[name='${name}']`);
    }
    this.button = button;

    /**
     * Returns `div` `HTMLElement` with given class name.
     *
     * @param {string} name - Class name of div element
     */
    function div(name) {
        return container.querySelector(`div.${name}`);
    }
    this.div = div;

    /**
     * Returns `HTMLElement` with given ID.
     *
     * @param {string} id - ID of element.
     */
    function element(id) {
        return document.getElementById(id);
    }
    this.element = element;

    /**
     * Returns `p` `HTMLElement` with given class name.
     *
     * @param {string} name - Class name of p element
     */
    function p(name) {
        return container.querySelector(`p.${name}`);
    }
    this.p = p;

    /**
     * Get an `iframe` `HTMLElement` w/in controller's view.
     *
     * @param {string} name - Name of `iframe` element
     * @returns HTMLElement?
     */
    function iframe(name) {
        return container.querySelector(`iframe[name='${name}']`);
    }
    this.iframe = iframe;

    /**
     * Returns the respective `input` `HTMLElement` given name.
     *
     * @param {string} name - Name of input element
     * @returns HTMLElement?
     */
    function input(name) {
        return container.querySelector(`input[name='${name}']`);
    }
    this.input = input;

    /**
     * Returns `select` `HTMLElement` with given name.
     *
     * @param {string} name - Name of select element
     */
    function select(name) {
        return container.querySelector(`select[name='${name}']`);
    }
    this.select = select;

    /**
     * Returns `pre` `HTMLElement` with given `name`.
     *
     * @param {string} name - Name of pre element
     */
    function pre(name) {
        return container.querySelector(`pre[name='${name}']`);
    }
    this.pre = pre;

    /**
     * Returns `radio` `HTMLElement` with given name and value.
     *
     * @param {string} name - Name of radio element
     * @param {string} value - Value of radio element
     */
    function radio(name, value) {
        return container.querySelector(`input[name='${name}'][value='${value}']`);
    }
    this.radio = radio;

    /**
     * Returns `span` `HTMLElement` with given name.
     *
     * @param {string} name - Name of span element
     */
    function span(name) {
        return container.querySelector(`span[name='${name}']`);
    }
    this.span = span;

    /**
     * Returns `table` `HTMLElement` with given name.
     *
     * @param {string} name - Name of table element
     */
    function table(name) {
        return container.querySelector(`table[name='${name}']`);
    }
    this.table = table;

    /**
     * Returns `td` `HTMLElement` with given name.
     *
     * @param {string} name - Name of td element
     */
    function td(name) {
        return container.querySelector(`td[name='${name}']`);
    }
    this.td = td;

    /**
     * Returns `textarea` `HTMLElement` with given name.
     *
     * @param {string} name - Name of textarea element
     */
    function textarea(name) {
        return container.querySelector(`textarea[name='${name}']`);
    }
    this.textarea = textarea;
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
        if (container.classList.contains("ui-popup-inactive")) {
            continue;
        }
        container.classList.remove("ui-popup-active");
        container.classList.add("ui-popup-inactive");
        // Reset arrow
        let choicesLabel = container.querySelector("." + className + "-label");
        choicesLabel.classList.remove("ui-popup-arrow-active");
    }
}

/**
 * Close all popup menus.
 */
function closeAllMenus() {
    closeMenuType("ui-menu");
    closeMenuType("ui-popup");
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
 * Provides extensions to a `.ui-popup-menu select`.
 *
 * The first option in the `select` provides information about what
 * is in the drop-down. This option is unfortunately necessary if
 * no options exist in the `select`. Otherwise, the height of the
 * drop-down will be 0, causing the `.ui-popup-menu` to collapse.
 */
function UIPopupMenu(select) {

    // Represents the parent view container (div.ui-popup-menu)
    let node = select.parentNode;

    function updateSelectedOptionLabel() {
        let label = select.parentNode.querySelector(".ui-popup-label");
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
     * @param {integer|string} index - The option index or label
     */
    function disableOption(index) {
    }
    this.disableOption = disableOption;

    /**
     * Enable an option.
     *
     * @param {integer|string} index - The option index or label
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
        let container = select.parentNode.querySelector(".ui-popup-choices");
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
     * @param {[UIPopupMenuChoice]} options
     */
    function addNewOptions(options) {
        _removeAllOptions();

        for (let i = 0; i < options.length; i++) {
            var option = document.createElement('option');
            var opt = options[i];
            option.value = opt["id"];
            option.text = opt["name"];
            option.data = opt["data"];
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
        let container = node.querySelector(".ui-popup-choices");
        if (isEmpty(container)) {
            console.error("Could not find .ui-popup-choices in select " + select);
            return;
        }

        // Create choices - ignore first choice
        for (let j = 1; j < select.length; j++) {
            let option = select.options[j];
            if (option.classList.contains("group")) {
                let group = document.createElement("div");
                group.setAttribute("class", "ui-popup-choice-group");
                container.appendChild(group);
                continue;
            }
            let choice = document.createElement("div");
            choice.setAttribute("class", "ui-popup-choice");
            if (option.disabled) {
                choice.classList.add("disabled");
            }

            // TODO: For now, options do not support images
            let label = option.innerHTML;
            if (label.startsWith("img:")) {
                let parts = label.split(",");
                label = parts[1];
            }

            choice.innerHTML = label;

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
 * Style an individual `ui-popup-menu`.
 *
 * @param {HTMLElement} menu - Container
 * @param {HTMLElement} select - select element used as backing store
 * @param {function?} option_fn - Function to generate options when label is tapped
 */
function styleUIPopupMenu(menu, select, options_fn) {
    select.ui = new UIPopupMenu(select);

    // The container is positioned absolute so that when a selection is made it overlays
    // the content instead of pushing it down.
    let container = document.createElement("div");
    container.setAttribute("class", "ui-popup-container ui-popup-inactive");
    // Inherit the parent's width (style)
    container.setAttribute("style", menu.getAttribute("style"));
    menu.removeAttribute("style");
    menu.appendChild(container);

    // Displays the selected option when the pop-up is inactive
    let choicesLabel = document.createElement("div");
    choicesLabel.setAttribute("class", "ui-popup-label");
    // Display the selected default option
    choicesLabel.innerHTML = select.options[select.selectedIndex].innerHTML;
    container.appendChild(choicesLabel);

    // Container for all choices
    let choices = document.createElement("div");
    choices.setAttribute("class", "ui-popup-choices");

    // Disable drop-down if select element is disabled
    if (select.disabled) {
        menu.classList.add("disabled");
    }

    let subContainer = document.createElement("div");
    subContainer.setAttribute("class", "sub-container");
    subContainer.appendChild(choices);
    container.appendChild(subContainer);

    select.ui.styleOptions(select);

    /**
     * Toggle the ui-popup-menu's state.
     *
     * If the state is inactive, the menu will be displayed. If active,
     * the menu will become hidden.
     *
     * NOTE: Only the first div in the container should have the click
     * event associated to the toggle state.
     */
    choicesLabel.addEventListener("click", function(e) {
        let popupMenu = this.parentNode.parentNode;
        if (!popupMenu.classList.contains("ui-popup-menu")) {
            console.error("Expected parent to be a ui-popup-menu")
            return;
        }
        // Do nothing if the control is disabled
        if (popupMenu.classList.contains("disabled")) {
            return;
        }
        let container = popupMenu.querySelector(".ui-popup-container");
        let isActive = container.classList.contains("ui-popup-active");
        e.stopPropagation();
        closeAllMenus();

        // If list of options is dynamic, re-generate the list of options
        // to display.
        if (!isEmpty(options_fn)) {
            let options = options_fn();
            select.ui.addNewOptions(options);
        }

        // Show menu
        if (!isActive) {
            container.classList.remove("ui-popup-inactive");
            container.classList.add("ui-popup-active");
            this.classList.add("ui-popup-arrow-active");
        }
        // User tapped on pop-up menu when it was active. This means they wish to collapse
        // (toggle) the menu's activate state.
        else {
            container.classList.remove("ui-popup-active");
            container.classList.add("ui-popup-inactive");
            this.classList.remove("ui-popup-arrow-active");
        }
    });
}

/**
 * Style all `ui-popup-menu` elements contained within `element`.
 *
 * @param {HTMLElement} element - Container of `ui-popup-menu`s
 */
function styleAllUIPopupMenus(element) {
    // FIX: Does not select respective select menu. Probably because it has to be reselected.
    let menus = element.getElementsByClassName("ui-popup-menu");
    for (let i = 0; i < menus.length; i++) {
        let menu = menus[i];
        let select = menu.getElementsByTagName("select")[0];
        styleUIPopupMenu(menu, select);
    }
}

function UIMenus(container) {
    /**
     * Returns instance of `select` inside of UIMenus container.
     *
     * @param {string} name - Name of select element
     */
    function select(name) {
        return container.querySelector(`select[name='${name}']`);
    }
    this.select = select;
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
     * Enable menu option.
     *
     * @param {string} value - The value of the option to disable
     */
    function enableOption(value) {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                option.disabled = false;
                if (option.ui.classList.contains("disabled")) {
                    option.ui.classList.remove("disabled");
                }
                break;
            }
        }
    }
    this.enableOption = enableOption;

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

function UIListBox(select, container, isButtons) {

    let delegate = protocol(
        "UIListBoxDelegate", this, "delegate",
        [
            // Option was selected
            "didSelectListBoxOption",
            // Option was de-selected
            "didDeselectListBoxOption",
            // Called when all options are removed from the list.
            //
            // This occurs when a user removes the last option in the list
            // OR the list has been updated w/ no options.
            //
            // This will be called every time `addNewOptions` is called with
            // empty options. However, subsequent calls to `removeOption`, after
            // all options are removed, will not emit this signal.
            "didRemoveAllOptions"
        ],
        // Allows delegate to update its UI immediately if an option
        // requires HTMLElements to be enabled/disabled.
        function () {
            if (!select.multiple && !isButtons) {
                selectOption(0);
            }
        }
    );

    // Default action to take when an item in the list box is double tapped
    let defaultAction = null;

    /**
     * Set the default action to take when an option is double-tapped.
     *
     * Note: This only works on single select list boxes.
     */
    function setDefaultAction(fn) {
        if (select.multiple) {
            return;
        }
        defaultAction = fn;
    }
    this.setDefaultAction = setDefaultAction;

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
        // Remove from selected index, but only if selection takes place
        let selectedIndex;
        for (let i = 0; i < select.options.length; i++) {
            let opt = select.options[i];
            if (opt.index == index && !opt.disabled) {
                selectedIndex = index;
                break;
            }
        }

        // No option selected
        if (isEmpty(selectedIndex)) {
            return;
        }

        let opt = select.options[selectedIndex];

        // Already selected
        if (opt.ui.classList.contains("selected")) {
            return;
        }
        else {
            // De-select previous option
            let prevOpt = select.options[select.selectedIndex];
            prevOpt.ui.classList.remove("selected");
        }

        select.selectedIndex = selectedIndex;
        opt.ui.classList.add("selected");
        delegate.didSelectListBoxOption(opt);
    }
    this.selectOption = selectOption;

    /**
     * Remove all options from list.
     */
    function removeAllOptions() {
        for (;select.options.length > 0;) {
            let option = select.options[0];
            option.remove();
            option.ui.remove();
        }
    }
    this.removeAllOptions = removeAllOptions;

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
     * @param {[UIListBoxChoice]} options - Options to add.
     * @param {[UIListBoxChoiceConfig]} config
     */
    function addNewOptions(options, config) {
        removeAllOptions();

        for (let i = 0; i < options.length; i++) {
            let option = document.createElement("option");
            let opt = options[i];
            option.value = opt.id;
            option.text = opt.name;
            if (opt?.child === true) {
                option.classList.add("child");
            }
            if (config?.setModelToData === true) {
                option.data = opt;
            }
            else {
                option.data = opt.data;
            }
            select.appendChild(option);
        }

        if (!select.multiple) {
            select.selectedIndex = 0;

            // When new options are added, the first option is automatically
            // selected. The consumer should know when this happens.
            if (options.length > 0) {
                delegate.didSelectListBoxOption(selectedOption());
            }
        }

        // If all options are removed, inform.
        if (options.length == 0) {
            delegate.didRemoveAllOptions();
        }

        styleOptions();
    }
    this.addNewOptions = addNewOptions;

    /**
     * Add option to end of list.
     *
     * @param {UIListBoxChoice} model - Option to add to list
     */
    function addOption(model) {
        let option = new Option(model.name, model.id);
        option = model.data;
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
        let hasOptions = select.options.length > 0;

        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                select.remove(i);
                container.removeChild(option.ui)
                break;
            }
        }

        // If all options have been removed, inform delegate
        if (hasOptions && select.options.length == 0) {
            delegate.didRemoveAllOptions();
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
     * Returns the selected option's index.
     *
     * @returns {int} The selected option's index
     */
    function selectedIndex() {
        if (select.disabled) {
            return null;
        }
        let idx = select.selectedIndex;
        return idx;
    }
    this.selectedIndex = selectedIndex;

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

        if (isButtons) {
            elem.classList.add("button");
        }

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

        // Transfer onclick event
        if (!isEmpty(option.onclick)) {
            elem.addEventListener("click", function() {
                if (!option.disabled) {
                    option.onclick();
                }
            });
        }

        elem.classList.add("option");
        if (option.disabled) {
            elem.classList.add("disabled");
        }
        // When `select` is not `multiple`, selected index is always 0. This causes
        // the first option to always be selected. There's no way around this.
        if (!isButtons && option.selected) {
            elem.classList.add("selected");
        }
        for (let j = 0; j < option.classList.length; j++) {
            elem.classList.add(option.classList[j]);
        }
        option.ui = elem;

        container.appendChild(elem);
        elem.addEventListener("mouseup", function(obj) {
            if (select.multiple) {
                if (option.disabled) {
                    return;
                }
                option.selected = !option.selected;
                elem.classList.remove("selected");
                if (!isButtons && option.selected) {
                    elem.classList.add("selected");
                }
                if (option.selected) {
                    delegate.didSelectListBoxOption(option);
                }
                else if (!isButtons) {
                    delegate.didDeselectListBoxOption(option);
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

    // Configuration

    // Buttons must make the select `multiple` in order to not have any button
    // selected initially.
    if (isButtons) {
        select.multiple = true;
    }

    styleOptions();

    container.addEventListener("dblclick", function(event) {
        if (!isEmpty(defaultAction)) {
            defaultAction();
        }
    });
}

function styleUIListBox(list) {
    let container = document.createElement("div");
    container.classList.add("container");
    list.appendChild(container);

    let select = list.querySelector("select");
    if (isEmpty(select.name)) {
        throw new Error("A UIListBox select element must have a name");
    }
    // View ID used for automated testing
    list.classList.add(`ui-list-box-${select.name}`);
    // Defines if the options should be treated as buttons instead of options
    let isButtons = list.classList.contains("buttons");
    let box = new UIListBox(select, container, isButtons);
    select.ui = box;
}

function styleAllUIListBoxes(elem) {
    let lists = elem.getElementsByClassName("ui-list-box");
    for (let i = 0; i < lists.length; i++) {
        let list = lists[i];
        styleUIListBox(list);
    }
}

/**
 * UITabs
 *
 * A horizontally aligned list of tabs which may be optionally closed.
 */

function UITabs(select, container) {

    let delegate = protocol(
        "UITabsDelegate", this, "delegate",
        ["didCloseTab", "didSelectTab"],
        // Allows delegate to update its UI immediately if an option
        // requires HTMLElements to be enabled/disabled.
        function () {
            selectTabIndex(0);
        }
    );

    /**
     * Select tab by value.
     *
     * @param {string} value - Tab value to select
     */
    function selectTab(value) {
        for (let idx = 0; idx < select.options.length; idx++) {
            if (select.options[idx].value == value) {
                selectTabIndex(idx);
                return;
            }
        }
    }
    this.selectTab = selectTab;

    /**
     * Select tab by its index.
     *
     * @param {int} index - Index of tab to select
     */
    function selectTabIndex(index) {
        // NOTE: When an option is removed, the `selectedIndex` may automatically
        // update. When this happens, and selectTabIndex is called directly after,
        // it's not possible if this was the previously selected state or not.
        // That is why this _always_ selects the index and reconciles every time.

        select.selectedIndex = index;

        // Reconcile class list and then select tab
        for (let i = 0; i < select.options.length; i++) {
            let opt = select.options[i];
            opt.ui.classList.remove("selected");
            if (opt.selected) {
                opt.ui.classList.add("selected");
                delegate.didSelectTab(opt);
            }
        }
    }
    this.selectTabIndex = selectTabIndex;

    function removeAllTabs() {
        // Remove all options from the select and facade
        for (;select.options.length > 0;) {
            let option = select.options[0];
            option.remove();
            option.ui.remove();
        }
        // Remove elements from container
    }

    /**
     * Add option choice to tab list.
     *
     * @param {UITabChoice} model
     */
    function addOption(model) {
        let option = document.createElement("option");
        option.value = model.id;
        option.text = model.name;
        option.data = model.data;
        if (model.close === true) {
            option.classList.add("close-button");
        }
        select.add(option, undefined); // Append to end of list
        return option;
    }

    /**
     * Add new tabs.
     *
     * This will remove all existing tabs.
     *
     * @param {[UITabChoice]} tabs - Tabs to add.
     */
    function addNewTabs(tabs) {
        removeAllTabs();

        for (let i = 0; i < tabs.length; i++) {
            addOption(tabs[i]);
        }

        select.selectedIndex = 0;

        styleTabs();
    }
    this.addNewTabs = addNewTabs;

    /**
     * Add tab to end of list.
     *
     * @param {object[id:name:]} model - Tab to add to list
     */
    function addTab(model) {
        let option = addOption(model);
        styleTab(option);
        scrollToLastTab();
    }
    this.addTab = addTab;

    /**
     * Check if tab is in list.
     *
     * @param {string} value - Tab value
     * @returns `true` if tab, with `value`, is in list
     */
    function contains(value) {
        for (let idx = 0; idx < select.options.length; idx++) {
            if (select.options[idx].value == value) {
                return true;
            }
        }
        return false;
    }
    this.contains = contains;

    /**
     * Check if tabs are present.
     *
     * @returns `true` if at least one tab exists
     */
    function hasTabs() {
        return select.options.length > 0;
    }
    this.hasTabs = hasTabs;

    /**
     * Remove tab by value.
     *
     * @param {string} value - Value of tab
     */
    function removeTab(value) {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                removeTabIndex(i);
                break;
            }
        }
    }
    this.removeTab = removeTab;

    /**
     * Remove tab from list by its index.
     */
    function removeTabIndex(index) {
        let option = select.options[index];
        if (isEmpty(option)) {
            console.warn(`Attempting to remove tab at index (${index}) which does not exist in select (${select.name})`);
            return;
        }
        select.remove(index);
        container.removeChild(option.ui);
    }
    this.removeTabIndex = removeTabIndex;

    /**
     * Returns respective tab option given index.
     *
     * @param {int} value - Value of tab
     * @returns {HTMLElement?} the tab w/ value, if any
     */
    function getTab(value) {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            if (option.value == value) {
                return option;
            }
        }
        return null;
    }
    this.getTab = getTab;

    /**
     * Return the selected tab.
     *
     * @returns {HTMLOption?} The selected tab. `null` if `select` is disabled.
     */
    function selectedTab() {
        if (select.disabled) {
            return null;
        }
        let idx = select.selectedIndex;
        return select.options[idx]
    }
    this.selectedTab = selectedTab;

    /**
     * Returns the value of the selected tab, if any.
     *
     * @returns {any?}
     */
    function selectedValue() {
        let opt = selectedTab();
        return opt?.value;
    }
    this.selectedValue = selectedValue;

    /**
     * Selects the first tab, if needed.
     */
    function selectTabIfNeeded() {
        let hasSelectedTab = false;
        for (let i = 0; i < select.options.length; i++) {
            if (select.options[i].ui.classList.contains("selected")) {
                hasSelectedTab = true;
                break;
            }
        }
        if (!hasSelectedTab) {
            selectTabIndex(0);
        }
    }

    function styleTab(option) {
        let elem = document.createElement("div");
        elem.classList.add("ui-tab");
        let label = option.innerHTML;
        let labels = label.split(",");

        if (option.classList.contains("close-button")) {
            option.classList.remove("close-button");
            let button = document.createElement("div");
            button.classList.add("close-button");
            button.addEventListener("click", function (e) {
                e.stopPropagation();
                removeTabIndex(option.index);
                delegate.didCloseTab(option);
                selectTabIfNeeded();
            });
            // Prevents the tab from being selected
            button.addEventListener("mouseup", function (e) {
                e.stopPropagation();
            });
            elem.append(button);
        }

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
            let span = document.createElement("span");
            span.innerHTML = label;
            elem.append(span);
        }

        // Transfer onclick event
        if (!isEmpty(option.onclick)) {
            elem.addEventListener("click", function() {
                if (!option.disabled) {
                    option.onclick();
                }
            });
        }

        // NOTE: The default state of options when 'buttons' mode is
        // activated is that no buttons are initially selected.
        if (option.selected) {
            elem.classList.add("selected");
        }
        for (let j = 0; j < option.classList.length; j++) {
            elem.classList.add(option.classList[j]);
        }
        option.ui = elem;

        container.appendChild(elem);
        elem.addEventListener("mouseup", function(obj) {
            selectTab(option.value);
        });
    }

    function scrollToLastTab() {
        container.scrollLeft = container.scrollWidth;
    }

    function styleTabs() {
        for (let i = 0; i < select.options.length; i++) {
            let option = select.options[i];
            styleTab(option);
        }
        scrollToLastTab();
    }

    styleTabs();
}

function styleUITabs(elem) {
    let container = document.createElement("div");
    container.classList.add("container");
    elem.style = null;
    elem.appendChild(container);
    let select = elem.querySelector("select");
    if (isEmpty(select.name)) {
        throw new Error("UITabs select element must have a name");
    }
    if (select.multiple) {
        throw new Error("UITabs select element may not be multiple select");
    }
    // View ID used for automated testing
    elem.classList.add(`ui-tabs-${select.name}`);
    let tabs = new UITabs(select, container);
    select.ui = tabs;
}

function styleAllUITabs(elem) {
    let lists = elem.getElementsByClassName("ui-tabs");
    for (let i = 0; i < lists.length; i++) {
        let list = lists[i];
        styleUITabs(list);
    }
}

/**
 * left/above - Display left-adjusted, above element
 * left/below - Disply left-adjusted, below element
 * right/above - Display right-adjusted, above element
 * right/below - Display right-adjusted, below element (common for OS bar components on right)
 */
function UIPopOverSide(leftRight, aboveBelow) {
    readOnly(this, "left", leftRight == "left");
    readOnly(this, "right", leftRight == "right");
    readOnly(this, "top", aboveBelow == "above");
    readOnly(this, "bottom", aboveBelow == "below");
}

/**
 * A pop-over provides, small, helpful message to user. It points to the
 * element it references.
 *
 * @param {HTMLElement} element - The element the message will relate to
 * @param {string} message - The message to display in the pop-over
 * @param {UIPopOverSide} side - Indicates where the arrow indicator will display relative to the element
 */
function UIPopOver(element, side) {
    let container;
    let message;
    let topArrow;
    let bottomArrow;

    function make() {
        container = document.createElement("div");
        container.classList.add("ui-pop-over");

        topArrow = document.createElement("div");
        topArrow.classList.add("top-arrow");
        topArrow.style.zIndex = 100;
        container.appendChild(topArrow);

        message = document.createElement("div");
        message.classList.add("message");
        message.style.zIndex = 99;
        container.appendChild(message);

        bottomArrow = document.createElement("div");
        bottomArrow.classList.add("bottom-arrow");
        bottomArrow.style.zIndex = 100;
        container.appendChild(bottomArrow);
    }

    function setMessage(msg) {
        message.innerHTML = msg;
    }
    this.setMessage = setMessage;

    function show() {
        let desktop = document.getElementById("desktop");
        desktop.appendChild(container);

        let crect = container.getBoundingClientRect();
        let rect = element.getBoundingClientRect()

        // NOTE: Arrows are 16x11

        // Hard-coded to right/below
        let top = rect.y + rect.height /* make space for arrow to touch element */;
        let left = rect.x - crect.width + 21 /* offset arrow on right */;
        container.style.top = `${top}px`;
        container.style.left = `${left}px`;

        left = crect.width - 24;
        topArrow.style.top = `2px`;
        topArrow.style.left = `${left}px`;
        topArrow.style.display = null;
        bottomArrow.style.display = "none";
        // -- right/below
    }
    this.show = show;

    function hide() {
        container.remove();
    }
    this.hide = hide;

    make();
}

/**
 * Represents a progress bar.
 */
function UIProgressBar(elem, indeterminate, _amount) {

    let amount = _amount;
    property(this, "amount",
        function() { return amount },
        function() { }
    );

    let bar = elem.querySelector(".ui-progress");

    /**
     * Set the amount of progress that has finished w/ an optional value
     * to display within the bar.
     *
     * @param {int} amount - The amount of finished progress
     * @param {str} value - A string value to display w/in the bar
     */
    function setProgress(amt, value) {
        amount = amt;

        // Special case where if a value exists, and there is no amount, the bar
        // should be resized to fit the `value`.
        if (amt == 0 && !isEmpty(value)) {
            bar.style.width = null; // Shrink just in case it's a re-used element
            bar.style.display = 'inline-block';
        }
        else {
            bar.style.display = null;
            bar.style.width = `${amount}%`;
        }
        bar.textContent = isEmpty(value) ? '' : value;
    }
    this.setProgress = setProgress;
}

/**
 * Create a UIProgressBar from a partial or fully formed `.ui-progress-bar` element.
 *
 * Associates UIProgressBar to `elem.ui`
 *
 * @param {HTMLElement} elem - `.ui-progress-bar` element
 */
function styleUIProgressBar(elem) {
    let container = elem.querySelector(".ui-progress-container");
    let amount = 0;
    if (isEmpty(container)) {
        container = document.createElement("div");
        container.classList.add("ui-progress-container");
        elem.appendChild(container);
        let progress = document.createElement("div");
        progress.classList.add("ui-progress");
        container.appendChild(progress);
    }
    else {
        amount = parseInt(elem.querySelector(".ui-progress").style.width);
        if (isEmpty(amount)) {
            amount = 0;
        }
    }
    elem.ui = new UIProgressBar(
        elem,
        elem.classList.contains("indeterminate"),
        amount
    );
}

/**
 * Style all `.ui-progress-bar` elements.
 *
 * @param {HTMLElement} container
 */
function styleAllUIProgressBars(container) {
    let bars = container.getElementsByClassName("ui-progress-bar");
    for (let i = 0; i < bars.length; i++) {
        let bar = bars[i];
        styleUIProgressBar(bar);
    }
}
