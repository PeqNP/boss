# Scheduler App — Implementation Plan

## Identity
- **Bundle ID:** `io.bithead.scheduler`
- **App name:** Scheduler
- **Deep-link scheme:** `scheduler`
- **Public app dir:** `public/boss/app/io.bithead.scheduler/`
- **Private service dir:** `private/app/io.bithead.scheduler/`
- **Test file:** `private/tests/test_scheduler.py`
- **Backend:** Python (FastAPI, SQLite) + Swift vendor layer (email/SMS/payment)
- **Reference app for UI patterns:** `public/boss/app/io.bithead.lean/`
- **Reference for settings-style tab navigation:** `io.bithead.settings` app
- **Reference for test harness setup:** `private/tests/test_wordy.py` + `private/tests/libtest/`

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
| `/a/scheduler/{businessId}` | `{ businessId }` | `SchedulerKioskController` |
| `/a/scheduler/appointment/{appointmentId}` | `{ appointmentId }` | `AppointmentModifyController` (requires login) |
| No params | `null` | `OperatorSignupController` or `OperatorDashboardController` depending on login state |

---

## Stage 1 — UI/UX (Stubbed Backends)

Build all controllers with hard-coded stub data returned from stub endpoint functions. No real database. Goal: validate all flows, layouts, and state machines before writing a single line of backend logic.

**Rule:** Every controller calls `network.get(...)` / `network.post(...)` as it will in production. Stubs live in the Python service and return fixture JSON. No mocking inside the JS.

### Stub Convention
Each stub endpoint is decorated `@router.get(...)` and returns a hard-coded Pydantic model instance. When the real implementation is written in Stage 4, the stub is replaced in-place.

---

### 1.1 Public / Kiosk Controllers

#### `SchedulerKioskController` (`kiosk/index.html`)
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
9. `step-confirmation` — Job type, date/time, employee(s) (first name + last initial), business phone (tel: link), Job ID (short alphanumeric), create-account prompt

**Kiosk close button:** Shown only when `os.user` is set and `/api/io.bithead.scheduler/operator/me` returns an operator for this business. Customers never see it.

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
- `POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/confirm` → finalizes job, returns `{ jobId, jobCode, stripePaymentUrl? }`
- `GET /api/io.bithead.scheduler/operator/me?businessId=` → returns operator record or 404 (used for kiosk close button)

---

#### `AppointmentModifyController` (`appointment/index.html`)
Requires BOSS login. Opens pre-loaded with the appointment's current date/time.

**Actions:**
- Change date/time → same slot selection flow (steps 3–5 from kiosk, no contact/OTP/payment)
- Cancel → modal: "Schedule a different service?" → Yes: cancel + open `SchedulerKioskController`; No: cancellation confirmation page (thank you + "reschedule or schedule different service" buttons)

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/appointment/{appointmentId}` → appointment detail
- `PUT /api/io.bithead.scheduler/appointment/{appointmentId}/reschedule` → new date/time
- `DELETE /api/io.bithead.scheduler/appointment/{appointmentId}` → cancel

---

#### `CustomerDashboardController` (`customer/index.html`)
Requires BOSS login.

**Layout:**
- Header: "Hello, {name}. You have {N} upcoming appointments."
- Table rows: business name, date/time, assigned employee(s); Edit and Cancel buttons per row
- "Appointment history" button → modal, all historical jobs, descending by date, no pagination

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/customer/appointments` → upcoming + past appointments

---

### 1.2 Operator Admin Controllers

#### `OperatorDashboardController` (`admin/dashboard/index.html`)
**Stats:** Jobs today, jobs this week, revenue this month, upcoming jobs, unassigned conflicts count.
**Buttons:** View Schedule, Search Jobs (also in app menu).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/dashboard` → stats object

---

#### `ScheduleCalendarController` (`admin/schedule/index.html`)
Three view modes: month, week, day. Toggled by segmented control.

- **Month:** Highlighted days showing job count; tap day → day view
- **Week:** Sun–Sat (fixed); condensed rows (time + truncated job name + employee initials); UITokenField employee filter (empty = all)
- **Day:** Overlapping jobs shown side-by-side and time-offset; edit via form (no drag-and-drop)
- **"Assign employees for week" button:** Posts to bulk-assign endpoint; applies immediately

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/schedule/month?year=&month=` → days with job counts
- `GET /api/io.bithead.scheduler/admin/schedule/week?date=` → jobs for week
- `GET /api/io.bithead.scheduler/admin/schedule/day?date=` → jobs for day with overlap metadata
- `GET /api/io.bithead.scheduler/admin/employees` → employee list (for filter token field)
- `POST /api/io.bithead.scheduler/admin/schedule/assign-week?date=` → auto-assigns unassigned jobs

