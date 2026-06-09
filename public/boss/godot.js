
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
 */
function GodotController(id) {
    this.id = id;

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
}
