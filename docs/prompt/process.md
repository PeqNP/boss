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

#### Name the documents while planning

Stage 1 lists every controller. For each window, say in the plan whether it is a
**document** — see [`js.md` § Document windows](js.md#document-windows). A
window that edits one record and offers Cancel, Delete or Save is one, and
declaring it hands those actions to the OS.

Decide it here rather than while writing the controller. The choice reaches into
the markup and the controller together — no File menu, no `didHitEnter`,
`doc-action` in place of `onclick`, a `save()` that returns a boolean, a
`cancel` and `delete` that do not ask — so a window hand-rolled first and
converted later is a rewrite of both, and every form that gets it wrong asks a
different question in different words.

**It is a document if it edits one record and has a controls row.** That covers
almost every add/edit form in an app.

**It is not a document if:**

| Not a document | Why |
|---|---|
| A modal | A dialog is not a document window; `showMessage` and the generated File menu both need `.ui-window` |
| A control panel that saves as the user works | Nothing to Save, so nothing to confirm or discard |
| A list, dashboard, report or search | Edits no record |
| A multi-step flow — a kiosk, a wizard | No single record with a Save; the steps are the shape |

**Where it is not obvious, ask the developer.** The cases that need asking are
real ones, not hypothetical:

- One record, but only a **Save** — a settings screen with a single field.
  Usually still a document: it earns the discard question and "Saved".
- A screen whose parts **save themselves**, with one control left over —
  ask whether the leftover is a document Save or a plain button.
- A form that edits one record but is opened as a **modal** — ask whether it
  should be a window instead, rather than hand-rolling a document's behavior
  inside a dialog.
- A record with an action **beside** the three — Mark Complete, Duplicate,
  Send. It is still a document; the extra button keeps its own `onclick`.
  Confirm which of the buttons are the document's.

Record the answer in the plan, with any control that is not one of the three
and any label that differs from Cancel/Delete/Save.

`bin/validate-app` warns when a window's controls row holds a Save that writes
a record and the controller declares no `this.document`. It is a warning
because the exceptions are real — answer it by declaring the document or by
saying in the plan why this window is not one.

#### Say which documents draft themselves on open

A child belongs to a parent that exists. A document holding a list of children
— a job type's sizes, an employee's working days — has nothing to add them to
until its own record has an ID, so it creates one as the form opens: a draft
with a placeholder name, discarded if the user cancels. The pattern and its
cost are in
[`js.md` § A form that owns a list creates its model up front](js.md#a-form-that-owns-a-list-creates-its-model-up-front).

**This is a planning decision because it constrains Stage 2.** A draft is
created from a placeholder name and nothing else, so every other column on that
table must be nullable or carry a default. Decide it while writing the DDL and
the schema simply works; decide it while writing the controller and the `POST`
fails against columns already declared `NOT NULL` with nothing to put in them.

Stage 1 should carry a table of parents, their children, and the modal that
edits each — and say which parents draft on open and which deliberately do not.
A form with only its own fields has nothing to create early and must not.

**Ask the developer when:**

- **A draft would be visible to someone else.** The row exists before anyone
  meant to keep it, and a status column defaulting to active is enough to put a
  half-written record in front of a customer. Ask whether drafts are excluded
  from the surfaces that read that table, or whether the default should be
  inactive until the first real save.
- **Abandoned drafts accumulate.** Cancel and the close box discard one, but a
  closed browser does not. Ask whether they are swept, and after how long.
- **The parent is created by another flow.** Scheduler's `Customer` is created
  by booking, so its form never creates one and its notes always have a parent
  already.
- **Creating the parent has an effect beyond the row** — a notification, a
  slot held, an external record. Drafting is not free, and the answer may be to
  keep the children in the payload after all.

---

## System Layers

From top (user-facing) to bottom (data):

| Layer | Responsibility | Source |
|---|---|---|
| **Tactile surface** | UI/UX the user interacts with (`UIController`) | `public/boss/app/<bundle_id>/` |
| **BOSS OS** | Middleware for drawing and interaction. Almost exclusively written by humans. **Ask the developer before modifying this layer** — an existing API likely already covers the need. | `public/boss/` |
| **Public API** | Thin routing layer. Routes requests to the Private API. | `server/web/` (Swift), `private/` (Python) |
| **Private API** | Business rules, database access. Swift: `server/bosslib/`. Python: `private/app/<bundle_id>/`. | `server/bosslib/`, `private/app/<bundle_id>/` |

### The tactile surface decides nothing

Every business rule lives in the Private API. The screen is a dumb interface:
it collects what the user typed, sends it, and draws what comes back.

The test is whether the answer could differ between two callers who send the
same request. If it could, the server has to decide — it owns the clock, the
database, and the rules, and it is the only layer that cannot be edited by
whoever is looking at the page.

| The screen asks | Rather than |
|---|---|
| "may this person close the kiosk?" — the server answers `isOperator` | comparing the signed-in user against the business |
| "is this appointment past its change window?" — the server answers `changesClosed` | comparing the appointment's time against the browser's clock |
| "which of these times is the soonest?" — the server marks one slot `asap` | assuming the first slot in the list must be the soon one |
| "what was actually sent?" — the server answers `confirmationSentTo` | inferring it from the business's notification settings |

Each of those was written the wrong way round first, and each was wrong for the
same reason: the client had only part of what the decision needed.

What the screen may decide for itself is presentation, and one courtesy:

- **Empty required fields.** Checking a field has something in it before
  sending saves a round trip. Every other rule — length, format, range,
  uniqueness, permission, timing — is the server's, and the server enforces it
  whether or not the screen checked. See
  [`swift.md`](swift.md) § Client-side validation.
- **What to show.** Hiding a button because the response said `locked`,
  formatting a phone number, choosing a step to display. The rule came from the
  server; the drawing is the screen's.

A rule implemented in both places is worse than a rule implemented in one. The
copies drift, and the copy the user can edit is the one that stops matching.

#### Read the conclusion, not the evidence beside it

A response often carries both — a conclusion and the data it was drawn from:

```json
{ "configured": false, "tasks": [ … ] }
```

`configured` **is** `tasks == []`, decided once, on the server. So this is
already wrong:

```javascript
if (setup.configured || setup.tasks.length === 0) {   // ✗
```

The second half re-derives the first. Nothing looks like business logic while
you are writing it — it looks like being careful — but the definition of
*configured* now lives in two places, and only one of them is the one that
changes when the rule does.

**When a payload carries a conclusion, that field is the answer.** Say so in
the plan when a response has both, so a reader knows which is authoritative.

#### Guarding transport is not guarding the contract

This is the distinction that makes the above easy to get wrong, because both
are written as defensive code and only one of them is:

```javascript
catch {
  return "OperatorDashboard";     // ✓ the request failed; not knowing is a real state
}
if (setup.configured || setup.tasks.length === 0) { … }   // ✗ the server contradicting itself
```

A request can fail, time out, or answer 500 — handle it. A server answering
`configured: false` with no tasks is a **bug in the service**, and a client
branch that quietly copes with it hides the bug and duplicates the rule in the
same stroke. Let it throw. A loud failure on a launch path gets fixed; a silent
fallback to the dashboard does not.

Ask which you are defending against. If the answer is "the backend being
wrong", stop and fix the backend, or agree the contract.

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

   **Order a menu by what depends on what.** The model everything else hangs
   off comes first, then the models that belong to it. Scheduler's `Manage`
   opens with Business Settings because a job type, an employee and a customer
   all belong to a business — even though each is edited on its own, and a
   customer never thinks about the business record while doing it.

   Where dependency does not settle it — two models at the same level, or a
   menu of actions rather than models — ask the developer. Menu order is the
   first thing a user reads and the last thing anyone decides on purpose.

   **Build every form the plan calls a document as one**, following
   [`js.md` § Document windows](js.md#document-windows). If the plan does not
   say — an older plan, or a window nobody thought about — apply the test in
   Phase 1 now and ask if it is not obvious, rather than hand-rolling a form
   whose Cancel asks a question of its own invention.

   **Finish the step before leaving it.** A screen agreed on part-way through
   — one that arrives from a conversation about something else — belongs to
   this step whatever else has already been called complete. Add it to the
   plan and build it now; a plan that describes a screen nobody built reads as
   done and is not.

   `bin/validate-app` reports a controller `plan.md` describes and the app does
   not register. Run it before calling this step finished, and again before
   step 3.

2. **Implement BOSS OS features** — Only if new OS-level support is needed and approved by the developer.

3. **Implement Public API routes** — Create the backend routes from the stub endpoints the plan records. Replace stubbed client data with real API calls. This finalizes the client integration.

4. **Write tests** — Working only in the Private API, write tests that encode the business requirements for each route.

5. **Write implementation** — Write logic to satisfy the tests, nothing more.

6. **Reconcile the client with the models**, and the models with each other.

   Before this step is finished, list every group of models sharing a field
   set and decide each one — see
   [`python.md` § Models that share a shape](python.md#models-that-share-a-shape).
   One table, one row per group:

   | Models | Fields | Suggested name | Replace |
   |---|---|---|---|

   Most duplicates are one model written twice, usually because a `POST` and a
   `PUT` returning the same thing each took a name from its route. Some are two
   ideas that coincide, and the names are the only thing keeping them apart.
   Say which, per row, rather than merging on sight.

   Step 1 built the controllers against invented fixtures. By the time the real models exist, the two have drifted: a field was renamed, a list lost its envelope, a computed value moved to the server. The routes still resolve and the calls still succeed, so nothing fails loudly — the screen simply renders blanks.

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

Reasoning from code structure cannot decide whether a missing pixel is a clip, a
border, a shadow, or a margin. Each has a different fix, and the only way to
tell them apart is to look at what was actually rendered.

Look at it with a probe: a throwaway spec that opens the one controller
involved, dumps the element's geometry and the styles governing it, and takes a
screenshot. The developer describes what looks wrong; everything after that is
measured rather than guessed. The workflow, the helpers, and the rule that the
probe is replaced by a regression test once the fix lands are in
[`uitest/README.md`](../../uitest/README.md) § "Diagnosing a visual bug".

The developer starts the servers — see "Running and Validating Locally" in
[`shared.md`](shared.md). A probe against a service that is not running proves
nothing, so confirm they are up rather than standing one up.