---

#### `JobEditController` (`admin/schedule/job-edit.html`)
Edit form for a single scheduled job: date, time, employee reassignment, notes.
Admin-only actions: mark completed, mark paid (cash), show QR payment code.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/job/{jobId}` → full job detail
- `PUT /api/io.bithead.scheduler/admin/job/{jobId}` → update job
- `POST /api/io.bithead.scheduler/admin/job/{jobId}/complete` → mark completed
- `POST /api/io.bithead.scheduler/admin/job/{jobId}/payment` → add payment transaction

---

#### `SearchJobController` (`admin/search/index.html`)
Filters: status, customer name/phone, date range, job type, employee. Max 50 results, descending by date. Shared between operators (all jobs) and employees (their jobs only).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/jobs?status=&name=&phone=&from=&to=&jobTypeId=&employeeId=` → job list

---

#### `JobTypeListController` (`admin/job-types/index.html`)
List of job types; add/edit/delete.

#### `JobTypeEditController` (`admin/job-types/edit.html`)
Fields: name, icon (picker modal), min employees, sizes (sub-list), custom attributes (sub-list), required contact fields (ordered, optional/required toggle), Stripe Product link (search from Stripe), employee capability list, payment settings (required toggle, deposit amount/type fixed-or-percent, non-refundable checkbox).

**Icon picker modal:** Two tabs — "System Icons" (4×N scrollable grid, from bundled SVGs) and "My Custom Icons" (uploaded images). Upload triggers file input.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/job-types` → list
- `GET /api/io.bithead.scheduler/admin/job-type/{id}` → detail
- `POST /api/io.bithead.scheduler/admin/job-type` → create
- `PUT /api/io.bithead.scheduler/admin/job-type/{id}` → update
- `DELETE /api/io.bithead.scheduler/admin/job-type/{id}` → delete
- `GET /api/io.bithead.scheduler/admin/icons?type=system|custom` → icon list
- `POST /api/io.bithead.scheduler/admin/icons` → upload custom icon (multipart)
- `GET /api/io.bithead.scheduler/admin/stripe/products` → list Stripe products from connected account
- `GET /api/io.bithead.scheduler/admin/contact-fields` → system contact field types (from super admin config)

---

#### `EmployeeListController` (`admin/employees/index.html`)
List; add/edit/delete.

#### `EmployeeEditController` (`admin/employees/edit.html`)
Fields: linked BOSS account (user search), weekly schedule template (7-day list with start/end time per day), time-off windows (date + start/end time), job types they can perform (multi-select), "include in schedule" flag, "can manage own schedule and job types" flag.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/employees` → list
- `GET /api/io.bithead.scheduler/admin/employee/{id}` → detail
- `POST /api/io.bithead.scheduler/admin/employee` → create
- `PUT /api/io.bithead.scheduler/admin/employee/{id}` → update
- `DELETE /api/io.bithead.scheduler/admin/employee/{id}` → delete
- `GET /api/io.bithead.scheduler/admin/employee/{id}/time-off` → time-off windows
- `POST /api/io.bithead.scheduler/admin/employee/{id}/time-off` → add time-off
- `DELETE /api/io.bithead.scheduler/admin/employee/{id}/time-off/{windowId}` → remove time-off

---

#### `BusinessConfigController` (`admin/config/index.html`)
Tabbed layout (left-side nav, reference: `io.bithead.settings`).

**Tabs:**
1. **General** — name, phone(s), address, owner info, description, site link, timezone dropdown (default from signup), read-only public URL
2. **Schedule** — cutoff window (days), slot increment (dropdown: 15m/30m/1h), min booking notice (hours), buffer time (minutes), reminder toggle (1 day before, email/SMS), completion mode (auto/manual), reminder opt-out per channel
3. **Notifications** — vendor type selection (email/SMS); per-type: vendor dropdown + config fields
4. **Payment** — Stripe Connect OAuth button; show connected account info when connected
5. **Business Type** — card grid showing templates; selecting one shows UIHelpBalloon with description and pre-fills other tab values

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/config` → full business config
- `PUT /api/io.bithead.scheduler/admin/config` → update
- `GET /api/io.bithead.scheduler/admin/config/stripe/connect` → Stripe Connect OAuth redirect URL
- `POST /api/io.bithead.scheduler/admin/config/stripe/callback` → OAuth callback handler
- `GET /api/io.bithead.scheduler/admin/config/templates` → business template list

---

#### `CustomerListController` (`admin/customers/index.html`)
List with search by name/phone.

#### `CustomerDetailController` (`admin/customers/detail.html`)
Contact info (read-only if BOSS account linked; editable otherwise), notes (add/edit/delete), appointment history table.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/customers?q=` → list
- `GET /api/io.bithead.scheduler/admin/customer/{id}` → detail
- `PUT /api/io.bithead.scheduler/admin/customer/{id}` → update contact info (only if no BOSS account)
- `POST /api/io.bithead.scheduler/admin/customer/{id}/notes` → add note
- `PUT /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}` → edit note
- `DELETE /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}` → delete note

