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

import json

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import db
from .model import *

# A job may be pending without holding anything: the customer opened the form
# and walked away. `db.get_booked_intervals` decides that by the session, which
# is the only place the timeout is applied.
HELD_STATUSES = ("pending", "confirmed")


class ValidationError(Exception):
    """Input that cannot be accepted, with a message meant for whoever asked."""


class OTPInvalid(Exception):
    """The code given is not the code sent, and an attempt has been spent."""

    def __init__(self, message, attempts_remaining):
        super().__init__(message)
        self.attemptsRemaining = attempts_remaining


class OTPMaxAttemptsExceeded(Exception):
    """The three tries are gone. Another code has to be sent."""


class JobNotFound(Exception):
    """No appointment carries that job code."""


class NoContactChannel(Exception):
    """The customer gave nothing a code could be sent to."""


class AppointmentInactive(Exception):
    """The appointment is cancelled or finished; there is nothing to get back into."""


class CodeInvalid(Exception):
    """The code given is not the code sent."""


class CodeSpent(Exception):
    """That code has already let someone in once, which is all it is good for."""


class CodeExpired(Exception):
    """The code was right half an hour ago."""


class AppointmentLocked(Exception):
    """Too many wrong codes. The customer's door is shut, the operator's is not."""


class CallerBlocked(Exception):
    """Too many unknown job codes. This caller may not submit another for a day."""


class InvalidDateRange(Exception):
    """A from-date after a to-date. No range can contain anything."""


class SessionExpired(Exception):
    """The hold on a time lapsed before the customer finished with it.

    Whatever they were part-way through has to start again from choosing a
    time, because the time they had may belong to somebody else now.
    """


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
    # A holiday closes the business itself, so it closes both modes.
    if db.is_holiday(business.id, date):
        return []

    day = hours.get(day_of_week(date))
    if business.slotMode == "unlimited":
        # The hours are the whole answer here, closed days included.
        if day is None or day.isClosed:
            return []
        return _unlimited_slots(business, duration, date, day, earliest, now, wanted)

    # Under `reserved` the hours are shown to the customer and nothing more:
    # when people work is what the employee schedules say, and a technician may
    # legitimately start before the office opens.
    return _reserved_slots(business, job_type, duration, date,
                           employee_id, earliest, now, wanted)


def _increments(start: int, end: int, step: int) -> List[int]:
    """Every increment from `start` up to but not including `end`."""
    return list(range(start, end, step)) if step > 0 else []


def _bookable(date: str, minute: int, now: datetime, earliest: datetime) -> bool:
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
        if not _bookable(date, minute, now, earliest):
            continue
        slots.append(_slot(business, date, minute, now, []))
        if len(slots) >= wanted:
            break
    return slots


