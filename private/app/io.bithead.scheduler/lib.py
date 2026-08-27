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

from datetime import date as _date, datetime, timedelta
from typing import Any, Dict, List, Optional

from . import db
from .model import *

# A job may be pending without holding anything: the customer opened the form
# and walked away. `db.get_booked_intervals` decides that by the session, which
# is the only place the timeout is applied.
HELD_STATUSES = ("pending", "confirmed")


class ValidationError(Exception):
    """Input that cannot be accepted, with a message meant for whoever asked."""


class Blocked(Exception):
    """Understood, and refused because of the state of something else.

    `blockers` names what is in the way, so the operator is told what to deal
    with rather than that it did not work.
    """

    def __init__(self, reason, blockers=None):
        super().__init__(reason)
        self.reason = reason
        self.blockers = blockers or []


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
                       durationMinutes=row.duration_minutes, cost=row.cost,
                       sortOrder=row.sort_order)


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
                        until_date: Optional[str] = None,
                        now: Optional[datetime] = None) -> List[Slot]:
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
        slots.extend(_slots_on(business, job_type, duration, date, hours,
                               employee_id, earliest, now, wanted))
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

# --- What a customer's kiosk is told --------------------------------------
#
# A narrower view of the same business. The kiosk is shown what it needs to
# draw and to behave by, and the conclusions rather than what they were drawn
# from — `configured` in place of the tasks, and the times themselves in place
# of the schedules they came from.


def get_kiosk(business_id: int) -> Optional[Kiosk]:
    """What a customer's screen needs to open against a business."""
    row = db.get_business_config(business_id)
    if row is None:
        return None
    return Kiosk(
        businessId=row.id,
        name=row.name,
        phone=row.phone or "",
        description=row.description or "",
        slotIncrementMinutes=row.slot_increment_minutes,
        cutoffDays=row.cutoff_days,
        minBookingNoticeHours=row.min_booking_notice_hours,
        minChangeNoticeMinutes=row.min_change_notice_minutes,
        allowCustomerEmployeeSelection=bool(row.allow_customer_employee_selection),
        # The hold's length comes from the platform, and the countdown the
        # customer watches is drawn from it — so the two agree by construction.
        scheduleTimeoutMinutes=get_schedule_timeout_minutes(),
        slotMode=row.slot_mode,
        operatingHours=get_operating_hours(business_id),
        configured=get_setup(business_id).configured,
    )


def get_kiosk_job_types(business_id: int) -> List[KioskJobTypesJobType]:
    """The services a customer may choose from.

    Active ones. A job type is created inactive by the form that owns it, so a
    draft somebody abandoned mid-edit is already excluded by the same flag the
    operator toggles.
    """
    return [
        KioskJobTypesJobType(
            id=j.id,
            name=j.name,
            iconUrl=None,
            sizes=get_job_type_sizes(j.id),
            contactFields=get_job_type_contact_fields(j.id),
            attributes=get_job_type_attributes(j.id),
            depositRequired=bool(db.get_job_type_detail(j.id).deposit_required),
        )
        for j in get_job_types(business_id, active_only=True)
    ]


def get_kiosk_employees(business_id: int) -> List[AdminJobTypeEmployee]:
    """Who a customer may ask for.

    Only those in the schedule. Somebody taken out of it is off the kiosk for
    the same reason they are off the availability search — they are not being
    booked.
    """
    return [
        AdminJobTypeEmployee(id=e.id, firstName=e.firstName, lastName=e.lastName)
        for e in get_employees(business_id) if e.includeInSchedule
    ]


def _month_bounds(year: int, month: int) -> tuple:
    """The first and last dates of a month, as `YYYY-MM-DD`."""
    first = _date(year, month, 1)
    last = _date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def get_kiosk_calendar(business_id: int, job_type_id: int,
                       size_id: Optional[int] = None,
                       employee_id: Optional[int] = None,
                       year: int = 0, month: int = 0,
                       now: Optional[datetime] = None) -> KioskCalendar:
    """Which days of a month a customer may choose from.

    Asked of the same availability the times come from, so a day the calendar
    offers has a time behind it. The month bounds the search rather than
    filtering it afterwards — a business open every day would otherwise need
    every slot in the year computed to answer about July.
    """
    start, end = _month_bounds(year, month)
    slots = get_available_slots(business_id, job_type_id, size_id, employee_id,
                                limit=0, from_date=start, until_date=end,
                                now=now)
    return KioskCalendar(
        year=year, month=month,
        availableDays=sorted({int(s.date[8:10]) for s in slots}),
    )


def get_kiosk_day_slots(business_id: int, job_type_id: int,
                        size_id: Optional[int] = None,
                        employee_id: Optional[int] = None,
                        date: str = "",
                        now: Optional[datetime] = None) -> KioskDaySlots:
    """The times on the one day a customer picked."""
    slots = get_available_slots(business_id, job_type_id, size_id, employee_id,
                                limit=0, from_date=date, until_date=date,
                                now=now)
    return KioskDaySlots(
        date=date,
        slots=[KioskDaySlotsSlot(time=s.time, displayTime=s.displayTime)
               for s in slots],
    )


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
    """How long a hold lasts before the time is released.

    A hold with no end is a time nobody else can take, so there is a floor of
    one minute rather than none.
    """
    if minutes < 1:
        raise ValidationError("A hold lasts at least a minute.")
    db.set_system_config("schedule_timeout_minutes", str(minutes))
    return minutes


# --- What every business chooses from -------------------------------------
#
# The contact field types are seeded once per installation and shared by every
# business. A business picks from them; the platform decides what there is to
# pick.

# The kinds a screen knows how to draw.
CONTACT_FIELD_TYPES = ("text", "phone", "email", "address_line",
                       "city", "state", "zip")

# A code reaches a phone or an inbox, and nothing else.
OTP_REACHABLE = ("phone", "email")


def _check_contact_field_type(name: str, field_type: str, otp_capable: bool,
                              field_id: Optional[int] = None):
    if not name.strip():
        raise ValidationError("Please name the field.")
    if field_type not in CONTACT_FIELD_TYPES:
        raise ValidationError(
            f"A field is one of: {', '.join(CONTACT_FIELD_TYPES)}.")
    if otp_capable and field_type not in OTP_REACHABLE:
        raise ValidationError(
            f"A verification code reaches a {' or a '.join(OTP_REACHABLE)}.")

    # Two fields of the same name are two boxes a customer cannot tell apart.
    for existing in db.get_contact_field_types():
        if existing.name.lower() == name.strip().lower() \
                and existing.id != field_id:
            raise ValidationError(f"There is already a {existing.name} field.")


def add_contact_field_type(name: str, field_type: str,
                           otp_capable: bool = False) -> ContactFieldType:
    """Offer every business one more kind of detail to ask for."""
    _check_contact_field_type(name, field_type, otp_capable)
    field_id = db.insert_contact_field_type(
        name.strip(), field_type, 1 if otp_capable else 0,
        db.next_contact_field_type_sort_order())
    return [f for f in get_contact_field_types() if f.id == field_id][0]


def update_contact_field_type(field_id: int, name: str, field_type: str,
                              otp_capable: bool = False) -> ContactFieldType:
    if db.get_contact_field_type(field_id) is None:
        raise ValidationError("That field no longer exists.")
    _check_contact_field_type(name, field_type, otp_capable, field_id)
    db.set_contact_field_type(field_id, name.strip(), field_type,
                              1 if otp_capable else 0)
    return [f for f in get_contact_field_types() if f.id == field_id][0]


def delete_contact_field_type(field_id: int) -> None:
    """Stop offering it.

    A field a job type is asking for stays: removing it would leave a booking
    form asking for something the platform no longer has a name for.
    """
    if db.get_contact_field_type(field_id) is None:
        raise ValidationError("That field no longer exists.")
    asking = db.count_job_types_asking_for(field_id)
    if asking:
        raise ValidationError(
            f"{asking} job type(s) ask for this field. Remove it from them first.")
    db.delete_contact_field_type(field_id)


def reorder_contact_field_types(field_ids: List[int]) -> List[ContactFieldType]:
    """Ask for them in this order, everywhere.

    The whole order arrives each time, as the job type's own reorder does.
    """
    current = [f.id for f in db.get_contact_field_types()]
    if sorted(field_ids) != sorted(current):
        raise ValidationError("That order no longer matches the fields there are.")
    for position, field_id in enumerate(field_ids):
        db.set_contact_field_type_sort_order(field_id, position)
    return get_contact_field_types()


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

