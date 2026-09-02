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
| 8 | Operator calendar | | Month, week and day draw what was booked; a day opens; a job opens from it; assigning a week puts somebody on each | |
| 9 | Job detail and payment | | Reschedule, reassign, complete, take payment, write off — each reads back | |
| 10 | Customers | | List, search, detail, notes, and the appointments a customer holds | |
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
| 2 | Nobody can open Scheduler for the first time: BOSS checks for a license in `openApplication`, before any of the app's code runs, and the only things that grant one are the app's own signup and an operator linking an employee. The admin is exempt, which is why every earlier spec passed. **Open** — the spec grants it through `/account/assign-acl`, as an app store will | No |

## Two things every flow has to do

**Sign in again after granting a role.** A role is minted into the token at the next sign-in, so a session opened before a signup carries none — and every operator route wants one. A spec that signs up and keeps its session gets 403 from everything.

**Every customer surface is a kiosk.** `SchedulerKiosk` and `Appointment` both have a `.ui-kiosk` root, because both are reached without an account.

**A kiosk is not a window.** Its root is `.ui-kiosk`, so `windowByTitle` never finds it and `settled` never resolves — `aria-busy` is something the OS sets on a window. Locate it by its container, and wait for a step to be drawn.

**A document's Save does not close its window.** Save writes and stays open; Cancel and Delete are what close. So a spec proves a save by reading the record back, never by the window going away.

**Wait for the app before opening a controller.** `openApplication` returns once the container is attached, which is before `applicationDidStart` has read `/me`. Every controller reads `getBusinessId()`, which is null until it has, so opening one straight away loads a window against `/business/null/...`.

## Notes

- A verification code goes to a phone nobody is holding, so in development the app records what a vendor would have sent — `lib/notify.py`, read through `GET /debug/last-message`. Nothing is wired in production, where sending is a no-op until a vendor is.
- `uitest/lib/scheduler.js` seeds through the API: `readyToBook` builds a business that can take a booking — hours, a service with a size, somebody to do it, and the contact fields without which the business is not ready — and `book` holds one through the kiosk. Reach for these rather than clicking a flow another spec already covers.
- `uitest/README.md` has signing in, seeding, and how to diagnose a visual bug.
- Run the flow's own spec while writing it, and the whole suite at the end of the step: the flows share an OS, a server and a database, and what one breaks for another shows up nowhere else.
