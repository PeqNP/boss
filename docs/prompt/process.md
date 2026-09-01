# BOSS Development Process

## Pre-Synthesis Phases

These phases happen **before any code is written**. Complete them fully and in order.

### Phase 0 — Design Interview

Before synthesizing any artifact, interview the developer relentlessly until the design is unambiguous. It is a structured dialogue, surfacing every edge case, role, data model constraint, integration dependency, and UX behavior.

**Rules:**
- Use `vscode_askQuestions` for all interview questions. Group related questions (max 4 per call) so responses stay focused.
- Complete the interview before synthesizing code, schemas, or plans.
- If a question is skipped, ask it again in the next round.
- Flag open decisions explicitly, and let the developer settle them.
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
2. **Roles & Access** — table of roles, how each is identified, access scope, followed by **who reaches each page** (see below)
3. **Deep-link routing** — URL patterns, `configure()` payloads, which controller each opens
4. **Stage 1 — UI/UX** — one subsection per controller: its audience, layout description, step/state machine, all stub endpoint signatures with method + path + return shape + ACL name + scoping rule
5. **Stage 2 — Data Model** — full SQLite DDL (or equivalent), one table at a time, with inline comments on non-obvious columns, followed by the **network models** each Stage 1 endpoint returns. The endpoint return shapes in Stage 1 are those models; name them here so Stage 4 has them to build against.
6. **Stage 3 — TDD** — one test function per logical subsystem; each function lists `describe:` / `it:` cases including error paths
7. **Stage 4 — Backend Implementation** — file layout, responsibilities per file, key function signatures
8. **Stage 5 — Integration** — checklist of every endpoint group to replace (stub → real); done when Stage 3 tests pass against a real database
9. **Open Decisions** — numbered list of unresolved choices to address before Stage 4 begins

#### Name the actors and what each reaches

Before the pages, the plan names every actor an app has, in a table of five
columns:

| Column | What goes in it |
|---|---|
| Actor | The name the app uses for them, in its own vocabulary |
| Told by | What the service reads to know which actor is calling |
| Scope | The record its other records hang off, and where the route gets it |
| Reaches | What they read and write inside that scope |
| Narrowed by | What limits them further, inside their own scope |

An app with one kind of user has one row. An app whose users never share
anything has no scope column worth filling in. The table is as long as the app
is, and writing it is what finds the actor nobody had named.

**Narrowed by** is the column that earns the table. It is what a route
implements beyond "may act in this scope", and each entry is a sentence —
*their own record*, *the ones assigned to them*, *while a flag is set*. Three
is a lot; more than that is a sign two actors have been written as one.

Every page and every endpoint below is consistent with this table. A page
reaching records its actor's row does not is a question to settle here, before
Stage 1 names a route.

From `io.bithead.scheduler`, whose scope is a business:

| Actor | Told by | Scope | Reaches | Narrowed by |
|---|---|---|---|---|
| Super admin | BOSS user id 1 | any, named in the path | every record | — |
| Operator | `employees.role = operator` | the one they run | every record of it | — |
| Employee | `employees.role = employee` | the one they work for | their own record, and jobs assigned to them | `canManageOwnSchedule` |
| Customer | an account with no `employees` row | none | their own appointments | — |
| Anonymous | no account | named in the path | the booking a job code opens | a verified code |

#### Say who reaches each page

The Roles & Access table names the roles. The inventory beneath it maps them to
pages: one row per controller, naming the audience that opens it and what
opens it.

A page two actors reach gets a row of its own naming both, and a sentence
saying which records the caller may reach. That sentence comes from the
**Narrowed by** column, and Stage 4 implements it as one call.

Carry the actor into Stage 1. Each controller's subsection opens with it, and
every endpoint signature carries three things beside its shape — its ACL name,
the actors that reach it, and the call that decides which records answer:

```
GET /business/{businessId}/employee/{employeeId} -> Employee
    acl:   employee.r
    who:   Operator, Employee
    scope: is_working_for_business(businessId, user)
```

A route with an audience has a guard, a name to grant, and a rule that decides
which records answer. Reviewing the endpoint list at the end of Stage 1 is
where a route serving two audiences is found — while it is three lines in a
document, rather than after it is written, wired to a screen, and reachable.

**The scope is named in the path, and checked.** `/business/{businessId}/…`
in the scheduler, `/project/{projectId}/…` in something else — for every route
an actor reaches by belonging to that scope. The check is the sentence from
the actor table, and one route then answers for every actor who may reach it.

A caller holding a token rather than a membership takes the scope from the
record instead: a booking opened by a job code names the business it is for.

#### Name the documents while planning

