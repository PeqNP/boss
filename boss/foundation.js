/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

function Result(value) {
    if (value instanceof Error) {
        this.ok = false;
        this.error = value;
    }
    else {
        this.ok = true;
        this.value = value;
    }
}

/**
 * Check if function is async.
 *
 * @returns {bool} `true` if async function
 */
function isAsyncFunction(fn) {
    return fn?.constructor.name === "AsyncFunction";
}

/**
 * Check if value is string.
 *
 * @param {mixed} value - value to test if string
 * @returns {bool} `true` if the type of `value` is a string.
 */
function isString(value) {
    return typeof value === 'string';
}

/**
 * Check if value is a dictionary.
 *
 * @param {mixed} value - value to test if dict
 * @returns {bool} `true` if value is a dictionary
 */
function isDictionary(value) {
    return Object.prototype.toString.call(value) === '[object Object]';
}

/**
 * Returns `true` if the value is `null` or `undefined`.
 *
 * @param {*} value - The value to check
 * @return {boolean} - True if the value is `null` or `undefined`
 */
function isEmpty(value, error) {
    // NOTE: Order matters here. The final comparison on arrays should not
    // inadvertently return true for strings that contain whitespace only.
    if (value === null || value === undefined) {
        if (error !== null && error !== undefined) {
            console.log(error);
        }
        return true;
    }
    else if (isString(value) && value.trim() === "") {
        if (error !== null && error !== undefined) {
            console.log(error);
        }
        return true;
    }
    else if (isDictionary(value) && Object.keys(value).length === 0) {
        if (error !== null && error !== undefined) {
            console.log(error);
        }
        return true;
    }
    else if (typeof value == 'object' && value['length'] !== undefined && value.length === 0) {
        return true;
    }
    return false;
}

/**
 * Generate a UUID.
 *
 * @returns {string} - UUID
 */
function generateUUID() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}

/**
 * Define a read-only function on an object.
 *
 * @param {object} obj - Object that will contain the property to be read-only
 * @param {string} name - Name of property that will be read-only
 * @param {any} value - The value of the read-only property
 */
function readOnly(obj, name, value) {
    Object.defineProperty(obj, name, {
        value: value,
        writable: false, // Do not allow property to be changed
        enumerable: true, // Allow it to be enumerated
        configurable: false // Do not allow property to be redefined
    });
}

/**
 * Define a property on an object.
 *
 * This is designed to encapsulate a local variable and expose it as
 * a computed property on `obj`.
 *
 * This was primarily designed to support delegation.
 *
 * @param {object} obj - Object to assign property
 * @param {string} name - Name of public property
 * @param {function} get - The getter function
 * @param {function} set - The setter function
 */
function property(obj, name, get, set) {
    Object.defineProperty(obj, name, {
        get: get,
        set: set,
        configurable: false,
        enumerable: true
    });
}

/**
 * Defines a delegate method.
 *
 * @param {string} name - Name of method
 * @param {bool} required - If `true`, enforces method to be implemented
 */
function DelegateMethod(name, required) {
    return {
        name: name,
        required: required
    }
}

/**
 * Provides protocol abstraction layer for a protocol's methods.
 *
 * NOTE: This is fully managed by `protocol` method.
 */
function Protocol() { }

/**
 * Define a set of methods that must exist on a delegate.
 *
 * Delegate methods may be a list of `string`s or `DelegateMethod`s. For
 * convenience, this will transform `string` methods into optional
 * `DelegateMethod`s.
 *
 * When an Object requests to be a delegate, they should NOT pass in
 * `this`. JavaScript scoping prevents this from working. Instead, a
 * new Object must be provided which implements only the methods defined
 * by the protocol.
 *
 * @param {string} name - Name of protocol
 * @param {string} obj - Object to assign public property to
 * @param {string} prop_name - Name of public property
 * @param {[DelegateMethod]} methods - Delegate methods.
 * @param {function?} init_fn - Called immediately upon setting the delegate
 * @returns Protocol
 * @throws if a required protocol method is not implemented
 */
