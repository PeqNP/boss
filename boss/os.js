/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * Bithead OS aka BOSS
 *
 * Provides system-level features
 * - Access to UI API
 * - Access to Network API
 * - Signing in and out
 * - Clock
 */
function OS() {

    // Displayed in OS menu, settings, etc.
    this.username = "";

    this.network = new Network(this);
    this.ui = new UI(this);

    function init() {
        this.ui.init();
        startClock();
    }
    this.init = init;

    /**
     * Log user out of system.
     */
    function logOut() {
        os.ui.showDeleteModal("Are you sure you want to log out?", null, function() {
            os.network.redirect('/account/signout');
        });
    }
    this.logOut = logOut;

    function signIn(username) {
        this.username = username;

        // Update the OS bar
        var option = document.getElementById("log-out-of-system");
        if (option === null) {
            console.warn("Signed in but not showing OS bar");
            return;
        }
        option.innerHTML = "Log out " + username + "...";
    }

    this.signIn = signIn;

    /**
     * Get the current time formatted in DDD MMM dd HH:MM AA.
     *
     * e.g. Fri Nov 15 9:24 PM
     */
    function getCurrentFormattedTime() {
        const date = new Date();

        // Get parts of the date
        const day = date.toLocaleString('default', { weekday: 'short' });  // Short day name
        const month = date.toLocaleString('default', { month: 'short' });  // Short month name
        const dayOfMonth = date.getDate();
        const hours = date.getHours();
        const minutes = date.getMinutes();

        // Determine AM or PM
        const ampm = hours >= 12 ? 'PM' : 'AM';

        // Convert to 12-hour format
        let formattedHours = hours % 12 || 12;

        // 9:23 PM
        const time = `${formattedHours}:${minutes < 10 ? '0' + minutes : minutes} ${ampm}`;

        // e.g. Fri Nov 15 9:23 PM
        return `${day} ${month} ${dayOfMonth} ${time}`;
    }

    /**
     * Update the clocks time.
     */
    function updateClock() {
        var time = getCurrentFormattedTime(); // "Fri Nov 15 10:23 AM";
        var option = document.getElementById("clock");
        if (option === null) {
            console.warn("Attemping to update clock when OS bar is not visible.");
            return;
        }
        option.innerHTML = time;
    }

    /**
     * Start updating clock.
     */
    function startClock() {
        updateClock();
        setInterval(updateClock, 2000);
    }

    /**
     * Copy string `item` to clipboard.
     *
     * - Parameter button: The button invoking the copy action
     * - Parameter item: The string item to copy to clipboard.
     */
    function copyToClipboard(button, item) {
        navigator.clipboard.writeText(item);
        let originalHTML = button.innerHTML;
        button.innerHTML = "Copied!";
        setInterval(function() {
            button.innerHTML = originalHTML;
        }, 2000);
    }
    this.copyToClipboard = copyToClipboard;
}

/**
 * Provides network functions.
 */
function Network(os) {

    /**
     * Redirect to a page using a GET request.
     */
    function redirect(url, redirectTo) {
        // TODO: If `redirectTo` provided, URL encode the value and add it as a GET parameter to the URL
        window.location = url;
    }

    // @deprecated - Use `this.redirect`
    this.request = redirect;
    this.redirect = redirect;

    /**
     * Make a POST request with an object that can be converted into JSON.
     *
     * Displays an error model if an error occurred.
     * Returns a JSON object.
     */
    function json(url, body, fn) {
        if (body === null || body.length < 1) {
            body = '{}';
        }
        else {
            body = JSON.stringify(body);
        }
        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: body
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is considered to be in error
                if (data.error !== undefined) {
                    throw new Error(data.error.message);
                }
                fn(data);
            })
            .catch(error => {
                os.ui.showErrorModal(error.message);
            });
    }

    // @deprecated - Use `post` instead
    this.json = json;
    this.post = json;

    function upload(url, file, fn) {
        let formData = new FormData();
        formData.append("file", file);

        fetch(url, {
            method: "POST",
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is considered to be in error
                if (data.error !== undefined) {
                    throw new Error(data.error.message);
                }
                fn(data);
            })
            .catch(error => {
                os.ui.showErrorModal(error.message);
            });
    }
    this.upload = upload;

    function __delete(url, fn) {
        fetch(url, {
            method: "DELETE"
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Request unexpectedly failed");
                }
                return response.json();
            })
            .then(data => {
                // If there is an `error` struct, the response is considered to be in error
                if (data.error !== undefined) {
                    throw new Error(data.error.message);
                }
                fn(data);
            })
            .catch(error => {
                os.ui.showErrorModal(error.message);
            });
    }

    /**
     * Make a DELETE request.
     *
     * This expects response to be JSON.
     *
     * Displays an error model if an error occurred.
     * @returns JSON object.
     */
    function _delete(url, msg, fn) {
        if (msg === null) {
            __delete(url, fn);
            return;
        }
        os.ui.showDeleteModal(msg, null, fn);
    }
    this.delete = _delete;

    function stylesheet(href) {
        return new Promise((resolve, reject) => {
            let link = document.createElement('link');
            link.rel = 'stylesheet';
            link.type = 'text/css';
            link.onload = resolve;
            link.onerror = reject;
            link.href = '/codemirror/lib/codemirror.css';
            document.head.appendChild(link);
        });
    }
    this.stylesheet = stylesheet;

    function javascript(href) {
        return new Promise((resolve, reject) => {
            let script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = href;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    this.javascript = javascript;
}