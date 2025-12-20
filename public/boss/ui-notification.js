/**
 * Display and manage `Notification`s.
 *
 *
 * This displays notifications as they come in but can also show the
 * "Notifications panel" which groups notificadtions by the app. A user may
 * dismiss an entire group, expand a group, collapse a group, etc.
 */
function UINotification(ui) {

    /**
     * Show a notification.
     *
     * This manages the showing, persisting, and grouping, of notifications.
     */
    async function show(notification) {
        if (!os.isLoaded()) {
            return console.error(error);
        }
        let app = await os.openApplication("io.bithead.boss");
        let notif = await app.loadController("Notification");

        // NOTE: The Notification controller/window is configured to be managed
        // directly by this library, and not the OS.

        // The position of notifications are at the top right and should not
        // be affected by the initial position set by UI lib.
        notif.style.top = `50px`;
        notif.style.right = `220px`;

        notif.ui.show(function(ctrl) {
            ctrl.configure(notification);
        });

        // TODO: If !persistent, hide the notification after 10 seconds
    }
    this.show = show;

    /**
     * Show all notifications that have not been dismissed by the user.
     */
    function showNotifications() {
        console.log("showNotifications");
    }
    this.showNotifications = showNotifications;

    /**
     * Hide all notifications that have not been dismissed by the user.
     */
    function hideNotifications() {
        console.log("hideNotifications");
    }
    this.hideNotifications = hideNotifications;
}
