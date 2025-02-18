
/**
 * Provides Desktop functionality.
 */
function Desktop(ui) {
    function init() {
        const icons = document.querySelectorAll('.desktop-icon');
        // Size includes padding, image, etc.
        const iconSize = 40;
        const totalPadding = 10; // 5+5 padding
        // Represents the initial padding on the left from the first icon in the
        // column. This should always be 1/2 of `totalPadding`.
        const leftPadding = 5;

        // To avoid complexity, each desktop icon takes up Npx. The padding is
        // defined in CSS. For example, padding between icons is 10px. The icon
        // will be centered in a div with padding of 5px, making 10px between
        // icons.

        // Icons have padding of 10px
        // TODO: Icons span the width of the window and repositioned if Desktop changes size
        // Icons that start to drag from the left of another icon, shift all other
        // icons to the top and left if the dragging icon when hovering.
        // Icons that start to drag from the right of another icon, shift all other
        // icons to the bottom and right when hovering.
        // TODO: Add the last icon. No icon goes before it.

        let selectedIcon;

        for (let i = 0; i < icons.length; i++) {
            // Drag and drop functionality with grid snap
            let offsetX, offsetY;

            let icon = icons[i];

            icon.addEventListener("mousedown", (e) => {
                console.log("mouse down");
                selectedIcon = icon.cloneNode(true);
                selectedIcon.classList.add("selected-desktop-icon");

                offsetX = e.clientX - icon.offsetLeft;
                offsetY = e.clientY - icon.offsetTop;
                // TODO: Create copy of the element and make transparent
                selectedIcon.style.top = `${offsetX}px`;
                selectedIcon.style.left = `${offsetY}px`;
            });

            icon.addEventListener("mouseenter", (e) => {
                if (isEmpty(selectedIcon)) {
                    return;
                }
                // Add `hovering` state to icon
                if (!icon.classList.contains("hovering")) {
                    icon.classList.add("hovering");
                }
            });

            icon.addEventListener("mouseleave", (e) => {
                if (isEmpty(selectedIcon)) {
                    return;
                }
                icon.classList.remove("hovering");
            });

            document.addEventListener("mousemove", (e) => {
                if (isEmpty(selectedIcon)) {
                    return;
                }

                console.log("mousemove");

                let x = e.clientX - offsetX;
                let y = e.clientY - offsetY;

                selectedIcon.style.left = `${x}px`;
                selectedIcon.style.top = `${y}px`;
            });

            document.addEventListener("mouseup", () => {
                if (isEmpty(selectedIcon)) {
                    return;
                }

                // TODO: Remove `hovering` state

                selectedIcon.remove();
                selectedIcon = null;

                // TODO: Resettle icon
                // icon.style.left = `${lastGridX}px`;
                // icon.style.top = `${lastGridY}px`;

                // TODO: Shift icons
                // TODO: Update user preferences?
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
}
