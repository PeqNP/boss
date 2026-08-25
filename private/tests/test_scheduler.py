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
    size = add_job_type_size(job_type.id, "Standard", duration, 50.0)
    return job_type.id, size.id


def an_employee(business_id, job_type_id, days=(1,), start="09:00", end="17:00",
                first="Alice", last="Kim"):
    """An employee who can do the work, and the days they work it."""
    employee = create_employee(business_id, first, last)
    allow_job_type(employee.id, job_type_id)
    for day in days:
        add_working_day(employee.id, day, start, end)
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


def test_installation_is_idempotent():
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


def test_a_record_belongs_to_something_that_exists():
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
    add_time_off(employee_id, MONDAY, "11:00", "13:00")

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


def test_unlimited_takes_nothing_from_anyone():
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


def test_minimum_change_notice_applies_to_reserved():
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


def test_expired_holds_are_cleaned_up():
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


def test_otp_sending_again_starts_over():
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


def test_otp_verification_is_remembered():
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


def test_appointment_access_sends_a_code():
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


def test_appointment_access_verifies_a_code():
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


def test_appointment_access_code_expires():
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


def test_appointment_locks_after_six_wrong_codes():
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


def test_six_wrong_codes_spread_out_do_not_lock():
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


def test_a_locked_appointment_is_the_customers_door_only():
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


def test_job_code_misses_spread_out_do_not_block():
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


def test_job_code_throttle_locks_and_notifies_nothing():
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


def test_recurrence_with_nobody_free():
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


def test_cancelled_recurrence_stops():
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


