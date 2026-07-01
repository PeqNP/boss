export default function(app) {
    let id;
    property(this, "id",
        function () { return id; },
        function (_id) { id = _id; }
    );

    const self = this;

    let factoryId;

    function configure(_factoryId) {
        factoryId = _factoryId;
    }
    this.configure = configure;

    async function reloadFactoryFloor() {
        self.send({ name: "factory-floor", data: {} });
    }

    /**
     * Receive an event from the Godot instance.
     *
     * Supported events:
     *   open-window: Open a BOSS controller window.
     *     data.controller  {string} - Controller name to load.
     *     data.parameters  {Array}  - Arguments forwarded to the controller's configure().
     *
     * @param {GodotEvent} ev
     */
    function ready() {
        self.send({ name: "configure", data: { factoryId: String(factoryId), baseUrl: window.location.origin } });
    }
    this.ready = ready;

    /**
     * Receive an event from the Godot instance.
     *
     * Supported events:
     *   open-window: Open a BOSS controller window.
     *     data.controller  {string} - Controller name to load.
     *     data.parameters  {Array}  - Arguments forwarded to the controller's configure().
     *
     * @param {GodotEvent} ev
     */
    async function receive(ev) {
        if (ev.name === "open-window") {
            const controllerName = ev.data.controller;
            const parameters = Array.from(ev.data.parameters);
            const win = await app.loadController(controllerName);
            win.ui.show(function(ctrl) {
                ctrl.configure(...parameters);
                ctrl.delegate = buildDelegate(controllerName);
            });
            return;
        }
        console.warn(`FactoryFloor GodotController: unknown event '${ev.name}'`);
    }
    this.receive = receive;

    /**
     * Build a controller delegate that triggers a factory floor reload.
     * Different controllers signal completion via different method names.
     * Controllers not listed here fall back to didCreateModel.
     *
     * @param {string} controllerName
     * @returns {object}
     */
    function buildDelegate(controllerName) {
        const methodMap = {
            CreateWorkUnit: ["didSaveWorkUnit"],
            IntakeQueue: ["didSaveIntakeQueue", "didDeleteIntakeQueue"],
            Station: ["didSaveStation", "didDeleteStation"],
            WorkUnit: ["didSaveWorkUnit", "didDeleteWorkUnit"]
        };
        const methods = methodMap[controllerName] || ["didCreateModel"];
        const delegate = {};
        for (const method of methods) {
            delegate[method] = reloadFactoryFloor;
        }
        return delegate;
    }

    this.events = {
        "io.bithead.lean.factory-floor": function (factory) {
            self.send({ name: "factory-floor", data: factory });
        }
    };
}
