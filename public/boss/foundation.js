/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 * Wraps a value or an error as a result type.
 *
 * @param {*} value - The result value, or an `Error` instance
 */
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
 * Check if a value is a function.
 *
 * @param {*} fn - Value to test
 * @returns {boolean} `true` if `fn` is a function
 */
function isFunction(fn) {
    return typeof fn === "function";
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
 * Check if value is numeric.
 *
 * @param {*} value - value to test if number
 * @returns {bool} `true` if the type of `value` is a number.
 */
function isNumeric(value) {
    if (isEmpty(value)) {
        return false;
    }
    const num = Number(value);
    return !isNaN(num) && isFinite(num);
}

/**
 * Check if value is an integer (whole number).
 *
 * This is designed to ensure values do not contain a decimal. Therefore, even
 * if a number is whole (e.g. `40.0`), it will not be considered an integer.
 *
 * @param {*} value - value to test if whole number
 * @returns {bool} `true` if the type of `value` is a whole number.
 */
function isInteger(value) {
    if (isEmpty(value)) {
        return false;
    }

    const str = String(value).trim();
    if (str.includes(".")) {
        return false
    }

    const num = Number(value);
    // Must be a valid finite number and an integer
    return !isNaN(num) && isFinite(num) && Number.isInteger(num);
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
 * Trims a string value and throws if empty.
 *
 * @param {string|null} value - Value to trim
 * @returns {string} trimmed value
 * @throws if value is empty or not a string
 */
function trimmed(value) {
    if (!isString(value)) {
        throw new Error("Value is not string");
    }
    value = value.trim();
    if (isEmpty(value)) {
        throw new Error("String value is empty");
    }
    return value;
}

/**
 * Check if a value is an array.
 *
 * @param {*} value - Value to test
 * @returns {boolean} `true` if `value` is an array
 */
function isArray(value) {
    if (Array.isArray(value)) {
        return true;
    }
    // I'm not sure if this is necessary
    else if (typeof value == 'object' && value['length'] !== undefined) {
        return true;
    }
    return false;
}

/**
 * Test if a value is a boolean.
 *
 * Examples
 * ```javascript
 * console.log(isBoolean(true));        // true
 * console.log(isBoolean(false));       // true
 * console.log(isBoolean(0));           // false
 * console.log(isBoolean("true"));      // false
 * console.log(isBoolean(null));        // false
 * console.log(isBoolean(undefined));   // false
 * ```
 *
 * @param {*} value - Value to test
 * @return {boolean}
 */
function isBoolean(value) {
    return typeof value === 'boolean';
}

/**
 * Returns `true` if the value is `null`, `undefined`, empty string, empty
 * dictionary, or an empty array.
 *
 * @param {*} value - The value to check
 * @param {string} [error] - Optional message to log to console if value is empty
 * @return {boolean} - True if the value is empty
 */
function isEmpty(value, error) {
    // NOTE: Order matters here. The final comparison on arrays should not
    // inadvertently return true for strings that contain whitespace only.
    if (value === null || value === undefined || Number.isNaN(value)) {
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
    else if (isArray(value) && value.length === 0) {
        if (error !== null && error !== undefined) {
            console.log(error);
        }
        return true;
    }
    return false;
}

/**
 * Return the value if it is not empty, or return the default value.
 *
 * @param {*} value - The value to coalesce
 * @param {*} defaultValue - The value to return if `value` is empty (uses `isEmpty`)
 * @returns {*}
 */
function coalesce(value, defaultValue) {
    return isEmpty(value) ? defaultValue : value;
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
 * Define a read-only property on an object.
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
                proto[method] = function(...args) {
                    return value[method](...args);
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
 * @param {string} keyPath - Dot-separated path identifying a key in a nested dictionary
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

/**
 * Debounce a signal.
 *
 * @param {function} fn - Function to call when `wait` time reached
 * @param {int} wait - Amount of time to wait
 * @returns {function} Function to run for debounce operation
 */
function debounce(fn, wait) {
    let timeout;
    const debounced = function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), wait);
    };
    // Add cancel method
    debounced.cancel = function () {
        clearTimeout(timeout);
    };
    return debounced;
}

/**
 * Prevent function from being called more than once at a time, while
 * it is currently being processed.
 *
 * This will call the function, only if the function is not currently
 * active.
 *
 * This requires the function being passed in to be an async function.
 *
 * @param {Function} fn - The function to call
 */
function mutex(fn) {
    let active = false;
    return async function() {
        if (active) {
            console.log("mutex: prevented call");
            return;
        }
        active = true;
        try {
            await fn();
        }
        catch (error) {
            console.error(`mutex: error (${error})`);
        }
        finally {
            active = false;
        }
    }
}

/**
 * Creates a simple enum-like type modeled after Swift enums.
 *
 * The definition object maps case names to primitive values (used for
 * matching in primitive form). When initialized with a primitive, the
 * value is compared against the definition values; the matching case
 * stores that primitive. When initialized with `{ name, value }`, the
 * `name` selects the case and `value` is stored directly.
 *
 * An optional second parameter provides a default case name used when
 * no match is found. If omitted and no match occurs, an error is thrown.
 *
 * Each returned instance has a readOnly property for every case (the
 * active case holds the value; others are `null`) plus a `.case` string
 * indicating the active case name.
 *
 * NOTE: This is capitalized because `enum` is a reserved future keyword.
 *
 * @param {Object} cases - Mapping of case name → primitive value
 * @param {string} [defaultCase] - Optional default case name
 * @returns {Function} Enum initializer
 */
function Enum(cases, defaultCase) {
    if ("case" in cases) {
        throw new Error("Enum definition cannot contain a case named 'case'");
    }
    const caseEntries = Object.entries(cases);

    return function init(arg) {
        let activeName = null;
        let activeValue = null;

        if (arg == null) {
            if (defaultCase != null) {
                activeName = defaultCase;
                activeValue = cases[defaultCase];
            } else {
                throw new Error("Enum value is required");
            }
        } else if (typeof arg === "object" && arg !== null && "name" in arg) {
            activeName = arg.name;
            if (!(activeName in cases)) {
                if (defaultCase != null) {
                    activeName = defaultCase;
                    activeValue = cases[defaultCase];
                } else {
                    throw new Error(`Unknown enum case: ${activeName}`);
                }
            } else {
                activeValue = arg.value;
            }
        } else {
            const match = caseEntries.find(([, v]) => v === arg);
            if (match) {
                activeName = match[0];
                activeValue = arg;
            } else if (defaultCase != null) {
                activeName = defaultCase;
                activeValue = cases[defaultCase];
            } else {
                throw new Error(`Unknown enum value: ${arg}`);
            }
        }

        const result = {};
        for (const [name] of caseEntries) {
            readOnly(result, name, name === activeName ? activeValue : null);
        }
        readOnly(result, "case", activeName);
        return result;
    };
}
