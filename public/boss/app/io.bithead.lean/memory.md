# Session Memory

## Last updated: 2026-05-18

---

## Project: io.bithead.lean (Factory Floor UI)

### Key files
- **UI controller**: `public/boss/app/io.bithead.lean/controller/FactoryFloor.html`
- **CSS**: `public/boss/app/io.bithead.lean/graph.css`
- **App manifest**: `public/boss/app/io.bithead.lean/application.json`
- **Controllers dir**: `public/boss/app/io.bithead.lean/controller/`
- **Lean routes**: `server/web/Sources/App/Routes/Lean/LeanRoute.swift`
- **Lean forms**: `server/web/Sources/App/Routes/Lean/Lean+Forms.swift`
- **Lean fragments**: `server/web/Sources/App/Routes/Lean/Lean+Fragments.swift`
- **DB migration**: `server/bosslib/Sources/bosslib/Database/v1_3_0.swift`

---

## Lean fragment naming

- `LeanFragment.List.Xxx` — lightweight (`id` + `name`) structs used to populate `UIListBox` controls
  - e.g. `LeanFragment.List.Company`, `LeanFragment.List.Companies`
  - e.g. `LeanFragment.List.Factory`, `LeanFragment.List.Factories`
- `LeanFragment.Xxx` — full structs with all form fields, used for detail/edit windows
  - e.g. `LeanFragment.Company` (has `id`, `name`, `userName`)

---

## Model hierarchy

```
Company (1) → Factory (many) → FactoryFloor (1:1 with Factory)
```

- `FactoryFloor.configure(_factoryId)` receives a **factory ID** (not company ID)

---

## All controllers

| Controller | File | configure param | Notes |
|---|---|---|---|
| `Company` | `Company.html` | `(_companyId)` | Create or edit; `companyId` is null when creating |
| `Factories` | `Factories.html` | `(_companyId)` | Lists factories for a company |
| `Factory` | `Factory.html` | `(_companyId, _factoryId)` | Create or edit; `factoryId` is null when creating |
| `FactoryFloor` | `FactoryFloor.html` | `(_factoryId)` | singleton |
| `Home` | `Home.html` | none | singleton; lists companies |
| `WorkUnit` | `WorkUnit.html` | `(_intakeQueueId, _workUnitId?)` | |
| `WorkUnits` | `WorkUnits.html` | `(_intakeQueueId)` | |
| `IntakeQueue` | `IntakeQueue.html` | `(_intakeQueueId)` | |
| `OutputWorkUnits` | `OutputWorkUnits.html` | `(_outputId)` | |
| `Line` | `Line.html` | `(_lineId)` | |
| `Station` | `Station.html` | `(_stationId)` | |
| `StationNotificationEvent` | `StationNotificationEvent.html` | `(_stationId, _companyId, _triggerId)` | `triggerId` null when creating |
| `StationWorkspace` | `StationWorkspace.html` | `(_workUnitId)` | |
| `Inventory` | `Inventory.html` | `(_inventoryId)` | |

All registered in `application.json`.

---

## Navigation flow

```
Home (company list)
  → Add → Company (no configure)
  → Edit → Company (configure companyId)
  → Open → Factories (configure companyId)
              → Add → Factory (no configure)
              → Edit → Factory (configure factoryId)
              → Open → FactoryFloor (configure factoryId)
```

---

## Button wiring (FactoryFloor.html)

| Button | Opens | Configured with |
|---|---|---|
| Line > Edit | `Line` | `id` (line ID) |
| IntakeQueue > Add | `WorkUnit` | `queueDefinition.id` |
| IntakeQueue > Edit | `IntakeQueue` | `queueDefinition.id` |
| IntakeQueue > Work Units | `WorkUnits` | `queueDefinition.id` |
| Station > Edit | `Station` | `station.__stationDefinition.id` |
| Station work unit card (click/keydown) | `StationWorkspace` | `workUnit.id` |
| Output button | `OutputWorkUnits` | `id` (line ID) |
| Inventory > Edit | `Inventory` | `id` (inventory ID) |

---

## Reusing search/suggest routes

