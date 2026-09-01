#
# Scheduler — when a business could do a piece of work.
#
# The one question the kiosk asks and every booking rule is written against:
# given a job type, a size, and maybe a person, what times are open?
#
# Two modes, and they answer differently. Under `reserved` a time is a resource
# — somebody has to be free for it, and taking it takes it from everyone else.
# Under `unlimited` a time is a preference: the business decides later who does
# what, so the slots run from now rather than from who is free.
#

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .. import db
from ..model import *
from .time import (day_of_week, display_date, display_time, overlaps,
                    to_minutes, to_time)
from .transform import _business, _employee, _hours, _job_type


def get_available_slots(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    limit: int = 5,
    from_date: Optional[str] = None,
    until_date: Optional[str] = None,
    now: Optional[datetime] = None
) -> List[Slot]:
    """The next times a customer may choose, soonest first.

    Branches on the business's Time Slots mode: `reserved` works out who is
    free, `unlimited` offers every increment the business is open.

    `limit` bounds how many come back; `0` asks for all of them, which is what
    a calendar wants — it needs every day that has anything, rather than the
    next few times.

    `until_date` stops the search early. The cutoff still applies, so this
    narrows the window and never widens it: a calendar asking about a month
    past the cutoff is answered with nothing.

    `now` is taken rather than read so a caller can ask what was available at a
    moment other than this one. It defaults to the clock.
    """
    business_row = db.get_business(business_id)
    if business_row is None:
        return []
    business = _business(business_row)

    job_type_row = db.get_job_type(business_id, job_type_id)
    if job_type_row is None:
        return []
    job_type = _job_type(job_type_row)

    duration = _duration_minutes(size_id)
    now = now or datetime.now()
    start_date = from_date or now.strftime("%Y-%m-%d")

    # Nothing before the notice window, and nothing past the cutoff.
    earliest = now + timedelta(hours=business.minBookingNoticeHours)
    last_date = (now + timedelta(days=business.cutoffDays)).strftime("%Y-%m-%d")
    if until_date:
        last_date = min(last_date, until_date)

    hours = {h.dayOfWeek: h for h in
             (_hours(r) for r in db.get_business_hours(business_id))}

    # `0` asks for every slot in the window. `wanted` stays large enough that
    # each day answers in full.
    unbounded = limit == 0

    slots: List[Slot] = []
    date = start_date
    while (unbounded or len(slots) < limit) and date <= last_date:
        wanted = MANY if unbounded else limit - len(slots)
        slots.extend(_slots_on(
            business,
            job_type,
            duration,
            date,
            hours,
            employee_id,
            earliest,
            now,
            wanted
        ))
        date = _next_day(date)
    return slots if unbounded else slots[:limit]


# More times than a day can hold, for a caller asking for all of them.
MANY = 10_000


def _duration_minutes(size_id: Optional[int]) -> int:
    """How long the work takes. A job type with no sizes takes an hour."""
    if size_id is None:
        return 60
    row = db.get_job_type_size(size_id)
    return row.duration_minutes if row is not None else 60


def _next_day(date: str) -> str:
    return (datetime.strptime(
        date,
        "%Y-%m-%d"
    ) + timedelta(days=1)).strftime("%Y-%m-%d")


def _slots_on(
    business: Business,
    job_type: JobType,
    duration: int,
    date: str,
    hours: Dict[int, BusinessHours],
    employee_id: Optional[int],
    earliest: datetime,
    now: datetime,
    wanted: int
) -> List[Slot]:
    """Times available on one day."""
    # A holiday closes the business itself, so it closes both modes.
    if db.is_holiday(business.id, date):
        return []

    day = hours.get(day_of_week(date))
    if business.slotMode == "unlimited":
        # The hours are the whole answer here, closed days included.
        if day is None or day.isClosed:
            return []
        return _unlimited_slots(
            business,
            duration,
            date,
            day,
            earliest,
            now,
            wanted
        )

    # Under `reserved` the hours are shown to the customer and nothing more:
    # when people work is what the employee schedules say, and a technician may
    # legitimately start before the office opens.
    return _reserved_slots(
        business,
        job_type,
        duration,
        date,
        employee_id,
        earliest,
        now,
        wanted
    )