def _reserved_slots(business: Business, job_type: JobType, duration: int,
                    date: str, employee_id: Optional[int], earliest: datetime,
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
        if not _bookable(date, minute, now, earliest):
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


# --- What the platform seeds ---------------------------------------------

def get_contact_field_types() -> List[ContactFieldType]:
    """The kinds of contact information a job type may ask a customer for.

    A business chooses from these rather than inventing them, which is why the
    kiosk can trust that a field marked verifiable can receive a code.
    """
    return [
        ContactFieldType(id=r.id, name=r.name, fieldType=r.field_type,
                         otpCapable=bool(r.otp_capable), sortOrder=r.sort_order)
        for r in db.get_contact_field_types()
    ]


def get_business_templates() -> List[BusinessTemplate]:
    """Starting points a new business may take its settings from."""
    return [
        BusinessTemplate(id=r.id, name=r.name, description=r.description,
                         config=json.loads(r.config_json))
        for r in db.get_business_templates()
    ]


def get_schedule_timeout_minutes() -> int:
    """How long a customer has to finish scheduling before their time is released."""
    value = db.get_system_config("schedule_timeout_minutes")
    return int(value) if value is not None else 10


def set_schedule_timeout_minutes(minutes: int) -> int:
    return db.set_system_config("schedule_timeout_minutes", str(minutes))


# --- Configuring a business ----------------------------------------------
#
# What an operator does before a customer can book: describe the business, say
# when it is open, offer work, and say who does it.

def create_business(name: str, timezone: str = "UTC",
                    slot_mode: str = "reserved") -> Business:
    """Start a business. Everything else it needs has a default."""
    return get_business(db.insert_business(name, timezone, slot_mode))


def get_business(business_id: int) -> Optional[Business]:
    row = db.get_business(business_id)
    return _business(row) if row is not None else None


def set_scheduling(business_id: int, slot_increment_minutes: int,
                   cutoff_days: int, min_booking_notice_hours: int,
                   buffer_minutes: int) -> Optional[Business]:
    """How far ahead, how soon, and how finely a customer may choose."""
    db.set_business_scheduling(business_id, slot_increment_minutes, cutoff_days,
                               min_booking_notice_hours, buffer_minutes)
    return get_business(business_id)


def set_operating_hours(business_id: int, day_of_week: int, open_time: str,
                        close_time: str, is_closed: bool = False) -> List[BusinessHours]:
    """When the business is open on one weekday.

    Under `unlimited` these bound the day. Under `reserved` they say when the
    counter is open, and the employees' own schedules decide what can be
    booked.
    """
    db.set_business_hours(business_id, day_of_week, open_time, close_time,
                          1 if is_closed else 0)
    return get_operating_hours(business_id)


def get_operating_hours(business_id: int) -> List[BusinessHours]:
    return [_hours(r) for r in db.get_business_hours(business_id)]


def close_on_holiday(business_id: int, name: str, date: str,
                     country_code: str = "US") -> None:
    """Observe a holiday, closing the business for that date."""
    year = int(date[:4])
    holiday_id = db.insert_system_holiday(country_code, country_code, name, date, year)
    db.observe_holiday(business_id, holiday_id, year)


# --- What the business offers --------------------------------------------

def create_job_type(business_id: int, name: str,
                    min_employees: int = 1) -> JobType:
    return get_job_type(db.insert_job_type(business_id, name, min_employees))


def get_job_type(job_type_id: int) -> Optional[JobType]:
    row = db.get_job_type(job_type_id)
    return _job_type(row) if row is not None else None


def add_job_type_size(job_type_id: int, name: str, duration_minutes: int,
                      cost: float) -> JobTypeSize:
    """A size is what carries the duration and the price."""
    return _size(db.get_job_type_size(
        db.insert_job_type_size(job_type_id, name, duration_minutes, cost)
    ))


# --- Who does the work ---------------------------------------------------

def create_employee(business_id: int, first_name: str, last_name: str,
                    include_in_schedule: bool = True) -> Employee:
    employee_id = db.insert_employee(business_id, first_name, last_name,
                                     1 if include_in_schedule else 0)
    return Employee(id=employee_id, businessId=business_id,
                    firstName=first_name, lastName=last_name,
                    includeInSchedule=include_in_schedule,
                    canManageOwnSchedule=False)


def allow_job_type(employee_id: int, job_type_id: int) -> None:
    """Say this employee can perform this work."""
    db.link_employee_to_job_type(job_type_id, employee_id)


def add_working_day(employee_id: int, day_of_week: int, start_time: str,
                    end_time: str) -> List[EmployeeSchedule]:
    db.insert_employee_schedule(employee_id, day_of_week, start_time, end_time)
    return get_working_days(employee_id)


def get_working_days(employee_id: int) -> List[EmployeeSchedule]:
    return [EmployeeSchedule(id=r.id, employeeId=r.employee_id,
                             dayOfWeek=r.day_of_week, startTime=r.start_time,
                             endTime=r.end_time)
            for r in db.get_employee_schedule(employee_id)]


def add_time_off(employee_id: int, date: str, start_time: str,
                 end_time: str) -> EmployeeTimeOff:
    """A stretch of one day this employee is not available."""
    window_id = db.insert_employee_time_off(employee_id, date, start_time, end_time)
    return EmployeeTimeOff(id=window_id, employeeId=employee_id, date=date,
                           startTime=start_time, endTime=end_time)


# --- Taking a booking ----------------------------------------------------

# What a customer sees on their appointment, and quotes to get back into it.
JOB_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOB_CODE_LENGTH = 6


def _job_code() -> str:
    """A short code a customer can read out over the phone.

    The alphabet leaves out the characters that are heard or seen as each
    other — I and 1, O and 0 — because this one is spoken aloud.
    """
    import secrets
    return "".join(secrets.choice(JOB_CODE_ALPHABET) for _ in range(JOB_CODE_LENGTH))


def _stamp(when: datetime) -> str:
    """A moment, as the database stores one."""
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _expiry(now: Optional[datetime]) -> str:
    """When a hold taken at `now` lapses."""
    return _stamp((now or datetime.utcnow())
                  + timedelta(minutes=get_schedule_timeout_minutes()))


def create_job_session(business_id: int, job_type_id: int,
                       size_id: Optional[int], scheduled_date: str,
                       scheduled_time: str,
                       employee_ids: Optional[List[int]] = None,
                       now: Optional[datetime] = None) -> JobSession:
    """Hold a time while the customer finishes scheduling.

    The job exists from here, pending, and the hold expires on its own after
    the platform's schedule timeout. Under `unlimited` nobody is allocated and
    the hold takes nothing from anyone — it is still created, so confirming
    works the same way in both modes.
    """
    duration = _duration_minutes(size_id)
    job_id = db.insert_scheduled_job(_job_code(), business_id, job_type_id,
                                     size_id, scheduled_date, scheduled_time,
                                     duration, "pending")
    for employee_id in employee_ids or []:
        db.assign_employee_to_job(job_id, employee_id)

    import secrets
    token = secrets.token_urlsafe(24)
    db.insert_job_session(job_id, token, _expiry(now))

    return _session(token)


def _session(session_token: str) -> Optional[JobSession]:
    """The hold and the appointment it is holding, as one shape."""
    row = db.get_session(session_token)
    if row is None:
        return None
    job = db.get_scheduled_job(row.job_id)
    return JobSession(sessionToken=session_token, jobId=job.id,
                      jobCode=job.job_code, scheduledDate=job.scheduled_date,
                      scheduledTime=job.scheduled_time,
                      expiresAt=row.expires_at,
                      employeeIds=db.get_job_employee_ids(job.id))


def _live_session(session_token: str, now: Optional[datetime] = None):
    """The hold, if it is still the customer's to use."""
    row = db.get_session(session_token)
    if row is None or row.expires_at <= _stamp(now or datetime.utcnow()):
        raise SessionExpired(
            "Your session has expired. Please choose a time again."
        )
    return row


def extend_session(session_token: str, now: Optional[datetime] = None) -> JobSession:
    """Give the customer the full timeout again, because they are still here."""
    _live_session(session_token, now)
    db.extend_session(session_token, _expiry(now))
    return _session(session_token)


def confirm_session(session_token: str,
                    contact: Optional[Dict[str, str]] = None,
                    now: Optional[datetime] = None) -> JobSession:
    """Turn a held time into a booking.

    `contact` is what the customer typed, keyed by the contact field's name —
    `{"Phone": "+15552340000"}`. It is stored with the appointment, and it is
    what a later lookup sends a code to.

    Finalising is what keeps the session record: the sweep removes lapsed
    holds whose appointment was never finished, and this one was.
    """
    row = _live_session(session_token, now)
    for name, value in (contact or {}).items():
        field = db.get_contact_field_type_by_name(name)
        if field is None:
            raise ValidationError(f"There is no contact field called {name}.")
        db.insert_job_contact(row.job_id, field[0], value)
    db.set_job_status(row.job_id, "confirmed")
    db.set_job_finalized(row.job_id)

    session = _session(session_token)
    session.confirmationSentTo = send_booking_confirmation(row.job_id)
    return session


def cleanup_expired_sessions() -> int:
    """Sweep lapsed holds nobody finished. Returns how many went.

    Hourly. The appointment row stays for analytics; only the hold goes.
    """
    return db.delete_expired_sessions()


# --- Changing an appointment ---------------------------------------------
#
# Minimum Change Notice says how close to the appointment a customer may still
# move or cancel it. It applies in both Time Slots modes — a technician already
# driving over is a wasted trip whether or not the time was taken from anyone
# else — and it binds the customer only. The operator changes an appointment
# whenever they like, which is what makes "call the business" useful advice.

def set_change_notice(business_id: int, minutes: int) -> Optional[Business]:
    """How many minutes before the start a customer may still make changes.

    Zero means up to the moment it starts.
    """
    db.set_business_change_notice(business_id, minutes)
    return get_business(business_id)


def get_appointment(job_id: int, now: Optional[datetime] = None) -> Optional[Appointment]:
    """A booking as the customer who made it sees it."""
    row = db.get_appointment(job_id)
    if row is None:
        return None
    return Appointment(
        id=row.id, jobCode=row.job_code, businessName=row.business_name,
        businessPhone=row.business_phone, jobTypeName=row.job_type_name,
        scheduledDate=row.scheduled_date, scheduledTime=row.scheduled_time,
        displayDate=display_date(row.scheduled_date),
        displayTime=display_time(row.scheduled_time),
        durationMinutes=row.duration_minutes, status=row.status,
        changesClosed=_changes_closed(row, now or datetime.now())
    )


def _changes_closed(row, now: datetime) -> bool:
    """Whether the customer's window for changing this has passed."""
    starts = datetime.strptime(f"{row.scheduled_date} {row.scheduled_time}",
                               "%Y-%m-%d %H:%M")
    return now > starts - timedelta(minutes=row.min_change_notice_minutes)


def _refuse_if_closed(job_id: int, as_operator: bool, now: Optional[datetime]):
    """Stop a customer acting inside the notice window.

    Returns the booking so the caller does not read it twice.
    """
    row = db.get_appointment(job_id)
    if row is None:
        raise ValidationError("That appointment no longer exists.")
    if not as_operator and db.get_job_locked_date(job_id) is not None:
        raise AppointmentLocked(
            "This appointment is locked. Please contact the business to make"
            " a change."
        )
    if not as_operator and _changes_closed(row, now or datetime.now()):
        raise ValidationError(
            "It is not possible to edit or cancel your appointment as it is too"
            " close to the scheduled appointment time. Please contact the"
            f" business at {row.business_phone or 'the number on your confirmation'}"
            " to make a change."
        )
    return row


def reschedule_appointment(job_id: int, scheduled_date: str, scheduled_time: str,
                           as_operator: bool = False,
                           now: Optional[datetime] = None) -> Optional[Appointment]:
    """Move an appointment to another time."""
    row = _refuse_if_closed(job_id, as_operator, now)
    db.set_job_schedule(job_id, scheduled_date, scheduled_time)
    _notify_customer(
        job_id,
        f"{row.business_name}: your {row.job_type_name} has moved to"
        f" {display_date(scheduled_date)} at {display_time(scheduled_time)}."
        f" Job code {row.job_code}."
    )
    return get_appointment(job_id, now=now)


def cancel_appointment(job_id: int, as_operator: bool = False,
                       now: Optional[datetime] = None) -> Optional[Appointment]:
    """Cancel an appointment, giving its time back under `reserved`."""
    _refuse_if_closed(job_id, as_operator, now)
    db.set_job_status(job_id, "cancelled")
    return get_appointment(job_id, now=now)


# --- Verifying a contact detail ------------------------------------------
#
# A code goes to what the customer typed, which is what proves the phone
# number or the address is theirs. Three tries, because somebody reading six
# digits off one screen and typing them into another will occasionally slip,
# and because an unlimited number of tries is not a check at all.

MAX_OTP_ATTEMPTS = 3
OTP_LENGTH = 6

# Where a code actually goes. The app wires the vendor layer in at startup;
# until it does, sending is a no-op rather than an error, so a business with no
# SMS or email vendor configured fails at the vendor check rather than here.
_otp_sender = None


def set_otp_sender(sender) -> None:
    """Wire up delivery. `sender(destination, code)`."""
    global _otp_sender
    _otp_sender = sender


def _hash_code(code: str, salt: str) -> str:
    import hashlib
    return hashlib.sha256((salt + code).encode()).hexdigest()


def send_otp(session_token: str, destination: str,
             now: Optional[datetime] = None) -> OtpResult:
    """Send a fresh code to `destination`, and start the attempts over.

    Asking for another code replaces the one before it. Two live codes at once
    would double the guesses an attacker gets for the same three attempts.
    """
    _live_session(session_token, now)

    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
    salt = secrets.token_hex(8)
    db.set_otp(session_token, f"{salt}:{_hash_code(code, salt)}")

    if _otp_sender is not None:
        _otp_sender(destination, code)
    return OtpResult(verified=False, attemptsRemaining=MAX_OTP_ATTEMPTS)


def verify_otp(session_token: str, code: str,
               now: Optional[datetime] = None) -> OtpResult:
    """Check a code against the one that was sent.

    A correct code spends no attempt; the three are for getting it wrong.
    """
    _live_session(session_token, now)
    record = db.get_otp(session_token)
    if record is None or record[0] is None:
        raise ValidationError("No code has been sent for this session.")

    stored, attempts, verified = record
    if verified:
        return OtpResult(verified=True,
                         attemptsRemaining=MAX_OTP_ATTEMPTS - attempts)
    if attempts >= MAX_OTP_ATTEMPTS:
        raise OTPMaxAttemptsExceeded(
            "That is too many attempts. Please ask for a new code."
        )

    salt, expected = stored.split(":", 1)
    if _hash_code(code, salt) != expected:
        db.count_otp_attempt(session_token)
        remaining = MAX_OTP_ATTEMPTS - (attempts + 1)
        if remaining <= 0:
            raise OTPMaxAttemptsExceeded(
                "That is too many attempts. Please ask for a new code."
            )
        raise OTPInvalid("That code is not right. Please try again.", remaining)

    db.set_otp_verified(session_token)
    return OtpResult(verified=True, attemptsRemaining=MAX_OTP_ATTEMPTS - attempts)


# --- Getting back into an appointment ------------------------------------
#
# A job code is not a secret. It is printed on a confirmation, read out over
# the phone, and short enough to guess at. So it identifies the appointment and
# proves nothing; a code sent to the contact detail the customer gave is what
# proves the booking is theirs.

ACCESS_CODE_MINUTES = 30
ACCESS_CODE_LENGTH = 6

# Live statuses. A cancelled or completed appointment has nothing to get back
# into, and saying so beats sending a code that leads nowhere.
ACTIVE_STATUSES = ("pending", "confirmed")


def _mask(channel: str, value: str) -> str:
    """Enough of a destination to recognise, not enough to learn.

    Someone who guessed a job code should not come away knowing the customer's
    phone number, and the customer should still know which of theirs it went
    to.
    """
    if channel == "email":
        name, _, domain = value.partition("@")
        return f"{name[:1]}{'•' * max(len(name) - 1, 1)}@{domain}"
    return f"{'•' * max(len(value) - 4, 0)}{value[-4:]}"


def _contact_channel(job_id: int):
    """Where to send a code, preferring the phone.

    A text reaches somebody standing at a counter; an email may not be read
    for hours.
    """
    contact = db.get_job_contact(job_id)
    for field_type, channel in (("phone", "sms"), ("email", "email")):
        for row in contact:
            if row.field_type == field_type and row.value.strip():
                return channel, row.value
    return None, None


def _active_job(job_code: str):
    """The appointment a job code names, if it is one that can be opened."""
    job = db.get_job_by_code(job_code)
    if job is None:
        raise JobNotFound("We could not find an appointment with that code.")
    if job.status not in ACTIVE_STATUSES:
        raise AppointmentInactive(
            "That appointment is no longer active. Please contact the business."
        )
    return job


def request_appointment_access(job_code: str, caller: Optional[str] = None,
                               now: Optional[datetime] = None) -> AccessCodeSent:
    """Send a single-use code to whoever booked this appointment.

    `caller` is whatever identifies the person submitting, and the throttle
    below is keyed on it. What fills it is the route's decision — see the plan
    under Open Decisions — and `None` turns the throttle off, which is what an
    operator-side call wants.
    """
    _refuse_if_blocked(caller, now)
    try:
        job = _active_job(job_code)
    except JobNotFound:
        # The miss that trips the block says so, rather than answering
        # not-found and refusing everything afterwards without explanation.
        if _count_miss(caller, now):
            raise CallerBlocked(
                "Too many attempts. Please try again tomorrow, or contact the"
                " business."
            )
        raise
    _refuse_if_locked(job)
    channel, destination = _contact_channel(job.id)
    if channel is None:
        raise NoContactChannel(
            "This appointment has no phone number or email address on it."
            " Please contact the business."
        )

    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(ACCESS_CODE_LENGTH))
    salt = secrets.token_hex(8)
    expires = _stamp((now or datetime.utcnow())
                     + timedelta(minutes=ACCESS_CODE_MINUTES))
    db.insert_access_code(job.id, f"{salt}:{_hash_code(code, salt)}", channel,
                          destination, expires)

    if _otp_sender is not None:
        _otp_sender(destination, code)
    return AccessCodeSent(channel=channel, sentTo=_mask(channel, destination))