Do **not** create a new `suggested-*` or `find-*` route for a model when one already exists for the appropriate scope. Reuse the existing route and pass the required ID (e.g. `companyId`) through the controller's `configure` method.

Examples of existing routes to reuse:
- Operator search: `GET /lean/suggested-operator/:companyId` and `GET /lean/find-operator/:companyId?q=`
- Assignee operator search: `GET /lean/suggested-operators/:companyId` and `GET /lean/find-operators/:companyId?q=`
- Intake queue search: `GET /lean/suggested-intake-queue/:lineId` and `GET /lean/find-intake-queue/:lineId?q=`

If a controller needs operator search but only knows a `stationId`, add `companyId` to its parent fragment so it can be threaded through `configure`.

---

## All Lean routes

| Method | Path | Form/Response | Notes |
|---|---|---|---|
| GET | `/lean/companies` | → `LeanFragment.List.Companies` | |
| GET | `/lean/factories/:companyId` | → `LeanFragment.List.Factories` | path param |
| GET | `/lean/company/:companyId` | → `LeanFragment.Company` | |
| GET | `/lean/factory/:factoryId` | → `LeanFragment.Factory` | |
| GET | `/lean/inventory/:inventoryId` | → `LeanFragment.Inventory` | |
| GET | `/lean/line/:lineId` | → `LeanFragment.Line` | |
| GET | `/lean/suggested-intake-queue/:lineId` | → `[Fragment.Option]` | suggested intake queues for a line |
| GET | `/lean/find-intake-queue/:lineId?q=` | → `[Fragment.Option]` | search intake queues for a line |
| GET | `/lean/suggested-operators/:companyId` | → `[Fragment.Option]` | suggested operators for a company |
| GET | `/lean/find-operators/:companyId?q=` | → `[Fragment.Option]` | search operators for a company |
| POST | `/lean/company` | `LeanForm.CreateCompany` → `LeanFragment.List.Company` | create only |
| POST | `/lean/factory` | `LeanForm.CreateFactory` → `LeanFragment.List.Factory` | create only |
| POST | `/lean/line` | `LeanForm.CreateLine` → `LeanFragment.Line` | `factoryId`, `name` |
| POST | `/lean/inventory` | `LeanForm.CreateInventory` → `LeanFragment.Inventory` | `factoryId`, `name` |
| POST | `/lean/start-work-unit` | `LeanForm.StartWorkUnit` → `LeanFragment.StartWorkUnitResponse` | `id` — stub |
| POST | `/lean/update-station-name` | `LeanForm.UpdateStationName` → `Fragment.OK()` | `id, name` — stub |
| POST | `/lean/update-intake-queue-name` | `LeanForm.UpdateIntakeQueueName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-intake-queue-mix-ratio` | `LeanForm.UpdateIntakeQueueMixRatio` → `Fragment.OK()` | `id, mixRatio` |
| PUT | `/lean/company/:companyId` | `LeanForm.UpdateCompany` → `Fragment.OK()` | `name` |
| PUT | `/lean/factory/:factoryId` | `LeanForm.UpdateFactory` → `Fragment.OK()` | `name` |
| PATCH | `/lean/save-line-position` | `LeanForm.SaveLinePosition` → `Fragment.OK()` | `id, gridX, gridY` |
| PATCH | `/lean/save-inventory-position` | `LeanForm.SaveInventoryPosition` → `Fragment.OK()` | `id, gridX, gridY` |
| PATCH | `/lean/save-line-locked` | `LeanForm.SaveLineLocked` → `Fragment.OK()` | `id, locked` |
| PATCH | `/lean/save-line-focus` | `LeanForm.SaveLineFocus` → `Fragment.OK()` | `id, focused` |
| PATCH | `/lean/update-line-name` | `LeanForm.UpdateLineName` → `Fragment.OK()` | `id, name` |
| PATCH | `/lean/update-inventory-name` | `LeanForm.UpdateInventoryName` → `Fragment.OK()` | `id, name` |
| PUT | `/lean/work-unit/reporter/:workUnitId` | `LeanForm.UpdateWorkUnitReporter` → `Fragment.OK()` | `operatorId: Operator.ID?` — nil clears reporter |
| PUT | `/lean/work-unit/assignees/:workUnitId` | `LeanForm.UpdateWorkUnitAssignees` → `Fragment.OK()` | `operatorIds: [Operator.ID]` — full list, not delta |
| PUT | `/lean/work-unit/:workUnitId` | `LeanForm.UpdateWorkUnit` → `Fragment.OK()` | `name, eta` |
| DELETE | `/lean/company/:companyId` | → `Fragment.OK()` | |
| DELETE | `/lean/factory/:factoryId` | → `Fragment.OK()` | |
| GET | `/lean/station/:stationId/work-units` | → `LeanFragment.WorkUnits` | work units for a station |
| GET | `/lean/station/:stationId/notification-triggers` | → `[Fragment.Option]` | notification triggers for a station |
| GET | `/lean/station-notification-trigger/:triggerId` | → `LeanFragment.StationNotificationTrigger` | |
| POST | `/lean/station-notification-trigger` | `LeanForm.CreateStationNotificationTrigger` → `Fragment.OK()` | |
| PUT | `/lean/station-notification-trigger/:triggerId` | `LeanForm.UpdateStationNotificationTrigger` → `Fragment.OK()` | |
| DELETE | `/lean/station-notification-trigger/:triggerId` | → `Fragment.OK()` | |