def _increments(start: int, end: int, step: int) -> List[int]:
    """Every increment from `start` up to but not including `end`."""
    return list(range(start, end, step)) if step > 0 else []


def _bookable(
    date: str,
    minute: int,
    now: datetime,
    earliest: datetime
) -> bool:
    """Whether a time is still ahead, and far enough ahead.

    Two conditions, and they are not the same one. A time has to be in the
    future at all — the increment starting this second has arrived, and by the
    time anyone chose it, it would have passed. And it has to clear the
    business's booking notice, where a time exactly that far out is far enough.
    """
    when = datetime.strptime(date, "%Y-%m-%d") + timedelta(minutes=minute)
    return when > now and when >= earliest


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


def _unlimited_slots(
    business: Business,
    duration: int,
    date: str,
    day: Optional[BusinessHours],
    earliest: datetime,
    now: datetime,
    wanted: int
) -> List[Slot]:
    """Every increment the business is open.

    Nothing is asked about employees or existing jobs: under this mode a time
    is not a resource. The last slot sits one increment before closing
    whatever the job type's duration says — the duration is nominal when
    nothing is being reserved.
    """
    if day is None:
        return []

    slots = []
    for minute in _increments(
        to_minutes(day.openTime),
        to_minutes(day.closeTime),
        business.slotIncrementMinutes
    ):
        if not _bookable(date, minute, now, earliest):
            continue
        slots.append(_slot(business, date, minute, now, []))
        if len(slots) >= wanted:
            break
    return slots


def _reserved_slots(
    business: Business,
    job_type: JobType,
    duration: int,
    date: str,
    employee_id: Optional[int],
    earliest: datetime,
    now: datetime,
    wanted: int
) -> List[Slot]:
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

    day_start = min(
        (w[0] for shifts in working.values() for w in shifts),
        default=None
    )
    day_end = max(
        (w[1] for shifts in working.values() for w in shifts),
        default=None
    )
    if day_start is None:
        return []

    slots = []
    for minute in _increments(
        day_start,
        day_end,
        business.slotIncrementMinutes
    ):
        if minute + span > day_end:
            break
        if not _bookable(date, minute, now, earliest):
            continue
        free = [e.id for e in candidates
                if _is_free(
                    e.id,
                    minute,
                    minute + span,
                    working,
                    away,
                    committed
                )]
        if len(free) < job_type.minEmployees:
            continue
        slots.append(_slot(
            business,
            date,
            minute,
            now,
            free[:job_type.minEmployees]
        ))
        if len(slots) >= wanted:
            break
    return slots


def _is_free(
    employee_id: int,
    start: int,
    end: int,
    working: Dict[int, List[tuple]],
    away: Dict[int, List[tuple]],
    committed: Dict[int, List[tuple]]
) -> bool:
    """Whether one employee could take on this stretch of the day."""
    if not any(shift[0] <= start and end <= shift[1] for shift in working[employee_id]):
        return False
    if any(overlaps(start, end, *window) for window in away[employee_id]):
        return False
    if any(overlaps(start, end, *window) for window in committed[employee_id]):
        return False
    return True


def _slot(
    business: Business,
    date: str,
    minute: int,
    now: datetime,
    employee_ids: List[int]
) -> Slot:
    time = to_time(minute)
    return Slot(
        date=date,
        time=time,
        displayDate=_label(date, minute, business, now),
        displayTime=display_time(time),
        employeeIds=employee_ids
    )


def employees_free_at(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int],
    date: str,
    time: str,
    employee_id: Optional[int] = None,
    now: Optional[datetime] = None
) -> List[int]:
    """Who would do the work at a chosen time.

    The customer chose a time, not a person, so this asks the same question
    availability already answered rather than trusting the client to name
    anybody. Empty under `unlimited`, where nobody is allocated.
    """
    for slot in get_available_slots(
        business_id,
        job_type_id,
        size_id,
        employee_id,
        limit=200,
        from_date=date,
        now=now
    ):
        if slot.date == date and slot.time == time:
            return slot.employeeIds
    return []