def get_business_holidays(business_id: int, year: int,
                          country_code: str = "US") -> List[Holiday]:
    """The year's holidays, and which of them this business closes on."""
    observed = set(db.get_observed_holiday_ids(business_id, year))
    return [
        Holiday(id=r.id, name=r.name, date=r.date, selected=r.id in observed)
        for r in db.get_system_holidays(year, country_code)
    ]


def set_business_holidays(business_id: int, year: int,
                          holiday_ids: List[int],
                          country_code: str = "US") -> List[Holiday]:
    """Close on exactly these, and open on the rest.

    The year's choices are replaced rather than added to, because the screen
    sends what is ticked — a holiday missing from the list is one the owner
    unticked, and it has to re-open.
    """
    chosen = []
    for holiday_id in holiday_ids:
        holiday = db.get_system_holiday(holiday_id)
        if holiday is None:
            raise ValidationError("That holiday no longer exists.")
        if holiday.year != year:
            raise ValidationError(
                f"{holiday.name} falls in {holiday.year}, not {year}.")
        # The same holiday ticked twice is still one closed day.
        if holiday_id not in chosen:
            chosen.append(holiday_id)

    db.clear_observed_holidays(business_id, year)
    for holiday_id in chosen:
        db.observe_holiday(business_id, holiday_id, year)
    return get_business_holidays(business_id, year, country_code)


# --- Customers -----------------------------------------------------------
#
# A customer is a business's own record of somebody it has served. Two
# businesses that serve the same person hold two rows: neither is entitled to
# know the other has them.

CUSTOMER_FIELDS = {
    "firstName": "first_name",
    "lastName": "last_name",
    "phone": "phone",
    "email": "email",
    "addressLine1": "address_line1",
    "addressLine2": "address_line2",
    "city": "city",
    "state": "state",
    "zip": "zip",
}

CUSTOMER_REQUIRED = {"firstName", "lastName"}


def _customer(row: "db.CustomerRow") -> Customer:
    return Customer(
        id=row.id,
        firstName=row.first_name,
        lastName=row.last_name,
        phone=row.phone or "",
        email=row.email or "",
        hasBossAccount=row.user_id is not None,
    )


def _note(row: "db.CustomerNoteRow") -> Note:
    return Note(
        id=row.id,
        note=row.note,
        # Who wrote it, once there is a way to ask. Sign-in is not wired
        # through — `_operator_business` carries the same placeholder — and a
        # user id is not a name, so this stays empty rather than showing one.
        createdBy="",
        date=row.create_date[:10],
    )


def create_customer(business_id: int, first_name: str, last_name: str,
                    phone: Optional[str] = None, email: Optional[str] = None,
                    user_id: Optional[int] = None) -> Customer:
    """Record somebody this business has served."""
    if not first_name.strip():
        raise ValidationError("Please provide a first name.")
    customer_id = db.insert_customer(business_id, first_name.strip(),
                                     last_name.strip(), phone, email, user_id)
    return _customer(db.get_customer(customer_id))


def get_customers(business_id: int, term: Optional[str] = None) -> List[Customer]:
    return [_customer(r) for r in db.get_customers(business_id, term)]


def get_customer(customer_id: int) -> Optional[AdminCustomer]:
    """One customer, with what has been written down and what they have booked."""
    row = db.get_customer(customer_id)
    if row is None:
        return None
    return AdminCustomer(
        id=row.id,
        firstName=row.first_name,
        lastName=row.last_name,
        phone=row.phone or "",
        email=row.email or "",
        addressLine1=row.address_line1 or "",
        addressLine2=row.address_line2 or "",
        city=row.city or "",
        state=row.state or "",
        zip=row.zip or "",
        hasBossAccount=row.user_id is not None,
        notes=[_note(n) for n in db.get_customer_notes(customer_id)],
        appointments=[
            AdminCustomerAppointment(
                id=a.id,
                jobCode=a.job_code,
                jobType=a.job_type,
                scheduledDate=a.scheduled_date,
                displayDate=display_date(a.scheduled_date),
                displayTime=display_time(a.scheduled_time),
                status=a.status,
            )
            for a in db.get_customer_appointments(customer_id)
        ],
    )


def update_customer(customer_id: int, details: dict) -> Optional[AdminCustomer]:
    """Change a customer's contact details.

    Refused outright when a BOSS account owns them: the account holder
    maintains their own details, and an operator editing them would be writing
    over somebody else's record of themselves.
    """
    row = db.get_customer(customer_id)
    if row is None:
        raise ValidationError("That customer no longer exists.")
    if row.user_id is not None:
        raise ValidationError(
            "This customer keeps their own details through their BOSS account.")

    unknown = set(details) - set(CUSTOMER_FIELDS)
    if unknown:
        raise ValidationError(
            f"Not a customer detail: {', '.join(sorted(unknown))}.")

    columns = {}
    for field, value in details.items():
        if field in CUSTOMER_REQUIRED:
            value = str(value).strip()
            if not value:
                raise ValidationError("Please provide a first and last name.")
        columns[CUSTOMER_FIELDS[field]] = value

    db.set_customer(customer_id, columns)
    return get_customer(customer_id)


def _phone_digits(phone: str) -> str:
    """A phone number reduced to what identifies it.

    The punctuation goes, and so does anything before the last ten digits —
    the same person writes `(555) 234-5678` one time and `+1 555 234 5678` the
    next, and a country code is not what tells two people apart.
    """
    return "".join(c for c in phone if c.isdigit())[-10:]


def find_or_create_customer(business_id: int, contact: Dict[str, str],
                            user_id: Optional[int] = None) -> Customer:
    """The business's record for whoever this booking is for.

    **A signed-in account first**, when there is one. It is the only mark that
    is not an inference: the customer is who BOSS says they are, whatever the
    booking form happened to ask for. A job type that never asks for an email
    would otherwise leave a record nobody could match later.

    **Email second.** An address is one person across the whole of BOSS — it is
    what a BOSS account is keyed on — so a match on it cannot merge two people,
    and a business should never hold two records under one address.

    **Phone second, and only when it does not contradict.** A number is a
    weaker mark: a household shares one and a number gets reassigned. So a
    phone match is accepted only when the record it found does not already
    carry a *different* email. A booking that gives an address nobody holds,
    at a number somebody does, is the ordinary case of two people at one number
    — and joining them would put one person's history on another's screen.

    A booking with neither still gets a record. The operator needs somebody to
    call the appointment about, and a name with nothing behind it is still that.
    """
    email = (contact.get("Email") or "").strip()
    phone = (contact.get("Phone") or "").strip()

    def theirs(candidate) -> bool:
        """Whether a record found by a weaker mark can be this person's.

        A record already held by another account is not, whatever address the
        booking typed — the account is the stronger claim. Neither is one
        carrying a different email, which is the record saying so itself.
        """
        if candidate is None:
            return False
        if (user_id is not None and candidate.user_id is not None
                and candidate.user_id != user_id):
            return False
        return not (email and candidate.email
                    and candidate.email.strip().lower() != email.lower())

    found = None
    if user_id is not None:
        found = db.find_customer_by_user(business_id, user_id)
    if found is None and email:
        candidate = db.find_customer_by_email(business_id, email)
        if theirs(candidate):
            found = candidate
    if found is None and phone:
        candidate = db.find_customer_by_phone_digits(business_id,
                                                     _phone_digits(phone))
        if theirs(candidate):
            found = candidate

    if found is not None:
        # Fill what the record is missing, and only that. A customer who gave
        # an address this time and not last time should not have to give it
        # again; one who gave a different address is not corrected by a
        # booking, because the record may be the one that is right.
        missing = {}
        if email and not found.email:
            missing["email"] = email
        if phone and not found.phone:
            missing["phone"] = phone
        if missing:
            db.set_customer(found.id, missing)
        # Booking while signed in claims the record they left behind booking
        # anonymously. Separate from the fields above because `user_id` is not
        # one the operator's form may write.
        if user_id is not None and found.user_id is None:
            db.claim_customer(found.id, user_id)
            missing = True
        if missing:
            found = db.get_customer(found.id)
        return _customer(found)

    return create_customer(
        business_id,
        contact.get("First Name") or "Customer",
        contact.get("Last Name") or "",
        phone=phone or None,
        email=email or None,
        user_id=user_id,
    )


