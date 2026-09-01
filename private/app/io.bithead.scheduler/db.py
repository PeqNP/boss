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
            -- One choice per kind, as a fact rather than a convention: setting
            -- a vendor clears the previous row, and a path that forgets to
            -- fails here instead of leaving two rows where the answer to
            -- "which service sends the mail" depends on row order.
            vendor_type TEXT NOT NULL UNIQUE,   -- email | sms | payment
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
            -- Who they are to this business. An operator is an employee of the
            -- business they run, holding the operator role — so a one-person
            -- business is one row, and `include_in_schedule` says separately
            -- whether they are given work.
            --
            -- Lower case, because `Me.role` is what the app opens a window on.
            -- The `Role` enum's value is the label BOSS shows in Settings; the
            -- two are related without being the same string.
            role TEXT NOT NULL DEFAULT 'employee',   -- operator | employee
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
    _create_indexes(cursor)

    _seed_system_config(cursor)
    _seed_contact_field_types(cursor)
    _seed_business_templates(cursor)

    cursor.execute("INSERT INTO versions (version) VALUES (?)", (CURRENT_VERSION,))
    conn.commit()
    cursor.close()


# =========================================================================
# Indexes
#
# Anything a query looks a row up *by* gets one. Every internal id does,
# without asking whether a query needs it yet — an unindexed foreign key is a
# table scan that only shows itself once there is enough data for it to hurt,
# which is exactly when nobody wants to be diagnosing it.
#
# Primary keys and UNIQUE columns already have one and are left alone.
#
# The list is derived from the DDL rather than written beside it, so a column
# added to a table is indexed by having been added. A list maintained by hand
# is a list that falls behind.
# =========================================================================

# Columns that are not internal ids but are still looked up by.
BY_VALUE = {
    ("customers", "email"),
    ("customers", "phone"),
    # A Stripe webhook arrives naming one of these and nothing else.
    ("businesses", "stripe_account_id"),
    ("job_transactions", "stripe_payment_intent_id"),
}

# Where a query always narrows by two columns, one index over both beats two
# over one each — the second column is what makes the first selective.
COMPOSITE = [
    ("customers", ("business_id", "user_id")),
    ("business_holidays", ("business_id", "year")),
    ("scheduled_jobs", ("business_id", "scheduled_date")),
    ("system_holidays", ("country_code", "year")),
]

def _expression_indexes() -> List[tuple]:
    """Lookups whose WHERE clause is an expression rather than a bare column.

    An index on an expression helps only a query written the identical way, so
    both are generated from the same function. Built when called rather than at
    import, because `_phone_expression` is defined with the query it serves.
    """
    return [
        ("customers", "business_id, LOWER(email)"),
        ("customers", f"business_id, {_phone_expression()}"),
    ]


def _indexed_columns(cursor) -> List[tuple]:
    """Every (table, column) worth an index, read off the schema itself.

    A primary key already has an index and is skipped — but only its *leading*
    column. SQLite's implicit index on `PRIMARY KEY (job_id, employee_id)`
    answers a lookup by `job_id`, and by both together, and not by
    `employee_id` alone. Skipping every column of a composite key leaves the
    join table's other side unindexed, which is a scan on the query a join
    table exists to serve — "which jobs is this employee on".
    """
    wanted = []
    tables = [r[0] for r in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    for table in tables:
        for row in cursor.execute(f"PRAGMA table_info({table})").fetchall():
            column, pk_position = row[1], row[5]
            # `pk_position` is 0 for a non-key column, else its 1-based place
            # in the key. Position 1 is what the implicit index is sorted by.
            if pk_position == 1:
                continue
            if column.endswith("_id") or (table, column) in BY_VALUE:
                wanted.append((table, column))
    return wanted


# A BOSS account works for one business. Opening a second means a second
# account, as does working for a second employer — which is how a company email
# already works. Stated here so the database refuses a second link rather than
# every path that makes one being trusted to.
#
# `user_id` is NULL until somebody is invited to BOSS, and SQLite allows any
# number of NULLs in a unique index — so an operator adds people long before
# any of them has an account.
UNIQUE_COLUMNS = [
    ("employees", "user_id"),
]


def _create_indexes(cursor):
    for table, column in _indexed_columns(cursor):
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{column}"
                       f" ON {table}({column})")
    for table, columns in COMPOSITE:
        name = "_".join(columns)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{name}"
                       f" ON {table}({', '.join(columns)})")
    for table, column in UNIQUE_COLUMNS:
        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS uq_{table}_{column}"
                       f" ON {table}({column})")
    for i, (table, expression) in enumerate(_expression_indexes()):
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_expr_{i}"
                       f" ON {table}({expression})")


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


def create_schema(conn):
    """Bring a connection up to the current schema, whatever version it is at.

    Every version function in turn, each returning early once its own version
    has been applied. `bin/check-db` runs this into an empty database to see
    what the schema declares, so this is the one definition of that.
    """
    version = get_db_version(conn)
    create_version_1_0_0(conn, version)


def start_database():
    """Create or migrate the database. Called once when the service starts."""
    conn = get_conn()
    try:
        logging.info(f"Scheduler database version ({get_db_version(conn)})")
        create_schema(conn)
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


class BusinessConfigRow(BaseModel):
    """Every column the Business Settings window shows.

    `BusinessRow` is the subset the scheduling rules read, and stays small
    because it is fetched on every slot computation. This is the whole record,
    fetched once when the owner opens the window.
    """
    id: int
    name: str
    phone: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    owner_name: Optional[str]
    description: Optional[str]
    site_url: Optional[str]
    timezone: str
    slot_mode: str
    slot_increment_minutes: int
    cutoff_days: int
    min_booking_notice_hours: int
    min_change_notice_minutes: int
    buffer_minutes: int
    reminder_enabled: int
    confirm_by_sms: int
    confirm_by_email: int
    completion_mode: str
    allow_customer_employee_selection: int
    notify_employees: int
    # Read but never written here: whether the business is trading is the
    # platform's, and `enable_business` is the door.
    is_active: int = 1


class CustomerRow(BaseModel):
    id: int
    business_id: int
    user_id: Optional[int]
    first_name: str
    last_name: str
    phone: Optional[str]
    email: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]


class CustomerNoteRow(BaseModel):
    id: int
    customer_id: int
    business_id: int
    note: str
    created_by_user_id: int
    create_date: str


class CustomerAppointmentRow(BaseModel):
    id: int
    job_code: str
    job_type: str
    scheduled_date: str
    scheduled_time: str
    status: str


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
    sort_order: int


class EmployeeRow(BaseModel):
    id: int
    business_id: int
    user_id: Optional[int] = None
    role: str = "employee"
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


BUSINESS_CONFIG_COLUMNS = """
    id, name, phone, address_line1, address_line2, city, state, zip,
    owner_name, description, site_url, timezone, slot_mode,
    slot_increment_minutes, cutoff_days, min_booking_notice_hours,
    min_change_notice_minutes, buffer_minutes, reminder_enabled,
    confirm_by_sms, confirm_by_email, completion_mode,
    allow_customer_employee_selection, notify_employees, is_active
"""

# The columns `set_business_config` will write, so a caller cannot name one
# that is not a setting — `id`, `is_active`, and `stripe_account_id` are on the
# same table and none of them belong to the owner.
BUSINESS_CONFIG_WRITABLE = frozenset(
    c.strip() for c in BUSINESS_CONFIG_COLUMNS.replace("\n", " ").split(",")
) - {"id", "is_active"}


