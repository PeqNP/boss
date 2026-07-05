# BOSS Swift Backend Reference

Rules for the Vapor web layer (`server/web/`) and bosslib private API (`server/bosslib/`).

---

## 13. Backend — Swift Web Layer

The Swift+Vapor web layer lives in `/server/web/Sources/App/Routes/`.

### Route file pattern

```swift
// Routes/<Feature>/<Feature>Route.swift
import Vapor

struct MyFeatureRoute {
    func boot(routes: RoutesBuilder) throws {
        let r = routes.grouped("my-feature")
        r.get("items", use: getItems).addScope(.user)
        r.post("item", use: createItem).addScope(.user)
        r.put("item", ":itemId", use: updateItem).addScope(.user)
        r.delete("item", ":itemId", use: deleteItem).addScope(.user)
    }

    func getItems(req: Request) async throws -> [MyFeatureFragment.List.Item] {
        let _ = try req.authUser
        return try await MyFeatureAPI.getItems(req.db)
    }

    func createItem(req: Request) async throws -> MyFeatureFragment.List.Item {
        let _ = try req.authUser
        let form = try req.content.decode(MyFeatureForm.CreateItem.self)
        let item = try await MyFeatureAPI.createItem(req.db, name: form.name)
        return MyFeatureFragment.List.Item(id: item.id, name: item.name)
    }

    func updateItem(req: Request) async throws -> Fragment.OK {
        let _ = try req.authUser
        let itemId = try req.parameters.require("itemId", as: Int.self)
        let form = try req.content.decode(MyFeatureForm.UpdateItem.self)
        try await MyFeatureAPI.updateItem(req.db, id: itemId, name: form.name)
        return Fragment.OK()
    }

    func deleteItem(req: Request) async throws -> Fragment.OK {
        let _ = try req.authUser
        let id = try req.parameters.require("itemId", as: Int.self)
        try await MyFeatureAPI.deleteItem(req.db, id: id)
        return Fragment.OK()
    }
}
```

### Forms and Fragments

```swift
// Routes/<Feature>/<Feature>+Forms.swift
enum MyFeatureForm {
    struct CreateItem: Content {
        let name: String?
    }
    struct UpdateItem: Content {
        let name: String?
    }
}

// Routes/<Feature>/<Feature>+Fragments.swift
enum MyFeatureFragment {
    enum List {
        struct Item: Content {
            let id: Int
            let name: String
        }
        typealias Items = [Item]
    }
    struct Item: Content {
        let id: Int
        let name: String
        let status: String
    }
}
```

**Rules:**
- Auth check: `let _ = try req.authUser` (or `let authUser = try req.authUser` if needed)
- Empty response: `return Fragment.OK()` — **not** `Response(status: .ok)` (causes JSON parse error)
- All routes require `.addScope(.user)` after the handler
- **Every route must have an `.openAPI(...)` annotation** chained before `.addScope(.user)`. Use the following patterns:

  ```swift
  // GET with response body
  group.get("items") { req in ... }
      .openAPI(
          summary: "Brief description",
          response: .type(MyFragment.Items.self),
          responseContentType: .application(.json)
      )
      .addScope(.user)

  // POST/PUT/PATCH with request body and response body
  group.post("item") { req in ... }
      .openAPI(
          summary: "Brief description",
          body: .type(MyForm.CreateItem.self),
          contentType: .application(.json),
          response: .type(MyFragment.Item.self),
          responseContentType: .application(.json)
      )
      .addScope(.user)

  // Mutation returning Fragment.OK (no meaningful body)
  group.delete("item", ":itemId") { req in ... }
      .openAPI(
          summary: "Brief description",
          response: .type(Fragment.OK.self),
          responseContentType: .application(.json)
      )
      .addScope(.user)
  ```

  - Omit `body:` / `contentType:` for GET and DELETE routes that take no body.
  - Add `description:` for routes where `summary:` alone is insufficient (e.g. search endpoints with a `?q=` param, type-change routes with side effects).