function protocol(name, obj, prop_name, _methods, init_fn) {
    let methods = [];
    let methodNames = [];
    for (let i = 0; i < _methods.length; i++) {
        let method = _methods[i];
        if (typeof method === "string") {
            methods.push(DelegateMethod(method, false));
            methodNames.push(method);
        }
        else {
            methods.push(method);
            methodNames.push(method.name);
        }
    }

    // Instance of object implementing protocol
    let instance;
    let proto = new Protocol();

    property(
        obj, prop_name,
        function() {
            // FIXME: Is this even needed?
            return instance;
        },
        function(value) {
            // Wrap and validate implemented methods
            // implemented: [string]
            let implemented = Object.keys(value);
            for (let i = 0; i < implemented.length; i++) {
                let method = implemented[i];
                if (!methodNames.includes(method)) {
                    throw new Error(`Protocol (${name}) does not contain method (${method})`);
                }
                proto[method] = function(values) {
                    if (values === undefined) {
                        value[method]();
                    }
                    else if (values.length === undefined) {
                        value[method](values);
                    }
                    else {
                        value[method](...values); // Untested
                    }
                }
            }

            // Ensure required methods are implemented
            for (let i = 0; i < methods.length; i++) {
                let method = methods[i];
                if (method.required && !implemented.includes(method.name)) {
                    throw new Error(`Protocol (${name}) requires method (${method}) to be implemented`);
                }
            }
            instance = value;

            if (!isEmpty(init_fn)) {
                init_fn();
            }
        }
    );

    // Set default implementation of proto
    for (let i = 0; i < methods.length; i++) {
        let method = methods[i];
        if (!method.required) {
            proto[method.name] = function() { }
        }
    }

    return proto;
}

/**
 * Call function, if it exists.
 *
 * This is a convenience method. It was designed for delegate callbacks.
 *
 * @param {function} fn - Call fn, if it has been set
 */
function call(fn) {
    if (!isEmpty(fn)) {
        fn();
    }
}

/**
 * Generate an 8 character object ID that starts with a character.
 *
 * This is designed for generating IDs used for a window instance.
 *
 * @returns {int} Returns a unique object ID
 */
function makeObjectId() {
    const alphanumeric = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

    let id = "";
    for (let i = 0; i < 8; i++) {
        id += alphanumeric[Math.floor(Math.random() * alphanumeric.length)];
    }

    return id;
}

/**
 * Returns value for given key path in nested dictionary.
 *
 * Used in conjunction with `interpolate`.
 *
 * @param {object} obj - Dictionary
 * @param {string} path - String path that identfies key in nested dictionary
 */
function getValue(obj, keyPath) {
    if (typeof(keyPath) !== 'string') {
        console.warn(`Invalid key path (${keyPath}). Expected string.`);
        return null;
    }

    let path = keyPath.split('.')
    return path.reduce(function(x, y) {
        return x[y];
    }, obj);
}

/**
 * Interpolate tokens in string with values in object.
 *
 * ```
 * let person = {person: {name: 'Joe'}};
 * let name = 'My name is, ${person.name}.';
 * console.log(interpolate(name, person));
 * // prints 'My name is, Joe.'
 * ```
 *
 * @param {string} str - String that contains tokens to interpolate
 * @param {object} obj - Dictionary that contains token values
 * @returns {string}
 */
function interpolate(str, obj) {
    return str.replace(/\$\((.*?)\)/g, (x, g) => getValue(obj, g));
}

/**
 * Transforms `undefined` | `null` string value to an empty string.
 *
 * @param {string?} value - Possible string value
 * @returns empty string if `value` is empty.
 */
function emptyString(value) {
    if (isEmpty(value)) {
        return "";
    }
    return value;
}
