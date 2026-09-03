# Scheduler — UI test coverage

`plan.md` is the implementation contract: what each screen is and what each route answers. This is the coverage contract: which flows are tested, in what order, and what each one has to prove.

They are separate because UI testing is long and interruptible. The table below is what lets it stop and resume — it says what is done, so nobody has to remember a conversation.

## What a flow is for

A UI test proves the **wiring**: that a screen calls the right endpoint and puts the answer in the right place. The rules are settled by the private suite, faster and in more cases — that a booking cannot be made inside the notice window is answered there, and asserting it again through a browser buys nothing.

So each flow below earns its place by catching what the private suite is blind to: a renamed field, a call sent to the wrong path, a response nobody reads, a button wired to nothing.

Keep to happy paths plus a little edge cover. See [`process.md` § When to Write Tests](../../../docs/prompt/process.md).

## Order

Dependency first, then how often a break there would go unnoticed.

1. **Operator onboarding** comes first because everything else needs a business to exist.
2. **The kiosk** next: it is the only surface a customer reaches, and the one nobody signs in to check.
3. The operator's own screens follow, roughly in the order the Manage menu lists them.
4. The employee portal and the platform screens last — fewest users, and both read what the earlier flows wrote.

## Flows

| # | Flow | Spec | Must prove | Status |
|---|---|---|---|---|
| 1 | Who reaches what | `scheduler-access.spec.js` | Every business-scoped route refuses a caller who does not work for that business; the kiosk answers a stranger; a role reaches only what it is granted | **Done** — 8 specs |
| 2 | Operator signup | `scheduler-signup.spec.js` | Signing up opens a business, grants the operator role, and lands on the dashboard; the templates load before a business exists | **Done** — 2 specs. The Setup Assistant's own listing is still to cover |
| 3 | Business settings | `scheduler-business-settings.spec.js` | Each tab saves and reads back — hours, slot mode, notice windows, confirmation channels; an invalid value is refused with a message the screen shows | **Done** — 3 specs. Hours and slot mode still to cover |
| 4 | Job types | `scheduler-job-types.spec.js` | Create, name, size, attribute, contact field, reorder, delete; a draft left unsaved does not reach the kiosk | **Done** — 2 specs. Sizes, attributes, contact fields and reorder still to cover |
| 5 | Employees | `scheduler-employees.spec.js` | Create, working days, time off, job types they can take, linking a BOSS account, `canManageOwnSchedule` | **Done** — 3 specs. Working days, time off, job types and account linking still to cover |
| 6 | Kiosk booking | `scheduler-kiosk.spec.js` | The whole path a customer walks: service, size, employee, slot, contact, OTP, confirm — and the appointment exists afterwards with what they chose | **Done** — 2 specs. OTP, deposit and the employee step still to cover |
| 7 | Appointment lookup | `scheduler-lookup.spec.js` | A job code and a verification code let a customer back in; a wrong code refuses; six wrong codes lock it and the operator can still change it | **Done** — 3 specs. The lockout still to cover |
| 8 | Operator calendar | `scheduler-calendar.spec.js` | Month, week and day draw what was booked; a day opens; a job opens from it; assigning a week puts somebody on each | **Done** — 3 specs. Assigning a week still to cover |
| 9 | Job detail and payment | `scheduler-job.spec.js` | Reschedule, reassign, complete, take payment, write off — each reads back | **Done** — 4 specs. Reassigning, completing and writing off still to cover |
| 10 | Customers | `scheduler-customers.spec.js` | List, search, detail, notes, and the appointments a customer holds | **Done** — 10 specs. A customer with a BOSS account, whose details are read-only, still to cover |
| 11 | Financial report | | The figures match what was booked and paid over a period, and the CSV downloads | |
| 12 | Employee portal | | The dashboard shows today's work, the calendar shows their own jobs and no colleague's, the profile saves | |
| 13 | Platform screens | | Businesses, contact fields, holidays, timeout, vendors, templates — each list and its editor | |

## Findings

Defects UI testing turns up, so a later session can tell a gap in coverage from a gap in the app.

| Flow | Finding | Fixed |
|---|---|---|
| 1 | `PUT /business/{id}/job/{id}` and `GET /business/{id}/stripe/products` named `boss_user` with no decorator to supply it, and answered 422 to everybody | Yes |
| 1 | `whoami` called anyone who ran no business a customer, so the admin opened Scheduler onto an appointment list | Yes |
| 1 | `POST /business/{id}/employee` accepted `canManageOwnSchedule` and dropped it | Yes |
| 1 | `ConfirmationSentTo.sms` was required while `email` was optional, so confirming a booking that sent no text raised | Yes |
| 2 | `OperatorSignup` asked `/business/{businessId}/config/templates` before a business existed. It answered 422 into a `catch` that swallowed it, leaving an empty template grid and no way past the step — so nobody could open a business | Yes |
| 7 | `AppointmentBusiness.phone` was a required string while a business's phone is optional, so opening an appointment for a business with no number recorded raised rather than answering | Yes |
| 9 | The Job screen asked for a payment amount but not a method. A payment with no method went to the server, was refused for the missing field, and came back as "Failed to record payment", which does not say what is missing | Yes |
| 10 | `update_customer_note` and `delete_customer_note` read the note through the customer and never through the business, so an operator naming their own business and another business's customer rewrote and deleted that business's notes | Yes |
| 10 | `signInAs` and `ensureAccount` read `response.ok()`, and `/account/*` answers a refusal with HTTP 200 and an `error` body. A sign-in that failed left the caller signed in as whoever they were before | Yes |
| 8 | `ScheduleCalendar.isoDate` formatted in UTC while `startOfWeek` and `addDays` reckoned locally, so west of Greenwich after mid-afternoon the week opened on Monday, dropped Sunday, and drew Saturday twice | Yes |
| 2 | Nobody can open Scheduler for the first time: BOSS checks for a license in `openApplication`, before any of the app's code runs, and the only things that grant one are the app's own signup and an operator linking an employee. The admin is exempt, which is why every earlier spec passed. **Open** — the spec grants it through `/account/assign-acl`, as an app store will | No |

