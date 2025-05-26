
class SessionExpiredError extends Error {
  constructor(url) {
    super(`Must be signed in to access resource (${url})`);
    this.name = 'SessionExpiredError';
  }
}

class NetworkError extends Error {
  constructor() {
    super("Request unexpectedly failed");
    this.name = 'NetworkError';
  }
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
     * Make a GET request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {string} msg? - Show progress bar with message
     * @param {string} decoder - Response decoder. Supported: text | json. Default is `json`
     * @throws
     */
    async function get(url, decoder) {
        if (isEmpty(decoder)) {
            decoder = "json";
        }
        return fetch(url, {
            method: "GET",
            // FIXME: Required when loading controller files. Failing to do this
            // will prevent controller JSON files from being loaded when changes
            // are made, as the older cached version will be served. How these
            // files are served (using Etag) could be smarter as it has more to
            // do with the backend (probably) then the front-end.
            cache: "no-cache"
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (response.status == 401) {
                    throw new SessionExpiredError(url);
                }
                else if (!response.ok) {
                    try {
                        return reponse.json();
                    }
                    catch {
                        throw new NetworkError();
                    }
                }
                else if (decoder === "json") {
                    return response.json();
                }
                else {
                    return response.text();
                }
            })
            .then(data => {
                if (isEmpty(data)) {
                    return data;
                }

                // Typically the text decoder is only for HTML. With that
                // assumption, if the response looks like JSON it's because
                // there's an error.
                if (decoder === "text" && data.startsWith("{")) {
                    let obj = null;
                    try {
                        obj = JSON.parse(data);
                    }
                    catch (error) {
                        console.log("Attempting to decode JSON object that wasn't JSON.");
                    }

                    if (!isEmpty(obj?.error)) {
                        throw new Error(obj.error.message);
                    }
                }

                // If there is an `error`, or `detail`, the response is considered to be in error
                if (!isEmpty(data.detail)) {
                    throw new Error(data.detail);
                }
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: GET ${url}`);
                throw error;
            })
            .then(data => {
                return data;
            });
    }
    this.get = get;

    /**
     * Make a POST request with an object that can be converted into JSON.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {dict} body - Object to pass as JSON
     * @throws
     */
    async function json(url, body) {
        if (isEmpty(body) || body.length < 1) {
            body = '{}';
        }
        else {
            body = JSON.stringify(body);
        }

        return fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: body
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (response.status == 401) {
                    throw new SessionExpiredError(url);
                }
                else if (!response.ok) {
                    try {
                        return response.json();
                    }
                    catch {
                        throw new NetworkError();
                    }
                }
                return response.json();
            })
            .then(data => {
                if (isEmpty(data)) {
                    return data;
                }

                // If there is an `error`, or `detail`, the response is considered to be in error
                if (!isEmpty(data.detail)) {
                    throw new Error(data.detail);
                }
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: POST ${url}`);
                throw error;
            })
            .then(data => {
                return data;
            });
    }

    // @deprecated - Use `post` instead
    this.json = json;
    this.post = json;

    /**
     * Upload a file.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {File} file - File object to upload
     * @param {dict} body - Additional key/value pairs to send in request
     * @throws
     */
    async function upload(url, file, body) {
        let formData = new FormData();
        formData.append("file", file);

        if (!isEmpty(body)) {
            for (const key in body) {
                let value = body[key];
                formData.append(key, value);
            }
        }

        return fetch(url, {
            method: "POST",
            body: formData
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (response.status == 401) {
                    throw new SessionExpiredError(url);
                }
                else if (!response.ok) {
                    try {
                        return response.json();
                    }
                    catch {
                        throw new NetworkError();
                    }
                }
                return response.json();
            })
            .then(data => {
                if (isEmpty(data)) {
                    return data;
                }

                // If there is an `error`, or `detail`, the response is considered to be in error
                if (!isEmpty(data.detail)) {
                    throw new Error(data.detail);
                }
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure upload: POST ${url}`);
                throw error;
            })
            .then(data => {
                return data;
            });
    }
    this.upload = upload;

    async function __delete(url) {
        return fetch(url, {
            method: "DELETE"
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (response.status == 401) {
                    throw new SessionExpiredError(url);
                }
                else if (!response.ok) {
                    try {
                        return reponse.json();
                    }
                    catch {
                        throw new NetworkError();
                    }
                }
                return response.json();
            })
            .then(data => {
                if (isEmpty(data)) {
                    return data;
                }

                // If there is an `error`, or `detail`, the response is considered to be in error
                if (!isEmpty(data.detail)) {
                    throw new Error(data.detail);
                }
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: DELETE ${url}`);
                throw error;
            })
            .then(data => {
                return data;
            });
    }

    /**
     * Make a DELETE request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {string?} msg - Message to display before deleting
     * @param {function?} fn - Response function
     * @throws
     */
    async function _delete(url, msg, fn) {
        if (isEmpty(msg)) {
            let data = await __delete(url);
            if (!isEmpty(fn)) {
                fn(data);
            }
            return;
        }
        os.ui.showDeleteModal(msg, null, async function () {
            let data = await __delete(url);
            fn(data);
        });
    }
    this.delete = _delete;

    /**
     * Make PATCH request.
     *
     * Note: Displays error message if request failed.
     *
     * @param {string} url
     * @param {object} body - request object to send as JSON to `url`
     * @param {function} fn? - Response function
     * @param {string} msg? - Show progress bar with message
     * @throws
     */
    async function patch(url, body, msg) {
        if (body === null || body.length < 1) {
            body = '{}';
        }
        else {
            body = JSON.stringify(body);
        }

        return fetch(url, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json"
            },
            body: body
        })
            .then(response => {
                if (response.redirected) {
                    redirect(response.url);
                    return;
                }
                else if (response.status == 401) {
                    throw new SessionExpiredError(url);
                }
                else if (!response.ok) {
                    try {
                        return reponse.json();
                    }
                    catch {
                        throw new NetworkError();
                    }
                }
                return response.json();
            })
            .then(data => {
                if (isEmpty(data)) {
                    return data;
                }

                // If there is an `error`, or `detail`, the response is considered to be in error
                if (!isEmpty(data.detail)) {
                    throw new Error(data.detail);
                }
                if (!isEmpty(data.error)) {
                    throw new Error(data.error.message);
                }
                return data;
            })
            .catch(error => {
                console.log(`failure: PATCH ${url}`);
                throw error;
            })
            .then(data => {
                return data;
            });
    }
    this.patch = patch;

    /**
     * Dynamically load stylesheet.
     *
     * @param {string} href
     */
    async function stylesheet(href) {
        let styles = document.head.querySelectorAll("style");
        for (let i = 0; i < styles.length; i++) {
            let style = styles[i];
            if (style.data == href) {
                console.log(`link (${href}) already loaded`);
                return;
            }
        }

        return fetch(href, {
            cache: "no-cache"
        })
        .then(response => response.text())
        .then(css => {
            let style = document.createElement("style");
            style.textContent = css;
            style.data = href;
            document.head.appendChild(style);
        });
    }
    this.stylesheet = stylesheet;

    /**
     * Dynamically load javascript.
     */
    async function javascript(href) {
        let scripts = document.head.querySelectorAll("script");
        for (let i = 0; i < scripts.length; i++) {
            let script = scripts[i];
            if (script.src.endsWith(href)) {
                console.log(`script (${href}) already loaded`);
                return;
            }
        }

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
