export default function Kiosk(view, app) {
    let businessId;

    function close() {
        view.ui.close();
    }
    this.close = close;

    function configure(_businessId) {
        businessId = _businessId;
    }
    this.configure = configure;

    function viewDidLoad() {
        if (isEmpty(businessId)) {
            return os.ui.showError("Kiosk must be configured.");
        }
    }
    this.viewDidLoad = viewDidLoad;
}