def get_business_config(business_id: int) -> Optional[BusinessConfigRow]:
    return _one_as(BusinessConfigRow,
                   f"SELECT {BUSINESS_CONFIG_COLUMNS} FROM businesses WHERE id = ?",
                   (business_id,))


def set_business_config(business_id: int, columns: dict) -> int:
    """Write the named columns and nothing else.

    Takes the columns to write rather than every setting, so an owner changing
    one field does not rewrite the other twenty-two with whatever the window
    last read — two people in the same settings would otherwise overwrite each
    other with stale values.
    """
    unknown = set(columns) - BUSINESS_CONFIG_WRITABLE
    if unknown:
        raise ValueError(f"not business settings: {', '.join(sorted(unknown))}")
    if not columns:
        return 0
    assignments = ", ".join(f"{c} = ?" for c in columns)
    return update(
        f"UPDATE businesses SET {assignments}, update_date = datetime('now')"
        f" WHERE id = ?",
        tuple(columns.values()) + (business_id,)
    )


class PlatformBusinessRow(BaseModel):
    """A business as the platform lists it."""
    id: int
    name: str
    owner_name: Optional[str]
    phone: Optional[str]
    address_line1: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    timezone: str
    is_active: int
    create_date: str


PLATFORM_BUSINESS_COLUMNS = """
    id, name, owner_name, phone, address_line1, city, state, zip,
    timezone, is_active, create_date
"""


def get_platform_businesses(active: Optional[int] = None) -> List[PlatformBusinessRow]:
    where = "" if active is None else " WHERE is_active = ?"
    params = () if active is None else (active,)
    return _all_as(PlatformBusinessRow,
                   f"SELECT {PLATFORM_BUSINESS_COLUMNS} FROM businesses"
                   f"{where} ORDER BY id",
                   params)


def get_platform_business(business_id: int) -> Optional[PlatformBusinessRow]:
    return _one_as(PlatformBusinessRow,
                   f"SELECT {PLATFORM_BUSINESS_COLUMNS} FROM businesses"
                   " WHERE id = ?",
                   (business_id,))


def set_business_active(business_id: int, is_active: int) -> int:
    return update(
        "UPDATE businesses SET is_active = ?, update_date = datetime('now')"
        " WHERE id = ?",
        (is_active, business_id)
    )


def delete_business(business_id: int) -> int:
    """Remove a business and everything that belongs only to it.

    Innermost first, so a row is gone before the row it references. `lib`
    refuses a business with appointments behind it, so nothing here reaches a
    booking or a customer.
    """
    for statement in (
        "DELETE FROM employee_schedule_templates WHERE employee_id IN"
        " (SELECT id FROM employees WHERE business_id = ?)",
        "DELETE FROM employee_time_off WHERE employee_id IN"
        " (SELECT id FROM employees WHERE business_id = ?)",
        "DELETE FROM job_type_employees WHERE job_type_id IN"
        " (SELECT id FROM job_types WHERE business_id = ?)",
        "DELETE FROM job_type_sizes WHERE job_type_id IN"
        " (SELECT id FROM job_types WHERE business_id = ?)",
        "DELETE FROM job_type_attributes WHERE job_type_id IN"
        " (SELECT id FROM job_types WHERE business_id = ?)",
        "DELETE FROM job_type_contact_fields WHERE job_type_id IN"
        " (SELECT id FROM job_types WHERE business_id = ?)",
        "DELETE FROM employees WHERE business_id = ?",
        "DELETE FROM job_types WHERE business_id = ?",
        "DELETE FROM business_hours WHERE business_id = ?",
        "DELETE FROM business_holidays WHERE business_id = ?",
        "DELETE FROM customer_notes WHERE customer_id IN"
        " (SELECT id FROM customers WHERE business_id = ?)",
        "DELETE FROM customers WHERE business_id = ?",
        "DELETE FROM icons WHERE business_id = ?",
    ):
        update(statement, (business_id,))
    return update("DELETE FROM businesses WHERE id = ?", (business_id,))


def count_jobs_for_business(business_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM scheduled_jobs WHERE business_id = ?",
               (business_id,))
    return row[0] if row else 0


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


class SystemHolidayRow(BaseModel):
    id: int
    country_code: str
    name: str
    date: str
    year: int


def get_system_holidays(year: int, country_code: str = "US") -> List[SystemHolidayRow]:
    return _all_as(SystemHolidayRow,
                   "SELECT id, country_code, name, date, year FROM system_holidays"
                   " WHERE year = ? AND country_code = ? ORDER BY date, name",
                   (year, country_code))


class CountryHolidayRow(BaseModel):
    id: int
    country_code: str
    country_name: str
    name: str
    date: str


def get_holidays_for_year(year: int) -> List[CountryHolidayRow]:
    """Every holiday in a year, by country and then by date."""
    return _all_as(CountryHolidayRow,
                   "SELECT id, country_code, country_name, name, date"
                   " FROM system_holidays WHERE year = ?"
                   " ORDER BY country_code, date, name",
                   (year,))


def get_system_holiday(holiday_id: int) -> Optional[SystemHolidayRow]:
    return _one_as(SystemHolidayRow,
                   "SELECT id, country_code, name, date, year FROM system_holidays"
                   " WHERE id = ?",
                   (holiday_id,))


def get_observed_holiday_ids(business_id: int, year: int) -> List[int]:
    return [r[0] for r in select(
        "SELECT holiday_id FROM business_holidays WHERE business_id = ? AND year = ?",
        (business_id, year)
    )]


def clear_observed_holidays(business_id: int, year: int) -> int:
    """Drop one year's choices, so a save replaces rather than accumulates."""
    return update(
        "DELETE FROM business_holidays WHERE business_id = ? AND year = ?",
        (business_id, year)
    )


def get_holiday_years(country_code: Optional[str] = None) -> List[int]:
    """The years there are holidays for, earliest first.

    Every country by default: the platform screen offers the years it knows
    about, whichever country supplied them.
    """
    where = "" if country_code is None else " WHERE country_code = ?"
    params = () if country_code is None else (country_code,)
    return [r[0] for r in select(
        f"SELECT DISTINCT year FROM system_holidays{where} ORDER BY year", params)]


def observe_holiday(business_id: int, holiday_id: int, year: int) -> int:
    """Close the business on a system holiday, for one year."""
    return insert(
        "INSERT INTO business_holidays (business_id, holiday_id, year) VALUES (?, ?, ?)",
        (business_id, holiday_id, year)
    )


# --- Customers -----------------------------------------------------------

CUSTOMER_COLUMNS = """
    id, business_id, user_id, first_name, last_name, phone, email,
    address_line1, address_line2, city, state, zip
"""

CUSTOMER_WRITABLE = frozenset({
    "first_name", "last_name", "phone", "email", "address_line1",
    "address_line2", "city", "state", "zip"
})


