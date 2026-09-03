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
# Two things below reach past that interface, and both say why where they sit:
# proving foreign keys are enforced, and moving a session's expiry into the
# past. Neither can be reached by anything a customer or operator can do.
#

import os
import re

import pytest

from datetime import datetime, timedelta

from lib import configure_logging, media
from libtest import *

get_app_module("io.bithead.scheduler")
from io.bithead.scheduler import db
from io.bithead.scheduler import lib
from io.bithead.scheduler.lib import *

# A Monday, far enough out that no notice or cutoff rule reaches it unless a
# test asks for one. Dates are fixed rather than relative so a failure reads
# the same on any day of the week.
BUNDLE = "io.bithead.scheduler"

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

MONDAY = "2026-07-13"
TUESDAY = "2026-07-14"

# The Monday `NOW` falls on, which is where a recurrence starting today lands.
FIRST_MONDAY = "2026-07-06"

# The clock every availability test is asked about. Slots are computed against
# a moment, and a test that used the real one would drift out of its own
# fixtures overnight.
NOW = datetime(2026, 7, 6, 9, 0)


def a_business(slot_mode="reserved", increment=30, cutoff_days=30,
               notice_hours=0, buffer_minutes=0):
    """A business that can take a booking, configured as the test needs."""
    business = create_business("Test Business", "UTC", slot_mode)
    set_scheduling(business.id, increment, cutoff_days, notice_hours, buffer_minutes)
    for day in range(7):
        set_operating_hours(business.id, day, "09:00", "17:00")
    return business.id


def a_job_type(business_id, min_employees=1, duration=60):
    """A job type with one size, which is what the kiosk books against."""
    job_type = create_job_type(business_id, "Lawn Mowing", min_employees)
    size = add_job_type_size(business_id, job_type.id, "Standard", duration, 50.0)
    return job_type.id, size.id


def an_employee(business_id, job_type_id, days=(1,), start="09:00", end="17:00",
                first="Alice", last="Kim"):
    """An employee who can do the work, and the days they work it."""
    employee = create_employee(business_id, first, last)
    allow_job_type(employee.id, job_type_id)
    for day in days:
        add_working_day(business_id, employee.id, day, start, end)
    return employee.id


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

    # describe: contact field types are seeded
    fields = get_contact_field_types()
    names = [f.name for f in fields]
    assert names == ["First Name", "Last Name", "Phone", "Email", "Address Line 1",
                     "Address Line 2", "City", "State", "Zip"], \
        "it: seeds the fields a customer can be asked for, in the order asked"

    verifiable = [f.name for f in fields if f.otpCapable]
    assert verifiable == ["Phone", "Email"], \
        "it: marks only the fields that can receive a code as verifiable"

    # describe: business templates are seeded
    templates = get_business_templates()
    assert len(templates) == 6, "it: seeds a template for each kind of business"

    food = [t for t in templates if t.name == "Food & Drink"]
    assert food, "it: includes the one that schedules a queue"
    assert food[0].config["slotMode"] == "unlimited", \
        "it: Food & Drink presets Time Slots to unlimited, which is what makes it a queue"

    # describe: the schedule timeout is seeded
    assert get_schedule_timeout_minutes() == 10, \
        "it: a customer starts with ten minutes to finish scheduling"


def test_installation_idempotent():
    """Starting a service twice does not seed twice.

    The service calls `start_database` on every start, and a restart is
    ordinary. Seeding again would give a business two of every field type to
    choose from.
    """
    fresh_database()

    db.start_database()
    db.start_database()

    assert len(get_contact_field_types()) == 9, "it: seeds the field types once"
    assert len(get_business_templates()) == 6, "it: seeds the templates once"


# --- The exceptions ------------------------------------------------------
#
# Two rules cannot be reached through the interface. Both are asked of `db` by
# name, so how they are stored stays in `db`.
#
# Foreign key enforcement is a property of the connection, not of any rule, so
# nothing an operator does can report on it. And a session expiring is the
# passage of time, which no customer can perform.


def test_foreign_keys():
    """A child cannot be written against a parent that is not there.

    The schema leans on this throughout — an employee belongs to a business, a
    size to a job type — and SQLite enforces foreign keys per connection,
    defaulting to off. This is the check that the connection turns them on,
    because everything that depends on it fails silently otherwise.
    """
    fresh_database()

    with pytest.raises(Exception):
        db.insert_employee(999, "Nobody", "Here", 1)


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
    add_time_off(business_id, employee_id, MONDAY, "11:00", "13:00")

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
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                              [employee_id])
    confirm_session(held.sessionToken)

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
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                              [employee_id])

    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=50, from_date=MONDAY, now=NOW), MONDAY)
    assert "10:00" not in times, \
        "it: holds the time while someone is still filling in the form"

    # describe: expired pending job
    db.expire_session(held.sessionToken)
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
    an_employee(business_id, job_type_id, days=(1,), first="Bob", last="Torres")
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
    close_on_holiday(business_id, "A Holiday", MONDAY)

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


def test_unlimited_slots():
    """When a time is a preference rather than a resource.

    Under this mode every increment the business is open is offered, always,
    and choosing one takes nothing away from anyone. A café taking an order for
    10:15 does not care that four other people also said 10:15 — so none of the
    machinery that guards a resource applies.
    """
    fresh_database()

    # describe: unlimited business
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=100, from_date=MONDAY, now=NOW)
    times = times_on(slots, MONDAY)
    assert times[0] == "09:00", "it: starts when the business opens"
    assert len(times) == 16, "it: offers every increment between opening and closing"

    # describe: last slot of the day
    assert times[-1] == "16:30", \
        "it: offers one increment before closing, whatever the work would take"

    # describe: no employees
    assert times, "it: offers times with nobody employed — nobody is being allocated"

    # describe: closed day
    set_operating_hours(business_id, 1, "09:00", "17:00", is_closed=True)
    assert times_on(get_available_slots(business_id, job_type_id, size_id,
                                        limit=10, from_date=MONDAY, now=NOW),
                    MONDAY) == [], "it: offers nothing on a day marked closed"

    # describe: holiday
    fresh_database()
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    close_on_holiday(business_id, "A Holiday", MONDAY)
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=10, from_date=MONDAY, now=NOW)
    assert times_on(slots, MONDAY) == [], "it: offers nothing on a holiday, as reserved does"
    assert times_on(slots, TUESDAY), "it: carries on to the next day"


def test_unlimited_slots_run_from_now():
    """The soonest time offered, and what the row calls it."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=5)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    # describe: times run from now
    five_past_ten = datetime(2026, 7, 13, 10, 5)
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=3, from_date=MONDAY, now=five_past_ten)
    assert times_on(slots, MONDAY)[0] == "10:10", \
        "it: starts at the next increment, not at the day's opening"

    # describe: first slot inside the next increment
    assert slots[0].displayDate == "ASAP", \
        "it: calls a time this close ASAP rather than naming the day"
    assert slots[1].displayDate != "ASAP", \
        "it: names the day for everything after it"

    # describe: first slot beyond the next increment
    #
    # Asked late on Monday, so Monday has nothing left and the soonest time is
    # Tuesday morning — which is far enough away to need its date.
    late = datetime(2026, 7, 13, 23, 30)
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=3, from_date=MONDAY, now=late)
    assert slots[0].date == TUESDAY, "it: moves to the next day"
    assert all(s.displayDate != "ASAP" for s in slots), \
        "it: names the day when the soonest time is not close"

    # describe: reserved business
    fresh_database()
    business_id = a_business(increment=5)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1,))
    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=5, from_date=MONDAY, now=five_past_ten)
    assert all(s.displayDate != "ASAP" for s in slots), \
        "it: never says ASAP where a time is a resource"


def test_unlimited_slots_windows():
    """The notice and cutoff windows bind here too."""
    fresh_database()

    # describe: minimum booking notice on an unlimited business
    business_id = a_business(slot_mode="unlimited", increment=30, notice_hours=2)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    nine = datetime(2026, 7, 13, 9, 0)
    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=100, from_date=MONDAY, now=nine), MONDAY)
    assert "10:30" not in times, "it: offers nothing inside the notice window"
    assert times[0] == "11:00", "it: starts once the notice has passed"

    # describe: cutoff window
    fresh_database()
    business_id = a_business(slot_mode="unlimited", increment=30, cutoff_days=1)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    for day in range(7):
        set_operating_hours(business_id, day, "09:00", "17:00", is_closed=(day != 3))

    slots = get_available_slots(business_id, job_type_id, size_id,
                                limit=5, from_date=MONDAY, now=nine)
    assert slots == [], "it: offers nothing beyond the cutoff"


def test_unlimited_slots_unallocated():
    """Two customers may choose the same time.

    This is the whole of what `unlimited` means, and the one case that would
    pass by accident if availability were simply never computed.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    def offered():
        return times_on(get_available_slots(business_id, job_type_id, size_id,
                                            limit=100, from_date=MONDAY, now=NOW), MONDAY)

    assert "10:00" in offered(), "it: offers the time to the first customer"

    # describe: two customers, same time
    first = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(first.sessionToken)
    assert "10:00" in offered(), \
        "it: still offers the time once somebody has taken it"

    second = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirmed = confirm_session(second.sessionToken)
    assert confirmed is not None, "it: lets the second customer take it too"
    assert confirmed.jobCode != first.jobCode, "it: books them as two appointments"
    assert "10:00" in offered(), "it: is still there afterwards"


def a_booking(business_id, job_type_id, size_id, date, time, employee_ids=None):
    """An appointment a customer has already made."""
    held = create_job_session(business_id, job_type_id, size_id, date, time,
                              employee_ids or [])
    confirm_session(held.sessionToken)
    return held.jobId


def test_minimum_change_notice():
    """How close to the appointment a customer may still change it.

    It binds the customer only. The operator changes an appointment whenever
    they like, which is what makes "call the business" useful advice rather
    than a brush-off.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    set_change_notice(business_id, 120)

    # An appointment at 14:00 on the Monday.
    job_id = a_booking(business_id, job_type_id, size_id, MONDAY, "14:00")

    # describe: outside the window
    well_before = datetime(2026, 7, 13, 9, 0)
    assert get_appointment(job_id, now=well_before).changesClosed is False, \
        "it: is open to the customer while the appointment is far off"
    reschedule_appointment(job_id, MONDAY, "15:00", now=well_before)
    assert get_appointment(job_id, now=well_before).scheduledTime == "15:00", \
        "it: lets the customer move it"

    # describe: inside the window
    just_inside = datetime(2026, 7, 13, 13, 30)
    assert get_appointment(job_id, now=just_inside).changesClosed is True, \
        "it: closes to the customer inside the notice window"
    with pytest.raises(ValidationError):
        reschedule_appointment(job_id, MONDAY, "16:00", now=just_inside)
    with pytest.raises(ValidationError):
        cancel_appointment(job_id, now=just_inside)
    assert get_appointment(job_id, now=just_inside).scheduledTime == "15:00", \
        "it: leaves the appointment where it was"

    # describe: inside the window, operator acting
    reschedule_appointment(job_id, MONDAY, "16:00", as_operator=True, now=just_inside)
    assert get_appointment(job_id, now=just_inside).scheduledTime == "16:00", \
        "it: lets the business move it whenever it likes"
    cancel_appointment(job_id, as_operator=True, now=just_inside)
    assert get_appointment(job_id, now=just_inside).status == "cancelled", \
        "it: lets the business cancel it too"


def test_minimum_change_notice_of_zero():
    """Zero notice means up to the moment the appointment starts."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    set_change_notice(business_id, 0)
    job_id = a_booking(business_id, job_type_id, size_id, MONDAY, "14:00")

    # describe: notice of zero
    a_minute_before = datetime(2026, 7, 13, 13, 59)
    assert get_appointment(job_id, now=a_minute_before).changesClosed is False, \
        "it: stays open right up to the start"
    cancel_appointment(job_id, now=a_minute_before)
    assert get_appointment(job_id, now=a_minute_before).status == "cancelled", \
        "it: lets the customer cancel a minute before"

    # describe: once it has started
    job_id = a_booking(business_id, job_type_id, size_id, MONDAY, "14:00")
    after_it_starts = datetime(2026, 7, 13, 14, 1)
    assert get_appointment(job_id, now=after_it_starts).changesClosed is True, \
        "it: closes once the appointment has begun"


def test_minimum_change_notice_reserved():
    """A reserved business has the same problem.

    A technician already driving over is a wasted trip whether or not the time
    was taken from anyone else.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))
    set_change_notice(business_id, 120)
    job_id = a_booking(business_id, job_type_id, size_id, MONDAY, "14:00",
                       [employee_id])

    # describe: reserved business
    just_inside = datetime(2026, 7, 13, 13, 30)
    assert get_appointment(job_id, now=just_inside).changesClosed is True, \
        "it: applies where a time is a resource too"
    with pytest.raises(ValidationError):
        cancel_appointment(job_id, now=just_inside)


def test_business_hours():
    """What the business's own hours decide, which depends on the mode.

    They are separate from employee schedules, which say when people work: a
    technician may legitimately start before the office opens. Under `reserved`
    the hours are shown to the customer and nothing more; under `unlimited`
    they are the whole answer.
    """
    fresh_database()

    # describe: reserved business
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1,), start="07:00", end="19:00")

    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=100, from_date=MONDAY, now=NOW), MONDAY)
    assert times[0] == "07:00", \
        "it: offers a time before the business opens, because someone is working"
    assert "17:30" in times, \
        "it: offers a time after it closes, for the same reason"

    # describe: unlimited business
    fresh_database()
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    set_operating_hours(business_id, 1, "10:00", "12:00")

    times = times_on(get_available_slots(business_id, job_type_id, size_id,
                                         limit=100, from_date=MONDAY, now=NOW), MONDAY)
    assert times == ["10:00", "10:30", "11:00", "11:30"], \
        "it: offers exactly the increments the business is open"


def test_business_hours_closed_day():
    """A day the business marks closed, in each mode."""
    fresh_database()

    # describe: a day marked closed, unlimited
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    set_operating_hours(business_id, 1, "09:00", "17:00", is_closed=True)

    assert times_on(get_available_slots(business_id, job_type_id, size_id,
                                        limit=10, from_date=MONDAY, now=NOW),
                    MONDAY) == [], "it: offers nothing, because the hours are the answer"

    # describe: a day marked closed, reserved
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1,))
    set_operating_hours(business_id, 1, "09:00", "17:00", is_closed=True)

    assert times_on(get_available_slots(business_id, job_type_id, size_id,
                                        limit=10, from_date=MONDAY, now=NOW),
                    MONDAY), \
        "it: still offers the employee's day — the schedule governs, not the counter"


def test_job_session():
    """The hold a customer takes on a time while they finish scheduling.

    Under `reserved` this is what stops two customers taking the same time,
    and it lapses on its own so a customer who wanders off does not keep a
    time forever.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))

    # describe: create session
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                              [employee_id])
    assert held.sessionToken, "it: hands back a token to carry through the flow"
    assert held.jobCode, "it: gives the appointment its customer-facing code"
    assert held.expiresAt, "it: says when the hold lapses"
    assert get_appointment(held.jobId, now=NOW).status == "pending", \
        "it: the appointment exists, not yet confirmed"

    # describe: extend session
    #
    # Asked a minute later, so the new expiry is a minute further out. Both
    # calls inside one second would land on the same timestamp and prove
    # nothing.
    later = extend_session(held.sessionToken, now=datetime.utcnow() + timedelta(minutes=1))
    assert later.expiresAt > held.expiresAt, \
        "it: pushes the hold out by the timeout when the customer is still working"

    # describe: commit session
    confirmed = confirm_session(held.sessionToken)
    assert confirmed is not None
    assert get_appointment(held.jobId, now=NOW).status == "confirmed", \
        "it: turns the hold into a booking"


def test_job_session_expires():
    """A hold that lapses gives the time back."""
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))

    def offered():
        return times_on(get_available_slots(business_id, job_type_id, size_id,
                                            limit=100, from_date=MONDAY, now=NOW),
                        MONDAY)

    first = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                               [employee_id])
    assert "10:00" not in offered(), "it: holds the time while the session is live"

    db.expire_session(first.sessionToken)
    assert "10:00" in offered(), "it: gives the time back when the hold lapses"

    # describe: expired session on re-lock
    #
    # Somebody else takes the time in the meantime, which is the whole risk of
    # wandering off.
    second = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                                [employee_id])
    confirm_session(second.sessionToken)

    with pytest.raises(SessionExpired):
        confirm_session(first.sessionToken)
    with pytest.raises(SessionExpired):
        extend_session(first.sessionToken)
    assert "10:00" not in offered(), \
        "it: the time now belongs to whoever confirmed it"