---

#### `FinancialReportController` (`admin/reports/index.html`)
Period selector (quarterly/yearly). Aggregate table: revenue, deposits collected, write-offs, jobs completed. CSV export button.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/reports/financial?period=quarter|year&year=&quarter=` → aggregate data
- `GET /api/io.bithead.scheduler/admin/reports/financial/export?period=&year=&quarter=` → CSV download

---

#### `QRPaymentController` (`admin/payment/qr.html`)
Shows Stripe Payment Link as a QR code + job amount. Opened by operator or employee to show customer.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/admin/job/{jobId}/payment-link` → Stripe payment link URL + amount

---

### 1.3 Employee Portal Controllers

#### `EmployeeDashboardController` (`employee/index.html`)
Default view: today's day schedule. Full job info visible: customer contact, co-workers (full names), job attributes, address if applicable. If `can_manage_own_schedule` flag: show buttons for schedule management and job type management.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/employee/today` → today's jobs for the logged-in employee

---

#### `EmployeeCalendarController` (`employee/schedule/index.html`)
Month/week/day views, read-only, scoped to the employee's assignments.

**Stub endpoints:** Same shape as admin schedule endpoints, scoped server-side to the employee.

---

#### `EmployeeProfileController` (`employee/profile/index.html`)
Weekly schedule template editor, time-off windows. Visible only if `can_manage_own_schedule` is true. Also allows editing which job types they can perform.

---

### 1.4 Super Admin Controllers

#### `SuperAdminBusinessListController` (`superadmin/businesses/index.html`)
View, enable/disable, delete, edit all businesses. Filter by status.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/businesses?status=` → list
- `GET /api/io.bithead.scheduler/superadmin/business/{id}` → detail
- `PUT /api/io.bithead.scheduler/superadmin/business/{id}` → edit
- `POST /api/io.bithead.scheduler/superadmin/business/{id}/enable` → enable
- `POST /api/io.bithead.scheduler/superadmin/business/{id}/disable` → disable
- `DELETE /api/io.bithead.scheduler/superadmin/business/{id}` → delete

---

#### `ContactInfoFieldsController` (`superadmin/contact-fields/index.html`)
System-wide contact field types. Reorder (drag or up/down buttons), add, edit, delete.

**Default fields (seeded on install):** first name, last name, phone, email, address line 1, address line 2, city, state, zip.
**Field properties:** name, type (text/phone/email/address), validation supported (bool), OTP capable (bool).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/contact-fields` → ordered list
- `POST /api/io.bithead.scheduler/superadmin/contact-field` → create
- `PUT /api/io.bithead.scheduler/superadmin/contact-field/{id}` → update
- `DELETE /api/io.bithead.scheduler/superadmin/contact-field/{id}` → delete
- `POST /api/io.bithead.scheduler/superadmin/contact-fields/reorder` → `{ ids: [int] }`

---

#### `HolidayManagerController` (`superadmin/holidays/index.html`)
Query third-party API for current and next year on first load (cached in DB). Display holidays grouped by country. Operators view their own selection (operator-facing sub-view).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/holidays?year=` → holidays list, grouped by country
- `POST /api/io.bithead.scheduler/superadmin/holidays/refresh?year=` → force re-fetch from API
- `GET /api/io.bithead.scheduler/admin/holidays?year=` → operator view of holidays with their selections
- `PUT /api/io.bithead.scheduler/admin/holidays?year=` → `{ holidayIds: [int] }` save operator selections

---

#### `ScheduleTimeoutController` (`superadmin/timeout/index.html`)
Single integer field (minutes). Save button.

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/timeout` → `{ timeoutMinutes: int }`
- `PUT /api/io.bithead.scheduler/superadmin/timeout` → `{ timeoutMinutes: int }`

