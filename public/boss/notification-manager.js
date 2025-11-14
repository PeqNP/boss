/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

class NotificationError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'NotificationError';
  }
}

/**
 * Connect to the BOSS notifications server.
 */
function NotificationManager(os) {
    const RECONNECT_DELAY = 1000;

    // The WebSocket connection to BOSS Notification Server
    let conn = null;

    // Pending notifications to send to server.
    let sendQueue = [];
    let seenQueue = [];
    let deleteQueue = [];

    // Retry connecting to notification server
    let retry = false;

    /**
     * Connect to the notifications manager.
     *
     * This should occur after a user has signed in. As this endpoint requires
     * a signed in user.
     */
    async function connect() {
        if (!isEmpty(conn)) {
            await conn.close();
        }

        retry = true;

        // TODO: If connection fails, attempt to reconnect
        conn = new WebSocket("/notification/connect");

        conn.onopen = async function() {
            console.log("Connected to Notifications server");
            // TODO: Send queued notifications
            // TODO: Show pending server notifications
        };

        conn.onmessage = async function(ev) {
            const data = JSON.parse(ev.data);
            console.log(`Received message (${data})`);
        };

        conn.onclose = async function() {
            console.log("Connection closed to Notifications server");
            conn = null;
        };

        conn.onerror = async function(err) {
            // TODO: If disconnected uncleanly, reconnect after DELAY seconds.
            console.error(err);
            await conn.close();
        }
    }
    this.connect = connect;

    /**
     * Disconnect from the notifications manager.
     *
     * This must be called before the user is signed out. This should
     * be awaited to ensure the user is not prematurely signed out before
     * the connection can be closed.
     */
    async function close() {
        if (isEmpty(conn)) {
            console.warning("Connection to notification server is already closed.");
            return;
        }

        retry = false;

        // Clear queue of pending notifications. This prevents other users from
        // sending notifications on another user's session.
        sendQueue = [];
        seenQueue = [];
        deleteQueue = [];

        await conn.close();
    }
    this.close = close;

    /**
     * Show all notifications queued on the server.
     */
    async function show() {
        if (isEmpty(conn)) {
            throw new NotificationError("Connect to notification server before getting notifications");
        }
    }

    /**
     * Send a generic notification.
     *
     * This will use the generic BOSS `NotificationController` to display
     * the message.
     *
     * This only sends messages to the signed in user.
     *
     * @param {String} deepLink - A deep link that will redirect user to app
     *      when the notification is tapped.
     * @param {String} title - The title of the notification
     * @param {String} message - The notification of the message
     * @returns `true` if message sent
     */
    async function send(deepLink, message) {
        if (isEmpty(conn)) {
            console.warning("Not connected to notification server");
            sendQueue.push(0);
            return false;
        }
        return true;
    }
    this.send = send;

    /**
     * Send an application notification.
     *
     * This will send a notification using the respective app's `NotificationController`
     * to present the notification. This is required for any notification that requires
     * a custom interface.
     *
     * @param {String} bundleId - The application bundle ID sending the request
     * @param {String} controllerName - The application's `NotificationController`
     * @param {String} deepLink - A deep link that will redirect user to app
     *      when notification is tapped.
     * @param {dict} metadata - Dictionary containing data to configure respective
     * @param {int?} userId - The user to send the message to. If omitted, the
     *      notification is sent to the signed in user
     */
    async function sendAppNotifiation(bundleId, controllerName, deepLink, metadata, userId) {
        if (isEmpty(conn)) {
            console.warning("Not connected to notification server");
            sendQueue.push(0);
            return;
        }
        return;
    }
    this.sendAppNotifiation = sendAppNotifiation;

    /**
     */
    async function seen(notificationIds) {
        if (isEmpty(conn)) {
            console.warning("Not connected to notification server");
            seenQueue.push(0);
            return;
        }
    }
    this.seen = seen;

    /**
     */
    async function _delete(notificationIds) {
        if (isEmpty(conn)) {
            console.warning("Not connected to notification server");
            deleteQueue.push(0);
            return;
        }
    }
    this.delete = _delete;
}