def get_appointment_by_code(job_code: str,
                            now: Optional[datetime] = None) -> Optional[Appointment]:
    """The appointment a job code names, without proving anything.

    For an operator, and for a test that already knows the code is real. The
    customer's route is `verify_appointment_access`, which asks for proof.
    """
    job = db.get_job_by_code(job_code)
    return None if job is None else get_appointment(job.id, now=now)


def verify_appointment_access(job_code: str, code: str,
                              now: Optional[datetime] = None) -> Appointment:
    """Check a code and hand back the appointment it opens.

    A code opens the appointment once. Spending it on success is what stops a
    code shared or intercepted from being a standing key.
    """
    job = _active_job(job_code)
    _refuse_if_locked(job)
    record = db.get_latest_access_code(job.id)
    if record is None:
        raise CodeInvalid("Please ask for a code first.")

    moment = _stamp(now or datetime.utcnow())
    if record.used_date is not None:
        raise CodeSpent("That code has already been used. Please ask for a new one.")
    if record.expires_at <= moment:
        raise CodeExpired("That code has expired. Please ask for a new one.")

    salt, expected = record.code_hash.split(":", 1)
    if _hash_code(code, salt) != expected:
        db.count_access_attempt(record.id)
        db.insert_access_attempt(job.id, moment)
        window_opened = _stamp((now or datetime.utcnow())
                               - timedelta(seconds=ACCESS_ATTEMPT_WINDOW_SECONDS))
        if db.count_recent_access_attempts(job.id, window_opened) >= MAX_ACCESS_ATTEMPTS:
            _lock_and_notify(job, moment)
            raise AppointmentLocked(
                "This appointment is locked after too many incorrect attempts."
                " Please contact the business to make a change."
            )
        raise CodeInvalid("That code is not right. Please try again.")

    db.spend_access_code(record.id, moment)
    return get_appointment(job.id, now=now)


