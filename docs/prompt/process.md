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
5. **Stage 2 — Data Model** — full SQLite DDL (or equivalent), one table at a time, with inline comments on non-obvious columns
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

## When to Write Tests

Tests are written for the **Private APIs only** — that is where business rules live.

> **Note:** UI integration tests, and rules, will be added in the future.

Write a test when **three or more behaviors** can be exhibited for a given input (e.g., null check, empty string, size limit, uniqueness, success path). For a simple `if/then`, a test is not required. When unsure, ask before proceeding.

Always write tests for critical subsystems: authentication, notifications, shared helper functions.

## Test-First Approach

When tests are warranted, write them **before** the implementation.

- Tests encode business requirements in human-readable form using Gherkin style: `describe` (context), `when` (state), `it` (expected behavior).
- Write only the implementation logic sufficient to satisfy the current test.
- If a test only requires returning a value of `1`, return `1` — write database logic only when a test requires a database query.

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

---

## Development Log

Each entry records what was learned during a real project so the process can improve over time.

---

### 2026-07-25 — `io.bithead.scheduler` (Scheduler App)

**Established:** The pre-synthesis interview + plan.md workflow.

**What worked well:**
- Grouping 4 related interview questions per `vscode_askQuestions` call kept responses focused without fatigue.
- Producing a full written Design Summary after the interview created a shared record that caught missing topics (recurring jobs, write-off status, employee permissions, timezone handling) before any code was written.
- Writing `plan.md` with all 5 stages before synthesizing any file forced the data model, test cases, and endpoint signatures to be designed together — surfacing cross-cutting concerns (e.g., deposit_type on both job_type_sizes and job_transactions) early.

**Tradeoffs decided during interview:**
- Recurring jobs: rolling horizon (materialize within cutoff window) over full pre-commit.
- Vendor credentials: platform-level for now; Stripe is per-business via Connect OAuth.
- Employee permissions: per-employee flag over business-wide toggle or full RBAC.
- Payment states: `unpaid | deposit_paid | fully_paid | written_off` (separate `written_off` recommended and accepted for reporting accuracy).
- Customer contact info: read-only for operators if customer has a BOSS account; operator-editable otherwise.

**Open decisions carried forward:**
1. Holiday API provider (evaluate `nager.date` free tier first).
2. OTP code storage: `otp_hash` column on `job_sessions` vs. separate table.
3. Job code alphabet and length (suggested: 6-char uppercase A-Z0-9).
4. Stripe webhook exposure: public Python endpoint via reverse-proxy rule vs. Swift relay.
5. BOSS user search API endpoint for linking employee records.

**Process adjustments made:**
- Added Phase 0 (Design Interview) and Phase 1 (Write the Plan) to the process before the existing Development Order steps.
- Added this Development Log section so future sessions can see how the process evolved.

