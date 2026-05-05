# Software Development Process

This document descibes a high-level overview of the software development process.

## Software layers

Below describe the layers of the BOSS system from top to bottom, respectively. Each layer has a specific responsibility. These are used as short-hand to describe specific processes applied to each layer.

- Tacticle surface - The UI/UX the user interacts with. A `UIController` (`ui-window` or `ui-modal`)
- BOSS OS - Middleware that supports the drawing and interacting with the tactile surface.
  - This logic is almost exclusively written by a human. Therefore, before making changes in this layer, ask the developer if the changes can be made. It may be that there is an existing API that can satisfy the request.
- BOSS Public API - The public API that the BOSS OS intergates with. This can be provided by either Python or Swift. This source for this is `server/web` (Swift) and `private` (Python). This is a thin layer that routes requests to the BOSS Private API.
- BOSS Private API - The private API layer implements the business rules, saves records to the database, etc. The source for this is `server/bosslib` and only implemented in Swift. Public BOSS APIs, implemented in Python, may have their own private API to implement business rules and manage the storage of records, etc. Their source will live in the respective application folders. e.g. `private/app/<bundle_id>` You may also refer to `private/app/io.bithead.wordy` for examples on how private Python APIs may be implemented.

## When to write tests

Tests are usually reserved only for BOSS private APIs. This is because most of the business rules are encoded in this layer. Some Python APIs have their own tests (refer to `private/tests/test_wordy.py` for an example). A good rule of thumb, as to when tests, is how many behaviors can be exhibited for a given action. For example, imagine you are saving a record, and the name is required. When the backend tests the name it checks for the correct data type, `null`, an empty string, size limitation, unique constraints, and/or whether the record is saved successfully, etc. The server may respond with three or more behaviors depending on the input. A good rule of thumb is to require a test when three or more behaviors may be exhibited for an input. If it's a simple `if...then`, it doesn't necessarily need an input. If you're unsure, ask before continuing.

Typically tests are always written for critical BOSS sub systems, such as authentication, notifications, and/or helper functions that many consumers depend on.

## Test first approach

When tests are determined, write the tests first. Using the above example, there should be at least four tests, if saving a model where the `name` must have a value (not `null` or empty string), has size/unique constraints, and the record being saved correctly.

The tests encode the business requirements, in a human-readable way, and should be a point of reference on how to use the API under different contexts. Therefore, I use Gherkin to describe (`describe`) the context, state differences (`when`), and the expected behavior (`it`).

Only write the corresponding logic to satisfy a test. If a test says to return a value of `1`, for a given context, even though the _intent_ is to save a record in the database, only return the value of `1` with no logic saving the record to the database. Only when the test requires you to query for a record, given an ID, should the logic be written to save, and retrieve, the record to/from the database. Tests should guide the development of the backend in order to reduce the amount of logic to implement business requirements.

> Note: There have been innumerable instances where I discovered I did not need a dependency, or additional logic, to satisfy a business requirement.

## Development process

Always begin development from the top-most layer you are working on, to the bottom. The top-most layer is what defines what is required. This ensures only the necessary logic is implemented in the respective bottom layers. Too often the bottom layers guess what the user needs in the present _and_ the future.

For example, let's imagine we're adding a new "Friend" feature where users can invite other users to be friends. The following steps should be applied:

- Define UI/UX: Create the tacticle surfaces the user will interact with to add, remove, and/or ignore friends.
  - Before writing network requests, stub locations that will eventually make network calls for fast iteration. In places where these dummy structures are created, make a note to yourself that the data will eventually be integrated by backend API call. I'll usually add a TODO with a possible API request that will satisfy the request e.g. `TODO: Make request to: <path_to_network_request>`.
- Implement necessary BOSS features: Write any supporting BOSS OS logic necessary to support this new feature -- if they don't already exist. As stated earlier, ask the developer before making changes in this layer.
- Implement public API thin wrapper routes: Write the BOSS Public APIs necessary to implement the respective requests. Based on the TODOs, create the necessary backend routes. At this point you can remove the stubbed data from within the client and move them to the backend as a static structure. This has the effect of (mostly) finalizing the client integration and positioning the backend work to begin immediately.
- Write tests: Using the public API network requests as a reference, work exclusively in the BOSS private API to write tests to satisify the respective requests. This is where the business requirements will be encoded.
- Write implementation: Write the logic to implement the behavior requested by the tests.

Once a step is complete, stop, wait for confirmation, and then move on to the next step.