## Two things every flow has to do

**Sign in again after granting a role.** A role is minted into the token at the next sign-in, so a session opened before a signup carries none — and every operator route wants one. A spec that signs up and keeps its session gets 403 from everything.

**Every customer surface is a kiosk.** `SchedulerKiosk` and `Appointment` both have a `.ui-kiosk` root, because both are reached without an account.

**A kiosk is not a window.** Its root is `.ui-kiosk`, so `windowByTitle` never finds it and `settled` never resolves — `aria-busy` is something the OS sets on a window. Locate it by its container, and wait for a step to be drawn.

**A document's Save does not close its window.** Save writes and stays open; Cancel and Delete are what close. So a spec proves a save by reading the record back, never by the window going away.

**Wait for the app before opening a controller.** `openApplication` returns once the container is attached, which is before `applicationDidStart` has read `/me`. Every controller reads `getBusinessId()`, which is null until it has, so opening one straight away loads a window against `/business/null/...`.

## Close what a test opens

A window or kiosk left open outlives the test that opened it. The next test's setup then times out, and tearing the browser context down takes twenty minutes rather than a second — a failure that reads as flakiness and points nowhere near the spec that caused it.

Close it the way a person does: the screen's own Close or Cancel. That also proves the screen tears down without throwing.

## One suite at a time

`bin/check` runs the UI tests as its last step. Starting a separate `npx playwright test` beside it puts two suites on one server and one database, and what comes back is neither run's answer: tests time out in minutes, and the failures land on whichever spec was unlucky.

Run one or the other. A Python suite that takes 9 seconds alone took 673 beside a UI run, which is what this looks like from the other side.

## A record named by an id is read through the business

`_working_for` checks the caller against the business the path names. It says
nothing about the record the path names next. A handler that then passes only
that record's id has left the business behind, and the lib call has nothing to
scope by.

Twenty-two lib functions were reached that way, and the hole was real: a rival
operator completed another business's appointment — which sent that business's
customer a receipt — and read their job types in full. Each resource now has a
guard in the module that owns it, because what "belongs to this business" means
depends on the resource: a size belongs through its job type, a time-off window
through its employee, an appointment directly.

`bin/check-routes` reports a handler that names a business in the path and
calls `lib` without it.

## A role is minted at sign-in

A token carries the roles held when it was issued. Signing up, being linked to
a business, being given a role — none of it reaches a session already open. A
test that acts as somebody whose role it just granted signs in again first.

Getting this wrong does not fail the test. The route refuses a caller with no
role at all, which is the same refusal the test was looking for — so it passes
without ever reaching the rule. `scope notes to the business in the path` was
written that way and passed against a route that had no such scoping.

## A helper that cannot fail is a helper that cannot be trusted

The `/account/*` routes answer a refusal with HTTP 200 and an `error` key in
the body, so `response.ok()` is true when nothing happened. `signInAs` read
only the status: a sign-in that failed left the caller as whoever they were
before, and every assertion after it was about the wrong person. It reads the
body now, and checks that the session came back in the name it asked for.

## A client guard needs a client assertion

A rule the server also enforces cannot be proved by its effect. "Nothing was recorded" passes whether or not the screen ever checked, because the server would have refused it anyway — so the assertion has to be the thing only the screen does: the message it shows before sending.

`reject empty payment` was written the first way and passed with the screen's check deleted. It asserts the alert now.

## Assert the data, not the frame

A calendar draws seven columns whether or not anything was booked, and a table draws its header with no rows. An assertion that counts the frame passes against an empty answer, which is the failure it was written to catch.

Each spec here was checked by breaking the read it depends on: emptying the month broke the month spec, the week the week, the day the day. A spec that survives its own route being broken is not testing that route.

## Notes

- A verification code goes to a phone nobody is holding, so in development the app records what a vendor would have sent — `lib/notify.py`, read through `GET /debug/last-message`. Nothing is wired in production, where sending is a no-op until a vendor is.
- `uitest/lib/scheduler.js` seeds through the API: `readyToBook` builds a business that can take a booking — hours, a service with a size, somebody to do it, and the contact fields without which the business is not ready — and `book` holds one through the kiosk. Reach for these rather than clicking a flow another spec already covers.
- `uitest/README.md` has signing in, seeding, and how to diagnose a visual bug.
- Run the flow's own spec while writing it, and the whole suite at the end of the step: the flows share an OS, a server and a database, and what one breaks for another shows up nowhere else.