def reconcile_boss_user(user_id: int, email: str) -> int:
    """Give a signed-in user every unclaimed record under their address.

    Run when the app loads and again whenever somebody signs in, rather than
    pushed from wherever the account was made. Two reasons: the app already
    knows who is signed in and does not have to be told, and reconciliation
    only matters when the person is there to see the result.

    It is not a migration that runs once. Somebody who already has an account
    can still book anonymously — from a shop's own kiosk, without signing in —
    so unclaimed records keep appearing, and this keeps finding them.

    That is also why there is no "already reconciled" flag. The query claims
    whatever is unclaimed, so running it twice costs a lookup and changes
    nothing, and there is no state to fall out of step with the truth.

    A record another account already holds is never taken. Returns how many
    were claimed.
    """
    if not email.strip():
        raise ValidationError("Please provide an email address.")
    return db.link_customers_to_user(email, user_id)


def link_job_to_customer(job_id: int, customer_id: int) -> None:
    """Say which customer a booking belongs to."""
    if db.get_customer(customer_id) is None:
        raise ValidationError("That customer no longer exists.")
    db.set_job_customer(job_id, customer_id)


def _customer_note(customer_id: int, note_id: int) -> "db.CustomerNoteRow":
    """The note, if it is this customer's. Refused otherwise.

    The note id comes off the screen, and the screen was opened against one
    customer — a note belonging to another is a mistake, not a permission
    question, and either way it is not this customer's to change.
    """
    row = db.get_customer_note(note_id)
    if row is None or row.customer_id != customer_id:
        raise ValidationError("That note no longer exists.")
    return row


def add_customer_note(customer_id: int, note: str, user_id: int) -> Note:
    """Write something down about a customer."""
    row = db.get_customer(customer_id)
    if row is None:
        raise ValidationError("That customer no longer exists.")
    if not note.strip():
        raise ValidationError("Please write the note.")
    note_id = db.insert_customer_note(customer_id, row.business_id,
                                      note.strip(), user_id)
    return _note(db.get_customer_note(note_id))


def update_customer_note(customer_id: int, note_id: int, note: str) -> Note:
    _customer_note(customer_id, note_id)
    if not note.strip():
        raise ValidationError("Please write the note.")
    db.set_customer_note(note_id, note.strip())
    return _note(db.get_customer_note(note_id))


def delete_customer_note(customer_id: int, note_id: int) -> None:
    _customer_note(customer_id, note_id)
    db.delete_customer_note(note_id)


def create_job_type(business_id: int, name: str,
                    min_employees: int = 1) -> JobType:
    return get_job_type(db.insert_job_type(business_id, name, min_employees))


def get_job_type(job_type_id: int) -> Optional[JobType]:
    row = db.get_job_type(job_type_id)
    return _job_type(row) if row is not None else None


def get_job_type_detail(job_type_id: int) -> Optional[AdminJobType]:
    """Everything the JobType window draws, in one answer.

    The window opens on a draft it has just created and hangs three lists off
    it, so it reads them together — a screen assembling this from four calls
    draws in four stages.
    """
    row = db.get_job_type_detail(job_type_id)
    if row is None:
        return None
    return AdminJobType(
        id=row.id,
        name=row.name,
        iconId=row.icon_id,
        minEmployees=row.min_employees,
        paymentRequired=bool(row.payment_required),
        depositRequired=bool(row.deposit_required),
        depositType=row.deposit_type,
        depositAmount=row.deposit_amount,
        depositNonrefundable=bool(row.deposit_nonrefundable),
        stripeProductId=row.stripe_product_id,
        stripePriceId=row.stripe_price_id,
        isActive=bool(row.is_active),
        sizes=get_job_type_sizes(job_type_id),
        attributes=get_job_type_attributes(job_type_id),
        contactFields=get_job_type_contact_fields(job_type_id),
        employees=[AdminJobTypeEmployee(id=e.id, firstName=e.first_name,
                                        lastName=e.last_name)
                   for e in db.get_employees_for_job_type(job_type_id)],
    )


def add_job_type_size(job_type_id: int, name: str, duration_minutes: int,
                      cost: float) -> JobTypeSize:
    """A size is what carries the duration and the price."""
    return _size(db.get_job_type_size(
        db.insert_job_type_size(job_type_id, name, duration_minutes, cost,
                                db.next_size_sort_order(job_type_id))
    ))


# --- The questions a job type asks ---------------------------------------
#
# An attribute is a question the customer answers at booking — property size,
# gate code, which surface. The kinds are fixed: the screen has to know how to
# draw each one, so a job type chooses from them rather than inventing one.

ATTRIBUTE_TYPES = ("text", "number", "dropdown", "checkbox")

# The one kind that is nothing without its choices.
CHOICE_TYPES = ("dropdown",)


def _attribute(row: "db.JobTypeAttributeRow") -> JobTypeAttribute:
    return JobTypeAttribute(
        id=row.id, name=row.name, attributeType=row.attribute_type,
        options=json.loads(row.options_json) if row.options_json else [],
        isRequired=bool(row.is_required), sortOrder=row.sort_order,
    )


def _check_attribute(name: str, attribute_type: str,
                     options: Optional[List[Any]]) -> str:
    """The rules every attribute obeys, whether it is new or being changed."""
    if not name.strip():
        raise ValidationError("Please name the question.")
    if attribute_type not in ATTRIBUTE_TYPES:
        raise ValidationError(
            f"A question is one of: {', '.join(ATTRIBUTE_TYPES)}.")
    if attribute_type in CHOICE_TYPES and not options:
        raise ValidationError("Please give the choices this question offers.")
    return json.dumps(options) if options else None


def add_job_type_attribute(job_type_id: int, name: str, attribute_type: str,
                           options: Optional[List[Any]] = None,
                           is_required: bool = False) -> JobTypeAttribute:
    """Ask the customer one more thing when they book this."""
    options_json = _check_attribute(name, attribute_type, options)
    attribute_id = db.insert_job_type_attribute(
        job_type_id, name.strip(), attribute_type, options_json,
        1 if is_required else 0,
        # Appended rather than placed: a new question goes at the end of the
        # form, and the operator reorders from the screen if they want it
        # elsewhere.
        db.next_attribute_sort_order(job_type_id)
    )
    return _attribute(db.get_job_type_attribute(attribute_id))


def get_job_type_attributes(job_type_id: int) -> List[JobTypeAttribute]:
    return [_attribute(r) for r in db.get_job_type_attributes(job_type_id)]


def update_job_type_attribute(attribute_id: int, name: str, attribute_type: str,
                              options: Optional[List[Any]] = None,
                              is_required: bool = False) -> JobTypeAttribute:
    if db.get_job_type_attribute(attribute_id) is None:
        raise ValidationError("That question no longer exists.")
    options_json = _check_attribute(name, attribute_type, options)
    db.set_job_type_attribute(attribute_id, name.strip(), attribute_type,
                              options_json, 1 if is_required else 0)
    return _attribute(db.get_job_type_attribute(attribute_id))


def delete_job_type_attribute(attribute_id: int) -> None:
    """Stop asking. Answers already given stay on the jobs that gave them."""
    if db.get_job_type_attribute(attribute_id) is None:
        raise ValidationError("That question no longer exists.")
    db.delete_job_type_attribute(attribute_id)


# --- What a job type asks the customer for --------------------------------
#
# A contact field points at one of the seeded types — a business chooses from
# them rather than inventing one — and says whether the customer has to fill it
# in, and whether it has to be verified before the booking stands.


def _contact_field(row: "db.JobTypeContactFieldRow") -> JobTypeContactField:
    return JobTypeContactField(
        id=row.id, contactFieldTypeId=row.contact_field_type_id,
        name=row.name, fieldType=row.field_type,
        isRequired=bool(row.is_required), requireOtp=bool(row.require_otp),
        sortOrder=row.sort_order,
    )


def _check_contact_field(job_type_id: int, contact_field_type_id: int,
                         require_otp: bool, field_id: Optional[int] = None):
    """The rules a contact field obeys, adding or changing.

    A code goes to a phone or an email, so `otp_capable` is what decides
    whether verification can be asked for. The screen hides the checkbox for a
    type that cannot take one; this is what settles it.
    """
    field_type = db.get_contact_field_type(contact_field_type_id)
    if field_type is None:
        raise ValidationError("That contact field no longer exists.")
    if require_otp and not field_type.otp_capable:
        raise ValidationError(
            f"{field_type.name} cannot receive a verification code.")

    # One question per kind of detail. Asking twice puts two boxes for the same
    # thing on the form, and the second value overwrites the first.
    for existing in db.get_job_type_contact_fields(job_type_id):
        if existing.contact_field_type_id == contact_field_type_id \
                and existing.id != field_id:
            raise ValidationError(f"This already asks for {field_type.name}.")