- Do not add comments describing what a route does (e.g. `// SupplyFieldOption CRUD` or `// Company-scoped search...`). The `summary` inside the `.openAPI(...)` declaration already provides this context. `TODO` comments are still required while the implementation is pending.
- Use path params for IDs: `GET /my-feature/items/:companyId`
- Path param extraction: `let id = try req.parameters.require("companyId", as: Int.self)`
- Route naming: `POST /resource` to create; `PUT /resource/:id` to replace all editable fields; `PATCH /resource/:id` to update a subset of fields
- **Controller / route / fragment name alignment**: the BOSS controller name, the init route path, and the response fragment struct must all derive from the same base name. Convert the PascalCase controller name to kebab-case for the route and use PascalCase for the fragment. Example: controller `CreateWorkUnit` → route `GET /lean/create-work-unit/:id` → fragment `LeanFragment.CreateWorkUnit`. Never invent a different name for any of the three.
- **Route ordering within a route file**: Group routes alphabetically by their first path segment (resource name). Within each group, order routes by HTTP method: GET first, then POST, PUT, PATCH, DELETE. List sub-resource routes (e.g. `GET /station/:id/work-units`) immediately after the parent resource's routes, following the same method order.
- **Search/suggest route naming** — this flat-prefix naming convention applies **only** to search/suggest routes that populate `UISearchMenu` or `UIPopupMenu`. Place them at the root of the feature group using one of two prefixes:
  - `GET /feature/suggested-<model-name>/:scopeId` — returns a default list (no search term); used for the initial dropdown state
  - `GET /feature/find-<model-name>/:scopeId?q=` — returns results filtered by the search term `q`
  - Examples: `GET /lean/suggested-intake-queue/:lineId`, `GET /lean/find-intake-queue/:lineId?q=`
  - Use the flat prefix (e.g. `suggested-intake-queue`) to avoid Vapor ambiguity with existing nested routes. Do **not** apply this pattern to ordinary sub-resource routes — those should use standard nested paths (e.g. `GET /lean/station/:stationId/work-units`).
- List fragments use lightweight `id` + `name` structs; detail fragments use all fields
- Do not suffix fragment names with `Detail` (e.g. `MyFragment.Item` not `MyFragment.ItemDetail`)
- POST/PUT payload: include only editable fields — omit read-only display fields
- For `PUT /:id` and `PATCH /:id`, the ID is in the URL — do **not** include it in the body
- When a form represents a discriminated union (e.g. `SupplyFieldType`), the `save()` function must branch on the selected type and construct the correct shape of the request body for each case (e.g. `text` needs `textType` + `placeholder`; `file` needs `mimeType`; `radio`/`multiSelect` need `append`).
- `save()` in the controller branches on the private ID variable: `PUT /resource/:id` when editing, `POST /resource` when creating
- Validation logic belongs in `XxxService`, not routes or API layer
- **Client-side validation is minimal** — the controller only checks whether required fields are empty (using `isEmpty` / `view.ui.inputValue`). All other business rules (max length, format, range, uniqueness, etc.) are enforced exclusively on the backend. This keeps business logic in one place and avoids duplicating rules across JS and Swift.
- **Numeric field validation** — use `foundation.js` helpers rather than `isNaN`:
  - `isInteger(value)` — for fields that map to `Int` on the backend (whole numbers, no decimal allowed). e.g. mix ratio, count, position.
  - `isNumeric(value)` — for fields that allow decimals or floating-point values.
  - Both functions return `false` for empty/null, so a single check covers both the empty and type cases.
- **Always define a fragment struct** (`*+Fragments.swift`) for every response type — never return a `bosslib` model directly from a route. Reasons:
  1. `bosslib` must never import `Vapor`; conforming bosslib types to `Content` would create that dependency.
  2. Domain models and client-facing service models often diverge: enums are encoded as strings, nested objects are flattened, computed fields are added, and sensitive fields are omitted. A fragment is the explicit contract with the client.
  3. Fragments give you a natural place to reshape data (e.g. `MixRatioType.distributed` → `"distributed"`) without polluting the domain model with serialisation concerns.