def test_expired_holds():
    """Abandoned holds are swept; a booking's is left alone.

    The sweep is what `finalized` is for: a confirmed appointment keeps its
    session record, and a customer who never finished does not.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))

    abandoned = create_job_session(business_id, job_type_id, size_id, MONDAY,
                                   "10:00", [employee_id])
    booked = create_job_session(business_id, job_type_id, size_id, MONDAY,
                                "12:00", [employee_id])
    confirm_session(booked.sessionToken)

    # describe: nothing has lapsed yet
    assert cleanup_expired_sessions() == 0, "it: leaves live holds alone"

    # describe: both have lapsed
    db.expire_session(abandoned.sessionToken)
    db.expire_session(booked.sessionToken)

    assert cleanup_expired_sessions() == 1, \
        "it: sweeps the hold nobody finished, and only that one"
    assert cleanup_expired_sessions() == 0, "it: has nothing left to sweep"
    assert get_appointment(booked.jobId, now=NOW).status == "confirmed", \
        "it: the booking is untouched"


def sent_codes():
    """Capture what the vendor layer would have sent.

    The app wires a real sender at startup; a test wires this one and reads
    the code back, which is the only way to then type it in correctly.
    """
    sent = []
    set_otp_sender(lambda destination, code: sent.append((destination, code)))
    return sent


def test_otp():
    """Verifying that a contact detail belongs to the person giving it.

    A code goes to what the customer typed, and only a field that can receive
    one — a phone number, an email address — can be verified at all.
    """
    fresh_database()
    sent = sent_codes()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")

    # describe: send OTP
    result = send_otp(held.sessionToken, "+15552340000")
    assert len(sent) == 1, "it: hands the code to the vendor layer"
    assert sent[0][0] == "+15552340000", "it: sends it where the customer said"
    assert len(sent[0][1]) == 6 and sent[0][1].isdigit(), \
        "it: is six digits, because somebody reads it off a screen and types it"
    assert result.attemptsRemaining == 3, "it: starts with three tries"
    assert result.verified is False, "it: is not verified by being sent"

    # describe: verify correct OTP
    code = sent[0][1]
    verified = verify_otp(held.sessionToken, code)
    assert verified.verified is True, "it: accepts the code that was sent"
    assert verified.attemptsRemaining == 3, "it: spends no attempt on a correct code"


def test_otp_wrong_code():
    """Getting it wrong, and running out of tries."""
    fresh_database()
    sent = sent_codes()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    send_otp(held.sessionToken, "someone@example.com")
    code = sent[0][1]
    wrong = "000000" if code != "000000" else "111111"

    # describe: verify wrong OTP
    with pytest.raises(OTPInvalid) as first:
        verify_otp(held.sessionToken, wrong)
    assert first.value.attemptsRemaining == 2, "it: spends an attempt"

    with pytest.raises(OTPInvalid) as second:
        verify_otp(held.sessionToken, wrong)
    assert second.value.attemptsRemaining == 1, "it: counts down"

    # describe: max attempts exceeded
    with pytest.raises(OTPMaxAttemptsExceeded):
        verify_otp(held.sessionToken, wrong)

    # describe: the right code, too late
    with pytest.raises(OTPMaxAttemptsExceeded):
        verify_otp(held.sessionToken, code)


def test_otp_resend():
    """A customer who asks for another code gets a fresh three tries.

    The old code stops working: a code still live after its replacement was
    sent would mean two valid codes at once.
    """
    fresh_database()
    sent = sent_codes()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")

    send_otp(held.sessionToken, "+15552340000")
    first_code = sent[0][1]
    with pytest.raises(OTPInvalid):
        verify_otp(held.sessionToken, "000000" if first_code != "000000" else "111111")

    again = send_otp(held.sessionToken, "+15552340000")
    assert again.attemptsRemaining == 3, "it: gives the customer three tries again"

    second_code = sent[1][1]
    if second_code != first_code:
        with pytest.raises(OTPInvalid):
            verify_otp(held.sessionToken, first_code)
    assert verify_otp(held.sessionToken, second_code).verified is True, \
        "it: accepts the code it just sent"


def test_otp_remembered():
    """Once verified, the contact detail stays verified.

    The customer may come back to the step, or the screen may ask twice. Having
    proved the number is theirs, they do not prove it again — and a wrong code
    typed afterwards does not undo it or cost them an attempt.
    """
    fresh_database()
    sent = sent_codes()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    send_otp(held.sessionToken, "+15552340000")
    code = sent[0][1]

    assert verify_otp(held.sessionToken, code).verified is True

    again = verify_otp(held.sessionToken, "000000" if code != "000000" else "111111")
    assert again.verified is True, "it: is still verified"
    assert again.attemptsRemaining == 3, "it: spends no attempt once verified"


def a_booked_appointment(contact, business_id=None, job_type_id=None, size_id=None):
    """A confirmed appointment with the contact details a customer gave."""
    if business_id is None:
        business_id = a_business(slot_mode="unlimited", increment=30)
        job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact=contact)
    return held.jobCode


def test_appointment_access_send():
    """Getting back into a booking you already made.

    A job code is not a secret — it is printed on a confirmation and read out
    over the phone — so it is not enough on its own. A code sent to the contact
    detail the customer gave is what proves the booking is theirs.
    """
    fresh_database()
    sent = sent_codes()

    # describe: known job code
    job_code = a_booked_appointment({"Phone": "+15552340000"})
    result = request_appointment_access(job_code)
    assert result.channel == "sms", "it: sends it to the phone they gave"
    assert len(sent) == 1, "it: hands the code to the vendor layer"
    assert len(sent[0][1]) == 6 and sent[0][1].isdigit(), "it: is six digits"
    assert result.sentTo.endswith("0000"), \
        "it: shows the last four, so the customer knows which number it went to"
    assert "5552340000" not in result.sentTo, \
        "it: hides the rest, so guessing a job code teaches nobody a phone number"

    # describe: customer gave only an email
    fresh_database()
    sent = sent_codes()
    job_code = a_booked_appointment({"Email": "someone@example.com"})
    assert request_appointment_access(job_code).channel == "email", \
        "it: falls back to email when that is all there is"

    # describe: customer gave both
    fresh_database()
    sent = sent_codes()
    job_code = a_booked_appointment({"Phone": "+15552340000",
                                     "Email": "someone@example.com"})
    assert request_appointment_access(job_code).channel == "sms", \
        "it: prefers the phone, which reaches someone standing in a queue"


def test_appointment_access_refusals():
    """The job codes that cannot be sent a code at all."""
    fresh_database()
    sent = sent_codes()

    # describe: customer gave neither
    job_code = a_booked_appointment({})
    with pytest.raises(NoContactChannel):
        request_appointment_access(job_code)
    assert sent == [], "it: sends nothing"

    # describe: unknown job code
    with pytest.raises(JobNotFound):
        request_appointment_access("ZZZZZZ")
    assert sent == [], "it: sends nothing for a code that is not a booking"

    # describe: cancelled job
    fresh_database()
    sent = sent_codes()
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
    cancel_appointment(held.jobId, as_operator=True)

    with pytest.raises(AppointmentInactive):
        request_appointment_access(held.jobCode)
    assert sent == [], "it: does not let someone back into a cancelled appointment"


def test_appointment_access_verify():
    """Typing the code back in, and the ways that can fail."""
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    request_appointment_access(job_code)
    code = sent[0][1]

    # describe: wrong code
    with pytest.raises(CodeInvalid):
        verify_appointment_access(job_code, "000000" if code != "000000" else "111111")

    # describe: correct code
    appointment = verify_appointment_access(job_code, code)
    assert appointment.jobCode == job_code, "it: hands back the appointment"

    # describe: correct code used twice
    with pytest.raises(CodeSpent):
        verify_appointment_access(job_code, code)


def test_appointment_access_handle():
    """What a customer carries once they have proved the booking is theirs.

    The three routes a customer reaches — read, move, cancel — take this and
    not the appointment's id. An id is a small integer, so a route taking one
    is a route anybody reaches by counting.
    """
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    request_appointment_access(job_code)
    opened = verify_appointment_access(job_code, sent[0][1])

    # describe: the handle proving a code was spent
    assert opened.accessHandle, "it: is handed back"
    assert appointment_for_handle(opened.accessHandle).jobCode == job_code, \
        "it: opens the appointment it was minted for"
    assert appointment_for_handle(opened.accessHandle.lower()).jobCode == job_code, \
        "it: is read however it was typed"

    # describe: a handle nobody was given
    assert appointment_for_handle("ZZZZZZ") is None, \
        "it: opens nothing"
    assert appointment_for_handle("") is None, \
        "it: opens nothing when it is empty"

    # describe: proving it again
    request_appointment_access(job_code)
    again = verify_appointment_access(job_code, sent[-1][1])
    assert again.accessHandle != opened.accessHandle, \
        "it: is a new handle each time"
    assert appointment_for_handle(opened.accessHandle) is None, \
        "it: stops the one before it opening anything"


def test_appointment_access_expiry():
    """A code is good for thirty minutes, and the digits do not outlive that."""
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    half_past = datetime(2026, 7, 6, 12, 0)
    request_appointment_access(job_code, now=half_past)
    code = sent[0][1]

    # describe: expired code
    too_late = half_past + timedelta(minutes=31)
    with pytest.raises(CodeExpired):
        verify_appointment_access(job_code, code, now=too_late)

    just_in_time = half_past + timedelta(minutes=29)
    assert verify_appointment_access(job_code, code, now=just_in_time).jobCode == job_code, \
        "it: accepts the same digits inside the window"


def wrong_code(code):
    return "000000" if code != "000000" else "111111"


def test_appointment_access_lockout():
    """Six wrong codes inside a minute is somebody working through the digits.

    A rate rather than a total: six spread over an afternoon is a forgetful
    customer, and locking them out would be the rule doing harm.
    """
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000",
                                     "Email": "someone@example.com"})
    start = datetime(2026, 7, 6, 12, 0)
    request_appointment_access(job_code, now=start)
    code = sent[0][1]
    sent.clear()

    # describe: five wrong codes in a minute
    for i in range(5):
        with pytest.raises(CodeInvalid):
            verify_appointment_access(job_code, wrong_code(code),
                                      now=start + timedelta(seconds=i + 1))
    assert sent == [], "it: says nothing while the customer is still trying"

    # describe: sixth wrong code in a minute
    with pytest.raises(AppointmentLocked):
        verify_appointment_access(job_code, wrong_code(code),
                                  now=start + timedelta(seconds=6))
    assert len(sent) == 2, \
        "it: tells the customer on every channel they gave, not just the preferred one"

    # describe: the right code, once locked
    with pytest.raises(AppointmentLocked):
        verify_appointment_access(job_code, code, now=start + timedelta(seconds=7))


def test_appointment_access_lockout_window():
    """The window is a minute, so a slow guesser is a customer."""
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    start = datetime(2026, 7, 6, 12, 0)
    request_appointment_access(job_code, now=start)
    code = sent[0][1]

    # describe: sixth wrong code spread over two minutes
    for i in range(6):
        with pytest.raises(CodeInvalid):
            verify_appointment_access(job_code, wrong_code(code),
                                      now=start + timedelta(seconds=i * 20))

    assert verify_appointment_access(job_code, code,
                                     now=start + timedelta(minutes=3)).jobCode == job_code, \
        "it: still opens for the customer who eventually gets it right"


def test_appointment_access_lockout_scope():
    """The lock shuts the customer out. The business is never shut out."""
    fresh_database()
    sent = sent_codes()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})

    start = datetime(2026, 7, 6, 12, 0)
    request_appointment_access(held.jobCode, now=start)
    code = sent[0][1]
    for i in range(5):
        with pytest.raises(CodeInvalid):
            verify_appointment_access(held.jobCode, wrong_code(code),
                                      now=start + timedelta(seconds=i + 1))
    with pytest.raises(AppointmentLocked):
        verify_appointment_access(held.jobCode, wrong_code(code),
                                  now=start + timedelta(seconds=6))

    # describe: lookup for a locked job
    sent.clear()
    with pytest.raises(AppointmentLocked):
        request_appointment_access(held.jobCode, now=start + timedelta(minutes=5))
    assert sent == [], "it: sends no further codes"

    # describe: reschedule a locked job through the public route
    with pytest.raises(AppointmentLocked):
        reschedule_appointment(held.jobId, MONDAY, "15:00", now=NOW)
    with pytest.raises(AppointmentLocked):
        cancel_appointment(held.jobId, now=NOW)

    # describe: modify a locked job as the operator
    reschedule_appointment(held.jobId, MONDAY, "15:00", as_operator=True, now=NOW)
    assert get_appointment(held.jobId, now=NOW).scheduledTime == "15:00", \
        "it: the business moves it regardless"

    # describe: a lock cannot be lifted
    assert not [name for name in dir(lib)
                if "unlock" in name.lower() or "clear_lock" in name.lower()], \
        "it: there is no call that reopens the customer's door"


def test_job_code_throttle():
    """Guessing at job codes costs the guesser a day.

    A wrong job code is somebody guessing, and guessing is the only way to find
    an appointment that is not yours.
    """
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    guesser = "203.0.113.9"
    start = datetime(2026, 7, 6, 12, 0)

    # describe: two unknown codes in a minute
    for i in range(2):
        with pytest.raises(JobNotFound):
            request_appointment_access("ZZZZZ%d" % i, caller=guesser,
                                       now=start + timedelta(seconds=i))
    assert request_appointment_access(job_code, caller=guesser,
                                      now=start + timedelta(seconds=3)).channel == "sms", \
        "it: the caller may keep going after two misses"

    # describe: third unknown code in a minute
    fresh_database()
    sent = sent_codes()
    job_code = a_booked_appointment({"Phone": "+15552340000"})
    for i in range(2):
        with pytest.raises(JobNotFound):
            request_appointment_access("ZZZZZ%d" % i, caller=guesser,
                                       now=start + timedelta(seconds=i))
    with pytest.raises(CallerBlocked):
        request_appointment_access("ZZZZZ9", caller=guesser,
                                   now=start + timedelta(seconds=2))

    # describe: a blocked caller submits a valid code
    sent.clear()
    with pytest.raises(CallerBlocked):
        request_appointment_access(job_code, caller=guesser,
                                   now=start + timedelta(seconds=5))
    assert sent == [], "it: sends nothing; the block is on the caller, not the code"

    # describe: another caller is unaffected
    assert request_appointment_access(job_code, caller="198.51.100.4",
                                      now=start + timedelta(seconds=6)).channel == "sms", \
        "it: somebody else may still look up their own appointment"

    # describe: the block lasts 24 hours
    with pytest.raises(CallerBlocked):
        request_appointment_access(job_code, caller=guesser,
                                   now=start + timedelta(hours=23, minutes=59))

    # describe: block expires
    assert request_appointment_access(job_code, caller=guesser,
                                      now=start + timedelta(hours=24, minutes=1)).channel == "sms", \
        "it: the caller may submit again the next day"


def test_job_code_throttle_window():
    """The window is a minute, so a slow mistyper is a customer."""
    fresh_database()
    sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    caller = "203.0.113.9"
    start = datetime(2026, 7, 6, 12, 0)

    # describe: three misses spread over two minutes
    for i in range(3):
        with pytest.raises(JobNotFound):
            request_appointment_access("ZZZZZ%d" % i, caller=caller,
                                       now=start + timedelta(seconds=i * 45))

    assert request_appointment_access(job_code, caller=caller,
                                      now=start + timedelta(minutes=3)).channel == "sms", \
        "it: still lets them look up their own appointment"


def test_job_code_throttle_lockout():
    """A miss identifies no appointment, so there is nobody to tell."""
    fresh_database()
    sent = sent_codes()

    job_code = a_booked_appointment({"Phone": "+15552340000"})
    caller = "203.0.113.9"
    start = datetime(2026, 7, 6, 12, 0)
    sent.clear()

    # describe: nothing is locked or notified
    for i in range(2):
        with pytest.raises(JobNotFound):
            request_appointment_access("ZZZZZ%d" % i, caller=caller,
                                       now=start + timedelta(seconds=i))
    with pytest.raises(CallerBlocked):
        request_appointment_access("ZZZZZ9", caller=caller,
                                   now=start + timedelta(seconds=2))

    assert sent == [], "it: nobody is messaged"
    appointment = get_appointment_by_code(job_code)
    assert appointment.status == "confirmed", \
        "it: the real appointment is untouched and unlocked"
    assert request_appointment_access(job_code, caller="198.51.100.4",
                                      now=start + timedelta(seconds=5)).channel == "sms", \
        "it: and still opens for its own customer"


def test_recurrence():
    """Repeating work, materialised a cutoff window at a time.

    A recurrence is a standing arrangement, not a pile of appointments made
    years ahead: instances appear as the horizon rolls forward, so a customer
    who stops after three months has not filled the calendar to 2030.
    """
    fresh_database()

    business_id = a_business(increment=30, cutoff_days=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))
    recurrence = create_recurrence(business_id, job_type_id, size_id,
                                   "weekly", "10:00", days_of_week=[1])

    # describe: rolling horizon creates instance
    made = materialize_recurrences(now=datetime(2026, 7, 6, 9, 0))
    assert made == 5, "it: creates the Mondays inside the cutoff window and no more"

    jobs = get_recurring_jobs(recurrence.id)
    assert jobs[0].scheduledDate == FIRST_MONDAY, \
        "it: starts on the first matching day, today included"
    assert jobs[-1].scheduledDate == "2026-08-03", \
        "it: stops at the last one inside the cutoff"
    assert all(j.scheduledTime == "10:00" for j in jobs), \
        "it: books them at the preferred time"
    assert all(j.status == "confirmed" for j in jobs), \
        "it: they are bookings, not holds — nobody is choosing a time"
    assert jobs[0].employeeIds == [employee_id], "it: assigns whoever is free"

    # describe: instance already exists
    assert materialize_recurrences(now=datetime(2026, 7, 6, 9, 0)) == 0, \
        "it: running again creates nothing"
    assert len(get_recurring_jobs(recurrence.id)) == 5, "it: leaves the same five"

    # describe: the horizon rolls forward
    made = materialize_recurrences(now=datetime(2026, 7, 13, 9, 0))
    assert made == 1, "it: creates the one Monday that has come into the window"


def test_recurrence_unavailable():
    """Work nobody can do is still work.

    The appointment is made and left unassigned rather than skipped: a customer
    with a standing arrangement expects their slot, and an operator would
    rather see it in Needs Attention than find out it never existed.
    """
    fresh_database()

    # A three-day window, so exactly one Monday falls inside it.
    business_id = a_business(increment=30, cutoff_days=3)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    # An employee who works Tuesdays only, for a Monday recurrence.
    an_employee(business_id, job_type_id, days=(2,))
    recurrence = create_recurrence(business_id, job_type_id, size_id,
                                   "weekly", "10:00", days_of_week=[1])

    # describe: no available employees
    assert materialize_recurrences(now=datetime(2026, 7, 6, 9, 0)) == 1, \
        "it: makes the appointment anyway"

    jobs = get_recurring_jobs(recurrence.id)
    assert jobs[0].status == "confirmed", "it: it is a real booking"
    assert jobs[0].employeeIds == [], "it: with nobody on it"
    assert [j.id for j in get_unassigned_jobs(business_id)] == [jobs[0].id], \
        "it: and it turns up in the unassigned list"


def test_cancel_recurrence():
    """Cancelling stops the next instance, and leaves the ones already made."""
    fresh_database()

    business_id = a_business(increment=30, cutoff_days=8)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(1,))
    recurrence = create_recurrence(business_id, job_type_id, size_id,
                                   "weekly", "10:00", days_of_week=[1])
    materialize_recurrences(now=datetime(2026, 7, 6, 9, 0))
    already = len(get_recurring_jobs(recurrence.id))

    # describe: recurrence cancelled
    cancel_recurrence(recurrence.id)
    assert materialize_recurrences(now=datetime(2026, 7, 13, 9, 0)) == 0, \
        "it: creates no more instances"
    assert len(get_recurring_jobs(recurrence.id)) == already, \
        "it: leaves the appointments already made, which customers are expecting"


def test_recurrence_interval_limits():
    """An arrangement that saves and then books nothing is the worst failure.

    The operator sees it in their list, the customer waits for an appointment
    that was never made, and nothing anywhere says so. Refusing at the point of
    setting it up puts the problem in front of the person who can fix it.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    # describe: an interval that is not built yet
    for interval in ("biweekly", "monthly", "custom"):
        with pytest.raises(ValidationError):
            create_recurrence(business_id, job_type_id, size_id, interval,
                              "10:00", days_of_week=[1])

    # describe: weekly with no days chosen
    with pytest.raises(ValidationError):
        create_recurrence(business_id, job_type_id, size_id, "weekly", "10:00")

    # describe: the intervals that are built
    assert create_recurrence(business_id, job_type_id, size_id, "weekly",
                             "10:00", days_of_week=[1]).intervalType == "weekly"
    assert create_recurrence(business_id, job_type_id, size_id, "daily",
                             "10:00").intervalType == "daily"


def test_send_reminders():
    """The day-before nudge, for whoever asked to be nudged."""
    fresh_database()
    sent = sent_codes()

    business_id, job_type_id, size_id, alice, _ = a_scheduled_business()
    contact = {"First Name": "Jane", "Phone": "555-0101"}
    tomorrow = book_at(business_id, job_type_id, size_id, "2026-09-02", "10:00",
                       [alice], contact=contact)
    later = book_at(business_id, job_type_id, size_id, "2026-09-03", "10:00",
                    [alice], contact=contact)

    reminded = send_reminders(now=datetime(2026, 9, 1, 9, 0))

    assert reminded == 1, "it: is tomorrow's, and only tomorrow's"
    assert len(sent) == 1
    assert "555-0101" in sent[0][0]
    assert "2" in sent[0][1] or "September" in sent[0][1], \
        "it: says when, which is the whole point of the message"

    # describe: run again the same day
    sent.clear()
    assert send_reminders(now=datetime(2026, 9, 1, 17, 0)) == 1, \
        "it: is not idempotent yet — the cron runs once a day"

    # describe: a business that turned reminders off
    sent.clear()
    update_business_config(business_id, {"reminderEnabled": False})
    assert send_reminders(now=datetime(2026, 9, 1, 9, 0)) == 0, \
        "it: says nothing for a business that asked for nothing"
    assert sent == []

    # describe: an appointment called off
    update_business_config(business_id, {"reminderEnabled": True})
    cancel_appointment(tomorrow, as_operator=True)
    assert send_reminders(now=datetime(2026, 9, 1, 9, 0)) == 0, \
        "it: does not remind anybody about an appointment that is off"
    assert later is not None


def test_background_jobs():
    """The two things a clock runs, and the order the daily one runs them in."""
    fresh_database()
    from io.bithead.scheduler import jobs

    declared = jobs.get_jobs()
    assert sorted(j.name for j in declared) == ["daily", "hourly"], \
        "it: is what the service reads to decide what to run"
    assert all(j.seconds > 0 for j in declared)

    # describe: an hour with nothing to sweep
    assert jobs.hourly() == 0

    # it: makes what is due before telling anybody about it — an appointment
    # materialised today may be tomorrow's, and that customer has to hear
    called = []
    was_materialize, was_remind = lib.materialize_recurrences, lib.send_reminders
    lib.materialize_recurrences = lambda *a, **k: called.append("made") or 0
    lib.send_reminders = lambda *a, **k: called.append("told") or 0
    try:
        jobs.daily()
    finally:
        lib.materialize_recurrences, lib.send_reminders = was_materialize, was_remind
    assert called == ["made", "told"]


def test_daily_recurrence():
    """Every day inside the window, which is what `daily` has to mean."""
    fresh_database()

    business_id = a_business(increment=30, cutoff_days=3)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id, days=(0, 1, 2, 3, 4, 5, 6))
    recurrence = create_recurrence(business_id, job_type_id, size_id,
                                   "daily", "10:00")

    assert materialize_recurrences(now=datetime(2026, 7, 6, 9, 0)) == 4, \
        "it: creates one for each day in the window, today included"
    assert [j.scheduledDate for j in get_recurring_jobs(recurrence.id)] == \
        ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09"], \
        "it: consecutive days, not just the matching weekdays"


def test_booking_confirmation():
    """What the customer is sent once the appointment is made.

    Two settings decide it, and both have to agree: the business has to have
    the channel switched on, and the customer has to have given something to
    send to. Enabling both does not promise both — a job type that never asks
    for an email sends a text and nothing else.
    """
    fresh_database()

    # describe: business sends neither
    sent = sent_codes()
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirmed = confirm_session(held.sessionToken,
                                contact={"Phone": "+15552340000",
                                         "Email": "someone@example.com"})
    assert sent == [], "it: sends nothing when the business asked for nothing"
    assert confirmed.confirmationSentTo == [], \
        "it: and reports that nothing went out, so the kiosk says to keep the code"

    # describe: business sends both, customer gave both
    fresh_database()
    sent = sent_codes()
    business_id = a_business(slot_mode="unlimited", increment=30)
    set_confirmation_channels(business_id, by_sms=True, by_email=True)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirmed = confirm_session(held.sessionToken,
                                contact={"Phone": "+15552340000",
                                         "Email": "someone@example.com"})
    assert [c.channel for c in confirmed.confirmationSentTo] == ["sms", "email"], \
        "it: sends on both"
    assert len(sent) == 2, "it: two messages went to the vendor layer"

    # describe: business sends both, customer gave only a phone
    fresh_database()
    sent = sent_codes()
    business_id = a_business(slot_mode="unlimited", increment=30)
    set_confirmation_channels(business_id, by_sms=True, by_email=True)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirmed = confirm_session(held.sessionToken,
                                contact={"Phone": "+15552340000"})
    assert [c.channel for c in confirmed.confirmationSentTo] == ["sms"], \
        "it: uses only the channel the customer can receive"

    # describe: business sends email, customer gave none
    fresh_database()
    sent = sent_codes()
    business_id = a_business(slot_mode="unlimited", increment=30)
    set_confirmation_channels(business_id, by_sms=False, by_email=True)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirmed = confirm_session(held.sessionToken,
                                contact={"Phone": "+15552340000"})
    assert confirmed.confirmationSentTo == [], \
        "it: sends nothing when the one channel enabled is one the customer did not give"
    assert sent == [], "it: and nothing reaches the vendor layer"


def test_booking_confirmation_message():
    """What the message says, and what it deliberately leaves out."""
    fresh_database()
    sent = sent_codes()

    business_id = a_business(slot_mode="unlimited", increment=30)
    set_confirmation_channels(business_id, by_sms=True, by_email=False)
    set_business_phone(business_id, "+15559998888")
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})

    # describe: message content
    message = sent[0][1]
    assert held.jobCode in message, "it: carries the job code, which is the credential"
    assert "Lawn Mowing" in message, "it: names the service"
    assert "Monday, July 13" in message, "it: says the day in words"
    assert "10:00 AM" in message, "it: says the time as a customer reads one"
    assert "+15559998888" in message, "it: gives the business phone to call"
    assert "http" not in message and "www." not in message, \
        "it: carries no link — the code is the credential, and a forwarded link is a second one"


def a_job_needing_payment(cost=100.0, deposit_type=None, deposit_amount=None):
    """A confirmed appointment with a price on it."""
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id = create_job_type(business_id, "Lawn Mowing").id
    if deposit_type is not None:
        set_job_type_deposit(job_type_id, deposit_type, deposit_amount)
    size_id = add_job_type_size(business_id, job_type_id, "Standard", 60, cost).id
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
    return business_id, held.jobId


