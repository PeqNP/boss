# Setting Up a Business — Implementation Plan

Queued behind `plan.md`. Nothing here starts until that plan is finished.

## Identity

Bundle: `io.bithead.scheduler`. No new tables and no new endpoints. This plan
retires one controller and sends what opened it somewhere else.

## The problem

`OperatorSignup` asks for what `BusinessConfig` already asks for.

| `OperatorSignup` step | Already in `BusinessConfig` |
|---|---|
| `business` — `biz-name`, `biz-phone`, `owner-name`, `address-line1`, `city`, `state`, `zip` | the `general` tab, under the same input names |
| the timezone it sends | the `general` tab's `timezone` menu |
| `template` — pick a business template | the `business-type` tab |
| `account` — a prompt to sign in | BOSS signs a user in before any app window opens |

So an owner fills in one form to create the business and a second, identical
one to change it. Two screens hold one set of fields, and a field added to
either has to be added to the other.

## What replaces it

A signed-in user who runs no business opens `BusinessConfig`. Saving the
`general` tab creates the business.

`SetupAssistant` is unchanged and keeps its job. It is the one place that shows
state across controllers — job types, employees, hours, payment — and links
each outstanding thing to the window that fixes it. `BusinessConfig` does not
take that on: a second guide inside one tab set is the duplication this plan
exists to remove.

## Stage 1 — UI/UX

### 1.1 `BusinessConfig` opens without a business

`configure()` accepts no `businessId`. When `/me` reports none:

- The `general` tab opens, and it is the only tab enabled. The others act on a
  business that does not exist yet.
- Save on `general` calls `POST /signup` rather than
  `PUT /business/{businessId}/config`, then re-reads `/me` and enables the
  rest.

The tabs are enabled from that point on, in the order they already sit in.
Nothing is gated after the business exists.

### 1.2 What opens after signing in

`OperatorDashboard` when the business exists. `BusinessConfig` when it does
not. `SetupAssistant` continues to open over the dashboard while `configured`
is false, which is what it does today.

### 1.3 Nothing new on the readiness endpoint

`GET /business/{business_id}/setup` already returns
`{ configured, tasks: [{ text, controller, section, done }] }`, and `section`
is already one of `BusinessConfig`'s `TAB_NAMES`. `SetupAssistant` reads it
unchanged.

## Stage 2 — Data Model

None.

## Stage 3 — TDD

`POST /signup` and `GET /business/{id}/setup` are covered. The work is UI, so
the tests are UI tests, added to `ui-plan.md` as a flow:

- A signed-in user who runs no business opens `BusinessConfig`, not
  `OperatorSignup`
- Only `general` is enabled until the business exists
- Saving `general` creates the business, and the other tabs open
- `SetupAssistant` then names what is still outstanding

## Stage 4 — Backend Implementation

None expected. `POST /signup` gains a caller.

## Stage 5 — Integration

Delete `OperatorSignup.html`. Remove it from `plan.md` § Controllers,
§ Who reaches each page, and § 1.5. Remove the launch behaviour that opens it.
Name the removal in the commit message; `bin/check-commit` will ask for it.

`uitest/tests/scheduler-signup.spec.js` covers the retired flow. It moves to
the new one rather than being deleted — the behaviour it proves, that a user
who runs nothing can open a business, still has to hold.

## Stage 6 — Grouping

None.

## Open Decisions

1. **Does `POST /signup` still take a name?** It takes a name and a timezone
   today, and the `general` tab already refuses an empty name. If the first
   save is the thing that creates the business, the two checks are the same
   check and one of them should go.

2. **What does a disabled tab look like?** `BusinessConfig` has no disabled
   state for a tab today. A tab that cannot be opened yet has to say why, or
   the owner reads it as broken.
