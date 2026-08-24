#
# Scheduler — business rules
#
# The only module tests import for behaviour. Everything here takes and returns
# plain values, and every statement it issues is a named function in `db.py`.
#
# Two kinds of business live here, and one distinction separates them. Under
# `reserved`, a time is a resource: choosing one takes it from everyone else,
# and availability is computed from who is working and what they are already
# committed to. Under `unlimited`, a time is a preference: every increment the
# business is open is offered, always, and nobody is allocated. A café taking
# an order for 10:15 does not care that four other people also said 10:15.
#

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import db
from .model import *

# A job may be pending without holding anything: the customer opened the form
# and walked away. `db.get_booked_intervals` decides that by the session, which
# is the only place the timeout is applied.
HELD_STATUSES = ("pending", "confirmed")


# --- Conversions ---------------------------------------------------------
#
# One per concept, at the top, so a rule below works in attributes and a
# mistyped column fails here rather than three calls later.

def _business(row: db.BusinessRow) -> Business:
    return Business(
        id=row.id, name=row.name, phone=row.phone, timezone=row.timezone,
        slotMode=row.slot_mode, slotIncrementMinutes=row.slot_increment_minutes,
        cutoffDays=row.cutoff_days,
        minBookingNoticeHours=row.min_booking_notice_hours,
        minChangeNoticeMinutes=row.min_change_notice_minutes,
        bufferMinutes=row.buffer_minutes, isActive=bool(row.is_active)
    )


def _hours(row: db.BusinessHoursRow) -> BusinessHours:
    return BusinessHours(dayOfWeek=row.day_of_week, openTime=row.open_time,
                         closeTime=row.close_time, isClosed=bool(row.is_closed))


def _job_type(row: db.JobTypeRow) -> JobType:
    return JobType(id=row.id, businessId=row.business_id, name=row.name,
                   minEmployees=row.min_employees, isActive=bool(row.is_active))


def _size(row: db.JobTypeSizeRow) -> JobTypeSize:
    return JobTypeSize(id=row.id, jobTypeId=row.job_type_id, name=row.name,
                       durationMinutes=row.duration_minutes, cost=row.cost)


def _employee(row: db.EmployeeRow) -> Employee:
    return Employee(id=row.id, businessId=row.business_id,
                    firstName=row.first_name, lastName=row.last_name,
                    includeInSchedule=bool(row.include_in_schedule),
                    canManageOwnSchedule=bool(row.can_manage_own_schedule))


# --- Times ---------------------------------------------------------------
#
# Minutes since midnight, which is what every comparison here wants. A day is
# short enough that arithmetic on integers beats arithmetic on clocks.

def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def display_time(hhmm: str) -> str:
    """`09:00` as `9:00 AM`, which is how a customer reads a time."""
    minutes = to_minutes(hhmm)
    hour, minute = minutes // 60, minutes % 60
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {suffix}"


def display_date(date: str) -> str:
    """`2026-07-13` as `Monday, July 13`."""
    when = datetime.strptime(date, "%Y-%m-%d")
    return when.strftime("%A, %B ") + str(when.day)


def day_of_week(date: str) -> int:
    """0 for Sunday, matching how schedules and operating hours are stored."""
    return (datetime.strptime(date, "%Y-%m-%d").weekday() + 1) % 7


def overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    """Whether two stretches of a day share any minute.

    Touching is not overlapping: a job ending at 10:00 and one starting at
    10:00 can both happen.
    """
    return start < other_end and other_start < end


# --- Availability --------------------------------------------------------

def get_available_slots(business_id: int, job_type_id: int,
                        size_id: Optional[int] = None,
                        employee_id: Optional[int] = None,
                        limit: int = 5,
                        from_date: Optional[str] = None,
                        now: Optional[datetime] = None) -> List[Slot]:
    """The next times a customer may choose, soonest first.

    Branches on the business's Time Slots mode: `reserved` works out who is
    free, `unlimited` offers every increment the business is open.

    `now` is taken rather than read so a caller can ask what was available at a
    moment other than this one. It defaults to the clock.
    """
    business_row = db.get_business(business_id)
    if business_row is None:
        return []
    business = _business(business_row)

    job_type_row = db.get_job_type(job_type_id)
    if job_type_row is None:
        return []
    job_type = _job_type(job_type_row)

    duration = _duration_minutes(size_id)
    now = now or datetime.now()
    start_date = from_date or now.strftime("%Y-%m-%d")

    # Nothing before the notice window, and nothing past the cutoff.
    earliest = now + timedelta(hours=business.minBookingNoticeHours)
    last_date = (now + timedelta(days=business.cutoffDays)).strftime("%Y-%m-%d")

    hours = {h.dayOfWeek: h for h in
             (_hours(r) for r in db.get_business_hours(business_id))}

    slots: List[Slot] = []
    date = start_date
    while len(slots) < limit and date <= last_date:
        slots.extend(_slots_on(business, job_type, duration, date, hours,
                               employee_id, earliest, now,
                               limit - len(slots)))
        date = _next_day(date)
    return slots[:limit]


def _duration_minutes(size_id: Optional[int]) -> int:
    """How long the work takes. A job type with no sizes takes an hour."""
    if size_id is None:
        return 60
    row = db.get_job_type_size(size_id)
    return row.duration_minutes if row is not None else 60


