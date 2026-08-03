# BOSS Development Process

## Pre-Synthesis Phases

These phases happen **before any code is written**. Complete them fully and in order.

### Phase 0 — Design Interview

Before synthesizing any artifact, interview the developer relentlessly until there is no ambiguity in the design. This is not a one-pass summary — it is a structured dialogue that surfaces every edge case, role, data model constraint, integration dependency, and UX behavior.

**Rules:**
- Use `vscode_askQuestions` for all interview questions. Group related questions (max 4 per call) so responses stay focused.
- Complete the interview before synthesizing code, schemas, or plans.
- If a question is skipped, ask it again in the next round.
- Flag open decisions explicitly rather than making assumptions.
- When the developer asks for your opinion on a design tradeoff, provide a brief rationale and a clear recommendation before asking them to decide.
- Once the interview is complete, produce a written **Design Summary** in the chat as a shared record of all decisions. Ask the developer to confirm or correct it before proceeding.

**Topics to cover in every interview (adapt depth to the project):**
- Roles and access levels
- Multi-tenancy or single-tenant
- Public-facing vs. admin-only surfaces
- Authentication and authorization rules
- Data ownership and editability
- Integration dependencies (payment, email, SMS, OAuth, external APIs)
- Slot/availability logic if scheduling is involved
- Notification triggers and channels
- Job/record lifecycle states
- Background job requirements
- Edge states (no data, expired sessions, failed OTP, etc.)
- Reporting and export needs
- MVP scope vs. future extensibility

---

### Phase 1 — Write the Plan

After the Design Summary is confirmed, write a `plan.md` to:

```
private/app/<bundle_id>/plan.md
```

**Format:** Markdown structured for machine readability. The plan is the implementation contract — it is referenced during every subsequent development stage.

**Required sections:**
1. **Identity** — bundle ID, scheme, backend stack, reference apps
2. **Roles & Access** — table of roles, how each is identified, access scope
3. **Deep-link routing** — URL patterns, `configure()` payloads, which controller each opens
4. **Stage 1 — UI/UX** — one subsection per controller: layout description, step/state machine, all stub endpoint signatures with method + path + return shape
5. **Stage 2 — Data Model** — full SQLite DDL (or equivalent), one table at a time, with inline comments on non-obvious columns, followed by the **network models** each Stage 1 endpoint returns. The endpoint return shapes in Stage 1 are those models; name them here so Stage 4 has them to build against.
6. **Stage 3 — TDD** — one test function per logical subsystem; each function lists `describe:` / `it:` cases including error paths
7. **Stage 4 — Backend Implementation** — file layout, responsibilities per file, key function signatures
8. **Stage 5 — Integration** — checklist of every endpoint group to replace (stub → real); done when Stage 3 tests pass against a real database
9. **Open Decisions** — numbered list of unresolved choices to address before Stage 4 begins

---

## System Layers

From top (user-facing) to bottom (data):

| Layer | Responsibility | Source |
|---|---|---|
| **Tactile surface** | UI/UX the user interacts with (`UIController`) | `public/boss/app/<bundle_id>/` |
| **BOSS OS** | Middleware for drawing and interaction. Almost exclusively written by humans. **Ask the developer before modifying this layer** — an existing API likely already covers the need. | `public/boss/` |
| **Public API** | Thin routing layer. Routes requests to the Private API. | `server/web/` (Swift), `private/` (Python) |
| **Private API** | Business rules, database access. Swift: `server/bosslib/`. Python: `private/app/<bundle_id>/`. | `server/bosslib/`, `private/app/<bundle_id>/` |

## Network and Domain Models

**Domain models** are what the app reasons about. We own them, we name them, and business rules take and return them.

**Network models** are how data looks outside the app. The other side owns the shape. A database row is a network model — the data could be stored any number of ways, and the table is one of them. So is the JSON a screen receives, and so is the body of a third-party API.

```
  database row ─┐
  external API ─┼──▶ domain model ──▶ the client
   (network)    ┘      (ours)
   snake_case          camelCase
```

The client is handed the domain model itself. There is no separate model for the wire out, because the domain model's shape is already dictated by its consumer — the app layer's job is to query, join, and shape the data into something convenient for the screen that reads it.

**Domain models are `camelCase`.** That is our convention, so it does not bend to whatever a given outside party uses.

**Network models take whatever case that party uses.** A database row model is `snake_case`, because that is the column convention — declare its fields as the columns are spelled, so constructing one from a row is a splat and nothing else.

The two families need not correspond one-to-one. One domain model may be assembled from several joined rows, and one table may feed several domain models — a list row and a detail view are different shapes because different screens read them. Expect more network models than domain models, and sometimes the reverse.

**Incoming request bodies are domain models**, grouped under an *Input Models* heading. The client dictates their shape too.

Declare both even where the fields currently match, because they change for different reasons. Renaming a column is a storage decision and must not reach the client. Adding a count a dashboard wants is a presentation decision and must not become a column. A row model also states what the store actually hands back — SQLite has no boolean, so `active` arrives as an `int` and becomes a `bool` on the way in. Sharing one type hides that, and scatters the coercion across every call site.

**Rules:**
- The data layer owns its network models and knows nothing about the domain. It does not import the domain models.
- The app layer owns the conversion. It imports both, and turns rows into domain models once per concept rather than once per call site.
- Give a domain model exactly the fields its consumer reads. A field nothing consumes will drift.
- Name a network model for the query or payload it came from — `JobRow`, `LineResourceRow`. Name a domain model for what it is to us — `Job`, `JobDetail`, `LineState`.
- A query returning one column returns a list of values. A scalar is not a shape and does not need a model.
- In Python both families are Pydantic `BaseModel`s (see `python.md` §19). In Swift both are `Codable`.

