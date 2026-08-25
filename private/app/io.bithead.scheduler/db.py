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
            otp_verified INTEGER NOT NULL DEFAULT 0
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
