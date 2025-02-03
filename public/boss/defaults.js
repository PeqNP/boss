/**
 * Provides user default registry.
 *
 * A "default registry" is a key/value store designed to store application
 * specific values per user.
 *
 * Imagine that you wish to show a modal to a user, but only if the app
 * is launched for the first time. This can be achieved using defaults.
 *
 * Example
 * ```javascript
 * // Get Defaults key for app-specific `isFirstLaunch` variable
 * let seen = os.defaults.get("hasSeenFirstLaunchModal");
 *
 * // NOTE: if the key is not set, `null` is returned, which makes
 * // this value empty.
 * if (isEmpty(seen)) {
 *   // Show a preview modal...
 *
 *   // Set the value
 *   os.defaults.set("hasSeenFirstLaunchModal", true);
 * }
 * ```
 */
function Defaults(os) {
    /**
     * Get user default for `key`.
     *
     * @param {string} key - User default key to retrieve
     * @returns `null` if key is not set
     */
    function get(key) {
        console.log(os.user);
        return null;
    }
    this.get = get;

    /**
     * Set user default.
     *
     * @param {string} key - User default key to set
     * @param {mixed} value - Value to set
     */
    function set(key, value) {
        console.log(os.user);
    }
    this.set = set;
}