def add_job_type_contact_field(job_type_id: int, contact_field_type_id: int,
                               is_required: bool = True,
                               require_otp: bool = False) -> JobTypeContactField:
    """Ask the customer for one more detail when they book this."""
    _check_contact_field(job_type_id, contact_field_type_id, require_otp)
    field_id = db.insert_job_type_contact_field(
        job_type_id, contact_field_type_id,
        1 if is_required else 0, 1 if require_otp else 0,
        db.next_contact_field_sort_order(job_type_id)
    )
    return _contact_field(db.get_job_type_contact_field(field_id))


def get_job_type_contact_fields(job_type_id: int) -> List[JobTypeContactField]:
    return [_contact_field(r) for r in db.get_job_type_contact_fields(job_type_id)]


def update_job_type_contact_field(field_id: int, contact_field_type_id: int,
                                  is_required: bool = True,
                                  require_otp: bool = False) -> JobTypeContactField:
    row = db.get_job_type_contact_field(field_id)
    if row is None:
        raise ValidationError("That contact field no longer exists.")
    _check_contact_field(row.job_type_id, contact_field_type_id, require_otp,
                         field_id)
    db.set_job_type_contact_field(field_id, contact_field_type_id,
                                  1 if is_required else 0,
                                  1 if require_otp else 0)
    return _contact_field(db.get_job_type_contact_field(field_id))


def delete_job_type_contact_field(field_id: int) -> None:
    """Stop asking. Values already given stay on the bookings that gave them."""
    if db.get_job_type_contact_field(field_id) is None:
        raise ValidationError("That contact field no longer exists.")
    db.delete_job_type_contact_field(field_id)


def reorder_job_type_contact_fields(job_type_id: int,
                                    field_ids: List[int]) -> List[JobTypeContactField]:
    """Ask them in this order.

    The whole order arrives each time, which is what lets the screen move one
    row with a button and send the result. Every field the job type has appears
    exactly once, so a list that has drifted from the screen is refused whole
    and the order stands as it was.
    """
    current = [r.id for r in db.get_job_type_contact_fields(job_type_id)]
    if sorted(field_ids) != sorted(current):
        raise ValidationError(
            "That order no longer matches this job type's contact fields.")

    for position, field_id in enumerate(field_ids):
        db.set_contact_field_sort_order(field_id, position)
    return get_job_type_contact_fields(job_type_id)


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


def _check_span(start_time: str, end_time: str, what: str) -> None:
    if to_minutes(end_time) <= to_minutes(start_time):
        raise ValidationError(f"A {what} has to end after it starts.")


def add_working_day(employee_id: int, day_of_week: int, start_time: str,
                    end_time: str) -> EmployeeSchedule:
    """Add a day this employee works. Returns the day that was added.

    The added one rather than the whole list: the list is ordered by weekday,
    so the newest is not the last, and a caller that took the last would report
    a different day than it created.
    """
    if day_of_week not in range(7):
        raise ValidationError("A working day is one of the seven.")
    _check_span(start_time, end_time, "working day")
    if db.get_employee(employee_id) is None:
        raise ValidationError("That employee no longer exists.")

    day_id = db.insert_employee_schedule(employee_id, day_of_week, start_time,
                                         end_time)
    row = db.get_schedule_day(day_id)
    return EmployeeSchedule(id=row.id, employeeId=row.employee_id,
                            dayOfWeek=row.day_of_week, startTime=row.start_time,
                            endTime=row.end_time)


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
    # Checked before the insert, so a job type that is not there is a refusal
    # the customer can be told about rather than an integrity error and a 500.
    if db.get_business(business_id) is None:
        raise ValidationError("That business is no longer taking bookings.")
    if db.get_job_type(job_type_id) is None:
        raise ValidationError("That service is no longer offered.")
    if size_id is not None and db.get_job_type_size(size_id) is None:
        raise ValidationError("That option is no longer offered.")

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
                    contact: Optional[Dict[Any, str]] = None,
                    attributes: Optional[Dict[int, Any]] = None,
                    user_id: Optional[int] = None,
                    now: Optional[datetime] = None) -> JobSession:
    """Turn a held time into a booking.

    `contact` is what the customer typed. A key is either the contact field's
    name — `{"Phone": "+15552340000"}`, which is how a test says it — or the id
    of the job type's field, which is what the kiosk sends because that is what
    it rendered. Both resolve to the same kind of detail.

    `attributes` are the job type's own questions, keyed by attribute id.

    Finalising is what keeps the session record: the sweep removes lapsed
    holds whose appointment was never finished, and this one was.
    """
    row = _live_session(session_token, now)
    for key, value in (contact or {}).items():
        field = (db.get_contact_field_type_for_job_type_field(key)
                 if isinstance(key, int) else db.get_contact_field_type_by_name(key))
        if field is None:
            raise ValidationError(f"There is no contact field ({key}).")
        db.insert_job_contact(row.job_id, field[0], value)

    for attribute_id, value in (attributes or {}).items():
        db.insert_job_attribute(row.job_id, attribute_id,
                                "" if value is None else str(value))

    # Whoever this booking is for, as a record the business keeps. Read back
    # from storage rather than from `contact`, because the kiosk keys its
    # fields by id and a test keys them by name — this is where both are the
    # same thing again.
    job = db.get_scheduled_job(row.job_id)
    typed = {c.name: c.value for c in db.get_job_contact(row.job_id)}
    db.set_job_customer(
        row.job_id,
        find_or_create_customer(job.business_id, typed, user_id).id)

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
        id=row.id, jobCode=row.job_code, businessId=row.business_id,
        businessName=row.business_name, businessPhone=row.business_phone,
        jobTypeId=row.job_type_id, jobTypeName=row.job_type_name,
        sizeId=row.size_id, sizeName=row.size_name, cost=row.cost,
        scheduledDate=row.scheduled_date, scheduledTime=row.scheduled_time,
        displayDate=display_date(row.scheduled_date),
        displayTime=display_time(row.scheduled_time),
        durationMinutes=row.duration_minutes, status=row.status,
        changesClosed=_changes_closed(row, now or datetime.now()),
        locked=row.locked_date is not None,
        employees=[f"{e.first_name} {e.last_name[:1]}."
                   for e in db.get_employees_on_job(row.id)]
    )


def get_admin_job(job_id: int) -> Optional[AdminJob]:
    """A booking as the operator sees it.

    More than `get_appointment` returns, because the operator acts on it: what
    was paid, what the customer answered, who is doing it, and how many wrong
    codes somebody has tried — the last being what they are usually being
    called about.
    """
    row = db.get_admin_job(job_id)
    if row is None:
        return None

    return AdminJob(
        id=row.id,
        jobCode=row.job_code,
        jobType=AdminEmployeeJobType(id=row.job_type_id, name=row.job_type_name),
        size=(Size(id=row.size_id, name=row.size_name or "",
                   durationMinutes=row.size_duration_minutes or 0,
                   cost=row.cost or 0.0)
              if row.size_id is not None else None),
        scheduledDate=row.scheduled_date,
        scheduledTime=row.scheduled_time,
        durationMinutes=row.duration_minutes,
        status=row.status,
        paymentStatus=row.payment_status,
        locked=row.locked_date is not None,
        failedCodeAttempts=db.count_access_attempts(job_id),
        isRecurring=bool(row.is_recurring),
        employees=[AdminJobTypeEmployee(id=e.id, firstName=e.first_name,
                                        lastName=e.last_name)
                   for e in db.get_employees_on_job(job_id)],
        customer=_job_customer(row),
        attributes=[AdminJobAttribute(name=a.name, value=a.value)
                    for a in db.get_job_attributes(job_id)],
        transactions=get_payments(job_id),
    )