def test_payment():
    """Money against an appointment, and what the total says about it."""
    fresh_database()

    # describe: add cash transaction
    business_id, job_id = a_job_needing_payment(cost=100.0)
    result = record_payment(business_id, job_id, 100.0, "cash")
    assert result.paymentStatus == "fully_paid", \
        "it: paying the cost in full settles it"
    assert [t.amount for t in get_payments(job_id)] == [100.0], \
        "it: and the payment is on the record"
    assert get_payments(job_id)[0].method == "cash", "it: with how it was taken"

    # describe: partial payment
    fresh_database()
    business_id, job_id = a_job_needing_payment(cost=100.0)
    assert record_payment(business_id, job_id, 40.0, "cash").paymentStatus == "unpaid", \
        "it: part of the cost is not the cost"
    assert record_payment(business_id, job_id, 30.0, "cash").paymentStatus == "unpaid", \
        "it: and still is not"
    assert record_payment(business_id, job_id, 30.0, "cash").paymentStatus == "fully_paid", \
        "it: until the payments add up to it"
    assert len(get_payments(job_id)) == 3, "it: each payment is kept, not merged"

    # describe: overpayment
    fresh_database()
    business_id, job_id = a_job_needing_payment(cost=100.0)
    assert record_payment(business_id, job_id, 120.0, "cash").paymentStatus == "fully_paid", \
        "it: paying more than the cost is still paid"


def test_payment_deposit():
    """A deposit settles the appointment without settling the bill."""
    fresh_database()

    # describe: deposit payment, a fixed amount
    business_id, job_id = a_job_needing_payment(cost=100.0, deposit_type="fixed",
                                      deposit_amount=25.0)
    assert record_payment(business_id, job_id, 25.0, "cash").paymentStatus == "deposit_paid", \
        "it: the deposit is taken and the balance is not"
    assert record_payment(business_id, job_id, 75.0, "cash").paymentStatus == "fully_paid", \
        "it: the rest settles it"

    # describe: deposit payment, a percentage
    fresh_database()
    business_id, job_id = a_job_needing_payment(cost=200.0, deposit_type="percent",
                                      deposit_amount=10.0)
    assert record_payment(business_id, job_id, 15.0, "cash").paymentStatus == "unpaid", \
        "it: fifteen is short of ten percent of two hundred"
    assert record_payment(business_id, job_id, 5.0, "cash").paymentStatus == "deposit_paid", \
        "it: twenty in total is the deposit"

    # describe: less than the deposit
    fresh_database()
    business_id, job_id = a_job_needing_payment(cost=100.0, deposit_type="fixed",
                                      deposit_amount=25.0)
    assert record_payment(business_id, job_id, 10.0, "cash").paymentStatus == "unpaid", \
        "it: part of a deposit is not a deposit"


def test_payment_written_off():
    """Work the business decides not to chase."""
    fresh_database()

    business_id, job_id = a_job_needing_payment(cost=100.0)
    record_payment(business_id, job_id, 40.0, "cash")

    # describe: mark written_off
    assert write_off_payment(business_id, job_id).paymentStatus == "written_off", \
        "it: the balance stops being owed"
    assert [t.amount for t in get_payments(job_id)] == [40.0], \
        "it: what was actually taken is left alone"

    # describe: a payment after a write-off
    assert record_payment(business_id, job_id, 60.0, "cash").paymentStatus == "fully_paid", \
        "it: money arriving later settles it after all"


def test_job_lifecycle():
    """An appointment from booked to finished, or not finished."""
    fresh_database()
    sent = sent_codes()

    # describe: cancel job
    business_id, job_id = a_job_needing_payment(cost=100.0)
    assert cancel_appointment(job_id, as_operator=True).status == "cancelled", \
        "it: the business may cancel it"

    # describe: complete job (manual)
    fresh_database()
    sent = sent_codes()
    business_id, job_id = a_job_needing_payment(cost=100.0)
    set_completion_mode(business_id, "manual")
    sent.clear()

    finished = complete_job(business_id, job_id, now=NOW)
    assert finished.status == "completed", "it: the business marks it done"
    assert len(sent) == 1, "it: and the customer is sent a receipt"
    assert "Lawn Mowing" in sent[0][1], "it: naming what was done"

    # describe: admin reschedule
    fresh_database()
    sent = sent_codes()
    business_id, job_id = a_job_needing_payment(cost=100.0)
    sent.clear()

    moved = reschedule_appointment(job_id, TUESDAY, "14:00", as_operator=True,
                                   now=NOW)
    assert moved.scheduledDate == TUESDAY and moved.scheduledTime == "14:00", \
        "it: the appointment moves"
    assert moved.status == "confirmed", "it: and is still a booking"
    assert len(sent) == 1, "it: the customer is told it moved"
    assert TUESDAY in sent[0][1] or "July 14" in sent[0][1], \
        "it: and told when it moved to"


def test_job_auto_complete():
    """Under `auto`, an appointment finishes because the time did.

    A business that never marks anything complete still wants its calendar to
    reflect what happened, and its revenue to count the work it did.
    """
    fresh_database()

    business_id, job_id = a_job_needing_payment(cost=100.0)
    set_completion_mode(business_id, "auto")

    # The appointment is 10:00 for an hour on the Monday.
    during = datetime(2026, 7, 13, 10, 30)
    after = datetime(2026, 7, 13, 11, 1)

    # describe: before the end time
    assert complete_finished_jobs(now=during) == 0, "it: leaves work still under way"
    assert get_appointment(job_id, now=during).status == "confirmed"

    # describe: complete job (auto)
    assert complete_finished_jobs(now=after) == 1, "it: finishes it once the time passes"
    assert get_appointment(job_id, now=after).status == "completed"

    # describe: running again
    assert complete_finished_jobs(now=after) == 0, "it: has nothing left to finish"


def test_job_manual_complete():
    """Under `manual`, only the business says a job is done."""
    fresh_database()

    business_id, job_id = a_job_needing_payment(cost=100.0)
    set_completion_mode(business_id, "manual")

    after = datetime(2026, 7, 13, 11, 1)
    assert complete_finished_jobs(now=after) == 0, \
        "it: the passing of time settles nothing here"
    assert get_appointment(job_id, now=after).status == "confirmed"

    # describe: a cancelled job is never completed
    fresh_database()
    business_id, job_id = a_job_needing_payment(cost=100.0)
    set_completion_mode(business_id, "auto")
    cancel_appointment(job_id, as_operator=True)
    assert complete_finished_jobs(now=after) == 0, \
        "it: a cancelled appointment did not happen, whatever the clock says"

    # describe: marking a cancelled appointment complete by hand
    with pytest.raises(ValidationError):
        complete_job(business_id, job_id, now=after)
    assert get_appointment(job_id, now=after).status == "cancelled", \
        "it: and the business cannot mark one done either"


def test_job_search_date_range():
    """The date range an operator searches by.

    An inverted range is a mistake rather than an empty result: answering
    "nothing found" to a range that cannot contain anything tells the operator
    their data is missing when their dates are backwards.
    """
    fresh_database()

    business_id, job_id = a_job_needing_payment(cost=100.0)

    # describe: from after to
    with pytest.raises(InvalidDateRange):
        search_jobs(business_id, from_date=TUESDAY, to_date=MONDAY)

    # describe: from equal to to
    found = search_jobs(business_id, from_date=MONDAY, to_date=MONDAY)
    assert [j.id for j in found] == [job_id], "it: a single day is a range"

    # describe: only one end given
    assert [j.id for j in search_jobs(business_id, from_date=MONDAY)] == [job_id], \
        "it: an open range with only a start is a range"
    assert [j.id for j in search_jobs(business_id, to_date=TUESDAY)] == [job_id], \
        "it: and so is one with only an end"

    # describe: neither given
    assert [j.id for j in search_jobs(business_id)] == [job_id], \
        "it: no dates means no date constraint"


def test_job_search_filters():
    """Narrowing a search by the things an operator knows."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    mowing_size = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id
    hedging = create_job_type(business_id, "Hedge Trimming").id
    hedging_size = add_job_type_size(business_id, hedging, "Standard", 60, 80.0).id

    monday = create_job_session(business_id, mowing, mowing_size, MONDAY, "10:00")
    confirm_session(monday.sessionToken, contact={"Phone": "+15552340000"})
    tuesday = create_job_session(business_id, hedging, hedging_size, TUESDAY, "10:00")
    confirm_session(tuesday.sessionToken, contact={"Phone": "+15559990000"})
    cancel_appointment(tuesday.jobId, as_operator=True)

    # describe: by date
    assert [j.id for j in search_jobs(business_id, from_date=TUESDAY)] == [tuesday.jobId], \
        "it: finds only what falls in the range"

    # describe: by job type
    assert [j.id for j in search_jobs(business_id, job_type_id=mowing)] == [monday.jobId], \
        "it: finds only the service asked for"

    # describe: by status
    assert [j.id for j in search_jobs(business_id, status="cancelled")] == [tuesday.jobId], \
        "it: finds only appointments in that state"

    # describe: by job code
    assert [j.id for j in search_jobs(business_id, job_code=monday.jobCode)] == [monday.jobId], \
        "it: finds the one a customer read out"

    # describe: another business
    other = a_business(slot_mode="unlimited", increment=30)
    assert search_jobs(other) == [], \
        "it: never reaches across into somebody else's appointments"


def test_financial_report():
    """What a business took over a period, and what it gave up on.

    Revenue is money that actually arrived, not money that was owed: a written
    off job leaves whatever was paid in revenue and the rest in write-offs, so
    the two columns together account for the work.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, job_type_id, "Standard", 60, 100.0).id

    def booked(date, time="10:00"):
        held = create_job_session(business_id, job_type_id, size_id, date, time)
        confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
        return held.jobId

    paid = booked("2026-07-13")
    record_payment(business_id, paid, 100.0, "cash")

    part = booked("2026-08-03")
    record_payment(business_id, part, 40.0, "cash")
    write_off_payment(business_id, part)

    # Owed but not given up on. Without this, a fully-paid job contributes
    # zero to the write-off sum and the filter cannot be told from its absence.
    unpaid = booked("2026-08-10")

    outside = booked("2026-11-02")
    record_payment(business_id, outside, 100.0, "cash")

    # describe: quarterly report
    q3 = get_financial_report(business_id, year=2026, quarter=3)
    assert q3.revenue == 140.0, \
        "it: counts what arrived in the quarter, including on a written-off job"
    assert q3.writeOffs == 60.0, \
        "it: only the balance of jobs actually written off, not everything owed"
    assert q3.jobsCompleted == 0 and q3.jobsCancelled == 0, \
        "it: none of the three was finished or called off"

    # describe: another quarter
    q4 = get_financial_report(business_id, year=2026, quarter=4)
    assert q4.revenue == 100.0, "it: a later quarter counts only its own"

    # describe: a year
    year = get_financial_report(business_id, year=2026)
    assert year.revenue == 240.0, "it: a year is its quarters together"

    # describe: a quarter with nothing in it
    empty = get_financial_report(business_id, year=2025, quarter=1)
    assert empty.revenue == 0.0 and empty.jobsCompleted == 0, \
        "it: reports zero rather than refusing"

    # describe: another business
    other = a_business(slot_mode="unlimited", increment=30)
    assert get_financial_report(other, year=2026).revenue == 0.0, \
        "it: never counts somebody else's money"


def test_financial_report_export():
    """The same figures as a file an accountant can open."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, job_type_id, "Standard", 60, 100.0).id
    held = create_job_session(business_id, job_type_id, size_id, "2026-07-13", "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
    record_payment(business_id, held.jobId, 100.0, "cash")

    # describe: CSV export
    csv = export_financial_report(business_id, year=2026, quarter=3)
    lines = csv.strip().split("\n")
    assert lines[0] == "Job Code,Date,Service,Status,Payment Status,Cost,Paid", \
        "it: names its columns"
    assert len(lines) == 2, "it: one row per appointment"
    assert held.jobCode in lines[1], "it: identified by the code the customer has"
    assert "100.00" in lines[1], "it: with the money on it"

    # describe: a value containing a comma
    comma_type = create_job_type(business_id, "Mowing, Edging and Blowing").id
    comma_size = add_job_type_size(business_id, comma_type, "Standard", 60, 10.0).id
    other = create_job_session(business_id, comma_type, comma_size, "2026-07-14", "10:00")
    confirm_session(other.sessionToken, contact={"Phone": "+15552340000"})

    csv = export_financial_report(business_id, year=2026, quarter=3)
    row = [l for l in csv.strip().split("\n") if other.jobCode in l][0]
    assert '"Mowing, Edging and Blowing"' in row, \
        "it: quotes a value with a comma, so the columns still line up"


def test_employee_availability():
    """Who is available, asked of the employee rather than of a slot.

    The same three facts the kiosk depends on, read directly: the days
    somebody works, the windows they are away, and whether they are in the
    schedule at all.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    # describe: weekly template
    employee_id = an_employee(business_id, job_type_id, days=(1, 3),
                              start="09:00", end="17:00")
    assert is_employee_available(employee_id, MONDAY, "10:00", 60) is True, \
        "it: available on a day they work, inside their hours"
    assert is_employee_available(employee_id, MONDAY, "08:00", 60) is False, \
        "it: not before they start"
    assert is_employee_available(employee_id, MONDAY, "16:30", 60) is False, \
        "it: not when the work would run past when they finish"
    assert is_employee_available(employee_id, TUESDAY, "10:00", 60) is False, \
        "it: not on a day they do not work"

    # describe: time-off window partial day
    add_time_off(business_id, employee_id, MONDAY, "11:00", "13:00")
    assert is_employee_available(employee_id, MONDAY, "09:00", 60) is True, \
        "it: still available before the window"
    assert is_employee_available(employee_id, MONDAY, "10:30", 60) is False, \
        "it: not when the work would run into the window"
    assert is_employee_available(employee_id, MONDAY, "12:00", 60) is False, \
        "it: not inside the window"
    assert is_employee_available(employee_id, MONDAY, "13:00", 60) is True, \
        "it: available again when the window ends"

    # describe: include_in_schedule = false
    fresh_database()
    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    excluded = create_employee(business_id, "Sam", "Doe", include_in_schedule=False)
    allow_job_type(excluded.id, job_type_id)
    add_working_day(business_id, excluded.id, 1, "09:00", "17:00")

    assert is_employee_available(excluded.id, MONDAY, "10:00", 60) is False, \
        "it: somebody out of the schedule is never available"
    assert get_available_slots(business_id, job_type_id, size_id,
                               limit=5, from_date=MONDAY, now=NOW) == [], \
        "it: and offers no times, even though their working days say otherwise"


def test_business_template():
    """Starting a business from a template, rather than from nothing."""
    fresh_database()

    business_id = a_business(increment=30)
    before = get_business(business_id)
    assert before.slotMode == "reserved", "it: starts as an ordinary diary"

    templates = get_business_templates()
    food = [t for t in templates if t.name == "Food & Drink"][0]

    # describe: apply template
    after = apply_business_template(business_id, food.id)
    assert after.slotMode == "unlimited", \
        "it: Food & Drink makes it a queue, which is the whole of what it changes"
    assert after.minBookingNoticeHours == 0, "it: with no notice required"
    assert after.bufferMinutes == 0, "it: and no gap between orders"

    # describe: a template that says nothing about a setting
    field = [t for t in templates if t.name == "Field Service"][0]
    applied = apply_business_template(business_id, field.id)
    assert applied.slotMode == "unlimited", \
        "it: leaves alone what the template has no opinion about"
    assert applied.bufferMinutes == 30, "it: and sets what it does"

    # describe: settings the template is silent about survive
    #
    # Personal Service has an opinion on the increment and on employee
    # selection, and none on the buffer or the cutoff — so a business that set
    # those keeps them.
    set_scheduling(business_id, slot_increment_minutes=30, cutoff_days=45,
                   min_booking_notice_hours=6, buffer_minutes=20)
    personal = [t for t in templates if t.name == "Personal Service"][0]
    kept = apply_business_template(business_id, personal.id)
    assert kept.bufferMinutes == 20, "it: leaves a buffer the template never mentions"
    assert kept.cutoffDays == 45, "it: and a cutoff it never mentions"
    assert kept.minBookingNoticeHours == 6, "it: and a notice it never mentions"
    assert kept.slotIncrementMinutes == 15, "it: while setting the one it does"

    # describe: a template that is not there
    with pytest.raises(ValidationError):
        apply_business_template(business_id, 999)


def test_assign_employees():
    """The customer chooses a time; the server decides who.

    Nothing the client sends names an employee, so a caller cannot book
    somebody who is busy by claiming they are free.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))

    # describe: a time somebody is free for
    assert employees_free_at(business_id, job_type_id, size_id,
                             MONDAY, "10:00", now=NOW) == [employee_id], \
        "it: names whoever availability would have given that slot to"

    # describe: a time nobody is free for
    assert employees_free_at(business_id, job_type_id, size_id,
                             TUESDAY, "10:00", now=NOW) == [], \
        "it: names nobody on a day nobody works"

    # describe: a time already taken
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                              [employee_id])
    confirm_session(held.sessionToken)
    assert employees_free_at(business_id, job_type_id, size_id,
                             MONDAY, "10:00", now=NOW) == [], \
        "it: names nobody once the time is spoken for"

    # describe: an unlimited business
    fresh_database()
    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    assert employees_free_at(business_id, job_type_id, size_id,
                             MONDAY, "10:00", now=NOW) == [], \
        "it: allocates nobody where a time is not a resource"


def test_session_contact_value():
    """Where a verification code should go, without the client saying."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000",
                                                "Email": "someone@example.com"})

    # describe: a kind the customer gave
    assert contact_value_for(held.sessionToken, "phone") == "+15552340000"
    assert contact_value_for(held.sessionToken, "email") == "someone@example.com"

    # describe: a kind they did not
    with pytest.raises(ValidationError):
        contact_value_for(held.sessionToken, "zip")

    # describe: a session that does not exist
    with pytest.raises(SessionExpired):
        contact_value_for("not-a-token", "phone")


def test_kiosk_contact_fields():
    """The kiosk sends the id of the field it rendered, not a name.

    A job type's contact field and the kind of detail it asks for are two
    different ids, and confusing them silently stores the value against the
    wrong kind.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    phone_type = [f for f in get_contact_field_types() if f.name == "Phone"][0]
    field_id = db.insert_job_type_contact_field(job_type_id, phone_type.id)

    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={field_id: "+15552340000"})

    # describe: sending a code to it
    assert contact_value_for(held.sessionToken, "phone") == "+15552340000", \
        "it: stored the value as a phone number, which is what that field asks for"


def test_hold_missing_job_type():
    """A booking against a service that has gone is a refusal, not a crash.

    A kiosk left open while an operator deletes a job type will send exactly
    this, and the customer should be told rather than shown an error page.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)

    # describe: a business that is not there
    with pytest.raises(ValidationError):
        create_job_session(999, job_type_id, size_id, MONDAY, "10:00")

    # describe: a job type that is not there
    with pytest.raises(ValidationError):
        create_job_session(business_id, 999, size_id, MONDAY, "10:00")

    # describe: a size that is not there
    with pytest.raises(ValidationError):
        create_job_session(business_id, job_type_id, 999, MONDAY, "10:00")

    # describe: all of them real
    assert create_job_session(business_id, job_type_id, size_id,
                              MONDAY, "10:00").jobCode, "it: still books"


def test_appointment_detail():
    """Everything `Appointment` draws, from one call.

    The reschedule flow asks the business for its open slots, so the business
    id has to be on the appointment — reading it off a response that never
    carried one is what makes "Change Date/Time" open an empty page.
    """
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                              [employee_id])
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})

    appointment = get_appointment(held.jobId, now=NOW)
    assert appointment.businessId == business_id, \
        "it: names the business, so rescheduling knows whose slots to ask for"
    assert appointment.jobTypeId == job_type_id, "it: and the service"
    assert appointment.sizeId == size_id and appointment.sizeName == "Standard", \
        "it: and which size was chosen"
    assert appointment.cost == 50.0, "it: and what it costs"
    assert appointment.employees == ["Alice K."], \
        "it: names who is coming, given name and an initial"
    assert appointment.locked is False, "it: and is open to the customer"

    # describe: once locked
    start = datetime(2026, 7, 6, 12, 0)
    request_appointment_access(held.jobCode, now=start)
    sent = sent_codes()
    request_appointment_access(held.jobCode, now=start)
    code = sent[0][1]
    for i in range(5):
        with pytest.raises(CodeInvalid):
            verify_appointment_access(held.jobCode, wrong_code(code),
                                      now=start + timedelta(seconds=i + 1))
    with pytest.raises(AppointmentLocked):
        verify_appointment_access(held.jobCode, wrong_code(code),
                                  now=start + timedelta(seconds=6))

    assert get_appointment(held.jobId, now=NOW).locked is True, \
        "it: reports the lock, which is what the screen explains to the customer"


def test_job_type_management():
    """What an operator does to the work they offer."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing")
    hedging = create_job_type(business_id, "Hedge Trimming", min_employees=2)

    # describe: listing them
    listed = get_job_types(business_id)
    assert [j.name for j in listed] == ["Lawn Mowing", "Hedge Trimming"], \
        "it: lists what the business offers"

    # describe: searching by name
    assert [j.name for j in get_job_types(business_id, term="hedge")] == \
        ["Hedge Trimming"], "it: matches on part of a name, whatever the case"

    # describe: another business
    other = a_business(slot_mode="unlimited", increment=30)
    assert get_job_types(other) == [], "it: never lists somebody else's work"

    # describe: a job type starts inactive
    #
    # It exists from the moment the form opens, so it must not reach a customer
    # while it is still being typed. Saving is what turns it on.
    assert mowing.isActive is False, "it: is not offered until it is saved"
    assert get_job_types(business_id, active_only=True) == [], \
        "it: so a customer is offered nothing yet"

    # describe: renaming one
    renamed = update_job_type(business_id, mowing.id, name="Lawn Care", min_employees=2,
                              is_active=True)
    assert renamed.name == "Lawn Care" and renamed.minEmployees == 2
    assert renamed.isActive is True, "it: saving is what makes it available"

    # describe: a name that is blank
    with pytest.raises(ValidationError):
        update_job_type(business_id, mowing.id, name="   ")

    # describe: needing nobody
    with pytest.raises(ValidationError):
        update_job_type(business_id, mowing.id, name="Lawn Care", min_employees=0)

    # describe: retiring one
    update_job_type(business_id, hedging.id, name="Hedge Trimming", is_active=True)
    retired = update_job_type(business_id, hedging.id, name="Hedge Trimming", is_active=False)
    assert retired.isActive is False, "it: stops being offered"
    assert [j.name for j in get_job_types(business_id, active_only=True)] == \
        ["Lawn Care"], "it: and drops out of what a customer may choose"
    assert len(get_job_types(business_id)) == 2, \
        "it: while the operator still sees it"


def test_delete_job_type():
    """Work already booked against a job type keeps it."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    unused = create_job_type(business_id, "Never Booked")
    booked = create_job_type(business_id, "Lawn Mowing")
    size = add_job_type_size(business_id, booked.id, "Standard", 60, 50.0)
    held = create_job_session(business_id, booked.id, size.id, MONDAY, "10:00")
    confirm_session(held.sessionToken)

    # describe: one nothing was booked against
    delete_job_type(business_id, unused.id)
    assert [j.name for j in get_job_types(business_id)] == ["Lawn Mowing"], \
        "it: goes"

    # describe: one with appointments against it
    with pytest.raises(Blocked):
        delete_job_type(business_id, booked.id)
    assert get_appointment(held.jobId, now=NOW).jobTypeName == "Lawn Mowing", \
        "it: stays, because an appointment that names it is still real"


