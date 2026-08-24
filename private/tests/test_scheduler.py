#!/usr/bin/env python3
#
# Scheduler — business rule tests
#
# Black box. A test builds its situation and checks its outcome through the
# same interface the client uses: it configures a business, offers job types,
# takes a booking, then reads back the same shapes the screens read. No test
# knows how anything is stored.
#
# That is deliberate. A test written against columns passes when the data is
# right, which is not the same as passing when the *customer's* action works —
# and it breaks whenever the schema moves, even though nothing anyone can see
# has changed. Written this way, a passing test is evidence that a customer can
# book, and the implementation stays free to change underneath.
#
# The schema tests below are the exception, and only until there is a rule to
# ask instead: they check that an installation starts with the things a
# business chooses from, which nothing else can yet report.
#

import pytest

from datetime import datetime, timedelta

from lib import configure_logging
from libtest import *

get_app_module("io.bithead.scheduler")
from io.bithead.scheduler import db
from io.bithead.scheduler import lib
from io.bithead.scheduler.lib import *

# A Monday, far enough out that no notice or cutoff rule reaches it unless a
# test asks for one. Dates are fixed rather than relative so a failure reads
# the same on any day of the week.
MONDAY = "2026-07-13"
TUESDAY = "2026-07-14"

# The clock every availability test is asked about. Slots are computed against
# a moment, and a test that used the real one would drift out of its own
# fixtures overnight.
NOW = datetime(2026, 7, 6, 9, 0)


def a_business(slot_mode="reserved", increment=30, cutoff_days=30,
               notice_hours=0, buffer_minutes=0):
    """A business that can take a booking, configured as the test needs."""
    business_id = db.insert_business("Test Business", "UTC", slot_mode)
    db.set_business_scheduling(business_id, increment, cutoff_days,
                               notice_hours, buffer_minutes)
    for day in range(7):
        db.set_business_hours(business_id, day, "09:00", "17:00", 0)
    return business_id


def a_job_type(business_id, min_employees=1, duration=60):
    """A job type with one size, which is what the kiosk books against."""
    job_type_id = db.insert_job_type(business_id, "Lawn Mowing", min_employees)
    size_id = db.insert_job_type_size(job_type_id, "Standard", duration, 50.0)
    return job_type_id, size_id


def an_employee(business_id, job_type_id, days=(1,), start="09:00", end="17:00"):
    """An employee who can do the work, and the days they work it."""
    employee_id = db.insert_employee(business_id, "Alice", "Kim", 1)
    db.link_employee_to_job_type(job_type_id, employee_id)
    for day in days:
        db.insert_employee_schedule(employee_id, day, start, end)
    return employee_id


def times_on(slots, date):
    return [s.time for s in slots if s.date == date]


def fresh_database():
    """A database containing only the schema and its seeds.

    The one thing a test may know about storage is that there *is* some, and
    that it can be emptied. It never looks inside.
    """
    db.set_database_name("test-scheduler.sqlite3")
    db.delete_database()
    db.start_database()


def test_installation():
    """What a business finds waiting for it before it has configured anything.

    Every one of these is chosen from rather than invented: a job type asks for
    contact information by picking from the field types, and a new business
    starts from one of the templates. An installation missing them leaves the
    first screen an operator sees with nothing on it.
    """
    fresh_database()

    # describe: the schema is created
    tables = [r[0] for r in db.select(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )]
    assert "businesses" in tables, "it: creates the business"
    assert "scheduled_jobs" in tables, "it: creates what a business exists to hold"
    assert "job_sessions" in tables, "it: creates the hold a customer takes on a time"

    version = db.select("SELECT version FROM versions ORDER BY id DESC LIMIT 1")
    assert version[0][0] == db.CURRENT_VERSION, "it: records the schema version"

    # describe: contact field types are seeded
    fields = db.select("SELECT name, field_type, otp_capable FROM contact_field_types"
                       " ORDER BY sort_order")
    names = [f[0] for f in fields]
    assert names == ["First Name", "Last Name", "Phone", "Email", "Address Line 1",
                     "Address Line 2", "City", "State", "Zip"], \
        "it: seeds the fields a customer can be asked for, in the order asked"

    verifiable = [f[0] for f in fields if f[2] == 1]
    assert verifiable == ["Phone", "Email"], \
        "it: marks only the fields that can receive a code as verifiable"

    # describe: business templates are seeded
    templates = [t[0] for t in db.select("SELECT name FROM business_templates ORDER BY id")]
    assert len(templates) == 6, "it: seeds a template for each kind of business"
    assert "Food & Drink" in templates, "it: includes the one that schedules a queue"

    food = db.select("SELECT config_json FROM business_templates WHERE name = 'Food & Drink'")
    assert '"unlimited"' in food[0][0], \
        "it: Food & Drink presets Time Slots to unlimited, which is what makes it a queue"

    # describe: the schedule timeout is seeded
    timeout = db.select("SELECT value FROM system_config WHERE key = 'schedule_timeout_minutes'")
    assert timeout[0][0] == "10", "it: a customer starts with ten minutes to finish scheduling"


def test_installation_is_idempotent():
    """Starting a service twice does not seed twice.

    The service calls `start_database` on every start, and a restart is
    ordinary. Seeding again would give a business two of every field type to
    choose from.
    """
    fresh_database()

    db.start_database()
    db.start_database()

    fields = db.select("SELECT COUNT(*) FROM contact_field_types")
    assert fields[0][0] == 9, "it: seeds the field types once"

    templates = db.select("SELECT COUNT(*) FROM business_templates")
    assert templates[0][0] == 6, "it: seeds the templates once"