---

#### `VendorConfigController` (`superadmin/vendors/index.html`)
Per vendor type (email, SMS): dropdown of registered vendor integrations, then vendor-specific config fields (stored as JSON blob).

**Stub endpoints:**
- `GET /api/io.bithead.scheduler/superadmin/vendors` → registered vendor types and current configs
- `PUT /api/io.bithead.scheduler/superadmin/vendor/{type}` → `{ vendor: str, config: dict }`

---

#### `BusinessTemplateListController` (`superadmin/templates/index.html`)
CRUD. Each template: icon (from icon picker), name, description, pre-config values for all business settings (see BusinessConfigController tab fields).

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

---

### 1.5 Operator Signup Controllers

#### `OperatorSignupController` (`signup/index.html`)
Shown when app is opened with no businessId and user is not already an operator.
Steps:
1. BOSS account creation or login
2. Business info form (name, phone, address, timezone, description)
3. Business template selection (large cards with UIHelpBalloon on hover/tap)
4. Redirect to `OperatorDashboardController`

**Stub endpoints:**
- `POST /api/io.bithead.scheduler/signup` → `{ businessId, operatorId }`

---

## Stage 2 — Data Model (SQLite Schema)

Write the full DDL for all tables before writing any backend logic. Schema is the contract between Stage 3 tests and Stage 4 implementation.

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
    slot_increment_minutes INTEGER NOT NULL DEFAULT 15,
    cutoff_days INTEGER NOT NULL DEFAULT 30,
    min_booking_notice_hours INTEGER NOT NULL DEFAULT 0,
    buffer_minutes INTEGER NOT NULL DEFAULT 0,
    reminder_enabled INTEGER NOT NULL DEFAULT 1,
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
    boss_user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator'   -- operator | superadmin
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
    boss_user_id INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    include_in_schedule INTEGER NOT NULL DEFAULT 1,
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
    is_active INTEGER NOT NULL DEFAULT 1
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
    is_recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_id INTEGER REFERENCES recurrences(id),
    created_by_boss_user_id INTEGER,                -- set if admin created on behalf of customer
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
    otp_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE job_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
    amount REAL NOT NULL,
    method TEXT NOT NULL,           -- stripe | cash | other
    stripe_payment_intent_id TEXT,
    collected_by_boss_user_id INTEGER,
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
    days_of_week_json TEXT,         -- JSON array of ints [0-6] for custom/weekly
    preferred_time TEXT NOT NULL,   -- HH:MM
    is_active INTEGER NOT NULL DEFAULT 1,
    create_date TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Customers

CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    boss_user_id INTEGER,           -- NULL if no BOSS account
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
    created_by_boss_user_id INTEGER NOT NULL,
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
- `get_available_slots(business_id, job_type_id, size_id, employee_id, limit, from_date)` → `List[Slot]`
- `create_job_session(business_id, job_type_id, size_id, employee_id, scheduled_dt)` → `Session`
- `extend_session(session_token)` → updated `expires_at`
- `confirm_session(session_token, contact_info, attributes)` → `ScheduledJob`
- `send_otp(session_token, field_type)` → calls Swift vendor layer private endpoint
- `verify_otp(session_token, code)` → `bool`
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
- [ ] Appointment modify/cancel
- [ ] Admin schedule (month/week/day, assign week)
- [ ] Job CRUD + payment
- [ ] Job type CRUD + Stripe product link
- [ ] Employee CRUD + schedule templates + time-off
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

## Open Decisions (to revisit before Stage 4)

1. **Holiday API provider** — Identify a third-party API that supports querying holidays by country and year (e.g. `holidayapi.com`, `nager.date`). Evaluate free tier limits vs. annual query cadence.
2. **OTP storage** — OTP code should be stored as a hash (e.g. SHA-256 + salt) in `job_sessions`. Decide whether to add an `otp_hash` column or a separate `otp_attempts` table.
3. **Job code generation** — Confirm alphabet and length. Suggested: 6 uppercase alphanumeric (A-Z, 0-9), collision-checked at insert.
4. **Stripe webhook endpoint exposure** — Stripe webhooks must be publicly accessible. Decide whether the webhook lands on the Python private service (via a public reverse-proxy rule) or on the Swift public web server (which then calls Python internally).
5. **BOSS user search API** — When an operator links a BOSS account to an employee record, a user search is needed. Confirm which BOSS platform endpoint to use.