def test_job_type_sizes():
    """The sizes a job type is offered in, which carry its duration and price."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type = create_job_type(business_id, "Lawn Mowing")

    small = add_job_type_size(business_id, job_type.id, "Small", 30, 50.0)
    add_job_type_size(business_id, job_type.id, "Large", 90, 120.0)

    # describe: listing them
    assert [s.name for s in get_job_type_sizes(job_type.id)] == ["Small", "Large"], \
        "it: lists them in the order they were added"

    # describe: changing one
    changed = update_job_type_size(business_id, small.id, "Small", 45, 60.0)
    assert changed.durationMinutes == 45 and changed.cost == 60.0

    # describe: a duration of nothing
    with pytest.raises(ValidationError):
        update_job_type_size(business_id, small.id, "Small", 0, 60.0)

    # describe: a negative price
    with pytest.raises(ValidationError):
        update_job_type_size(business_id, small.id, "Small", 45, -1.0)

    # describe: removing one nothing was booked against
    delete_job_type_size(business_id, small.id)
    assert [s.name for s in get_job_type_sizes(job_type.id)] == ["Large"]

    # describe: removing one an appointment used
    large = get_job_type_sizes(job_type.id)[0]
    held = create_job_session(business_id, job_type.id, large.id, MONDAY, "10:00")
    confirm_session(held.sessionToken)
    with pytest.raises(Blocked):
        delete_job_type_size(business_id, large.id)


def test_employee_management():
    """The people a business schedules work for."""
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    alice = create_employee(business_id, "Alice", "Kim")
    bob = create_employee(business_id, "Bob", "Torres")

    # describe: listing them
    assert [f"{e.firstName} {e.lastName}" for e in get_employees(business_id)] == \
        ["Alice Kim", "Bob Torres"], "it: lists who works here"

    # describe: another business
    other = a_business(increment=30)
    assert get_employees(other) == [], "it: never lists somebody else's staff"

    # describe: changing one
    changed = update_employee(business_id, alice.id, "Alice", "Kim-Smith",
                              include_in_schedule=False,
                              can_manage_own_schedule=True)
    assert changed.lastName == "Kim-Smith"
    assert changed.includeInSchedule is False, "it: can be taken out of the schedule"
    assert changed.canManageOwnSchedule is True, "it: and given their own diary"

    # describe: a name that is blank
    with pytest.raises(ValidationError):
        update_employee(business_id, alice.id, "", "Kim")

    # describe: which work they can do
    allow_job_type(bob.id, job_type_id)
    assert [j.name for j in get_employee_job_types(business_id, bob.id)] == ["Lawn Mowing"], \
        "it: says what they are allowed to be given"
    set_employee_job_types(business_id, bob.id, [])
    assert get_employee_job_types(business_id, bob.id) == [], "it: and can be cleared"


def test_delete_employee():
    """Somebody who has been assigned work keeps it."""
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    spare = create_employee(business_id, "Never", "Booked")
    working = an_employee(business_id, job_type_id, days=(1,))

    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00",
                              [working])
    confirm_session(held.sessionToken)

    # describe: one who has never been assigned anything
    delete_employee(business_id, spare.id)
    assert [e.id for e in get_employees(business_id)] == [working], "it: goes"

    # describe: one with work against them
    with pytest.raises(Blocked):
        delete_employee(business_id, working)
    assert get_appointment(held.jobId, now=NOW).employees == ["Alice K."], \
        "it: stays, because an appointment names them"


def test_employee_schedule():
    """When somebody works, and when they are away."""
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    employee_id = an_employee(business_id, job_type_id, days=(1,))

    # describe: a working day
    days = get_working_days(business_id, employee_id)
    assert [(d.dayOfWeek, d.startTime, d.endTime) for d in days] == \
        [(1, "09:00", "17:00")], "it: lists the days they work"

    # describe: changing one
    changed = update_working_day(business_id, days[0].id, 2, "08:00", "12:00")
    assert (changed.dayOfWeek, changed.startTime, changed.endTime) == \
        (2, "08:00", "12:00")

    # describe: a day that ends before it starts
    with pytest.raises(ValidationError):
        update_working_day(business_id, days[0].id, 2, "12:00", "08:00")

    # describe: a day outside the week
    with pytest.raises(ValidationError):
        update_working_day(business_id, days[0].id, 7, "08:00", "12:00")

    # describe: removing one
    delete_working_day(business_id, days[0].id)
    assert get_working_days(business_id, employee_id) == [], "it: goes"

    # describe: time off
    window = add_time_off(business_id, employee_id, MONDAY, "11:00", "13:00")
    assert [w.date for w in get_time_off(business_id, employee_id)] == [MONDAY], \
        "it: lists when they are away"

    # describe: a window that ends before it starts
    with pytest.raises(ValidationError):
        update_time_off(business_id, window.id, MONDAY, "13:00", "11:00")

    # describe: changing one
    moved = update_time_off(business_id, window.id, TUESDAY, "09:00", "10:00")
    assert (moved.date, moved.startTime) == (TUESDAY, "09:00")

    # describe: removing one
    delete_time_off(business_id, window.id)
    assert get_time_off(business_id, employee_id) == [], "it: goes"


def test_add_working_day():
    """Adding a day, and the ways it can be wrong.

    It returns the day it added rather than the list: the list is ordered by
    weekday, so the newest is not the last, and a caller that took the last
    would report a different day than it created.
    """
    fresh_database()

    business_id = a_business(increment=30)
    employee = create_employee(business_id, "Alice", "Kim")
    add_working_day(business_id, employee.id, 5, "09:00", "17:00")

    # describe: a day earlier in the week than one already there
    added = add_working_day(business_id, employee.id, 1, "08:00", "12:00")
    assert (added.dayOfWeek, added.startTime) == (1, "08:00"), \
        "it: returns the day just added, not whichever sorts last"

    # describe: a day that ends before it starts
    with pytest.raises(ValidationError):
        add_working_day(business_id, employee.id, 2, "17:00", "09:00")

    # describe: a day outside the week
    with pytest.raises(ValidationError):
        add_working_day(business_id, employee.id, 9, "09:00", "17:00")

    # describe: an employee who is not there
    with pytest.raises(ValidationError):
        add_working_day(business_id, 999, 1, "09:00", "17:00")


def test_business_readiness():
    """What is still stopping customers from booking.

    Computed on every call rather than kept in a column: a rule added here
    takes effect everywhere at once, and there is no flag that can fall out of
    step with the thing it describes.
    """
    fresh_database()

    # describe: a brand new business
    business_id = db.insert_business("", "UTC", "reserved")
    setup = get_setup(business_id)
    assert setup.configured is False, "it: cannot take a booking yet"
    outstanding = [t.text for t in setup.tasks if not t.done]
    assert any("name" in t.lower() for t in outstanding), \
        "it: asks for a business name"

    # describe: naming it
    named_business = update_business_config(business_id, {"name": "Green Thumb"})
    assert named_business.name == "Green Thumb"
    named = get_setup(business_id)
    assert [t.done for t in named.tasks if "name" in t.text.lower()] == [True], \
        "it: ticks off the name"
    assert named.configured is False, "it: still needs work to offer"

    # describe: what a task points at
    name_task = [t for t in named.tasks if "name" in t.text.lower()][0]
    assert name_task.controller == "BusinessConfig", "it: names the window"
    assert name_task.section == "general", "it: and the page of it"


def test_business_readiness_reserved():
    """A reserved business needs somebody to do the work."""
    fresh_database()

    # Deliberately without operating hours: a reserved business never asks for
    # them, because the employees' schedules are what bound the day.
    business_id = db.insert_business("Green Thumb", "UTC", "reserved")

    def outstanding():
        return [t.text for t in get_setup(business_id).tasks if not t.done]

    def texts():
        return [t.text for t in get_setup(business_id).tasks]

    assert not any("hours" in t.lower() for t in texts()), \
        "it: never asks a reserved business when it is open"

    assert any("job type" in t.lower() or "service" in t.lower()
               for t in outstanding()), "it: asks for something to offer"

    job_type = create_job_type(business_id, "Lawn Mowing")
    update_job_type(business_id, job_type.id, "Lawn Mowing", is_active=True)
    assert any("size" in t.lower() for t in outstanding()), \
        "it: asks for a size, which carries the duration and the price"

    add_job_type_size(business_id, job_type.id, "Standard", 60, 50.0)
    assert any("contact" in t.lower() for t in outstanding()), \
        "it: asks how to reach the customer"

    phone = [f for f in get_contact_field_types() if f.name == "Phone"][0]
    db.insert_job_type_contact_field(job_type.id, phone.id)
    assert any(t.startswith("No employee can perform") for t in outstanding()), \
        "it: asks for somebody who can do it, because availability comes from them"

    employee = create_employee(business_id, "Alice", "Kim")
    allow_job_type(employee.id, job_type.id)
    assert not any(t.startswith("No employee can perform") for t in outstanding()), \
        "it: stops asking once somebody can perform it"
    assert any(t.startswith("Give an employee working days") for t in outstanding()), \
        "it: and asks for the days they work, because nobody working means no slots"

    add_working_day(business_id, employee.id, 1, "09:00", "17:00")
    assert get_setup(business_id).configured is True, \
        "it: is ready once somebody can be booked"

    # describe: a retired job type asks for nothing
    #
    # It is not offered, so what it lacks cannot stop a customer booking. A
    # half-finished job type nobody activated would otherwise hold the whole
    # business open forever.
    create_job_type(business_id, "Hedge Trimming")
    assert get_setup(business_id).configured is True, \
        "it: an inactive job type adds no tasks"
    assert not any("Hedge" in t for t in texts()), \
        "it: and is not mentioned at all"


def test_business_readiness_unlimited():
    """An unlimited business needs opening hours, and nobody at all."""
    fresh_database()

    business_id = db.insert_business("Corner Cafe", "UTC", "unlimited")
    job_type = create_job_type(business_id, "Coffee")
    update_job_type(business_id, job_type.id, "Coffee", is_active=True)
    add_job_type_size(business_id, job_type.id, "Regular", 15, 3.5)
    phone = [f for f in get_contact_field_types() if f.name == "Phone"][0]
    db.insert_job_type_contact_field(job_type.id, phone.id)

    def outstanding():
        return [t.text for t in get_setup(business_id).tasks if not t.done]

    # describe: no hours yet
    assert any("open" in t.lower() or "hours" in t.lower() for t in outstanding()), \
        "it: asks when the business is open, which is what bounds the day"
    assert not any("employee" in t.lower() for t in outstanding()), \
        "it: never asks for employees, because nobody is allocated"

    # describe: opening on one day
    set_operating_hours(business_id, 1, "08:00", "16:00")
    assert get_setup(business_id).configured is True, \
        "it: is ready with one open day and nobody employed"


def test_business_config():
    """Everything the owner sets on the Business Settings window."""
    fresh_database()

    business_id = a_business(increment=30)

    # describe: reading it back before anything is filled in
    config = get_business_config(business_id)
    assert config.name != "", "it: always has the name the business was created with"
    assert config.city == "", "it: and blanks for what nobody has entered"
    assert config.publicUrl.endswith(f"/{business_id}"), \
        "it: carries the address a customer books at, which is read-only"

    # describe: filling it in
    saved = update_business_config(business_id, {
        "name": "Green Thumb Landscaping",
        "phone": "(555) 867-5309",
        "addressLine1": "456 Garden Blvd",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "ownerName": "Maria Garcia",
        "description": "Lawns, hedges, and leaf removal.",
        "siteUrl": "https://greenthumb.example.com",
        "timezone": "America/Chicago",
        "slotIncrementMinutes": 15,
        "cutoffDays": 45,
        "minBookingNoticeHours": 24,
        "minChangeNoticeMinutes": 90,
        "bufferMinutes": 15,
        "slotMode": "unlimited",
        "reminderEnabled": False,
        "confirmBySms": True,
        "confirmByEmail": True,
        "completionMode": "manual",
        "allowCustomerEmployeeSelection": True,
        "notifyEmployees": True,
    })
    assert saved.city == "Springfield", "it: keeps what was written"
    assert saved.cutoffDays == 45, "it: including how far ahead a customer may book"
    assert saved.slotMode == "unlimited", "it: and whether a time is taken when chosen"
    assert saved.confirmBySms and saved.confirmByEmail, \
        "it: both confirmation channels, either, or neither"
    assert saved.completionMode == "manual"
    assert saved.notifyEmployees is True

    # Read through a second call rather than trusting the one that wrote it —
    # a column written to the wrong field looks right until it is fetched.
    again = get_business_config(business_id)
    assert again.model_dump() == saved.model_dump(), \
        "it: reads back exactly what was saved"

    # describe: changing one field
    update_business_config(business_id, {"city": "Chicago"})
    after = get_business_config(business_id)
    assert after.city == "Chicago", "it: takes the change"
    assert after.zip == "62701", "it: and leaves every field it was not given"

    # describe: a blank business name
    with pytest.raises(ValidationError):
        update_business_config(business_id, {"name": "   "})
    assert get_business_config(business_id).name == "Green Thumb Landscaping", \
        "it: keeps the name it had"

    # The window writes as the owner works, so a refused name must not take the
    # rest of the form down with it — an owner who fills in a phone before
    # reaching the name would lose the phone.
    with pytest.raises(ValidationError):
        update_business_config(business_id, {"name": "", "phone": "(555) 111-2222"})
    assert get_business_config(business_id).phone == "(555) 111-2222", \
        "it: still saves every other field in the same write"

    # describe: a field the settings window does not have
    with pytest.raises(ValidationError):
        update_business_config(business_id, {"isActive": False})
    assert get_business_config(business_id).name == "Green Thumb Landscaping", \
        "it: refuses the whole write rather than guessing at a column"


def test_business_config_operating_hours():
    """The seven days sit on the config, and come back in weekday order."""
    fresh_database()

    # Not `a_business`, which opens all seven days — the point here is which
    # days came back and in what order.
    business_id = create_business("Test Business", "UTC", "reserved").id
    set_operating_hours(business_id, 1, "08:00", "18:00")
    set_operating_hours(business_id, 0, "09:00", "17:00", is_closed=True)

    hours = get_business_config(business_id).operatingHours
    assert [h.dayOfWeek for h in hours] == [0, 1], "it: reads Sunday first"
    assert hours[0].isClosed is True, "it: says which days the doors do not open"
    assert hours[1].openTime == "08:00"


def test_business_holidays():
    """Which of the year's holidays a business closes on."""
    fresh_database()

    business_id = a_business(increment=30)

    # The system's dates, which a business chooses from rather than inventing.
    new_year = db.insert_system_holiday("US", "US", "New Year's Day", "2026-01-01", 2026)
    july4 = db.insert_system_holiday("US", "US", "Independence Day", "2026-07-04", 2026)
    christmas = db.insert_system_holiday("US", "US", "Christmas Day", "2026-12-25", 2026)
    next_year = db.insert_system_holiday("US", "US", "New Year's Day", "2027-01-01", 2027)

    # describe: before any are chosen
    listed = get_business_holidays(business_id, 2026)
    assert [h.name for h in listed] == \
        ["New Year's Day", "Independence Day", "Christmas Day"], \
        "it: offers the year's holidays in date order"
    assert not any(h.selected for h in listed), "it: with none observed yet"

    # describe: choosing some
    after = set_business_holidays(business_id, 2026, [new_year, christmas])
    assert [h.name for h in after if h.selected] == \
        ["New Year's Day", "Christmas Day"], "it: closes on the ones chosen"
    assert lib.db.is_holiday(business_id, "2026-01-01") is True, \
        "it: and the day is closed for booking"
    assert lib.db.is_holiday(business_id, "2026-07-04") is False, \
        "it: while an unchosen one stays open"

    # describe: changing the choice
    after = set_business_holidays(business_id, 2026, [july4])
    assert [h.name for h in after if h.selected] == ["Independence Day"], \
        "it: replaces the year's choice rather than adding to it"
    assert lib.db.is_holiday(business_id, "2026-01-01") is False, \
        "it: so one taken off the list re-opens"

    # describe: the same holiday twice in one save
    set_business_holidays(business_id, 2026, [july4, july4])
    # Read through `db`: one closed day looks identical either way, and the
    # duplicate row is the whole of what would be wrong. No `lib` call shows it.
    assert db.get_observed_holiday_ids(business_id, 2026) == [july4], \
        "it: is observed once, not twice"

    # describe: another year
    set_business_holidays(business_id, 2027, [next_year])
    assert [h.name for h in get_business_holidays(business_id, 2026) if h.selected] == \
        ["Independence Day"], "it: leaves the other years alone"

    # describe: a holiday that belongs to a different year
    with pytest.raises(ValidationError):
        set_business_holidays(business_id, 2026, [next_year])

    # describe: a holiday that does not exist
    with pytest.raises(ValidationError):
        set_business_holidays(business_id, 2026, [9999])

    # describe: closing on nothing
    assert [h for h in set_business_holidays(business_id, 2026, []) if h.selected] == [], \
        "it: can observe none of them"


def test_customers():
    """The people a business has served."""
    fresh_database()

    business_id = a_business(increment=30)
    jane = create_customer(business_id, "Jane", "Doe",
                           phone="(555) 234-5678", email="jane@example.com")
    create_customer(business_id, "John", "Smith", phone="(555) 345-6789")

    # describe: listing them
    assert [f"{c.firstName} {c.lastName}" for c in get_customers(business_id)] == \
        ["Jane Doe", "John Smith"], "it: lists who has been served"

    # describe: another business
    other = a_business(increment=30)
    assert get_customers(other) == [], "it: never lists somebody else's customers"

    # describe: searching as the operator types
    assert [c.lastName for c in get_customers(business_id, "smi")] == ["Smith"], \
        "it: finds them by name, whatever the case"
    assert [c.firstName for c in get_customers(business_id, "234")] == ["Jane"], \
        "it: and by any part of the phone number"
    assert get_customers(business_id, "zzz") == [], "it: or finds nobody"

    # describe: one of them
    detail = get_customer(business_id, jane.id)
    assert detail.email == "jane@example.com"
    assert detail.hasBossAccount is False, \
        "it: says whether a BOSS account owns this contact information"

    # describe: changing their details
    changed = update_customer(business_id, jane.id, {"city": "Springfield", "zip": "62701"})
    assert changed.city == "Springfield"
    assert changed.phone == "(555) 234-5678", "it: leaves what it was not given"

    # describe: a name that is blank
    with pytest.raises(ValidationError):
        update_customer(business_id, jane.id, {"firstName": "  "})

    # describe: a detail the customer form does not have
    with pytest.raises(ValidationError):
        update_customer(business_id, jane.id, {"hasBossAccount": True})
    assert get_customer(business_id, jane.id).hasBossAccount is False, \
        "it: refuses the whole write rather than guessing at a column"

    # describe: somebody who is not there
    with pytest.raises(ValidationError):
        update_customer(business_id, 9999, {"city": "Nowhere"})


def test_customer_boss_account():
    """Contact details a BOSS account owns are not the operator's to edit."""
    fresh_database()

    business_id = a_business(increment=30)
    linked = create_customer(business_id, "Ada", "Lovelace",
                             phone="(555) 111-0000", user_id=42)

    assert get_customer(business_id, linked.id).hasBossAccount is True

    # describe: the operator editing them
    with pytest.raises(ValidationError):
        update_customer(business_id, linked.id, {"phone": "(555) 999-9999"})
    assert get_customer(business_id, linked.id).phone == "(555) 111-0000", \
        "it: keeps what the account holder set"


def test_customer_notes():
    """What an operator writes down about a customer."""
    fresh_database()

    business_id = a_business(increment=30)
    jane = create_customer(business_id, "Jane", "Doe", phone="(555) 234-5678")
    john = create_customer(business_id, "John", "Smith")

    # describe: writing one
    note = add_customer_note(business_id, jane.id, "Prefers morning appointments.", user_id=7)
    assert note.note == "Prefers morning appointments."
    assert note.date != "", "it: is dated, so the list reads in order"
    assert [n.id for n in get_customer(business_id, jane.id).notes] == [note.id], \
        "it: shows on the customer it was written about"
    assert get_customer(business_id, john.id).notes == [], "it: and on nobody else"

    # describe: a note with nothing in it
    with pytest.raises(ValidationError):
        add_customer_note(business_id, jane.id, "   ", user_id=7)

    # describe: changing one
    changed = update_customer_note(
        business_id, jane.id, note.id, "Prefers afternoons now.")
    assert changed.note == "Prefers afternoons now."
    assert get_customer(business_id, jane.id).notes[0].note == "Prefers afternoons now."

    # describe: emptying one
    with pytest.raises(ValidationError):
        update_customer_note(business_id, jane.id, note.id, "")

    # describe: another customer's note
    with pytest.raises(ValidationError):
        update_customer_note(business_id, john.id, note.id, "Not mine to edit.")
    with pytest.raises(ValidationError):
        delete_customer_note(business_id, john.id, note.id)

    # describe: the same note through another business
    other_id = a_business(increment=31)
    with pytest.raises(ValidationError):
        update_customer_note(other_id, jane.id, note.id, "Not mine to edit.")
    with pytest.raises(ValidationError):
        delete_customer_note(other_id, jane.id, note.id)
    assert get_customer(business_id, jane.id).notes[0].note == "Prefers afternoons now.", \
        "it: is left as this business's operator wrote it"

    # describe: removing one
    delete_customer_note(business_id, jane.id, note.id)
    assert get_customer(business_id, jane.id).notes == [], "it: is gone"
    with pytest.raises(ValidationError):
        delete_customer_note(business_id, jane.id, note.id)


