/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

class NotificationError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'NotificationError';
  }
}

/**
 * BOSS Notification Manager provides real-time messaging to client.
 *
 * - Notifications
 * - Application events
 * - Session status
 *
 * Regarding disconnecting from the server;
 * Because the notification server is responsible for refreshing
 * the session, and sessions are currently invalidated when the
 * server shuts down, when disconnected, this will not retry
 * connecting to the server. This assumes the listener is signing
 * the user out immediately upon disconnecting.
 */
function NotificationManager(os) {
    const RECONNECT_DELAY = 1000;
    // Response to a server command e.g. `ping`
    const NOTIFICATION_TYPE_COMMAND = 0;
    // Display system/user notification
    const NOTIFICATION_TYPE_NOTIFICATION = 1;
    // Session is expiring soon
    const NOTIFICATION_TYPE_EXPIRES = 2;

    // The WebSocket connection to BOSS Notification Server
    let conn = null;

    // Pending notifications to send to server.
    let sendQueue = [];
    let seenQueue = [];
    let deleteQueue = [];

    let delegate = protocol(
        "NotificationManagerDelegate", this, "delegate",
        [
            /**
             * Called when connected to notifications server.
             */
            "didConnect",
            /**
             * Called when disconnected from notifications server.
             */
            "didDisconnect",
            /**
             * Called when notification(s) are returned from server
             */
            "didReceiveNotifications",
            /**
             * Called when response from command is processed
             * @param {String} response - The response to the command
             */
            "didReceiveResponse",
            /**
             * Called when the session is about to expire
             *
             * @param {Integer} secondsRemaining - The amount of time left before session expires on server
             */
            "didReceiveSessionWillExpireSoon"
        ]
    );

    /**
     * Connect to the notifications manager.
     *
     * This should occur after a user has signed in. As this endpoint requires
     * a signed in user.
     *
     * @param {Function?} fn - Function to call after connection is re-established.
     */
    async function connect(fn) {
        if (!isEmpty(conn)) {
            // await conn.close();
            return;
        }

        const ws = new WebSocket("/notification/connect");

        ws.onopen = async function() {
            console.log("Connected to Notifications server");
            conn = ws;
            delegate?.didConnect();

            if (!isEmpty(fn)) {
                fn();
            }
            // TODO: Send queued notifications
            // TODO: Show pending server notifications
        };

        ws.onmessage = async function(ev) {
            console.log(`Received message (${ev.data})`);
            const data = JSON.parse(ev.data);
            if (data.type == NOTIFICATION_TYPE_COMMAND) {
                delegate?.didReceiveResponse(data.command);
            }
            else if (data.type == NOTIFICATION_TYPE_EXPIRES) {
                delegate?.didReceiveSessionWillExpireSoon(parseInt(data.sessionExpiresInSeconds));
            }
            else {
                delegate?.didReceiveNotifiations(data.notifications);
            }
        };

        ws.onclose = async function() {
            console.log("Connection closed to Notifications server");
            conn = null;
            delegate?.didDisconnect();
        };

        ws.onerror = async function(err) {
            console.log(`Received error (${err})`);
        }
    }

    /**
     * Start listening to notifications manager.
     *
     * This must be called directly after signing in.
     */
    async function start() {
        if (!isEmpty(conn)) {
            console.warn("Notification server already started.");
            return;
        }

        await connect();
    }
    this.start = start;

    /**
     * Stop listening to notifications manager.
     *
     * This must be called before the user is signed out. This should
     * be awaited to ensure the user is not prematurely signed out before
     * the connection can be closed.
     */
    async function stop() {
        if (isEmpty(conn)) {
            console.warn("Notification server already stopped.");
            return;
        }

        // Clear queue of pending notifications. This prevents other users from
        // sending notifications on another user's session.
        sendQueue = [];
        seenQueue = [];
        deleteQueue = [];

        await conn.close();
    }
    this.stop = stop;

    /**
     * Show all notifications queued on the server.
     */
    async function show() {
        if (isEmpty(conn)) {
            throw new NotificationError("Connect to notification server before getting notifications");
        }
    }

    async function refreshSession() {
        sendMessage(function() {
            conn.send("refresh");
        }, "Connect to the notification server before refreshing session");
    }
    this.refreshSession = refreshSession;

    /**
     * Send message (command|notification|etc.)
     *
     * Reconnects to the server, if needed.
     *
     * @param {Function} fn - Function to call once connection is (re)established
     * @param {String?} msg - Message to display if no connection is made
     */
    function sendMessage(fn, msg) {
        if (!isEmpty(conn)) {
            fn();
            return;
        }

        let err = isEmpty(msg) ? msg : "Not connected to notification server";
        throw new NotificationError(err);
    }

    /**
     * Send command to notification server.
     *
     * You must listen to didReceiveResponse for respective command.
     *
     * Available commands:
     * - ping: Returns with "pong"
     *
     * @param {string} command - Command to send to server
     */
    function sendCommand(cmd) {
        sendMessage(function() {
            conn.send(cmd);
        }, "Connect to the notification server before sending commands");
    }
    this.sendCommand = sendCommand;

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
     */
    function send(deepLink, title, message) {
        sendMessage(function() {
            // TODO: Send message. `0` is pushed for illustrative purpose only.
            sendQueue.push(0);
        });
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
        sendMessage(function() {
            // TODO: Send message. `0` is pushed for illustrative purpose only.
            sendQueue.push(0);
        });
    }
    this.sendAppNotifiation = sendAppNotifiation;

    /**
     * Mark notification as "seen." This prevents them from showing in the active list
     * of notifications.
     *
     * @param {[Integer]} notificationIds - The notification IDs to mark as seen
     */
    async function seen(notificationIds) {
        sendMessage(function() {
            // TODO: Seen message. `0` is pushed for illustrative purpose only.
            seenQueue.push(0);
        });
    }
    this.seen = seen;

    /**
     * Delete notifications.
     *
     * @param {[Integer]} notificationIds - the notification IDs to delete
     */
    async function _delete(notificationIds) {
        sendMessage(function() {
            // TODO: Delete messages. `0` is pushed for illustrative purpose only.
            deleteQueue.push(0);
        });
    }
    this.delete = _delete;
}