Remaining stubs (have `// TODO:` in route body): `start-work-unit`, `update-station-name`, `GET/POST intake-queue/:id`, `GET/POST inventory/:inventoryId`, `GET/POST line/:lineId`, `GET/POST station/:stationId`, all `work-unit` PUT routes, `GET work-unit/:workUnitId`.

---

## LeanFragment types

```swift
Company, Companies, WorkUnit, StartWorkUnitResponse, Factory, Factories
// Note: bare Line, Inventory, Station structs were removed — use Fragment.Option for {id,name} responses
```

## LeanAPI methods (bosslib)

| Method | Signature | Notes |
|---|---|---|
| `companies` | `(user:)` | Returns `[Company]` |
| `createCompany` | `(user:name:)` | |
| `company` | `(user:id:)` | Single record fetch |
| `updateCompany` | `(user:id:name:)` | Returns `Void` |
| `deleteCompany` | `(user:id:)` | Returns `Void` |
| `factories` | `(companyId:)` | Returns `[Factory]` |
| `createFactory` | `(user:companyId:name:)` | |
| `factory` | `(user:id:)` | Single record fetch |
| `updateFactory` | `(user:id:name:)` | Returns `Void` |
| `deleteFactory` | `(user:id:)` | Returns `Void` |
| `createLine` | `(user:factoryId:name:)` | Creates sibling `Hopper` |
| `line` | `(user:id:)` | Returns partial model: name + viewState; intakeQueues/stations/shifts are `[]` |
| `updateLineName` | `(user:id:name:)` | Returns `Void` |
| `saveLinePosition` | `(user:id:x:y:)` | Returns `Void` |
| `saveLineLocked` | `(user:id:locked:)` | Returns `Void` |
| `saveLineFocus` | `(user:id:focused:)` | Returns `Void` |
| `createInventory` | `(user:factoryId:name:)` | Creates sibling `Supply` |
| `inventory` | `(user:id:)` | Single record fetch |
| `updateInventoryName` | `(user:id:name:)` | Returns `Void` |
| `saveInventoryPosition` | `(user:id:x:y:)` | Returns `Void` |
| `intakeQueue` | `(user:id:)` | Single record fetch |
| `createIntakeQueue` | `(user:lineId:name:key:)` | Redistributes mix ratios |
| `updateIntakeQueueName` | `(user:id:name:)` | Returns `Void` |
| `updateIntakeQueueMixRatio` | `(user:id:mixRatio:)` | Returns `Void` |

## LeanForm types

```swift
CreateLine, CreateInventory, SaveLinePosition, SaveInventoryPosition,
SaveLineLocked, SaveLineFocus, StartWorkUnit,
UpdateLineName, UpdateStationName, UpdateIntakeQueueName, UpdateInventoryName,
UpdateWorkUnit, UpdateWorkUnitReporter, UpdateWorkUnitAssignees
```

