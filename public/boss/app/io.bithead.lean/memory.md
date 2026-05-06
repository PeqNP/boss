# Session Memory

## Last updated: 2026-05-06

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
| GET | `/lean/companies` | → `LeanFragment.Companies` | |
| GET | `/lean/factories/:companyId` | → `LeanFragment.Factories` | path param |
| POST | `/lean/company` | `LeanForm.SaveCompany` → `LeanFragment.List.Company` | `companyId` (null=create), `name` |
| POST | `/lean/factory` | `LeanForm.SaveFactory` → `LeanFragment.List.Factory` | `companyId`, `factoryId` (null=create), `name` |
| POST | `/lean/line` | `LeanForm.CreateLine` → `LeanFragment.Line` | `factoryId`, `name` |
| POST | `/lean/inventory` | `LeanForm.CreateInventory` → `LeanFragment.Inventory` | `factoryId`, `name` |
| POST | `/lean/start-work-unit` | `LeanForm.StartWorkUnit` → `LeanFragment.StartWorkUnitResponse` | `id` |
| POST | `/lean/save-line-position` | `LeanForm.SaveLinePosition` → `Fragment.OK()` | `id, gridX, gridY` |
| POST | `/lean/save-inventory-position` | `LeanForm.SaveInventoryPosition` → `Fragment.OK()` | `id, gridX, gridY` |
| POST | `/lean/save-line-locked` | `LeanForm.SaveLineLocked` → `Fragment.OK()` | `id, locked` |
| POST | `/lean/save-line-focus` | `LeanForm.SaveLineFocus` → `Fragment.OK()` | `id, focused` |
| POST | `/lean/update-line-name` | `LeanForm.UpdateLineName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-station-name` | `LeanForm.UpdateStationName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-intake-queue-name` | `LeanForm.UpdateIntakeQueueName` → `Fragment.OK()` | `id, name` |
| POST | `/lean/update-inventory-name` | `LeanForm.UpdateInventoryName` → `Fragment.OK()` | `id, name` |

Implemented routes (no longer stubs):
- `POST /lean/update-intake-queue-name` — calls `api.lean.updateIntakeQueueName(user:id:name:)`

Remaining stubs in `LeanRoute.swift` with `// TODO:` comments: all others listed above.

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
| `factories` | `(companyId:)` | Returns `[Factory]` |
| `createFactory` | `(user:companyId:name:)` | |
| `createLine` | `(user:factoryId:name:)` | Creates sibling `Hopper` |
| `createInventory` | `(user:factoryId:name:)` | Creates sibling `Supply` |
| `intakeQueue` | `(user:id:)` | Single record fetch |
| `createIntakeQueue` | `(user:lineId:name:key:)` | Redistributes mix ratios |
| `updateIntakeQueueName` | `(user:id:name:)` | Returns `Void` |

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

> Universal bosslib architecture and XCTest patterns are documented in §14 of `boss-reference.md`.

---

## Other fixes / changes

- Do NOT run `swift build` to verify after edits — the user runs tests independently

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