# --- Locking an appointment ----------------------------------------------
#
# Six wrong codes inside a minute is somebody working through the digits, not
# a customer mistyping. The appointment closes to the customer permanently and
# a notice goes out on every channel they gave, so the person whose booking it
# is hears about it.
#
# It is a rate rather than a total, which is why the attempts carry timestamps:
# six spread over an afternoon is a forgetful customer, and locking them out
# would be the rule doing harm.
#
# This replaces the three-attempt rule the kiosk applies while booking rather
# than sitting beside it. That one guards a contact detail being given; this
# one guards a booking that already exists.

MAX_ACCESS_ATTEMPTS = 6
ACCESS_ATTEMPT_WINDOW_SECONDS = 60


def _refuse_if_locked(job) -> None:
    if db.get_job_locked_date(job.id) is not None:
        raise AppointmentLocked(
            "This appointment is locked. Please contact the business to make"
            " a change."
        )


def _lock_and_notify(job, moment: str) -> None:
    """Shut the door and tell the customer it happened."""
    db.lock_job(job.id, moment)
    if _otp_sender is None:
        return
    # Every channel they gave, not the preferred one: this is the message that
    # explains why nothing works any more, and it should be hard to miss.
    for row in db.get_job_contact(job.id):
        if row.field_type in ("phone", "email") and row.value.strip():
            _otp_sender(row.value,
                        "Your appointment has been locked after too many"
                        " incorrect verification attempts. Please contact the"
                        " business to make a change.")