## When to Write Tests

The two suites answer different questions, and neither should try to answer the other's.

**Private API tests** prove the **rules**. Write one when **three or more behaviours** can be exhibited for a given input (null check, empty string, size limit, uniqueness, success path). A simple `if/then` needs none. Always test critical subsystems: authentication, notifications, shared helper functions.

**UI tests** prove the **wiring** — that a screen calls the right endpoint and puts the answer in the right place. Keep them to happy flows plus a little edge-case cover. They are not a second place to test business logic: that a requeue jumps the queue is settled by the private suite, and asserting it again through a browser is slower, flakier, and no more true.

The distinction is what keeps a UI suite worth running. A test that clicks through a rule can only fail for reasons the private suite already reports faster, so it costs time and tells you nothing new. A test that clicks Save and checks the row appeared catches the whole class of defect the private suite is blind to: a renamed field, a call sent to the wrong path, a response nobody reads.

## Test-First Approach

When tests are warranted, write them **before** the implementation.

- Tests encode business requirements in human-readable form using Gherkin style: `describe` (context), `when` (state), `it` (expected behavior).
- Write only the implementation logic sufficient to satisfy the current test.
- If a test only requires returning a value of `1`, return `1` — write database logic only when a test requires a database query.

## Development Order

Always develop **top to bottom** — the UI defines what the backend actually needs. This prevents over-engineering lower layers.

### Steps (complete each step fully before moving to the next; stop and wait for confirmation between steps)

1. **Define UI/UX** — Create the tactile surfaces (windows, modals, forms). Stub every network call with static data:
   ```javascript
   const friends = [{ id: 1, name: "Alice" }];
   ```

   The plan records each stub endpoint with its method, path, and return shape, and the Stage 5 checklist tracks which are still stubbed. That is where a reader looks to find out what is real.

2. **Implement BOSS OS features** — Only if new OS-level support is needed and approved by the developer.

3. **Implement Public API routes** — Create the backend routes from the stub endpoints the plan records. Replace stubbed client data with real API calls. This finalizes the client integration.

4. **Write tests** — Working only in the Private API, write tests that encode the business requirements for each route.

5. **Write implementation** — Write logic to satisfy the tests, nothing more.

6. **Reconcile the client with the models** — Step 1 built the controllers against invented fixtures. By the time the real models exist, the two have drifted: a field was renamed, a list lost its envelope, a computed value moved to the server. The routes still resolve and the calls still succeed, so nothing fails loudly — the screen simply renders blanks.

   Run `bin/validate-app <bundle>`, which compares every field a controller reads off a response against what the models declare. Fix the client where the model is right, and the model where the client is right; say which you chose and why.

7. **Write UI tests** — Only once the app runs against a live service and a first pass has confirmed the screens draw.

   Write a `ui-plan.md` beside the app's `plan.md` first. `plan.md` is the implementation contract; `ui-plan.md` is the coverage contract — the flows to cover, in order, each saying what it must prove, plus a status table. UI testing is long and interruptible, so the plan is what lets it stop and resume: the table says what is done, and no one has to remember a conversation.

   Each flow becomes one spec file. Update its status in the same commit as the spec, and record any defect it turns up under **Findings**, so the next session can tell a gap in coverage from a gap in the app.

   Finish each flow with a changelog the developer can paste into a commit or pull request. One bullet per change, one line each, unwrapped. Say what changed, not which files — the diff already names those.

   Run the flow's own spec while writing it — the whole suite takes minutes and most of it cannot be affected by the line just typed. Then run every test at the end of the step, without exception: flows share an OS, a server, and a database, and what one breaks for another shows up nowhere else.

   Keep to wiring, not rules — see "When to Write Tests" above, and `uitest/README.md` for signing in and seeding.

### After each step — close the gaps

Before moving to the next step, review what consumed the most time and convert it into a durable fix, so the same cost is not paid twice.

Ask: **what did I spend time on that was not the work itself?** Then fix the cause.

| What cost the time | The fix |
|---|---|
| Rediscovering an API by reading OS source | Regenerate or extend the index (`bin/boss-api`), and add a pointer wherever you looked first |
| A defect that only surfaced at runtime | Add a check to `bin/validate-app` |
| Not knowing how to run or exercise something | Document it in `shared.md` |
| A document that existed but went unread | Fix the routing (`AGENTS.md` triggers), not the document |
| A document that was wrong, missing, or ambiguous | Fix the document |
| A convention rediscovered from another app's `plan.md` | Promote it into `docs/prompt/` and leave a pointer behind |

Rules:
- **Fix the cause, not the instance.** A corrected call site helps once; a check that catches every call site helps forever.
- **Prefer a tool to a document, and a document to a habit.** A tool enforces, a document informs, a habit decays.
- **Keep no incident log.** The fix is the record. A description of what went wrong helps nobody build the next app, and it is carried into every future session as dead prompt context.

---

## Debugging Visual Issues

For visual bugs (missing pixels, alignment problems, clipping, shadow rendering), ask the developer to inspect the rendered component in browser DevTools before proposing any fix.

The right workflow:
1. Developer opens the affected component in the browser
2. Developer opens DevTools, selects the specific element where the visual issue appears
3. Developer shares what the Styles panel shows — the computed CSS values on that element and which rule is applying them
4. Based on that evidence, propose one targeted fix

Reasoning from code structure alone cannot determine whether a missing pixel is a clipping issue, a border issue, a shadow issue, or a margin issue. Each has a different fix. DevTools inspection takes two minutes and gives a definitive answer.
