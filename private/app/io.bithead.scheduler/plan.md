# Scheduler App — Implementation Plan

## Identity
- **Bundle ID:** `io.bithead.scheduler`
- **App name:** Scheduler
- **Deep-link scheme:** `scheduler`
- **Public app dir:** `public/boss/app/io.bithead.scheduler/`
- **Private service dir:** `private/app/io.bithead.scheduler/`
- **App stylesheet:** `public/boss/app/io.bithead.scheduler/scheduler.css` (loaded via `os.network.stylesheet()` in `applicationDidStart`)
- **Test file:** `private/tests/test_scheduler.py`
- **Backend:** Python (FastAPI, SQLite) + Swift vendor layer (email/SMS/payment)
- **Reference app for UI patterns:** `public/boss/app/io.bithead.production/`
- **Reference for settings-style left-side navigation:** `io.bithead.settings` app (`Home.html`)
- **Reference for test harness setup:** `private/tests/test_wordy.py` + `private/tests/libtest/`

---

## Controllers

Every controller is `public/boss/app/io.bithead.scheduler/controller/<Name>.html`
and is registered in `application.json`. Naming follows
[`js.md` § Controller naming](../../../docs/prompt/js.md#controller-naming):
the model's name for a form, its plural for a list, no verb suffixes.

| Group | Windows | Modals |
|---|---|---|
| Entry | `Welcome` | |
| Kiosk / customer | `SchedulerKiosk`, `AppointmentLookup`, `Appointment`, `CustomerDashboard` | |
| Operator | `SetupAssistant`, `OperatorDashboard`, `OperatorSignup`, `ScheduleCalendar`, `SearchJob`, `AssignEmployees`, `Job`, `FinancialReport`, `BusinessConfig` | `QRPayment`, `IconPicker` |
| Job types | `JobTypes`, `JobType` | `JobTypeSize`, `JobTypeAttribute`, `JobTypeContactField` |
| Employees | `Employees`, `Employee` | `EmployeeSchedule`, `EmployeeTimeOff` |
| Customers | `Customers`, `Customer` | `CustomerNote` |
| Employee portal | `EmployeeDashboard`, `EmployeeCalendar`, `EmployeeProfile` | |
| Super admin | `SuperAdminBusinesses`, `SuperAdminBusiness`, `SuperAdminContactFields`, `SuperAdminHolidays`, `SuperAdminTimeout`, `SuperAdminVendors`, `SuperAdminTemplates` | `SuperAdminContactField`, `SuperAdminTemplate` |

### Documents

Eight of these windows edit one record and hand Cancel, Delete and Save to the
OS — see [`js.md` § Document windows](../../../docs/prompt/js.md#document-windows).
They declare `this.document = new UIDocument(...)`, write no File menu and no
`didHitEnter`, and their controls carry `doc-action` instead of `onclick`:

`SuperAdminBusiness`, `JobType`, `Employee`, `Customer`, `Job`,
`EmployeeProfile`, `SuperAdminTimeout`, `SuperAdminVendors`.

Two of them are not the plain three:

- **`Job`** adds **Mark Complete**, which is the app's own action rather than
  one of the document's. It keeps its `onclick`, asks for itself, and is
  wrapped in `os.ui.mutex`.
- **`EmployeeProfile`**'s leaving control reads **Close**, because the working
  days and time off beside it have already saved themselves. It is still
  `doc-action="cancel"`.

`JobType` and `Employee` create their record on open (see the draft pattern
below), so their discard question speaks of the record rather than of changes —
leaving throws away the job type or employee itself, not just edits to it.

Deliberately not documents: the modals (a dialog is not a document window, and
`showMessage` and the generated File menu both need `.ui-window`),
`BusinessConfig` (a control panel that saves as the user works), and the list
and dashboard windows, which edit nothing.

## Time Slots — reserved or unlimited

A business decides whether **a time is a resource or a preference**, in
Business Settings → Schedule:

> **Time Slots**
> ○ **Reserved** — one customer per time. Times already taken are not offered.
> ○ **Unlimited** — any number of customers may choose the same time.

**Reserved** is everything this plan describes elsewhere: availability is
computed from employee schedules, time off, holidays, buffers and existing
jobs; choosing a time holds it; the hold expires.

**Unlimited** removes capacity from the model. Every increment between the
business's opening and closing is offered, always, and choosing one takes
nothing away from anyone. A coffee shop taking an order for 10:15 does not care
that four other people also said 10:15.

That single distinction switches off most of the machinery:

| Under Unlimited | Why |
|---|---|
| No availability computation | Every increment is offered; there is nothing to work out |
| No session lock, no countdown, no "still there?" modal | Nothing is being held, so nothing can lapse |
| No auto-assignment, no unassigned-job warnings | Nobody is allocated to a time |
| Employee selection is not offered | Same reason |
| A business with no employees is still open for business | The "still configuring" state asks only for a job type |
| Slots run to closing | A 15-minute increment is offered at 5:45 for a 6:00 close whatever the job type's duration says — the duration is nominal when nothing is reserved |
| Times run from **now**, not from opening | 10:05 with a 5-minute increment offers 10:10 first. Nothing is reserved, so there is no reason to start the list anywhere else |
| A row may say **ASAP** | The server puts that word in the slot's `displayDate`. It is an ordinary row — selecting it selects it, and it is the only thing selected — labelled so a customer at a counter can take it without reading the rest |

Everything else — job types, sizes, costs, contact fields, attributes, deposits,
confirmations, the job code and the lookup flow — is unchanged.

## Operating Hours

The business now keeps its own hours, per weekday, one range each, and a day may
be closed. They are separate from employee schedules, which say when people
work: a technician may legitimately start before the office opens.

| Time Slots | What bounds the times offered | What the hours are for |
|---|---|---|
| Reserved | employee schedules, as today | shown to the customer, and nothing more |
| Unlimited | the business's hours | they are the whole answer |

The kiosk shows them in a footer on every step, in both modes, so a customer
can see when the business is open whether they are choosing a service, a time,
or typing their name.

### `SlotPicker` — the shared way to choose a time

Booking and rescheduling ask the same question, so they ask it with the same
code: a
[shared embedded controller](../../../docs/prompt/js.md#shared-embedded-controllers)
declared as `<template id="SlotPicker">` in `Application.html` and injected with
`EmbedController(SlotPicker)`.

It owns three views and the navigation between them — the next five openings, a
month with the open days marked, and the times on a chosen day — along with the
empty states, the selection marks, and its own Back. It reports two things:

| Delegate method | Meaning |
|---|---|
| `didSelectSlot(slot)` | The customer chose a time |
| `didLeaveSlotPicker()` | They backed out of the first view; what is behind it is the parent's business |

Configured before each `load()` with `{ businessId, jobTypeId, sizeId, employeeId?, businessPhone? }`.

| Parent | Where it sits | What `didSelectSlot` does |
|---|---|---|
| `SchedulerKiosk` | the `slot` step | opens a session and moves to the contact form |
| `Appointment` | the `reschedule-slot` step | PUTs the reschedule and returns to the detail |

The kiosk had `calendar` and `day-slots` as steps of its own; both are gone, and
choosing a time is one step holding the picker. `Appointment` had a five-slot
list and no calendar at all, which is what this closes.

The reason it is shared rather than copied: four defects were fixed in this flow
in a single session — steps that could only be hidden, an invisible empty state,
Back jumping to the start, and selections not surviving a step back. A second
copy is a second place for each of them, and the second copy is the one nobody
clicks.

### Forms that own lists

`JobType` and `Employee` each hold lists of children, so they create their model
as the form opens and every child is saved through its own route as it is
added. Cancel or the close button discards an unsaved draft. The pattern, and
what it costs, is
[`js.md` § A form that owns a list creates its model up front](../../../docs/prompt/js.md#a-form-that-owns-a-list-creates-its-model-up-front).

**A drafted record reads as active even though it is not.** The column is `0`
so a half-typed job type cannot reach a customer, but the form leaves its
checkbox on: saving is what says the operator wants it, and the first save
sends whatever the box says. Cancelling deletes the draft, so it never has to
be switched off.

**A draft is invisible until it is saved for real.** The row exists from the
moment the form opens, so the column that decides whether the rest of the
system may see it defaults to off: `job_types.is_active` and
`employees.include_in_schedule` are both `0`. Otherwise an `Untitled` job type
reaches the kiosk, and an unnamed employee is auto-assigned to a job, while the
operator is still typing.

Turning it on is the operator's, not the save's. The form shows the choice as a
checked box — a new job type is meant to be active — and the first real `PUT`
sends whatever the box says. While the record is still a draft the form leaves
that box at its markup default rather than loading the stored `0`, so the two
states stay distinct: the column means *may others see this yet*, the checkbox
means *should they, once it is saved*.

The children this app has, and the modal that edits each:

| Parent | Children | Modal |
|---|---|---|
| `JobType` | sizes | `JobTypeSize` |
| `JobType` | attributes | `JobTypeAttribute` |
| `JobType` | contact fields asked of the customer (ordered) | `JobTypeContactField` |
| `Employee` | working days | `EmployeeSchedule` |
| `Employee` | time off | `EmployeeTimeOff` |
| `Customer` | notes | `CustomerNote` |
| `SuperAdminContactFields` | contact field types (ordered) | `SuperAdminContactField` |
| `SuperAdminTemplates` | business templates | `SuperAdminTemplate` |

`Customer` and the two super-admin lists create nothing up front — a customer
is created by scheduling, and a template or field type is a top-level record —
so their Add button opens the modal with no parent to draft.

---

## Roles & Access

| Role | How identified | Notes |
|---|---|---|
| Super Admin | BOSS platform role | Manages system-wide config across all businesses |
| Operator | `business_users` record + BOSS account | Admin of one business; may have multiple per business |
| Employee | `employees` record linked to BOSS account | Read-only schedule; self-manage flag per record |
| Customer | BOSS account (optional) | Anonymous for scheduling; account needed to modify/cancel |

---

## Deep-Link URL Routing

Both URLs are handled by `Application.html`. `configure()` receives the parsed parameters and opens the correct controller.

| URL | configure() payload | Opens |
|---|---|---|
| `/a/scheduler/{businessId}` | `{ businessId }` | `SchedulerKiosk` |
| `/a/scheduler/appointment` | `null` | `AppointmentLookup` — the anonymous door, opened with a job code |
| `/a/scheduler/appointment/{appointmentId}` | `{ appointmentId }` | `Appointment` (requires login) |
| No params | `null` | `Welcome` for a guest; otherwise the window that fits the role |

## Signing In

Scheduler is a **secure** app (`"secure": true`), so BOSS closes it when the user
signs out. Nothing here has to handle a session ending.

Starting it is the case that needs handling. A guest is nobody yet and every
route in this app answers 401 for them, so `applicationDidStart` does not ask:
`os.isGuestUser(os.user)` decides, and a guest gets `Welcome` — a window with
what the app is for and two buttons, `os.ui.showCreateAccount()` and
`os.ui.showSignIn()`.

`Welcome` implements `userDidSignIn`, which the OS sends to every open window
when a real user signs in (never for the guest). It calls
`$(app.controller).showMainWindow()` and then closes itself — in that order, so
the desktop never flashes empty and the OS finishes handing the signal to every
window before this one leaves the list it is iterating.

### Is this business ready?

One endpoint answers it, and nothing is stored:

```
GET /api/io.bithead.scheduler/admin/setup
  → { configured: bool, tasks: [{ text, controller, section, done }] }
```

`configured` is every task `done`. The tasks are sentences in the operator's
words, each naming the window where that thing is fixed — and, where that
window has sections, which one:

> Give your business a name → `BusinessConfig`, `general`
> Add a size to "Lawn Mowing" → `JobTypes`
> No employee can perform "Hedge Trimming" → `Employees`
> Connect Stripe — "Lawn Mowing" takes a deposit → `BusinessConfig`, `payment`

`section` is `null` unless the window has more than one page. For
`BusinessConfig` it is one of its `TAB_NAMES` — a name rather than an index, so
reordering the nav does not silently send an owner to the wrong page.

**Every check is returned, done or not.** The response is the whole list with a
`done` on each, which is what lets `SetupAssistant` put a checkmark beside a
task the moment it is finished instead of having the row vanish. The assistant
decides what to show; the server just answers what is true.

Computed on every call rather than kept in a column. A rule added here takes
effect everywhere at once, and there is no flag that can fall out of step with
the thing it describes.

**Two callers, one answer.** `OperatorDashboard` is not one of them: while a
business is unfinished the assistant opens over the dashboard, so the dashboard
has nothing to say about it — and a configuration broken later by an admin is
not something the dashboard needs to notice either.

| Caller | Uses |
|---|---|
| `applicationDidStart` | opens `SetupAssistant` instead of the dashboard; a dashboard has nothing to report about a business that cannot be booked, and a form opened cold explains nothing about why |
| `GET /kiosk/{businessId}` | its `configured` is this same check. The customer sees the boolean and `step-not-configured`, never the tasks |

**What it weighs.** None of this arrives with a new business:

- a business name
- an active job type, with at least one **size** — duration and cost live there
  and the kiosk reads `sizes[0]` — and at least one **contact field**, without
  which a booking has nobody attached. The field *types* are seeded; this
  per-job-type selection is not, and a drafted job type starts empty
- **Reserved:** an employee, scheduled, linked to that job type. Availability
  comes from employee schedules, so none means no slots ever
- **Unlimited:** at least one open day in operating hours. They bound the day,
  and a new business has no `business_hours` rows at all
- an SMS or email vendor, if any contact field requires OTP
- Stripe, if any job type takes a deposit or payment

The last two are the awkward ones: without them a business looks complete and
fails partway through a booking, which is the worst moment to find out.

**What it does not weigh.** Contact field types, business templates and the
schedule timeout are seeded on install. Timezone, slot increment, cutoff,
booking notice and buffer all have defaults. A wrong timezone is a problem, but
it is not an unfinished setup.

The task text and the window it names are both the server's, because the rule
that produced them is — see
[`process.md` § The tactile surface decides nothing](../../../docs/prompt/process.md#the-tactile-surface-decides-nothing).

### OS bar menus

Scheduler is secure, so its menus declare who they are for — the mechanism is
[`js.md` § Secure menus](../../../docs/prompt/js.md#secure-menus).

| Menu | Class | Seen by |
|---|---|---|
| `scheduler-menu` (About, Quit) | none | everyone, guest included |
| `schedule-menu` | `secure` | a signed-in user |
| `manage-menu` | `secure` | a signed-in user |
| `superadmin-menu` | `super-user` | the BOSS super user |

`manage-menu` ends with **Setup Assistant**, below a divider
(`<option class="divider">`) separating it from the models above. Last rather
than first: it opens itself for as long as it is needed, and once the business
is configured a first-position item is only ever in the way.

`super-user` is `os.isSuperUser(os.user)` — the BOSS account, not this app's
`superadmin` role from `/me`. The two are the same person today because the plan
defines Super Admin as a BOSS platform role. If that ever changes, the menu is
the wrong lever and the app has to hide it itself; the routes enforce the role
regardless.

`showMainWindow()` is the role routing, public on the Application controller
because both `applicationDidStart` and `Welcome` need it:

| `/me` role | Window |
|---|---|
| `customer` | `CustomerDashboard` |
| `employee` | `EmployeeDashboard` |
| `operator`, `superadmin` | `OperatorDashboard` |
| anything else | `OperatorSignup` |

**Open:** `OperatorSignup` still begins with "BOSS account creation or login",
which `Welcome` has already done by the time anyone reaches it. That first step
should go.

---

## Stage 1 — UI/UX (Stubbed Backends)

Build all controllers with hard-coded stub data returned from stub endpoint functions. No real database. Goal: validate all flows, layouts, and state machines before writing a single line of backend logic.

**Rule:** Every controller calls `network.get(...)` / `network.post(...)` as it will in production. Stubs live in the Python service and return fixture JSON. No mocking inside the JS.

### Stub Convention
Each stub endpoint is decorated `@router.get(...)` and returns a hard-coded Pydantic model instance. When the real implementation is written in Stage 4, the stub is replaced in-place.

### UI/UX Conventions

BOSS-wide conventions — form spacing, the model list pattern, left-side navigation, icon button classes, label rules, `UIPopupMenu` usage, date and time fields — are documented in [`docs/prompt/js.md`](../../../docs/prompt/js.md). OS API signatures are indexed per component in [`docs/prompt/js-api.md`](../../../docs/prompt/js-api.md).

Follow those documents. This plan records only what is specific to Scheduler:

**Unassigned job indicator:**
- Week and day calendar views show `⚠` on job blocks/rows where no employees are assigned

**Assign Employees workflow:**
- Lives in the `OperatorDashboard` "Needs Attention" fieldset
- Dashboard shows separate counts for unassigned one-time jobs and unassigned recurring jobs
- "Assign Employees" button opens `AssignEmployees` controller (checkbox table, auto-assign)

---

### 1.1 Public / Kiosk Controllers

#### `SchedulerKiosk`
Multi-step state machine. Steps shown/hidden by JS state variable `currentStep`.

**Steps:**
1. `step-employee` — Employee selection grid (shown only if `business.allowCustomerEmployeeSelection`)
2. `step-job-type` — 2×N table of job types (icon left of title)
3. `step-slot` — First 5 available slots list; "Select custom date and time" button
4. `step-calendar` — Month calendar (unavailable days greyed); tap day → `step-day-slots`
5. `step-day-slots` — Vertical list of slots for selected day
6. `step-contact` — Contact info form (fields from job type config, ordered)
7. `step-otp` — OTP entry (shown only if business requires validation for provided email/phone; 3 attempts max)
8. `step-deposit` — Stripe redirect trigger (shown only if job type requires deposit)
9. `step-confirmation` — Job type, date/time, employee(s) (first name + last initial), business phone (tel: link), Job ID (short alphanumeric), create-account prompt, and a centred **Start Over** button beneath the text

**Start Over**, centred and 20px below the confirmation, hands the kiosk to the
next customer. It clears two different things:

- what the app believes — the session, the employee, job type, size and slot,
  the pending contact data, the OTP count
- what the screen still shows — the marks on the job type and employee lists,
  the size list built for the last choice, both contact containers, and the
  slot picker, which is asked to `reset()`

The second half is the half that is easy to miss. The contact form deliberately
restores what was typed, so a form left standing would greet the next person
with the last one's name and address; a mark left on a job type would tell them
they had chosen it.

### ASAP

`displayDate` is already the label the server writes for a row — "Monday, July
28". **"ASAP" is one of the values it can hold.** Nothing is added to the
response and nothing is asked of the client: it draws `displayDate` beside
`displayTime` as it always has.

Use it for a slot falling inside the next increment from now, and at most one
per response. That window is what makes "as soon as possible" mean today and
within minutes — *first* and *soon* are not the same thing. A shop closed when
someone walks up has a first slot tomorrow morning, and a row reading "ASAP"
with a time and no day would tell that customer nothing.

The decision needs the clock and the business's increment. The screen has
neither, which is why it does not participate — see
[`process.md` § The tactile surface decides nothing](../../../docs/prompt/process.md#the-tactile-surface-decides-nothing).

**What the confirmation says.** The closing line depends on what was actually
sent, which the confirm response reports rather than the client inferring it
from the business config — a business may send email while this customer gave
only a phone number.

| `confirmationSentTo` | Line shown |
|---|---|
| a phone | "A confirmation text has been sent to •••-•••-5309." |
| an email | "A confirmation email has been sent to j•••@example.com." |
| both | "A confirmation text and email have been sent." |
| neither | "Save your job code to modify or cancel your appointment." |

The destination is masked. A kiosk is a shared screen, and the job code that
reached it is a short string.

**"Edit my appointment":** top right of the kiosk header, and to the **left** of
the Close button on the occasions Close is there at all. Shown on the **first
step** and on the **confirmation**, and nowhere between — once someone is
part-way through booking they are holding a time, and a button that abandons it
is not what those words mean.

Which door it opens depends on whether the kiosk knows the appointment:

| From | Opens | Why |
|---|---|---|
| the first step | `AppointmentLookup` | the kiosk knows nothing about this person; the job code and verification code are how they prove the booking is theirs |
| the confirmation | `Appointment`, configured with the job it just booked | it booked the appointment moments ago with this customer standing here — there is nothing left to prove |

The kiosk forgets that job the moment it returns to the first step. A shared
screen must not hand the next customer the last one's appointment.

**On the confirmation step** the reservation countdown is cleared — the hold is
spent, and a number still counting down describes something that is no longer
true — and **"Edit my appointment"** is offered, which is the moment a customer
holding a fresh job code is most likely to want it.

**Kiosk close button:** Shown only when `os.user` is set and `/api/io.bithead.scheduler/operator/me` answers `isOperator`. Customers never see it — the kiosk covers the screen until this button is tapped, which is what makes a tablet on a counter a kiosk rather than a desktop.

`isOperator` is true for exactly two people: someone who owns *this* business — a `business_users` record for it — and a BOSS platform super admin, who always sees it. Everyone else does not, and that includes an operator of a **different** business: owning some business is not owning this one.

The kiosk hides the menu bar and the dock and has no other close affordance, so a session without the button ends by reloading the browser. That is the intent rather than a gap: a customer must not be able to leave the kiosk and reach BOSS, and the check cannot be loosened for convenience without handing them that.

**Entering the kiosk from inside BOSS:** two ways in, both opening `SchedulerKiosk` with a business ID.
- `OperatorDashboard` → **Enter Site**, for the operator's own business
- `SuperAdminBusinesses` → **Enter Site**, for the selected business. A super admin always has the close button, so this is always a round trip.

**Edge states:**
- Business has no job types or employees → show "configuring" message with business phone
- No slots within cutoff window → "no slots available, call us" message with `tel:` link
- OTP max attempts (3) → "call us" message with `tel:` link

**Resource lock timer:** Displayed after slot selection. Counts down from timeout value. On expiry: modal "Do you want to continue?" → yes: re-lock attempt → failure: back to `step-slot` (contact info preserved in JS); no: reset flow.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/kiosk/{businessId}` → business config, job types, slot increment, cutoff window, `allowCustomerEmployeeSelection`
- `GET /api/io.bithead.scheduler/kiosk/{businessId}/employees` → employee list (if customer selection enabled)
- `GET /api/io.bithead.scheduler/kiosk/{businessId}/job-types` → job types with sizes, icons, contact fields, attributes
- `GET /api/io.bithead.scheduler/kiosk/{businessId}/slots?jobTypeId=&sizeId=&employeeId=&limit=5` → first N available slots
- `GET /api/io.bithead.scheduler/kiosk/{businessId}/calendar?jobTypeId=&sizeId=&employeeId=&month=&year=` → available days in month
- `GET /api/io.bithead.scheduler/kiosk/{businessId}/day-slots?jobTypeId=&sizeId=&employeeId=&date=` → slots for a day
- `POST /api/io.bithead.scheduler/kiosk/{businessId}/session` → creates pending job, returns `sessionId`, `jobId`, lock expiry
- `PUT /api/io.bithead.scheduler/kiosk/session/{sessionId}/extend` → shifts lock expiry by timeout
- `POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/otp/send` → sends OTP to email or phone
- `POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/otp/verify` → verifies OTP; returns `{ verified: bool, attemptsRemaining: int }`
- `POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/confirm` → finalizes job, sends the confirmation on whichever channels the business enabled and the customer provided, returns `{ jobId, jobCode, stripePaymentUrl?, confirmationSentTo: { sms: str?, email: str? } }` (each masked, `null` when not sent)
- `GET /api/io.bithead.scheduler/operator/me?businessId=` → returns operator record or 404 (used for kiosk close button)

---

#### `AppointmentLookup`
How a customer without a BOSS account gets back to a booking they made
anonymously. One window, two steps, and the customer never leaves it.

**Steps:**
1. `step-code` — "Enter your job code". The code is on the kiosk confirmation
   screen and in the confirmation text or email.
2. `step-verify` — "We sent a verification code to •••-•••-5309". A field for
   that code, and a "Send it again" button.

On success the window closes and `Appointment` opens, configured with the
appointment the code belongs to.

**Where the verification code goes:** the phone the customer gave, or their
email if they gave no phone. When they gave both, the phone. The destination is
shown masked — a job code is a short string, and whoever holds it has not
proven anything yet.

**The code:** six digits, **usable once**, **expires 30 minutes** after it is
sent. An expired code returns to `step-code`; the job code has to be entered
again.

**Five attempts a minute, then the appointment is locked for good.** The sixth
wrong verification code inside a minute locks that appointment permanently. This
replaces the kiosk OTP's three-attempt rule rather than sitting beside it — one
number, so there are not two that can disagree.

**The lock closes the customer's door, not the business's.** The operator still
changes the appointment normally in `Job` and `ScheduleCalendar`; what is gone
permanently is the anonymous job-code path and the signed-in customer's own
Change Date/Time. That is what makes "call us" useful advice — the business can
act on it.

The lock cannot be lifted, by anyone. That is the point of it, and it is worth
being clear about the cost: a customer who mistypes six times loses
self-service on that booking forever, and anyone who has seen a job code can
lock the appointment it belongs to. The business is the fallback in both cases.

When it happens:
- `step-locked` — an apology, and the business phone, saying to call them to
  change the appointment.
- The same wording is sent to the customer, on whichever channels they gave —
  email if there is one, text if there is only a phone, both if both. A
  phone-only customer still finds out.

**Three unknown job codes in a minute costs 24 hours.** A wrong job code is
somebody guessing, and guessing is the only way to find an appointment that is
not yours. The third miss inside a minute blocks that caller from submitting
any job code for 24 hours — every code, not just the ones they tried, since the
point is to stop the search rather than to protect one booking.

Nothing is locked and nobody is notified: no appointment was found, so there is
no customer to tell. `step-blocked` says to try again tomorrow or call the
business.

**The caller is the client IP**, read from `X-Real-IP`, which nginx sets on
every proxied request. Trusting that header is safe only because the Python
service binds to `127.0.0.1` and is reachable through nginx alone; exposed
directly, a caller could forge it and the throttle would be decorative.

A household, an office and most mobile carriers share an address, so a block
can catch somebody who was not guessing. That is accepted: they are told to
try tomorrow or call the business, and the phone call works. It is also worth
being clear about what the throttle defends. A job code alone opens nothing —
it sends a code to the *real* customer's phone — so guessing at scale buys
nuisance messaging rather than access, and the verification code is what
actually stands in front of the appointment. With a code space of 32⁶ ≈ 1.07
billion, blind guessing is impractical before the throttle is reached at all.

**The operator side is not throttled.** A signed-in operator looking up a
customer's booking is not guessing, and `caller=None` turns it off.

**Edge states:**
- Unknown job code → "We can't find that job code." Stay on `step-code`.
- Job code belongs to a locked appointment → `step-locked` immediately, without
  sending a code. There is nothing to verify any more.
- Job cancelled, or its appointment has passed → "That appointment is no longer
  active", with the business phone.
- The job carries neither phone nor email → there is nowhere to send a code, so
  say so and give the business phone. This is reachable: contact fields are per
  job type, and a business may ask for neither.

**Stub endpoints:**
- `POST /api/io.bithead.scheduler/appointment/lookup` → `{ jobCode }` → sends the code, returns `{ sentTo: str, channel: "sms"|"email" }` (masked); 404 when the code is unknown, 429 once the caller has missed three times in a minute and for 24 hours after
- `POST /api/io.bithead.scheduler/appointment/lookup/verify` → `{ jobCode, code }` → `{ verified: bool, appointmentId: int?, attemptsRemaining: int, locked: bool }`; `locked` is the sixth failure inside a minute, and it is permanent

---

#### Minimum Change Notice

How close to the appointment a customer may still change or cancel it
themselves. It applies in **both** Time Slots modes — a reserved business has
the same problem, since a technician already driving over is a wasted trip
either way. Zero means up to the moment it starts.

It binds the customer only. The operator changes the appointment from `Job` and
`ScheduleCalendar` regardless, which is what makes "call the business" useful
advice.

`GET /appointment/{id}` reports `changesClosed`, decided by the server rather
than the client — the client would be trusting its own clock, and the rule is
the business's either way. When it is true, `Appointment` disables Change
Date/Time and Cancel Appointment and shows:

> It is not possible to edit or cancel your appointment as it is too close to
> the scheduled appointment time. Please contact the business at *(phone)* to
> make a change.

The lookup still lets the customer in: seeing the appointment is useful even
when nothing about it can be changed.

#### `Appointment`
Opened two ways: by a signed-in customer from `CustomerDashboard`, and by
`AppointmentLookup` once an anonymous customer has verified a code. Opens
pre-loaded with the appointment's current date/time.

**Actions:**
- Change date/time → same slot selection flow (steps 3–5 from kiosk, no contact/OTP/payment)
- Cancel → modal: "Schedule a different service?" → Yes: cancel + open `SchedulerKiosk`; No: cancellation confirmation page (thank you + "reschedule or schedule different service" buttons)

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/appointment/{appointmentId}` → appointment detail
- `PUT /api/io.bithead.scheduler/appointment/{appointmentId}/reschedule` → new date/time
- `DELETE /api/io.bithead.scheduler/appointment/{appointmentId}` → cancel

---

#### `CustomerDashboard`
Requires BOSS login.

**Layout:**
- Header: "Hello, {name}. You have {N} upcoming appointments."
- Table rows: business name, date/time, assigned employee(s); Edit and Cancel buttons per row
- "Appointment history" button → modal, all historical jobs, descending by date, no pagination

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/customer/appointments` → upcoming + past appointments

---

### 1.2 Operator Admin Controllers

#### `SetupAssistant`
The first window an owner sees, until their business can take a booking.

A paragraph saying what it is for, then a list box of the things still to
configure — the `tasks` from `/admin/setup`, in the server's words. Tapping a
row opens the window that row names and lands on the right page of it.

**Tapping a row opens it**, so the list is a `buttons` list box — every row is
somewhere to go, and none is selected to begin with.

**It shows the tasks that were outstanding when it opened**, and ticks them
rather than removing them: a finished row keeps its place and gains a
checkmark, so the owner sees what they have done, not a list that quietly gets
shorter. A check already satisfied before the window opened is never listed —
nobody needs congratulating for a business name they typed at signup. A task
that appears later, because a new job type takes a deposit, joins the list.

**The checkmark is the list box's existing icon support.** A done task's label
is `img:/boss/img/checkmark.svg,<text>` — the same `img:` prefix `Customers`
uses for the BOSS mark — so it needs nothing new, and it inverts with the row
when the row is selected.

**It refreshes when it regains focus.** The work happens in other windows, so
coming back is the moment to re-ask `/admin/setup`.

**A window, not a modal.** It asks the owner to go and do things; a modal would
block the very work it is requesting. It can be closed, and reopened from the
menu afterwards. It stops opening on launch once `configured` is true.

**Opening a row** — `os.ui.openSettings(loc)` and `Home.configure(loc)` in
`io.bithead.settings` are the pattern:

```javascript
const win = await $(app.controller).loadController(task.controller);
win.ui.show(function(ctrl) { ctrl.configure(task.section); });
```

A section is sent only when the task names one, so a window with a single page
needs no `configure` at all. A window with pages takes one and honours it
whether it is opening or already open — `show` runs the callback either way, so
an owner tapping a second row is moved to the page that row names.
`BusinessConfig` is the only one with pages today.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/setup` → `{ configured, tasks }` — the
  same call every other reader of readiness makes

---

#### `OperatorDashboard`
**Stats:** Jobs today, jobs this week, revenue this month, upcoming jobs, unassigned one-time jobs, unassigned recurring jobs.
**Buttons:** Enter Site (opens `SchedulerKiosk` for this business), View Schedule, Search Jobs (the last two also in the app menu).
**"Needs Attention" fieldset:** Shown when unassigned jobs or recurring conflicts exist. Contains an "Assign Employees" button that opens `AssignEmployees`.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/dashboard` → `{ businessId, jobsToday, jobsThisWeek, revenueThisMonth, upcomingJobs, unassignedJobs, unassignedConflicts }`

---

#### `AssignEmployees`
Checkbox table of all unassigned jobs (one-time and recurring). Header checkbox selects all. "Auto-assign work (N)" button enabled when at least one row is checked; disabled by default. Checkboxes unchecked by default.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/jobs/unassigned` → list of unassigned jobs
- `POST /api/io.bithead.scheduler/admin/jobs/assign` → `{ jobIds: [int] }` → auto-assigns employees

---

#### `ScheduleCalendar`
Three view modes: month, week, day. Toggled by segment buttons.

- **Month:** Highlighted days showing job count; tap day → day view
- **Week:** Sun–Sat (fixed, always 7 columns); condensed rows (time + truncated job name + employee initials); unassigned jobs show `⚠` prefix
- **Day:** Overlapping jobs shown side-by-side and time-offset; unassigned jobs show `⚠`; edit via `Job` form (no drag-and-drop)
Edit form for a single scheduled job: date, time, employee reassignment, notes.
Admin-only actions: mark completed, mark paid (cash), show QR payment code.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/job/{jobId}` → full job detail
- `PUT /api/io.bithead.scheduler/admin/job/{jobId}` → update job
- `POST /api/io.bithead.scheduler/admin/job/{jobId}/complete` → mark completed
- `POST /api/io.bithead.scheduler/admin/job/{jobId}/payment` → add payment transaction

---

#### `SearchJob`
Filters: status, customer name/phone, date range, job type, employee. Max 50 results, descending by date. Shared between operators (all jobs) and employees (their jobs only).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/jobs?status=&name=&phone=&fromDate=&toDate=&jobTypeId=&employeeId=` → job list. **Refuses `fromDate > toDate`.** The screen keeps the pair in order as the operator edits it, moving whichever field was not just touched — but that is a convenience, and a request can arrive from anywhere

---

#### `JobTypes`
List of job types; add/edit/delete.

#### `JobType`
Own fields: name, icon (picker modal), employees needed, active flag, Stripe product link, payment settings (required toggle, deposit amount/type fixed-or-percent, non-refundable checkbox).

Three child lists — sizes, attributes, contact fields — each a list box with Add and Edit, each edited in its own modal. The contact field list is ordered: the up and down buttons post the whole order and the list is redrawn from what the server hands back.

Created as a draft on open, so the child lists work before anything is named.

**Icon picker modal:** Two tabs — "System Icons" (4×N scrollable grid, from bundled SVGs) and "My Custom Icons" (uploaded images). Upload triggers file input.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/job-types?term=` → list, matched on
  `term` when one is given. `Employee`'s token menu sends a request per focus
  and per keystroke; the match is the server's, not the client's
- `GET /api/io.bithead.scheduler/admin/job-type/{id}` → detail, including `sizes`, `attributes`, `contactFields`
- `POST /api/io.bithead.scheduler/admin/job-type` → create the draft; `{ id }`
- `PUT /api/io.bithead.scheduler/admin/job-type/{id}` → update
- `DELETE /api/io.bithead.scheduler/admin/job-type/{id}` → delete
- `POST /api/io.bithead.scheduler/admin/job-type/{id}/size` → add size
- `PUT /api/io.bithead.scheduler/admin/job-type-size/{id}` → update size
- `DELETE /api/io.bithead.scheduler/admin/job-type-size/{id}` → delete size
- `POST /api/io.bithead.scheduler/admin/job-type/{id}/attribute` → add attribute
- `PUT /api/io.bithead.scheduler/admin/job-type-attribute/{id}` → update attribute
- `DELETE /api/io.bithead.scheduler/admin/job-type-attribute/{id}` → delete attribute
- `POST /api/io.bithead.scheduler/admin/job-type/{id}/contact-field` → ask for a contact field
- `PUT /api/io.bithead.scheduler/admin/job-type-contact-field/{id}` → update it
- `DELETE /api/io.bithead.scheduler/admin/job-type-contact-field/{id}` → stop asking for it
- `POST /api/io.bithead.scheduler/admin/job-type/{id}/contact-fields/reorder` → `{ ids: [int] }`
- `GET /api/io.bithead.scheduler/admin/icons?type=system|custom` → icon list
- `POST /api/io.bithead.scheduler/admin/icons` → upload custom icon (multipart)
- `GET /api/io.bithead.scheduler/admin/stripe/products` → list Stripe products from connected account
- `GET /api/io.bithead.scheduler/admin/contact-fields` → system contact field types (from super admin config)

---

#### `Employees`
List; add/edit/delete.

#### `Employee`
Own fields: linked BOSS account (user search), first and last name, "include in schedule" flag, "can manage own schedule and job types" flag, and the job types they can perform (token menu, saved with the employee).

**Job types are a token menu, not a list box.** They are a fixed set the
business already offers, associated to this employee — which is what a token
field is for, and it carries its own add and remove. A multi-select list box
offers neither; it asks the operator to know that a modifier key means "and
also", and a stray click silently clears the lot. `Job` already renders this
same association from the other side — employees on a job — as a token menu, so
this is one relationship drawn one way.

Two child lists — working days and time off — each a list box with Add and Edit, each edited in its own modal.

Created as a draft on open, so the child lists work before anyone is named.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/employees` → list
- `GET /api/io.bithead.scheduler/admin/employee/{id}` → detail, including `scheduleTemplate`, `timeOff`, `jobTypes`
- `POST /api/io.bithead.scheduler/admin/employee` → create the draft; `{ id }`
- `PUT /api/io.bithead.scheduler/admin/employee/{id}` → update, including `jobTypeIds`
- `DELETE /api/io.bithead.scheduler/admin/employee/{id}` → delete
- `POST /api/io.bithead.scheduler/admin/employee/{id}/schedule` → add a working day
- `PUT /api/io.bithead.scheduler/admin/employee-schedule/{id}` → update a working day
- `DELETE /api/io.bithead.scheduler/admin/employee-schedule/{id}` → remove a working day
- `GET /api/io.bithead.scheduler/admin/employee/{id}/time-off` → time-off windows
- `POST /api/io.bithead.scheduler/admin/employee/{id}/time-off` → add time-off
- `PUT /api/io.bithead.scheduler/admin/employee-time-off/{id}` → update time-off
- `DELETE /api/io.bithead.scheduler/admin/employee/{id}/time-off/{windowId}` → remove time-off

---

#### `BusinessConfig`
Tabbed layout (left-side nav, reference: `io.bithead.settings`).

**Tabs**, named as `TAB_NAMES` spells them, because `/admin/setup` sends an
owner to one by name:
1. **General** (`general`) — name, phone(s), address, owner info, description, site link, timezone dropdown (default from signup), read-only public URL
2. **Business Type** (`business-type`) — the template that fills in the rest; choosing one asks before overwriting what is already set
3. **Schedule** (`schedule`) — **Time Slots** (Reserved / Unlimited), **Operating Hours** (seven days, one range each, closable), cutoff window (days), slot increment (dropdown: 15m/30m/1h), min booking notice (hours), **minimum change notice (minutes)**, buffer time (minutes), reminder toggle (1 day before, email/SMS), completion mode (auto/manual), reminder opt-out per channel, and **Send confirmation** (below)
4. **Notifications** (`notifications`) — vendor type selection (email/SMS); per-type: vendor dropdown + config fields

**No Save button.** Business Settings writes as the owner works —
[`js.md` § Saving as the user works](../../../docs/prompt/js.md#saving-as-the-user-works)
has the pattern. Four triggers: a field losing focus, an option being chosen,
the section changing, and the window closing. Each write says so with
`view.ui.showMessage("Saved")`, which clears after a moment; a failure stays
until the next write succeeds and leaves the form dirty so the next trigger
retries. Connect Stripe keeps its button — it is an action, not a field.

**The business name is required**, and it is the one field that does not save
around a mistake: leaving it empty says so and writes nothing for it. Every
other field still saves, so an owner who fills in a phone number before
reaching the name does not lose it. The name field takes focus when the window
opens, so an owner sent here by `/admin/setup` is already in the field that
sent them.

**`configure(section)`** selects that page of the nav, and works on a window
already open as well as one being created — `SetupAssistant` sends an owner
here more than once, and the second tap must move the page. `null` opens
`general`. The pattern is `Home.configure(loc)` in `io.bithead.settings`.
5. **Payment** (`payment`) — Stripe Connect OAuth button; show connected account info when connected

Tab order is **General, Business Type, Schedule, Notifications, Payment**.
Business Type sits second because choosing one fills in the tabs below it — a
new operator wants it before the settings it drives, not after them.

5. **Business Type** — card grid showing templates; selecting one shows UIHelpBalloon with description and pre-fills other tab values

**Send confirmation:** a fieldset in the Schedule tab with two checkboxes,
**Text message** and **Email**. Either, both, or neither.

A channel is used only when the customer supplied the matching contact field,
so enabling both does not promise both: a job type that never asks for an email
sends a text and nothing else. Neither checked means nothing is sent, and the
kiosk falls back to telling the customer to keep their job code.

The message carries the job code, the service, the date and time, and the
business phone. It carries **no link** — the code is the credential, and a link
in a message that can be forwarded is a second one nobody asked for.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/config` → full business config, including `confirmBySms` and `confirmByEmail`
- `PUT /api/io.bithead.scheduler/admin/config` → update
- `GET /api/io.bithead.scheduler/admin/config/stripe/connect` → Stripe Connect OAuth redirect URL
- `POST /api/io.bithead.scheduler/admin/config/stripe/callback` → OAuth callback handler
- `GET /api/io.bithead.scheduler/admin/config/templates` → business template list

---

#### `Customers`
List, searched as the operator types by name or phone. Enter opens the selected customer.

#### `Customer`
Contact info (read-only if BOSS account linked; editable otherwise), notes (list box, `CustomerNote` modal), appointment history table.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/customers?q=` → list
- `GET /api/io.bithead.scheduler/admin/customer/{id}` → detail
- `PUT /api/io.bithead.scheduler/admin/customer/{id}` → update contact info (only if no BOSS account)
- `POST /api/io.bithead.scheduler/admin/customer/{id}/notes` → add note
- `PUT /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}` → edit note
- `DELETE /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}` → delete note

---

#### `FinancialReport`
Period selector (quarterly/yearly). Aggregate table: revenue, deposits collected, write-offs, jobs completed. CSV export button.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/reports/financial?period=quarter|year&year=&quarter=` → aggregate data
- `GET /api/io.bithead.scheduler/admin/reports/financial/export?period=&year=&quarter=` → CSV download

---

#### `QRPayment`
Shows Stripe Payment Link as a QR code + job amount. Opened by operator or employee to show customer.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/job/{jobId}/payment-link` → Stripe payment link URL + amount

---

### 1.3 Employee Portal Controllers

#### `EmployeeDashboard`
Default view: today's day schedule. Full job info visible: customer contact, co-workers (full names), job attributes, address if applicable. If `can_manage_own_schedule` flag: show buttons for schedule management and job type management.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/employee/today` → today's jobs for the logged-in employee

---

#### `EmployeeCalendar`
Month/week/day views, read-only, scoped to the employee's assignments.

**Stub endpoints:** Same shape as admin schedule endpoints, scoped server-side to the employee.

---

#### `EmployeeProfile`
The employee's own record, and the same shape as `Employee` seen from the other
side: a list box of working days and one of time off, each with Add and Edit
opening `EmployeeSchedule` and `EmployeeTimeOff`, plus a token menu of the
job types they can perform. Visible only if `can_manage_own_schedule` is true.

**It reuses the operator's child routes.** `EmployeeSchedule` and
`EmployeeTimeOff` post to `/admin/employee/{id}/…` whoever opened them, and the
service decides who may call: an employee with `can_manage_own_schedule` acting
on their own record, or an operator acting on anyone in their business. A
second set of routes differing only in prefix would be the same rule written
twice, and the second copy is the one that drifts.

The `/admin/` prefix reads oddly for an employee calling it. That is a naming
wart rather than a permissions one — worth revisiting if it grates.

Working days and time off save themselves as they are edited, so Save covers
the one thing left: which job types this employee can perform.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/employee/profile` → the signed-in employee's record, including `employeeId`, `scheduleTemplate`, `timeOff`, `jobTypes`
- `PUT /api/io.bithead.scheduler/employee/profile` → `{ jobTypeIds }`; only what an employee owns about themselves

---

### 1.4 Super Admin Controllers

#### `SuperAdminBusinesses`
Lists all businesses using the `controls-right separated` model list pattern. Filter by status. Add opens `SuperAdminBusiness` (no configure); Edit opens `SuperAdminBusiness` (with configure). Enter Site, above Edit, opens the selected business's `SchedulerKiosk`. Both act on the selection and are disabled without one.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/businesses?status=` → list
- `GET /api/io.bithead.scheduler/superadmin/business/{id}` → detail
- `POST /api/io.bithead.scheduler/superadmin/businesses` → create
- `PUT /api/io.bithead.scheduler/superadmin/business/{id}` → edit
- `POST /api/io.bithead.scheduler/superadmin/business/{id}/enable` → enable
- `POST /api/io.bithead.scheduler/superadmin/business/{id}/disable` → disable
- `DELETE /api/io.bithead.scheduler/superadmin/business/{id}` → delete

#### `SuperAdminBusiness`
Model form for creating and editing a business. Fields: name, owner name, phone, address, city, state, zip, timezone, active toggle. Delete button hidden when creating (no businessId). Uses `controls-right` style with Cancel → Delete → Save.

---

#### `SuperAdminContactFields`
System-wide contact field types, as an ordered list box. Add and Edit open `SuperAdminContactField`; up and down post the whole order and the list is redrawn from what the server hands back. Delete lives in the modal.

**Default fields (seeded on install):** first name, last name, phone, email, address line 1, address line 2, city, state, zip.
**Field properties:** name, type (text/phone/email/address), validation supported (bool), OTP capable (bool).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/contact-fields` → ordered list
- `POST /api/io.bithead.scheduler/superadmin/contact-field` → create
- `PUT /api/io.bithead.scheduler/superadmin/contact-field/{id}` → update
- `DELETE /api/io.bithead.scheduler/superadmin/contact-field/{id}` → delete
- `POST /api/io.bithead.scheduler/superadmin/contact-fields/reorder` → `{ ids: [int] }`

---

#### `SuperAdminHolidays`
Query third-party API for current and next year on first load (cached in DB). Display holidays grouped by country. Operators view their own selection (operator-facing sub-view).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/holidays?year=` → holidays list, grouped by country
- `POST /api/io.bithead.scheduler/superadmin/holidays/refresh?year=` → force re-fetch from API
- `GET /api/io.bithead.scheduler/admin/holidays?year=` → operator view of holidays with their selections
- `PUT /api/io.bithead.scheduler/admin/holidays?year=` → `{ holidayIds: [int] }` save operator selections

---

#### `SuperAdminTimeout`
Single integer field (minutes). Save button.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/timeout` → `{ timeoutMinutes: int }`
- `PUT /api/io.bithead.scheduler/superadmin/timeout` → `{ timeoutMinutes: int }`

---

#### `SuperAdminVendors`
Per vendor type (email, SMS): dropdown of registered vendor integrations, then vendor-specific config fields (stored as JSON blob).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/vendors` → registered vendor types and current configs
- `PUT /api/io.bithead.scheduler/superadmin/vendor/{type}` → `{ vendor: str, config: dict }`

---

#### `SuperAdminTemplates`
List box; Add and Edit open `SuperAdminTemplate`, where Delete also lives. Each template: icon (from icon picker), name, description, pre-config values for all business settings (see BusinessConfig tab fields).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/templates` → list
- `POST /api/io.bithead.scheduler/superadmin/template` → create
- `PUT /api/io.bithead.scheduler/superadmin/template/{id}` → update
- `DELETE /api/io.bithead.scheduler/superadmin/template/{id}` → delete

**Seeded templates (on install):**
1. Personal Service — icon, "Salons, spas, fitness studios. Clients choose their service provider."
2. Field Service — icon, "Landscaping, cleaning, home repair. Technicians go to the customer."
3. Healthcare/Wellness — icon, "Dental, chiropractic, therapy. Privacy and verification matter."
4. Pet Services — icon, "Grooming, walking, sitting. Mix of at-location and field visits."
5. General — icon, "A flexible starting point for any service business."
6. Food & Drink — icon, "Cafés, bakeries, takeaway. Customers choose a pickup
   time and you handle the queue." Presets **Time Slots: Unlimited**, minimum
   booking notice 0, buffer 0.

---

### 1.5 Operator Signup Controllers

#### `OperatorSignup`
Shown when app is opened with no businessId and user is not already an operator.
Steps:
1. BOSS account creation or login
2. Business info form (name, phone, address, timezone, description)
3. Business template selection (large cards with UIHelpBalloon on hover/tap)
4. Redirect to `OperatorDashboard`

**Stub endpoints:**
- `POST /api/io.bithead.scheduler/signup` → `{ businessId, operatorId }`

---

## Stage 2 — Data Model (SQLite Schema)

Write the full DDL for all tables before writing any backend logic. Schema is the contract between Stage 3 tests and Stage 4 implementation.

**No migrations until the next plan.** While this one is being built the DDL is
edited in place at `1.0.0` and the development database is deleted and created
again whenever it falls behind — see
[`python.md` § Changing the schema](../../../docs/prompt/python.md#changing-the-schema).
The schema this plan lands on is what a migration would start from.

### Tables

```sql
-- System-level

CREATE TABLE system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Seeded: ('schedule_timeout_minutes', '10')

CREATE TABLE contact_field_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    field_type TEXT NOT NULL,       -- text | phone | email | address_line | city | state | zip
    otp_capable INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL
);

CREATE TABLE system_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    country_name TEXT NOT NULL,
    name TEXT NOT NULL,
    date TEXT NOT NULL,             -- ISO 8601: YYYY-MM-DD
    year INTEGER NOT NULL
);

CREATE TABLE vendor_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_type TEXT NOT NULL,      -- email | sms | payment
    vendor_name TEXT NOT NULL,      -- sendgrid | twilio | stripe
    config_json TEXT NOT NULL,      -- JSON blob of vendor-specific credentials
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE business_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    icon_id INTEGER REFERENCES icons(id),
    -- pre-configured defaults (JSON blob mirrors business config fields)
    config_json TEXT NOT NULL
);

CREATE TABLE icons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER REFERENCES businesses(id), -- NULL = system icon
    filename TEXT NOT NULL,
    is_system INTEGER NOT NULL DEFAULT 0
);

-- Per-business

CREATE TABLE businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    owner_name TEXT,
    description TEXT,
    site_url TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    slot_mode TEXT NOT NULL DEFAULT 'reserved',     -- reserved | unlimited
    slot_increment_minutes INTEGER NOT NULL DEFAULT 15,
    cutoff_days INTEGER NOT NULL DEFAULT 30,
    min_booking_notice_hours INTEGER NOT NULL DEFAULT 0,
    min_change_notice_minutes INTEGER NOT NULL DEFAULT 0,  -- how close to the
                                    -- appointment a customer may still change
                                    -- or cancel it. 0 = up to the moment it
                                    -- starts. The business is never bound by it.
    buffer_minutes INTEGER NOT NULL DEFAULT 0,
    reminder_enabled INTEGER NOT NULL DEFAULT 1,
    confirm_by_sms INTEGER NOT NULL DEFAULT 0,      -- text a confirmation when the job is booked
    confirm_by_email INTEGER NOT NULL DEFAULT 0,    -- email one; both, either, or neither
    completion_mode TEXT NOT NULL DEFAULT 'auto',  -- auto | manual
    allow_customer_employee_selection INTEGER NOT NULL DEFAULT 0,
    notify_employees INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    stripe_account_id TEXT,
    create_date TEXT NOT NULL DEFAULT (datetime('now')),
    update_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE business_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator'   -- operator | superadmin
);

CREATE TABLE business_hours (
    -- When the business is open, as distinct from when its employees work.
    -- One range per weekday; a closed day has `is_closed = 1` and its times
    -- are ignored.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    day_of_week INTEGER NOT NULL,   -- 0=Sunday … 6=Saturday
    open_time TEXT NOT NULL,        -- HH:MM (24h, business local time)
    close_time TEXT NOT NULL,
    is_closed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE business_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    holiday_id INTEGER NOT NULL REFERENCES system_holidays(id),
    year INTEGER NOT NULL
);

-- Employees

CREATE TABLE employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    user_id INTEGER,           -- NULL until they are invited to BOSS
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    -- 0 for the same reason as `job_types.is_active`: a draft employee must
    -- not be auto-assigned to a job while their name is still being typed.
    include_in_schedule INTEGER NOT NULL DEFAULT 0,
    can_manage_own_schedule INTEGER NOT NULL DEFAULT 0,
    create_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE employee_schedule_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    day_of_week INTEGER NOT NULL,   -- 0=Sunday … 6=Saturday
    start_time TEXT NOT NULL,       -- HH:MM (24h, business local time)
    end_time TEXT NOT NULL
);

CREATE TABLE employee_time_off (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    date TEXT NOT NULL,             -- YYYY-MM-DD
    start_time TEXT NOT NULL,       -- HH:MM
    end_time TEXT NOT NULL
);

-- Job Types

CREATE TABLE job_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    icon_id INTEGER REFERENCES icons(id),
    min_employees INTEGER NOT NULL DEFAULT 1,
    payment_required INTEGER NOT NULL DEFAULT 0,
    deposit_required INTEGER NOT NULL DEFAULT 0,
    deposit_type TEXT,              -- fixed | percent
    deposit_amount REAL,
    deposit_nonrefundable INTEGER NOT NULL DEFAULT 0,
    stripe_product_id TEXT,
    stripe_price_id TEXT,
    -- 0, not 1: this row exists from the moment the form opens, and an
    -- `Untitled` job type must not reach a customer while it is still being
    -- typed. The first real save sends what the Active checkbox says.
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE job_type_sizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type_id INTEGER NOT NULL REFERENCES job_types(id),
    name TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    cost REAL NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE job_type_employees (
    -- employees who can perform this job type
    job_type_id INTEGER NOT NULL REFERENCES job_types(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    PRIMARY KEY (job_type_id, employee_id)
);

CREATE TABLE job_type_contact_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type_id INTEGER NOT NULL REFERENCES job_types(id),
    contact_field_type_id INTEGER NOT NULL REFERENCES contact_field_types(id),
    is_required INTEGER NOT NULL DEFAULT 1,
    require_otp INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE job_type_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type_id INTEGER NOT NULL REFERENCES job_types(id),
    name TEXT NOT NULL,
    attribute_type TEXT NOT NULL,   -- text | number | dropdown | checkbox
    options_json TEXT,              -- JSON array for dropdown options
    is_required INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- Scheduled Jobs

CREATE TABLE scheduled_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_code TEXT NOT NULL UNIQUE,  -- short alphanumeric, customer-facing ID
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    job_type_id INTEGER NOT NULL REFERENCES job_types(id),
    job_type_size_id INTEGER REFERENCES job_type_sizes(id),
    customer_id INTEGER REFERENCES customers(id),
    scheduled_date TEXT NOT NULL,   -- YYYY-MM-DD (business local)
    scheduled_time TEXT NOT NULL,   -- HH:MM (business local)
    duration_minutes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',         -- pending | confirmed | cancelled | completed
    payment_status TEXT NOT NULL DEFAULT 'unpaid',  -- unpaid | deposit_paid | fully_paid | written_off
    finalized INTEGER NOT NULL DEFAULT 0,
    locked_date TEXT,               -- set when someone failed the verification
                                    -- code six times in a minute. Once set the
                                    -- customer may never modify the job again
                                    -- through any public route. The operator
                                    -- still can. Never cleared.
    is_recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_id INTEGER REFERENCES recurrences(id),
    created_by_user_id INTEGER,                -- set if admin created on behalf of customer
    create_date TEXT NOT NULL DEFAULT (datetime('now')),
    update_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE job_employees (
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    PRIMARY KEY (job_id, employee_id)
);

CREATE TABLE job_contact_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    contact_field_type_id INTEGER NOT NULL REFERENCES contact_field_types(id),
    value TEXT NOT NULL
);

CREATE TABLE job_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    job_type_attribute_id INTEGER NOT NULL REFERENCES job_type_attributes(id),
    value TEXT NOT NULL
);

CREATE TABLE job_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    session_token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,       -- ISO 8601 UTC
    otp_attempts INTEGER NOT NULL DEFAULT 0,
    otp_verified INTEGER NOT NULL DEFAULT 0,
    otp_hash TEXT                   -- salt:sha256 of the code last sent. Never
                                    -- the code itself: a session row read by
                                    -- anyone would otherwise hand over the
                                    -- verification it exists to demand.
);