# --- Guessing at job codes -----------------------------------------------
#
# A wrong job code is somebody guessing, and guessing is the only way to find
# an appointment that is not yours. Three misses inside a minute blocks that
# caller from submitting any job code for a day — every code, not only the
# ones they tried, because the point is to stop the search rather than to
# protect one booking.
#
# Nothing is locked and nobody is notified: no appointment was found, so there
# is no customer to tell.
#
# The block is on the caller, which is the part with no good answer — see the
# plan under Open Decisions. This takes whatever the route hands it.

MAX_JOB_CODE_MISSES = 3
JOB_CODE_WINDOW_SECONDS = 60
JOB_CODE_BLOCK_HOURS = 24


def _refuse_if_blocked(caller: Optional[str], now: Optional[datetime]) -> None:
    """Stop a blocked caller before the job code is even looked up.

    Before, so that a valid code is refused too. A block that let the right
    answer through would be a way to test whether a guess was right.
    """
    if caller is None:
        return
    if db.is_caller_blocked(caller, _stamp(now or datetime.utcnow())):
        raise CallerBlocked(
            "Too many attempts. Please try again tomorrow, or contact the"
            " business."
        )


def _count_miss(caller: Optional[str], now: Optional[datetime]) -> bool:
    """Record a miss. Returns whether it was the one that tripped the block."""
    if caller is None:
        return False
    moment = now or datetime.utcnow()
    window_opened = _stamp(moment - timedelta(seconds=JOB_CODE_WINDOW_SECONDS))
    # Counted before this one is written, so the third miss is the one that
    # trips it rather than the fourth.
    earlier = db.count_recent_job_code_attempts(caller, window_opened)
    blocked_until = None
    if earlier + 1 >= MAX_JOB_CODE_MISSES:
        blocked_until = _stamp(moment + timedelta(hours=JOB_CODE_BLOCK_HOURS))
    db.insert_job_code_attempt(caller, _stamp(moment), blocked_until)
    return blocked_until is not None


# --- Repeating work ------------------------------------------------------
#
# A recurrence is a standing arrangement rather than a pile of appointments
# made years ahead. Instances are materialised a cutoff window at a time, as
# the horizon rolls forward, so a customer who stops after three months has not
# filled the calendar to 2030 — and a business that changes its hours has not
# already committed to the old ones.

def _recurrence(row: db.RecurrenceRow) -> Recurrence:
    return Recurrence(
        id=row.id, businessId=row.business_id, jobTypeId=row.job_type_id,
        jobTypeSizeId=row.job_type_size_id, intervalType=row.interval_type,
        daysOfWeek=json.loads(row.days_of_week_json) if row.days_of_week_json else [],
        preferredTime=row.preferred_time, isActive=bool(row.is_active)
    )


# What `materialize_recurrences` knows how to work out dates for. The column
# allows more — `biweekly | monthly | custom` — and each is refused on creation
# until it is built, because a recurrence that saves and then quietly books
# nothing is found out by the customer who did not get their appointment.
#
# `biweekly` needs an anchor the schema does not have: with only a window to
# work from, which weeks are "on" depends on when the job happens to run, so
# the same arrangement drifts between runs.
SUPPORTED_INTERVALS = ("daily", "weekly")


def create_recurrence(business_id: int, job_type_id: int,
                      size_id: Optional[int], interval_type: str,
                      preferred_time: str,
                      days_of_week: Optional[List[int]] = None) -> Recurrence:
    """Set up repeating work. Nothing is booked until it is materialised."""
    if interval_type not in SUPPORTED_INTERVALS:
        raise ValidationError(
            f"Repeating {interval_type} is not available yet."
            f" Please choose {' or '.join(SUPPORTED_INTERVALS)}."
        )
    if interval_type == "weekly" and not days_of_week:
        raise ValidationError("Please choose which days of the week to repeat on.")
    days = json.dumps(days_of_week) if days_of_week else None
    return _recurrence(db.get_recurrence(
        db.insert_recurrence(business_id, job_type_id, size_id, interval_type,
                             days, preferred_time)
    ))


