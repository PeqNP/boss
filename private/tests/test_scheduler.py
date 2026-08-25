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