- **Encode Swift enums as human-readable strings in fragments** — never as raw integer IDs. e.g. `MixRatioType.fixed` → `"fixed"`, `.distributed` → `"distributed"`. This makes client code readable without named constants mapping IDs. When the route receives the string back on save, map it to the storage ID before persisting (e.g. `"fixed"` → `0`, `"distributed"` → `1`).
- **One form struct per route** — every `PUT`, `POST`, and `PATCH` route must have its own dedicated form struct named after the action (e.g. `UpdateIntakeQueue` for `PUT /intake-queue/:id`). Never reuse a form struct from an unrelated route, even if the fields happen to overlap today.
- **All fragment and form models belong inside the main enum** — when adding new models to `LeanFragment` or `LeanForm`, declare them directly inside the `enum LeanFragment { ... }` or `enum LeanForm { ... }` block. Do **not** use separate `extension LeanFragment` or `extension LeanForm` declarations. This keeps the entire surface area of the API contract in one contiguous, easy-to-navigate location.

- **Shared sub-model form struct** — when the same nested model appears in multiple `Update*` form structs, declare it once as a nested struct inside `LeanForm` (or the relevant form enum). Mark `id` as optional so it can represent both an existing record and a new one:

```swift
// Declared once in LeanForm
struct Theme: Content {
    var id: Int?      // nil when the theme does not yet exist in the DB
    var fill: String
    var stroke: String
}

// Reused in any form that includes a theme
struct UpdateStation: Content {
    var name: String?
    var assigneeAction: String?
    var theme: LeanForm.Theme?
}

struct UpdateIntakeQueue: Content {
    var name: String?
    // ...
    var theme: LeanForm.Theme?
}
```

- **Sub-resource form fields** — when some fields of a model are saved independently from the main form (e.g., a reporter or assignees list that auto-saves on change), define separate form structs and PUT endpoints for those sub-resources rather than including those fields in the main `UpdateXxx` form:

```swift
// Main update — only contains the fields saved by the Save button
struct UpdateWorkUnit: Content {
    var name: String?
    var eta: String?
}

// Sub-resource updates — saved immediately via delegate callbacks
struct UpdateWorkUnitReporter: Content {
    var operatorId: Operator.ID?   // Optional — nil clears the reporter
}

struct UpdateWorkUnitAssignees: Content {
    var operatorIds: [Operator.ID] // Full current list, not a delta
}
```

The PUT routes use a static path segment before the ID parameter so Vapor can distinguish them from the main `PUT /resource/:id` route:

```swift
group.put("work-unit", "reporter",  ":workUnitId") { ... }  // PUT /work-unit/reporter/:id
group.put("work-unit", "assignees", ":workUnitId") { ... }  // PUT /work-unit/assignees/:id
group.put("work-unit",              ":workUnitId") { ... }  // PUT /work-unit/:id (main)
```

Declare the more-specific routes **before** the parameter-only route; Vapor matches routes in registration order.

- **Nullable sub-resource FK fields** — when a sub-resource can be cleared (e.g. deselecting a reporter), use `Operator.ID?` (optional) in the form struct so the client can send `null` to clear the value. A non-optional ID means the field is always required and can only be replaced, never removed.

- **Search endpoints for `UISearchMenu` / `UITokenMenu`** — use a two-route pattern per resource: one for the initial suggested list and one for term-filtered results. Scope both by a parent ID (e.g. `companyId`) so results are relevant to the user's context. Use a `?q=` query parameter for the search term rather than a path segment.

```swift
// Suggested list — called on first focus (initialize == true)
group.get("operator", "suggested", ":companyId") { req in
    let companyId = try req.parameters.require("companyId", as: Int.self)
    // return suggested Fragment.Option[]
}

// Term search — called while typing (debounced)
group.get("operator", ":companyId") { req in
    let companyId = try req.parameters.require("companyId", as: Int.self)
    let q = req.query[String.self, at: "q"] ?? ""
    // return matching Fragment.Option[]
}
```

Client wiring:
```javascript
reporterMenu.delegate = {
  didFocusSearchMenu: async function(initialize) {
    if (!initialize) { return null; }  // use cached results on re-focus
    if (isEmpty(companyId)) { return []; }
    return os.network.get(`/lean/operator/suggested/${companyId}`);
  },
  didSearchForTerm: async function(term) {
    if (isEmpty(companyId)) { return []; }
    return os.network.get(`/lean/operator/${companyId}?q=${encodeURIComponent(term)}`);
  }
};
```