def _job_customer(row: "db.AdminJobRow") -> AdminJobCustomer:
    """Who the work is for.

    A booking need not have a customer record behind it — most do not, because
    a customer books without an account and the business has never served them
    before. What they typed at booking is then the only answer there is, and
    `id` is 0 to say there is nothing to open.
    """
    if row.customer_id is not None:
        c = db.get_customer(row.customer_id)
        if c is not None:
            return AdminJobCustomer(
                id=c.id, firstName=c.first_name, lastName=c.last_name,
                phone=c.phone or "", email=c.email or "",
                addressLine1=c.address_line1 or "", city=c.city or "",
                state=c.state or "", zip=c.zip or "")

    typed = {c.name: c.value for c in db.get_job_contact(row.id)}
    return AdminJobCustomer(
        id=0,
        firstName=typed.get("First Name", ""),
        lastName=typed.get("Last Name", ""),
        phone=typed.get("Phone", ""),
        email=typed.get("Email", ""),
        addressLine1=typed.get("Address Line 1", ""),
        city=typed.get("City", ""),
        state=typed.get("State", ""),
        zip=typed.get("Zip", ""),
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
                               now: Optional[datetime] = None) -> Delivery:
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
    return Delivery(channel=channel, sentTo=_mask(channel, destination))


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


# --- The operator's calendar ----------------------------------------------
#
# Three views over the same appointments: a month of counts, a week of
# columns, and a day laid out on a grid. Each asks the same question of a
# different range.


def _display_week_day(date: str) -> str:
    """`Sun 7/12`, as a week column heads itself."""
    when = datetime.strptime(date, "%Y-%m-%d")
    return f"{DAY_ABBREVIATIONS[day_of_week(date)]} {when.month}/{when.day}"


DAY_ABBREVIATIONS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def _week_start(date: str) -> str:
    """The Sunday of the week this date falls in."""
    when = datetime.strptime(date, "%Y-%m-%d")
    return (when - timedelta(days=day_of_week(date))).strftime("%Y-%m-%d")


def _end_time(start: str, duration_minutes: int) -> str:
    return to_time(to_minutes(start) + duration_minutes)


def _initials(row: "db.EmployeeRow") -> str:
    return f"{row.first_name[:1]}{row.last_name[:1]}".upper()


def get_schedule_month(business_id: int, year: int, month: int) -> AdminScheduleMonth:
    """How busy each day of a month is.

    Only the days with work on them. The screen draws a grid of every day and
    fills in what it is given, so an empty day is an absence rather than a zero.
    """
    start, end = _month_bounds(year, month)
    counts: Dict[str, int] = {}
    for row in db.get_scheduled_jobs(business_id, start, end):
        counts[row.scheduled_date] = counts.get(row.scheduled_date, 0) + 1
    return AdminScheduleMonth(
        year=year, month=month,
        # In date order because the rows arrive in date order and a dict keeps
        # what it was given.
        days=[Day(date=date, jobCount=count) for date, count in counts.items()],
    )


def get_schedule_week(business_id: int, date: str) -> AdminScheduleWeek:
    """Seven days from the Sunday, whatever day was asked about.

    Always seven, empty ones included: the week is a row of columns, and a day
    left out would close the gap and mislabel every column after it.
    """
    start = _week_start(date)
    end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")

    rows = db.get_scheduled_jobs(business_id, start, end)
    crew = _crew_for([r.id for r in rows])

    days = []
    for offset in range(7):
        on = (datetime.strptime(start, "%Y-%m-%d")
              + timedelta(days=offset)).strftime("%Y-%m-%d")
        days.append(AdminScheduleWeekDay(
            date=on,
            displayDate=_display_week_day(on),
            jobs=[
                AdminScheduleWeekJob(
                    id=r.id, jobCode=r.job_code, jobType=r.job_type_name,
                    startTime=r.scheduled_time,
                    endTime=_end_time(r.scheduled_time, r.duration_minutes),
                    employeeInitials=[_initials(e) for e in crew.get(r.id, [])],
                    status=r.status,
                )
                for r in rows if r.scheduled_date == on
            ],
        ))
    return AdminScheduleWeek(weekStart=start, days=days)


def _crew_for(job_ids: List[int]) -> Dict[int, list]:
    """Who is on each of these jobs, in one query rather than one per job."""
    crew: Dict[int, list] = {}
    for row in db.get_employees_for_jobs(job_ids):
        crew.setdefault(row.job_id, []).append(row)
    return crew


def _lay_out(jobs: List[tuple]) -> Dict[int, tuple]:
    """Which column each appointment takes, and how many share its group.

    Appointments running at the same time are drawn side by side, so each needs
    a column and the width to divide. A group is every appointment reachable
    from another by overlapping — three appointments in a chain all take a
    third of the width, which keeps the grid honest as one is added.

    Takes `(id, start, end)` in start order; returns `id -> (column, total)`.
    """
    layout: Dict[int, tuple] = {}

    def settle(members):
        """Place one group, then give every member the group's width."""
        columns: List[int] = []          # when each column is next free
        placed = []
        for job_id, start, end in members:
            column = next((i for i, free in enumerate(columns) if free <= start),
                          len(columns))
            if column == len(columns):
                columns.append(end)
            else:
                columns[column] = end
            placed.append((job_id, column))
        for job_id, column in placed:
            layout[job_id] = (column, len(columns))

    group: List[tuple] = []
    group_ends = 0
    for job_id, start, end in jobs:
        # A gap with nothing running across it closes the group: what follows
        # overlaps none of it, and divides the width afresh.
        if group and start >= group_ends:
            settle(group)
            group, group_ends = [], 0
        group.append((job_id, start, end))
        group_ends = max(group_ends, end)
    if group:
        settle(group)
    return layout


def get_schedule_day(business_id: int, date: str) -> AdminScheduleDay:
    """One day, laid out so two appointments at once can both be seen."""
    rows = db.get_scheduled_jobs(business_id, date, date)
    crew = _crew_for([r.id for r in rows])
    layout = _lay_out([
        (r.id, to_minutes(r.scheduled_time),
         to_minutes(r.scheduled_time) + r.duration_minutes)
        for r in rows
    ])

    return AdminScheduleDay(
        date=date,
        jobs=[
            AdminScheduleDayJob(
                id=r.id, jobCode=r.job_code, jobType=r.job_type_name,
                customerName=" ".join(
                    part for part in (r.first_name, r.last_name) if part),
                startTime=r.scheduled_time,
                endTime=_end_time(r.scheduled_time, r.duration_minutes),
                startMinuteOffset=to_minutes(r.scheduled_time),
                durationMinutes=r.duration_minutes,
                employees=[AppointmentEmployee(firstName=e.first_name,
                                               lastInitial=e.last_name[:1])
                           for e in crew.get(r.id, [])],
                overlapColumn=layout[r.id][0],
                overlapTotal=layout[r.id][1],
                status=r.status,
                paymentStatus=r.payment_status,
            )
            for r in rows
        ],
    )


def get_unassigned_jobs(business_id: int) -> List[AdminJobsUnassignedJob]:
    """Live appointments with nobody on them, for Needs Attention."""
    return [
        AdminJobsUnassignedJob(
            id=r.id, jobCode=r.job_code, jobType=r.job_type_name,
            customerName=" ".join(
                part for part in (r.first_name, r.last_name) if part),
            scheduledDate=r.scheduled_date, scheduledTime=r.scheduled_time,
            displayDate=display_date(r.scheduled_date),
            displayTime=display_time(r.scheduled_time),
            isRecurring=bool(r.is_recurring),
        )
        for r in db.get_unassigned_jobs(business_id)
    ]


def assign_jobs(business_id: int, job_ids: List[int],
                now: Optional[datetime] = None) -> AdminJobsAssign:
    """Put somebody free on each appointment chosen.

    Asked of the same availability the kiosk asks, so an appointment is never
    given to somebody the booking screen would have refused. An appointment
    nobody is free for is counted rather than forced onto whoever is nearest —
    the operator is being told there is a conflict to resolve.

    An appointment that already has a crew is left alone. The screen lists only
    unassigned work, so one arriving here is a list that has gone stale.
    """
    assigned = unassigned = 0
    for job_id in job_ids:
        row = db.get_scheduled_job(job_id)
        if row is None or row.business_id != business_id:
            continue
        if db.get_employees_on_job(job_id):
            continue

        free = employees_free_at(business_id, row.job_type_id,
                                 row.job_type_size_id, row.scheduled_date,
                                 row.scheduled_time, now=now)
        if not free:
            unassigned += 1
            continue

        job_type = get_job_type(row.job_type_id)
        wanted = job_type.minEmployees if job_type else 1
        for employee_id in free[:wanted]:
            db.assign_employee_to_job(job_id, employee_id)
        assigned += 1

    return AdminJobsAssign(assigned=assigned, unassigned=unassigned)


