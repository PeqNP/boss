export function GodotController(id) {
    readOnly(this, "id", id);

    function receive(ev) {
        console.log(`It works! (${ev})`);
    }
    this.receive = receive;

    function ready() {
    }
    this.ready = ready;
}