Guard both delegates with `if (isEmpty(scopeId)) { return []; }` when the scope ID may not be set yet (e.g. before the work unit response arrives).

### Fixture pattern

When a route is not yet backed by real data, or you need to iterate on updating/fixing a client feature/bug, use a JSON fixture instead of hardcoding Swift structs in the route.

**File layout** — fixtures live in `server/web/Fixtures/<RouteGroupFolder>/`, where `<RouteGroupFolder>` matches the route group folder name under `Routes/` (e.g. `Routes/Lean/` → `Fixtures/Lean/`). The folder and file names use the same casing as the route group folder.

```
server/web/
  Fixtures/
    Lean/
      factory-floor.json
      intake-queue.json
  Sources/App/
    Fixture.swift          ← loadFixture helper
    Routes/Lean/
      LeanRoute.swift
```

**`loadFixture` helper** — defined in `server/web/Sources/App/Fixture.swift`:
```swift
func loadFixture<T: Decodable>(_ path: String) throws -> T
```

**Usage in a route** — one line, type inferred, commented out by default to allow it to be turned on or off quickly. It can be placed directly after authentication:
```swift
group.get("factory-floor", ":factoryId") { req in
    let _ = try req.authUser
    return try loadFixture("Fixtures/Lean/factory-floor.json") as LeanFragment.FactoryFloor
    let factoryId = try req.parameters.require("factoryId", as: Int.self)
    // ... logic to query and return pattern from library would go here
}
.addScope(.user)
```

