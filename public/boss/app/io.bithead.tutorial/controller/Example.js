export default function Example(view, app) {
    let msg = "Controller was not configured.";

    function embeddedConuroller(name) {
        const controllerView = view.querySelector(`.ui-controller[name="${name}"]`);
        if (isEmpty(controllerView)) {
            throw new Error(`Embedded controller (${name}) was not found.`);
        }
        return os.ui.controller[controllerView.id];
    }

    function showImage(url) {
        os.ui.showImageViewer([url]);
    }
    this.showImage = showImage;

    function close() {
        view.ui.close();
    }
    this.close = close;

    function _delete() {
        os.ui.showDelete(
            "Are you sure you want to delete this model?", null,
            async function () {
                os.ui.showInfo("Model deleted.");
            }
        );
    }
    this.delete = _delete;

    function save() {
        console.log("Saved model");
    }
    this.save = save;

    function cancel() {
        view.ui.close();
    }
    this.cancel = cancel;

    function configure(_msg) {
        msg = _msg;
    }
    this.configure = configure;

    function viewDidLoad() {
        view.ui.pByClassName("test-message").innerHTML = msg;
        view.ui.p("test-message").innerHTML = msg;

        function updateSliderValue(option) {
            let div = view.ui.element("slider-value");
            div.textContent = option.value;
        }

        let slider = view.ui.select("my-slider-3");
        slider.ui.delegate = {
            didSelectOption: updateSliderValue
        };
        updateSliderValue(slider.ui.selectedOption());

        let listBox = view.ui.select("option-5").ui;
        listBox.delegate = {
            didChangePositionOfListBoxOptions: async function(options, newPosition) {
                return Promise.resolve("Success")
                    .then(data => {
                        console.log(`Promise data (${data})`);
                        listBox.deselectAllOptions();
                        return data;
                    });
            }
        };

        let searchMenu = view.ui.select("search-1").ui;
        searchMenu.delegate = {
            didFocusSearchMenu: async function(initialize) {
                if (initialize) {
                    return Promise.resolve([
                        new UIChoice(1, "Harry Potter"),
                        new UIChoice(2, "Tasty Treat"),
                        new UIChoice(3, "Crash Adams")
                    ]);
                }
                return null;
            },
            didSearchForTerm: async function(term) {
                return Promise.resolve([
                    new UIChoice(1, `${term} Potter`),
                    new UIChoice(2, `${term} Treat`),
                    new UIChoice(3, `${term} Adams`)
                ]);
            },
            didSelectOption: async function(opt) {
                console.log("Call server to save selected option.");
                console.log(opt);
            },
            didDeselectOption: async function() {
                console.log("Call server to clear section.");
            }
        };

        let tokenMenu = view.ui.select("token-1").ui;
        tokenMenu.delegate = {
            didFocusTokenMenu: async function(initialize) {
                return Promise.resolve([
                    new UIChoice(1, "Fei Fong Wong"),
                    new UIChoice(2, "Elly Houten"),
                    new UIChoice(3, "Citan Uzuki")
                ]);
            },
            didSearchForTerm: async function(term) {
                return Promise.resolve([
                    new UIChoice(1, `${term} Wong`),
                    new UIChoice(2, `${term} Houten`),
                    new UIChoice(3, `${term} Uzuki`)
                ]);
            },
            didAddToken: async function(opt) {
                console.log("Call server to save option.");
                console.log(opt);
                return Promise.resolve(true);
            },
            didRemoveToken: async function(opt) {
                console.log("Call server to remove option.");
                console.log(opt);
                return Promise.resolve(true);
            }
        };

        Promise.all([
            os.network.stylesheet(`${app.resourcePath}/example.css`),
            os.network.javascript(`${app.resourcePath}/example.js`)
        ])
            .then(() => {
                os.network.javascript(`${app.resourcePath}/example2.js`)
                    .then(async function() {
                        runExample2();
                    });
            });

        const theme = embeddedController("theme");
        theme.configure({fill: "blue", stroke: "orange"});
        theme.delegate = {
            didSelectTheme: function (theme) {
                console.log(theme);
            }
        };
    }
    this.viewDidLoad = viewDidLoad;

    function viewDidAppear() {
        view.ui.input("email").focus();
    }
    this.viewDidAppear = viewDidAppear;

    async function showInfo(msg) {
        await os.ui.showInfo(msg);
    }
    this.showInfo = showInfo;

    async function showError(msg) {
        await os.ui.showError(msg);
    }
    this.showError = showError;

    async function showColorPicker() {
        await os.ui.showColorPicker(function(color) {
            view.ui.div("color-swatch").style.backgroundColor = color;
        });
    }
    this.showColorPicker = showColorPicker;

    this.didHitEnter = save;

    this.didHitKey = function (key) {
        console.log(`Hit key (${key})`);
    };

    this.events = {
        "io.bithead.boss.debug": async function (ev) {
            console.log(`Application (${ev})`);
        }
    };
}
