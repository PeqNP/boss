# Session Memory

## Last updated: 2026-04-22

---

## Project: io.bithead.lean (Factory Floor UI)

### Key files
- **UI controller**: `public/boss/app/io.bithead.lean/controller/FactoryFloor.html`
- **CSS**: `public/boss/app/io.bithead.lean/graph.css`
- **App manifest**: `public/boss/app/io.bithead.lean/application.json`
- **Controllers dir**: `public/boss/app/io.bithead.lean/controller/`
- **Lean routes**: `server/web/Sources/App/Routes/Lean/LeanRoute.swift`
- **Lean forms**: `server/web/Sources/App/Routes/Lean/Lean+Forms.swift`
- **DB migration**: `server/bosslib/Sources/bosslib/Database/v1_3_0.swift`

---

## Conventions

### JS controller pattern
- Load a window: `const win = await $(app.controller).loadController("Name");`
- Show and configure: `win.ui.show(function(ctrl) { ctrl.configure(arg); });`
- POST to server: `await os.network.post("/route/path", { id, name });`
- Parameters: ≤2 args → individual with `_` prefix + jsdoc; ≥3 → Object with jsdoc
- `configure` always has jsdoc

### Swift route pattern (see `FriendRoute.swift` for reference)
- Decode form: `let form = try req.content.decode(LeanForm.SomeName.self)`
- Forms go in `Lean+Forms.swift` as `LeanForm` enum cases conforming to `Content`
- Auth check: `let _ = try req.authUser` (or `let authUser = try req.authUser` if needed)

---

## Completed work this session

### Database
- Created `v1_3_0.swift` — 35 SQLite tables for all Lean.swift models
- Registered `Version1_3_0` in `Database.swift`

### Controllers created
| Controller | File | configure param |
|---|---|---|
| `WorkUnit` | `WorkUnit.html` | `(_intakeQueueId, _workUnitId?)` |
| `WorkUnits` | `WorkUnits.html` | `(_intakeQueueId)` |
| `IntakeQueue` | `IntakeQueue.html` | `(_intakeQueueId)` |
| `OutputWorkUnits` | `OutputWorkUnits.html` | `(_outputId)` |
| `Line` | `Line.html` | `(_lineId)` |
| `Station` | `Station.html` | `(_stationId)` |
| `StationWorkspace` | `StationWorkspace.html` | `(_workUnitId)` |
| `Inventory` | `Inventory.html` | `(_inventoryId)` |

All registered in `application.json`.

### Button wiring (FactoryFloor.html)
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

### Insert control fix
- `syncInsertButton()` selector changed from `button:not(.line-insert-button)` to `button:not(.line-insert-button):not(.station-insert-button)` so `+` buttons are never disabled in insert mode (both in `syncInsertButton` and the other-lines deactivation loop)
- `.station-insert-button` has `cursor: pointer !important` in `graph.css`

### Name editing → server sync
`makeNameEditable` callbacks now call `os.network.post` after updating local model:

| Model | Route | Payload |
|---|---|---|
| Line | `POST /lean/update-line-name` | `{ id, name }` |
| Station | `POST /lean/update-station-name` | `{ id, name }` |
| Intake Queue | `POST /lean/update-intake-queue-name` | `{ id, name }` |
| Inventory | `POST /lean/update-inventory-name` | `{ id, name }` |

Stubbed in `LeanRoute.swift`, forms in `Lean+Forms.swift` (`LeanForm` enum).

---

## Pending / TODO
- All new controllers (`Line`, `Station`, `WorkUnit`, `WorkUnits`, `IntakeQueue`, `OutputWorkUnits`, `StationWorkspace`, `Inventory`) are empty shells — UI and logic still needed
- Lean route stubs all have `// TODO:` comments — server-side logic not yet implemented
- Sample station data uses hard-coded IDs 1–17; real IDs will come from the DB
