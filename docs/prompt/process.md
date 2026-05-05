# BOSS Development Process

## System Layers

From top (user-facing) to bottom (data):

| Layer | Responsibility | Source |
|---|---|---|
| **Tactile surface** | UI/UX the user interacts with (`UIController`) | `public/boss/app/<bundle_id>/` |
| **BOSS OS** | Middleware for drawing and interaction. Almost exclusively written by humans. **Ask the developer before modifying this layer** — an existing API likely already covers the need. | `public/boss/` |
| **Public API** | Thin routing layer. Routes requests to the Private API. | `server/web/` (Swift), `private/` (Python) |
| **Private API** | Business rules, database access. Swift: `server/bosslib/`. Python: `private/app/<bundle_id>/`. | `server/bosslib/`, `private/app/<bundle_id>/` |

## When to Write Tests

Tests are written for the **Private APIs only** — that is where business rules live.

> **Note:** UI integration tests, and rules, will be added in the future.

Write a test when **three or more behaviors** can be exhibited for a given input (e.g., null check, empty string, size limit, uniqueness, success path). For a simple `if/then`, a test is not required. When unsure, ask before proceeding.

Always write tests for critical subsystems: authentication, notifications, shared helper functions.

## Test-First Approach

When tests are warranted, write them **before** the implementation.

- Tests encode business requirements in human-readable form using Gherkin style: `describe` (context), `when` (state), `it` (expected behavior).
- Only write implementation logic sufficient to satisfy the current test. Do not anticipate future needs.
- If a test only requires returning a value of `1`, return `1` — do not write database logic until a test requires a database query.

## Development Order

Always develop **top to bottom** — the UI defines what the backend actually needs. This prevents over-engineering lower layers.

### Steps (complete each step fully before moving to the next; stop and wait for confirmation between steps)

1. **Define UI/UX** — Create the tactile surfaces (windows, modals, forms). Stub all network calls with static data and add a `TODO` comment indicating the eventual API path, e.g.:
   ```javascript
   // TODO: GET /friends
   const friends = [{ id: 1, name: "Alice" }];
   ```

2. **Implement BOSS OS features** — Only if new OS-level support is needed and approved by the developer.

3. **Implement Public API routes** — Based on the TODOs from step 1, create the backend routes. Replace stubbed client data with real API calls. This finalizes the client integration.

4. **Write tests** — Working only in the Private API, write tests that encode the business requirements for each route.

5. **Write implementation** — Write logic to satisfy the tests, nothing more.


