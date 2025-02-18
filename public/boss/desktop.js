
/**
 * Provides Desktop functionality.
 */
function Desktop(ui) {
    function init() {
        const icons = document.querySelectorAll(".desktop-icon");
        const container = document.querySelector("#desktop-icons");

        let selectedIcon;
        let selectedIndex;

        for (let i = 0; i < icons.length; i++) {
            let icon = icons[i];
            let isSameIcon = false;
            let index;

            // The hot-spot is either the `img` or the `#last-desktop-icon`. Tracking
            // this makes it easy to turn hovering state on and off.
            let selectedHotSpot;
            let lastIcon = icon.querySelector("#last-desktop-icon");
            if (isEmpty(lastIcon)) {
                selectedHotSpot = icon.querySelector("img");
            }
            else {
                selectedHotSpot = lastIcon;
            }

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
                // Always move icon before the last desktop icon
                if (!isEmpty(icon.querySelector("#last-desktop-icon"))) {
                    icon.before(selectedIcon);
                }
                else {
                    let index = Array.from(container.children).indexOf(icon);
                    if (selectedIndex > index) {
                        icon.before(selectedIcon);
                    }
                    else {
                        icon.after(selectedIcon);
                    }
                }

                selectedIcon = null;
            });

            icon.addEventListener("click", () => {
                console.log("Clicked");
            });

            icon.addEventListener("contextmenu", (e) => {
                e.preventDefault();
                // TODO: Display option to remove, open, etc.
                // TODO: Remove the icon, update user preferences, etc.
                // icon.remove();
                console.log("Right-clicked");
            });
        }
    }
    this.init = init;

    function addApplicationIcon(app) {
    }
    this.addApplicationIcon = addApplicationIcon;

    function addApplicationIcons(apps) {
    }
    this.addApplicationIcons = addApplicationIcons;

    function removeApplicationIcon(bundleId) {
    }
    this.removeApplicationIcon = removeApplicationIcon;
}