Stage 1 lists every controller. For each window, say in the plan whether it is a
**document** — see [`js.md` § Document windows](js.md#document-windows). A
window that edits one record and offers Cancel, Delete or Save is one, and
declaring it hands those actions to the OS.

Decide it here, while the plan is being written. The choice reaches into the
markup and the controller together — the OS supplies the File menu, the Enter
key, and the confirmations, and the controller supplies `doc-action` in place of
`onclick` and a `save()` returning a boolean.

**It is a document if it edits one record and has a controls row.** That covers
almost every add/edit form in an app.

**These are windows in their own right:**

| Window | What it is |
|---|---|
| A modal | A dialog; `showMessage` and the generated File menu both want `.ui-window` |
| A control panel that saves as the user works | Every field is already committed, so Save has nothing left to confirm or discard |
| A list, dashboard, report or search | A view over records |
| A multi-step flow — a kiosk, a wizard | The steps are the shape, and each one commits as it passes |

**Where it is ambiguous, ask the developer.** These are the cases that come up:

- One record, but only a **Save** — a settings screen with a single field.
  Usually still a document: it earns the discard question and "Saved".
- A screen whose parts **save themselves**, with one control left over —
  ask whether the leftover is a document Save or a plain button.
- A form that edits one record but is opened as a **modal** — ask whether it
  should be a window instead, which is where a document's behavior lives.
- A record with an action **beside** the three — Mark Complete, Duplicate,
  Send. It is still a document; the extra button keeps its own `onclick`.
  Confirm which of the buttons are the document's.

Record the answer in the plan, along with every control beyond the three and
every label that departs from Cancel/Delete/Save.

`bin/validate-app` warns when a window's controls row holds a Save that writes
a record and the controller declares no `this.document`. Answer it by declaring
the document, or by recording in the plan which kind of window this is.

#### Say which documents draft themselves on open

A child belongs to a parent that exists. A document holding a list of children
— a job type's sizes, an employee's working days — has nothing to add them to
until its own record has an ID, so it creates one as the form opens: a draft
with a placeholder name, discarded if the user cancels. The pattern and its
cost are in
[`js.md` § A form that owns a list creates its model up front](js.md#a-form-that-owns-a-list-creates-its-model-up-front).

**Decide this in planning — it constrains Stage 2.** A draft is created from a
placeholder name and nothing else, so every other column on that table is
nullable or carries a default. Deciding it while writing the DDL is what makes
the schema fit the form.

Stage 1 carries a table of parents, their children, and the modal that edits
each, saying which parents draft on open. A form holding only its own fields
saves once, at the end.

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
  slot held, an external record. The answer here may be to keep the children in
  the payload and save once.

---

## System Layers

From top (user-facing) to bottom (data):

| Layer | Responsibility | Source |
|---|---|---|
| **Tactile surface** | UI/UX the user interacts with (`UIController`) | `public/boss/app/<bundle_id>/` |
| **BOSS OS** | Middleware for drawing and interaction. Almost exclusively written by humans. **Ask the developer before modifying this layer** — an existing API likely already covers the need. | `public/boss/` |
| **Public API** | Thin routing layer. Routes requests to the Private API. | `server/web/` (Swift), `private/` (Python) |
| **Private API** | Business rules, database access. Swift: `server/bosslib/`. Python: `private/app/<bundle_id>/`. | `server/bosslib/`, `private/app/<bundle_id>/` |

### One app, one backend — write it in Python

An app's backend is Python or Swift. Choose Python.

Swift is for BOSS subsystems — accounts, sessions, ACL, notifications: the
parts every app sits on. It is harder to deploy, and a change there rebuilds
and restarts the whole server. Python is what an app is written in.

**Never write both for one app.** Authorization is not built for it. A backend
registers what its app has — its features, and the roles that reach them — and
BOSS rebuilds that app's record from what arrived. Two backends registering one
bundle each rebuild the other's, so whichever registered last is what the app
has, and nothing reports the loss.

If an app needs something only Swift can reach, that thing belongs in a BOSS
subsystem the Python service calls. The app still has one backend.

### The tactile surface decides nothing

Every business rule lives in the Private API. The screen is a dumb interface:
it collects what the user typed, sends it, and draws what comes back.

The test is whether the answer could differ between two callers who send the
same request. If it could, the server decides — it owns the clock, the
database, and the rules, and it is the one layer beyond the reach of whoever is
looking at the page.

| The screen asks | The version written first |
|---|---|
| "may this person close the kiosk?" — the server answers `isOperator` | comparing the signed-in user against the business |
| "is this appointment past its change window?" — the server answers `changesClosed` | comparing the appointment's time against the browser's clock |
| "which of these times is the soonest?" — the server marks one slot `asap` | assuming the first slot in the list must be the soon one |
| "what was actually sent?" — the server answers `confirmationSentTo` | inferring it from the business's notification settings |

Each of those was written the second way first. The client held part of what
the decision needed.

What the screen may decide for itself is presentation, and one courtesy:

- **Empty required fields.** Checking a field has something in it before
  sending saves a round trip. Every other rule — length, format, range,
  uniqueness, permission, timing — is the server's, and the server enforces it
  whether or not the screen checked. See
  [`swift.md`](swift.md) § Client-side validation.
- **What to show.** Hiding a button because the response said `locked`,
  formatting a phone number, choosing a step to display. The rule came from the
  server; the drawing is the screen's.

A rule lives in one place, and that place is the server.

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

The second half re-derives the first, and the definition of *configured* comes
to live in two places while the server's is the one that changes when the rule
does.

**When a payload carries a conclusion, that field is the answer.** Say so in
the plan when a response has both, naming which is authoritative.

#### Transport failures and contract violations

Both are written as defensive code:

```javascript
catch {
  return "OperatorDashboard";     // ✓ the request failed; not knowing is a real state
}
if (setup.configured || setup.tasks.length === 0) { … }   // ✗ the server contradicting itself
```

A request can fail, time out, or answer 500 — handle it. A server answering
`configured: false` with no tasks is a **bug in the service**. Let it throw: a
loud failure on a launch path is the one that gets fixed.

Ask which of the two you are defending against. Where the answer is "the
backend being wrong", fix the backend or agree the contract.

## Network and Domain Models

**Domain models** are what the app reasons about. We own them, we name them, and business rules take and return them.

**Network models** are how data looks outside the app. The other side owns the shape. A database row is a network model — the data could be stored any number of ways, and the table is one of them. So is the JSON a screen receives, and so is the body of a third-party API.

```
  database row ─┐
  external API ─┼──▶ domain model ──▶ the client
   (network)    ┘      (ours)
   snake_case          camelCase
```

The client is handed the domain model itself. Its shape is already dictated by its consumer — the app layer queries, joins, and shapes the data into what the screen reading it wants.

**Domain models are `camelCase`**, throughout, whatever case an outside party uses.

**Network models take whatever case that party uses.** A database row model is `snake_case`, matching the column convention — declare its fields as the columns are spelled, and constructing one from a row is a splat.

The two families correspond loosely. One domain model may be assembled from several joined rows, and one table may feed several domain models — a list row and a detail view are different shapes for different screens. Expect more network models than domain models, and sometimes the reverse.

**Incoming request bodies are domain models**, grouped under an *Input Models* heading. The client dictates their shape too.

Declare both even where the fields currently match. They change for different reasons: renaming a column is a storage decision and stops at the data layer, while adding a count a dashboard wants is a presentation decision and stops at the domain model. A row model also states what the store hands back — SQLite has no boolean, so `active` arrives as an `int` and becomes a `bool` on the way in, in one place.

**Rules:**
- The data layer owns its network models and imports nothing from the domain.
- The app layer owns the conversion. It imports both, and turns rows into domain models once per concept rather than once per call site.
- Give a domain model exactly the fields its consumer reads. A field nothing consumes will drift.
- Name a network model for the query or payload it came from — `JobRow`, `LineResourceRow`. Name a domain model for what it is to us — `Job`, `JobDetail`, `LineState`.
- A query returning one column returns a list of values.
- In Python both families are Pydantic `BaseModel`s (see `python.md` §19). In Swift both are `Codable`.

## When to Write Tests

The two suites answer different questions, and each stays with its own.

**Private API tests** prove the **rules**. Write one when **three or more behaviours** can be exhibited for a given input (null check, empty string, size limit, uniqueness, success path). A simple `if/then` needs none. Always test critical subsystems: authentication, notifications, shared helper functions.

**UI tests** prove the **wiring** — that a screen calls the right endpoint and puts the answer in the right place. Keep them to happy flows plus a little edge-case cover. Business logic is settled by the private suite: that a requeue jumps the queue is answered there, faster.

A UI test earns its place by catching the class of defect the private suite is blind to — a renamed field, a call sent to the wrong path, a response nobody reads. It clicks Save and checks the row appeared.

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

   Where dependency leaves two models at the same level, or the menu lists
   actions in place of models, ask the developer. Menu order is the first thing
   a user reads, and worth deciding on purpose.

   **Build every form the plan calls a document as one**, following
   [`js.md` § Document windows](js.md#document-windows). Where the plan is
   silent — an older plan, or a window nobody thought about — apply the test in
   Phase 1 now, and ask where it stays ambiguous.

   **Finish the step before leaving it.** A screen agreed on part-way through
   — one that arrives from a conversation about something else — belongs to
   this step whatever else has already been called complete. Add it to the plan
   and build it now, so the plan and the app describe the same thing.

   `bin/validate-app` reports every controller `plan.md` describes and the app
   has yet to register. Run it before calling this step finished, and again
   before step 3.

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
   Say which, per row.

   Step 1 built the controllers against invented fixtures. By the time the real models exist, the two have drifted: a field was renamed, a list lost its envelope, a computed value moved to the server. The routes still resolve and the calls still succeed, so the screen renders blanks.

   Run `bin/validate-app <bundle>`, which compares every field a controller reads off a response against what the models declare. Fix the client where the model is right, and the model where the client is right; say which you chose and why.

7. **Write UI tests** — Only once the app runs against a live service and a first pass has confirmed the screens draw.

   Write a `ui-plan.md` beside the app's `plan.md` first. `plan.md` is the implementation contract; `ui-plan.md` is the coverage contract — the flows to cover, in order, each saying what it must prove, plus a status table. UI testing is long and interruptible, so the plan is what lets it stop and resume: the table says what is done, and no one has to remember a conversation.

   Each flow becomes one spec file. Update its status in the same commit as the spec, and record any defect it turns up under **Findings**, so the next session can tell a gap in coverage from a gap in the app.

   Finish each flow with a changelog the developer can paste into a commit or pull request. One bullet per change, one line each, unwrapped. Say what changed, not which files — the diff already names those.

   Run the flow's own spec while writing it — the whole suite takes minutes and most of it cannot be affected by the line just typed. Then run every test at the end of the step, without exception: flows share an OS, a server, and a database, and what one breaks for another shows up nowhere else.

   Keep to wiring, not rules — see "When to Write Tests" above, and `uitest/README.md` for signing in and seeding.

### After each step — close the gaps

Before moving to the next step, review what consumed the most time and convert it into a durable fix.

Ask: **what took time beyond the work itself?** Then fix the cause.

| What cost the time | The fix |
|---|---|
| Rediscovering an API by reading OS source | Regenerate or extend the index (`bin/boss-api`), and add a pointer wherever you looked first |
| A defect that only surfaced at runtime | Add a check to `bin/validate-app` |
| A mistake made twice | A check in `bin/`, run from `bin/check` |
| Deciding *how* to check something, each time | A `bin/` command that decides it once |
| Not knowing how to run or exercise something | Document it in `shared.md` |
| A document that existed but went unread | Fix the routing (`AGENTS.md` triggers), not the document |
| A document that was wrong, missing, or ambiguous | Fix the document |
| A convention rediscovered from another app's `plan.md` | Promote it into `docs/prompt/` and leave a pointer behind |

Rules:
- **Fix the cause, not the instance.** A corrected call site helps once; a check that catches every call site helps forever.
- **Prefer a tool to a document, and a document to a habit.** A tool enforces, a document informs, a habit decays.
- **A mistake made twice earns a check.** The second time is the signal: once is carelessness, twice says the shape of the work invites it.
- **Extend a check before writing one.** A new command is for a question the existing ones have no place to ask.
- **The fix is the record.** It travels with the code, where the next session meets it.

#### What a check has to be

- **It fails closed.** When it cannot read what it compares, it says so.
  A check that answers "nothing found" from an empty input reads as success to
  one person and as catastrophe to the next, and is wrong for both.
- **It gives the same answer from anywhere.** Resolve paths from the script's
  own location, so the directory it was run from changes nothing.
- **It runs from `bin/check`.** A check somebody remembers to run informs; a
  check in the pipeline enforces.
- **It is validated against everything that exists** before it is kept. A false
  positive marks a missing piece of your model of the system, and is worth
  understanding — nginx forking workers, a template literal's inner `+`.
- **Its severity is what breaks.** Ask what goes wrong for the developer if it
  is ignored. Where something breaks, it is an error; where the form is merely
  irregular, a warning; the rest is silence.

---

## Debugging Visual Issues

A missing pixel is a clip, a border, a shadow, or a margin, and each has its
own fix. Looking at what was rendered is what tells them apart.

Look with a probe: a throwaway spec that opens the one controller involved,
dumps the element's geometry and the styles governing it, and takes a
screenshot. The developer describes what looks wrong; everything after that is
measured. The workflow, the helpers, and the rule that the probe becomes a
regression test once the fix lands are in
[`uitest/README.md`](../../uitest/README.md) § "Diagnosing a visual bug".

The developer starts the servers — see "Running and Validating Locally" in
[`shared.md`](shared.md). Confirm they are up before probing.