def get_dashboard(business_id: int,
                  now: Optional[datetime] = None) -> Optional[AdminDashboard]:
    """The figures the operator lands on."""
    business_row = db.get_business(business_id)
    if business_row is None:
        return None
    business = _business(business_row)
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")

    week_start = _week_start(today)
    week_end = (datetime.strptime(week_start, "%Y-%m-%d")
                + timedelta(days=6)).strftime("%Y-%m-%d")
    month_start, month_end = _month_bounds(now.year, now.month)

    waiting = db.get_unassigned_jobs(business_id)

    # An appointment nobody is free for is a conflict the operator has to
    # resolve, and it is counted apart from the rest. Asked only under
    # `reserved`: `unlimited` allocates nobody, so every appointment would
    # count and the figure would say nothing.
    conflicts = 0
    if business.slotMode == "reserved":
        conflicts = len([
            r for r in waiting
            if not employees_free_at(business_id, r.job_type_id,
                                     r.job_type_size_id, r.scheduled_date,
                                     r.scheduled_time, now=now)
        ])

    return AdminDashboard(
        # The kiosk button opens against a business, and the screen already
        # asks this route for everything else it draws.
        businessId=business_id,
        # `unlimited` allocates nobody, so the screen hides the panel rather
        # than showing a count that can only ever be the whole list.
        slotMode=business.slotMode,
        jobsToday=db.count_jobs_between(business_id, today, today),
        jobsThisWeek=db.count_jobs_between(business_id, week_start, week_end),
        revenueThisMonth=db.get_revenue_between(business_id, month_start, month_end),
        upcomingJobs=db.count_jobs_between(business_id, today, LAST_DATE),
        unassignedJobs=len(waiting),
        unassignedConflicts=conflicts,
    )


# Far enough out that "upcoming" means everything ahead. A date rather than a
# window: an appointment booked two years from now is still upcoming.
LAST_DATE = "9999-12-31"



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


