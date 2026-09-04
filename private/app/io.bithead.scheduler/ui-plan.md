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
| 2 | Opening a business | `scheduler-onboarding.spec.js` | A business is opened for whoever runs none, unnamed; the assistant asks for the name; the session is minted again so the operator role is in it; a nameless business takes no bookings | **Done** — 6 specs |
| 3 | Business settings | `scheduler-business-settings.spec.js` | Each tab saves and reads back — hours, slot mode, notice windows, confirmation channels; an invalid value is refused with a message the screen shows | **Done** — 7 specs |
| 4 | Job types | `scheduler-job-types.spec.js` | Create, name, size, attribute, contact field, reorder, delete; a draft left unsaved does not reach the kiosk | **Done** — 7 specs. Deleting an attribute or a contact field still to cover |
| 5 | Employees | `scheduler-employees.spec.js` | Create, working days, time off, the work they may be given, and a draft left unsaved | **Done** — 7 specs. Deleting a time-off window still to cover |
| 6 | Kiosk booking | `scheduler-kiosk.spec.js` | The whole path a customer walks: service, size, employee, slot, contact, OTP, confirm — and the appointment exists afterwards with what they chose | **Done** — 3 specs. The OTP and deposit steps need a vendor before they can be reached; see `review.md` |
| 7 | Appointment lookup | `scheduler-lookup.spec.js` | A job code and a verification code let a customer back in; a wrong code refuses; six wrong codes lock it and the operator can still change it | **Done** — 5 specs |
| 8 | Operator calendar | `scheduler-calendar.spec.js` | Month, week and day draw what was booked; a day opens; a job opens from it; assigning a week puts somebody on each | **Done** — 4 specs |
| 9 | Job detail and payment | `scheduler-job.spec.js` | Reschedule, reassign, complete, take payment, cancel — each reads back | **Done** — 7 specs. Writing off is unbuilt, see Findings |
| 10 | Customers | `scheduler-customers.spec.js` | List, search, detail, notes, and the appointments a customer holds | **Done** — 11 specs |
| 11 | Financial report | `scheduler-report.spec.js` | The figures match what was booked and paid over a period, and the CSV downloads | **Done** — 5 specs, no defects found |
| 12 | Employee portal | `scheduler-portal.spec.js` | The dashboard shows today's work, the calendar shows their own jobs and no colleague's, the profile saves | **Done** — 5 specs, no defects found. Working days and time off from the portal still to cover |
| 13 | Platform screens | `scheduler-platform.spec.js` | Businesses, contact fields, holidays, timeout, vendors, templates — each list and its editor | **Done** — 8 specs, no defects found. Holidays and editing a vendor still to cover |

## Findings

Defects UI testing turns up, so a later session can tell a gap in coverage from a gap in the app.

| Flow | Finding | Fixed |
|---|---|---|
| 1 | `PUT /business/{id}/job/{id}` and `GET /business/{id}/stripe/products` named `boss_user` with no decorator to supply it, and answered 422 to everybody | Yes |
| 1 | `whoami` called anyone who ran no business a customer, so the admin opened Scheduler onto an appointment list | Yes |
| 1 | `POST /business/{id}/employee` accepted `canManageOwnSchedule` and dropped it | Yes |
| 1 | `ConfirmationSentTo.sms` was required while `email` was optional, so confirming a booking that sent no text raised | Yes |
| 2 | `OperatorSignup` asked `/business/{businessId}/config/templates` before a business existed. It answered 422 into a `catch` that swallowed it, leaving an empty template grid and no way past the step — so nobody could open a business | Yes |
| 2 | `OperatorSignup` asked for every field `BusinessConfig`'s `general` and `business-type` tabs already ask for, under the same input names. Two screens held one set of fields, and a field added to either had to be added to the other | Yes — the screen is gone |
| 7 | `AppointmentBusiness.phone` was a required string while a business's phone is optional, so opening an appointment for a business with no number recorded raised rather than answering | Yes |
| 9 | The Job screen asked for a payment amount but not a method. A payment with no method went to the server, was refused for the missing field, and came back as "Failed to record payment", which does not say what is missing | Yes |
| 10 | `update_customer_note` and `delete_customer_note` read the note through the customer and never through the business, so an operator naming their own business and another business's customer rewrote and deleted that business's notes | Yes |
| 10 | `signInAs` and `ensureAccount` read `response.ok()`, and `/account/*` answers a refusal with HTTP 200 and an `error` body. A sign-in that failed left the caller signed in as whoever they were before | Yes |
| 11 | `GET`, `PUT .../reschedule` and `DELETE` on `/appointment/{id}` carried no guard and no proof of verification. Anyone with no session at all read, moved and cancelled any appointment by guessing an integer id, and the access code the lookup flow sends protected nothing | Yes |
| 5 | The Employee screen has no way to link a BOSS account. `plan.md` § 1.2 says it carries a "linked BOSS account (user search)", and `PUT /business/{id}/employee/{id}/account` is wired and tested — no screen calls it, so an operator cannot give an employee access to the app | **No** — unbuilt rather than uncovered |
| 9 | An appointment cannot be written off. `lib.write_off_payment` is written and tested, no route calls it, and no screen offers it — so `payment_status` never becomes `written_off` and the Financial Report's Write-Offs figure can only ever read $0.00 | **No** — unbuilt rather than uncovered |
| 7 | The lookup screen's locked and blocked steps never drew. Both are chosen on `error.detail.locked` and `error.detail.blocked`, and `@handled` sent only `reason` — so a customer whose appointment was locked, or who was blocked for the day, saw a one-line error instead of the step carrying the number to call | Yes |
| 8 | `ScheduleCalendar.isoDate` formatted in UTC while `startOfWeek` and `addDays` reckoned locally, so west of Greenwich after mid-afternoon the week opened on Monday, dropped Sunday, and drew Saturday twice | Yes |
| 2 | Nobody could open Scheduler for the first time: BOSS checked for a license in `openApplication`, before any of the app's code ran, and the only things that granted one were the app's own signup and an operator linking an employee | Yes — `application.json` declares `licensed`, absent meaning no, and this app does not declare it. `scheduler-onboarding.spec.js` opens it as an account that has never held a license |

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

## A customer carries a handle, never an id

`POST /appointment/lookup/verify` used to hand back `appointmentId`, and the
three routes the customer then called — read, reschedule, cancel — took that id
and checked nothing. So the code was decorative: a caller with no session
cancelled any appointment with `DELETE /appointment/5`, and ids are sequential.

Verification mints a six-character handle now, stored on the appointment and
replaced each time somebody proves the booking is theirs. The routes take the
handle, so a caller who has proved nothing has nothing to send. A handle that
opens nothing is a 404 rather than a refusal — an id is a small integer and a
handle is not, so a refusal that told the two apart would say which ids are
real.

The lockout in flow 7 rested on the same footing. Six wrong codes close the
customer's door, and the door was never the way in.

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

`bin/io.bithead.scheduler/check.py` reports a handler that names a business in
the path and calls `lib` without it. It lives with the app rather than in
`bin/check-routes`, which runs against every service and holds only rules that
are true of every service.

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
