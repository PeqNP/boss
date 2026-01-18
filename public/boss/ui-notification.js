/**
 * Display and manage `Notification`s.
 *
 *
 * This displays notifications as they come in but can also show the
 * "Notifications panel" which groups notificadtions by the app. A user may
 * dismiss an entire group, expand a group, collapse a group, etc.
 */
function UINotification(os) {

    const START_TOP_POS = 40;

    let displayedNotifications = 0;
    let unreadNotifications = false;
    let clearNotificationsButton;

    function init() {
        let icon = document.getElementById("os-bar-notifications");
        icon.style.display = "none";
        icon.addEventListener("click", async function(e) {
            toggleNotificationsVisibility();
        });

        // Currently the button floats
        let button = document.createElement("button");
        button.classList.add("primary");
        button.style.position = "absolute";
        button.style.top = `${START_TOP_POS}px`;
        button.style.right = `18px`;
        button.innerHTML = "Clear notifications";
        button.addEventListener("click", async function(e) {
            clearAllNotifications();
            hideNotifications();
        });
        let desktop = document.querySelector("#desktop");
        desktop.appendChild(button);
        clearNotificationsButton = button;

        hideNotifications();
    }
    this.init = init;

    function didCloseNotification(notification) {
        displayedNotifications -= 1;
        if (displayedNotifications < 1) {
            let icon = document.getElementById("os-bar-notifications");
            icon.style.display = "none";
            hideNotifications();
        }
    }

    /**
     * Show a notification.
     *
     * This manages the showing, persisting, and grouping, of notifications.
     */
    async function show(notification) {
        if (!os.isLoaded()) {
            return console.error(error);
        }

        showNotifications();

        let app = await os.openApplication(notification.bundleId);
        let notif = await app.loadController(notification.controllerName);

        // NOTE: The Notification controller/window is configured to be managed
        // directly by this library, and not the OS.

        // FIXME: The 'close' button may still be tapped, even though the windows
        // behind the current notification window can not be brought into focus.
        // Not sure if I should disable closing a window if it's a type of window
        // that is managed by another service, and it is not the top-most notification
        // window.

        let endTopPos = START_TOP_POS + (displayedNotifications * 10) + 34;

        // The position of notifications are at the top right and should not
        // be affected by the initial position set by UI lib.
        notif.style.top = `${endTopPos}px`;
        // The window is 340px in size. Add 20px for padding
        notif.style.right = `360px`;

        notif.ui.show(function(ctrl) {
            ctrl.configure(notification);
            ctrl.delegate = {
                didCloseNotification: didCloseNotification
            };
        });

        // TODO: If !persistent, close the notification after 10 seconds
        // (done by NotificationController)

        displayedNotifications += 1;
        let icon = document.getElementById("os-bar-notifications");
        // TODO: Display icon w/ light if unread (is not possible to be visible)
        icon.style.display = null;
        // icon.classList.add("unread");
    }
    this.show = show;

    /**
     * Toggle notifications visibility.
     */
    function toggleNotificationsVisibility() {
        if (clearNotificationsButton.style.display == "none") {
            showNotifications();
        }
        else {
            hideNotifications();
        }
    }

    /**
     * Returns all of the UINotification windows.
     *
     * @returns {[UIWindow]}
     */
    function uiNotifications() {
        let notifs = document.querySelectorAll(".ui-notification");
        let windows = [];
        for (const notif of notifs) {
            windows.push(notif.parentNode);
        }
        return windows;
    }

    /**
     * Show notifications that have not yet been dismissed.
     *
     * This also shows the "Clear notifications" button.
     */
    function showNotifications() {
        clearNotificationsButton.style.display = null;
        let notifs = uiNotifications();
        for (const notif of notifs) {
            notif.style.display = null;
        }
    }

    /**
     * Hide notifications.
     */
    function hideNotifications() {
        clearNotificationsButton.style.display = "none";
        let notifs = uiNotifications();
        for (const notif of notifs) {
            notif.style.display = "none";
        }
    }

    /**
     * Clear all notifications.
     */
    function clearAllNotifications() {
        let notifs = uiNotifications();
        for (const notif of notifs) {
            notif.ui.close();
        }
    }
    this.clearAllNotifications = clearAllNotifications;
}