CREATE TABLE appointment_access_codes (
    -- Proves an anonymous customer owns the job code they typed. Separate from
    -- `job_sessions`: that OTP verifies a contact field while booking, this one
    -- lets someone back into a booking that already exists.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    code_hash TEXT NOT NULL,        -- SHA-256 + salt; never the code itself
    channel TEXT NOT NULL,          -- sms | email
    sent_to TEXT NOT NULL,          -- the address it went to, for the audit trail
    attempts INTEGER NOT NULL DEFAULT 0,
    used_date TEXT,                 -- set on success; a used code is spent
    expires_at TEXT NOT NULL,       -- ISO 8601 UTC, 30 minutes after it is sent
    create_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE appointment_access_attempts (
    -- One row per failed verification, so the lock can ask how many happened
    -- inside the last minute. A counter on the code row cannot: it knows how
    -- many, never how recently, and the rule is a rate rather than a total.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    create_date TEXT NOT NULL      -- ISO 8601 UTC
);

CREATE TABLE job_code_attempts (
    -- A miss at the appointment lookup, so the throttle can ask how many the
    -- same caller made inside the last minute. `blocked_until` is set on the
    -- attempt that trips it, which is what makes the block start from that
    -- moment rather than from the first miss.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller TEXT NOT NULL,           -- however the route identifies a caller;
                                    -- see Open Decisions, "How a blocked
                                    -- caller is identified"
    create_date TEXT NOT NULL,      -- ISO 8601 UTC
    blocked_until TEXT              -- ISO 8601 UTC, set on the tripping attempt
);

CREATE TABLE job_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    amount REAL NOT NULL,
    method TEXT NOT NULL,           -- stripe | cash | other
    stripe_payment_intent_id TEXT,
    collected_by_user_id INTEGER,
    note TEXT,
    create_date TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recurrences

CREATE TABLE recurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    job_type_id INTEGER NOT NULL REFERENCES job_types(id),
    job_type_size_id INTEGER REFERENCES job_type_sizes(id),
    customer_id INTEGER REFERENCES customers(id),
    interval_type TEXT NOT NULL,    -- daily | weekly | biweekly | monthly | custom
                                    -- Only `daily` and `weekly` are built.
                                    -- The rest are refused on creation rather
                                    -- than saved and silently never booked.
                                    -- `biweekly` needs an anchor date this
                                    -- table does not carry.
    days_of_week_json TEXT,         -- JSON array of ints [0-6] for custom/weekly
    preferred_time TEXT NOT NULL,   -- HH:MM
    is_active INTEGER NOT NULL DEFAULT 1,
    create_date TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Customers

CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    user_id INTEGER,           -- NULL if no BOSS account
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    create_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE customer_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    note TEXT NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    create_date TEXT NOT NULL DEFAULT (datetime('now')),
    update_date TEXT NOT NULL DEFAULT (datetime('now'))
);
```

---

## Stage 3 — TDD (Tests Before Implementation)

File: `private/tests/test_scheduler.py`
Setup mirrors `test_wordy.py`: `get_app_module("io.bithead.scheduler")`, then import from `io.bithead.scheduler.db` and `io.bithead.scheduler.lib`.

### Test Structure
Each `describe` comment groups related `it:` assertions within a single test function. Use `pytest.raises` for error cases.

```python
get_app_module("io.bithead.scheduler")
from io.bithead.scheduler.lib import *
from io.bithead.scheduler import db
```

### Test Groups (one function each unless noted)

#### `test_slot_availability()`
- `describe: single employee, no conflicts` → slot list covers job duration + buffer, respects slot increment
- `describe: employee has time-off window` → slots within time-off window are excluded
- `describe: employee has a confirmed job` → overlapping slots are excluded
- `describe: pending job within timeout` → locked slot is excluded from available slots
- `describe: expired pending job` → expired lock is ignored, slot is available
- `describe: job requires 2 employees, only 1 available` → no slots returned
- `describe: job requires 2 employees, both available` → slots returned
- `describe: holiday closed day` → no slots on that day
- `describe: cutoff window` → no slots beyond cutoff_days
- `describe: min booking notice` → slots within notice window excluded

#### `test_unlimited_slots()`
- `describe: unlimited business` → every increment between opening and closing is offered
- `describe: times run from now` → at 10:05 with a 5-minute increment the first slot is 10:10, not the day's opening
- `describe: first slot inside the next increment` → its `displayDate` is "ASAP"
- `describe: first slot beyond the next increment` → every `displayDate` is a date; the shop was closed and the soonest time is tomorrow, which needs its day
- `describe: reserved business` → no slot is labelled "ASAP"
- `describe: two customers, same time` → both succeed; neither removes the time from the other
- `describe: closed day` → no slots
- `describe: last slot of the day` → offered at closing minus one increment, whatever the job type's duration
- `describe: minimum booking notice on an unlimited business` → increments before now + notice are excluded
- `describe: cutoff window` → nothing beyond `cutoff_days`
- `describe: holiday` → no slots, the same as a reserved business
- `describe: no employees` → still offers slots; nobody is being allocated
- `describe: confirming` → no session lock is taken

#### `test_minimum_change_notice()`
- `describe: outside the window` → the customer may reschedule and cancel
- `describe: inside the window` → both refused for the customer, `changesClosed` is true
- `describe: inside the window, operator acting` → allowed; the rule binds the customer only
- `describe: notice of zero` → allowed up to the appointment's start
- `describe: reserved business` → the rule applies there too

#### `test_business_hours()`
- `describe: reserved business` → hours do not narrow what employee schedules offer
- `describe: unlimited business` → hours are what bound the day
- `describe: a day marked closed` → no slots that day in either mode… for unlimited; for reserved the employee schedule still governs

#### `test_job_session()`
- `describe: create session` → pending job created, session token returned, expires_at set
- `describe: extend session` → expires_at shifts by timeout minutes
- `describe: expired session on re-lock` → raises `SessionExpired`; new lock attempt respects current availability
- `describe: commit session` → job status → confirmed, finalized = 1, session record retained

#### `test_otp()`
- `describe: send OTP` → record created, stub verifies send called
- `describe: verify correct OTP` → verified = 1, attempts not incremented
- `describe: verify wrong OTP` → attempts incremented, raises `OTPInvalid`
- `describe: max attempts exceeded` → raises `OTPMaxAttemptsExceeded`

#### `test_recurrence()`
- `describe: rolling horizon creates instance` → instance materialized when within cutoff window
- `describe: no available employees` → job created with status confirmed but no job_employees, added to unassigned list
- `describe: recurrence cancelled` → no new instances created
- `describe: instance already exists` → no duplicate created

#### `test_appointment_access()`
- `describe: known job code` → code created, hashed, expires 30 minutes out, sent on the customer's phone
- `describe: customer gave only an email` → sent by email
- `describe: customer gave both` → sent by phone
- `describe: customer gave neither` → raises `NoContactChannel`; no code created
- `describe: unknown job code` → raises `JobNotFound`; no code created
- `describe: cancelled job` → raises `AppointmentInactive`
- `describe: correct code` → verified, returns the appointment, `used_date` set
- `describe: correct code used twice` → second attempt raises `CodeSpent`
- `describe: expired code` → raises `CodeExpired` even when the digits match
- `describe: wrong code` → attempts incremented, raises `CodeInvalid`
- `describe: five wrong codes in a minute` → each raises `CodeInvalid`; the job is not locked
- `describe: sixth wrong code in a minute` → raises `AppointmentLocked`, `locked_date` set, notice sent on every channel the customer gave
- `describe: sixth wrong code spread over two minutes` → not locked; the window is a minute
- `describe: lookup for a locked job` → raises `AppointmentLocked`; no code is sent
- `describe: modify a locked job as the operator` → allowed; the lock is the customer's door only
- `describe: reschedule a locked job through the public route` → raises `AppointmentLocked`
- `describe: a lock cannot be lifted` → no path sets `locked_date` back to null

#### `test_job_code_throttle()`
- `describe: two unknown codes in a minute` → both answer not-found; the caller may keep going
- `describe: third unknown code in a minute` → blocked, and the block lasts 24 hours
- `describe: a blocked caller submits a valid code` → still refused; the block is on the caller, not the code
- `describe: three misses spread over two minutes` → not blocked
- `describe: block expires` → the caller may submit again after 24 hours
- `describe: nothing is locked or notified` → no `locked_date` is set and no message is sent; no appointment was identified

#### `test_booking_confirmation()`
- `describe: business sends neither` → nothing sent, `confirmationSentTo` is empty
- `describe: business sends both, customer gave both` → text and email sent
- `describe: business sends both, customer gave only a phone` → text only
- `describe: business sends email, customer gave none` → nothing sent
- `describe: message content` → carries the job code, service, date/time, business phone, and no link

#### `test_payment()`
- `describe: add cash transaction` → job_transactions record created, payment_status updates to fully_paid if total >= cost
- `describe: partial payment` → payment_status remains unpaid until threshold met
- `describe: deposit payment` → payment_status → deposit_paid
- `describe: mark written_off` → payment_status → written_off

#### `test_job_lifecycle()`
- `describe: cancel job` → status → cancelled
- `describe: complete job (manual)` → status → completed, receipt email triggered
- `describe: complete job (auto)` → status → completed when scheduled end time passes
- `describe: admin reschedule` → date/time updated, status stays confirmed, customer notified

#### `test_job_search()`
- `describe: from after to` → raises `InvalidDateRange`; no query is run
- `describe: from equal to to` → allowed; a single day is a range
- `describe: only one end given` → allowed; an open range is a range
- `describe: neither given` → allowed; no date constraint

#### `test_financial_report()`
- `describe: quarterly report` → revenue = sum of fully_paid transactions in period
- `describe: write-offs` → written_off jobs appear in write-off column, excluded from revenue
- `describe: CSV export` → returns valid CSV string with correct headers and rows

#### `test_employee_availability()`
- `describe: weekly template` → employee available on configured days/times
- `describe: time-off window partial day` → employee available only outside the time-off window
- `describe: include_in_schedule = false` → employee excluded from all slot computation

#### `test_business_template()`
- `describe: apply template` → business config fields updated to template defaults

---

## Stage 4 — Backend Implementation

After all Stage 3 tests pass against stub implementations, replace each stub function with real logic.

### File Layout

```
private/app/io.bithead.scheduler/
    __init__.py         # FastAPI router, start/shutdown, all API route handlers
    db.py               # SQLite connection, DDL creation, all raw queries
    lib.py              # Business logic (slot computation, session management, OTP, recurrence)
    model.py            # Pydantic models (request/response bodies, DB row models)
    jobs.py             # Background jobs: hourly cleanup cron, rolling recurrence, reminder dispatch
    stripe_client.py    # Stripe Connect integration (OAuth, product query, payment link generation, webhook)
