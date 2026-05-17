# Session Memory

## Last updated: 2026-05-11

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

## All Lean routes

| Method | Path | Form/Response | Notes |
|---|---|---|---|
| GET | `/lean/companies` | → `LeanFragment.List.Companies` | |
| GET | `/lean/factories/:companyId` | → `LeanFragment.List.Factories` | path param |
| GET | `/lean/company/:companyId` | → `LeanFragment.Company` | |
| GET | `/lean/factory/:factoryId` | → `LeanFragment.Factory` | |
| GET | `/lean/inventory/:inventoryId` | → `LeanFragment.Inventory` | |
| GET | `/lean/line/:lineId` | → `LeanFragment.Line` | |
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
| DELETE | `/lean/company/:companyId` | → `Fragment.OK()` | |
| DELETE | `/lean/factory/:factoryId` | → `Fragment.OK()` | |

Remaining stubs (have `// TODO:` in route body): `start-work-unit`, `update-station-name`, `GET/POST intake-queue/:id`, `GET/POST inventory/:inventoryId`, `GET/POST line/:lineId`, `GET/POST station/:stationId`, `GET/POST work-unit/:workUnitId`.

---

## LeanFragment types

```swift
Company, Companies, Line, Inventory, WorkUnit, StartWorkUnitResponse, Factory, Factories
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
UpdateLineName, UpdateStationName, UpdateIntakeQueueName, UpdateInventoryName
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
- **Single owner** (e.g. `reporter`): use a `UISearchMenu`. `didFocusSearchMenu` calls `GET /lean/suggested-operators`; `didSearchForTerm` calls `GET /lean/operator/:name`.
- **Multiple owners** (e.g. `assignees`): use a `UITokenMenu`. `didFocusTokenMenu` calls `GET /lean/suggested-operators`; `didSearchForTerm` calls `GET /lean/operator/:name`.

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
- All controllers except `FactoryFloor` and `Home` are empty shells — UI and logic still needed
- `factory-floor` route still uses a fixture (`Fixtures/Lean/factory-floor.json`); real DB query not yet implemented
- `intake-queue/:id` GET still uses a fixture; real DB query not yet implemented
- `start-work-unit`, `update-station-name`, `GET/POST station/:stationId`, `GET/POST work-unit/:workUnitId`, `POST intake-queue/:id`, `POST inventory/:inventoryId`, `POST line/:lineId` routes are stubs with `// TODO:` comments
- Sample data in fixtures uses hard-coded IDs; real IDs will come from the DB