def cancel_recurrence(recurrence_id: int) -> Optional[Recurrence]:
    """Stop making new appointments from this arrangement.

    The ones already made stay: customers are expecting them, and an operator
    who wanted them gone cancels them.
    """
    db.set_recurrence_active(recurrence_id, 0)
    row = db.get_recurrence(recurrence_id)
    return _recurrence(row) if row is not None else None


def get_recurring_jobs(recurrence_id: int) -> List[RecurringJob]:
    return [
        RecurringJob(id=r.id, jobCode=r.job_code, scheduledDate=r.scheduled_date,
                     scheduledTime=r.scheduled_time, status=r.status,
                     employeeIds=db.get_job_employee_ids(r.id))
        for r in db.get_jobs_for_recurrence(recurrence_id)
    ]


def get_unassigned_jobs(business_id: int) -> List[RecurringJob]:
    """Live appointments with nobody on them, for Needs Attention."""
    return [
        RecurringJob(id=r.id, jobCode=r.job_code, scheduledDate=r.scheduled_date,
                     scheduledTime=r.scheduled_time, status=r.status)
        for r in db.get_unassigned_jobs(business_id)
    ]


def _recurrence_dates(recurrence: Recurrence, start: str, last: str) -> List[str]:
    """The dates this arrangement falls on, inside a window."""
    dates, date = [], start
    while date <= last:
        weekday = day_of_week(date)
        if recurrence.intervalType == "daily":
            dates.append(date)
        elif weekday in recurrence.daysOfWeek:
            dates.append(date)
        date = _next_day(date)
    return dates


def materialize_recurrences(now: Optional[datetime] = None) -> int:
    """Make the appointments each arrangement is due, inside its cutoff window.

    Runs on a schedule. Returns how many were created, which is nothing on a
    run where the horizon has not moved.

    An appointment nobody is free for is still made, and left unassigned: a
    customer with a standing arrangement expects their slot, and an operator
    would rather see it in Needs Attention than find out it never existed.
    """
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    created = 0

    for row in db.get_active_recurrences():
        recurrence = _recurrence(row)
        business_row = db.get_business(recurrence.businessId)
        if business_row is None:
            continue
        business = _business(business_row)
        last = (now + timedelta(days=business.cutoffDays)).strftime("%Y-%m-%d")

        duration = _duration_minutes(recurrence.jobTypeSizeId)
        for date in _recurrence_dates(recurrence, today, last):
            if db.recurrence_instance_exists(recurrence.id, date):
                continue
            job_id = db.insert_recurring_job(
                _job_code(), business.id, recurrence.jobTypeId,
                recurrence.jobTypeSizeId, date, recurrence.preferredTime,
                duration, recurrence.id
            )
            for employee_id in _free_for(business, recurrence, date, duration, now):
                db.assign_employee_to_job(job_id, employee_id)
            created += 1
    return created


def _free_for(business: Business, recurrence: Recurrence, date: str,
              duration: int, now: datetime) -> List[int]:
    """Who could take this instance, or nobody.

    Asked of the same availability the kiosk asks, so a recurrence cannot be
    assigned someone the booking screen would refuse.
    """
    slots = get_available_slots(business.id, recurrence.jobTypeId,
                                recurrence.jobTypeSizeId, limit=100,
                                from_date=date, now=now)
    for slot in slots:
        if slot.date == date and slot.time == recurrence.preferredTime:
            return slot.employeeIds
    return []


# --- Telling the customer it is booked -----------------------------------
#
# Two settings decide what goes out, and both have to agree: the business turns
# a channel on, and the customer has to have given something to send to.
# Enabling both does not promise both — a job type that never asks for an email
# sends a text and nothing else.

def set_confirmation_channels(business_id: int, by_sms: bool,
                              by_email: bool) -> Optional[Business]:
    """Which channels a booking confirmation goes out on. Either, both, neither."""
    db.set_business_confirmation(business_id, 1 if by_sms else 0,
                                 1 if by_email else 0)
    return get_business(business_id)


def set_business_phone(business_id: int, phone: str) -> Optional[Business]:
    """The number a customer is told to call."""
    db.set_business_phone(business_id, phone)
    return get_business(business_id)


def _confirmation_message(row: db.ConfirmationJobRow) -> str:
    """What the customer is sent.

    No link. The job code is the credential, and a link in a message that can
    be forwarded is a second one nobody asked for.
    """
    return (
        f"{row.business_name}: your {row.job_type_name} is booked for"
        f" {display_date(row.scheduled_date)} at"
        f" {display_time(row.scheduled_time)}."
        f" Your job code is {row.job_code}."
        f" Call {row.business_phone or 'the business'} to make a change."
    )


def send_booking_confirmation(job_id: int) -> List[ConfirmationSent]:
    """Send the confirmation, on each channel the business and customer share.

    Returns what went out, masked, which is what the kiosk shows. An empty list
    means nothing was sent and the customer should keep their job code.
    """
    row = db.get_confirmation_details(job_id)
    if row is None:
        return []

    wanted = {"sms": bool(row.confirm_by_sms), "email": bool(row.confirm_by_email)}
    message = _confirmation_message(row)

    out = []
    for field_type, channel in (("phone", "sms"), ("email", "email")):
        if not wanted[channel]:
            continue
        for contact in db.get_job_contact(job_id):
            if contact.field_type == field_type and contact.value.strip():
                if _otp_sender is not None:
                    _otp_sender(contact.value, message)
                out.append(ConfirmationSent(channel=channel,
                                            sentTo=_mask(channel, contact.value)))
                break
    return out


# --- Money against an appointment ----------------------------------------
#
# `payment_status` is derived from what has been taken rather than set by hand,
# so it cannot disagree with the transactions underneath it. The one exception
# is writing off, which is a decision rather than an arithmetic result — and
# even that gives way if money turns up later.

# Amounts are compared with a tolerance. A deposit of ten percent of a price
# ending in a third of a penny is exact in nobody's arithmetic, and a customer
# who paid what they were asked should not be a penny short of `deposit_paid`.
PENNY = 0.005