def insert_customer(business_id: int, first_name: str, last_name: str,
                    phone: Optional[str] = None, email: Optional[str] = None,
                    user_id: Optional[int] = None) -> int:
    return insert(
        """
        INSERT INTO customers (business_id, user_id, first_name, last_name, phone, email)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (business_id, user_id, first_name, last_name, phone, email)
    )


def get_customer_anywhere(customer_id: int) -> Optional[CustomerRow]:
    """The customer, whichever business they booked with.

    For the paths that reach one from a booking, where the job already names
    the business. A route takes its business from the path and calls
    `get_customer`.
    """
    return _one_as(CustomerRow,
                   f"SELECT {CUSTOMER_COLUMNS} FROM customers WHERE id = ?",
                   (customer_id,))


def get_customer(business_id: int, customer_id: int) -> Optional[CustomerRow]:
    """The customer, when they booked with this business."""
    return _one_as(CustomerRow,
                   f"SELECT {CUSTOMER_COLUMNS} FROM customers"
                   " WHERE business_id = ? AND id = ?",
                   (business_id, customer_id))


def get_customers(business_id: int, term: Optional[str] = None) -> List[CustomerRow]:
    """The business's customers, narrowed by name or phone.

    The operator types into one box and expects either to match, so the term is
    tried against both rather than asking them which they meant.
    """
    if not term:
        return _all_as(CustomerRow,
                       f"SELECT {CUSTOMER_COLUMNS} FROM customers"
                       " WHERE business_id = ? ORDER BY last_name, first_name",
                       (business_id,))
    like = f"%{term.lower()}%"
    return _all_as(CustomerRow,
                   f"""
                   SELECT {CUSTOMER_COLUMNS} FROM customers
                   WHERE business_id = ?
                     AND (LOWER(first_name) LIKE ?
                          OR LOWER(last_name) LIKE ?
                          OR LOWER(first_name || ' ' || last_name) LIKE ?
                          OR IFNULL(phone, '') LIKE ?)
                   ORDER BY last_name, first_name
                   """,
                   (business_id, like, like, like, like))


def find_customer_by_user(business_id: int, user_id: int) -> Optional[CustomerRow]:
    """This business's record for a signed-in BOSS user."""
    return _one_as(CustomerRow,
                   f"SELECT {CUSTOMER_COLUMNS} FROM customers"
                   " WHERE business_id = ? AND user_id = ?"
                   " ORDER BY id LIMIT 1",
                   (business_id, user_id))


def find_customer_by_email(business_id: int, email: str) -> Optional[CustomerRow]:
    """This business's record for an address, whatever case it was typed in."""
    return _one_as(CustomerRow,
                   f"SELECT {CUSTOMER_COLUMNS} FROM customers"
                   " WHERE business_id = ? AND LOWER(email) = ?"
                   " ORDER BY id LIMIT 1",
                   (business_id, email.strip().lower()))


def _phone_expression(column: str = "phone") -> str:
    """SQL reducing a stored number to the digits that identify it.

    Used by the lookup *and* by the index that serves it. An index on an
    expression only helps a query using the identical expression, so the two
    are generated from here rather than written twice.
    """
    stripped = column
    for character in (" ", "-", "(", ")", ".", "+"):
        stripped = f"REPLACE({stripped}, '{character}', '')"
    return f"SUBSTR({stripped}, -10)"


def find_customer_by_phone_digits(business_id: int, digits: str) -> Optional[CustomerRow]:
    """This business's record for a number, however it was punctuated.

    The punctuation is stripped from the stored value in SQL, and both sides
    are compared on their last ten digits — so `(555) 234-5678` matches
    `+1 555 234 5678`. The same customer writes their number both ways, and a
    country code is not what tells two people apart.

    `digits` is expected already reduced the same way; `lib._phone_digits` is
    what does it.
    """
    return _one_as(CustomerRow,
                   f"SELECT {CUSTOMER_COLUMNS} FROM customers"
                   f" WHERE business_id = ? AND phone IS NOT NULL"
                   f"   AND {_phone_expression()} = ?"
                   f" ORDER BY id LIMIT 1",
                   (business_id, digits))


def claim_customer(customer_id: int, user_id: int) -> int:
    """Give one record to a BOSS account.

    Its own function rather than a column on `set_customer`: that one is what
    the Customer form writes through, and `user_id` is not the operator's to
    set. Only claims an unheld record, so a race cannot move one between
    accounts.
    """
    return update(
        "UPDATE customers SET user_id = ? WHERE id = ? AND user_id IS NULL",
        (user_id, customer_id)
    )


def link_customers_to_user(email: str, user_id: int) -> int:
    """Give every record under this address to a BOSS account.

    Across businesses on purpose: an address is one person everywhere in BOSS,
    and each business's record of them is theirs to maintain from here on. It
    tells no business about another — only that this customer now has an
    account.
    """
    return update(
        "UPDATE customers SET user_id = ?"
        " WHERE user_id IS NULL AND LOWER(email) = ?",
        (user_id, email.strip().lower())
    )


def set_customer(customer_id: int, columns: dict) -> int:
    unknown = set(columns) - CUSTOMER_WRITABLE
    if unknown:
        raise ValueError(f"not customer details: {', '.join(sorted(unknown))}")
    if not columns:
        return 0
    assignments = ", ".join(f"{c} = ?" for c in columns)
    return update(f"UPDATE customers SET {assignments} WHERE id = ?",
                  tuple(columns.values()) + (customer_id,))


def set_job_customer(job_id: int, customer_id: int) -> int:
    return update(
        "UPDATE scheduled_jobs SET customer_id = ?, update_date = datetime('now')"
        " WHERE id = ?",
        (customer_id, job_id)
    )


def get_customer_appointments(customer_id: int) -> List[CustomerAppointmentRow]:
    return _all_as(CustomerAppointmentRow,
                   """
                   SELECT j.id, j.job_code, t.name AS job_type,
                          j.scheduled_date, j.scheduled_time, j.status
                   FROM scheduled_jobs j
                   JOIN job_types t ON t.id = j.job_type_id
                   WHERE j.customer_id = ?
                   ORDER BY j.scheduled_date DESC, j.scheduled_time DESC
                   """,
                   (customer_id,))


def insert_customer_note(customer_id: int, business_id: int, note: str,
                         created_by_user_id: int) -> int:
    return insert(
        """
        INSERT INTO customer_notes (customer_id, business_id, note, created_by_user_id)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, business_id, note, created_by_user_id)
    )


def get_customer_notes(customer_id: int) -> List[CustomerNoteRow]:
    return _all_as(CustomerNoteRow,
                   "SELECT id, customer_id, business_id, note,"
                   " created_by_user_id, create_date FROM customer_notes"
                   " WHERE customer_id = ? ORDER BY create_date DESC, id DESC",
                   (customer_id,))


def get_customer_note(note_id: int) -> Optional[CustomerNoteRow]:
    return _one_as(CustomerNoteRow,
                   "SELECT id, customer_id, business_id, note,"
                   " created_by_user_id, create_date FROM customer_notes"
                   " WHERE id = ?",
                   (note_id,))


def set_customer_note(note_id: int, note: str) -> int:
    return update(
        "UPDATE customer_notes SET note = ?, update_date = datetime('now')"
        " WHERE id = ?",
        (note, note_id)
    )


def delete_customer_note(note_id: int) -> int:
    return update("DELETE FROM customer_notes WHERE id = ?", (note_id,))


# --- Job types -----------------------------------------------------------

def get_job_type(business_id: int, job_type_id: int) -> Optional[JobTypeRow]:
    """The job type, when this business offers it."""
    return _one_as(JobTypeRow,
                   "SELECT id, business_id, name, min_employees, is_active"
                   " FROM job_types WHERE business_id = ? AND id = ?",
                   (business_id, job_type_id))


class JobTypeDetailRow(BaseModel):
    """Every column the JobType window shows.

    `JobTypeRow` is the subset the scheduling rules read. This is the record.
    """
    id: int
    business_id: int
    name: str
    icon_id: Optional[int]
    min_employees: int
    payment_required: int
    deposit_required: int
    deposit_type: Optional[str]
    deposit_amount: Optional[float]
    deposit_nonrefundable: int
    stripe_product_id: Optional[str]
    stripe_price_id: Optional[str]
    is_active: int


def get_job_type_detail(job_type_id: int) -> Optional[JobTypeDetailRow]:
    return _one_as(JobTypeDetailRow,
                   """
                   SELECT id, business_id, name, icon_id, min_employees,
                          payment_required, deposit_required, deposit_type,
                          deposit_amount, deposit_nonrefundable,
                          stripe_product_id, stripe_price_id, is_active
                   FROM job_types WHERE id = ?
                   """,
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
                   "SELECT id, job_type_id, name, duration_minutes, cost, sort_order"
                   " FROM job_type_sizes WHERE id = ?",
                   (size_id,))


def next_size_sort_order(job_type_id: int) -> int:
    row = _one("SELECT IFNULL(MAX(sort_order), -1) + 1 FROM job_type_sizes"
               " WHERE job_type_id = ?", (job_type_id,))
    return row[0] if row else 0


def insert_job_type_size(job_type_id: int, name: str, duration_minutes: int,
                         cost: float, sort_order: int = 0) -> int:
    return insert(
        """
        INSERT INTO job_type_sizes
            (job_type_id, name, duration_minutes, cost, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_type_id, name, duration_minutes, cost, sort_order)
    )


# --- Employees -----------------------------------------------------------

def get_employee_by_user(user_id: int) -> Optional[EmployeeRow]:
    """The employee record a signed-in BOSS user works under."""
    return _one_as(EmployeeRow,
                   "SELECT id, business_id, user_id, role, first_name, last_name,"
                   " include_in_schedule, can_manage_own_schedule"
                   " FROM employees WHERE user_id = ? ORDER BY id LIMIT 1",
                   (user_id,))


def set_employee_user(employee_id: int, user_id: Optional[int]) -> int:
    """Link a BOSS account to this record, or `None` to take it off."""
    return update("UPDATE employees SET user_id = ? WHERE id = ?",
                  (user_id, employee_id))


def get_jobs_for_employee(employee_id: int, date: str) -> List[ScheduleJobRow]:
    """One employee's work on one day."""
    return _all_as(ScheduleJobRow,
                   f"""
                   SELECT j.id, j.job_code, jt.name AS job_type_name,
                          j.scheduled_date, j.scheduled_time, j.duration_minutes,
                          j.status, j.payment_status,
                          {CONTACT_VALUE('First Name')} AS first_name,
                          {CONTACT_VALUE('Last Name')} AS last_name
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   JOIN job_employees je ON je.job_id = j.id
                   WHERE je.employee_id = ? AND j.scheduled_date = ?
                     AND j.status != 'cancelled'
                   ORDER BY j.scheduled_time, j.id
                   """,
                   (employee_id, date))


def insert_employee(business_id: int, first_name: str, last_name: str,
                    include_in_schedule: int,
                    can_manage_own_schedule: int = 0) -> int:
    return insert(
        """
        INSERT INTO employees (business_id, first_name, last_name,
                               include_in_schedule, can_manage_own_schedule)
        VALUES (?, ?, ?, ?, ?)
        """,
        (business_id, first_name, last_name, include_in_schedule,
         can_manage_own_schedule)
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


def insert_contact_field_type(name: str, field_type: str, otp_capable: int,
                              sort_order: int) -> int:
    return insert(
        "INSERT INTO contact_field_types (name, field_type, otp_capable, sort_order)"
        " VALUES (?, ?, ?, ?)",
        (name, field_type, otp_capable, sort_order)
    )


def set_contact_field_type(field_id: int, name: str, field_type: str,
                           otp_capable: int) -> int:
    return update(
        "UPDATE contact_field_types SET name = ?, field_type = ?, otp_capable = ?"
        " WHERE id = ?",
        (name, field_type, otp_capable, field_id)
    )


def set_contact_field_type_sort_order(field_id: int, sort_order: int) -> int:
    return update("UPDATE contact_field_types SET sort_order = ? WHERE id = ?",
                  (sort_order, field_id))


def delete_contact_field_type(field_id: int) -> int:
    return update("DELETE FROM contact_field_types WHERE id = ?", (field_id,))


def next_contact_field_type_sort_order() -> int:
    row = _one("SELECT IFNULL(MAX(sort_order), -1) + 1 FROM contact_field_types", ())
    return row[0] if row else 0


def count_job_types_asking_for(field_id: int) -> int:
    """How many job types ask a customer for this kind of detail."""
    row = _one("SELECT COUNT(*) FROM job_type_contact_fields"
               " WHERE contact_field_type_id = ?", (field_id,))
    return row[0] if row else 0


def insert_business_template(name: str, description: str, config_json: str) -> int:
    return insert(
        "INSERT INTO business_templates (name, description, config_json)"
        " VALUES (?, ?, ?)",
        (name, description, config_json)
    )


def get_business_template(template_id: int) -> Optional[BusinessTemplateRow]:
    return _one_as(BusinessTemplateRow,
                   "SELECT id, name, description, config_json"
                   " FROM business_templates WHERE id = ?",
                   (template_id,))


def set_business_template(template_id: int, name: str, description: str) -> int:
    return update(
        "UPDATE business_templates SET name = ?, description = ? WHERE id = ?",
        (name, description, template_id)
    )


def delete_business_template(template_id: int) -> int:
    return update("DELETE FROM business_templates WHERE id = ?", (template_id,))


class IconRow(BaseModel):
    id: int
    business_id: Optional[int]
    filename: str
    is_system: int


def insert_icon(business_id: Optional[int], filename: str,
                is_system: int) -> int:
    return insert(
        "INSERT INTO icons (business_id, filename, is_system) VALUES (?, ?, ?)",
        (business_id, filename, is_system)
    )


def get_icon(icon_id: int) -> Optional[IconRow]:
    return _one_as(IconRow,
                   "SELECT id, business_id, filename, is_system FROM icons"
                   " WHERE id = ?",
                   (icon_id,))


def get_system_icons() -> List[IconRow]:
    """The ones the platform ships, shared by every business."""
    return _all_as(IconRow,
                   "SELECT id, business_id, filename, is_system FROM icons"
                   " WHERE is_system = 1 ORDER BY filename",
                   ())


def get_business_icons(business_id: int) -> List[IconRow]:
    """The ones this business uploaded."""
    return _all_as(IconRow,
                   "SELECT id, business_id, filename, is_system FROM icons"
                   " WHERE is_system = 0 AND business_id = ? ORDER BY id",
                   (business_id,))


def delete_icon(icon_id: int) -> int:
    return update("DELETE FROM icons WHERE id = ?", (icon_id,))


class VendorConfigRow(BaseModel):
    id: int
    vendor_type: str
    vendor_name: str
    config_json: str


def get_vendor_configs() -> List[VendorConfigRow]:
    return _all_as(VendorConfigRow,
                   "SELECT id, vendor_type, vendor_name, config_json"
                   " FROM vendor_configs WHERE is_active = 1 ORDER BY vendor_type",
                   ())


def clear_vendor_config(vendor_type: str) -> int:
    """One choice per kind, so setting one replaces what was there."""
    return update("DELETE FROM vendor_configs WHERE vendor_type = ?",
                  (vendor_type,))


def insert_vendor_config(vendor_type: str, vendor_name: str,
                         config_json: str) -> int:
    return insert(
        "INSERT INTO vendor_configs (vendor_type, vendor_name, config_json)"
        " VALUES (?, ?, ?)",
        (vendor_type, vendor_name, config_json)
    )


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
    business_id: int
    business_name: str
    business_phone: Optional[str]
    min_change_notice_minutes: int
    job_type_id: int
    job_type_name: str
    size_id: Optional[int]
    size_name: Optional[str]
    cost: Optional[float]
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int
    status: str
    locked_date: Optional[str]


def get_appointment(job_id: int) -> Optional[AppointmentRow]:
    """A booking with the two names the customer's screen shows."""
    return _one_as(AppointmentRow,
                   """
                   SELECT j.id, j.job_code, j.business_id, b.name AS business_name,
                          b.phone AS business_phone, b.min_change_notice_minutes,
                          j.job_type_id, jt.name AS job_type_name,
                          j.job_type_size_id AS size_id, s.name AS size_name,
                          s.cost, j.scheduled_date, j.scheduled_time,
                          j.duration_minutes, j.status, j.locked_date
                   FROM scheduled_jobs j
                   JOIN businesses b ON b.id = j.business_id
                   JOIN job_types jt ON jt.id = j.job_type_id
                   LEFT JOIN job_type_sizes s ON s.id = j.job_type_size_id
                   WHERE j.id = ?
                   """,
                   (job_id,))


class JobDetailRow(BaseModel):
    """A booking as the operator sees it, which is the whole of it."""
    id: int
    job_code: str
    business_id: int
    customer_id: Optional[int]
    job_type_id: int
    job_type_name: str
    size_id: Optional[int]
    size_name: Optional[str]
    size_duration_minutes: Optional[int]
    cost: Optional[float]
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int
    status: str
    payment_status: str
    locked_date: Optional[str]
    is_recurring: int


def get_job_detail(business_id: int, job_id: int) -> Optional[JobDetailRow]:
    """The booking, when this business took it."""
    return _one_as(JobDetailRow,
                   """
                   SELECT j.id, j.job_code, j.business_id, j.customer_id,
                          j.job_type_id, jt.name AS job_type_name,
                          j.job_type_size_id AS size_id, s.name AS size_name,
                          s.duration_minutes AS size_duration_minutes, s.cost,
                          j.scheduled_date, j.scheduled_time, j.duration_minutes,
                          j.status, j.payment_status, j.locked_date, j.is_recurring
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   LEFT JOIN job_type_sizes s ON s.id = j.job_type_size_id
                   WHERE j.business_id = ? AND j.id = ?
                   """,
                   (business_id, job_id))


def count_access_attempts(job_id: int) -> int:
    """Every wrong code ever tried on this booking.

    The lock is a rate — six inside a minute — but the operator taking the call
    is asked "how many times has this happened", which is the total.
    """
    row = _one("SELECT COUNT(*) FROM appointment_access_attempts WHERE job_id = ?",
               (job_id,))
    return row[0] if row else 0


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


class UnassignedJobRow(BaseModel):
    """A live appointment with nobody on it, as the screen lists it."""
    id: int
    job_code: str
    job_type_id: int
    job_type_size_id: Optional[int]
    job_type_name: str
    scheduled_date: str
    scheduled_time: str
    is_recurring: int
    first_name: Optional[str]
    last_name: Optional[str]


def get_unassigned_jobs(business_id: int) -> List[UnassignedJobRow]:
    """Live appointments with nobody on them."""
    return _all_as(UnassignedJobRow,
                   f"""
                   SELECT j.id, j.job_code, j.job_type_id, j.job_type_size_id,
                          jt.name AS job_type_name,
                          j.scheduled_date, j.scheduled_time, j.is_recurring,
                          {CONTACT_VALUE('First Name')} AS first_name,
                          {CONTACT_VALUE('Last Name')} AS last_name
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   LEFT JOIN job_employees je ON je.job_id = j.id
                   WHERE j.business_id = ? AND j.status IN ('pending', 'confirmed')
                     AND je.job_id IS NULL
                   ORDER BY j.scheduled_date, j.scheduled_time
                   """,
                   (business_id,))


def count_jobs_between(business_id: int, from_date: str, to_date: str) -> int:
    """Live appointments in a date range."""
    row = _one("SELECT COUNT(*) FROM scheduled_jobs WHERE business_id = ?"
               " AND scheduled_date >= ? AND scheduled_date <= ?"
               " AND status != 'cancelled'",
               (business_id, from_date, to_date))
    return row[0] if row else 0


def get_revenue_between(business_id: int, from_date: str, to_date: str) -> float:
    """What arrived against appointments in a date range."""
    row = _one("""
               SELECT COALESCE(SUM(t.amount), 0)
               FROM job_transactions t
               JOIN scheduled_jobs j ON j.id = t.job_id
               WHERE j.business_id = ?
                 AND j.scheduled_date >= ? AND j.scheduled_date <= ?
               """,
               (business_id, from_date, to_date))
    return float(row[0]) if row else 0.0


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


class JobSearchRow(BaseModel):
    id: int
    job_code: str
    job_type_name: str
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int
    status: str
    payment_status: str
    # What the customer typed when they booked. A job may carry no name at all
    # — a job type need not ask for one — so both halves are optional.
    first_name: Optional[str]
    last_name: Optional[str]


class JobEmployeeRow(BaseModel):
    job_id: int
    employee_id: int
    first_name: str
    last_name: str


def get_employees_for_jobs(job_ids: List[int]) -> List[JobEmployeeRow]:
    """Who is doing each of these jobs, in one query rather than one per row."""
    if not job_ids:
        return []
    marks = ", ".join("?" for _ in job_ids)
    return _all_as(JobEmployeeRow,
                   f"""
                   SELECT je.job_id, je.employee_id, e.first_name, e.last_name
                   FROM job_employees je
                   JOIN employees e ON e.id = je.employee_id
                   WHERE je.job_id IN ({marks})
                   ORDER BY e.first_name, e.last_name
                   """,
                   tuple(job_ids))


def CONTACT_VALUE(field_name: str) -> str:
    """A scalar subquery reading one of the job's contact details.

    Written as a subquery rather than a join so a job missing the detail — or
    carrying several — is still exactly one row.
    """
    return (f"(SELECT ci.value FROM job_contact_info ci"
            f" JOIN contact_field_types cf ON cf.id = ci.contact_field_type_id"
            f" WHERE ci.job_id = j.id AND cf.name = '{field_name}' LIMIT 1)")


def search_jobs(business_id: int, from_date: Optional[str] = None,
                to_date: Optional[str] = None, status: Optional[str] = None,
                job_type_id: Optional[int] = None,
                job_code: Optional[str] = None,
                name: Optional[str] = None,
                phone: Optional[str] = None,
                employee_id: Optional[int] = None,
                limit: int = 200) -> List[JobSearchRow]:
    """Appointments matching whatever the operator narrowed by.

    Every filter is optional and every one is scoped to the business, which is
    not a filter — it is the boundary, and it is applied whether or not the
    caller asked for it.
    """
    where = ["j.business_id = ?"]
    params: List[Any] = [business_id]
    for clause, value in (("j.scheduled_date >= ?", from_date),
                          ("j.scheduled_date <= ?", to_date),
                          ("j.status = ?", status),
                          ("j.job_type_id = ?", job_type_id),
                          ("j.job_code = ?", job_code)):
        if value is not None:
            where.append(clause)
            params.append(value)

    # Name and phone are what the customer typed when they booked, which lives
    # on the job rather than on a customer record — a booking never requires
    # one. Matched with EXISTS so a job with several contact details is still
    # one row.
    if name:
        where.append("""
            EXISTS (SELECT 1 FROM job_contact_info ci
                    JOIN contact_field_types cf ON cf.id = ci.contact_field_type_id
                    WHERE ci.job_id = j.id
                      AND cf.name IN ('First Name', 'Last Name')
                      AND LOWER(ci.value) LIKE ?)
            OR LOWER(IFNULL(""" + CONTACT_VALUE("First Name") + """, '')
                     || ' '
                     || IFNULL(""" + CONTACT_VALUE("Last Name") + """, '')) LIKE ?
        """)
        like = f"%{name.lower()}%"
        params.extend([like, like])
    if phone:
        where.append("""
            EXISTS (SELECT 1 FROM job_contact_info ci
                    JOIN contact_field_types cf ON cf.id = ci.contact_field_type_id
                    WHERE ci.job_id = j.id AND cf.name = 'Phone'
                      AND ci.value LIKE ?)
        """)
        params.append(f"%{phone}%")
    if employee_id is not None:
        where.append("EXISTS (SELECT 1 FROM job_employees je"
                     " WHERE je.job_id = j.id AND je.employee_id = ?)")
        params.append(employee_id)

    params.append(limit)
    return _all_as(JobSearchRow,
                   f"""
                   SELECT j.id, j.job_code, jt.name AS job_type_name,
                          j.scheduled_date, j.scheduled_time, j.duration_minutes,
                          j.status, j.payment_status,
                          {CONTACT_VALUE('First Name')} AS first_name,
                          {CONTACT_VALUE('Last Name')} AS last_name
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   WHERE {' AND '.join(f'({w})' for w in where)}
                   ORDER BY j.scheduled_date, j.scheduled_time
                   LIMIT ?
                   """,
                   tuple(params))


class ReportRow(BaseModel):
    """One appointment in a period, with what was taken against it."""
    id: int
    job_code: str
    job_type_name: str
    scheduled_date: str
    status: str
    payment_status: str
    cost: Optional[float]
    paid: float


def get_booked_years(business_id: int) -> List[int]:
    """Every year this business has an appointment in, earliest first."""
    return [int(r[0]) for r in select(
        "SELECT DISTINCT SUBSTR(scheduled_date, 1, 4) FROM scheduled_jobs"
        " WHERE business_id = ? ORDER BY 1",
        (business_id,)
    )]


class ScheduleJobRow(BaseModel):
    """One appointment on the operator's calendar."""
    id: int
    job_code: str
    job_type_name: str
    scheduled_date: str
    scheduled_time: str
    duration_minutes: int
    status: str
    payment_status: str
    first_name: Optional[str]
    last_name: Optional[str]


def get_scheduled_jobs(business_id: int, from_date: str,
                       to_date: str) -> List[ScheduleJobRow]:
    """Live appointments in a date range, in the order of the day.

    Cancelled ones are left out: the calendar shows what is happening, and a
    called-off appointment holds no time.
    """
    return _all_as(ScheduleJobRow,
                   f"""
                   SELECT j.id, j.job_code, jt.name AS job_type_name,
                          j.scheduled_date, j.scheduled_time, j.duration_minutes,
                          j.status, j.payment_status,
                          {CONTACT_VALUE('First Name')} AS first_name,
                          {CONTACT_VALUE('Last Name')} AS last_name
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   WHERE j.business_id = ?
                     AND j.scheduled_date >= ? AND j.scheduled_date <= ?
                     AND j.status != 'cancelled'
                   ORDER BY j.scheduled_date, j.scheduled_time, j.id
                   """,
                   (business_id, from_date, to_date))


def get_jobs_in_period(business_id: int, from_date: str,
                       to_date: str) -> List[ReportRow]:
    """Appointments in a date range, with the money against each.

    Summed in SQL rather than per row: a quarter is a few hundred appointments
    and a round trip each would be a few hundred round trips.
    """
    return _all_as(ReportRow,
                   """
                   SELECT j.id, j.job_code, jt.name AS job_type_name,
                          j.scheduled_date, j.status, j.payment_status, s.cost,
                          COALESCE((SELECT SUM(t.amount) FROM job_transactions t
                                    WHERE t.job_id = j.id), 0) AS paid
                   FROM scheduled_jobs j
                   JOIN job_types jt ON jt.id = j.job_type_id
                   LEFT JOIN job_type_sizes s ON s.id = j.job_type_size_id
                   WHERE j.business_id = ?
                     AND j.scheduled_date >= ? AND j.scheduled_date <= ?
                   ORDER BY j.scheduled_date, j.id
                   """,
                   (business_id, from_date, to_date))


def get_employee_for_business(business_id: int,
                              user_id: int) -> Optional[EmployeeRow]:
    """Whether this BOSS account works for *this* business, and as what."""
    return _one_as(EmployeeRow,
                   "SELECT id, business_id, user_id, role, first_name,"
                   " last_name, include_in_schedule, can_manage_own_schedule"
                   " FROM employees WHERE business_id = ? AND user_id = ?",
                   (business_id, user_id))


def insert_employee_member(business_id: int, user_id: int, role: str,
                           first_name: str, last_name: str) -> int:
    """The row that makes somebody part of a business.

    `include_in_schedule` starts at 0: an operator opening a business is not
    given work until they say so, and a one-person business turns it on.
    """
    return insert(
        "INSERT INTO employees (business_id, user_id, role, first_name,"
        " last_name, include_in_schedule) VALUES (?, ?, ?, ?, ?, 0)",
        (business_id, user_id, role, first_name, last_name)
    )


def get_employee_anywhere(employee_id: int) -> Optional[EmployeeRow]:
    """The employee, whichever business they belong to.

    For the paths that reach an employee before a business is known — linking
    a BOSS account, and asking whether somebody is free. A route takes its
    business from the path and calls `get_employee`.
    """
    return _one_as(EmployeeRow,
                   "SELECT id, business_id, user_id, role, first_name, last_name,"
                   " include_in_schedule, can_manage_own_schedule"
                   " FROM employees WHERE id = ?",
                   (employee_id,))


def get_employee(business_id: int, employee_id: int) -> Optional[EmployeeRow]:
    """The employee, when they belong to this business.

    The scope is a parameter rather than a check beside the call, so reaching
    an employee without naming a business is a `TypeError`.
    """
    return _one_as(EmployeeRow,
                   "SELECT id, business_id, user_id, role, first_name, last_name,"
                   " include_in_schedule, can_manage_own_schedule"
                   " FROM employees WHERE business_id = ? AND id = ?",
                   (business_id, employee_id))


def set_business_slot_mode(business_id: int, slot_mode: str) -> int:
    return update(
        "UPDATE businesses SET slot_mode = ?, update_date = datetime('now')"
        " WHERE id = ?", (slot_mode, business_id)
    )


def set_business_employee_selection(business_id: int, allow: int,
                                    notify: int) -> int:
    return update(
        "UPDATE businesses SET allow_customer_employee_selection = ?,"
        " notify_employees = ?, update_date = datetime('now') WHERE id = ?",
        (allow, notify, business_id)
    )


def get_business_template(template_id: int) -> Optional[BusinessTemplateRow]:
    return _one_as(BusinessTemplateRow,
                   "SELECT id, name, description, config_json"
                   " FROM business_templates WHERE id = ?",
                   (template_id,))


def get_business_flags(business_id: int) -> Optional[tuple]:
    row = _one("SELECT allow_customer_employee_selection, notify_employees"
               " FROM businesses WHERE id = ?", (business_id,))
    return (row[0], row[1]) if row else None


class JobTypeContactFieldRow(BaseModel):
    id: int
    job_type_id: int
    contact_field_type_id: int
    name: str
    field_type: str
    otp_capable: int
    is_required: int
    require_otp: int
    sort_order: int


CONTACT_FIELD_COLUMNS = """
    f.id, f.job_type_id, f.contact_field_type_id, t.name, t.field_type,
    t.otp_capable, f.is_required, f.require_otp, f.sort_order
"""

CONTACT_FIELD_FROM = """
    FROM job_type_contact_fields f
    JOIN contact_field_types t ON t.id = f.contact_field_type_id
"""


def get_job_type_contact_fields(job_type_id: int) -> List[JobTypeContactFieldRow]:
    return _all_as(JobTypeContactFieldRow,
                   f"SELECT {CONTACT_FIELD_COLUMNS} {CONTACT_FIELD_FROM}"
                   " WHERE f.job_type_id = ? ORDER BY f.sort_order, f.id",
                   (job_type_id,))


def get_job_type_contact_field(field_id: int) -> Optional[JobTypeContactFieldRow]:
    return _one_as(JobTypeContactFieldRow,
                   f"SELECT {CONTACT_FIELD_COLUMNS} {CONTACT_FIELD_FROM}"
                   " WHERE f.id = ?",
                   (field_id,))


def get_contact_field_type(contact_field_type_id: int) -> Optional[ContactFieldTypeRow]:
    return _one_as(ContactFieldTypeRow,
                   "SELECT id, name, field_type, otp_capable, sort_order"
                   " FROM contact_field_types WHERE id = ?",
                   (contact_field_type_id,))


def next_contact_field_sort_order(job_type_id: int) -> int:
    row = _one("SELECT IFNULL(MAX(sort_order), -1) + 1 FROM job_type_contact_fields"
               " WHERE job_type_id = ?", (job_type_id,))
    return row[0] if row else 0


def set_job_type_contact_field(field_id: int, contact_field_type_id: int,
                               is_required: int, require_otp: int) -> int:
    return update(
        "UPDATE job_type_contact_fields SET contact_field_type_id = ?,"
        " is_required = ?, require_otp = ? WHERE id = ?",
        (contact_field_type_id, is_required, require_otp, field_id)
    )


def set_contact_field_sort_order(field_id: int, sort_order: int) -> int:
    return update("UPDATE job_type_contact_fields SET sort_order = ? WHERE id = ?",
                  (sort_order, field_id))


def delete_job_type_contact_field(field_id: int) -> int:
    return update("DELETE FROM job_type_contact_fields WHERE id = ?", (field_id,))


def insert_job_type_contact_field(job_type_id: int, contact_field_type_id: int,
                                  is_required: int = 1, require_otp: int = 0,
                                  sort_order: int = 0) -> int:
    return insert(
        """
        INSERT INTO job_type_contact_fields
            (job_type_id, contact_field_type_id, is_required, require_otp, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_type_id, contact_field_type_id, is_required, require_otp, sort_order)
    )


def get_contact_field_type_for_job_type_field(job_type_contact_field_id: int):
    """The kind of contact detail a job type's field asks for."""
    return _one(
        "SELECT contact_field_type_id FROM job_type_contact_fields WHERE id = ?",
        (job_type_contact_field_id,)
    )


class JobTypeAttributeRow(BaseModel):
    id: int
    job_type_id: int
    name: str
    attribute_type: str
    options_json: Optional[str]
    is_required: int
    sort_order: int


ATTRIBUTE_COLUMNS = ("id, job_type_id, name, attribute_type, options_json,"
                     " is_required, sort_order")


def insert_job_type_attribute(job_type_id: int, name: str, attribute_type: str,
                              options_json: Optional[str], is_required: int,
                              sort_order: int) -> int:
    return insert(
        """
        INSERT INTO job_type_attributes
            (job_type_id, name, attribute_type, options_json, is_required, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_type_id, name, attribute_type, options_json, is_required, sort_order)
    )


def get_job_type_attributes(job_type_id: int) -> List[JobTypeAttributeRow]:
    return _all_as(JobTypeAttributeRow,
                   f"SELECT {ATTRIBUTE_COLUMNS} FROM job_type_attributes"
                   " WHERE job_type_id = ? ORDER BY sort_order, id",
                   (job_type_id,))


def get_job_type_attribute(attribute_id: int) -> Optional[JobTypeAttributeRow]:
    return _one_as(JobTypeAttributeRow,
                   f"SELECT {ATTRIBUTE_COLUMNS} FROM job_type_attributes"
                   " WHERE id = ?",
                   (attribute_id,))


def next_attribute_sort_order(job_type_id: int) -> int:
    row = _one("SELECT IFNULL(MAX(sort_order), -1) + 1 FROM job_type_attributes"
               " WHERE job_type_id = ?", (job_type_id,))
    return row[0] if row else 0


def set_job_type_attribute(attribute_id: int, name: str, attribute_type: str,
                           options_json: Optional[str], is_required: int) -> int:
    return update(
        "UPDATE job_type_attributes SET name = ?, attribute_type = ?,"
        " options_json = ?, is_required = ? WHERE id = ?",
        (name, attribute_type, options_json, is_required, attribute_id)
    )


def delete_job_type_attribute(attribute_id: int) -> int:
    return update("DELETE FROM job_type_attributes WHERE id = ?", (attribute_id,))


class JobAttributeRow(BaseModel):
    name: str
    value: str


def get_job_attributes(job_id: int) -> List[JobAttributeRow]:
    """What the customer answered, named as the question was asked."""
    return _all_as(JobAttributeRow,
                   """
                   SELECT a.name, ja.value
                   FROM job_attributes ja
                   JOIN job_type_attributes a ON a.id = ja.job_type_attribute_id
                   WHERE ja.job_id = ?
                   ORDER BY a.sort_order, a.id
                   """,
                   (job_id,))


def insert_job_attribute(job_id: int, job_type_attribute_id: int, value: str) -> int:
    return insert(
        "INSERT INTO job_attributes (job_id, job_type_attribute_id, value)"
        " VALUES (?, ?, ?)",
        (job_id, job_type_attribute_id, value)
    )


def get_employees_on_job(job_id: int) -> List[EmployeeRow]:
    """Who is assigned to an appointment."""
    return _all_as(EmployeeRow,
                   """
                   SELECT e.id, e.business_id, e.first_name, e.last_name,
                          e.include_in_schedule, e.can_manage_own_schedule
                   FROM employees e
                   JOIN job_employees je ON je.employee_id = e.id
                   WHERE je.job_id = ? ORDER BY e.id
                   """,
                   (job_id,))


def get_job_types(business_id: int, term: Optional[str] = None,
                  active_only: bool = False) -> List[JobTypeRow]:
    where = ["business_id = ?"]
    params: List[Any] = [business_id]
    if term:
        where.append("LOWER(name) LIKE ?")
        params.append(f"%{term.lower()}%")
    if active_only:
        where.append("is_active = 1")
    return _all_as(JobTypeRow,
                   f"SELECT id, business_id, name, min_employees, is_active"
                   f" FROM job_types WHERE {' AND '.join(where)} ORDER BY id",
                   tuple(params))


def update_job_type(job_type_id: int, name: str, min_employees: int,
                    is_active: int) -> int:
    return update(
        "UPDATE job_types SET name = ?, min_employees = ?, is_active = ?"
        " WHERE id = ?",
        (name, min_employees, is_active, job_type_id)
    )


def count_jobs_for_job_type(job_type_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM scheduled_jobs WHERE job_type_id = ?",
               (job_type_id,))
    return row[0] if row else 0


def delete_job_type(job_type_id: int) -> int:
    update("DELETE FROM job_type_employees WHERE job_type_id = ?", (job_type_id,))
    update("DELETE FROM job_type_sizes WHERE job_type_id = ?", (job_type_id,))
    update("DELETE FROM job_type_attributes WHERE job_type_id = ?", (job_type_id,))
    update("DELETE FROM job_type_contact_fields WHERE job_type_id = ?", (job_type_id,))
    return update("DELETE FROM job_types WHERE id = ?", (job_type_id,))


def get_job_type_sizes(job_type_id: int) -> List[JobTypeSizeRow]:
    return _all_as(JobTypeSizeRow,
                   "SELECT id, job_type_id, name, duration_minutes, cost, sort_order"
                   " FROM job_type_sizes WHERE job_type_id = ?"
                   " ORDER BY sort_order, id",
                   (job_type_id,))


def update_job_type_size(size_id: int, name: str, duration_minutes: int,
                         cost: float) -> int:
    return update(
        "UPDATE job_type_sizes SET name = ?, duration_minutes = ?, cost = ?"
        " WHERE id = ?",
        (name, duration_minutes, cost, size_id)
    )


def count_jobs_for_size(size_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM scheduled_jobs WHERE job_type_size_id = ?",
               (size_id,))
    return row[0] if row else 0


def delete_job_type_size(size_id: int) -> int:
    return update("DELETE FROM job_type_sizes WHERE id = ?", (size_id,))


def get_employees(business_id: int) -> List[EmployeeRow]:
    return _all_as(EmployeeRow,
                   "SELECT id, business_id, user_id, role, first_name, last_name,"
                   " include_in_schedule, can_manage_own_schedule"
                   " FROM employees WHERE business_id = ? ORDER BY id",
                   (business_id,))


def update_employee(employee_id: int, first_name: str, last_name: str,
                    include_in_schedule: int, can_manage_own_schedule: int) -> int:
    return update(
        "UPDATE employees SET first_name = ?, last_name = ?,"
        " include_in_schedule = ?, can_manage_own_schedule = ? WHERE id = ?",
        (first_name, last_name, include_in_schedule, can_manage_own_schedule,
         employee_id)
    )


def count_jobs_for_employee(employee_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM job_employees WHERE employee_id = ?",
               (employee_id,))
    return row[0] if row else 0


def delete_employee(employee_id: int) -> int:
    update("DELETE FROM job_type_employees WHERE employee_id = ?", (employee_id,))
    update("DELETE FROM employee_schedule_templates WHERE employee_id = ?",
           (employee_id,))
    update("DELETE FROM employee_time_off WHERE employee_id = ?", (employee_id,))
    return update("DELETE FROM employees WHERE id = ?", (employee_id,))


def get_job_types_for_employee(employee_id: int) -> List[JobTypeRow]:
    return _all_as(JobTypeRow,
                   """
                   SELECT jt.id, jt.business_id, jt.name, jt.min_employees, jt.is_active
                   FROM job_types jt
                   JOIN job_type_employees jte ON jte.job_type_id = jt.id
                   WHERE jte.employee_id = ? ORDER BY jt.id
                   """,
                   (employee_id,))


def clear_job_types_for_employee(employee_id: int) -> int:
    return update("DELETE FROM job_type_employees WHERE employee_id = ?",
                  (employee_id,))


def get_schedule_day(schedule_id: int) -> Optional[EmployeeScheduleRow]:
    return _one_as(EmployeeScheduleRow,
                   "SELECT id, employee_id, day_of_week, start_time, end_time"
                   " FROM employee_schedule_templates WHERE id = ?",
                   (schedule_id,))


def update_schedule_day(schedule_id: int, day_of_week: int, start_time: str,
                        end_time: str) -> int:
    return update(
        "UPDATE employee_schedule_templates SET day_of_week = ?, start_time = ?,"
        " end_time = ? WHERE id = ?",
        (day_of_week, start_time, end_time, schedule_id)
    )


def delete_schedule_day(schedule_id: int) -> int:
    return update("DELETE FROM employee_schedule_templates WHERE id = ?",
                  (schedule_id,))


def get_all_time_off(employee_id: int) -> List[EmployeeTimeOffRow]:
    return _all_as(EmployeeTimeOffRow,
                   "SELECT id, employee_id, date, start_time, end_time"
                   " FROM employee_time_off WHERE employee_id = ?"
                   " ORDER BY date, start_time",
                   (employee_id,))


def get_time_off_window(window_id: int) -> Optional[EmployeeTimeOffRow]:
    return _one_as(EmployeeTimeOffRow,
                   "SELECT id, employee_id, date, start_time, end_time"
                   " FROM employee_time_off WHERE id = ?",
                   (window_id,))


def update_time_off(window_id: int, date: str, start_time: str,
                    end_time: str) -> int:
    return update(
        "UPDATE employee_time_off SET date = ?, start_time = ?, end_time = ?"
        " WHERE id = ?",
        (date, start_time, end_time, window_id)
    )


def delete_time_off(window_id: int) -> int:
    return update("DELETE FROM employee_time_off WHERE id = ?", (window_id,))


def count_job_type_sizes(job_type_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM job_type_sizes WHERE job_type_id = ?",
               (job_type_id,))
    return row[0] if row else 0


def count_job_type_contact_fields(job_type_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM job_type_contact_fields WHERE job_type_id = ?",
               (job_type_id,))
    return row[0] if row else 0


def count_open_days(business_id: int) -> int:
    row = _one("SELECT COUNT(*) FROM business_hours"
               " WHERE business_id = ? AND is_closed = 0", (business_id,))
    return row[0] if row else 0


def job_type_requires_otp(job_type_id: int) -> bool:
    row = _one("SELECT 1 FROM job_type_contact_fields"
               " WHERE job_type_id = ? AND require_otp = 1", (job_type_id,))
    return row is not None


def count_active_vendors(vendor_type: str) -> int:
    row = _one("SELECT COUNT(*) FROM vendor_configs"
               " WHERE vendor_type = ? AND is_active = 1", (vendor_type,))
    return row[0] if row else 0


def get_business_stripe_account(business_id: int) -> Optional[str]:
    row = _one("SELECT stripe_account_id FROM businesses WHERE id = ?",
               (business_id,))
    return row[0] if row else None


def job_type_takes_money(job_type_id: int) -> bool:
    row = _one("SELECT 1 FROM job_types WHERE id = ?"
               " AND (payment_required = 1 OR deposit_required = 1)",
               (job_type_id,))
    return row is not None