```

### `db.py` Responsibilities
- `start_database()` — create tables, seed contact_field_types, seed business_templates, seed system_config
- One function per query; no business logic; returns typed model instances
- `delete_database()` for test teardown

### `lib.py` Responsibilities
- `get_available_slots(business_id, job_type_id, size_id, employee_id, limit, from_date)` → `List[Slot]`. Branches on `slot_mode`: `reserved` computes availability as described in Stage 3; `unlimited` enumerates increments between the day's opening and closing, minus notice and cutoff, and asks nothing about employees or existing jobs
- `create_job_session(business_id, job_type_id, size_id, employee_id, scheduled_dt)` → `Session`
- `extend_session(session_token)` → updated `expires_at`
- `confirm_session(session_token, contact_info, attributes)` → `ScheduledJob`
- `send_otp(session_token, field_type)` → calls Swift vendor layer private endpoint
- `verify_otp(session_token, code)` → `bool`
- `send_booking_confirmation(job_id)` → sends on each channel the business enabled and the customer supplied; returns what was sent, masked
- `request_appointment_access(job_code)` → creates a single-use code, sends it, returns `(channel, masked_destination)`
- `verify_appointment_access(job_code, code)` → the appointment, and spends the code; the sixth failure inside a minute locks the job permanently and sends the notice
- `lock_appointment(job_id)` → sets `locked_date`, notifies the customer. Has no inverse, by design; the public routes refuse a locked job, the admin routes do not
- `cancel_job(job_id, cancelled_by)` → updated job; triggers notification
- `complete_job(job_id, completed_by)` → updated job; triggers receipt
- `add_payment(job_id, amount, method, stripe_intent_id, collected_by)` → `Transaction`
- `assign_employees_for_week(business_id, week_start_date)` → `List[JobAssignment]`
- `get_financial_report(business_id, period, year, quarter)` → `FinancialReport`
- `generate_job_code()` → short alphanumeric (e.g. 6 chars, uppercase A-Z0-9, collision-checked)

### `jobs.py` Responsibilities
- `cleanup_expired_sessions()` — hourly cron; deletes job_sessions where expires_at < now AND job.finalized = 0. Leaves scheduled_jobs row for analytics.
- `materialize_recurrences()` — daily cron; for each active recurrence, create next instance if within cutoff window and no instance exists for that date
- `send_reminders()` — daily cron; find confirmed jobs scheduled for tomorrow with reminder_enabled = 1; call Swift vendor layer

### `stripe_client.py` Responsibilities
- `get_connect_oauth_url(business_id)` → Stripe Connect OAuth redirect URL
- `handle_oauth_callback(code, business_id)` → exchange code for `stripe_account_id`; store on business
- `list_products(business_id)` → query Stripe Products from the business's connected account
- `create_payment_link(business_id, stripe_price_id, amount, metadata)` → Stripe Payment Link URL
- `handle_webhook(payload, sig_header)` → verify signature; on `payment_intent.succeeded` → call `add_payment()`

### Swift Vendor Layer (private endpoints, Swift web server)
These are called by the Python service only. Not exposed publicly.

- `POST /private/vendor/email/send` → `{ to, subject, body, vendor }` → routes to registered email vendor
- `POST /private/vendor/sms/send` → `{ to, body, vendor }` → routes to registered SMS vendor
- `POST /private/vendor/otp/send` → `{ to, channel (email|sms), vendor }` → generates + sends OTP, stores hash
- `POST /private/vendor/otp/verify` → `{ to, code }` → `{ verified: bool }`

Vendor registration pattern: each vendor module implements a `VendorProtocol` and registers itself with a `VendorRegistry` keyed by type.

---

## Stage 5 — Integration

Replace each stub endpoint body with a call to the corresponding `lib.py` or `db.py` function. Integration is complete when all Stage 3 tests pass against the real database.

### Integration Checklist (per endpoint group)
- [ ] Kiosk scheduling flow (slots, session, OTP, confirm)
- [ ] Booking confirmation by text and email
- [ ] Appointment lookup by job code + verification code
- [ ] Permanent lock after six failures, and every writer that has to honour it
- [ ] Appointment modify/cancel
- [ ] Admin schedule (month/week/day, assign week)
- [ ] Job CRUD + payment
- [ ] Job type CRUD + Stripe product link
- [ ] Employee CRUD + schedule templates + time-off
- [ ] Time Slots mode + operating hours
- [ ] Business config + Stripe Connect OAuth
- [ ] Customer list + detail + notes
- [ ] Financial report + CSV export
- [ ] Search jobs
- [ ] Super admin: businesses, contact fields, holidays, timeout, vendors, templates
- [ ] Employee portal: today view, calendar, profile self-management
- [ ] Customer dashboard + appointment history
- [ ] Background jobs: cleanup, recurrence materialization, reminders
- [ ] Stripe webhook handler
- [ ] Swift vendor layer: email, SMS, OTP

---

## Stage 1 — Complete

Every screen is built, and every one reads as BOSS: components come from the OS
or its factories, forms follow the model-list and draft-on-create patterns, and
no screen assembles a BOSS control by hand.

The inputs still built at run time — the kiosk's contact fields, the
operating-hours rows in Business Settings — are bare inputs in table cells and
in the kiosk's own layout, which
[`js.md`](../../../docs/prompt/js.md#building-components-at-run-time) allows.
They are not components missing their `ui` interface.

---

## Open Decisions (to revisit before Stage 4)

1. **Holiday API provider** — Identify a third-party API that supports querying holidays by country and year (e.g. `holidayapi.com`, `nager.date`). Evaluate free tier limits vs. annual query cadence.
2. ~~**OTP storage**~~ — **Resolved.** `job_sessions.otp_hash` holds `salt:sha256` of the code last sent. A column rather than a table, because `otp_attempts` and `otp_verified` already sit on the session and the three are read and written together.
3. **Job code generation** — Confirm alphabet and length. Suggested: 6 uppercase alphanumeric (A-Z, 0-9), collision-checked at insert.
4. **Stripe webhook endpoint exposure** — Stripe webhooks must be publicly accessible. Decide whether the webhook lands on the Python private service (via a public reverse-proxy rule) or on the Swift public web server (which then calls Python internally).
5. **BOSS user search API** — When an operator links a BOSS account to an employee record, a user search is needed. Confirm which BOSS platform endpoint to use.
6. ~~**How a blocked caller is identified**~~ — **Resolved.** The client IP,
   read from `X-Real-IP`. It is the industry default for an anonymous endpoint
   and the only marker the caller cannot reset; a cookie is cleared from a
   menu. The shared-address problem is accepted, because a wrongly blocked
   person is told to call the business and that still works.
7. **The selected business template is not stored** — `businesses` has no
   column for it, so only a template's effects survive. "Selected Template"
   reads None again next time the window opens, despite the settings being
   applied.