def test_customer_appointment_history():
    """Every booking that customer holds, newest first."""
    fresh_database()

    business_id = a_business(increment=30)
    job_type_id, size_id = a_job_type(business_id, duration=60)
    an_employee(business_id, job_type_id)
    jane = create_customer(business_id, "Jane", "Doe", phone="(555) 234-5678")

    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "09:00",
                              now=NOW)
    confirm_session(held.sessionToken, now=NOW)
    link_job_to_customer(held.jobId, jane.id)

    history = get_customer(business_id, jane.id).appointments
    assert len(history) == 1, "it: carries the booking"
    assert history[0].jobType == "Lawn Mowing"
    assert history[0].scheduledDate == MONDAY
    assert history[0].displayTime == "9:00 AM", "it: as the screen spells it"
    assert history[0].status == "confirmed"


def test_job_search_by_customer():
    """The operator searches by the customer in front of them, or on the phone."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id
    alice = an_employee(business_id, mowing)

    jane = create_job_session(business_id, mowing, size, MONDAY, "10:00",
                              employee_ids=[alice])
    confirm_session(jane.sessionToken, contact={
        "First Name": "Jane", "Last Name": "Doe", "Phone": "(555) 234-5678"})
    john = create_job_session(business_id, mowing, size, TUESDAY, "10:00")
    confirm_session(john.sessionToken, contact={
        "First Name": "John", "Last Name": "Smith", "Phone": "(555) 345-6789"})

    # describe: the row the screen draws
    row = [j for j in search_jobs(business_id) if j.id == jane.jobId][0]
    assert row.customerName == "Jane Doe", "it: names who the work is for"
    assert row.jobType == "Lawn Mowing"
    assert [f"{e.firstName} {e.lastInitial}" for e in row.employees] == ["Alice K"], \
        "it: and who is doing it, by first name and an initial"

    # describe: by name
    assert [j.id for j in search_jobs(business_id, name="doe")] == [jane.jobId], \
        "it: finds them by any part of the name, whatever the case"
    assert [j.id for j in search_jobs(business_id, name="jane doe")] == [jane.jobId], \
        "it: including the whole of it"

    # describe: by phone
    assert [j.id for j in search_jobs(business_id, phone="345-6789")] == [john.jobId], \
        "it: finds them by any part of the number"

    # describe: by who is doing the work
    assert [j.id for j in search_jobs(business_id, employee_id=alice)] == [jane.jobId], \
        "it: finds only what that employee was given"

    # describe: nobody by that name
    assert search_jobs(business_id, name="nobody") == [], "it: or finds nothing"

    # describe: a job nobody was assigned to
    unassigned = [j for j in search_jobs(business_id) if j.id == john.jobId][0]
    assert unassigned.employees == [], "it: says nobody, rather than leaving it out"


def test_operator_job_view():
    """What the Job window shows, which is more than the customer is shown."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Medium", 60, 80.0).id
    attribute = add_job_type_attribute(business_id, mowing, "Property Size (sq ft)", "number")
    alice = an_employee(business_id, mowing)
    jane = create_customer(business_id, "Jane", "Doe",
                           phone="(555) 234-5678", email="jane@example.com")

    held = create_job_session(business_id, mowing, size_id, MONDAY, "09:00",
                              employee_ids=[alice])
    confirm_session(held.sessionToken,
                    contact={"First Name": "Jane", "Last Name": "Doe",
                             "Phone": "+15552340000"},
                    attributes={attribute.id: 2500})
    link_job_to_customer(held.jobId, jane.id)
    record_payment(business_id, held.jobId, 40.0, "cash")

    job = get_job_detail(business_id, held.jobId)

    # describe: the appointment itself
    assert job.jobCode == held.jobCode
    assert job.jobType.name == "Lawn Mowing"
    assert job.size.name == "Medium", "it: says which size was booked"
    assert job.size.cost == 80.0, "it: and what that size costs"
    assert job.durationMinutes == 60
    assert job.status == "confirmed"
    # Half the cost, but the job type asks for no deposit — so there is no
    # threshold this clears, and part-paid is not a state the screen has.
    assert job.paymentStatus == "unpaid", \
        "it: says how much of it has been paid for"
    assert job.isRecurring is False

    # describe: who is involved
    assert [e.firstName for e in job.employees] == ["Alice"], \
        "it: names the whole crew, not an initial — the operator manages them"
    assert job.customer.id == jane.id
    assert job.customer.email == "jane@example.com"

    # describe: what the customer answered
    assert [(a.name, a.value) for a in job.attributes] == \
        [("Property Size (sq ft)", "2500")], "it: carries the job type's questions"

    # describe: what has been taken
    assert [t.amount for t in job.transactions] == [40.0]

    # describe: the lock the operator gets called about
    assert job.locked is False
    assert job.failedCodeAttempts == 0, \
        "it: counts the wrong codes somebody has tried"

    # The operator is called about this: somebody cannot get in, and the count
    # is what tells them whether it is a forgetful customer or somebody else.
    sent = sent_codes()
    start = datetime(2026, 7, 6, 12, 0)
    request_appointment_access(held.jobCode, now=start)
    for i in range(2):
        with pytest.raises(CodeInvalid):
            verify_appointment_access(held.jobCode, wrong_code(sent[0][1]),
                                      now=start + timedelta(seconds=i + 1))
    assert get_job_detail(business_id, held.jobId).failedCodeAttempts == 2, \
        "it: counts every one of them"

    # describe: a job that is not there
    assert get_job_detail(business_id, 9999) is None