WRITTEN_OFF = "written_off"


def set_job_type_deposit(job_type_id: int, deposit_type: str,
                         deposit_amount: float) -> None:
    """Ask for a deposit on this job type. `fixed` is an amount, `percent` a rate."""
    if deposit_type not in ("fixed", "percent"):
        raise ValidationError("A deposit is either a fixed amount or a percentage.")
    db.set_job_type_deposit(job_type_id, deposit_type, deposit_amount)


def _deposit_due(cost: db.JobCostRow) -> Optional[float]:
    """What a deposit on this job comes to, or `None` if none is asked for."""
    if not cost.deposit_required or cost.deposit_amount is None:
        return None
    if cost.deposit_type == "percent":
        return (cost.cost or 0.0) * cost.deposit_amount / 100.0
    return cost.deposit_amount


def _payment_status(job_id: int) -> str:
    """Where the appointment stands, worked out from what has been taken."""
    cost = db.get_job_cost(job_id)
    if cost is None:
        return "unpaid"
    paid = db.get_paid_total(job_id)
    total = cost.cost or 0.0

    if paid + PENNY >= total and total > 0:
        return "fully_paid"
    deposit = _deposit_due(cost)
    if deposit is not None and paid + PENNY >= deposit:
        return "deposit_paid"
    return "unpaid"


def _payment_result(job_id: int) -> PaymentResult:
    cost = db.get_job_cost(job_id)
    return PaymentResult(jobId=job_id,
                         paymentStatus=db.get_payment_status(job_id),
                         paidTotal=db.get_paid_total(job_id),
                         cost=(cost.cost or 0.0) if cost else 0.0)


def record_payment(job_id: int, amount: float, method: str,
                   collected_by_user_id: Optional[int] = None,
                   note: Optional[str] = None) -> PaymentResult:
    """Take money against an appointment and restate where it stands.

    A payment after a write-off settles the appointment after all: the write-off
    said the business had stopped chasing it, not that it refuses to be paid.
    """
    if method not in ("stripe", "cash", "other"):
        raise ValidationError("A payment is taken by card, in cash, or some other way.")
    if amount <= 0:
        raise ValidationError("A payment has to be for something.")

    db.insert_transaction(job_id, amount, method, collected_by_user_id, note)
    db.set_payment_status(job_id, _payment_status(job_id))
    return _payment_result(job_id)


def write_off_payment(job_id: int) -> PaymentResult:
    """Stop chasing the balance. What was taken stays on the record."""
    db.set_payment_status(job_id, WRITTEN_OFF)
    return _payment_result(job_id)


def get_payments(job_id: int) -> List[Payment]:
    return [
        Payment(id=r.id, amount=r.amount, method=r.method, date=r.create_date,
                collectedBy=r.collected_by_user_id)
        for r in db.get_transactions(job_id)
    ]


# --- Finishing an appointment --------------------------------------------
#
# A business either marks work done or lets the clock do it. Under `auto` an
# appointment finishes because its end time passed, which is what keeps a
# calendar honest for a business that never marks anything.

COMPLETION_MODES = ("auto", "manual")


def set_completion_mode(business_id: int, mode: str) -> Optional[Business]:
    if mode not in COMPLETION_MODES:
        raise ValidationError("Work is finished automatically or by hand.")
    db.set_business_completion_mode(business_id, mode)
    return get_business(business_id)


def _receipt_message(row: db.ConfirmationJobRow, paid: float) -> str:
    return (
        f"{row.business_name}: your {row.job_type_name} on"
        f" {display_date(row.scheduled_date)} is complete."
        f" Paid: ${paid:.2f}. Job code {row.job_code}."
    )


def _notify_customer(job_id: int, message: str) -> None:
    """Send to whatever the customer gave, preferring the phone."""
    if _otp_sender is None:
        return
    channel, destination = _contact_channel(job_id)
    if channel is not None:
        _otp_sender(destination, message)


def complete_job(job_id: int, now: Optional[datetime] = None) -> Optional[Appointment]:
    """Mark work done, and send the customer a receipt."""
    row = db.get_appointment(job_id)
    if row is None:
        raise ValidationError("That appointment no longer exists.")
    if row.status == "cancelled":
        raise ValidationError("That appointment was cancelled.")

    db.set_job_status(job_id, "completed")
    details = db.get_confirmation_details(job_id)
    if details is not None:
        _notify_customer(job_id, _receipt_message(details, db.get_paid_total(job_id)))
    return get_appointment(job_id, now=now)


def complete_finished_jobs(now: Optional[datetime] = None) -> int:
    """Finish appointments whose time has passed, at businesses set to `auto`.

    Runs on a schedule. Returns how many were finished.
    """
    now = now or datetime.now()
    finished = 0
    for row in db.get_confirmed_jobs_for_auto_completion():
        ends = (datetime.strptime(f"{row.scheduled_date} {row.scheduled_time}",
                                  "%Y-%m-%d %H:%M")
                + timedelta(minutes=row.duration_minutes))
        if now > ends:
            complete_job(row.id, now=now)
            finished += 1
    return finished


# --- Finding an appointment ----------------------------------------------

def search_jobs(business_id: int, from_date: Optional[str] = None,
                to_date: Optional[str] = None, status: Optional[str] = None,
                job_type_id: Optional[int] = None,
                job_code: Optional[str] = None,
                limit: int = 200) -> List[JobSearchResult]:
    """Appointments matching what the operator narrowed by.

    An inverted range is refused rather than answered with nothing found.
    "No appointments" to a range that cannot contain any tells the operator
    their data is missing, when their dates are backwards.

    An open range is a range: one end, or neither, constrains what it can.

    `YYYY-MM-DD` compares correctly as a string, so no parsing is needed.
    """
    if from_date and to_date and from_date > to_date:
        raise InvalidDateRange("The From date has to be on or before the To date.")

    return [
        JobSearchResult(id=r.id, jobCode=r.job_code, jobTypeName=r.job_type_name,
                        scheduledDate=r.scheduled_date,
                        scheduledTime=r.scheduled_time,
                        displayDate=display_date(r.scheduled_date),
                        displayTime=display_time(r.scheduled_time),
                        status=r.status, paymentStatus=r.payment_status)
        for r in db.search_jobs(business_id, from_date, to_date, status,
                                job_type_id, job_code, limit)
    ]


