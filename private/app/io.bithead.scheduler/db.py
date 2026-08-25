#
# Scheduler — database layer
#
# Schema creation, every SQL statement the app issues, and the row models those
# statements return.
#
# Those row models are network models: they describe how SQLite hands data
# back, not what the app means by it. Fields are spelled as the columns are, so
# building one is a splat; booleans arrive as integers and JSON as text,
# because that is what the store holds.
#
# This module knows nothing about the domain and imports nothing from
# `model.py`. `lib.py` imports both and owns the conversion.
#
# Dates are `YYYY-MM-DD` and times are `HH:MM`, both in the business's own
# timezone: a business opens at nine o'clock wherever it is, and the hour it
# opens does not move when the offset does. Timestamps that mark a moment —
# when a session expires, when a row was written — are ISO 8601 UTC.
#

import logging
import os
import sqlite3

from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from lib import get_config

DB_NAME = "scheduler.sqlite3"

# Bump when a `create_version_*` function is added, and add it to the chain in
# `start_database`.
CURRENT_VERSION = "1.0.0"


def set_database_name(name: str):
    """Point the app at a different database file.

    Tests call this so a run never touches the real database.
    """
    global DB_NAME
    DB_NAME = name


def get_db_path() -> str:
    cfg = get_config()
    return os.path.join(cfg.db_path, DB_NAME)


def delete_database():
    """Remove the database file. Used by tests between cases."""
    path = get_db_path()
    if os.path.isfile(path):
        os.unlink(path)


def get_conn():
    """Connection to the Scheduler database.

    Foreign keys are enforced per connection in SQLite and default to off. The
    schema leans on them throughout — a job type's sizes belong to the job
    type, a business's employees to the business — so every connection turns
    them on.
    """
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Every statement closes its connection in a `finally`, and must keep doing so.
#
# A statement that fails — a NOT NULL violation, a bad column name — leaves its
# connection with `in_transaction` true, holding SQLite's write lock. If that
# connection is never closed, every later write in the process fails with
# "database is locked": one rejected request bricks the app until it restarts.
#
# This does not reproduce in a test. CPython drops the frame as the exception
# propagates, the connection is refcounted to zero and closed, and the lock
# goes with it. A web server is different — it retains the traceback to render
# its 500, the traceback holds the frame, and the frame holds the connection.
# So the `finally` is load-bearing in production and invisible in the suite.

def select(query: str, params: Optional[tuple] = None) -> List[Any]:
    conn = get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        records = cursor.fetchall()
        cursor.close()
        return records
    finally:
        conn.close()


def update(query: str, params: tuple) -> int:
    """Run a statement and return the number of rows it changed.

    The count is returned rather than asserted: several rules depend on an
    update matching nothing — spending a verification code another request
    already spent, for instance — and that is an outcome, not an error.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        changed = cursor.rowcount
        cursor.close()
        return changed
    finally:
        conn.close()


def insert(query: str, params: tuple) -> int:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rowid = cursor.lastrowid
        conn.commit()
        cursor.close()
        return rowid
    finally:
        conn.close()


def get_db_version(conn) -> Optional[tuple]:
    """Current schema version, or `None` when the database is not yet created."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT version
            FROM versions
            ORDER BY id DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()
    except sqlite3.OperationalError:
        return None
    if not latest:
        raise Exception("Could not read the Scheduler database version. This is fatal.")
    return tuple(int(v) for v in latest[0].split("."))


