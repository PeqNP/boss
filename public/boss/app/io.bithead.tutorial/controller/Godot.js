export function GodotController(id, app) {
    readOnly(this, "id", id);

    const self = this;

    let appId, controllerId;

    function receive(ev) {
        console.log(`It works! (${ev})`);
    }
    this.receive = receive;

    function configure(_appId, _controllerId) {
        appId = _appId;
        controllerId = _controllerId;

        console.log(`Parameters passed to GodotController appId (${appId}) controllerId (${controllerId})`);
    }
    this.configure = configure;

    function ready() {
        // Demonstrate sending a message to Godot app instance immediately
        // upon the Godot instance being loaded.
        console.log("Sending appId and controllerId to Godot...");
        self.send({"name": "Test application", "data": {"appId": appId, "controllerId": controllerId}});
    }
    this.ready = ready;
}