# --- What the business took ----------------------------------------------
#
# Revenue is money that arrived, not money that was owed. A written-off job
# leaves whatever was paid in revenue and the unpaid balance in write-offs, so
# the two columns together account for the work rather than double-counting it.

QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


def _period(year: int, quarter: Optional[int]) -> tuple:
    """The first and last date of a year, or of one quarter of it."""
    if quarter is None:
        return f"{year}-01-01", f"{year}-12-31"
    if quarter not in QUARTER_MONTHS:
        raise ValidationError("A quarter is 1, 2, 3 or 4.")
    first, last = QUARTER_MONTHS[quarter]
    end_day = 31 if last in (3, 12) else 30
    return f"{year}-{first:02d}-01", f"{year}-{last:02d}-{end_day:02d}"


def get_financial_report(business_id: int, year: int,
                         quarter: Optional[int] = None) -> FinancialReport:
    """Revenue, write-offs and the number of appointments over a period."""
    from_date, to_date = _period(year, quarter)
    rows = db.get_jobs_in_period(business_id, from_date, to_date)

    revenue = sum(r.paid for r in rows)
    written_off = sum(max((r.cost or 0.0) - r.paid, 0.0)
                      for r in rows if r.payment_status == WRITTEN_OFF)
    return FinancialReport(year=year, quarter=quarter, fromDate=from_date,
                           toDate=to_date, revenue=revenue,
                           writeOffs=written_off, jobCount=len(rows))


CSV_HEADERS = ("Job Code", "Date", "Service", "Status", "Payment Status",
               "Cost", "Paid")


def _csv_value(value) -> str:
    """One field, quoted when it would otherwise break the columns."""
    text = "" if value is None else str(value)
    if any(c in text for c in (",", '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


def export_financial_report(business_id: int, year: int,
                            quarter: Optional[int] = None) -> str:
    """The same period as a CSV, one row per appointment."""
    from_date, to_date = _period(year, quarter)
    lines = [",".join(CSV_HEADERS)]
    for r in db.get_jobs_in_period(business_id, from_date, to_date):
        lines.append(",".join(_csv_value(v) for v in (
            r.job_code, r.scheduled_date, r.job_type_name, r.status,
            r.payment_status, f"{r.cost or 0.0:.2f}", f"{r.paid:.2f}"
        )))
    return "\n".join(lines) + "\n"


# --- Is this employee free? ----------------------------------------------
#
# The same three facts slot availability rests on, asked of one employee: the
# days they work, the windows they are away, and whether they are in the
# schedule at all. Somebody out of the schedule is never available, whatever
# their working days say — which is what the flag is for.

def is_employee_available(employee_id: int, date: str, time: str,
                          duration_minutes: int,
                          buffer_minutes: int = 0) -> bool:
    """Whether this employee could take on a stretch of a day."""
    row = db.get_employee(employee_id)
    if row is None or not row.include_in_schedule:
        return False

    start = to_minutes(time)
    end = start + duration_minutes + buffer_minutes
    weekday = day_of_week(date)

    shifts = [(to_minutes(s.start_time), to_minutes(s.end_time))
              for s in db.get_employee_schedule(employee_id)
              if s.day_of_week == weekday]
    if not any(shift[0] <= start and end <= shift[1] for shift in shifts):
        return False

    away = [(to_minutes(t.start_time), to_minutes(t.end_time))
            for t in db.get_employee_time_off(employee_id, date)]
    if any(overlaps(start, end, *window) for window in away):
        return False

    committed = db.get_booked_intervals([employee_id], date)
    for interval in committed:
        held = to_minutes(interval.scheduled_time)
        if overlaps(start, end, held, held + interval.duration_minutes + buffer_minutes):
            return False
    return True


# --- Starting from a template --------------------------------------------
#
# A template is a set of opinions, not a full configuration: it writes the
# settings it has a view on and leaves the rest as they were. That is why
# applying a second one on top of a first does not undo it.

TEMPLATE_SETTERS = {
    "slotMode": lambda business_id, value: db.set_business_slot_mode(business_id, value),
}


def apply_business_template(business_id: int, template_id: int) -> Optional[Business]:
    """Write a template's settings onto a business."""
    row = db.get_business_template(template_id)
    if row is None:
        raise ValidationError("That business type is no longer available.")
    business = get_business(business_id)
    if business is None:
        raise ValidationError("That business no longer exists.")

    config = json.loads(row.config_json)

    if "slotMode" in config:
        db.set_business_slot_mode(business_id, config["slotMode"])

    # The four scheduling numbers are written together, so anything the
    # template is silent about keeps the value the business already had.
    db.set_business_scheduling(
        business_id,
        config.get("slotIncrementMinutes", business.slotIncrementMinutes),
        config.get("cutoffDays", business.cutoffDays),
        config.get("minBookingNoticeHours", business.minBookingNoticeHours),
        config.get("bufferMinutes", business.bufferMinutes)
    )

    flags = db.get_business_flags(business_id) or (0, 0)
    db.set_business_employee_selection(
        business_id,
        1 if config.get("allowCustomerEmployeeSelection", bool(flags[0])) else 0,
        1 if config.get("notifyEmployees", bool(flags[1])) else 0
    )
    return get_business(business_id)