def _next_day(date: str) -> str:
    return (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def _slots_on(business: Business, job_type: JobType, duration: int, date: str,
              hours: Dict[int, BusinessHours], employee_id: Optional[int],
              earliest: datetime, now: datetime, wanted: int) -> List[Slot]:
    """Times available on one day."""
    if db.is_holiday(business.id, date):
        return []

    day = hours.get(day_of_week(date))
    if day is not None and day.isClosed:
        return []

    if business.slotMode == "unlimited":
        return _unlimited_slots(business, duration, date, day, earliest, now, wanted)
    return _reserved_slots(business, job_type, duration, date, day,
                           employee_id, earliest, now, wanted)


def _increments(start: int, end: int, step: int) -> List[int]:
    """Every increment from `start` up to but not including `end`."""
    return list(range(start, end, step)) if step > 0 else []


def _after_earliest(date: str, minute: int, earliest: datetime) -> bool:
    when = datetime.strptime(date, "%Y-%m-%d") + timedelta(minutes=minute)
    return when >= earliest


def _label(date: str, minute: int, business: Business, now: datetime) -> str:
    """What the row reads.

    "ASAP" only when the time is inside the next increment — soon enough that
    naming the day would be stranger than saying it is now. Everything else is
    named by its date.
    """
    if business.slotMode == "unlimited":
        when = datetime.strptime(date, "%Y-%m-%d") + timedelta(minutes=minute)
        if timedelta(0) <= when - now <= timedelta(minutes=business.slotIncrementMinutes):
            return "ASAP"
    return display_date(date)


def _unlimited_slots(business: Business, duration: int, date: str,
                     day: Optional[BusinessHours], earliest: datetime,
                     now: datetime, wanted: int) -> List[Slot]:
    """Every increment the business is open.

    Nothing is asked about employees or existing jobs: under this mode a time
    is not a resource. The last slot sits one increment before closing
    whatever the job type's duration says — the duration is nominal when
    nothing is being reserved.
    """
    if day is None:
        return []

    slots = []
    for minute in _increments(to_minutes(day.openTime), to_minutes(day.closeTime),
                              business.slotIncrementMinutes):
        if not _after_earliest(date, minute, earliest):
            continue
        slots.append(_slot(business, date, minute, now, []))
        if len(slots) >= wanted:
            break
    return slots


def _reserved_slots(business: Business, job_type: JobType, duration: int,
                    date: str, day: Optional[BusinessHours],
                    employee_id: Optional[int], earliest: datetime,
                    now: datetime, wanted: int) -> List[Slot]:
    """Times enough employees are free to do the work.

    Availability comes from the employees' own schedules. Operating hours do
    not narrow it here — a business may take a booking for work its staff does
    outside the hours its counter is open.
    """
    candidates = [_employee(r) for r in db.get_employees_for_job_type(job_type.id)]
    if employee_id is not None:
        candidates = [e for e in candidates if e.id == employee_id]
    if len(candidates) < job_type.minEmployees:
        return []

    weekday = day_of_week(date)
    booked = db.get_booked_intervals([e.id for e in candidates], date)

    # When each candidate is working, and what they are already committed to.
    working: Dict[int, List[tuple]] = {}
    for employee in candidates:
        working[employee.id] = [
            (to_minutes(s.start_time), to_minutes(s.end_time))
            for s in db.get_employee_schedule(employee.id)
            if s.day_of_week == weekday
        ]

    away: Dict[int, List[tuple]] = {}
    for employee in candidates:
        away[employee.id] = [
            (to_minutes(t.start_time), to_minutes(t.end_time))
            for t in db.get_employee_time_off(employee.id, date)
        ]

    committed: Dict[int, List[tuple]] = {e.id: [] for e in candidates}
    for interval in booked:
        start = to_minutes(interval.scheduled_time)
        committed[interval.employee_id].append(
            (start, start + interval.duration_minutes + business.bufferMinutes)
        )

    # The work takes its duration plus whatever the business puts after it.
    span = duration + business.bufferMinutes

    day_start = min((w[0] for shifts in working.values() for w in shifts), default=None)
    day_end = max((w[1] for shifts in working.values() for w in shifts), default=None)
    if day_start is None:
        return []

    slots = []
    for minute in _increments(day_start, day_end, business.slotIncrementMinutes):
        if minute + span > day_end:
            break
        if not _after_earliest(date, minute, earliest):
            continue
        free = [e.id for e in candidates
                if _is_free(e.id, minute, minute + span, working, away, committed)]
        if len(free) < job_type.minEmployees:
            continue
        slots.append(_slot(business, date, minute, now, free[:job_type.minEmployees]))
        if len(slots) >= wanted:
            break
    return slots


def _is_free(employee_id: int, start: int, end: int,
             working: Dict[int, List[tuple]], away: Dict[int, List[tuple]],
             committed: Dict[int, List[tuple]]) -> bool:
    """Whether one employee could take on this stretch of the day."""
    if not any(shift[0] <= start and end <= shift[1] for shift in working[employee_id]):
        return False
    if any(overlaps(start, end, *window) for window in away[employee_id]):
        return False
    if any(overlaps(start, end, *window) for window in committed[employee_id]):
        return False
    return True


def _slot(business: Business, date: str, minute: int, now: datetime,
          employee_ids: List[int]) -> Slot:
    time = to_time(minute)
    return Slot(date=date, time=time,
                displayDate=_label(date, minute, business, now),
                displayTime=display_time(time),
                employeeIds=employee_ids)
