
class GodotCommand {
  name;
  data;

  constructor(name, data) {
    this.name = name;
    this.data = data;
  }
}

function GodotManager(delegate) {

    /**
     * Receive a ConnectionManager.swift:Fragment.NotificationResponse object from Godot and
     * dispatch it through the `NotificationManager`.
     *
     * @param {Object} ev - Refer to ConnectionManager.swift:Fragment.NotificationResponse
     */
    async function receive(ev) {
        os.notification.notify(ev);
    }
    this.receive = receive;

    /**
     * Send a `GodotCommand` to the Godot runtime.
     *
     * Requires Godot to have registered `window.godot_command_handler` via
     * JavaScriptBridge before this is called.
     *
     * @param {GodotCommand} cmd - Command to send to Godot
     */
    function send(cmd) {
        const handler = window.godot_command_handler;
        if (!handler) {
            console.warn("godot_send: Godot command handler is not registered");
            return;
        }
        handler(cmd);
    }
    this.send = send;
}

/**
 * Global bridge to receive messages from Godot.
 *
 * @param {Object} ev - Refer to ConnectionManager.swift:Fragment.NotificationResponse
 */
async function godot_receive(ev) {
    await os.godot.receive(ev);
}
