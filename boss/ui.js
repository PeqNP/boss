/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * Provides access to UI library.
 */
function UI(os) {

    // List of "open" window controllers.
    let controllers = {};

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
        // `prop` is the `id` of the `window`
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
        styleOSMenus();
        stylePopupMenus();
        styleFolders();

        /**
         * Close all menus when user clicks outside of `select`.
         */
        document.addEventListener("click", closeAllMenus);
    }
    this.init = init;

    /**
     * Creates an instance of a `UIWindow` given a `fragment.id`.
     *
     * - Parameter fragmentID: The `id` of the `fragment` in `document`.
     * - Returns: Instance of the `fragment` as a `UIWindow`
     */
    function makeWindow(fragmentID) {
        var fragment = document.getElementById(fragmentID);
        var win = fragment.querySelector(`.window`).cloneNode(true);
        let id = win.getAttribute("id");
        if (id === null) {
            console.error("Window w/ ID (" + id + ") must have a controller");
            return;
        }
        let code = "new window." + id + "(win)";
        let ctrl = eval(code);
        if (ctrl.viewDidLoad !== undefined) {
            ctrl.viewDidLoad();
        }
        controllers[id] = ctrl;
        // Register window
        win.ui = new UIWindow(this, win, ctrl);
        return win;
    }
    this.makeWindow = makeWindow;

    function makeModal(fragmentID) {
    }
    this.makeModal = makeModal;

    /**
     * Register all windows with the OS.
     *
     * This allows for window menus to be displayed in the OS bar.
     *
     * NOTE: This is temporary until all windows are creqated by the OS
     * and not pre-rendered before the OS starts.
     */
    function registerWindows() {
        let windows = document.getElementsByClassName("window");
        for (let i = 0; i < windows.length; i++) {
            registerWindow(windows[i]);
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
     */
    function registerWindow(win) {
        // Register window for life-cycle events
        let id = win.getAttribute("id");
        if (id !== null && id.length > 0) {
            let code = "new window." + id + "(win);";
            let ctrl = eval(code);
            if (ctrl !== null && ctrl !== "undefined") {
                // TODO: Eventually the controller will be registered and life-cycle events passed.
                // TODO: Eventually an instance of the controller will be created, container
                // content rendered, and then viewDidLoad called before it is visible in the #desktop.
                if (ctrl.viewDidLoad !== undefined) {
                    ctrl.viewDidLoad();
                }
                // For now, only the viewDidAppear life-cycle event is relevant
                // as everything is rendered at once.
                if (ctrl.viewDidAppear !== undefined) {
                    ctrl.viewDidAppear();
                }
                controllers[id] = ctrl;
            }
        }

        var osMenus = win.getElementsByClassName("os-menus");
        if (osMenus.length < 1) {
            return;
        }
        osMenus = osMenus[0];

        var menus = osMenus.getElementsByClassName("os-menu");
        for (;menus.length > 0;) {
            var menu = menus[0];
            menu.parentNode.removeChild(menu);
            addOSBarMenu(menu);
        }
        osMenus.parentNode.removeChild(osMenus);
    }

    /**
     * Add a menu to the OS bar.
     */
    function addOSBarMenu(menu) {
        var p = document.getElementById("menus");
        p.appendChild(menu);
    }
    this.addOSBarMenu = addOSBarMenu

    /**
     * Show Bithead OS About menu.
     *
     * FIXME: This needs to use the latest patterns to instantiate, show,
     * and hide windows/modals.
     */
    function showAboutModal() {
        var fragment = document.getElementById("about-modal");
        var modal = fragment.querySelector("div.modal").cloneNode(true);
        if (modal === null) {
            console.warn("OS About modal not found");
            return;
        }
        var button = modal.querySelector("button.default");
        button.addEventListener("click", function() {
            closeWindow(modal);
        });
        var desktop = document.getElementById("desktop-container");
        desktop.appendChild(modal);
    }
    this.showAboutModal = showAboutModal;

    /**
     * Close a (modal) window.
     *
     * Removes the window from the view hierarchy.
     *
     * FIXME: Needs to be updated to use latest UI patterns.
     *
     * - Parameter win: The window to close.
     */
    function closeWindow(win) {
        const parent = win.parentNode;
        parent.removeChild(win);
    }
    /**
     * Show an error modal above all other content.
     *
     * FIXME: Needs to be updated to use the latest patterns.
     */
    function showErrorModal(error) {
        var fragment = document.getElementById("error-modal");
        var modal = fragment.querySelector("div.modal").cloneNode(true);
        var message = modal.querySelector("p.message");
        message.innerHTML = error;
        var button = modal.querySelector("button.default");
        button.addEventListener("click", function() {
            closeWindow(modal);
        });
        // Center modal in the middle of the screen.
        modal.classList.add("center-control");
        // Display modal in desktop container
        var desktop = document.getElementById("desktop-container");
        desktop.appendChild(modal);
    }
    this.showErrorModal = showErrorModal;

    /**
     * Show a delete modal.
     *
     * Ask user if they want to delete a model. This can be used in all contexts
     * where a destructive action can take place.
     *
     * @param {string} msg - The (question) message to display.
     * @param {function} cancel - A function that is called when user presses `Cancel`
     * @param {function} ok - A function that is called when user presses `OK`
     */
    function showDeleteModal(msg, cancel, ok) {
        var fragment = document.getElementById("delete-modal");
        var modal = fragment.querySelector("div.modal").cloneNode(true);
        var message = modal.querySelector("p.message");
        message.innerHTML = msg;

        var cancelButton = modal.querySelector("button.default");
        cancelButton.addEventListener("click", function() {
            if (cancel !== null) { cancel(); }
            closeWindow(modal);
        });

        var okButton = modal.querySelector("button.primary");
        okButton.addEventListener("click", function() {
            if (ok !== null) { ok(); }
            closeWindow(modal);
        });

        // Display modal in desktop container
        var desktop = document.getElementById("desktop-container");
        desktop.appendChild(modal);
    }
    this.showDeleteModal = showDeleteModal;
}

/**
 * Provides window related functions.
 */
function UIWindow(ui, view, controller) {

    view.controller = controller;

    function show() {
        // NOTE: Can I use `?` for undefined properties too?
        if (controller.viewWillAppear !== undefined) {
            controller.viewWillAppear();
        }

        let desktop = document.getElementById("desktop-container");
        desktop.appendChild(view);

        if (controller.viewDidAppear !== undefined) {
            controller.viewDidAppear();
        }
    }
    this.show = show;

    function close() {
        if (controller.viewWillDisappear !== undefined) {
            controller.viewWillDisappear();
        }

        let desktop = document.getElementById("desktop-container");
        desktop.removeChild(view);

        if (controller.viewDidDisappear !== undefined) {
            controller.viewDidDisappear();
        }
    }
    this.close = close;
}

/**
 * Provides protocol definition for a Controller.
 *
 * A `UIController` allows a `div.window` to receive life-cycle events from the OS.
 *
 * All functions are optional. Therefore, implement only the functions needed.
 *
 * A `UIController` is defined on a `div.window` with the `id` attribute.
 * e.g. <div class="window" id="my_controller">
 *
 * When the `id` attribute exists, it is assumed there is a `script` tag inside the `div.window`.
 * The `script` tag must have a function with the same name as its `id`.
 * This `script` is used to receive view life-cycle signals from the OS.
 *
 * e.g.
 * ```
 * // The respective `UIController`'s `view` is provided as the first parameter.
 * function my_controller(view) {
 *     this.viewDidAppear = function() {
 *         // Do something when the view appears
 *     }
 * }
 * ```
 */
function UIController() {
    /**
     * Called directly before the window is rendered.
     *
     * TODO: Not yet implemented.
     */
    function viewDidLoad() { }

    /**
     * Called after the window has been rendered.
     */
    function viewDidAppear() { }
}

function styleFolders() {
    var folders = document.getElementsByClassName("folder");
    for (var i = 0; i < folders.length; i++) {
        var folder = new UIFolder(folders[i]);
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
    // console.log("Closing all (" + className + ")s");
    let parentClassName = className + "-container";
    var containers = document.getElementsByClassName(parentClassName);
    for (var j = 0; j < containers.length; j++) {
        var container = containers[j];
        if (container.classList.contains("popup-inactive")) {
            continue;
        }
        // console.log("Closing menu (" + container + ")");
        container.classList.remove("popup-active");
        container.classList.add("popup-inactive");
        // Reset arrow
        var choicesLabel = container.querySelector("." + className + "-choices-label");
        choicesLabel.classList.remove("popup-arrow-active");
    }
}

/**
 * Close all popup menus.
 */
function closeAllMenus() {
    closeMenuType("os-menu");
    closeMenuType("popup");
}

/**
 * Extract metadata column name, and style info, from list of `li`s.
 *
 * @param [li] - List of `li`s to parse that provides metadata column title information
 * @returns UIFolderMetadata
 */
function getFolderMetadata(lis) {
    var metadata = Array();
    for (var i = 0; i < lis.length; i++) {
        var name = lis[i].innerHTML;
        var style = lis[i].style;
        var m = new UIFolderMetadata(name, style);
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
        let label = select.parentNode.querySelector(".popup-choices-label");
        label.innerHTML = select.options[select.selectedIndex].innerHTML;
    }

    function selectValue(value) {
        for (let idx = 0; idx < select.options.length; idx++) {
            if (select.options[idx].value == `${value}`) {
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
        choicesLabel.setAttribute("class", "popup-choices-label");
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
 * Style menus displayed in the OS bar.
 */
function styleOSMenus() {
    // FIX: Does not select respective select menu. Probably because it has to be reselected.
    let menus = document.getElementsByClassName("os-menu");
    for (let i = 0; i < menus.length; i++) {
        let selectElement = menus[i].getElementsByTagName("select")[0];

        // The container is positioned absolute so that when a selection is made it overlays
        // the content instead of pushing it down.
        let container = document.createElement("div");
        container.setAttribute("class", "os-menu-container popup-inactive");
        menus[i].appendChild(container);

        // The first option is the label for the group of choicese. This will be removed upon selecting a choice.
        let choicesLabel = document.createElement("div");
        choicesLabel.setAttribute("class", "os-menu-choices-label");
        // FIXME: This _should_ always be the `0`th element
        let label = selectElement.options[selectElement.selectedIndex].innerHTML;
        if (label.startsWith("img:")) {
            let img = document.createElement("img");
            img.src = label.split(":")[1];
            choicesLabel.appendChild(img);
        }
        else {
            choicesLabel.innerHTML = label;
        }
        container.appendChild(choicesLabel);

        // Container for all choices
        let choices = document.createElement("div");
        choices.setAttribute("class", "popup-choices");

        // Create choices
        // NOTE: This skips the first choice, which is used as the label for the menu.
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
            choice.setAttribute("id", option.getAttribute("id"));
            option.setAttribute("id", "");
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
        choicesLabel.addEventListener("click", function(e) {
            var container = this.parentNode; // os-menu-container
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
        let desktop = document.getElementById("desktop-container");
        desktop.appendChild(element);
    }

    this.showImage = showImage;

    function make() {
        var fragment = document.getElementById("image-viewer");
        var modal = fragment.querySelector("div.modal").cloneNode(true);
        var button = modal.querySelector("button.default");
        button.addEventListener("click", function() {
            closeWindow(modal);
        });
        modal.classList.add("center-control");
        return modal;
    }

    element = make();
}