**Rules:**
- The `Fixtures/` directory is a sibling to `Sources/` and is **never declared as a resource in `Package.swift`**, so SPM never bundles the JSON files — in debug or release builds. They exist only on the developer's filesystem and are loaded at runtime via Vapor's working directory.
- `loadFixture` is always compiled in; only the JSON files are absent in production (they're never deployed).
- `path` is always relative to the package root (`server/web/`), which is Vapor's working directory at runtime.
- **Naming**: Name a single fixture after the model it represents (e.g. `intake-queue.json`). When a route needs **multiple fixtures** for the same model, use the numbered convention `<model>-<n>.json` starting at `1` (e.g. `line-1.json`, `line-2.json`). If a plain `<model>.json` already exists when a second fixture is added, rename it to `<model>-1.json` first.
- **Multiple fixtures**: When a route loads multiple numbered fixtures, interpolate the resource ID in the path and clamp unknown IDs to a valid range:
  ```swift
  var lineId = try req.parameters.require("lineId", as: Int.self)
  let availableIds: [Int] = [1, 2]
  if !availableIds.contains(lineId) { lineId = 1 }
  return try loadFixture("Fixtures/Lean/line-\(lineId).json") as LeanFragment.Line
  ```
- When the real route is implemented, comment out the fixture line so that it can be easily used again in the future for fast iteration.
- **Keep fixtures in sync with fragment structs** — whenever a nullable field is added to a `LeanFragment` (or any fragment) struct, add that field as `null` to every related fixture JSON file. A missing field causes a decode failure at runtime.

---

## 14. Backend — Swift Private API (bosslib)

The Swift private API lives in `/server/bosslib/Sources/bosslib/`.

### Architecture — 3-file pattern per domain

| File | Purpose |
|---|---|
| `xxx+api.swift` | `XxxProvider` protocol (interface) + `XxxAPI` final public class (no logic, delegates to provider) |
| `xxx+service.swift` | `XxxService` struct implementing `XxxProvider`; all business logic lives here |
| `xxx+errors.swift` | Domain-specific `BOSSError` subclasses |

Domain model placement:
- Domain models must live in their respective domain model file under `server/bosslib/Sources/bosslib/Models/`.
- Do not define domain models in `xxx+api.swift` or `xxx+service.swift` files.
- Exception: domain-specific `BOSSError` models belong in `xxx+errors.swift` (for example, `lean+errors.swift`, `acl+errors.swift`).
- Example: Lean domain models belong in `server/bosslib/Sources/bosslib/Models/Lean.swift`.

Registration on `api`:
```swift
public static let lean = LeanAPI(provider: LeanService())
```

Concurrency and dependency override rules:
- Prefer immutable API namespace registration (`static let`) over mutable global API state.
- Avoid `nonisolated(unsafe)` for API singleton registration unless there is no viable alternative.
- If tests need dependency substitution, use a scoped provider override pattern (for example, TaskLocal-backed override) rather than mutating `api.<domain>` globals.
- Keep provider override helpers (for example, `withProvider`) non-public inside bosslib unless there is a deliberate external API requirement.
- Any model that crosses concurrency boundaries must conform to `Sendable`.
- `Sendable` requirements are transitive: if `A: Sendable` stores `B`, then `B` (and its stored members) must also be `Sendable`.

### Implementation discipline
- Write **only** the logic needed to pass the current test. No speculative code.
- Stub unimplemented DB paths with `fatalError("not implemented")` until a test drives them.
- Never put business logic in `XxxAPI` — it belongs in `XxxService`.

### API naming conventions (bosslib route-surface)
- Follow Swift naming conventions for method names; avoid HTTP verb prefixes in API method names.
- Keep `find*` naming for lightweight search endpoints.
- Use `save<ModelName>` for create/update/partial-update operations that correspond to POST/PUT/PATCH routes.
- Use `<modelName>` for read operations that correspond to GET routes. Example: use `image(...)`, not `getImage(...)`.
- Use method overloading when it keeps names clear and signatures remain distinguishable by parameters.
- Prefer model names that match the method intent. Example: `suggestedAgents(...)` should return `[SuggestedItem]`.
- Reuse generic lightweight list models for shared list-style responses (`SuggestedItem`, `FoundItem`, `ListItem`) instead of creating one-off per-route models.
- For shared lightweight list responses, define one canonical model (for example, `ListItem`) and expose semantic intent through typealiases (for example, `typealias SuggestedItem = ListItem`, `typealias FoundItem = ListItem`). This is preferred over duplicating identical structs.
- For Swift backend API/provider calls, pass request properties as explicit function parameters instead of wrapping them in `Create*Request` / `Update*Request` model structs.
- Reserve wrapper request models for route-layer decoding concerns, not bosslib API/service signatures.
- Do not use a `DTO` suffix in Lean API model names.
- For Lean, place composite and light-weight API composition models in `server/bosslib/Sources/bosslib/Models/Lean.swift` under `MARK: Composite and Light-weight DTOs`. Do not declare these models in `lean+api.swift`.

### Validation errors
- **Required field** (nil, empty string, whitespace-only): `throw api.error.RequiredParameter("fieldName")`
- **Invalid value** (wrong format, out-of-range, etc.): `throw api.error.InvalidParameter(name: "fieldName")`
- Do **not** define a custom `BOSSError` subclass when `RequiredParameter` or `InvalidParameter` covers the case.
- Custom `BOSSError` subclasses (in `xxx+errors.swift`) are only for domain-specific conditions — e.g. `FriendIsSelf`, `AlreadyFriends`.

### Validation pattern in service
```swift
guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
    throw api.error.RequiredParameter("name")
}
```

### Provider protocol signature
Accept `String?` (not `String`) in the provider protocol when the caller may pass nil — validation happens inside the service.

### DB insert pattern
```swift
let rows = try await conn.sql().insert(into: "table_name")
    .columns("id", "col1", "col2")
    .values(SQLLiteral.null, SQLBind(value1), SQLBind(value2))
    .returning("id")
    .all()
let id = try rows[0].decode(column: "id", as: ModelType.ID.self)
```
- Always use `SQLLiteral.null` for the auto-increment `id` column.
- Always use `.returning("id").all()` to retrieve the inserted row's ID.
- Decode the returned ID immediately; do not re-query the database.

### DB select (list query) pattern
```swift
let rows = try await conn.select()
    .column("*")
    .from("table_name")
    .where("foreign_key_col", .equal, someId)
    .all()
return try rows.map { row in
    ModelType(
        id: try row.decode(column: "id", as: ModelType.ID.self),
        name: try row.decode(column: "name", as: String.self)
    )
}
```
- Use `conn.select()` (shorthand), not `conn.sql().select()`.
- Name list query functions with the **plural model name**: `companies(user:)`, `factories(companyId:)` — not `getCompanies` or `listCompanies`.

### DB update pattern
```swift
try await conn.sql().update("table_name")
    .set("column_name", to: SQLBind(value))
    .where("id", .equal, SQLBind(id))
    .run()
```
- Use `conn.sql().update(...)` (note: `sql()` is required here, unlike select).
- Use `.run()` when no return value is needed.
- Chain multiple `.set(...)` calls to update several columns at once.
- Update functions that return nothing should have a `Void` (implicit) return type — do not return `Fragment.OK()` from the service layer.

### DB delete pattern

```swift
func deleteFactory(session: Database.Session, user: User, id: Factory.ID) async throws {
    let conn = try await session.conn()
    let rows = try await conn.select()
        .column("id")
        .from("factories")
        .where("id", .equal, id)
        .all()
    guard rows.first != nil else {
        throw service.error.RecordNotFound()
    }
    try await conn.sql().delete(from: "factories")
        .where("id", .equal, SQLBind(id))
        .run()
}
```

- Always **check existence first** (select by ID) and throw `service.error.RecordNotFound()` when the record is missing. Do not attempt to infer success from affected row counts.
- Use `conn.sql().delete(from: "table_name").where(...).run()`. Note `sql()` is required (same as update).
- Only select `"id"` in the existence check — there is no need to decode the full row.
- Do **not** manually delete child records. Rely on `onDelete: .cascade` foreign keys in the schema to remove dependent rows automatically.

#### Adding cascade deletes in the schema

When defining a foreign key in a `DatabaseVersion` migration, add `onDelete: .cascade` so child records are automatically removed when the parent is deleted:

```swift
try await sql.create(table: "lines")
    ...
    .foreignKey(["factory_id"], references: "factories", ["id"], onDelete: .cascade)
    .run()
```

Use `onDelete: .setNull` (not `.cascade`) when the child row should survive but its reference should be cleared:

```swift
    .foreignKey(["theme_id"], references: "themes", ["id"], onDelete: .setNull)
```

Cascade chains propagate automatically: deleting a `Company` cascades to its `Factory` rows, which cascade to `Line` rows, which cascade to `Hopper`, `IntakeQueue`, `Station`, etc.

#### Cascade testing in XCTest

After deleting a parent, query the child table through the public API to confirm cascade removal:

```swift
try await api.lean.deleteFactory(user: user, id: factory.id)
let remaining = try await api.lean.factories(companyId: company.id)
XCTAssertEqual(remaining.count, 0)
```

#### Route wiring

The route handler retrieves the authenticated user, extracts the ID from the path parameter, and delegates directly to the API — no route-level existence check needed:

```swift
group.delete("factory", ":factoryId") { req in
    let authUser = try req.authUser
    let factoryId = try req.parameters.require("factoryId", as: Int.self)
    try await api.lean.deleteFactory(user: authUser.user, id: factoryId)
    return Fragment.OK()
}
.addScope(.user)
```

### DB boolean columns

SQLite has no native boolean type. Boolean fields are stored as `smallint` (0 = false, 1 = true). Always decode them as `Int` and convert:

```swift
let raw = try row.decode(column: "view_locked", as: Int.self)
let locked = raw != 0
```

Never attempt to decode a smallint column directly as `Bool` — it will fail at runtime.

When writing a boolean back, convert to int explicitly:

```swift
try await conn.sql().update("lines")
    .set("view_locked", to: SQLBind(locked ? 1 : 0))
    .where("id", .equal, SQLBind(id))
    .run()
```

In the schema, always declare boolean columns with `.default(0), .notNull` so that rows inserted without an explicit value never contain `NULL`, which would cause a decode failure at runtime:

```swift
.column("view_locked", type: .smallint, .default(0), .notNull)
.column("view_focused", type: .smallint, .default(0), .notNull)
```

### DB migrations

- **Always edit the latest migration file** — never create a new version until the current one has been deployed to production. Multiple iterations of a feature are accumulated in one version.
- When the current latest migration is deployed, create a new `vX_Y_Z.swift` file and register it in `Database.swift` in sequential order.
- SQLite requires **one column per `ALTER TABLE` statement**. Chain separate `.column(...).run()` calls for each new column:

```swift
try await sql.alter(table: "lines").column("view_focused", type: .smallint, .default(0), .notNull).run()
try await sql.alter(table: "lines").column("view_x",      type: .int,      .default(0), .notNull).run()
```

### Schema conventions
- Every FK column must have a corresponding index.
- Integer discriminators for enums: stored as `Int` raw values (e.g. `line_type`: 0=model, 1=replica, 2=subAssembly).
- Default new records to safe zero values for numeric columns (`view_x=0`, `view_y=0`, `view_locked=0`, `in_stock=0`, `reorder_point=0`).

### Returning a model from create
- Construct and return the model struct **directly from the inserted values** — do not query the DB again.
- Set all child collection properties (e.g. `intakeQueues`, `stations`, `managers`) to `[]` on creation.
- Set all optional properties (`theme`, `output`, `flowMetrics`) to `nil` on creation.

### Model hierarchy and dependent records
- Create models in dependency order: parent before child (e.g. `Company` → `Factory` → `Line`).
- When creating a child record, always use the actual ID returned from inserting the parent — never assume a hardcoded ID.
- Some models require **sibling records** on creation (additional rows in related tables inserted in the same service method). Check the app's `memory.md` for the specific sibling records required by that app's domain.

### Swift Tests (XCTest)

#### Test function setup
```swift
try await boss.start(storage: .memory)
```
This is always the first line of every test function.

#### Actors
- `superUser().user` — admin/super user
- `guestUser().user` — unauthenticated/guest user

#### Asserting errors
```swift
await XCTAssertError(
    try await api.lean.someMethod(...),
    api.error.RequiredParameter("fieldName")
)
```

#### Comment structure
```swift
// describe: [feature or model being tested]

// when: [condition]
// it: [expected outcome]
```

#### Test order
- Always test **negative/validation cases before** the happy path.
- Test `nil` before empty string; test empty string before valid values.

#### Numeric bounds testing

When a parameter has known numeric bounds, test each violated bound before the happy path:

1. Lower bound violation (value below minimum) — expects an error.
2. Upper bound violation (value above maximum) — expects an error.
3. Happy path — a valid value within the accepted range.

```swift
// when: x is negative
await XCTAssertError(
    try await api.lean.savePosition(user: user, id: id, x: -1, y: 0),
    service.error.InvalidInput("Position cannot be negative")
)

// when: y is negative
await XCTAssertError(
    try await api.lean.savePosition(user: user, id: id, x: 0, y: -1),
    service.error.InvalidInput("Position cannot be negative")
)

// when: x and y are valid
try await api.lean.savePosition(user: user, id: id, x: 5, y: 10)
let after = try await api.lean.fetch(user: user, id: id)
// it: should persist x and y
XCTAssertEqual(after.viewState.x, 5)
XCTAssertEqual(after.viewState.y, 10)
```

If only one bound is known, add only the test(s) for the known bound. **If bounds are not yet known, ask before writing any bound test.**

#### Boolean input testing

For boolean parameters, always test both `true` and `false` values:

```swift
// when: locking
try await api.lean.saveLocked(user: user, id: id, locked: true)
let afterLocked = try await api.lean.fetch(user: user, id: id)
// it: should persist locked = true
XCTAssertTrue(afterLocked.viewState.locked)

// when: unlocking
try await api.lean.saveLocked(user: user, id: id, locked: false)
let afterUnlocked = try await api.lean.fetch(user: user, id: id)
// it: should persist locked = false
XCTAssertFalse(afterUnlocked.viewState.locked)
```

#### What not to assert
- Do **not** assert that a primary key `> 0` (e.g. `XCTAssertGreaterThan(model.id, 0)`). A valid ID is an assumed postcondition of a successful insert; asserting it adds noise without catching real bugs.

#### Cascade testing for dependent models
- Create parent models first and use their returned IDs for child records.
- A single test function can cover the full hierarchy (e.g. Company → Factory → Line) to avoid boilerplate setup across tests.
- Validate `model.parentId == parent.id` to confirm the FK was stored correctly.

---