def create_version_1_0_0(conn, version):
    """Create the initial schema.

    Returns without doing anything when the database is already at this
    version or beyond, so `start_database` can call every version in turn.
    """
    if version is not None and version >= (1, 0, 0):
        return

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            create_date TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE contact_field_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            field_type TEXT NOT NULL,       -- text | phone | email | address_line | city | state | zip
            otp_capable INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE system_holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT NOT NULL,
            country_name TEXT NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,             -- ISO 8601: YYYY-MM-DD
            year INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE vendor_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_type TEXT NOT NULL,      -- email | sms | payment
            vendor_name TEXT NOT NULL,      -- sendgrid | twilio | stripe
            config_json TEXT NOT NULL,      -- JSON blob of vendor-specific credentials
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE business_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon_id INTEGER REFERENCES icons(id),
            -- pre-configured defaults (JSON blob mirrors business config fields)
            config_json TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE icons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER REFERENCES businesses(id), -- NULL = system icon
            filename TEXT NOT NULL,
            is_system INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE business_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL REFERENCES businesses(id),
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'operator'   -- operator | superadmin
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE business_holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL REFERENCES businesses(id),
            holiday_id INTEGER NOT NULL REFERENCES system_holidays(id),
            year INTEGER NOT NULL
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE employee_schedule_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            day_of_week INTEGER NOT NULL,   -- 0=Sunday … 6=Saturday
            start_time TEXT NOT NULL,       -- HH:MM (24h, business local time)
            end_time TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE employee_time_off (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            date TEXT NOT NULL,             -- YYYY-MM-DD
            start_time TEXT NOT NULL,       -- HH:MM
            end_time TEXT NOT NULL
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE job_type_sizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type_id INTEGER NOT NULL REFERENCES job_types(id),
            name TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            cost REAL NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE job_type_employees (
            -- employees who can perform this job type
            job_type_id INTEGER NOT NULL REFERENCES job_types(id),
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            PRIMARY KEY (job_type_id, employee_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE job_type_contact_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type_id INTEGER NOT NULL REFERENCES job_types(id),
            contact_field_type_id INTEGER NOT NULL REFERENCES contact_field_types(id),
            is_required INTEGER NOT NULL DEFAULT 1,
            require_otp INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE job_type_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type_id INTEGER NOT NULL REFERENCES job_types(id),
            name TEXT NOT NULL,
            attribute_type TEXT NOT NULL,   -- text | number | dropdown | checkbox
            options_json TEXT,              -- JSON array for dropdown options
            is_required INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE job_employees (
            job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            PRIMARY KEY (job_id, employee_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE job_contact_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
            contact_field_type_id INTEGER NOT NULL REFERENCES contact_field_types(id),
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE job_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
            job_type_attribute_id INTEGER NOT NULL REFERENCES job_type_attributes(id),
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE appointment_access_attempts (
            -- One row per failed verification, so the lock can ask how many happened
            -- inside the last minute. A counter on the code row cannot: it knows how
            -- many, never how recently, and the rule is a rate rather than a total.
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
            create_date TEXT NOT NULL      -- ISO 8601 UTC
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE job_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES scheduled_jobs(id),
            amount REAL NOT NULL,
            method TEXT NOT NULL,           -- stripe | cash | other
            stripe_payment_intent_id TEXT,
            collected_by_user_id INTEGER,
            note TEXT,
            create_date TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
        CREATE TABLE customer_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            business_id INTEGER NOT NULL REFERENCES businesses(id),
            note TEXT NOT NULL,
            created_by_user_id INTEGER NOT NULL,
            create_date TEXT NOT NULL DEFAULT (datetime('now')),
            update_date TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    _seed_system_config(cursor)
    _seed_contact_field_types(cursor)
    _seed_business_templates(cursor)

    cursor.execute("INSERT INTO versions (version) VALUES (?)", (CURRENT_VERSION,))
    conn.commit()
    cursor.close()


# =========================================================================
# Seeds
#
# What every installation starts with. Seeded once, as part of creating the
# schema, so a business that has configured nothing still has field types to
# choose from and templates to start from.
# =========================================================================


def _seed_system_config(cursor):
    """Platform settings a super admin may change, with their starting values."""
    cursor.executemany(
        "INSERT INTO system_config (key, value) VALUES (?, ?)",
        [
            # How long a customer has to finish scheduling before the time
            # they are holding is released.
            ("schedule_timeout_minutes", "10")
        ]
    )


def _seed_contact_field_types(cursor):
    """The kinds of contact information a job type may ask a customer for.

    A business chooses from these; it does not invent them. `otp_capable`
    marks the two that can receive a code, which is what a job type needs
    before it can ask for one to be verified.
    """
    cursor.executemany(
        """
        INSERT INTO contact_field_types (name, field_type, otp_capable, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("First Name",     "text",          0, 1),
            ("Last Name",      "text",          0, 2),
            ("Phone",          "phone",         1, 3),
            ("Email",          "email",         1, 4),
            ("Address Line 1", "address_line",  0, 5),
            ("Address Line 2", "address_line",  0, 6),
            ("City",           "city",          0, 7),
            ("State",          "state",         0, 8),
            ("Zip",            "zip",           0, 9)
        ]
    )


def _seed_business_templates(cursor):
    """Starting points a new business may take its settings from.

    `config_json` holds only the settings a template has an opinion about;
    anything it leaves out keeps the column default. Food & Drink is the one
    that changes how scheduling works at all — a queue rather than a diary —
    so it says so.
    """
    templates = [
        ("Personal Service",
         "Salons, spas, fitness studios. Clients choose their service provider.",
         '{"allowCustomerEmployeeSelection": true, "slotIncrementMinutes": 15}'),
        ("Field Service",
         "Landscaping, cleaning, home repair. Technicians go to the customer.",
         '{"notifyEmployees": true, "bufferMinutes": 30, "slotIncrementMinutes": 30}'),
        ("Healthcare/Wellness",
         "Dental, chiropractic, therapy. Privacy and verification matter.",
         '{"slotIncrementMinutes": 15, "bufferMinutes": 15}'),
        ("Pet Services",
         "Grooming, walking, sitting. Mix of at-location and field visits.",
         '{"allowCustomerEmployeeSelection": true, "bufferMinutes": 15}'),
        ("General",
         "A flexible starting point for any service business.",
         '{}'),
        ("Food & Drink",
         "Cafés, bakeries, takeaway. Customers choose a pickup time and you "
         "handle the queue.",
         '{"slotMode": "unlimited", "minBookingNoticeHours": 0, "bufferMinutes": 0}')
    ]
    cursor.executemany(
        """
        INSERT INTO business_templates (name, description, config_json)
        VALUES (?, ?, ?)
        """,
        templates
    )


def start_database():
    """Create or migrate the database. Called once when the service starts."""
    conn = get_conn()
    try:
        version = get_db_version(conn)
        logging.info(f"Scheduler database version ({version})")
        create_version_1_0_0(conn, version)
    finally:
        conn.close()


# =========================================================================
# Row models
#
# One per query shape, table-shaped or not: joining to save a round trip is
# the data layer's business, and the shape it returns is its own. A query
# selecting a single column returns a list of values instead — a scalar is not
# a shape.
# =========================================================================


class BusinessRow(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    timezone: str
    slot_mode: str
    slot_increment_minutes: int
    cutoff_days: int
    min_booking_notice_hours: int
    min_change_notice_minutes: int
    buffer_minutes: int
    is_active: int


class BusinessHoursRow(BaseModel):
    day_of_week: int
    open_time: str
    close_time: str
    is_closed: int


class JobTypeRow(BaseModel):
    id: int
    business_id: int
    name: str
    min_employees: int
    is_active: int


class JobTypeSizeRow(BaseModel):
    id: int
    job_type_id: int
    name: str
    duration_minutes: int
    cost: float


class EmployeeRow(BaseModel):
    id: int
    business_id: int
    first_name: str
    last_name: str
    include_in_schedule: int
    can_manage_own_schedule: int


class EmployeeScheduleRow(BaseModel):
    id: int
    employee_id: int
    day_of_week: int
    start_time: str
    end_time: str


class EmployeeTimeOffRow(BaseModel):
    id: int
    employee_id: int
    date: str
    start_time: str
    end_time: str


class BookedIntervalRow(BaseModel):
    """A stretch of an employee's day that is already spoken for."""
    employee_id: int
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int


def _one(query: str, params: tuple):
    rows = select(query, params)
    return rows[0] if rows else None


def _one_as(model, query: str, params: tuple):
    row = _one(query, params)
    return model(**row) if row else None


def _all_as(model, query: str, params: Optional[tuple] = None) -> List[Any]:
    return [model(**r) for r in select(query, params)]


# --- Businesses ----------------------------------------------------------

BUSINESS_COLUMNS = """
    id, name, phone, timezone, slot_mode, slot_increment_minutes, cutoff_days,
    min_booking_notice_hours, min_change_notice_minutes, buffer_minutes, is_active
"""


def get_business(business_id: int) -> Optional[BusinessRow]:
    return _one_as(BusinessRow,
                   f"SELECT {BUSINESS_COLUMNS} FROM businesses WHERE id = ?",
                   (business_id,))


def insert_business(name: str, timezone: str, slot_mode: str) -> int:
    return insert(
        "INSERT INTO businesses (name, timezone, slot_mode) VALUES (?, ?, ?)",
        (name, timezone, slot_mode)
    )


def set_business_scheduling(business_id: int, slot_increment_minutes: int,
                            cutoff_days: int, min_booking_notice_hours: int,
                            buffer_minutes: int) -> int:
    return update(
        """
        UPDATE businesses
        SET slot_increment_minutes = ?, cutoff_days = ?,
            min_booking_notice_hours = ?, buffer_minutes = ?,
            update_date = datetime('now')
        WHERE id = ?
        """,
        (slot_increment_minutes, cutoff_days, min_booking_notice_hours,
         buffer_minutes, business_id)
    )


# --- Operating hours -----------------------------------------------------

def get_business_hours(business_id: int) -> List[BusinessHoursRow]:
    return _all_as(BusinessHoursRow,
                   """
                   SELECT day_of_week, open_time, close_time, is_closed
                   FROM business_hours WHERE business_id = ?
                   ORDER BY day_of_week
                   """,
                   (business_id,))


def set_business_hours(business_id: int, day_of_week: int, open_time: str,
                       close_time: str, is_closed: int) -> int:
    update("DELETE FROM business_hours WHERE business_id = ? AND day_of_week = ?",
           (business_id, day_of_week))
    return insert(
        """
        INSERT INTO business_hours (business_id, day_of_week, open_time, close_time, is_closed)
        VALUES (?, ?, ?, ?, ?)
        """,
        (business_id, day_of_week, open_time, close_time, is_closed)
    )


def is_holiday(business_id: int, date: str) -> bool:
    """Whether the business observes a holiday on this date.

    A business does not keep its own dates: it observes one of the system
    holidays for a given year, so the date comes from there.
    """
    row = _one(
        """
        SELECT 1
        FROM business_holidays bh
        JOIN system_holidays sh ON sh.id = bh.holiday_id
        WHERE bh.business_id = ? AND sh.date = ?
        """,
        (business_id, date)
    )
    return row is not None


def insert_system_holiday(country_code: str, country_name: str, name: str,
                          date: str, year: int) -> int:
    return insert(
        """
        INSERT INTO system_holidays (country_code, country_name, name, date, year)
        VALUES (?, ?, ?, ?, ?)
        """,
        (country_code, country_name, name, date, year)
    )


def observe_holiday(business_id: int, holiday_id: int, year: int) -> int:
    """Close the business on a system holiday, for one year."""
    return insert(
        "INSERT INTO business_holidays (business_id, holiday_id, year) VALUES (?, ?, ?)",
        (business_id, holiday_id, year)
    )


# --- Job types -----------------------------------------------------------

def get_job_type(job_type_id: int) -> Optional[JobTypeRow]:
    return _one_as(JobTypeRow,
                   "SELECT id, business_id, name, min_employees, is_active"
                   " FROM job_types WHERE id = ?",
                   (job_type_id,))


def insert_job_type(business_id: int, name: str, min_employees: int) -> int:
    return insert(
        "INSERT INTO job_types (business_id, name, min_employees) VALUES (?, ?, ?)",
        (business_id, name, min_employees)
    )


def set_job_type_active(job_type_id: int, is_active: int) -> int:
    return update("UPDATE job_types SET is_active = ? WHERE id = ?",
                  (is_active, job_type_id))


def get_job_type_size(size_id: int) -> Optional[JobTypeSizeRow]:
    return _one_as(JobTypeSizeRow,
                   "SELECT id, job_type_id, name, duration_minutes, cost"
                   " FROM job_type_sizes WHERE id = ?",
                   (size_id,))


def insert_job_type_size(job_type_id: int, name: str, duration_minutes: int,
                         cost: float) -> int:
    return insert(
        """
        INSERT INTO job_type_sizes (job_type_id, name, duration_minutes, cost)
        VALUES (?, ?, ?, ?)
        """,
        (job_type_id, name, duration_minutes, cost)
    )


# --- Employees -----------------------------------------------------------

def insert_employee(business_id: int, first_name: str, last_name: str,
                    include_in_schedule: int) -> int:
    return insert(
        """
        INSERT INTO employees (business_id, first_name, last_name, include_in_schedule)
        VALUES (?, ?, ?, ?)
        """,
        (business_id, first_name, last_name, include_in_schedule)
    )


def get_employees_for_job_type(job_type_id: int) -> List[EmployeeRow]:
    """Employees who can perform a job type and are in the schedule at all."""
    return _all_as(EmployeeRow,
                   """
                   SELECT e.id, e.business_id, e.first_name, e.last_name,
                          e.include_in_schedule, e.can_manage_own_schedule
                   FROM employees e
                   JOIN job_type_employees jte ON jte.employee_id = e.id
                   WHERE jte.job_type_id = ? AND e.include_in_schedule = 1
                   ORDER BY e.id
                   """,
                   (job_type_id,))


def link_employee_to_job_type(job_type_id: int, employee_id: int) -> int:
    return insert(
        "INSERT INTO job_type_employees (job_type_id, employee_id) VALUES (?, ?)",
        (job_type_id, employee_id)
    )


def get_employee_schedule(employee_id: int) -> List[EmployeeScheduleRow]:
    return _all_as(EmployeeScheduleRow,
                   """
                   SELECT id, employee_id, day_of_week, start_time, end_time
                   FROM employee_schedule_templates WHERE employee_id = ?
                   ORDER BY day_of_week, start_time
                   """,
                   (employee_id,))


def insert_employee_schedule(employee_id: int, day_of_week: int,
                             start_time: str, end_time: str) -> int:
    return insert(
        """
        INSERT INTO employee_schedule_templates (employee_id, day_of_week, start_time, end_time)
        VALUES (?, ?, ?, ?)
        """,
        (employee_id, day_of_week, start_time, end_time)
    )


def get_employee_time_off(employee_id: int, date: str) -> List[EmployeeTimeOffRow]:
    return _all_as(EmployeeTimeOffRow,
                   """
                   SELECT id, employee_id, date, start_time, end_time
                   FROM employee_time_off WHERE employee_id = ? AND date = ?
                   ORDER BY start_time
                   """,
                   (employee_id, date))


def insert_employee_time_off(employee_id: int, date: str, start_time: str,
                             end_time: str) -> int:
    return insert(
        """
        INSERT INTO employee_time_off (employee_id, date, start_time, end_time)
        VALUES (?, ?, ?, ?)
        """,
        (employee_id, date, start_time, end_time)
    )


# --- Scheduled jobs ------------------------------------------------------

# A job holds an employee's time while it is confirmed, and while it is still
# pending inside its session's lifetime. A pending job whose session has
# expired holds nothing: the customer walked away and the time went back.
def get_booked_intervals(employee_ids: List[int], date: str) -> List[BookedIntervalRow]:
    """Every stretch of the day these employees are already committed to."""
    if not employee_ids:
        return []
    marks = ",".join("?" for _ in employee_ids)
    return _all_as(
        BookedIntervalRow,
        f"""
        SELECT je.employee_id, j.scheduled_date, j.scheduled_time, j.duration_minutes
        FROM scheduled_jobs j
        JOIN job_employees je ON je.job_id = j.id
        LEFT JOIN job_sessions s ON s.job_id = j.id
        WHERE je.employee_id IN ({marks})
          AND j.scheduled_date = ?
          AND j.status IN ('pending', 'confirmed')
          AND (j.status = 'confirmed' OR s.expires_at > datetime('now'))
        """,
        tuple(employee_ids) + (date,)
    )


def insert_scheduled_job(job_code: str, business_id: int, job_type_id: int,
                         size_id: Optional[int], scheduled_date: str,
                         scheduled_time: str, duration_minutes: int,
                         status: str) -> int:
    return insert(
        """
        INSERT INTO scheduled_jobs
            (job_code, business_id, job_type_id, job_type_size_id,
             scheduled_date, scheduled_time, duration_minutes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (job_code, business_id, job_type_id, size_id, scheduled_date,
         scheduled_time, duration_minutes, status)
    )


def assign_employee_to_job(job_id: int, employee_id: int) -> int:
    return insert(
        "INSERT INTO job_employees (job_id, employee_id) VALUES (?, ?)",
        (job_id, employee_id)
    )


def insert_job_session(job_id: int, session_token: str, expires_at: str) -> int:
    """`expires_at` is an ISO 8601 UTC timestamp, decided by `lib`.

    The clock lives there rather than in SQL, so a caller can say what moment
    to reckon from — which is what makes the lifetime testable.
    """
    return insert(
        """
        INSERT INTO job_sessions (job_id, session_token, expires_at)
        VALUES (?, ?, ?)
        """,
        (job_id, session_token, expires_at)
    )


# --- Seeded platform records ---------------------------------------------

class ContactFieldTypeRow(BaseModel):
    id: int
    name: str
    field_type: str
    otp_capable: int
    sort_order: int


class BusinessTemplateRow(BaseModel):
    id: int
    name: str
    description: str
    config_json: str


def get_contact_field_types() -> List[ContactFieldTypeRow]:
    return _all_as(ContactFieldTypeRow,
                   "SELECT id, name, field_type, otp_capable, sort_order"
                   " FROM contact_field_types ORDER BY sort_order")


def get_business_templates() -> List[BusinessTemplateRow]:
    return _all_as(BusinessTemplateRow,
                   "SELECT id, name, description, config_json"
                   " FROM business_templates ORDER BY id")


def get_system_config(key: str) -> Optional[str]:
    row = _one("SELECT value FROM system_config WHERE key = ?", (key,))
    return row[0] if row else None


def set_system_config(key: str, value: str) -> int:
    return update("UPDATE system_config SET value = ? WHERE key = ?", (value, key))


class ScheduledJobRow(BaseModel):
    id: int
    job_code: str
    business_id: int
    job_type_id: int
    job_type_size_id: Optional[int]
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int
    status: str


class JobSessionRow(BaseModel):
    id: int
    job_id: int
    session_token: str
    expires_at: str


def get_scheduled_job(job_id: int) -> Optional[ScheduledJobRow]:
    return _one_as(ScheduledJobRow,
                   """
                   SELECT id, job_code, business_id, job_type_id, job_type_size_id,
                          scheduled_date, scheduled_time, duration_minutes, status
                   FROM scheduled_jobs WHERE id = ?
                   """,
                   (job_id,))


def get_session(session_token: str) -> Optional[JobSessionRow]:
    return _one_as(JobSessionRow,
                   "SELECT id, job_id, session_token, expires_at"
                   " FROM job_sessions WHERE session_token = ?",
                   (session_token,))


def set_job_status(job_id: int, status: str) -> int:
    return update("UPDATE scheduled_jobs SET status = ?, update_date = datetime('now')"
                  " WHERE id = ?", (status, job_id))


def get_job_employee_ids(job_id: int) -> List[int]:
    return [r[0] for r in select(
        "SELECT employee_id FROM job_employees WHERE job_id = ? ORDER BY employee_id",
        (job_id,)
    )]


# =========================================================================
# For tests
#
# Statements that exist only so a test can reach a situation no interface can
# produce — the passage of time, so far. They ship with the app, which is the
# trade: storage stays entirely inside this module, so moving off SQLite
# changes this file and nothing in `private/tests`.
# =========================================================================


def expire_session(session_token: str) -> int:
    """Move a hold's expiry into the past, as waiting would."""
    return update(
        "UPDATE job_sessions SET expires_at = datetime('now', '-1 minutes')"
        " WHERE session_token = ?",
        (session_token,)
    )


class AppointmentRow(BaseModel):
    id: int
    job_code: str
    business_name: str
    business_phone: Optional[str]
    min_change_notice_minutes: int
    job_type_name: str
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int
    status: str


def get_appointment(job_id: int) -> Optional[AppointmentRow]:
    """A booking with the two names the customer's screen shows."""
    return _one_as(AppointmentRow,
                   """
                   SELECT j.id, j.job_code, b.name AS business_name,
                          b.phone AS business_phone, b.min_change_notice_minutes,
                          jt.name AS job_type_name, j.scheduled_date,
                          j.scheduled_time, j.duration_minutes, j.status
                   FROM scheduled_jobs j
                   JOIN businesses b ON b.id = j.business_id
                   JOIN job_types jt ON jt.id = j.job_type_id
                   WHERE j.id = ?
                   """,
                   (job_id,))


def set_job_schedule(job_id: int, scheduled_date: str, scheduled_time: str) -> int:
    return update(
        "UPDATE scheduled_jobs SET scheduled_date = ?, scheduled_time = ?,"
        " update_date = datetime('now') WHERE id = ?",
        (scheduled_date, scheduled_time, job_id)
    )


def set_business_change_notice(business_id: int, minutes: int) -> int:
    return update(
        "UPDATE businesses SET min_change_notice_minutes = ?,"
        " update_date = datetime('now') WHERE id = ?",
        (minutes, business_id)
    )


def extend_session(session_token: str, expires_at: str) -> int:
    """Move a hold's expiry to a moment `lib` worked out."""
    return update(
        "UPDATE job_sessions SET expires_at = ? WHERE session_token = ?",
        (expires_at, session_token)
    )


def set_job_finalized(job_id: int) -> int:
    """Mark a booking as finished with, so the sweep leaves its session alone."""
    return update("UPDATE scheduled_jobs SET finalized = 1 WHERE id = ?", (job_id,))


def delete_expired_sessions() -> int:
    """Remove lapsed holds whose appointment was never finished.

    A confirmed booking keeps its session record, which is what `finalized`
    distinguishes. The `scheduled_jobs` row is left either way.
    """
    return update(
        """
        DELETE FROM job_sessions
        WHERE expires_at < datetime('now')
          AND job_id IN (SELECT id FROM scheduled_jobs WHERE finalized = 0)
        """,
        ()
    )


def set_otp(session_token: str, otp_hash: str) -> int:
    """Record the code that was just sent, and start the attempts over."""
    return update(
        "UPDATE job_sessions SET otp_hash = ?, otp_attempts = 0, otp_verified = 0"
        " WHERE session_token = ?",
        (otp_hash, session_token)
    )


def get_otp(session_token: str) -> Optional[tuple]:
    """`(otp_hash, otp_attempts, otp_verified)` for a session, or `None`."""
    row = _one(
        "SELECT otp_hash, otp_attempts, otp_verified FROM job_sessions"
        " WHERE session_token = ?",
        (session_token,)
    )
    return (row[0], row[1], row[2]) if row else None


def count_otp_attempt(session_token: str) -> int:
    return update(
        "UPDATE job_sessions SET otp_attempts = otp_attempts + 1"
        " WHERE session_token = ?",
        (session_token,)
    )


def set_otp_verified(session_token: str) -> int:
    return update(
        "UPDATE job_sessions SET otp_verified = 1 WHERE session_token = ?",
        (session_token,)
    )


class JobContactRow(BaseModel):
    field_type: str
    name: str
    value: str


def insert_job_contact(job_id: int, contact_field_type_id: int, value: str) -> int:
    return insert(
        "INSERT INTO job_contact_info (job_id, contact_field_type_id, value)"
        " VALUES (?, ?, ?)",
        (job_id, contact_field_type_id, value)
    )


def get_job_contact(job_id: int) -> List[JobContactRow]:
    """What the customer gave, with the kind of thing each value is."""
    return _all_as(JobContactRow,
                   """
                   SELECT t.field_type, t.name, c.value
                   FROM job_contact_info c
                   JOIN contact_field_types t ON t.id = c.contact_field_type_id
                   WHERE c.job_id = ?
                   ORDER BY t.sort_order
                   """,
                   (job_id,))


def get_contact_field_type_by_name(name: str):
    return _one("SELECT id FROM contact_field_types WHERE name = ?", (name,))


def get_job_by_code(job_code: str) -> Optional[ScheduledJobRow]:
    return _one_as(ScheduledJobRow,
                   """
                   SELECT id, job_code, business_id, job_type_id, job_type_size_id,
                          scheduled_date, scheduled_time, duration_minutes, status
                   FROM scheduled_jobs WHERE job_code = ?
                   """,
                   (job_code,))


class AccessCodeRow(BaseModel):
    id: int
    job_id: int
    code_hash: str
    channel: str
    sent_to: str
    attempts: int
    used_date: Optional[str]
    expires_at: str


def insert_access_code(job_id: int, code_hash: str, channel: str, sent_to: str,
                       expires_at: str) -> int:
    return insert(
        """
        INSERT INTO appointment_access_codes
            (job_id, code_hash, channel, sent_to, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, code_hash, channel, sent_to, expires_at)
    )


def get_latest_access_code(job_id: int) -> Optional[AccessCodeRow]:
    """The most recent code sent for a job. Asking again replaces the one before."""
    return _one_as(AccessCodeRow,
                   """
                   SELECT id, job_id, code_hash, channel, sent_to, attempts,
                          used_date, expires_at
                   FROM appointment_access_codes
                   WHERE job_id = ?
                   ORDER BY id DESC LIMIT 1
                   """,
                   (job_id,))


def spend_access_code(code_id: int, used_date: str) -> int:
    return update("UPDATE appointment_access_codes SET used_date = ? WHERE id = ?",
                  (used_date, code_id))


def count_access_attempt(code_id: int) -> int:
    return update("UPDATE appointment_access_codes SET attempts = attempts + 1"
                  " WHERE id = ?", (code_id,))


def insert_access_attempt(job_id: int, create_date: str) -> int:
    """Record a failed verification, so the lock can count recent ones."""
    return insert(
        "INSERT INTO appointment_access_attempts (job_id, create_date) VALUES (?, ?)",
        (job_id, create_date)
    )


def count_recent_access_attempts(job_id: int, since: str) -> int:
    row = _one(
        "SELECT COUNT(*) FROM appointment_access_attempts"
        " WHERE job_id = ? AND create_date > ?",
        (job_id, since)
    )
    return row[0] if row else 0


def lock_job(job_id: int, locked_date: str) -> int:
    """Shut the customer's door on this appointment, for good.

    Never cleared. There is no route that sets `locked_date` back to null, and
    that is the point: the business reopens the booking by making a new one.
    """
    return update("UPDATE scheduled_jobs SET locked_date = ? WHERE id = ?",
                  (locked_date, job_id))


def get_job_locked_date(job_id: int) -> Optional[str]:
    row = _one("SELECT locked_date FROM scheduled_jobs WHERE id = ?", (job_id,))
    return row[0] if row else None


def insert_job_code_attempt(caller: str, create_date: str,
                            blocked_until: Optional[str] = None) -> int:
    return insert(
        "INSERT INTO job_code_attempts (caller, create_date, blocked_until)"
        " VALUES (?, ?, ?)",
        (caller, create_date, blocked_until)
    )


def count_recent_job_code_attempts(caller: str, since: str) -> int:
    row = _one(
        "SELECT COUNT(*) FROM job_code_attempts"
        " WHERE caller = ? AND create_date > ?",
        (caller, since)
    )
    return row[0] if row else 0


def is_caller_blocked(caller: str, moment: str) -> bool:
    row = _one(
        "SELECT 1 FROM job_code_attempts"
        " WHERE caller = ? AND blocked_until IS NOT NULL AND blocked_until > ?",
        (caller, moment)
    )
    return row is not None


class RecurrenceRow(BaseModel):
    id: int
    business_id: int
    job_type_id: int
    job_type_size_id: Optional[int]
    interval_type: str
    days_of_week_json: Optional[str]
    preferred_time: str
    is_active: int


def insert_recurrence(business_id: int, job_type_id: int, size_id: Optional[int],
                      interval_type: str, days_of_week_json: Optional[str],
                      preferred_time: str) -> int:
    return insert(
        """
        INSERT INTO recurrences
            (business_id, job_type_id, job_type_size_id, interval_type,
             days_of_week_json, preferred_time)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (business_id, job_type_id, size_id, interval_type, days_of_week_json,
         preferred_time)
    )


RECURRENCE_COLUMNS = """
    id, business_id, job_type_id, job_type_size_id, interval_type,
    days_of_week_json, preferred_time, is_active
"""


def get_recurrence(recurrence_id: int) -> Optional[RecurrenceRow]:
    return _one_as(RecurrenceRow,
                   f"SELECT {RECURRENCE_COLUMNS} FROM recurrences WHERE id = ?",
                   (recurrence_id,))


def get_active_recurrences() -> List[RecurrenceRow]:
    return _all_as(RecurrenceRow,
                   f"SELECT {RECURRENCE_COLUMNS} FROM recurrences"
                   " WHERE is_active = 1 ORDER BY id")


def set_recurrence_active(recurrence_id: int, is_active: int) -> int:
    return update("UPDATE recurrences SET is_active = ? WHERE id = ?",
                  (is_active, recurrence_id))


def recurrence_instance_exists(recurrence_id: int, scheduled_date: str) -> bool:
    row = _one(
        "SELECT 1 FROM scheduled_jobs WHERE recurrence_id = ? AND scheduled_date = ?",
        (recurrence_id, scheduled_date)
    )
    return row is not None


def insert_recurring_job(job_code: str, business_id: int, job_type_id: int,
                         size_id: Optional[int], scheduled_date: str,
                         scheduled_time: str, duration_minutes: int,
                         recurrence_id: int) -> int:
    return insert(
        """
        INSERT INTO scheduled_jobs
            (job_code, business_id, job_type_id, job_type_size_id,
             scheduled_date, scheduled_time, duration_minutes, status,
             is_recurring, recurrence_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', 1, ?)
        """,
        (job_code, business_id, job_type_id, size_id, scheduled_date,
         scheduled_time, duration_minutes, recurrence_id)
    )


def get_jobs_for_recurrence(recurrence_id: int) -> List[ScheduledJobRow]:
    return _all_as(ScheduledJobRow,
                   """
                   SELECT id, job_code, business_id, job_type_id, job_type_size_id,
                          scheduled_date, scheduled_time, duration_minutes, status
                   FROM scheduled_jobs WHERE recurrence_id = ?
                   ORDER BY scheduled_date
                   """,
                   (recurrence_id,))


def get_unassigned_jobs(business_id: int) -> List[ScheduledJobRow]:
    """Live appointments with nobody on them."""
    return _all_as(ScheduledJobRow,
                   """
                   SELECT j.id, j.job_code, j.business_id, j.job_type_id,
                          j.job_type_size_id, j.scheduled_date, j.scheduled_time,
                          j.duration_minutes, j.status
                   FROM scheduled_jobs j
                   LEFT JOIN job_employees je ON je.job_id = j.id
                   WHERE j.business_id = ? AND j.status IN ('pending', 'confirmed')
                     AND je.job_id IS NULL
                   ORDER BY j.scheduled_date, j.scheduled_time
                   """,
                   (business_id,))


def set_business_confirmation(business_id: int, by_sms: int, by_email: int) -> int:
    return update(
        "UPDATE businesses SET confirm_by_sms = ?, confirm_by_email = ?,"
        " update_date = datetime('now') WHERE id = ?",
        (by_sms, by_email, business_id)
    )


def set_business_phone(business_id: int, phone: str) -> int:
    return update(
        "UPDATE businesses SET phone = ?, update_date = datetime('now') WHERE id = ?",
        (phone, business_id)
    )


class ConfirmationJobRow(BaseModel):
    """What a confirmation message is written from."""
    job_code: str
    business_name: str
    business_phone: Optional[str]
    confirm_by_sms: int
    confirm_by_email: int
    job_type_name: str
    scheduled_date: str
    scheduled_time: str


def get_confirmation_details(job_id: int) -> Optional[ConfirmationJobRow]:
    return _one_as(ConfirmationJobRow,
                   """
                   SELECT j.job_code, b.name AS business_name,
                          b.phone AS business_phone, b.confirm_by_sms,
                          b.confirm_by_email, jt.name AS job_type_name,
                          j.scheduled_date, j.scheduled_time
                   FROM scheduled_jobs j
                   JOIN businesses b ON b.id = j.business_id
                   JOIN job_types jt ON jt.id = j.job_type_id
                   WHERE j.id = ?
                   """,
                   (job_id,))


class TransactionRow(BaseModel):
    id: int
    job_id: int
    amount: float
    method: str
    collected_by_user_id: Optional[int]
    note: Optional[str]
    create_date: str


def insert_transaction(job_id: int, amount: float, method: str,
                       collected_by_user_id: Optional[int] = None,
                       note: Optional[str] = None) -> int:
    return insert(
        """
        INSERT INTO job_transactions
            (job_id, amount, method, collected_by_user_id, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, amount, method, collected_by_user_id, note)
    )


def get_transactions(job_id: int) -> List[TransactionRow]:
    return _all_as(TransactionRow,
                   """
                   SELECT id, job_id, amount, method, collected_by_user_id,
                          note, create_date
                   FROM job_transactions WHERE job_id = ? ORDER BY id
                   """,
                   (job_id,))


def get_paid_total(job_id: int) -> float:
    row = _one("SELECT COALESCE(SUM(amount), 0) FROM job_transactions WHERE job_id = ?",
               (job_id,))
    return float(row[0]) if row else 0.0


def set_payment_status(job_id: int, status: str) -> int:
    return update(
        "UPDATE scheduled_jobs SET payment_status = ?, update_date = datetime('now')"
        " WHERE id = ?", (status, job_id)
    )


def get_payment_status(job_id: int) -> Optional[str]:
    row = _one("SELECT payment_status FROM scheduled_jobs WHERE id = ?", (job_id,))
    return row[0] if row else None


class JobCostRow(BaseModel):
    """What a job costs, and what a deposit on it would be."""
    cost: Optional[float]
    deposit_required: int
    deposit_type: Optional[str]
    deposit_amount: Optional[float]


def get_job_cost(job_id: int) -> Optional[JobCostRow]:
    return _one_as(JobCostRow,
                   """
                   SELECT s.cost, jt.deposit_required, jt.deposit_type,
                          jt.deposit_amount
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   LEFT JOIN job_type_sizes s ON s.id = j.job_type_size_id
                   WHERE j.id = ?
                   """,
                   (job_id,))


def set_job_type_deposit(job_type_id: int, deposit_type: str,
                         deposit_amount: float) -> int:
    return update(
        "UPDATE job_types SET deposit_required = 1, deposit_type = ?,"
        " deposit_amount = ? WHERE id = ?",
        (deposit_type, deposit_amount, job_type_id)
    )


def set_business_completion_mode(business_id: int, mode: str) -> int:
    return update(
        "UPDATE businesses SET completion_mode = ?, update_date = datetime('now')"
        " WHERE id = ?", (mode, business_id)
    )


def get_business_completion_mode(business_id: int) -> Optional[str]:
    row = _one("SELECT completion_mode FROM businesses WHERE id = ?", (business_id,))
    return row[0] if row else None


class FinishableJobRow(BaseModel):
    """A confirmed appointment whose end time may have passed."""
    id: int
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int


def get_confirmed_jobs_for_auto_completion() -> List[FinishableJobRow]:
    """Confirmed appointments at businesses that finish work automatically.

    Cancelled and already-completed appointments are left out: one did not
    happen, and the other is done.
    """
    return _all_as(FinishableJobRow,
                   """
                   SELECT j.id, j.scheduled_date, j.scheduled_time, j.duration_minutes
                   FROM scheduled_jobs j
                   JOIN businesses b ON b.id = j.business_id
                   WHERE j.status = 'confirmed' AND b.completion_mode = 'auto'
                   ORDER BY j.id
                   """)
