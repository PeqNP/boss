
/**
 * Provides Desktop functionality.
 */
function Desktop(ui) {
    let container;
    let selectedIcon;
    let selectedIndex;

    function init() {
        container = document.querySelector("#desktop-icons");
    }
    this.init = init;

    /**
     * @param {HTMLElement} icon
     */
    function registerDragEvents(icon) {
        let isSameIcon = false;
        let index;

        // The hot-spot is the `img` element. Tracking this makes it easy to
        // toggle hovering state.
        let selectedHotSpot = icon.querySelector("img");

        icon.addEventListener("dragstart", (e) => {
            isSameIcon = true;
            selectedIcon = icon;
            selectedIndex = Array.from(container.children).indexOf(icon);
            e.dataTransfer.setData('text/plain', 'dragging');

            icon.addEventListener("dragend", () => {
                isSameIcon = false;
            }, { once: true });
        });

        // These events are for targets, not the subject being dragged.
        icon.addEventListener("dragenter", (e) => {
            if (isSameIcon || e.currentTarget !== e.target || e.currentTarget.contains(e.relatedTarget) || isEmpty(selectedIcon)) {
                return;
            }

            e.stopPropagation();
            e.preventDefault();

            // Add `hovering` state to icon
            if (!selectedHotSpot.classList.contains("hovering")) {
                selectedHotSpot.classList.add("hovering");
            }
        });

        icon.addEventListener("dragover", (e) => {
            e.preventDefault(); // Required for drag/drop to work
        });

        icon.addEventListener("dragleave", (e) => {
            if (isSameIcon || e.currentTarget !== e.target || e.currentTarget.contains(e.relatedTarget) || isEmpty(selectedIcon)) {
                return;
            }

            e.stopPropagation();
            e.preventDefault();

            selectedHotSpot.classList.remove("hovering");
        });

        icon.addEventListener("drop", (e) => {
            if (isSameIcon || isEmpty(selectedIcon)) {
                return;
            }

            e.stopPropagation();
            e.preventDefault();

            selectedHotSpot.classList.remove("hovering");

            selectedIcon.remove();

            // Reposition icon in new location
            let index = Array.from(container.children).indexOf(icon);
            if (selectedIndex > index) {
                icon.before(selectedIcon);
            }
            else {
                icon.after(selectedIcon);
            }

            selectedIcon = null;
        });
    }

    /**
     * Add an app to the desktop.
     *
     * @param {AppLink} app
     */
    function addApp(app) {
        let icon = document.createElement("div");
        icon.id = `desktop-icon-${app.bundleId}`; // Automated testing
        icon.data = app;
        icon.classList.add("desktop-icon");

        let img = document.createElement("img");
        img.src = `/boss/app/${app.bundleId}/${app.icon}`;
        icon.appendChild(img);
        let span = document.createElement("span");
        span.innerHTML = app.name;
        icon.appendChild(span);

        container.appendChild(icon);

        registerDragEvents(icon, null);

        icon.addEventListener("click", () => {
            os.openApplication(app.bundleId);
        });

        icon.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            // TODO: Display option to remove, open, etc.
            // TODO: Remove the icon, update user preferences, etc.
            // icon.remove();
            console.log("Right-clicked");
        });
    }
    this.addApp = addApp;

    /**
     * Add N apps to desktop.
     *
     * @param {[AppLink]} apps
     */
    function addApps(apps) {
        for (let i = 0; i < apps.length; i++) {
            addApp(apps[i]);
        }
    }
    this.addApps = addApps;

    function removeApp(bundleId) {
        console.log("removeApp - not implemented");
    }
    this.removeApp = removeApp;
}