def send_booking_confirmation(job_id: int) -> List[Delivery]:
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
                out.append(Delivery(channel=channel,
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
                name: Optional[str] = None,
                phone: Optional[str] = None,
                employee_id: Optional[int] = None,
                limit: int = 200) -> List[Job]:
    """Appointments matching what the operator narrowed by.

    An inverted range is refused rather than answered with nothing found.
    "No appointments" to a range that cannot contain any tells the operator
    their data is missing, when their dates are backwards.

    An open range is a range: one end, or neither, constrains what it can.

    `YYYY-MM-DD` compares correctly as a string, so no parsing is needed.
    """
    if from_date and to_date and from_date > to_date:
        raise InvalidDateRange("The From date has to be on or before the To date.")

    rows = db.search_jobs(business_id, from_date, to_date, status, job_type_id,
                          job_code, name, phone, employee_id, limit)

    # Who is doing the work, for every row at once. Asking per row would be one
    # query per result, and the screen draws fifty.
    crew: Dict[int, List[AppointmentEmployee]] = {}
    for e in db.get_employees_for_jobs([r.id for r in rows]):
        crew.setdefault(e.job_id, []).append(
            AppointmentEmployee(firstName=e.first_name,
                                lastInitial=e.last_name[:1]))

    return [
        Job(id=r.id, jobCode=r.job_code, jobType=r.job_type_name,
            customerName=" ".join(
                part for part in (r.first_name, r.last_name) if part),
            scheduledDate=r.scheduled_date,
            scheduledTime=r.scheduled_time,
            displayDate=display_date(r.scheduled_date),
            displayTime=display_time(r.scheduled_time),
            status=r.status, paymentStatus=r.payment_status,
            employees=crew.get(r.id, []))
        for r in rows
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


def available_report_years(business_id: int) -> List[int]:
    """The years the report screen offers.

    Every year with an appointment in it, and this one — a business with
    nothing booked still needs a year selected for the menu to have a value.
    """
    # A list rather than a set: `get_booked_years` already answers in order,
    # and the current year is the one insertion — so the ordering is the
    # sort's doing rather than a set's iteration happening to agree.
    years = db.get_booked_years(business_id)
    current = datetime.now().year
    if current not in years:
        years.append(current)
        years.sort()
    return years


def get_financial_report(business_id: int, year: int,
                         quarter: Optional[int] = None) -> FinancialReport:
    """What a business took over a period, and what it gave up on.

    Revenue is money that arrived. A deposit is named apart from it: it is
    held against work still to come, and an owner reading one figure would be
    counting takings they may yet have to return.
    """
    from_date, to_date = _period(year, quarter)
    rows = db.get_jobs_in_period(business_id, from_date, to_date)

    revenue = sum(r.paid for r in rows)
    deposits = sum(r.paid for r in rows if r.payment_status == "deposit_paid")
    written_off = sum(max((r.cost or 0.0) - r.paid, 0.0)
                      for r in rows if r.payment_status == WRITTEN_OFF)
    return FinancialReport(
        period="quarter" if quarter is not None else "year",
        year=year, quarter=quarter, fromDate=from_date, toDate=to_date,
        availableYears=available_report_years(business_id),
        revenue=revenue,
        depositsCollected=deposits,
        writeOffs=written_off,
        jobsCompleted=len([r for r in rows if r.status == "completed"]),
        jobsCancelled=len([r for r in rows if r.status == "cancelled"]),
    )


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


# --- What one person sees of their own work -------------------------------
#
# Two portals over the same appointments. A customer sees what they booked,
# wherever they booked it; an employee sees what they have been given, one day
# at a time. Each is reached by the signed-in BOSS user, through the `user_id`
# their record carries.


def get_customer_appointments(user_id: int,
                              now: Optional[datetime] = None) -> CustomerAppointments:
    """Everything one person has booked, across every business.

    A customer record belongs to one business, and somebody who has used two
    has two records — so this gathers them by the account that holds them.
    """
    rows = db.get_jobs_for_customers(db.get_customer_ids_for_user(user_id))
    crew = _crew_for([r.id for r in rows])
    today = (now or datetime.now()).strftime("%Y-%m-%d")

    return CustomerAppointments(
        # What is still to come, which is what the dashboard leads with. A
        # cancelled appointment is still listed — the customer wants to see
        # what happened to it — and counted with the past.
        upcomingCount=len([r for r in rows if r.scheduled_date >= today
                           and r.status != "cancelled"]),
        appointments=[
            CustomerAppointmentsAppointment(
                id=r.id, jobCode=r.job_code, business=r.business_name,
                jobType=r.job_type_name,
                scheduledDate=r.scheduled_date, scheduledTime=r.scheduled_time,
                displayDate=display_date(r.scheduled_date),
                displayTime=display_time(r.scheduled_time),
                employees=[AppointmentEmployee(firstName=e.first_name,
                                               lastInitial=e.last_name[:1])
                           for e in crew.get(r.id, [])],
                status=r.status,
            )
            for r in rows
        ],
    )


def link_employee_to_user(employee_id: int, user_id: int) -> None:
    """Say which BOSS account works under this employee record."""
    if db.get_employee(employee_id) is None:
        raise ValidationError("That employee no longer exists.")
    db.set_employee_user(employee_id, user_id)


def get_employee_profile(user_id: int) -> Optional[EmployeeProfile]:
    """The signed-in employee's own record.

    `employeeId` is carried because the screen edits working days and time off
    through the routes the operator uses, which the service authorises rather
    than duplicates.
    """
    row = db.get_employee_by_user(user_id)
    if row is None:
        return None
    return EmployeeProfile(
        employeeId=row.id,
        firstName=row.first_name,
        lastName=row.last_name,
        canManageOwnSchedule=bool(row.can_manage_own_schedule),
        scheduleTemplate=get_working_days(row.id),
        timeOff=get_time_off(row.id),
        jobTypes=[AdminEmployeeJobType(id=j.id, name=j.name)
                  for j in get_employee_job_types(row.id)],
    )


def update_employee_profile(user_id: int,
                            job_type_ids: List[int]) -> EmployeeProfile:
    """What an employee says about themselves: the work they take.

    Their name, their business, and whether they may manage their own schedule
    at all are the operator's to set.
    """
    row = db.get_employee_by_user(user_id)
    if row is None:
        raise ValidationError("You are not on this business's staff.")

    for job_type_id in job_type_ids:
        job_type = db.get_job_type(job_type_id)
        if job_type is None or job_type.business_id != row.business_id:
            raise ValidationError("That service is not one this business offers.")

    set_employee_job_types(row.id, job_type_ids)
    return get_employee_profile(user_id)


def get_employee_today(user_id: int, date: str = "",
                       now: Optional[datetime] = None) -> Optional[EmployeeToday]:
    """The work one employee has in front of them on one day."""
    row = db.get_employee_by_user(user_id)
    if row is None:
        return None
    date = date or (now or datetime.now()).strftime("%Y-%m-%d")

    jobs = []
    for job in db.get_jobs_for_employee(row.id, date):
        typed = {c.name: c.value for c in db.get_job_contact(job.id)}
        jobs.append(EmployeeTodayJob(
            id=job.id, jobCode=job.job_code, jobType=job.job_type_name,
            startTime=job.scheduled_time,
            endTime=_end_time(job.scheduled_time, job.duration_minutes),
            displayTime=display_time(job.scheduled_time),
            customer=EmployeeTodayJobCustomer(
                firstName=typed.get("First Name", ""),
                lastName=typed.get("Last Name", ""),
                phone=typed.get("Phone", ""),
                addressLine1=typed.get("Address Line 1", ""),
                city=typed.get("City", ""),
                state=typed.get("State", ""),
            ),
            # Everyone else on the job. Themselves left out — they know.
            coWorkers=[CoWorker(firstName=e.first_name, lastName=e.last_name)
                       for e in db.get_employees_on_job(job.id) if e.id != row.id],
            attributes=[AdminJobAttribute(name=a.name, value=a.value)
                        for a in db.get_job_attributes(job.id)],
            status=job.status,
        ))

    return EmployeeToday(
        date=date,
        displayDate=display_date(date),
        jobs=jobs,
        canManageOwnSchedule=bool(row.can_manage_own_schedule),
    )


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


# --- What the routes need on top of the rules ----------------------------

def employees_free_at(business_id: int, job_type_id: int, size_id: Optional[int],
                      date: str, time: str,
                      employee_id: Optional[int] = None,
                      now: Optional[datetime] = None) -> List[int]:
    """Who would do the work at a chosen time.

    The customer chose a time, not a person, so this asks the same question
    availability already answered rather than trusting the client to name
    anybody. Empty under `unlimited`, where nobody is allocated.
    """
    for slot in get_available_slots(business_id, job_type_id, size_id,
                                    employee_id, limit=200, from_date=date,
                                    now=now):
        if slot.date == date and slot.time == time:
            return slot.employeeIds
    return []


def contact_value_for(session_token: str, field_type: str) -> str:
    """What the customer gave for a kind of contact detail, on this booking.

    The kiosk asks for a code to be sent to "the phone" without repeating the
    number back to the server; this is where the number comes from.
    """
    row = db.get_session(session_token)
    if row is None:
        raise SessionExpired("Your session has expired. Please choose a time again.")
    for contact in db.get_job_contact(row.job_id):
        if contact.field_type == field_type:
            return contact.value
    raise ValidationError(f"No {field_type} was given for this appointment.")


# --- The work a business offers ------------------------------------------

def get_job_types(business_id: int, term: Optional[str] = None,
                  active_only: bool = False) -> List[JobType]:
    """What the business offers. `active_only` is the customer's view."""
    return [_job_type(r) for r in db.get_job_types(business_id, term, active_only)]


def update_job_type(job_type_id: int, name: str,
                    min_employees: Optional[int] = None,
                    is_active: Optional[bool] = None) -> Optional[JobType]:
    current = get_job_type(job_type_id)
    if current is None:
        raise ValidationError("That job type no longer exists.")
    if not name or not name.strip():
        raise ValidationError("A job type needs a name.")
    people = current.minEmployees if min_employees is None else min_employees
    if people < 1:
        raise ValidationError("A job needs at least one person to do it.")

    db.update_job_type(job_type_id, name.strip(), people,
                       1 if (current.isActive if is_active is None else is_active) else 0)
    return get_job_type(job_type_id)


def delete_job_type(job_type_id: int) -> None:
    """Remove work the business no longer offers.

    Refused once an appointment names it: the appointment is still real, and
    the customer expects it. Retiring it with `is_active` is what stops it
    being offered without erasing what it was.
    """
    booked = db.count_jobs_for_job_type(job_type_id)
    if booked:
        raise Blocked(
            "This job type cannot be deleted while appointments are booked"
            " against it. Make it inactive instead.",
            [f"{booked} appointment(s)"]
        )
    db.delete_job_type(job_type_id)


def get_job_type_sizes(job_type_id: int) -> List[JobTypeSize]:
    return [_size(r) for r in db.get_job_type_sizes(job_type_id)]


def update_job_type_size(size_id: int, name: str, duration_minutes: int,
                         cost: float) -> Optional[JobTypeSize]:
    if not name or not name.strip():
        raise ValidationError("A size needs a name.")
    if duration_minutes < 1:
        raise ValidationError("A size needs to take some time.")
    if cost < 0:
        raise ValidationError("A size cannot cost less than nothing.")
    if db.get_job_type_size(size_id) is None:
        raise ValidationError("That size no longer exists.")

    db.update_job_type_size(size_id, name.strip(), duration_minutes, cost)
    return _size(db.get_job_type_size(size_id))


def delete_job_type_size(size_id: int) -> None:
    """Remove a size. Refused once an appointment was booked at it."""
    booked = db.count_jobs_for_size(size_id)
    if booked:
        raise Blocked(
            "This size cannot be deleted while appointments are booked at it.",
            [f"{booked} appointment(s)"]
        )
    db.delete_job_type_size(size_id)


# --- The people a business schedules -------------------------------------

def get_employees(business_id: int) -> List[Employee]:
    return [_employee(r) for r in db.get_employees(business_id)]


def get_employee(employee_id: int) -> Optional[Employee]:
    row = db.get_employee(employee_id)
    return _employee(row) if row is not None else None


def update_employee(employee_id: int, first_name: str, last_name: str,
                    include_in_schedule: Optional[bool] = None,
                    can_manage_own_schedule: Optional[bool] = None) -> Optional[Employee]:
    current = get_employee(employee_id)
    if current is None:
        raise ValidationError("That employee no longer exists.")
    if not first_name or not first_name.strip():
        raise ValidationError("An employee needs a first name.")
    if not last_name or not last_name.strip():
        raise ValidationError("An employee needs a last name.")

    db.update_employee(
        employee_id, first_name.strip(), last_name.strip(),
        1 if (current.includeInSchedule if include_in_schedule is None
              else include_in_schedule) else 0,
        1 if (current.canManageOwnSchedule if can_manage_own_schedule is None
              else can_manage_own_schedule) else 0
    )
    return get_employee(employee_id)


def delete_employee(employee_id: int) -> None:
    """Remove somebody who never worked here.

    Refused once an appointment names them: the appointment is still real and
    says who is coming. Taking them out of the schedule is what stops them
    being given more work.
    """
    assigned = db.count_jobs_for_employee(employee_id)
    if assigned:
        raise Blocked(
            "This employee cannot be deleted while they are assigned to"
            " appointments. Take them out of the schedule instead.",
            [f"{assigned} appointment(s)"]
        )
    db.delete_employee(employee_id)


def get_employee_job_types(employee_id: int) -> List[JobType]:
    """The work this employee is allowed to be given."""
    return [_job_type(r) for r in db.get_job_types_for_employee(employee_id)]


def set_employee_job_types(employee_id: int, job_type_ids: List[int]) -> List[JobType]:
    """Replace what this employee may be given, wholesale.

    Sent as the whole list rather than as additions and removals: the form
    shows every job type at once, and a difference computed here cannot
    disagree with what was on screen.
    """
    db.clear_job_types_for_employee(employee_id)
    for job_type_id in job_type_ids:
        db.link_employee_to_job_type(job_type_id, employee_id)
    return get_employee_job_types(employee_id)


# --- When they work, and when they are away ------------------------------

def update_working_day(schedule_id: int, day_of_week: int, start_time: str,
                       end_time: str) -> Optional[EmployeeSchedule]:
    if day_of_week not in range(7):
        raise ValidationError("A working day is one of the seven.")
    _check_span(start_time, end_time, "working day")
    if db.get_schedule_day(schedule_id) is None:
        raise ValidationError("That working day no longer exists.")

    db.update_schedule_day(schedule_id, day_of_week, start_time, end_time)
    row = db.get_schedule_day(schedule_id)
    return EmployeeSchedule(id=row.id, employeeId=row.employee_id,
                            dayOfWeek=row.day_of_week, startTime=row.start_time,
                            endTime=row.end_time)


def delete_working_day(schedule_id: int) -> None:
    db.delete_schedule_day(schedule_id)


def get_time_off(employee_id: int) -> List[EmployeeTimeOff]:
    return [EmployeeTimeOff(id=r.id, employeeId=r.employee_id, date=r.date,
                            startTime=r.start_time, endTime=r.end_time)
            for r in db.get_all_time_off(employee_id)]


def update_time_off(window_id: int, date: str, start_time: str,
                    end_time: str) -> Optional[EmployeeTimeOff]:
    _check_span(start_time, end_time, "time-off window")
    if db.get_time_off_window(window_id) is None:
        raise ValidationError("That time-off window no longer exists.")

    db.update_time_off(window_id, date, start_time, end_time)
    row = db.get_time_off_window(window_id)
    return EmployeeTimeOff(id=row.id, employeeId=row.employee_id, date=row.date,
                           startTime=row.start_time, endTime=row.end_time)


def delete_time_off(window_id: int) -> None:
    db.delete_time_off(window_id)


# --- Is this business ready? ---------------------------------------------
#
# One question, computed on every call rather than kept in a column. A rule
# added here takes effect everywhere at once, and there is no flag that can
# fall out of step with the thing it describes.
#
# The sentences are the server's, and so is the window each one names: it is
# the side that knows which job type is missing what.

def _task(text, controller, section=None, done=False):
    return SetupTask(text=text, controller=controller, section=section, done=done)


def get_setup(business_id: int) -> SetupResponse:
    """Everything standing between this business and a booking."""
    business_row = db.get_business(business_id)
    if business_row is None:
        return SetupResponse(configured=False, tasks=[])
    business = _business(business_row)
    reserved = business.slotMode == "reserved"

    tasks = [_task("Give your business a name", "BusinessConfig", "general",
                   bool(business.name and business.name.strip()))]

    # Under `unlimited` the hours are the whole answer, so a business with none
    # can offer nothing. Under `reserved` the employees' schedules govern and
    # the hours are shown to the customer, so they are not asked for.
    if not reserved:
        tasks.append(_task("Set the days and hours you are open",
                           "BusinessConfig", "schedule",
                           db.count_open_days(business_id) > 0))

    active = [_job_type(r) for r in db.get_job_types(business_id, active_only=True)]
    tasks.append(_task("Add a service customers can book", "JobTypes",
                       done=bool(active)))

    for job_type in active:
        tasks.append(_task(
            f'Add a size to "{job_type.name}"', "JobTypes",
            done=db.count_job_type_sizes(job_type.id) > 0
        ))
        tasks.append(_task(
            f'Ask "{job_type.name}" for a way to contact the customer', "JobTypes",
            done=db.count_job_type_contact_fields(job_type.id) > 0
        ))
        if reserved:
            # Availability comes from employee schedules, so a job type nobody
            # can perform — or nobody works a day for — offers no times ever.
            who = [e for e in db.get_employees_for_job_type(job_type.id)]
            tasks.append(_task(
                f'No employee can perform "{job_type.name}"', "Employees",
                done=bool(who)
            ))
            tasks.append(_task(
                f'Give an employee working days for "{job_type.name}"', "Employees",
                done=any(db.get_employee_schedule(e.id) for e in who)
            ))
        if db.job_type_requires_otp(job_type.id):
            tasks.append(_task(
                f'Connect a way to send codes — "{job_type.name}" verifies a'
                f' contact detail', "SuperAdminVendors",
                done=db.count_active_vendors("sms") + db.count_active_vendors("email") > 0
            ))
        if db.job_type_takes_money(job_type.id):
            tasks.append(_task(
                f'Connect Stripe — "{job_type.name}" takes a payment',
                "BusinessConfig", "payment",
                done=bool(db.get_business_stripe_account(business_id))
            ))

    return SetupResponse(configured=all(t.done for t in tasks), tasks=tasks)


# What the window calls a field, and what the column is called. Written out
# rather than derived, so a column renamed in the schema does not silently
# rename a field the client sends.
CONFIG_FIELDS = {
    "name": "name",
    "phone": "phone",
    "addressLine1": "address_line1",
    "addressLine2": "address_line2",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "ownerName": "owner_name",
    "description": "description",
    "siteUrl": "site_url",
    "timezone": "timezone",
    "slotMode": "slot_mode",
    "slotIncrementMinutes": "slot_increment_minutes",
    "cutoffDays": "cutoff_days",
    "minBookingNoticeHours": "min_booking_notice_hours",
    "minChangeNoticeMinutes": "min_change_notice_minutes",
    "bufferMinutes": "buffer_minutes",
    "reminderEnabled": "reminder_enabled",
    "confirmBySms": "confirm_by_sms",
    "confirmByEmail": "confirm_by_email",
    "completionMode": "completion_mode",
    "allowCustomerEmployeeSelection": "allow_customer_employee_selection",
    "notifyEmployees": "notify_employees",
}

CONFIG_BOOLEANS = {"reminderEnabled", "confirmBySms", "confirmByEmail",
                   "allowCustomerEmployeeSelection", "notifyEmployees"}

# Where a customer books. The business never sets this — it is shown so the
# owner can copy it, and it is derived so it cannot fall out of step.
PUBLIC_URL_BASE = "https://bithead.io/a/scheduler"


def _config(row: "db.BusinessConfigRow") -> BusinessConfig:
    return BusinessConfig(
        businessId=row.id,
        name=row.name,
        phone=row.phone or "",
        addressLine1=row.address_line1 or "",
        addressLine2=row.address_line2 or "",
        city=row.city or "",
        state=row.state or "",
        zip=row.zip or "",
        ownerName=row.owner_name or "",
        description=row.description or "",
        siteUrl=row.site_url or "",
        timezone=row.timezone,
        slotIncrementMinutes=row.slot_increment_minutes,
        cutoffDays=row.cutoff_days,
        minBookingNoticeHours=row.min_booking_notice_hours,
        minChangeNoticeMinutes=row.min_change_notice_minutes,
        bufferMinutes=row.buffer_minutes,
        slotMode=row.slot_mode,
        operatingHours=get_operating_hours(row.id),
        reminderEnabled=bool(row.reminder_enabled),
        confirmBySms=bool(row.confirm_by_sms),
        confirmByEmail=bool(row.confirm_by_email),
        completionMode=row.completion_mode,
        allowCustomerEmployeeSelection=bool(row.allow_customer_employee_selection),
        notifyEmployees=bool(row.notify_employees),
        publicUrl=f"{PUBLIC_URL_BASE}/{row.id}",
    )


def get_business_config(business_id: int) -> Optional[BusinessConfig]:
    """Everything the Business Settings window shows."""
    row = db.get_business_config(business_id)
    return _config(row) if row is not None else None


def update_business_config(business_id: int, settings: dict) -> Optional[BusinessConfig]:
    """Write the settings given, and only those.

    The window saves as the owner works, so this is usually one field. A field
    absent from `settings` is a field the owner did not touch, not a field they
    cleared.

    The business name is the one field that cannot be emptied, and it is
    refused *after* the rest of the write rather than before: an owner who
    fills in a phone number before reaching the name would otherwise lose the
    phone number to a complaint about the name.
    """
    if db.get_business_config(business_id) is None:
        raise ValidationError("That business no longer exists.")

    unknown = set(settings) - set(CONFIG_FIELDS)
    if unknown:
        raise ValidationError(
            f"Not a business setting: {', '.join(sorted(unknown))}.")

    blank_name = "name" in settings and not str(settings["name"]).strip()

    columns = {}
    for field, value in settings.items():
        if field == "name":
            if blank_name:
                continue
            value = str(value).strip()
        elif field in CONFIG_BOOLEANS:
            value = 1 if value else 0
        columns[CONFIG_FIELDS[field]] = value

    db.set_business_config(business_id, columns)

    if blank_name:
        raise ValidationError("Please provide a business name.")
    return get_business_config(business_id)