def test_a_record_belongs_to_something_that_exists():
    """A child cannot be written against a parent that is not there.

    The schema leans on this throughout — an employee belongs to a business, a
    size to a job type — and SQLite enforces foreign keys per connection,
    defaulting to off. This is the check that the connection turns them on,
    because everything that depends on it fails silently otherwise.
    """
    fresh_database()

    with pytest.raises(Exception):
        db.insert(
            "INSERT INTO employees (business_id, first_name, last_name) VALUES (?, ?, ?)",
            (999, "Nobody", "Here")
        )


def test_slot_availability():
    """When a reserved business can take work, and when it cannot.

    Under this mode a time is a resource: it comes from an employee's own
    schedule, and anything already sitting on it takes it away. Every case
    here is a different way of taking it away.
    """
    fresh_database()

    # describe: single employee, no conflicts
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1,))

    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=4, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY) == ["09:00", "09:30", "10:00", "10:30"], \
        "it: offers every increment the employee is working"
    assert slots[0].employeeIds, "it: says who would do the work"

    # describe: the last slot leaves room for the work
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=50, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY)[-1] == "16:00", \
        "it: stops an hour before the employee finishes, because the job takes an hour"

    # describe: buffer time is added to the work
    fresh_database()
    business_id = a_business(increment=30, buffer_minutes=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1,))
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=50, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY)[-1] == "15:30", \
        "it: leaves room for the buffer as well as the work"

    # describe: employee has a time-off window
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))
    db.insert_employee_time_off(employee_id, MONDAY, "11:00", "13:00")

    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=50, from_date=MONDAY, now=NOW), MONDAY)
    assert "10:00" in times, "it: still offers a time that finishes before the window"
    assert "10:30" not in times, "it: refuses a time that would run into the window"
    assert "12:00" not in times, "it: refuses a time inside the window"
    assert "13:00" in times, "it: offers the time the window ends"

    # describe: employee has a confirmed job
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))
    job_id = db.insert_scheduled_job("ABC123", business_id, job_type_id, size_id,
                                     MONDAY, "10:00", 60, "confirmed")
    db.assign_employee_to_job(job_id, employee_id)

    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=50, from_date=MONDAY, now=NOW), MONDAY)
    assert "09:00" in times, "it: leaves the times before the job alone"
    assert "09:30" not in times, "it: refuses a time that would overlap the job"
    assert "10:00" not in times, "it: refuses the job's own time"
    assert "11:00" in times, "it: offers the time the job ends"

    # describe: pending job within timeout
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))
    job_id = db.insert_scheduled_job("PEND01", business_id, job_type_id, size_id,
                                     MONDAY, "10:00", 60, "pending")
    db.assign_employee_to_job(job_id, employee_id)
    db.insert_job_session(job_id, "token-live", 10)

    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=50, from_date=MONDAY, now=NOW), MONDAY)
    assert "10:00" not in times, \
        "it: holds the time while someone is still filling in the form"

    # describe: expired pending job
    db.update("UPDATE job_sessions SET expires_at = datetime('now', '-1 minutes')"
              " WHERE session_token = ?", ("token-live",))
    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=50, from_date=MONDAY, now=NOW), MONDAY)
    assert "10:00" in times, \
        "it: gives the time back once the hold has lapsed"

    # describe: job requires two employees, only one available
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, min_employees=2, duration=60)
    an_employee(business_id, job_type_id, days=(1,))
    assert get_available_slots(business_id, job_type_id, size_id,
                               limit=5, from_date=MONDAY, now=NOW) == [], \
        "it: offers nothing when the work needs more people than are free"

    # describe: job requires two employees, both available
    second = db.insert_employee(business_id, "Bob", "Torres", 1)
    db.link_employee_to_job_type(job_type_id, second)
    db.insert_employee_schedule(second, 1, "09:00", "17:00")
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=1, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY) == ["09:00"], "it: offers the time once both are free"
    assert len(slots[0].employeeIds) == 2, "it: allocates as many as the work needs"


def test_slot_availability_closed_days():
    """Days a business is not open for the work at all."""
    fresh_database()

    # describe: holiday closed day
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1, 2))
    holiday_id = db.insert_system_holiday("US", "United States", "A Holiday", MONDAY, 2026)
    db.observe_holiday(business_id, holiday_id, 2026)

    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=5, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY) == [], "it: offers nothing on a holiday"
    assert times_on(slots, TUESDAY), "it: carries on to the next day"

    # describe: employee does not work that day
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(2,))
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=5, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY) == [], "it: offers nothing on a day nobody works"
    assert times_on(slots, TUESDAY), "it: offers the day they do"


def test_slot_availability_windows():
    """The two windows that bound how soon and how far ahead a booking goes."""
    fresh_database()

    # describe: min booking notice
    business_id = a_business(increment=30, notice_hours=48)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(0, 1, 2, 3, 4, 5, 6))

    # Asked on the Monday itself, at 09:00.
    monday_now = datetime(2026, 7, 13, 9, 0)
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=5, from_date=MONDAY, now=monday_now)
    assert times_on(slots, MONDAY) == [], "it: offers nothing inside the notice window"
    assert slots[0].date >= "2026-07-15", "it: starts once the notice has passed"

    # describe: cutoff window
    fresh_database()
    business_id = a_business(increment=30, cutoff_days=2)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(3,))   # Wednesday only

    monday_now = datetime(2026, 7, 13, 9, 0)
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=5, from_date=MONDAY, now=monday_now)
    assert times_on(slots, "2026-07-15"), "it: offers a day inside the cutoff"

    business_id = a_business(increment=30, cutoff_days=1)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(3,))
    assert get_available_slots(business_id, job_type_id, size_id,
                               limit=5, from_date=MONDAY, now=monday_now) == [], \
        "it: offers nothing beyond the cutoff"