---

## WorkUnit data model

- `id`: `Int` — numeric database ID, used for `ctrl.configure(workUnit.id)`
- `key`: `String` — human-readable identifier like `"FR-2001"`, used for display
- `normalizeStations` maps both `id` and `key`

---

## FactoryFloor state saves (fire-and-forget)

| Event | Route | Payload |
|---|---|---|
| Drag end (`onPointerUp`) | `PATCH /lean/save-line-position` or `save-inventory-position` | `{ id, gridX, gridY }` |
| Lock toggle | `PATCH /lean/save-line-locked` | `{ id, locked }` |
| Focus toggle | `PATCH /lean/save-line-focus` | `{ id, focused: activeFocusLineIds.has(id) }` |

> Universal bosslib architecture and XCTest patterns are documented in §14 of `boss-reference.md`.

---

## Reusing search/suggest routes

Do **not** create a new `suggested-*` or `find-*` route for a model when one already exists for the appropriate scope. Reuse the existing route and pass the required ID through the controller's `configure` method.

`suggested-*` and `find-*` routes always use the **plural** form of the model name (e.g. `suggested-operators`, not `suggested-operator`).

Examples of existing routes to reuse:
- Operator search: `GET /lean/suggested-operators/:companyId` and `GET /lean/find-operators/:companyId?q=`
- Intake queue search: `GET /lean/suggested-intake-queue/:lineId` and `GET /lean/find-intake-queue/:lineId?q=`

If a controller needs operator search but only has a `stationId`, add `companyId` to the parent fragment so it can be threaded through `configure`.

---

## Other fixes / changes

- Do NOT run `swift build` to verify after edits — the user runs tests independently

- `syncInsertButton()` excludes `.station-insert-button` so `+` buttons are never disabled in insert mode
- `.station-insert-button` has `cursor: pointer !important` in `graph.css`
- Removed unused functions: `pointsToD`, `getReplacementHopperWorkUnit`, `getGridSize`
- `Fragment.OK()` required for empty responses (HTTP 200 with empty body causes JSON parse error in `os.network.post`)

---

## Operator Fields in Forms

A model may have `Operator`-typed properties (e.g. `WorkUnit.creator`, `.reporter`, `.assignees`). Rules:

- **Read-only operator** (e.g. `creator`): `<div class="read-only"><label>Creator</label><span name="creator">—</span></div>`. Never editable.
- **Single owner** (e.g. `reporter`): use a `UISearchMenu`. `didFocusSearchMenu` calls `GET /lean/suggested-operators`; `didSearchForTerm` calls `GET /lean/operator/:name`. On select/deselect, PUT immediately to `/lean/work-unit/reporter/:workUnitId` (sub-resource save — does **not** go through the main Save button).
- **Multiple owners** (e.g. `assignees`): use a `UITokenMenu`. `didFocusTokenMenu` calls `GET /lean/suggested-operators`; `didSearchForTerm` calls `GET /lean/operator/:name`. On add/remove, read all `selectedOptions` from the backing `<select>` and PUT the full list to `/lean/work-unit/assignees/:workUnitId`.
- Guard both delegates with `if (isEmpty(workUnitId)) { return; }` so they are no-ops when creating a new work unit.

## Date Formatting

- All dates sent from server to client must be formatted using `formattedDate(for: ts, using: .usInformal)` in the route handler before placing them in a fragment.
- `DateFormatter.usInformal` produces the format: `"Fri, May 13 2026 @ 4:56pm"` (defined in `Date+boss.swift`).
- Date fields in forms are **read-only** `<span>` elements — never editable inputs.

## Form UI Conventions

- **Read-only `<span>` defaults**: always set to `—` (em dash) in HTML (e.g. `<span name="key">—</span>`).
- **`ui-token-menu` width**: always `style="width: auto;"` so it spans its container.
- **`ui-search-menu` width**: always `style="width: 200px;"`. Placeholder `<option>` text: `Assign <ModelName>…` (e.g. `<option>Assign Reporter…</option>`).