def test_recurrence_refuses_intervals_it_cannot_keep():
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
    size_id = add_job_type_size(job_type_id, "Standard", 60, cost).id
    held = create_job_session(business_id, job_type_id, size_id, MONDAY, "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
    return business_id, held.jobId


def test_payment():
    """Money against an appointment, and what the total says about it."""
    fresh_database()

    # describe: add cash transaction
    _, job_id = a_job_needing_payment(cost=100.0)
    result = record_payment(job_id, 100.0, "cash")
    assert result.paymentStatus == "fully_paid", \
        "it: paying the cost in full settles it"
    assert [t.amount for t in get_payments(job_id)] == [100.0], \
        "it: and the payment is on the record"
    assert get_payments(job_id)[0].method == "cash", "it: with how it was taken"

    # describe: partial payment
    fresh_database()
    _, job_id = a_job_needing_payment(cost=100.0)
    assert record_payment(job_id, 40.0, "cash").paymentStatus == "unpaid", \
        "it: part of the cost is not the cost"
    assert record_payment(job_id, 30.0, "cash").paymentStatus == "unpaid", \
        "it: and still is not"
    assert record_payment(job_id, 30.0, "cash").paymentStatus == "fully_paid", \
        "it: until the payments add up to it"
    assert len(get_payments(job_id)) == 3, "it: each payment is kept, not merged"

    # describe: overpayment
    fresh_database()
    _, job_id = a_job_needing_payment(cost=100.0)
    assert record_payment(job_id, 120.0, "cash").paymentStatus == "fully_paid", \
        "it: paying more than the cost is still paid"


def test_payment_deposit():
    """A deposit settles the appointment without settling the bill."""
    fresh_database()

    # describe: deposit payment, a fixed amount
    _, job_id = a_job_needing_payment(cost=100.0, deposit_type="fixed",
                                      deposit_amount=25.0)
    assert record_payment(job_id, 25.0, "cash").paymentStatus == "deposit_paid", \
        "it: the deposit is taken and the balance is not"
    assert record_payment(job_id, 75.0, "cash").paymentStatus == "fully_paid", \
        "it: the rest settles it"

    # describe: deposit payment, a percentage
    fresh_database()
    _, job_id = a_job_needing_payment(cost=200.0, deposit_type="percent",
                                      deposit_amount=10.0)
    assert record_payment(job_id, 15.0, "cash").paymentStatus == "unpaid", \
        "it: fifteen is short of ten percent of two hundred"
    assert record_payment(job_id, 5.0, "cash").paymentStatus == "deposit_paid", \
        "it: twenty in total is the deposit"

    # describe: less than the deposit
    fresh_database()
    _, job_id = a_job_needing_payment(cost=100.0, deposit_type="fixed",
                                      deposit_amount=25.0)
    assert record_payment(job_id, 10.0, "cash").paymentStatus == "unpaid", \
        "it: part of a deposit is not a deposit"


def test_payment_written_off():
    """Work the business decides not to chase."""
    fresh_database()

    _, job_id = a_job_needing_payment(cost=100.0)
    record_payment(job_id, 40.0, "cash")

    # describe: mark written_off
    assert write_off_payment(job_id).paymentStatus == "written_off", \
        "it: the balance stops being owed"
    assert [t.amount for t in get_payments(job_id)] == [40.0], \
        "it: what was actually taken is left alone"

    # describe: a payment after a write-off
    assert record_payment(job_id, 60.0, "cash").paymentStatus == "fully_paid", \
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

    finished = complete_job(job_id, now=NOW)
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


def test_job_completes_itself_when_the_time_has_passed():
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


def test_manual_businesses_do_not_complete_themselves():
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
        complete_job(job_id, now=after)
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
    mowing_size = add_job_type_size(mowing, "Standard", 60, 50.0).id
    hedging = create_job_type(business_id, "Hedge Trimming").id
    hedging_size = add_job_type_size(hedging, "Standard", 60, 80.0).id

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
    size_id = add_job_type_size(job_type_id, "Standard", 60, 100.0).id

    def booked(date, time="10:00"):
        held = create_job_session(business_id, job_type_id, size_id, date, time)
        confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
        return held.jobId

    paid = booked("2026-07-13")
    record_payment(paid, 100.0, "cash")

    part = booked("2026-08-03")
    record_payment(part, 40.0, "cash")
    write_off_payment(part)

    # Owed but not given up on. Without this, a fully-paid job contributes
    # zero to the write-off sum and the filter cannot be told from its absence.
    unpaid = booked("2026-08-10")

    outside = booked("2026-11-02")
    record_payment(outside, 100.0, "cash")

    # describe: quarterly report
    q3 = get_financial_report(business_id, year=2026, quarter=3)
    assert q3.revenue == 140.0, \
        "it: counts what arrived in the quarter, including on a written-off job"
    assert q3.writeOffs == 60.0, \
        "it: only the balance of jobs actually written off, not everything owed"
    assert q3.jobCount == 3, "it: over the appointments in the period"

    # describe: another quarter
    q4 = get_financial_report(business_id, year=2026, quarter=4)
    assert q4.revenue == 100.0, "it: a later quarter counts only its own"

    # describe: a year
    year = get_financial_report(business_id, year=2026)
    assert year.revenue == 240.0, "it: a year is its quarters together"
    assert year.jobCount == 4

    # describe: a quarter with nothing in it
    empty = get_financial_report(business_id, year=2025, quarter=1)
    assert empty.revenue == 0.0 and empty.jobCount == 0, \
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
    size_id = add_job_type_size(job_type_id, "Standard", 60, 100.0).id
    held = create_job_session(business_id, job_type_id, size_id, "2026-07-13", "10:00")
    confirm_session(held.sessionToken, contact={"Phone": "+15552340000"})
    record_payment(held.jobId, 100.0, "cash")

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
    comma_size = add_job_type_size(comma_type, "Standard", 60, 10.0).id
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
    add_time_off(employee_id, MONDAY, "11:00", "13:00")
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
    add_working_day(excluded.id, 1, "09:00", "17:00")

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


def test_who_would_do_the_work():
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


def test_contact_value_for_a_session():
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


def test_the_kiosk_can_identify_its_own_contact_fields():
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


def test_holding_a_time_on_something_that_is_not_there():
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


def test_an_appointment_carries_what_the_screen_shows():
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
    renamed = update_job_type(mowing.id, name="Lawn Care", min_employees=2,
                              is_active=True)
    assert renamed.name == "Lawn Care" and renamed.minEmployees == 2
    assert renamed.isActive is True, "it: saving is what makes it available"

    # describe: a name that is blank
    with pytest.raises(ValidationError):
        update_job_type(mowing.id, name="   ")

    # describe: needing nobody
    with pytest.raises(ValidationError):
        update_job_type(mowing.id, name="Lawn Care", min_employees=0)

    # describe: retiring one
    update_job_type(hedging.id, name="Hedge Trimming", is_active=True)
    retired = update_job_type(hedging.id, name="Hedge Trimming", is_active=False)
    assert retired.isActive is False, "it: stops being offered"
    assert [j.name for j in get_job_types(business_id, active_only=True)] == \
        ["Lawn Care"], "it: and drops out of what a customer may choose"
    assert len(get_job_types(business_id)) == 2, \
        "it: while the operator still sees it"


def test_deleting_a_job_type():
    """Work already booked against a job type keeps it."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    unused = create_job_type(business_id, "Never Booked")
    booked = create_job_type(business_id, "Lawn Mowing")
    size = add_job_type_size(booked.id, "Standard", 60, 50.0)
    held = create_job_session(business_id, booked.id, size.id, MONDAY, "10:00")
    confirm_session(held.sessionToken)

    # describe: one nothing was booked against
    delete_job_type(unused.id)
    assert [j.name for j in get_job_types(business_id)] == ["Lawn Mowing"], \
        "it: goes"

    # describe: one with appointments against it
    with pytest.raises(Blocked):
        delete_job_type(booked.id)
    assert get_appointment(held.jobId, now=NOW).jobTypeName == "Lawn Mowing", \
        "it: stays, because an appointment that names it is still real"


def test_job_type_sizes():
    """The sizes a job type is offered in, which carry its duration and price."""
    fresh_database()

    business_id = a_business(slot_mode="unlimited", increment=30)
    job_type = create_job_type(business_id, "Lawn Mowing")

    small = add_job_type_size(job_type.id, "Small", 30, 50.0)
    add_job_type_size(job_type.id, "Large", 90, 120.0)

    # describe: listing them
    assert [s.name for s in get_job_type_sizes(job_type.id)] == ["Small", "Large"], \
        "it: lists them in the order they were added"

    # describe: changing one
    changed = update_job_type_size(small.id, "Small", 45, 60.0)
    assert changed.durationMinutes == 45 and changed.cost == 60.0

    # describe: a duration of nothing
    with pytest.raises(ValidationError):
        update_job_type_size(small.id, "Small", 0, 60.0)

    # describe: a negative price
    with pytest.raises(ValidationError):
        update_job_type_size(small.id, "Small", 45, -1.0)

    # describe: removing one nothing was booked against
    delete_job_type_size(small.id)
    assert [s.name for s in get_job_type_sizes(job_type.id)] == ["Large"]

    # describe: removing one an appointment used
    large = get_job_type_sizes(job_type.id)[0]
    held = create_job_session(business_id, job_type.id, large.id, MONDAY, "10:00")
    confirm_session(held.sessionToken)
    with pytest.raises(Blocked):
        delete_job_type_size(large.id)