def test_operator_job_view_no_customer():
    """A booking gets its customer record when it is confirmed, not before.

    A held time is a job already — pending, unfinalised, and nobody's yet. The
    operator can still open it, and what it shows is whatever has been typed
    so far, which at that point is nothing.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id

    held = create_job_session(business_id, mowing, size_id, MONDAY, "09:00")

    job = get_job_detail(business_id, held.jobId)
    assert job.status == "pending", "it: is a held time, not a booking"
    assert job.customer.id == 0, "it: has no customer record behind it"
    assert job.customer.firstName == "", "it: and nothing has been typed yet"
    assert job.employees == [], "it: with nobody assigned"

    # describe: the customer finishing
    confirm_session(held.sessionToken, contact={
        "First Name": "Sam", "Last Name": "Reyes", "Phone": "(555) 777-1234"})
    job = get_job_detail(business_id, held.jobId)
    assert job.customer.id != 0, "it: is somebody the business has served now"
    assert job.customer.firstName == "Sam"
    assert job.customer.phone == "(555) 777-1234"


def test_job_type_attributes():
    """The questions a job type asks the customer at booking."""
    fresh_database()

    business_id = a_business(increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id

    # describe: adding one
    size = add_job_type_attribute(business_id, mowing, "Property Size (sq ft)", "number")
    assert size.sortOrder == 0, "it: is the first question asked"
    gate = add_job_type_attribute(business_id, mowing, "Gate Code", "text", is_required=True)
    assert gate.sortOrder == 1, "it: and the next goes after it"
    assert gate.isRequired is True

    # describe: one that offers a choice
    surface = add_job_type_attribute(business_id, mowing, "Surface", "dropdown",
                                     options=["Grass", "Gravel"])
    assert surface.options == ["Grass", "Gravel"], "it: keeps the choices offered"

    # describe: listing them
    assert [a.name for a in get_job_type_attributes(mowing)] == \
        ["Property Size (sq ft)", "Gate Code", "Surface"], \
        "it: reads in the order they are asked"

    # describe: a name that is blank
    with pytest.raises(ValidationError):
        add_job_type_attribute(business_id, mowing, "  ", "text")

    # describe: a kind of question that does not exist
    with pytest.raises(ValidationError):
        add_job_type_attribute(business_id, mowing, "Colour", "colour-picker")

    # describe: a dropdown with nothing to choose from
    with pytest.raises(ValidationError):
        add_job_type_attribute(business_id, mowing, "Surface", "dropdown", options=[])

    # describe: changing one
    changed = update_job_type_attribute(business_id, surface.id, "Surface Type", "dropdown",
                                        options=["Grass"], is_required=True)
    assert changed.name == "Surface Type"
    assert changed.options == ["Grass"]
    assert changed.isRequired is True

    # describe: removing one
    delete_job_type_attribute(business_id, gate.id)
    assert [a.name for a in get_job_type_attributes(mowing)] == \
        ["Property Size (sq ft)", "Surface Type"], "it: is no longer asked"

    # describe: one that is not there
    with pytest.raises(ValidationError):
        update_job_type_attribute(business_id, 9999, "Anything", "text")
    with pytest.raises(ValidationError):
        delete_job_type_attribute(business_id, 9999)


def a_booking_for(business_id, job_type_id, size_id, date, time, contact):
    """A confirmed booking made the way a customer at the kiosk makes one."""
    held = create_job_session(business_id, job_type_id, size_id, date, time)
    confirm_session(held.sessionToken, contact=contact)
    return held


def test_booking_matches_customer():
    """An anonymous booking attaches itself to the record it matches."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id

    # describe: the first booking anyone makes
    first = a_booking_for(business_id, mowing, size_id, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe",
        "Email": "jane@example.com", "Phone": "(555) 234-5678"})
    jane = get_job_detail(business_id, first.jobId).customer
    assert jane.id != 0, "it: is recorded as a customer of this business"
    assert jane.firstName == "Jane"
    assert [c.id for c in get_customers(business_id)] == [jane.id], \
        "it: and shows on the Customers screen"

    # describe: the same person booking again
    second = a_booking_for(business_id, mowing, size_id, TUESDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    assert get_job_detail(business_id, second.jobId).customer.id == jane.id, \
        "it: is the same customer, not a second record"
    assert len(get_customers(business_id)) == 1
    assert len(get_customer(business_id, jane.id).appointments) == 2, \
        "it: so both bookings sit in one history"

    # describe: the same address, spelled differently
    third = a_booking_for(business_id, mowing, size_id, MONDAY, "11:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "JANE@Example.com"})
    assert get_job_detail(business_id, third.jobId).customer.id == jane.id, \
        "it: matches an email whatever its case"

    # describe: somebody else entirely
    other = a_booking_for(business_id, mowing, size_id, MONDAY, "13:00", {
        "First Name": "John", "Last Name": "Smith", "Email": "john@example.com"})
    assert get_job_detail(business_id, other.jobId).customer.id != jane.id, \
        "it: is a different person, and a different record"
    assert len(get_customers(business_id)) == 2

    # describe: another business serving the same person
    elsewhere = a_business(slot_mode="unlimited", increment=30)
    hedging = create_job_type(elsewhere, "Hedge Trimming").id
    hedging_size = add_job_type_size(elsewhere, hedging, "Standard", 60, 80.0).id
    away = a_booking_for(elsewhere, hedging, hedging_size, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    assert get_job_detail(elsewhere, away.jobId).customer.id != jane.id, \
        "it: keeps its own record — one business is not told who another serves"


def test_booking_matches_phone():
    """Email is the surer match, so it is tried first. Phone is the fallback."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id

    first = a_booking_for(business_id, mowing, size_id, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Phone": "(555) 234-5678"})
    jane = get_job_detail(business_id, first.jobId).customer.id

    # describe: booking again with the number written another way
    again = a_booking_for(business_id, mowing, size_id, TUESDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Phone": "+1 555 234 5678"})
    assert get_job_detail(business_id, again.jobId).customer.id == jane, \
        "it: matches on the digits, not on how they were typed"

    # describe: a booking that gives an email the record does not have
    with_email = a_booking_for(business_id, mowing, size_id, MONDAY, "11:00", {
        "First Name": "Jane", "Last Name": "Doe",
        "Phone": "(555) 234-5678", "Email": "jane@example.com"})
    assert get_job_detail(business_id, with_email.jobId).customer.id == jane, \
        "it: still matches on the phone"
    assert get_customer(business_id, jane).email == "jane@example.com", \
        "it: and fills in the address the record was missing"

    # describe: a booking whose email belongs to somebody else
    conflict = a_booking_for(business_id, mowing, size_id, MONDAY, "13:00", {
        "First Name": "Someone", "Last Name": "Else",
        "Phone": "(555) 234-5678", "Email": "someone@example.com"})
    assert get_job_detail(business_id, conflict.jobId).customer.id != jane, \
        "it: an email nobody holds is a different person, whatever the phone says"
    assert get_customer(business_id, jane).email == "jane@example.com", \
        "it: and the record keeps the address it had"

    # describe: a booking that gives details the record already has, differently
    update_customer(business_id, jane, {"phone": "(555) 234-5678"})
    a_booking_for(business_id, mowing, size_id, TUESDAY, "13:00", {
        "First Name": "Jane", "Last Name": "Doe",
        "Phone": "555.234.5678", "Email": "jane@example.com"})
    assert get_customer(business_id, jane).phone == "(555) 234-5678", \
        "it: leaves the record spelling it the way the operator wrote it"

    # describe: a booking with neither
    anonymous = a_booking_for(business_id, mowing, size_id, TUESDAY, "11:00", {
        "First Name": "Nobody", "Last Name": "Known"})
    assert get_job_detail(business_id, anonymous.jobId).customer.id != 0, \
        "it: is still recorded — the operator needs somebody to call it"
    assert get_job_detail(business_id, anonymous.jobId).customer.firstName == "Nobody"


def test_claim_prior_bookings():
    """An email is one person across all of BOSS, so the account claims them."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id
    elsewhere = a_business(slot_mode="unlimited", increment=30)
    hedging = create_job_type(elsewhere, "Hedge Trimming").id
    hedging_size = add_job_type_size(elsewhere, hedging, "Standard", 60, 80.0).id

    # describe: booking anonymously, at two businesses, long before signing up
    here = a_booking_for(business_id, mowing, size_id, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    there = a_booking_for(elsewhere, hedging, hedging_size, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    assert get_job_detail(business_id, here.jobId).customer.id != 0
    assert get_customer(business_id, get_job_detail(business_id, here.jobId).customer.id).hasBossAccount is False

    # describe: signing up for BOSS with that address
    claimed = reconcile_boss_user(42, "jane@example.com")
    assert claimed == 2, "it: claims the record at every business she booked at"
    assert get_customer(business_id, get_job_detail(business_id, here.jobId).customer.id).hasBossAccount is True
    assert get_customer(elsewhere, get_job_detail(elsewhere, there.jobId).customer.id).hasBossAccount is True

    # The operator may no longer edit her details, which is the point of the
    # link — she maintains them herself now.
    with pytest.raises(ValidationError):
        update_customer(business_id, get_job_detail(business_id, here.jobId).customer.id, {"city": "Nowhere"})

    # describe: a different address
    assert reconcile_boss_user(43, "nobody@example.com") == 0, \
        "it: claims nothing when nobody booked under it"

    # describe: no address at all
    with pytest.raises(ValidationError):
        reconcile_boss_user(44, "   ")

    # describe: signing up, then booking
    after = a_booking_for(business_id, mowing, size_id, TUESDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    assert get_job_detail(business_id, after.jobId).customer.id == \
        get_job_detail(business_id, here.jobId).customer.id, \
        "it: still finds the record, which is hers now"


def test_signed_in_customer_identity():
    """A booking made while signed in attaches to the account, not to a guess."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id

    # describe: booking while signed in
    held = create_job_session(business_id, mowing, size_id, MONDAY, "09:00")
    confirm_session(held.sessionToken, user_id=42, contact={
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    jane = get_job_detail(business_id, held.jobId).customer.id
    assert get_customer(business_id, jane).hasBossAccount is True, \
        "it: is recorded as the account holder, with no email matching needed"

    # describe: booking again, giving nothing the first booking gave
    again = create_job_session(business_id, mowing, size_id, TUESDAY, "09:00")
    confirm_session(again.sessionToken, user_id=42, contact={})
    assert get_job_detail(business_id, again.jobId).customer.id == jane, \
        "it: is the same customer — the account says so, not the contact fields"

    # describe: a job type that never asks for an email
    third = create_job_session(business_id, mowing, size_id, MONDAY, "11:00")
    confirm_session(third.sessionToken, user_id=42, contact={
        "First Name": "Jane", "Last Name": "Doe", "Phone": "(555) 000-1111"})
    assert get_job_detail(business_id, third.jobId).customer.id == jane, \
        "it: still knows them, where email matching could not"

    # describe: a different account
    other = create_job_session(business_id, mowing, size_id, TUESDAY, "11:00")
    confirm_session(other.sessionToken, user_id=99, contact={
        "First Name": "Someone", "Last Name": "Else", "Email": "jane@example.com"})
    assert get_job_detail(business_id, other.jobId).customer.id != jane, \
        "it: is a different person, whatever address they typed"

    # describe: another business
    elsewhere = a_business(slot_mode="unlimited", increment=30)
    hedging = create_job_type(elsewhere, "Hedge Trimming").id
    hedging_size = add_job_type_size(elsewhere, hedging, "Standard", 60, 80.0).id
    away = create_job_session(elsewhere, hedging, hedging_size, MONDAY, "09:00")
    confirm_session(away.sessionToken, user_id=42, contact={})
    assert get_job_detail(elsewhere, away.jobId).customer.id != jane, \
        "it: keeps a separate record per business, as an anonymous booking does"


def test_booking_claims_customer():
    """Somebody who booked anonymously, then signed in, is one customer."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id

    anonymous = create_job_session(business_id, mowing, size_id, MONDAY, "09:00")
    confirm_session(anonymous.sessionToken, contact={
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    jane = get_job_detail(business_id, anonymous.jobId).customer.id
    assert get_customer(business_id, jane).hasBossAccount is False

    # describe: booking again, this time signed in
    signed_in = create_job_session(business_id, mowing, size_id, TUESDAY, "09:00")
    confirm_session(signed_in.sessionToken, user_id=42, contact={
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    assert get_job_detail(business_id, signed_in.jobId).customer.id == jane, \
        "it: is the record they already had"
    assert get_customer(business_id, jane).hasBossAccount is True, \
        "it: which the account now holds"
    assert len(get_customer(business_id, jane).appointments) == 2, \
        "it: so both bookings sit in one history"


def test_reconcile_user():
    """What the app does when it opens, and again whenever somebody signs in."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id
    elsewhere = a_business(slot_mode="unlimited", increment=30)
    hedging = create_job_type(elsewhere, "Hedge Trimming").id
    hedging_size = add_job_type_size(elsewhere, hedging, "Standard", 60, 80.0).id

    here = a_booking_for(business_id, mowing, size_id, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    there = a_booking_for(elsewhere, hedging, hedging_size, MONDAY, "09:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    jane_here = get_job_detail(business_id, here.jobId).customer.id

    # describe: the app opening for the first time after she signed up
    assert reconcile_boss_user(42, "jane@example.com") == 2, \
        "it: claims the record at every business she has booked with"
    assert get_customer(business_id, jane_here).hasBossAccount is True

    # describe: the app opening again
    assert reconcile_boss_user(42, "jane@example.com") == 0, \
        "it: has nothing left to do, and needs no flag to know that"

    # describe: booking anonymously at a shop's kiosk after signing up
    later = a_booking_for(business_id, mowing, size_id, TUESDAY, "13:00", {
        "First Name": "Jane", "Last Name": "Doe", "Email": "jane@example.com"})
    # Same address, so it lands on the record she already had.
    assert get_job_detail(business_id, later.jobId).customer.id == jane_here

    # describe: a record somebody else's account already holds
    taken = a_booking_for(business_id, mowing, size_id, TUESDAY, "15:00", {
        "First Name": "Someone", "Last Name": "Else", "Email": "someone@example.com"})
    someone = get_job_detail(business_id, taken.jobId).customer.id
    reconcile_boss_user(99, "someone@example.com")
    assert reconcile_boss_user(42, "someone@example.com") == 0, \
        "it: never takes a record another account already holds"
    assert get_customer(business_id, someone).hasBossAccount is True

    # describe: an address nobody booked under
    assert reconcile_boss_user(43, "nobody@example.com") == 0

    # Storage refuses to move a held record even asked directly. `lib` checks
    # first, so nothing reaches this — which is the point of testing it here:
    # a later caller that forgets is stopped by the statement itself.
    assert db.claim_customer(someone, 42) == 0, \
        "it: never moves a record from one account to another"
    assert get_customer(business_id, someone).hasBossAccount is True

    # describe: nothing to reconcile against
    with pytest.raises(ValidationError):
        reconcile_boss_user(44, "   ")


def test_email_matching():
    """Case is ignored on the stored address as well as the typed one.

    A test that varies only the search term passes against a comparison that is
    not case-insensitive at all, because the stored value happened to be
    lowercase. This stores a shouty one.
    """
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, mowing, "Standard", 60, 50.0).id

    pat = create_customer(business_id, "Pat", "Ng", email="Pat@Example.COM")
    booked = a_booking_for(business_id, mowing, size_id, MONDAY, "09:00", {
        "First Name": "Pat", "Last Name": "Ng", "Email": "pat@example.com"})

    assert get_job_detail(business_id, booked.jobId).customer.id == pat.id, \
        "it: is the record they already had"
    assert len(get_customers(business_id)) == 1, "it: and not a second one"


def test_job_type_contact_fields():
    """What a job type asks the customer for, and in what order."""
    fresh_database()

    business_id = a_business(increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    types = {f.name: f for f in get_contact_field_types()}

    # describe: asking for a name
    first = add_job_type_contact_field(business_id, mowing, types["First Name"].id)
    assert first.name == "First Name", "it: is named as the field type is"
    assert first.fieldType == "text", "it: and carries the kind of input to draw"
    assert first.sortOrder == 0, "it: is asked first"
    assert first.isRequired is True, "it: and is required unless told otherwise"

    last = add_job_type_contact_field(business_id, mowing, types["Last Name"].id, is_required=False)
    assert last.sortOrder == 1, "it: the next is asked after it"
    assert last.isRequired is False, "it: and may be optional"

    # describe: asking for something that can receive a code
    phone = add_job_type_contact_field(business_id, mowing, types["Phone"].id, require_otp=True)
    assert phone.requireOtp is True, "it: can be verified before the booking stands"

    # describe: asking a name to receive a code
    with pytest.raises(ValidationError):
        add_job_type_contact_field(business_id, mowing, types["City"].id, require_otp=True)

    # describe: asking for the same thing twice
    with pytest.raises(ValidationError):
        add_job_type_contact_field(business_id, mowing, types["Phone"].id)

    # describe: a field type nobody offers
    with pytest.raises(ValidationError):
        add_job_type_contact_field(business_id, mowing, 9999)

    # describe: listing them
    assert [f.name for f in get_job_type_contact_fields(mowing)] == \
        ["First Name", "Last Name", "Phone"], "it: reads in the order they are asked"

    # describe: changing one
    changed = update_job_type_contact_field(business_id, last.id, types["Email"].id,
                                            is_required=True, require_otp=True)
    assert changed.name == "Email", "it: can be pointed at another field type"
    assert changed.requireOtp is True
    assert changed.sortOrder == 1, "it: and keeps its place in the order"

    # describe: saving it with the type it already has
    # The modal posts every field each time, so a checkbox toggle arrives
    # carrying the same type — which is the field colliding with itself.
    same = update_job_type_contact_field(business_id, changed.id, types["Email"].id,
                                         is_required=False, require_otp=False)
    assert same.name == "Email"
    assert same.isRequired is False, "it: takes the change it was called for"

    # describe: changing it to something that cannot receive a code
    with pytest.raises(ValidationError):
        update_job_type_contact_field(business_id, changed.id, types["City"].id, require_otp=True)

    # describe: changing it onto a type already asked for
    with pytest.raises(ValidationError):
        update_job_type_contact_field(business_id, changed.id, types["Phone"].id)

    # describe: one that is not there
    with pytest.raises(ValidationError):
        update_job_type_contact_field(business_id, 9999, types["Email"].id)
    with pytest.raises(ValidationError):
        delete_job_type_contact_field(business_id, 9999)

    # describe: no longer asking
    delete_job_type_contact_field(business_id, changed.id)
    assert [f.name for f in get_job_type_contact_fields(mowing)] == \
        ["First Name", "Phone"], "it: is no longer asked"


def test_reorder_contact_fields():
    """The up and down buttons post the whole order."""
    fresh_database()

    business_id = a_business(increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing").id
    hedging = create_job_type(business_id, "Hedge Trimming").id
    types = {f.name: f for f in get_contact_field_types()}

    first = add_job_type_contact_field(business_id, mowing, types["First Name"].id)
    phone = add_job_type_contact_field(business_id, mowing, types["Phone"].id)
    email = add_job_type_contact_field(business_id, mowing, types["Email"].id)

    # describe: moving one up
    after = reorder_job_type_contact_fields(business_id, mowing, [phone.id, first.id, email.id])
    assert [f.name for f in after] == ["Phone", "First Name", "Email"], \
        "it: is asked in the order given"
    assert [f.sortOrder for f in after] == [0, 1, 2], \
        "it: renumbered from the top, whatever the order arrived as"

    # describe: reading it back
    assert [f.name for f in get_job_type_contact_fields(mowing)] == \
        ["Phone", "First Name", "Email"], "it: stays that way"

    # describe: an order missing one of them
    with pytest.raises(ValidationError):
        reorder_job_type_contact_fields(business_id, mowing, [phone.id, first.id])

    # describe: an order naming one twice
    with pytest.raises(ValidationError):
        reorder_job_type_contact_fields(business_id, mowing, [phone.id, phone.id, first.id])

    # describe: an order naming another job type's field
    stray = add_job_type_contact_field(business_id, hedging, types["First Name"].id)
    with pytest.raises(ValidationError):
        reorder_job_type_contact_fields(business_id, mowing, [phone.id, first.id, stray.id])
    assert [f.name for f in get_job_type_contact_fields(mowing)] == \
        ["Phone", "First Name", "Email"], "it: keeps the order it had"


def test_job_type_detail():
    """Everything the JobType window draws, in a single answer."""
    fresh_database()

    business_id = a_business(increment=30)
    mowing = create_job_type(business_id, "Lawn Mowing", min_employees=2)
    types = {f.name: f for f in get_contact_field_types()}

    add_job_type_size(business_id, mowing.id, "Small", 30, 40.0)
    add_job_type_size(business_id, mowing.id, "Large", 90, 120.0)
    add_job_type_attribute(business_id, mowing.id, "Gate Code", "text")
    add_job_type_contact_field(business_id, mowing.id, types["Phone"].id, require_otp=True)
    alice = an_employee(business_id, mowing.id)

    detail = get_job_type_detail(business_id, mowing.id)

    # describe: the job type itself
    assert detail.name == "Lawn Mowing"
    assert detail.minEmployees == 2
    assert detail.isActive is False, \
        "it: starts inactive, so a draft never reaches a customer"

    # describe: its three lists
    assert [s.name for s in detail.sizes] == ["Small", "Large"]
    assert detail.sizes[1].durationMinutes == 90
    assert [s.sortOrder for s in detail.sizes] == [0, 1], \
        "it: offers the sizes in the order they were added"
    assert [a.name for a in detail.attributes] == ["Gate Code"]
    assert [f.name for f in detail.contactFields] == ["Phone"]
    assert detail.contactFields[0].requireOtp is True

    # describe: who can do the work
    assert [e.id for e in detail.employees] == [alice], \
        "it: names the employees allowed to be given this"

    # describe: a job type that is not there
    assert get_job_type_detail(business_id, 9999) is None


def test_kiosk_business():
    """What a customer's screen needs, and nothing the operator sets privately."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    # Ready to take a booking: an active service, with a size and a way to
    # reach the customer. `configured` is drawn from the same tasks the Setup
    # Assistant lists.
    types = {f.name: f for f in get_contact_field_types()}
    offered = create_job_type(business_id, "Lawn Mowing")
    add_job_type_size(business_id, offered.id, "Standard", 60, 50.0)
    add_job_type_contact_field(business_id, offered.id, types["Phone"].id)
    update_job_type(business_id, offered.id, "Lawn Mowing", is_active=True)

    update_business_config(business_id, {
        "name": "Green Thumb Landscaping",
        "phone": "(555) 867-5309",
        "description": "Lawns, hedges, and leaf removal.",
        "allowCustomerEmployeeSelection": True,
        "confirmBySms": True,
        "minChangeNoticeMinutes": 90,
    })

    kiosk = get_kiosk(business_id)

    # describe: what the screen draws
    assert kiosk.name == "Green Thumb Landscaping"
    assert kiosk.phone == "(555) 867-5309"
    assert kiosk.description == "Lawns, hedges, and leaf removal."

    # describe: what the screen behaves by
    assert kiosk.slotMode == "unlimited", \
        "it: says whether choosing a time takes it from anyone else"
    assert kiosk.slotIncrementMinutes == 30
    assert kiosk.minChangeNoticeMinutes == 90
    assert kiosk.allowCustomerEmployeeSelection is True
    assert kiosk.scheduleTimeoutMinutes == 10, \
        "it: says how long a hold lasts, so the countdown matches the server"
    assert [h.dayOfWeek for h in kiosk.operatingHours] == list(range(7))

    # A customer is shown the answer, never the tasks behind it.
    assert kiosk.configured is True
    assert "confirmBySms" not in kiosk.model_dump(), \
        "it: carries nothing the business set for itself"

    # describe: a business that cannot take a booking yet
    empty = create_business("Not Ready", "UTC", "reserved").id
    assert get_kiosk(empty).configured is False, \
        "it: says so, and the kiosk shows the customer a closed door"

    # describe: a business that is not there
    assert get_kiosk(9999) is None


def test_kiosk_job_types():
    """A draft, or somebody taken out of the schedule, reaches no customer."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    types = {f.name: f for f in get_contact_field_types()}

    offered = create_job_type(business_id, "Lawn Mowing")
    add_job_type_size(business_id, offered.id, "Standard", 60, 50.0)
    add_job_type_contact_field(business_id, offered.id, types["Phone"].id, require_otp=True)
    add_job_type_attribute(business_id, offered.id, "Gate Code", "text")
    update_job_type(business_id, offered.id, "Lawn Mowing", is_active=True)

    # Created by a form that was never finished, so it stays inactive.
    create_job_type(business_id, "Untitled")

    alice = create_employee(business_id, "Alice", "Kim")
    allow_job_type(alice.id, offered.id)
    bob = create_employee(business_id, "Bob", "Torres", include_in_schedule=False)
    allow_job_type(bob.id, offered.id)

    # describe: the services offered
    listed = get_kiosk_job_types(business_id)
    assert [j.name for j in listed] == ["Lawn Mowing"], \
        "it: leaves a draft where it is"
    assert [s.name for s in listed[0].sizes] == ["Standard"]
    assert [f.name for f in listed[0].contactFields] == ["Phone"]
    assert listed[0].contactFields[0].requireOtp is True
    assert [a.name for a in listed[0].attributes] == ["Gate Code"]

    # describe: who a customer may ask for
    assert [f"{e.firstName} {e.lastName}" for e in get_kiosk_employees(business_id)] == \
        ["Alice Kim"], "it: offers only the people in the schedule"

    # describe: another business
    other = a_business(increment=30)
    assert get_kiosk_job_types(other) == []
    assert get_kiosk_employees(other) == []


def test_kiosk_calendar():
    """Which days of a month a customer may choose from."""
    fresh_database()

    # Open on Mondays alone, so the answer is countable by hand.
    business_id = create_business("Test Business", "UTC", "unlimited").id
    set_scheduling(business_id, 60, 60, 0, 0)
    set_operating_hours(business_id, 1, "09:00", "12:00")
    job_type_id, size_id = a_job_type(business_id, duration=60)

    # July 2026: Mondays fall on the 6th, 13th, 20th and 27th. `NOW` is the
    # 6th at 09:00, so that Monday still has its later hours.
    days = get_kiosk_calendar(business_id, job_type_id, size_id, None,
                              year=2026, month=7, now=NOW)

    assert days.year == 2026 and days.month == 7
    assert days.availableDays == [6, 13, 20, 27], \
        "it: offers the days the doors are open and something is left"

    # describe: a month past the cutoff
    # `NOW` is 6 July and the cutoff is 60 days, so nothing after 4 September
    # can be chosen — every Monday in September falls beyond it.
    september = get_kiosk_calendar(business_id, job_type_id, size_id, None,
                                   year=2026, month=9, now=NOW)
    assert september.availableDays == [], "it: offers nothing past the cutoff"

    # describe: a month already gone
    june = get_kiosk_calendar(business_id, job_type_id, size_id, None,
                              year=2026, month=6, now=NOW)
    assert june.availableDays == [], "it: offers no day that has passed"

    # describe: a holiday inside the month
    close_on_holiday(business_id, "A Holiday", "2026-07-13")
    after = get_kiosk_calendar(business_id, job_type_id, size_id, None,
                               year=2026, month=7, now=NOW)
    assert after.availableDays == [6, 20, 27], "it: drops a day it is closed"


def test_kiosk_day_slots():
    """The times on the one day a customer picked."""
    fresh_database()

    business_id = create_business("Test Business", "UTC", "unlimited").id
    set_scheduling(business_id, 60, 60, 0, 0)
    set_operating_hours(business_id, 1, "09:00", "12:00")
    job_type_id, size_id = a_job_type(business_id, duration=60)

    day = get_kiosk_day_slots(business_id, job_type_id, size_id, None,
                              date="2026-07-13", now=NOW)

    assert day.date == "2026-07-13"
    assert [s.time for s in day.slots] == ["09:00", "10:00", "11:00"], \
        "it: offers every increment the doors are open"
    assert day.slots[0].displayTime == "9:00 AM", "it: as the screen spells it"

    # describe: a day the business is closed
    closed = get_kiosk_day_slots(business_id, job_type_id, size_id, None,
                                 date="2026-07-14", now=NOW)
    assert closed.slots == [], "it: offers nothing"


def test_financial_report_screen():
    """What the Financial Report window draws, including the period it chose."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type_id = create_job_type(business_id, "Lawn Mowing").id
    size_id = add_job_type_size(business_id, job_type_id, "Standard", 60, 100.0).id

    def booked(date, time="10:00"):
        held = create_job_session(business_id, job_type_id, size_id, date, time)
        confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
        return held.jobId

    done = booked("2026-07-13")
    record_payment(business_id, done, 100.0, "cash")
    complete_job(business_id, done, now=datetime(2026, 7, 13, 12, 0))

    deposited = booked("2026-08-03")
    set_job_type_deposit(job_type_id, "percent", 25.0)
    record_payment(business_id, deposited, 25.0, "cash")

    dropped = booked("2026-08-10")
    cancel_appointment(dropped, as_operator=True)

    report = get_financial_report(business_id, 2026, quarter=3)

    # describe: the money
    assert report.revenue == 125.0, "it: counts what actually arrived"
    assert report.depositsCollected == 25.0, \
        "it: names separately what is held against work still to come"
    assert report.writeOffs == 0.0

    # describe: the work
    assert report.jobsCompleted == 1, "it: counts the appointments finished"
    assert report.jobsCancelled == 1, "it: and the ones that fell through"

    # describe: the period it covers
    assert report.period == "quarter"
    assert report.year == 2026 and report.quarter == 3
    assert report.fromDate == "2026-07-01" and report.toDate == "2026-09-30"

    # describe: a whole year
    annual = get_financial_report(business_id, 2026)
    assert annual.period == "year", "it: says which kind of period this is"
    assert annual.quarter is None
    assert annual.fromDate == "2026-01-01" and annual.toDate == "2026-12-31"
    assert annual.jobsCompleted == 1

    # describe: the years the screen offers
    # A year the business has work in, chosen away from the current one so the
    # current-year fallback cannot stand in for it.
    booked("2024-03-04")
    offered = get_financial_report(business_id, 2026).availableYears
    assert 2024 in offered, "it: offers a year with work in it"
    assert datetime.now().year in offered, "it: and always this one"

    # describe: a business booked either side of this year
    # The current year has to be placed among the booked ones rather than
    # appended, which is the only case where the ordering is decided here.
    straddling = a_business(slot_mode="unlimited", increment=30)
    other_type = create_job_type(straddling, "Hedge Trimming").id
    other_size = add_job_type_size(straddling, other_type, "Standard", 60, 10.0).id
    for date in ("2024-03-04", "2033-03-04"):
        held = create_job_session(straddling, other_type, other_size, date, "10:00")
        confirm_session(held.sessionToken, contact={"Phone": "+15559990000"})

    years = get_financial_report(straddling, 2026).availableYears
    assert years == [2024, datetime.now().year, 2033], \
        "it: reads earliest first, with this year in its place"

    # describe: a business with nothing booked
    empty = a_business(increment=30)
    quiet = get_financial_report(empty, 2026)
    assert quiet.revenue == 0.0 and quiet.jobsCompleted == 0
    assert quiet.availableYears == [datetime.now().year], \
        "it: still offers a year, so the screen has something to select"


def a_scheduled_business(mode="unlimited"):
    """A business with two employees who can do the one job type."""
    business_id = create_business("Test Business", "UTC", mode).id
    set_scheduling(business_id, 15, 90, 0, 0)
    for day in range(7):
        set_operating_hours(business_id, day, "08:00", "18:00")
    job_type_id, size_id = a_job_type(business_id, duration=60)
    alice = an_employee(business_id, job_type_id, days=tuple(range(7)),
                        first="Alice", last="Kim")
    bob = an_employee(business_id, job_type_id, days=tuple(range(7)),
                      first="Bob", last="Torres")
    return business_id, job_type_id, size_id, alice, bob


def book_at(business_id, job_type_id, size_id, date, time, employee_ids=None,
            contact=None):
    held = create_job_session(business_id, job_type_id, size_id, date, time,
                              employee_ids or [])
    confirm_session(held.sessionToken, contact=contact or {})
    return held.jobId


def test_business_scoping():
    """A record is reachable only through the business that holds it.

    Every id in a path comes off a screen, and a screen is opened for one
    business. The business is what the caller was admitted for, so a record
    named under any other business is one they were never admitted to —
    however senior they are at the business they did name.

    An operator who runs a business is admitted to it. Naming their own
    business and somebody else's record is what this refuses.
    """
    fresh_database()

    mine, job_type_id, size_id, alice, _ = a_scheduled_business()
    theirs = create_business("Somebody Else", "UTC", "unlimited").id

    job_id = book_at(mine, job_type_id, size_id, "2026-07-13", "09:00", [alice])
    attribute_id = add_job_type_attribute(
        mine, job_type_id, "Gate code", "text").id
    phone_type = [f for f in get_contact_field_types() if f.name == "Phone"][0]
    field_id = add_job_type_contact_field(mine, job_type_id, phone_type.id).id
    schedule_id = get_working_days(mine, alice)[0].id
    window_id = add_time_off(mine, alice, "2026-09-14", "08:00", "12:00").id

    # describe: an appointment
    with pytest.raises(ValidationError):
        complete_job(theirs, job_id)
    with pytest.raises(ValidationError):
        record_payment(theirs, job_id, 10.0, "cash")
    with pytest.raises(ValidationError):
        write_off_payment(theirs, job_id)
    assert get_job_detail(mine, job_id).status == "confirmed", \
        "it: is left as the business that holds it had it"

    # describe: a job type
    assert get_job_type_detail(theirs, job_type_id) is None, \
        "it: is not there to read"
    with pytest.raises(ValidationError):
        add_job_type_size(theirs, job_type_id, "Large", 90, 80.0)
    with pytest.raises(ValidationError):
        add_job_type_attribute(theirs, job_type_id, "Gate code", "text")
    with pytest.raises(ValidationError):
        add_job_type_contact_field(theirs, job_type_id, phone_type.id)
    with pytest.raises(ValidationError):
        reorder_job_type_contact_fields(theirs, job_type_id, [field_id])

    # describe: what hangs off a job type
    with pytest.raises(ValidationError):
        update_job_type_size(theirs, size_id, "Large", 90, 80.0)
    with pytest.raises(ValidationError):
        delete_job_type_size(theirs, size_id)
    with pytest.raises(ValidationError):
        update_job_type_attribute(theirs, attribute_id, "Gate code", "text")
    with pytest.raises(ValidationError):
        delete_job_type_attribute(theirs, attribute_id)
    with pytest.raises(ValidationError):
        update_job_type_contact_field(theirs, field_id, phone_type.id)
    with pytest.raises(ValidationError):
        delete_job_type_contact_field(theirs, field_id)
    assert [z.id for z in get_job_type_sizes(job_type_id)] == [size_id], \
        "it: is left as the business that offers it had it"

    # describe: an employee
    with pytest.raises(ValidationError):
        get_working_days(theirs, alice)
    with pytest.raises(ValidationError):
        get_time_off(theirs, alice)
    with pytest.raises(ValidationError):
        get_employee_job_types(theirs, alice)
    with pytest.raises(ValidationError):
        set_employee_job_types(theirs, alice, [])
    with pytest.raises(ValidationError):
        add_time_off(theirs, alice, "2026-09-15", "08:00", "12:00")

    # describe: what hangs off an employee
    with pytest.raises(ValidationError):
        update_working_day(theirs, schedule_id, 1, "10:00", "16:00")
    with pytest.raises(ValidationError):
        delete_working_day(theirs, schedule_id)
    with pytest.raises(ValidationError):
        update_time_off(theirs, window_id, "2026-09-14", "09:00", "11:00")
    with pytest.raises(ValidationError):
        delete_time_off(theirs, window_id)
    assert len(get_working_days(mine, alice)) == 7, \
        "it: still works the days their own business gave them"
    assert [w.id for w in get_time_off(mine, alice)] == [window_id], \
        "it: still has the time off their own business gave them"


def test_schedule_month():
    """How busy each day of a month is."""
    fresh_database()

    business_id, job_type_id, size_id, alice, _ = a_scheduled_business()
    book_at(business_id, job_type_id, size_id, "2026-07-13", "09:00", [alice])
    book_at(business_id, job_type_id, size_id, "2026-07-13", "11:00", [alice])
    book_at(business_id, job_type_id, size_id, "2026-07-20", "09:00", [alice])
    august = book_at(business_id, job_type_id, size_id, "2026-08-03", "09:00", [alice])

    month = get_schedule_month(business_id, 2026, 7)

    assert month.year == 2026 and month.month == 7
    assert [(d.date, d.jobCount) for d in month.days] == \
        [("2026-07-13", 2), ("2026-07-20", 1)], \
        "it: names only the days with work on them, in order"

    # describe: a cancelled appointment
    cancel_appointment(august, as_operator=True)
    assert get_schedule_month(business_id, 2026, 8).days == [], \
        "it: leaves a day whose only appointment was called off"

    # describe: a month with nothing in it
    assert get_schedule_month(business_id, 2026, 9).days == []

    # describe: another business
    other = a_business(increment=30)
    assert get_schedule_month(other, 2026, 7).days == []


def test_schedule_week():
    """Seven days from the Sunday, and what sits on each."""
    fresh_database()

    business_id, job_type_id, size_id, alice, bob = a_scheduled_business()
    # 2026-07-13 is a Monday, so its week starts Sunday the 12th.
    book_at(business_id, job_type_id, size_id, "2026-07-13", "09:00", [alice, bob])
    book_at(business_id, job_type_id, size_id, "2026-07-15", "14:00", [bob])
    book_at(business_id, job_type_id, size_id, "2026-07-20", "09:00", [alice])

    week = get_schedule_week(business_id, "2026-07-13")

    assert week.weekStart == "2026-07-12", "it: starts on the Sunday, whatever day was asked"
    assert len(week.days) == 7, "it: is always seven days, empty ones included"
    assert [d.date for d in week.days][0] == "2026-07-12"
    assert week.days[0].displayDate == "Sun 7/12", "it: as the column header reads"

    monday = week.days[1]
    assert [j.jobCode for j in monday.jobs] != []
    assert monday.jobs[0].startTime == "09:00"
    assert monday.jobs[0].endTime == "10:00", "it: says when the work ends"
    assert monday.jobs[0].employeeInitials == ["AK", "BT"], \
        "it: names the crew small enough to fit the column"

    assert week.days[3].jobs[0].startTime == "14:00"
    assert week.days[6].jobs == [], "it: the Saturday is empty"

    # describe: asking with the Sunday itself
    assert get_schedule_week(business_id, "2026-07-12").weekStart == "2026-07-12"

    # describe: the following week
    assert [d.date for d in get_schedule_week(business_id, "2026-07-20").days][0] == \
        "2026-07-19", "it: never reaches back into the week before"


def test_schedule_day():
    """One day, laid out so two appointments at once can both be seen."""
    fresh_database()

    business_id, job_type_id, size_id, alice, bob = a_scheduled_business()
    first = book_at(business_id, job_type_id, size_id, "2026-07-13", "09:00", [alice],
                    contact={"First Name": "Jane", "Last Name": "Doe"})
    book_at(business_id, job_type_id, size_id, "2026-07-13", "09:15", [bob],
            contact={"First Name": "John", "Last Name": "Smith"})
    book_at(business_id, job_type_id, size_id, "2026-07-13", "14:00", [alice])

    day = get_schedule_day(business_id, "2026-07-13")

    assert day.date == "2026-07-13"
    assert [j.startTime for j in day.jobs] == ["09:00", "09:15", "14:00"], \
        "it: reads in the order of the day"

    # describe: where each sits on the grid
    assert day.jobs[0].startMinuteOffset == 540, "it: minutes from midnight"
    assert day.jobs[0].durationMinutes == 60
    assert day.jobs[0].customerName == "Jane Doe"
    assert [e.firstName for e in day.jobs[0].employees] == ["Alice"]

    # describe: two appointments running at once
    assert day.jobs[0].overlapTotal == 2 and day.jobs[1].overlapTotal == 2, \
        "it: both know they are one of a pair"
    assert {day.jobs[0].overlapColumn, day.jobs[1].overlapColumn} == {0, 1}, \
        "it: and take a column each, so neither hides the other"

    # describe: one standing alone
    assert day.jobs[2].overlapTotal == 1 and day.jobs[2].overlapColumn == 0, \
        "it: has the width to itself"

    # describe: a third overlapping the pair
    book_at(business_id, job_type_id, size_id, "2026-07-13", "09:30", [alice])
    crowded = get_schedule_day(business_id, "2026-07-13")
    assert [j.overlapTotal for j in crowded.jobs[:3]] == [3, 3, 3], \
        "it: widens the group rather than the newest one overlapping"
    assert sorted(j.overlapColumn for j in crowded.jobs[:3]) == [0, 1, 2]

    # describe: one long appointment spanning two short ones
    # The second short one starts after the first has ended, so only the long
    # one still running holds them in the same group.
    long_size = add_job_type_size(business_id, job_type_id, "All morning", 180, 200.0).id
    short_size = add_job_type_size(business_id, job_type_id, "Quick", 30, 20.0).id
    book_at(business_id, job_type_id, long_size, "2026-07-14", "09:00", [alice])
    book_at(business_id, job_type_id, short_size, "2026-07-14", "09:15", [bob])
    book_at(business_id, job_type_id, short_size, "2026-07-14", "10:00", [alice])

    spanned = get_schedule_day(business_id, "2026-07-14")
    assert [j.startTime for j in spanned.jobs] == ["09:00", "09:15", "10:00"]
    assert [j.overlapTotal for j in spanned.jobs] == [2, 2, 2], \
        "it: keeps all three in one group — the long one runs across the gap"
    assert spanned.jobs[1].overlapColumn == spanned.jobs[2].overlapColumn, \
        "it: and the second short one reuses the column the first has left"

    # describe: an appointment that was called off
    cancel_appointment(first, as_operator=True)
    assert first not in [j.id for j in get_schedule_day(business_id, "2026-07-13").jobs], \
        "it: leaves the grid"

    # describe: a day with nothing on it
    assert get_schedule_day(business_id, "2026-07-16").jobs == []


def test_unassigned_jobs():
    """Live appointments with nobody on them, as the screen shows them."""
    fresh_database()

    business_id, job_type_id, size_id, alice, _ = a_scheduled_business()

    lonely = book_at(business_id, job_type_id, size_id, "2026-07-13", "10:00",
                     contact={"First Name": "Robert", "Last Name": "Chen"})
    book_at(business_id, job_type_id, size_id, "2026-07-14", "10:00", [alice])
    cancelled = book_at(business_id, job_type_id, size_id, "2026-07-15", "10:00")
    cancel_appointment(cancelled, as_operator=True)

    jobs = get_unassigned_jobs(business_id)

    assert [j.id for j in jobs] == [lonely], \
        "it: lists only what nobody is on, and nothing called off"
    assert jobs[0].jobType == "Lawn Mowing"
    assert jobs[0].customerName == "Robert Chen"
    assert jobs[0].displayTime == "10:00 AM", "it: as the screen spells it"
    assert jobs[0].isRecurring is False

    # describe: another business
    assert get_unassigned_jobs(a_business(increment=30)) == []


def test_update_job():
    """The schedule and the crew, as the Job window saves them."""
    fresh_database()

    business_id, job_type_id, size_id, alice, bob = a_scheduled_business("reserved")
    job_id = book_at(business_id, job_type_id, size_id, "2026-07-13", "10:00",
                     [alice])

    def crew(job):
        return sorted(e.firstName for e in job.employees)

    moved = update_job(business_id, job_id, "2026-07-14", "14:00", [bob], now=NOW)

    assert moved.scheduledDate == "2026-07-14"
    assert moved.scheduledTime == "14:00"
    assert crew(moved) == ["Bob"], \
        "it: is the crew given, not the crew added to"

    # describe: the crew changes and the time does not
    same = update_job(business_id, job_id, "2026-07-14", "14:00",
                      [alice, bob], now=NOW)
    assert same.scheduledDate == "2026-07-14"
    assert crew(same) == ["Alice", "Bob"]

    # describe: nobody on it
    emptied = update_job(business_id, job_id, "2026-07-14", "14:00", [], now=NOW)
    assert crew(emptied) == [], \
        "it: an appointment may have nobody on it, which is what unassigned is"

    # describe: an employee of another business
    elsewhere, other_type, other_size, carol, _ = a_scheduled_business("reserved")
    with pytest.raises(ValidationError):
        update_job(business_id, job_id, "2026-07-14", "14:00", [carol], now=NOW)

    # describe: a job the business does not have
    away = book_at(elsewhere, other_type, other_size, "2026-07-13", "10:00")
    with pytest.raises(ValidationError):
        update_job(business_id, away, "2026-07-14", "14:00", [], now=NOW)


def test_assign_jobs():
    """Auto-assign puts somebody free on each appointment chosen."""
    fresh_database()

    # `reserved`, which is the mode that allocates anybody — an unlimited
    # business puts nobody on an appointment, so there is nothing to assign.
    business_id, job_type_id, size_id, alice, bob = a_scheduled_business("reserved")
    first = book_at(business_id, job_type_id, size_id, "2026-07-13", "10:00")
    second = book_at(business_id, job_type_id, size_id, "2026-07-14", "10:00")
    untouched = book_at(business_id, job_type_id, size_id, "2026-07-15", "10:00")

    # Availability is asked as of a moment, and these dates are ahead of it.
    result = assign_jobs(business_id, [first, second], now=NOW)

    assert result.assigned == 2, "it: puts somebody on each one it was given"
    assert result.unassigned == 0
    assert [j.id for j in get_unassigned_jobs(business_id)] == [untouched], \
        "it: leaves the ones it was not given"

    crew = get_job_detail(business_id, first).employees
    assert len(crew) == 1 and crew[0].id in (alice, bob), \
        "it: names somebody who can do the work"

    # describe: more appointments at one hour than there are people
    # Three at the same time, and two employees between them.
    same_hour = [book_at(business_id, job_type_id, size_id, "2026-07-16", "10:00")
                 for _ in range(3)]
    crowded = assign_jobs(business_id, same_hour, now=NOW)
    assert crowded.assigned == 2, "it: places everybody who is free"
    assert crowded.unassigned == 1, \
        "it: and reports the one it could not, rather than doubling somebody up"

    # describe: an appointment that already has somebody
    assert assign_jobs(business_id, [first], now=NOW).assigned == 0, \
        "it: leaves an appointment that is already crewed"

    # describe: work that takes two people
    pair_type = create_job_type(business_id, "Tree Felling", min_employees=2).id
    pair_size = add_job_type_size(business_id, pair_type, "Standard", 60, 300.0).id
    for employee in (alice, bob):
        allow_job_type(employee, pair_type)
    heavy = book_at(business_id, pair_type, pair_size, "2026-07-17", "10:00")

    assert assign_jobs(business_id, [heavy], now=NOW).assigned == 1
    assert len(get_job_detail(business_id, heavy).employees) == 2, \
        "it: puts on as many as the work needs, not one"

    # describe: an appointment belonging to another business
    elsewhere = a_business(increment=30)
    assert assign_jobs(elsewhere, [untouched], now=NOW).assigned == 0, \
        "it: never reaches into somebody else's work"

    # describe: nothing chosen
    assert assign_jobs(business_id, [], now=NOW).assigned == 0


def test_operator_dashboard():
    """The figures the operator lands on."""
    fresh_database()

    business_id, job_type_id, size_id, alice, _ = a_scheduled_business()
    today = datetime.now().strftime("%Y-%m-%d")
    this_month = datetime.now().strftime("%Y-%m")

    paid = book_at(business_id, job_type_id, size_id, today, "10:00", [alice])
    record_payment(business_id, paid, 120.0, "cash")
    book_at(business_id, job_type_id, size_id, today, "11:00", [alice])
    # A day in this month that is not today, so `jobsToday` is seen counting
    # today rather than the month. Derived from the clock rather than written
    # down: a fixed day of the month *is* today once a month, and a test that
    # fails on one day of the month reads as the code having broken.
    other_day = datetime.now() + timedelta(days=1)
    if other_day.strftime("%Y-%m") != this_month:
        other_day = datetime.now() - timedelta(days=1)
    book_at(business_id, job_type_id, size_id,
            other_day.strftime("%Y-%m-%d"), "09:00")

    board = get_dashboard(business_id)

    assert board.businessId == business_id, \
        "it: carries the business the kiosk button opens against"
    assert board.slotMode == "unlimited", \
        "it: says whether anybody is allocated, which decides if the panel shows"
    assert board.jobsToday == 2, "it: counts what is happening today"
    assert board.revenueThisMonth == 120.0, "it: and what came in this month"
    assert board.unassignedJobs == 1, "it: counts what nobody is on"

    assert board.unassignedConflicts == 0, \
        "it: counts no conflict under unlimited, which allocates nobody"

    # describe: a business that allocates people
    reserved, rj, rs, _, _ = a_scheduled_business("reserved")
    for _ in range(3):
        book_at(reserved, rj, rs, "2026-07-16", "10:00")
    board = get_dashboard(reserved, now=NOW)
    assert board.unassignedJobs == 3
    assert board.unassignedConflicts == 0, \
        "it: nobody is booked yet, so all three could be taken"

    assign_jobs(reserved, [j.id for j in get_unassigned_jobs(reserved)], now=NOW)
    after = get_dashboard(reserved, now=NOW)
    assert after.unassignedJobs == 1, "it: one is left over"
    assert after.unassignedConflicts == 1, \
        "it: and it is a conflict — both employees are taken at that hour"

    # describe: a business with nothing
    quiet = get_dashboard(a_business(increment=30))
    assert quiet.jobsToday == 0 and quiet.revenueThisMonth == 0.0
    assert quiet.unassignedJobs == 0


def test_employee_profile():
    """What an employee may see and change about themselves."""
    fresh_database()

    business_id, job_type_id, size_id, alice, _ = a_scheduled_business()
    hedging = create_job_type(business_id, "Hedge Trimming").id
    update_employee(business_id, alice, "Alice", "Kim", can_manage_own_schedule=True)
    add_time_off(business_id, alice, "2026-09-14", "08:00", "12:00")
    link_employee_to_user(business_id, alice, user_id=7)

    profile = get_employee_profile(7)

    assert profile.employeeId == alice
    assert profile.firstName == "Alice" and profile.lastName == "Kim"
    assert profile.canManageOwnSchedule is True, \
        "it: says whether the schedule fields are theirs to edit"
    assert [d.dayOfWeek for d in profile.scheduleTemplate] == list(range(7))
    assert [w.date for w in profile.timeOff] == ["2026-09-14"]
    assert [j.name for j in profile.jobTypes] == ["Lawn Mowing"]

    # describe: changing what they can do
    updated = update_employee_profile(7, [job_type_id, hedging])
    assert [j.name for j in updated.jobTypes] == ["Lawn Mowing", "Hedge Trimming"], \
        "it: is theirs to say what work they take"

    # describe: a job type another business offers
    elsewhere = a_business(increment=30)
    stray = create_job_type(elsewhere, "Snow Clearing").id
    with pytest.raises(ValidationError):
        update_employee_profile(7, [stray])

    # describe: somebody the operator has kept off their own schedule
    bob = create_employee(business_id, "Bob", "Torres")
    link_employee_to_user(business_id, bob.id, user_id=8)
    assert get_employee_profile(8).canManageOwnSchedule is False, \
        "it: says so, and the schedule fields stay read-only"

    # describe: somebody who works nowhere
    assert get_employee_profile(999) is None
    with pytest.raises(ValidationError):
        update_employee_profile(999, [job_type_id])


def test_employee_today():
    """The work one employee has in front of them."""
    fresh_database()

    business_id, job_type_id, size_id, alice, bob = a_scheduled_business()
    attribute = add_job_type_attribute(business_id, job_type_id, "Gate Code", "text")
    link_employee_to_user(business_id, alice, user_id=7)
    update_employee(business_id, alice, "Alice", "Kim", can_manage_own_schedule=True)

    held = create_job_session(business_id, job_type_id, size_id,
                              "2026-09-14", "10:00", [alice, bob])
    confirm_session(held.sessionToken,
                    contact={"First Name": "Jane", "Last Name": "Doe",
                             "Phone": "(555) 234-5678",
                             "Address Line 1": "456 Garden Blvd"},
                    attributes={attribute.id: "1234"})
    book_at(business_id, job_type_id, size_id, "2026-09-14", "14:00", [bob])
    book_at(business_id, job_type_id, size_id, "2026-09-15", "10:00", [alice])

    day = get_employee_today(7, "2026-09-14")

    assert day.date == "2026-09-14"
    assert day.displayDate == "Monday, September 14", "it: as the heading reads"
    assert day.canManageOwnSchedule is True
    assert [j.id for j in day.jobs] == [held.jobId], \
        "it: is their work alone, and only this day's"

    job = day.jobs[0]
    assert job.startTime == "10:00" and job.endTime == "11:00"
    assert job.customer.firstName == "Jane"
    assert job.customer.phone == "(555) 234-5678", "it: so they can call ahead"
    assert job.customer.addressLine1 == "456 Garden Blvd", "it: and drive there"
    assert [f"{c.firstName} {c.lastName}" for c in job.coWorkers] == ["Bob Torres"], \
        "it: names who else is on it, themselves excluded"
    assert [(a.name, a.value) for a in job.attributes] == [("Gate Code", "1234")], \
        "it: and what the customer answered"

    # describe: a day with nothing on it
    assert get_employee_today(7, "2026-09-16").jobs == []

    # describe: somebody who works nowhere
    assert get_employee_today(999, "2026-09-14") is None


def test_platform_contact_fields():
    """What every business chooses from when asking a customer for details."""
    fresh_database()

    seeded = get_contact_field_types()
    assert [f.name for f in seeded][:3] == ["First Name", "Last Name", "Phone"], \
        "it: arrives seeded, in the order the installer set"

    # describe: adding one
    company = add_contact_field_type("Company", "text")
    assert company.otpCapable is False
    assert company.sortOrder > max(f.sortOrder for f in seeded), \
        "it: is asked last until moved"

    # describe: one that can receive a code
    mobile = add_contact_field_type("Mobile", "phone", otp_capable=True)
    assert mobile.otpCapable is True

    # describe: a kind of field a code cannot reach
    with pytest.raises(ValidationError):
        add_contact_field_type("Nickname", "text", otp_capable=True)

    # describe: a kind of field nothing knows how to draw
    with pytest.raises(ValidationError):
        add_contact_field_type("Colour", "colour-picker")

    # describe: a name that is blank, or one already taken
    with pytest.raises(ValidationError):
        add_contact_field_type("  ", "text")
    with pytest.raises(ValidationError):
        add_contact_field_type("Company", "text")

    # describe: changing one
    changed = update_contact_field_type(company.id, "Company Name", "text")
    assert changed.name == "Company Name"
    assert changed.sortOrder == company.sortOrder, "it: keeps its place"

    # describe: saving it with the name it already has
    # The modal posts every field each time, so a type change arrives carrying
    # the same name — which is the field colliding with itself.
    same = update_contact_field_type(changed.id, "Company Name", "phone")
    assert same.fieldType == "phone", "it: takes the change it was called for"

    # describe: changing one onto a name already taken
    with pytest.raises(ValidationError):
        update_contact_field_type(company.id, "Mobile", "text")

    # describe: reordering them
    order = [f.id for f in get_contact_field_types()]
    moved = reorder_contact_field_types([order[-1]] + order[:-1])
    assert moved[0].name == "Mobile", "it: is asked first now"
    assert [f.sortOrder for f in moved] == list(range(len(moved))), \
        "it: renumbered from the top"

    # describe: an order that has drifted
    with pytest.raises(ValidationError):
        reorder_contact_field_types(order[:-1])

    # describe: removing one
    delete_contact_field_type(company.id)
    assert "Company Name" not in [f.name for f in get_contact_field_types()]

    # describe: removing one a job type asks for
    business_id = a_business(increment=30)
    job_type_id = create_job_type(business_id, "Lawn Mowing").id
    phone = [f for f in get_contact_field_types() if f.name == "Phone"][0]
    add_job_type_contact_field(business_id, job_type_id, phone.id)
    with pytest.raises(ValidationError):
        delete_contact_field_type(phone.id)
    assert "Phone" in [f.name for f in get_contact_field_types()], \
        "it: stays, because a business is asking for it"

    # describe: one that is not there
    with pytest.raises(ValidationError):
        update_contact_field_type(9999, "Anything", "text")
    with pytest.raises(ValidationError):
        delete_contact_field_type(9999)


def test_platform_timeout():
    """How long a customer has to finish scheduling."""
    fresh_database()

    assert get_schedule_timeout_minutes() == 10, "it: starts at ten minutes"

    assert set_schedule_timeout_minutes(15) == 15
    assert get_schedule_timeout_minutes() == 15, "it: keeps what was set"

    # A hold the customer never sees the end of is a time nobody else can take.
    for refused in (0, -5):
        with pytest.raises(ValidationError):
            set_schedule_timeout_minutes(refused)
    assert get_schedule_timeout_minutes() == 15, "it: keeps the value it had"


def test_platform_businesses():
    """Every business on the platform, as the super admin sees them."""
    fresh_database()

    green = create_business("Green Thumb", "America/Chicago", "reserved").id
    update_business_config(green, {"ownerName": "Maria Garcia"})
    sparkle = create_business("Sparkle Clean", "UTC", "unlimited").id
    disable_business(sparkle)

    listed = get_platform_businesses()
    assert [b.name for b in listed] == ["Green Thumb", "Sparkle Clean"]
    assert listed[0].ownerName == "Maria Garcia", "it: names who runs it"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", listed[0].createDate), \
        "it: says the day it joined, and no hour"
    assert listed[0].isActive is True and listed[1].isActive is False

    # describe: filtering by status
    assert [b.name for b in get_platform_businesses("active")] == ["Green Thumb"]
    assert [b.name for b in get_platform_businesses("inactive")] == ["Sparkle Clean"]
    assert len(get_platform_businesses("all")) == 2, "it: `all` is every one"

    # describe: a status nobody offers
    with pytest.raises(ValidationError):
        get_platform_businesses("retired")


def test_platform_business():
    """Creating, editing, and closing a business from the platform side."""
    fresh_database()

    # A business comes from an account opening one. The platform manages what
    # an operator created rather than creating any of its own.
    opened = sign_up(user_id=42, details={
        "name": "Cut Above Salon",
        "ownerName": "Sandra Reyes",
        "phone": "(555) 111-2222",
        "timezone": "America/New_York",
    })
    made = get_platform_business(opened.businessId)
    assert made.name == "Cut Above Salon"
    assert made.ownerName == "Sandra Reyes"
    assert made.timezone == "America/New_York"
    assert made.isActive is True, "it: opens for business straight away"

    # describe: reading it back
    same = get_platform_business(made.businessId)
    assert same.model_dump() == made.model_dump()

    # describe: editing it
    changed = update_platform_business(made.businessId, {"city": "Albany", "zip": "12207"})
    assert changed.city == "Albany"
    assert changed.name == "Cut Above Salon", "it: leaves what it was not given"

    # describe: closing and re-opening it
    assert disable_business(made.businessId).isActive is False
    assert get_kiosk(made.businessId).configured is False, \
        "it: takes no booking while it is closed"
    assert enable_business(made.businessId).isActive is True

    # describe: one that is not there
    assert get_platform_business(9999) is None
    for call in (lambda: update_platform_business(9999, {"city": "Nowhere"}),
                 lambda: enable_business(9999),
                 lambda: disable_business(9999)):
        with pytest.raises(ValidationError):
            call()


def test_delete_business_with_staff():
    """A business that never traded, and the people it was opened with.

    Signing up writes the owner's employee record, so every business has staff
    from the moment it exists — and the rows that reference it have to go with
    it or the delete refuses on a foreign key.
    """
    fresh_database()

    made = sign_up(user_id=42, details={"name": "Green Thumb"})
    rosa = create_employee(made.businessId, "Rosa", "Alvarez")
    add_working_day(made.businessId, rosa.id, 0, "09:00", "17:00")

    delete_business(made.businessId)

    assert [b.id for b in get_platform_businesses()] == []
    assert whoami(42).role is None, \
        "it: takes the operator's own record with it"


def test_delete_business():
    """A business with history is closed rather than deleted."""
    fresh_database()

    empty = create_business("Never Traded", "UTC", "unlimited").id
    delete_business(empty)
    assert get_platform_business(empty) is None, "it: goes, having done nothing"

    # describe: one that has taken a booking
    traded, job_type_id, size_id, alice, _ = a_scheduled_business()
    book_at(traded, job_type_id, size_id, "2026-09-14", "10:00", [alice])

    with pytest.raises(ValidationError):
        delete_business(traded)
    assert get_platform_business(traded) is not None, \
        "it: stays, because its appointments are somebody's record"

    # describe: closing it instead
    assert disable_business(traded).isActive is False

    # describe: one that is not there
    with pytest.raises(ValidationError):
        delete_business(9999)


def test_platform_templates():
    """The starting points a new business may take its settings from."""
    fresh_database()

    seeded = get_business_templates()
    assert "Food & Drink" in [t.name for t in seeded], "it: arrives seeded"

    # describe: adding one
    made = add_business_template("Trades", "Plumbers, electricians, joiners.")
    assert made.name == "Trades"
    assert made.config == {}, \
        "it: changes nothing until somebody says what it should set"
    assert made.id in [t.id for t in get_business_templates()]

    # describe: one with settings behind it
    queue = add_business_template("Market Stall", "Serve whoever turns up.",
                                  config={"slotMode": "unlimited"})
    assert queue.config == {"slotMode": "unlimited"}

    # A template is worth having only if applying it does something.
    business_id = a_business(increment=30)
    after = apply_business_template(business_id, queue.id)
    assert after.slotMode == "unlimited"

    # describe: a name that is blank, or a description
    with pytest.raises(ValidationError):
        add_business_template("  ", "Something")
    with pytest.raises(ValidationError):
        add_business_template("Trades Two", "   ")

    # describe: a name already taken
    with pytest.raises(ValidationError):
        add_business_template("Trades", "Another go")

    # describe: changing one
    changed = update_business_template(made.id, "Skilled Trades",
                                       "Plumbers and electricians.")
    assert changed.name == "Skilled Trades"
    assert changed.config == {}, "it: keeps the settings it had"

    # describe: saving it under the name it already has
    same = update_business_template(changed.id, "Skilled Trades", "Reworded.")
    assert same.description == "Reworded."

    # describe: removing one
    delete_business_template(made.id)
    assert made.id not in [t.id for t in get_business_templates()]

    # describe: one that is not there
    with pytest.raises(ValidationError):
        update_business_template(9999, "Anything", "Anything")
    with pytest.raises(ValidationError):
        delete_business_template(9999)


def test_platform_holidays():
    """Every holiday the platform knows about, grouped by country."""
    fresh_database()

    db.insert_system_holiday("US", "United States", "Independence Day",
                             "2026-07-04", 2026)
    db.insert_system_holiday("US", "United States", "New Year's Day",
                             "2026-01-01", 2026)
    db.insert_system_holiday("CA", "Canada", "Canada Day", "2026-07-01", 2026)
    db.insert_system_holiday("US", "United States", "New Year's Day",
                             "2027-01-01", 2027)

    listed = get_platform_holidays(2026)

    assert listed.year == 2026
    assert [c.countryCode for c in listed.countries] == ["CA", "US"], \
        "it: groups by country, in a settled order"
    assert listed.countries[0].countryName == "Canada"
    assert [h.name for h in listed.countries[1].holidays] == \
        ["New Year's Day", "Independence Day"], "it: reads in date order"

    # describe: the years there are
    assert get_holiday_years() == [2026, 2027], "it: earliest first"

    # describe: a year nobody has fetched
    assert get_platform_holidays(2030).countries == []


def test_business_icons():
    """System icons every business shares, and its own uploads."""
    fresh_database()

    business_id = a_business(increment=30)
    other = a_business(increment=30)

    # describe: before anybody uploads anything
    assert get_icons(business_id, "custom") == []

    # describe: uploading one
    mine = add_icon(business_id, "mower.svg", b"<svg/>")
    assert mine.isSystem is False
    assert mine.url.startswith(f"/media/{BUNDLE}/public/"), \
        "it: is served off disk, so a job type can draw it"
    assert mine.filename.endswith(".svg"), "it: keeps the kind of file it is"
    assert [i.id for i in get_icons(business_id, "custom")] == [mine.id]

    # describe: another business
    assert get_icons(other, "custom") == [], \
        "it: never offers somebody else's uploads"

    # describe: a kind of file that is not an image
    for refused in ("notes.txt", "payload.exe", "archive.zip", "noextension"):
        with pytest.raises(ValidationError):
            add_icon(business_id, refused, b"...")

    # describe: a file with nothing in it
    with pytest.raises(ValidationError):
        add_icon(business_id, "empty.svg", b"")

    # describe: one larger than an icon has cause to be
    with pytest.raises(ValidationError):
        add_icon(business_id, "huge.png", b"x" * (media.MAX_ICON_BYTES + 1))

    # describe: the icons the platform ships
    # The rows are added by hand rather than seeded, so the set starts empty.
    assert get_icons(business_id, "system") == []

    system = add_system_icon("scissors.svg")
    assert system.isSystem is True
    assert system.url == f"/boss/app/{BUNDLE}/img/scissors.svg", \
        "it: comes from the bundle, its URL worked out from the filename"
    assert os.path.isfile(os.path.join(REPO, "public", "boss", "app", BUNDLE,
                                       "img", "scissors.svg")), \
        "it: and the bundle carries the file"
    assert [i.id for i in get_icons(other, "system")] == [system.id], \
        "it: is offered to every business at once"

    # describe: a kind nobody offers
    with pytest.raises(ValidationError):
        get_icons(business_id, "borrowed")

    # describe: a system icon with no name
    with pytest.raises(ValidationError):
        add_system_icon("   ")

    # describe: removing one
    on_disk = os.path.join(media.public_directory(BUNDLE), mine.filename)
    assert os.path.isfile(on_disk)
    delete_icon(business_id, mine.id)
    assert get_icons(business_id, "custom") == []
    assert not os.path.isfile(on_disk), \
        "it: takes the file with it, rather than leaving it served"

    # describe: removing another business's, or one the platform ships
    theirs = add_icon(other, "broom.svg", b"<svg/>")
    with pytest.raises(ValidationError):
        delete_icon(business_id, theirs.id)
    with pytest.raises(ValidationError):
        delete_icon(business_id, system.id)


def test_operator_signup():
    """A BOSS user opening a business, and becoming its operator."""
    fresh_database()

    templates = {t.name: t for t in get_business_templates()}
    made = sign_up(user_id=42, details={
        "name": "Green Thumb Landscaping",
        "phone": "(555) 867-5309",
        "ownerName": "Maria Garcia",
        "city": "Springfield",
        "timezone": "America/Chicago",
    }, template_id=templates["Food & Drink"].id)

    assert made.businessId != 0
    assert made.operatorId != 0, "it: is the record tying them to it"

    # describe: the business it opened
    config = get_business_config(made.businessId)
    assert config.name == "Green Thumb Landscaping"
    assert config.ownerName == "Maria Garcia"
    assert config.timezone == "America/Chicago"
    assert config.slotMode == "unlimited", \
        "it: takes the settings the chosen template carries"

    # describe: who the app now belongs to
    assert operator_business(42) == made.businessId, \
        "it: is the business every admin route acts on for them"
    assert whoami(42).role == "Operator"
    assert whoami(42).businessId == made.businessId

    # describe: somebody who has signed up for nothing
    assert operator_business(99) is None
    assert whoami(99).role is None, \
        "it: works for nobody until they open a business"
    assert whoami(99).businessId == 0

    # describe: signing up twice
    with pytest.raises(ValidationError):
        sign_up(user_id=42, details={"name": "Second Business"})
    assert operator_business(42) == made.businessId, "it: keeps the first"

    # describe: a business with no name
    with pytest.raises(ValidationError):
        sign_up(user_id=50, details={"name": "   "})
    assert operator_business(50) is None, "it: opened nothing"

    # describe: a template nobody offers
    # Checked before the business is created, so a refusal leaves nothing: the
    # alternative is a business with no operator, which no screen can reach.
    before = len(get_platform_businesses())
    with pytest.raises(ValidationError):
        sign_up(user_id=51, details={"name": "Third"}, template_id=9999)
    assert operator_business(51) is None
    assert len(get_platform_businesses()) == before, \
        "it: leaves no business behind, half-made and unreachable"

    # describe: signing up without choosing a template
    plain = sign_up(user_id=52, details={"name": "Plain Business"})
    assert get_business_config(plain.businessId).name == "Plain Business"


def test_kiosk_close_permission():
    """The close button belongs to whoever owns *this* business."""
    fresh_database()

    mine = sign_up(user_id=42, details={"name": "Mine"}).businessId
    theirs = sign_up(user_id=43, details={"name": "Theirs"}).businessId

    assert is_operator_of(mine, 42) is True
    assert is_operator_of(theirs, 42) is False, \
        "it: owning some business is not owning this one"
    assert is_operator_of(mine, 99) is False, "it: nor is owning none"


def test_platform_vendors():
    """Which service sends the mail, the texts, and takes the money."""
    fresh_database()

    vendors = {v.type: v for v in get_vendors()}
    assert set(vendors) == {"email", "sms", "payment"}, \
        "it: offers a choice for each kind of thing that leaves the platform"
    assert vendors["email"].currentVendor is None, \
        "it: has nobody chosen until somebody chooses"
    assert "sendgrid" in vendors["email"].registeredVendors
    assert vendors["email"].configKeys == []

    # describe: choosing one
    chosen = set_vendor("email", "sendgrid",
                        {"fromEmail": "noreply@bithead.io", "apiKey": "SG.secret"})
    assert chosen.currentVendor == "sendgrid"
    assert chosen.configKeys == ["apiKey", "fromEmail"], \
        "it: names what is configured without handing back the credentials"
    assert {v.type: v.currentVendor for v in get_vendors()}["email"] == "sendgrid", \
        "it: is what the platform uses from now on"

    # describe: changing to another
    changed = set_vendor("email", "mailgun", {"fromEmail": "hello@bithead.io"})
    assert changed.currentVendor == "mailgun"
    assert changed.configKeys == ["fromEmail"], \
        "it: replaces what was configured rather than keeping the old keys"
    assert {v.type: v.currentVendor for v in get_vendors()}["email"] == "mailgun"

    # describe: a kind of vendor the platform has no use for
    with pytest.raises(ValidationError):
        set_vendor("carrier-pigeon", "pigeon", {})

    # describe: a vendor the platform does not recognise
    with pytest.raises(ValidationError):
        set_vendor("email", "smoke-signal", {})

    # describe: clearing the choice
    cleared = set_vendor("email", None, {})
    assert cleared.currentVendor is None, "it: sends nothing until one is chosen"


def test_create_employee():
    """The draft the Employee window opens on."""
    fresh_database()

    business_id = a_business(increment=30)
    draft = create_employee(business_id, "Untitled", "")

    assert draft.firstName == "Untitled"
    assert draft.includeInSchedule is True, \
        "it: is in the schedule unless the operator says otherwise"
    assert [e.id for e in get_employees(business_id)] == [draft.id]

    assert draft.canManageOwnSchedule is False, \
        "it: manages nobody's schedule until the operator allows it"

    # describe: the operator allows it while adding them
    trusted = create_employee(business_id, "Rosa", "Alvarez",
                              can_manage_own_schedule=True)
    assert trusted.canManageOwnSchedule is True, \
        "it: is what was asked for, not what the default would have been"
    assert get_employee(business_id, trusted.id).canManageOwnSchedule is True, \
        "it: and it was stored, rather than only answered"

    # describe: a first name that is blank
    with pytest.raises(ValidationError):
        create_employee(business_id, "   ", "")


def test_whoami_employee():
    """An employee with a BOSS account opens on the employee screen.

    `whoami` read `business_users`, which only an operator ever had, so an
    employee resolved as a customer and the employee branch was unreachable.
    """
    fresh_database()

    business_id = a_business(increment=30)
    rosa = create_employee(business_id, "Rosa", "Alvarez")
    link_employee_to_user(business_id, rosa.id, 77)

    assert whoami(77).role == "Employee"
    assert whoami(77).businessId == business_id, \
        "it: is the business they work for"

    # describe: an employee with no BOSS account yet
    create_employee(business_id, "Unlinked", "Person")
    assert whoami(0).role is None


def test_working_for_business():
    """The one question every business-scoped route asks."""
    fresh_database()

    made = sign_up(user_id=42, details={"name": "Green Thumb"})
    other = a_business(increment=30)

    rosa = create_employee(made.businessId, "Rosa", "Alvarez")
    link_employee_to_user(made.businessId, rosa.id, 77)

    assert is_working_for_business(made.businessId, 42), "it: the operator"
    assert is_working_for_business(made.businessId, 77), "it: an employee"

    # describe: somebody who works for nobody
    assert not is_working_for_business(made.businessId, 99)

    # describe: the same people against a business they have nothing to do with
    assert not is_working_for_business(other, 42)
    assert not is_working_for_business(other, 77)

    # describe: nobody signed in
    assert not is_working_for_business(made.businessId, None)

    # describe: running it, which is not the same as working for it
    assert operator_business(42) == made.businessId
    assert operator_business(77) is None, \
        "it: an employee runs nothing"
    assert is_operator_of(made.businessId, 42) is True
    assert is_operator_of(made.businessId, 77) is False, \
        "it: working there is not running it"


def test_operator_is_an_employee():
    """A one-person business: the owner runs it and does the work."""
    fresh_database()

    made = sign_up(user_id=42, details={
        "name": "Solo Salon", "ownerName": "Maria Garcia"})

    staff = get_employees(made.businessId)
    assert [(e.firstName, e.lastName) for e in staff] == [("Maria", "Garcia")], \
        "it: is one record — the owner is an employee of the business they run"
    assert staff[0].includeInSchedule is False, \
        "it: is given no work until they say so"

    assert whoami(42).role == "Operator"
    assert is_working_for_business(made.businessId, 42)

    # describe: the owner does the work too
    update_employee(made.businessId, staff[0].id, "Maria", "Garcia", include_in_schedule=True)
    assert get_employees(made.businessId)[0].includeInSchedule is True, \
        "it: is the same record, now schedulable"
    assert whoami(42).role == "Operator", "it: still runs the business"


def test_one_business_per_user():
    """A BOSS account works for one business."""
    fresh_database()

    made = sign_up(user_id=42, details={"name": "Green Thumb"})
    other = a_business(increment=30)

    # describe: linking the same account to a second business
    elsewhere = create_employee(other, "Rosa", "Alvarez")
    with pytest.raises(ValidationError):
        link_employee_to_user(other, elsewhere.id, 42)

    assert whoami(42).businessId == made.businessId, "it: keeps the first"


def test_employee_scoping():
    """A record answers only for the business it belongs to.

    The route confirms the caller works for the business in the path. This is
    the other half: the record named by the id has to belong there too.
    """
    fresh_database()

    mine = a_business(increment=30)
    theirs = a_business(increment=30)
    rosa = create_employee(theirs, "Rosa", "Alvarez")

    assert get_employee(theirs, rosa.id) is not None
    assert get_employee(mine, rosa.id) is None, \
        "it: is absent from a business it does not belong to"

    # describe: writing to somebody else's record
    with pytest.raises(ValidationError):
        update_employee(mine, rosa.id, "Intruder", "X")
    assert get_employee(theirs, rosa.id).firstName == "Rosa", "it: is unchanged"

    with pytest.raises(ValidationError):
        delete_employee(mine, rosa.id)
    assert get_employee(theirs, rosa.id) is not None, "it: is still there"


def test_schedule_narrows_to_the_caller():
    """An employee's calendar shows the jobs they are on, and no others.

    `EmployeeCalendar` and `ScheduleCalendar` read the same routes. Without
    narrowing, an employee opening their calendar sees every appointment the
    business has.
    """
    fresh_database()

    business_id, job_type_id, size_id, alice, bob = a_scheduled_business()
    hers = book_at(business_id, job_type_id, size_id, MONDAY, "10:00", [alice])
    his = book_at(business_id, job_type_id, size_id, MONDAY, "11:00", [bob])

    # describe: the operator, who sees the business
    day = get_schedule_day(business_id, MONDAY)
    assert sorted(j.id for j in day.jobs) == sorted([hers, his])

    # describe: an employee, who sees their own
    theirs = get_schedule_day(business_id, MONDAY, employee_id=alice)
    assert [j.id for j in theirs.jobs] == [hers], \
        "it: leaves out a colleague's appointment"

    month = get_schedule_month(business_id, 2026, 7, employee_id=alice)
    booked = sum(d.jobCount for d in month.days)
    assert booked == 1, "it: counts only their own across the month"

    week = get_schedule_week(business_id, MONDAY, employee_id=alice)
    assert sum(len(d.jobs) for d in week.days) == 1


def test_job_type_scoping():
    """A job type answers only for the business that offers it."""
    fresh_database()

    mine = a_business(increment=30)
    theirs = a_business(increment=30)
    hedges = create_job_type(theirs, "Hedge Trimming")

    assert get_job_type(theirs, hedges.id) is not None
    assert get_job_type(mine, hedges.id) is None, \
        "it: is absent from a business that does not offer it"

    with pytest.raises(ValidationError):
        update_job_type(mine, hedges.id, "Stolen", 1)
    assert get_job_type(theirs, hedges.id).name == "Hedge Trimming"

    with pytest.raises(ValidationError):
        delete_job_type(mine, hedges.id)
    assert get_job_type(theirs, hedges.id) is not None


def test_customer_scoping():
    """A customer answers only for the business they booked with."""
    fresh_database()

    mine = a_business(increment=30)
    theirs = a_business(increment=30)
    rosa = create_customer(theirs, "Rosa", "Alvarez", "rosa@example.com", "")

    assert get_customer(theirs, rosa.id) is not None
    assert get_customer(mine, rosa.id) is None, \
        "it: is absent from a business they never booked with"

    with pytest.raises(ValidationError):
        update_customer(mine, rosa.id, {"firstName": "Intruder"})
    assert get_customer(theirs, rosa.id).firstName == "Rosa"


def test_job_scoping():
    """A job answers only for the business it was booked with.

    An employee is narrowed further: they reach the jobs they are on, and a
    colleague's is not theirs to open.
    """
    fresh_database()

    business_id, job_type_id, size_id, alice, bob = a_scheduled_business()
    other = a_business(increment=30)
    hers = book_at(business_id, job_type_id, size_id, MONDAY, "10:00", [alice])
    his = book_at(business_id, job_type_id, size_id, MONDAY, "11:00", [bob])

    assert get_job_detail(business_id, hers) is not None
    assert get_job_detail(other, hers) is None, \
        "it: is absent from a business it was not booked with"

    # describe: an employee, who reaches the jobs they are on
    assert get_job_detail(business_id, hers, employee_id=alice) is not None
    assert get_job_detail(business_id, his, employee_id=alice) is None, \
        "it: leaves a colleague's job alone"

    # describe: the operator, who reaches both
    assert get_job_detail(business_id, his) is not None


def test_link_employee_account():
    """An operator ties a BOSS account to an employee record."""
    fresh_database()

    business_id = a_business(increment=30)
    rosa = create_employee(business_id, "Rosa", "Alvarez")

    linked = link_employee_to_user(business_id, rosa.id, 77)
    assert linked.userId == 77
    assert whoami(77).role == "Employee", "it: opens on the employee screen now"
    assert is_working_for_business(business_id, 77)

    # describe: an employee of another business
    other = a_business(increment=30)
    theirs = create_employee(other, "Sam", "Doe")
    with pytest.raises(ValidationError):
        link_employee_to_user(business_id, theirs.id, 88)

    # describe: an account already working somewhere
    spare = create_employee(business_id, "Spare", "Person")
    with pytest.raises(ValidationError):
        link_employee_to_user(business_id, spare.id, 77)

    # describe: taking the link away
    unlinked = unlink_employee_from_user(business_id, rosa.id)
    assert unlinked.userId is None
    assert whoami(77).role is None, "it: is nobody's employee again"


def test_inactive_business():
    """A business that has stopped trading, and what each side is told.

    `is_active` says the operator has paid. An inactive business keeps every
    record it has — the operator still reads them — and stops being public.
    """
    fresh_database()

    business_id = a_business(increment=30)

    assert get_dashboard(business_id).isActive is True

    disable_business(business_id)

    # describe: a customer landing on it
    assert get_kiosk(business_id).configured is False, \
        "it: is unavailable, whether it is unfinished or not trading"

    # describe: the operator signing in
    board = get_dashboard(business_id)
    assert board.isActive is False, \
        "it: the dashboard says so, and the rest of the app still opens"
    assert board.jobsToday == 0, "it: still answers, being their own records"

    # describe: paying the bill
    enable_business(business_id)
    assert get_dashboard(business_id).isActive is True


def test_kiosk_availability():
    """A kiosk takes a booking once the business is set up and trading.

    The customer is told the same thing either way — which of the two it is
    concerns the operator, not somebody looking to book.
    """
    fresh_database()

    business_id = a_business(increment=30)

    # describe: trading, but nothing to book
    assert get_kiosk(business_id).configured is False

    set_operating_hours(business_id, 1, "09:00", "17:00")
    job_type = create_job_type(business_id, "Lawn Mowing")
    add_job_type_size(business_id, job_type.id, "Standard", 60, 50.0)
    phone = [f for f in get_contact_field_types() if f.name == "Phone"][0]
    db.insert_job_type_contact_field(job_type.id, phone.id)
    employee = create_employee(business_id, "Alice", "Kim")
    allow_job_type(employee.id, job_type.id)
    add_working_day(business_id, employee.id, 1, "09:00", "17:00")
    update_job_type(business_id, job_type.id, "Lawn Mowing", is_active=True)
    assert get_kiosk(business_id).configured is True, \
        "it: takes a booking once somebody can be booked"

    # describe: set up, but not trading
    disable_business(business_id)
    assert get_kiosk(business_id).configured is False, \
        "it: is unavailable even with everything set up"

    enable_business(business_id)
    assert get_kiosk(business_id).configured is True
