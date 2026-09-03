# Setting Up a Business — Implementation Plan

Queued behind `plan.md`. Nothing here starts until that plan is finished.

## Identity

Bundle: `io.bithead.scheduler`. No new tables. One controller is deleted, one
route gains a caller, and BOSS gains a way to re-mint a session.

## The problem

`OperatorSignup` asks for what `BusinessConfig` already asks for.

| `OperatorSignup` step | Already in `BusinessConfig` |
|---|---|
| `business` — `biz-name`, `biz-phone`, `owner-name`, `address-line1`, `city`, `state`, `zip` | the `general` tab, under the same input names |
| the timezone it sends | the `general` tab's `timezone` menu |
| `template` — pick a business template | the `business-type` tab |
| `account` — a prompt to sign in | BOSS signs a user in before any app window opens |

An owner fills in one form to create the business and a second, identical one
to change it. A field added to either has to be added to the other.

`SetupAssistant` already does the guiding. It is the one place that shows state
across controllers and links each outstanding thing to the window that fixes
it, including `Give your business a name → BusinessConfig, general`.

## What replaces it

The business is created for an operator when the app loads. `SetupAssistant`
and `BusinessConfig` open, and the assistant asks for the name.

`BusinessConfig` is unchanged. No new tab states, no creation on save, no
guidance inside it — that is the assistant's job and duplicating it is what
this plan removes.

## Stage 1 — UI/UX

### 1.1 The business is created on load

`applicationDidStart` already calls `POST /reconcile`. The same call creates
the business when the signed-in user has no `employees` row.

An employee is linked by an operator before they ever sign in, so they have a
row already. Anyone without one is nobody's employee, and is treated as an
operator. A person who opens Scheduler once to look at it gets a business
record; that is accepted.

The business is created with **no name**. `sign_up` refuses an empty name
today and stops refusing it on this path. `get_setup` already answers
`Give your business a name`, done only when the name is non-empty, so the
assistant asks for it with no new machinery.

A customer never meets a nameless business. `configured` is false while the
name is missing, and `GET /kiosk/{businessId}` shows the customer that same
boolean — a business that has not been named cannot take a booking.

### 1.2 The session is re-minted

`grant_license` and `grant_role(Role.OPERATOR)` write to BOSS, and a session
carries the roles it was minted with. Creating the business during a session
means that session does not name the operator role, and every
`@require_acl(..., roles=[Role.OPERATOR])` route refuses the new operator for
as long as they stay signed in.

`os.refreshSession()` does not solve this. It sends `refresh` over the
notification socket to hold off the inactivity timeout; it does not re-read
roles. Roles enter a session in `api.account.makeUserSession`, which only
`POST /account/signin` called.

`POST /account/session` is built. It removes the session the request arrived
on, mints one that names the caller's apps and roles as they now stand, and
sets the cookie. `uitest/tests/boss-session.spec.js` covers it.

The app calls it after the business is created and before it opens any
window.

### 1.3 What opens

| The signed-in user | What opens |
|---|---|
| runs a business, `configured` true | `OperatorDashboard` |
| runs a business, `configured` false | `OperatorDashboard`, with `SetupAssistant` over it |
| has no business | one is created, the session is re-minted, then as above |
| is an employee | `EmployeeDashboard`, unchanged |

A new operator therefore lands on the assistant, and the first thing it asks
for is the business name.

## Stage 2 — Data Model

None.

## Stage 3 — TDD

- `sign_up` opens a business with no name
- `whoami` reports the new operator against it
- The readiness answer for a nameless business is `configured: false`, with the
  name task outstanding
- A user who already has an `employees` row has no business created for them

UI, added to `ui-plan.md` as a flow:

- A signed-in user who has never opened Scheduler lands on `SetupAssistant`
- The assistant's first outstanding task is the business name
- Naming it in `BusinessConfig` marks the task done
- The new operator reaches an operator-only route in the same session, which is
  what proves the session was re-minted

## Stage 4 — Backend Implementation

`sign_up` stops requiring a name. `POST /reconcile` creates the business when
there is no `employees` row, and grants the license and the role as
`POST /signup` does now.

Whether `POST /signup` survives is Open Decision 1.

## Stage 5 — Integration

Delete `OperatorSignup.html`. Remove it from `plan.md` § Controllers,
§ Who reaches each page, and § 1.5, and remove the launch behaviour that opens
it. Name the removal in the commit message; `bin/check-commit` will ask.

`uitest/tests/scheduler-signup.spec.js` covers the retired flow and moves to
the new one rather than being deleted. What it proves — that somebody who runs
nothing ends up running something — still has to hold.

## Stage 6 — Grouping

None.

## Open Decisions

1. **Does `POST /signup` survive?** With `/reconcile` creating the business,
   the only caller left is a test. Either it goes, or it stays as the route
   that names a business and `/reconcile` calls it.
