
class GodotCommand {
    name;
    data;

    constructor(name, data) {
        this.name = name;
        this.data = data;
    }
}

class GodotEvent {
    name;
    data;

    constructor(name, data) {
        this.name = name;
        this.data = data;
    }
}

/**
 * Protocol definition for BOSS controllers to communicate with a Godot app
 * instance.
 *
 * @param {string} id - Controller ID name e.g. `Godot_0`
 */
function GodotController(id) {
    this.id = id;

    // Allows access to `this` safely within any context. Primarily used to call
    // `this.send`, the function used to send commands to the Godot instance.
    const self = this;

    /**
     * Send command to the Godot instance. This function is set by Godot.
     *
     * @param {GodotCommand} cmd - Command to send to Godot instance
     */
    function send(cmd) {
        console.warn("Godot did not register send function");
        console.log(cmd);
    }
    this.send = send;

    /**
     * Recieve an event from the Godot instance.
     *
     * @param {GodotEvent} ev - Event sent from Godot.
     */
    function receive(ev) {
        console.warn("Calling unimplemented GodotController.receive function");
        console.log(ev);
    }
    this.receive = receive;

    /**
     * Configure the controller with custom args.
     *
     * The `io.bithead.boss/controller/Godot` controller passes through the
     * arguments passed to it, to this instance.
     */
    function configure(...args) {
        console.warn("Calling unimplemented GodotController.configure function");
    }
    this.configure = configure;

    /**
     * Called after Godot loads and connects to the delegate. It is possible
     * to communicate with the Godot instance at this point.
     */
    function ready() {
        // It's possible to call `self.send(...)` at this point.
    }
    this.ready = ready;
}