## application.json

- Every new controller HTML file MUST be registered in `application.json` under the `"controllers"` key.
- Path: `public/boss/app/io.bithead.lean/application.json`
- Common options: `{ }` (default), `{ "modal": true }`, `{ "singleton": true }`

## Network / Route Patterns

- Fire-and-forget state saves: `os.network.post(url, payload)` (no await)
- Required calls: `await os.network.post(...)` with try/catch and `os.ui.showError`
- Empty responses: `Fragment.OK()`
- Forms: `LeanForm` enum in `Lean+Forms.swift`
- Response fragments: `LeanFragment` enum in `Lean+Fragments.swift`
- All routes: `.addScope(.user)` after each handler
- Auth check: `let _ = try req.authUser` at start of each handler
- Route paths use path params not query params (e.g. `/lean/factories/:companyId`)
- Before adding any new route feature, always read: `Lean+Fragments.swift`, `Lean+Forms.swift`, `LeanRoute.swift`, `application.json`.
- `operator` is a Swift reserved keyword but is safe in route path strings. If a type name conflicts with a Swift keyword, wrap it in backticks (e.g. `` `operator` ``) rather than adding a redundant suffix.
- `OperatorType` is represented in fragments as `type: String` — `"Human"` for `.user(_)`, `"AI Agent"` for `.agent(_)`.
- **Search/suggest route naming** — follows the pattern in `boss-reference.md` §13. Use singular vs plural to indicate cardinality of the response:
  - `GET /lean/suggested-<model>/:scopeId` — default list for initial dropdown state
  - `GET /lean/find-<model>/:scopeId?q=` — filtered by search term
  - Singular (`find-operator`, `suggested-operator`) when the search targets one model type; plural (`find-operators`, `suggested-operators`) when the context is a multi-select.

## Service Layer (bosslib)

- **All business logic belongs in the `XxxService` struct**, not in `XxxAPI`. `XxxAPI` only calls the provider.
- **`XxxProvider` protocol** defines the interface; `XxxService` implements it; `XxxAPI` wraps it publicly.
- **Write only the logic needed to pass the current test** — no speculative implementation.
- **Required field validation** (nil, empty, whitespace): throw `api.error.RequiredParameter("fieldName")`
- **Invalid value validation** (wrong format, out of range, etc.): throw `api.error.InvalidParameter(name: "fieldName")`
- Never define a custom `BOSSError` subclass when `RequiredParameter` or `InvalidParameter` covers the case.
- Stub unimplemented DB logic with `fatalError("not implemented")` until a test drives it.

## Test Patterns (leanTests / XCTest)

- Always call `try await boss.start(storage: .memory)` first.
- Use `superUser().user` for an admin actor; `guestUser().user` for unauthenticated.
- Use `await XCTAssertError(try await api.xxx.method(...), api.error.SomeError(...))` to assert thrown errors.
- Structure tests with `// describe:` / `// when:` / `// it:` comment hierarchy.
- Test the negative/validation cases before the happy path.

---

## Pending / TODO
- All controllers except `FactoryFloor`, `Home`, and `WorkUnit` are empty shells — UI and logic still needed
- `factory-floor` route still uses a fixture (`Fixtures/Lean/factory-floor.json`); real DB query not yet implemented
- `intake-queue/:id` GET still uses a fixture; real DB query not yet implemented
- `GET /lean/work-unit/:workUnitId` uses a fixture (`Fixtures/Lean/work-unit.json`); real DB query not yet implemented
- `GET /lean/suggested-operators` and `GET /lean/operator/:name` routes not yet implemented
- `PUT /lean/work-unit/reporter/:workUnitId`, `PUT /lean/work-unit/assignees/:workUnitId`, `PUT /lean/work-unit/:workUnitId` are stubs with `// TODO:` comments
- `start-work-unit`, `update-station-name`, `GET/POST station/:stationId`, `POST intake-queue/:id`, `POST inventory/:inventoryId`, `POST line/:lineId` routes are stubs with `// TODO:` comments
- Sample data in fixtures uses hard-coded IDs; real IDs will come from the DB
