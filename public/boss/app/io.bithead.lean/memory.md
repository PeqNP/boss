# Session Memory

## Last updated: 2026-04-23

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

## Conventions

### JS controller pattern
- Load a window: `const win = await $(app.controller).loadController("Name");`
- Show and configure: `win.ui.show(function(ctrl) { ctrl.configure(arg); });`
- POST to server: `await os.network.post("/route/path", { id, name });`
- Fire-and-forget (state saves): `os.network.post(url, payload)` — no `await`, no error handling
- Parameters: ≤2 args → individual with `_` prefix + jsdoc; ≥3 → Object with jsdoc
- `configure` always has jsdoc
- Load data in `viewDidLoad`, not `configure` (view not ready yet in `configure`)
- In `viewDidLoad`, initialize the `UIListBox` delegate **before** calling `loadXxx()` — ensures the `didSelectListBoxOption` callback fires for the first auto-selected option when data loads

### Swift route pattern (see `FriendRoute.swift` for reference)
- Decode form: `let form = try req.content.decode(LeanForm.SomeName.self)`
- Forms go in `Lean+Forms.swift` as `LeanForm` enum cases conforming to `Content`
- Fragments (responses) go in `Lean+Fragments.swift` as `LeanFragment` enum cases conforming to `Content`
- Auth check: `let _ = try req.authUser` (or `let authUser = try req.authUser` if needed)
- Empty response: `return Fragment.OK()` — NOT `Response(status: .ok)` (that causes JSON parse error)
- All routes require `.addScope(.user)` after the handler
- Route path params preferred over query params: e.g. `GET /lean/factories/:companyId`
- Path param extraction: `let id = try req.parameters.require("companyId", as: Int.self)`

### application.json rule
- **Every new controller MUST be registered** in `application.json` under `"controllers"`
- Common options: `{}` (default), `{ "modal": true }`, `{ "singleton": true }`

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
| `Company` | `Company.html` | `(_companyId)` | Edit only; Add opens with no configure |
| `Factories` | `Factories.html` | `(_companyId)` | Lists factories for a company |
| `Factory` | `Factory.html` | `(_factoryId)` | Edit only; Add opens with no configure |
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
| GET | `/lean/companies` | → `LeanFragment.Companies` | |
| GET | `/lean/factories/:companyId` | → `LeanFragment.Factories` | path param |
| POST | `/lean/create-line` | `LeanForm.CreateLine` → `LeanFragment.Line` | `companyId` |
| POST | `/lean/create-inventory` | `LeanForm.CreateInventory` → `LeanFragment.Inventory` | `companyId` |
| POST | `/lean/start-work-unit` | `LeanForm.StartWorkUnit` → `LeanFragment.StartWorkUnitResponse` | `id` |
| POST | `/lean/save-line-position` | `LeanForm.SaveLinePosition` → `Fragment.OK()` | `id, gridX, gridY` |
| POST | `/lean/save-inventory-position` | `LeanForm.SaveInventoryPosition` → `Fragment.OK()` | `id, gridX, gridY` |
| POST | `/lean/save-line-locked` | `LeanForm.SaveLineLocked` → `Fragment.OK()` | `id, locked` |
| POST | `/lean/save-line-focus` | `LeanForm.SaveLineFocus` → `Fragment.OK()` | `id, focused` |
| POST | `/lean/update-line-name` | `LeanForm.UpdateLineName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-station-name` | `LeanForm.UpdateStationName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-intake-queue-name` | `LeanForm.UpdateIntakeQueueName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-inventory-name` | `LeanForm.UpdateInventoryName` → `Fragment.OK()` | `id, name` |

All stubs are in `LeanRoute.swift` with `// TODO:` comments.

---

## LeanFragment types

```swift
Company, Companies, Line, Inventory, WorkUnit, StartWorkUnitResponse, Factory, Factories
```

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
| Drag end (`onPointerUp`) | `POST /lean/save-line-position` or `save-inventory-position` | `{ id, gridX, gridY }` |
| Lock toggle | `POST /lean/save-line-locked` | `{ id, locked }` |
| Focus toggle | `POST /lean/save-line-focus` | `{ id, focused: activeFocusLineIds.has(id) }` |

---

## Other fixes / changes

- `syncInsertButton()` excludes `.station-insert-button` so `+` buttons are never disabled in insert mode
- `.station-insert-button` has `cursor: pointer !important` in `graph.css`
- Removed unused functions: `pointsToD`, `getReplacementHopperWorkUnit`, `getGridSize`
- `Fragment.OK()` required for empty responses (HTTP 200 with empty body causes JSON parse error in `os.network.post`)

---

## Pending / TODO
- All controllers except `FactoryFloor` and `Home` are empty shells — UI and logic still needed
- All Lean route stubs have `// TODO:` comments — server-side logic not yet implemented
- Sample data uses hard-coded IDs; real IDs will come from the DB
- `FactoryFloor` currently wired to company-level data; needs to switch to factory-level data
