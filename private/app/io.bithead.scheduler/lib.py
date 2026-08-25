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
                    now: Optional[datetime] = None) -> JobSession:
    """Turn a held time into a booking.

    Finalising is what keeps the session record: the sweep removes lapsed
    holds whose appointment was never finished, and this one was.
    """
    row = _live_session(session_token, now)
    db.set_job_status(row.job_id, "confirmed")
    db.set_job_finalized(row.job_id)
    return _session(session_token)


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
    _refuse_if_closed(job_id, as_operator, now)
    db.set_job_schedule(job_id, scheduled_date, scheduled_time)
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
