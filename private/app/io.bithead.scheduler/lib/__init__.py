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

import os

from lib import media

from .. import db
from ..model import *

# The foundation every other module here is written on. Re-exported so a
# caller still reaches everything through `lib`, wherever it now lives.
from .exception import *
from .time import *
from .transform import *
from .platform import *
from .availability import *
# Private to `lib`, so `import *` passes over it. Named while the rules that
# call it are still here.
from .availability import _duration_minutes, _next_day
from .membership import *
from .money import *
from .employee import *
from .business import *
from .job_type import *
from .customer import *

# A job may be pending without holding anything: the customer opened the form
# and walked away. `db.get_booked_intervals` decides that by the session, which
# is the only place the timeout is applied.
HELD_STATUSES = ("pending", "confirmed")


#
# One per concept, at the top, so a rule below works in attributes and a
# mistyped column fails here rather than three calls later.


#
# Minutes since midnight, which is what every comparison here wants. A day is
# short enough that arithmetic on integers beats arithmetic on clocks.


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
        # Set up *and* trading. A customer is told the same thing either way —
        # which of the two it is concerns the operator, not somebody looking
        # to book.
        configured=bool(row.is_active) and get_setup(business_id).configured,
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


def get_kiosk_employees(business_id: int) -> List[JobTypeEmployee]:
    """Who a customer may ask for.

    Only those in the schedule. Somebody taken out of it is off the kiosk for
    the same reason they are off the availability search — they are not being
    booked.
    """
    return [
        JobTypeEmployee(id=e.id, firstName=e.firstName, lastName=e.lastName)
        for e in get_employees(business_id) if e.includeInSchedule
    ]


def _month_bounds(year: int, month: int) -> tuple:
    """The first and last dates of a month, as `YYYY-MM-DD`."""
    first = _date(year, month, 1)
    last = _date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def get_kiosk_calendar(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    year: int = 0,
    month: int = 0,
    now: Optional[datetime] = None
) -> KioskCalendar:
    """Which days of a month a customer may choose from.

    Asked of the same availability the times come from, so a day the calendar
    offers has a time behind it. The month bounds the search rather than
    filtering it afterwards — a business open every day would otherwise need
    every slot in the year computed to answer about July.
    """
    start, end = _month_bounds(year, month)
    slots = get_available_slots(
        business_id,
        job_type_id,
        size_id,
        employee_id,
        limit=0,
        from_date=start,
        until_date=end,
        now=now
    )
    return KioskCalendar(
        year=year,
        month=month,
        availableDays=sorted({int(s.date[8:10]) for s in slots})
    )


def get_kiosk_day_slots(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    date: str = "",
    now: Optional[datetime] = None
) -> KioskDaySlots:
    """The times on the one day a customer picked."""
    slots = get_available_slots(
        business_id,
        job_type_id,
        size_id,
        employee_id,
        limit=0,
        from_date=date,
        until_date=date,
        now=now
    )
    return KioskDaySlots(
        date=date,
        slots=[KioskDaySlotsSlot(time=s.time, displayTime=s.displayTime)
               for s in slots],
    )


# MARK: Vendors

# What the platform sends through, and the names it recognises for each.
#
# A vendor module implementing one of these is still to be written; the choice
# outlives the integration, so it is recorded now and read by whichever module
# comes to do the sending. A name outside this table is a typo — a saved choice
# nothing implements sends nothing and says it saved.


#
# A BOSS user joins a business by opening one or by being added to it, which
# writes the `employees` record every business-scoped route is then scoped by.
# Until then they are a customer: the app has customers who never work
# anywhere.
#
# An operator is an employee of the business they run, holding the operator
# role — so a one-person business is one record, and `includeInSchedule` says
# separately whether the owner is given work.


#
# Two kinds, told apart by where the file lives. A system icon ships in the app
# bundle and every business sees the same set; a custom one is an upload, and
# belongs to the business that made it.


#
# Both are shared: a business observes holidays it chooses from this list, and
# starts from one of these templates. The platform decides what there is.


#
# A super admin sees every business rather than one, and acts on the record
# itself: opening it, closing it, and removing one that never traded.


#
# The contact field types are seeded once per installation and shared by every
# business. A business picks from them; the platform decides what there is to
# pick.


#
# What an operator does before a customer can book: describe the business, say
# when it is open, offer work, and say who does it.


#
# A customer is a business's own record of somebody it has served. Two
# businesses that serve the same person hold two rows: neither is entitled to
# know the other has them.


#
# An attribute is a question the customer answers at booking — property size,
# gate code, which surface. The kinds are fixed: the screen has to know how to
# draw each one, so a job type chooses from them rather than inventing one.


#
# A contact field points at one of the seeded types — a business chooses from
# them rather than inventing one — and says whether the customer has to fill it
# in, and whether it has to be verified before the booking stands.


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


def create_job_session(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int],
    scheduled_date: str,
    scheduled_time: str,
    employee_ids: Optional[List[int]] = None,
    now: Optional[datetime] = None
) -> JobSession:
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
    if db.get_job_type(business_id, job_type_id) is None:
        raise ValidationError("That service is no longer offered.")
    if size_id is not None and db.get_job_type_size(size_id) is None:
        raise ValidationError("That option is no longer offered.")

    duration = _duration_minutes(size_id)
    job_id = db.insert_scheduled_job(
        _job_code(),
        business_id,
        job_type_id,
        size_id,
        scheduled_date,
        scheduled_time,
        duration,
        "pending"
    )
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
    return JobSession(
        sessionToken=session_token,
        jobId=job.id,
        jobCode=job.job_code,
        scheduledDate=job.scheduled_date,
        scheduledTime=job.scheduled_time,
        expiresAt=row.expires_at,
        employeeIds=db.get_job_employee_ids(job.id)
    )


def _live_session(session_token: str, now: Optional[datetime] = None):
    """The hold, if it is still the customer's to use."""
    row = db.get_session(session_token)
    if row is None or row.expires_at <= _stamp(now or datetime.utcnow()):
        raise SessionExpired(
            "Your session has expired. Please choose a time again."
        )
    return row


def extend_session(
    session_token: str,
    now: Optional[datetime] = None
) -> JobSession:
    """Give the customer the full timeout again, because they are still here."""
    _live_session(session_token, now)
    db.extend_session(session_token, _expiry(now))
    return _session(session_token)


def confirm_session(
    session_token: str,
    contact: Optional[Dict[Any, str]] = None,
    attributes: Optional[Dict[int, Any]] = None,
    user_id: Optional[int] = None,
    now: Optional[datetime] = None
) -> JobSession:
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
                 if isinstance(
                     key,
                     int
                 ) else db.get_contact_field_type_by_name(key))
        if field is None:
            raise ValidationError(f"There is no contact field ({key}).")
        db.insert_job_contact(row.job_id, field[0], value)

    for attribute_id, value in (attributes or {}).items():
        db.insert_job_attribute(
            row.job_id,
            attribute_id,
            "" if value is None else str(value)
        )

    # Whoever this booking is for, as a record the business keeps. Read back
    # from storage rather than from `contact`, because the kiosk keys its
    # fields by id and a test keys them by name — this is where both are the
    # same thing again.
    job = db.get_scheduled_job(row.job_id)
    typed = {c.name: c.value for c in db.get_job_contact(row.job_id)}
    db.set_job_customer(
        row.job_id,
        find_or_create_customer(job.business_id, typed, user_id).id
    )

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


def get_appointment(
    job_id: int,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
    """A booking as the customer who made it sees it."""
    row = db.get_appointment(job_id)
    if row is None:
        return None
    return Appointment(
        id=row.id,
        jobCode=row.job_code,
        businessId=row.business_id,
        businessName=row.business_name,
        businessPhone=row.business_phone,
        jobTypeId=row.job_type_id,
        jobTypeName=row.job_type_name,
        sizeId=row.size_id,
        sizeName=row.size_name,
        cost=row.cost,
        scheduledDate=row.scheduled_date,
        scheduledTime=row.scheduled_time,
        displayDate=display_date(row.scheduled_date),
        displayTime=display_time(row.scheduled_time),
        durationMinutes=row.duration_minutes,
        status=row.status,
        changesClosed=_changes_closed(row, now or datetime.now()),
        locked=row.locked_date is not None,
        employees=[f"{e.first_name} {e.last_name[:1]}."
        for e in db.get_employees_on_job(row.id)]
    )


def get_job_detail(
    business_id: int,
    job_id: int,
    employee_id: Optional[int] = None
) -> Optional[JobDetail]:
    """A booking as the operator sees it.

    More than `get_appointment` returns, because the operator acts on it: what
    was paid, what the customer answered, who is doing it, and how many wrong
    codes somebody has tried — the last being what they are usually being
    called about.

    `employee_id` narrows it to a booking they are on, which is what an
    employee reaches. `None` is the operator, who reaches the business.
    """
    row = db.get_job_detail(business_id, job_id)
    if row is not None and employee_id is not None:
        crew = _crew_for([row.id]).get(row.id, [])
        if not any(c.employee_id == employee_id for c in crew):
            return None
    if row is None:
        return None

    return JobDetail(
        id=row.id,
        jobCode=row.job_code,
        jobType=EmployeeJobType(id=row.job_type_id, name=row.job_type_name),
        size=(Size(
            id=row.size_id,
            name=row.size_name or "",
            durationMinutes=row.size_duration_minutes or 0,
            cost=row.cost or 0.0
        )
              if row.size_id is not None else None),
        scheduledDate=row.scheduled_date,
        scheduledTime=row.scheduled_time,
        durationMinutes=row.duration_minutes,
        status=row.status,
        paymentStatus=row.payment_status,
        locked=row.locked_date is not None,
        failedCodeAttempts=db.count_access_attempts(job_id),
        isRecurring=bool(row.is_recurring),
        employees=[JobTypeEmployee(
            id=e.id,
            firstName=e.first_name,
            lastName=e.last_name
        )
                   for e in db.get_employees_on_job(job_id)],
        customer=_job_customer(row),
        attributes=[JobAttribute(name=a.name, value=a.value)
                    for a in db.get_job_attributes(job_id)],
        transactions=get_payments(job_id),
    )


def _job_customer(row: "db.JobDetailRow") -> JobCustomer:
    """Who the work is for.

    A booking need not have a customer record behind it — most do not, because
    a customer books without an account and the business has never served them
    before. What they typed at booking is then the only answer there is, and
    `id` is 0 to say there is nothing to open.
    """
    if row.customer_id is not None:
        c = db.get_customer_anywhere(row.customer_id)
        if c is not None:
            return JobCustomer(
                id=c.id,
                firstName=c.first_name,
                lastName=c.last_name,
                phone=c.phone or "",
                email=c.email or "",
                addressLine1=c.address_line1 or "",
                city=c.city or "",
                state=c.state or "",
                zip=c.zip or ""
            )

    typed = {c.name: c.value for c in db.get_job_contact(row.id)}
    return JobCustomer(
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
    starts = datetime.strptime(
        f"{row.scheduled_date} {row.scheduled_time}",
        "%Y-%m-%d %H:%M"
    )
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


def reschedule_appointment(
    job_id: int,
    scheduled_date: str,
    scheduled_time: str,
    as_operator: bool = False,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
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


def update_job(
    business_id: int,
    job_id: int,
    scheduled_date: str,
    scheduled_time: str,
    employee_ids: List[int],
    now: Optional[datetime] = None
) -> Optional[JobDetail]:
    """The schedule and the crew, as the operator's Job window saves them.

    The crew is set rather than added to: the window sends who is on the job,
    and somebody taken off it has to come off.

    The customer hears only about a move. Changing who is coming is the
    business's own arrangement, and telling a customer their time has moved to
    the time it already had is worse than telling them nothing.
    """
    job = db.get_job_detail(business_id, job_id)
    if job is None:
        raise ValidationError("That appointment no longer exists.")

    for employee_id in employee_ids:
        if db.get_employee(business_id, employee_id) is None:
            raise ValidationError("That employee does not work for this business.")

    if (scheduled_date, scheduled_time) != (job.scheduled_date, job.scheduled_time):
        reschedule_appointment(
            job_id,
            scheduled_date,
            scheduled_time,
            as_operator=True,
            now=now
        )

    db.clear_job_employees(job_id)
    for employee_id in employee_ids:
        db.assign_employee_to_job(job_id, employee_id)

    # The same shape the operator read it in, so a save answers in the terms
    # the screen asked in.
    return get_job_detail(business_id, job_id)


def cancel_appointment(
    job_id: int,
    as_operator: bool = False,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
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


def send_otp(
    session_token: str,
    destination: str,
    now: Optional[datetime] = None
) -> OtpResult:
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


def verify_otp(
    session_token: str,
    code: str,
    now: Optional[datetime] = None
) -> OtpResult:
    """Check a code against the one that was sent.

    A correct code spends no attempt; the three are for getting it wrong.
    """
    _live_session(session_token, now)
    record = db.get_otp(session_token)
    if record is None or record[0] is None:
        raise ValidationError("No code has been sent for this session.")

    stored, attempts, verified = record
    if verified:
        return OtpResult(
            verified=True,
            attemptsRemaining=MAX_OTP_ATTEMPTS - attempts
        )
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
    return OtpResult(
        verified=True,
        attemptsRemaining=MAX_OTP_ATTEMPTS - attempts
    )


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


def request_appointment_access(
    job_code: str,
    caller: Optional[str] = None,
    now: Optional[datetime] = None
) -> Delivery:
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
    db.insert_access_code(
        job.id,
        f"{salt}:{_hash_code(code, salt)}",
        channel,
        destination,
        expires
    )

    if _otp_sender is not None:
        _otp_sender(destination, code)
    return Delivery(channel=channel, sentTo=_mask(channel, destination))


def get_appointment_by_code(
    job_code: str,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
    """The appointment a job code names, without proving anything.

    For an operator, and for a test that already knows the code is real. The
    customer's route is `verify_appointment_access`, which asks for proof.
    """
    job = db.get_job_by_code(job_code)
    return None if job is None else get_appointment(job.id, now=now)


def verify_appointment_access(
    job_code: str,
    code: str,
    now: Optional[datetime] = None
) -> Appointment:
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
        if db.count_recent_access_attempts(
            job.id,
            window_opened
        ) >= MAX_ACCESS_ATTEMPTS:
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
            _otp_sender(
                row.value,
                "Your appointment has been locked after too many"
                " incorrect verification attempts. Please contact the"
                " business to make a change."
            )


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
        id=row.id,
        businessId=row.business_id,
        jobTypeId=row.job_type_id,
        jobTypeSizeId=row.job_type_size_id,
        intervalType=row.interval_type,
        daysOfWeek=json.loads(row.days_of_week_json) if row.days_of_week_json else [],
        preferredTime=row.preferred_time,
        isActive=bool(row.is_active)
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


def create_recurrence(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int],
    interval_type: str,
    preferred_time: str,
    days_of_week: Optional[List[int]] = None
) -> Recurrence:
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
        db.insert_recurrence(
            business_id,
            job_type_id,
            size_id,
            interval_type,
            days,
            preferred_time
        )
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
        RecurringJob(
            id=r.id,
            jobCode=r.job_code,
            scheduledDate=r.scheduled_date,
            scheduledTime=r.scheduled_time,
            status=r.status,
            employeeIds=db.get_job_employee_ids(r.id)
        )
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


def get_schedule_month(
    business_id: int,
    year: int,
    month: int,
    employee_id: Optional[int] = None
) -> ScheduleMonth:
    """How busy each day of a month is.

    Only the days with work on them. The screen draws a grid of every day and
    fills in what it is given, so an empty day is an absence rather than a zero.
    """
    start, end = _month_bounds(year, month)
    counts: Dict[str, int] = {}
    for row in _for_employee(
        db.get_scheduled_jobs(business_id, start, end),
        employee_id
    ):
        counts[row.scheduled_date] = counts.get(row.scheduled_date, 0) + 1
    return ScheduleMonth(
        year=year,
        month=month,
        # In date order because the rows arrive in date order and a dict keeps
        # what it was given.
        days=[Day(date=date, jobCount=count) for date, count in counts.items()]
    )


def get_schedule_week(
    business_id: int,
    date: str,
    employee_id: Optional[int] = None
) -> ScheduleWeek:
    """Seven days from the Sunday, whatever day was asked about.

    Always seven, empty ones included: the week is a row of columns, and a day
    left out would close the gap and mislabel every column after it.
    """
    start = _week_start(date)
    end = (datetime.strptime(
        start,
        "%Y-%m-%d"
    ) + timedelta(days=6)).strftime("%Y-%m-%d")

    rows = _for_employee(
        db.get_scheduled_jobs(business_id, start, end),
        employee_id
    )
    crew = _crew_for([r.id for r in rows])

    days = []
    for offset in range(7):
        on = (datetime.strptime(start, "%Y-%m-%d")
              + timedelta(days=offset)).strftime("%Y-%m-%d")
        days.append(ScheduleWeekDay(
            date=on,
            displayDate=_display_week_day(on),
            jobs=[
                ScheduleWeekJob(
                    id=r.id,
                    jobCode=r.job_code,
                    jobType=r.job_type_name,
                    startTime=r.scheduled_time,
                    endTime=_end_time(r.scheduled_time, r.duration_minutes),
                    employeeInitials=[_initials(e) for e in crew.get(r.id, [])],
                    status=r.status
                )
                for r in rows if r.scheduled_date == on
            ],
        ))
    return ScheduleWeek(weekStart=start, days=days)


def _crew_for(job_ids: List[int]) -> Dict[int, list]:
    """Who is on each of these jobs, in one query rather than one per job."""
    crew: Dict[int, list] = {}
    for row in db.get_employees_for_jobs(job_ids):
        crew.setdefault(row.job_id, []).append(row)
    return crew


def _for_employee(rows: list, employee_id: Optional[int]) -> list:
    """The jobs this employee is on.

    `None` leaves the rows as they are, which is what an operator sees. An
    employee's calendar reads the same routes as the operator's, so the caller
    is what narrows them.
    """
    if employee_id is None:
        return rows
    crew = _crew_for([r.id for r in rows])
    return [r for r in rows
            if any(c.employee_id == employee_id
                   for c in crew.get(r.id, []))]


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
            column = next(
                (i for i, free in enumerate(columns) if free <= start),
                len(columns)
            )
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


def get_schedule_day(
    business_id: int,
    date: str,
    employee_id: Optional[int] = None
) -> ScheduleDay:
    """One day, laid out so two appointments at once can both be seen."""
    rows = _for_employee(
        db.get_scheduled_jobs(business_id, date, date),
        employee_id
    )
    crew = _crew_for([r.id for r in rows])
    layout = _lay_out([
        (r.id, to_minutes(r.scheduled_time),
         to_minutes(r.scheduled_time) + r.duration_minutes)
        for r in rows
    ])

    return ScheduleDay(
        date=date,
        jobs=[
            ScheduleDayJob(
                id=r.id,
                jobCode=r.job_code,
                jobType=r.job_type_name,
                customerName=" ".join(
                part for part in (r.first_name, r.last_name) if part),
                startTime=r.scheduled_time,
                endTime=_end_time(r.scheduled_time, r.duration_minutes),
                startMinuteOffset=to_minutes(r.scheduled_time),
                durationMinutes=r.duration_minutes,
                employees=[AppointmentEmployee(
                    firstName=e.first_name,
                    lastInitial=e.last_name[:1]
                )
                for e in crew.get(r.id, [])],
                overlapColumn=layout[r.id][0],
                overlapTotal=layout[r.id][1],
                status=r.status,
                paymentStatus=r.payment_status
            )
            for r in rows
        ],
    )


def get_unassigned_jobs(business_id: int) -> List[JobsUnassignedJob]:
    """Live appointments with nobody on them, for Needs Attention."""
    return [
        JobsUnassignedJob(
            id=r.id,
            jobCode=r.job_code,
            jobType=r.job_type_name,
            customerName=" ".join(
            part for part in (r.first_name, r.last_name) if part),
            scheduledDate=r.scheduled_date,
            scheduledTime=r.scheduled_time,
            displayDate=display_date(r.scheduled_date),
            displayTime=display_time(r.scheduled_time),
            isRecurring=bool(r.is_recurring)
        )
        for r in db.get_unassigned_jobs(business_id)
    ]


def assign_jobs(
    business_id: int,
    job_ids: List[int],
    now: Optional[datetime] = None
) -> JobsAssign:
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

        free = employees_free_at(
            business_id,
            row.job_type_id,
            row.job_type_size_id,
            row.scheduled_date,
            row.scheduled_time,
            now=now
        )
        if not free:
            unassigned += 1
            continue

        job_type = get_job_type(business_id, row.job_type_id)
        wanted = job_type.minEmployees if job_type else 1
        for employee_id in free[:wanted]:
            db.assign_employee_to_job(job_id, employee_id)
        assigned += 1

    return JobsAssign(assigned=assigned, unassigned=unassigned)


def get_dashboard(
    business_id: int,
    now: Optional[datetime] = None
) -> Optional[Dashboard]:
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
            if not employees_free_at(
                business_id,
                r.job_type_id,
                r.job_type_size_id,
                r.scheduled_date,
                r.scheduled_time,
                now=now
            )
        ])

    return Dashboard(
        # The kiosk button opens against a business, and the screen already
        # asks this route for everything else it draws.
        businessId=business_id,
        isActive=bool(business_row.is_active),
        # `unlimited` allocates nobody, so the screen hides the panel rather
        # than showing a count that can only ever be the whole list.
        slotMode=business.slotMode,
        jobsToday=db.count_jobs_between(business_id, today, today),
        jobsThisWeek=db.count_jobs_between(business_id, week_start, week_end),
        revenueThisMonth=db.get_revenue_between(
            business_id,
            month_start,
            month_end
        ),
        upcomingJobs=db.count_jobs_between(business_id, today, LAST_DATE),
        unassignedJobs=len(waiting),
        unassignedConflicts=conflicts,
    )


# Far enough out that "upcoming" means everything ahead. A date rather than a
# window: an appointment booked two years from now is still upcoming.
LAST_DATE = "9999-12-31"


def _recurrence_dates(
    recurrence: Recurrence,
    start: str,
    last: str
) -> List[str]:
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
                _job_code(),
                business.id,
                recurrence.jobTypeId,
                recurrence.jobTypeSizeId,
                date,
                recurrence.preferredTime,
                duration,
                recurrence.id
            )
            for employee_id in _free_for(
                business,
                recurrence,
                date,
                duration,
                now
            ):
                db.assign_employee_to_job(job_id, employee_id)
            created += 1
    return created


def _free_for(
    business: Business,
    recurrence: Recurrence,
    date: str,
    duration: int,
    now: datetime
) -> List[int]:
    """Who could take this instance, or nobody.

    Asked of the same availability the kiosk asks, so a recurrence cannot be
    assigned someone the booking screen would refuse.
    """
    slots = get_available_slots(
        business.id,
        recurrence.jobTypeId,
        recurrence.jobTypeSizeId,
        limit=100,
        from_date=date,
        now=now
    )
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

def set_confirmation_channels(
    business_id: int,
    by_sms: bool,
    by_email: bool
) -> Optional[Business]:
    """Which channels a booking confirmation goes out on. Either, both, neither."""
    db.set_business_confirmation(
        business_id,
        1 if by_sms else 0,
        1 if by_email else 0
    )
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
                out.append(Delivery(
                    channel=channel,
                    sentTo=_mask(channel, contact.value)
                ))
                break
    return out


#
# `payment_status` is derived from what has been taken rather than set by hand,
# so it cannot disagree with the transactions underneath it. The one exception
# is writing off, which is a decision rather than an arithmetic result — and
# even that gives way if money turns up later.


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


def send_reminders(now: Optional[datetime] = None) -> int:
    """Remind tomorrow's customers. Returns how many were told.

    Daily. Tomorrow rather than a window, because that is what the business
    turned on — a reminder the day before — and a window would send a second
    one to anybody whose appointment sat inside it twice.

    Nothing records that a reminder went out, so running this twice in a day
    sends two. The cron runs it once; that is the whole of the mechanism, and
    it is worth knowing before this is called from anywhere else.
    """
    now = now or datetime.now()
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    told = 0
    for job_id in db.get_jobs_to_remind(tomorrow):
        details = db.get_confirmation_details(job_id)
        if details is None:
            continue
        _notify_customer(
            job_id,
            f"{details.business_name}: a reminder that your"
            f" {details.job_type_name} is tomorrow,"
            f" {display_date(details.scheduled_date)} at"
            f" {display_time(details.scheduled_time)}."
            f" Job code {details.job_code}."
        )
        told += 1
    return told


def complete_job(
    job_id: int,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
    """Mark work done, and send the customer a receipt."""
    row = db.get_appointment(job_id)
    if row is None:
        raise ValidationError("That appointment no longer exists.")
    if row.status == "cancelled":
        raise ValidationError("That appointment was cancelled.")

    db.set_job_status(job_id, "completed")
    details = db.get_confirmation_details(job_id)
    if details is not None:
        _notify_customer(
            job_id,
            _receipt_message(details, db.get_paid_total(job_id))
        )
    return get_appointment(job_id, now=now)


def complete_finished_jobs(now: Optional[datetime] = None) -> int:
    """Finish appointments whose time has passed, at businesses set to `auto`.

    Runs on a schedule. Returns how many were finished.
    """
    now = now or datetime.now()
    finished = 0
    for row in db.get_confirmed_jobs_for_auto_completion():
        ends = (datetime.strptime(
            f"{row.scheduled_date} {row.scheduled_time}",
            "%Y-%m-%d %H:%M"
        )
                + timedelta(minutes=row.duration_minutes))
        if now > ends:
            complete_job(row.id, now=now)
            finished += 1
    return finished


# --- Finding an appointment ----------------------------------------------

def search_jobs(
    business_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    job_type_id: Optional[int] = None,
    job_code: Optional[str] = None,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    employee_id: Optional[int] = None,
    limit: int = 200
) -> List[Job]:
    """Appointments matching what the operator narrowed by.

    An inverted range is refused rather than answered with nothing found.
    "No appointments" to a range that cannot contain any tells the operator
    their data is missing, when their dates are backwards.

    An open range is a range: one end, or neither, constrains what it can.

    `YYYY-MM-DD` compares correctly as a string, so no parsing is needed.
    """
    if from_date and to_date and from_date > to_date:
        raise InvalidDateRange("The From date has to be on or before the To date.")

    rows = db.search_jobs(
        business_id,
        from_date,
        to_date,
        status,
        job_type_id,
        job_code,
        name,
        phone,
        employee_id,
        limit
    )

    # Who is doing the work, for every row at once. Asking per row would be one
    # query per result, and the screen draws fifty.
    crew: Dict[int, List[AppointmentEmployee]] = {}
    for e in db.get_employees_for_jobs([r.id for r in rows]):
        crew.setdefault(e.job_id, []).append(
            AppointmentEmployee(
                firstName=e.first_name,
                lastInitial=e.last_name[:1]
            ))

    return [
        Job(
            id=r.id,
            jobCode=r.job_code,
            jobType=r.job_type_name,
            customerName=" ".join(
            part for part in (r.first_name, r.last_name) if part),
            scheduledDate=r.scheduled_date,
            scheduledTime=r.scheduled_time,
            displayDate=display_date(r.scheduled_date),
            displayTime=display_time(r.scheduled_time),
            status=r.status,
            paymentStatus=r.payment_status,
            employees=crew.get(r.id, [])
        )
        for r in rows
    ]


#
# Revenue is money that arrived, not money that was owed. A written-off job
# leaves whatever was paid in revenue and the unpaid balance in write-offs, so
# the two columns together account for the work rather than double-counting it.


# --- What one person sees of their own work -------------------------------
#
# An employee sees what they have been given, one day at a time, reached by
# the signed-in BOSS user through the `user_id` their record carries.
#
# A customer has no portal here. Theirs is the kiosk, which asks for no
# account: they find an appointment by its code.


def link_employee_to_user(
    business_id: int,
    employee_id: int,
    user_id: int
) -> Employee:
    """Say which BOSS account works under this employee record.

    An account works for one business, so an account already linked elsewhere
    is refused here rather than by the unique index — which would surface as a
    database error where a message is wanted.

    The route grants them the app license and the employee role afterwards.
    Both reach BOSS over the network, which `lib` does not do.
    """
    if db.get_employee(business_id, employee_id) is None:
        raise ValidationError("That employee no longer exists.")
    existing = db.get_employee_by_user(user_id)
    if existing is not None and existing.id != employee_id:
        raise ValidationError(
            "That account already works for a business. Working for a second"
            " one means a second account."
        )
    db.set_employee_user(employee_id, user_id)
    return get_employee(business_id, employee_id)


def unlink_employee_from_user(business_id: int, employee_id: int) -> Employee:
    """Take the BOSS account off an employee record.

    The record stays: they are still on the schedule and still named on the
    appointments they worked. What goes is the account's reach into this
    business, which the route revokes.
    """
    if db.get_employee(business_id, employee_id) is None:
        raise ValidationError("That employee no longer exists.")
    db.set_employee_user(employee_id, None)
    return get_employee(business_id, employee_id)


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
        jobTypes=[EmployeeJobType(id=j.id, name=j.name)
                  for j in get_employee_job_types(row.id)],
    )


def update_employee_profile(
    user_id: int,
    job_type_ids: List[int]
) -> EmployeeProfile:
    """What an employee says about themselves: the work they take.

    Their name, their business, and whether they may manage their own schedule
    at all are the operator's to set.
    """
    row = db.get_employee_by_user(user_id)
    if row is None:
        raise ValidationError("You are not on this business's staff.")

    for job_type_id in job_type_ids:
        if db.get_job_type(row.business_id, job_type_id) is None:
            raise ValidationError("That service is not one this business offers.")

    set_employee_job_types(row.id, job_type_ids)
    return get_employee_profile(user_id)


def get_employee_today(
    user_id: int,
    date: str = "",
    now: Optional[datetime] = None
) -> Optional[EmployeeToday]:
    """The work one employee has in front of them on one day."""
    row = db.get_employee_by_user(user_id)
    if row is None:
        return None
    date = date or (now or datetime.now()).strftime("%Y-%m-%d")

    jobs = []
    for job in db.get_jobs_for_employee(row.id, date):
        typed = {c.name: c.value for c in db.get_job_contact(job.id)}
        jobs.append(EmployeeTodayJob(
            id=job.id,
            jobCode=job.job_code,
            jobType=job.job_type_name,
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
            attributes=[JobAttribute(name=a.name, value=a.value)
            for a in db.get_job_attributes(job.id)],
            status=job.status
        ))

    return EmployeeToday(
        date=date,
        displayDate=display_date(date),
        jobs=jobs,
        canManageOwnSchedule=bool(row.can_manage_own_schedule),
    )


#
# The same three facts slot availability rests on, asked of one employee: the
# days they work, the windows they are away, and whether they are in the
# schedule at all. Somebody out of the schedule is never available, whatever
# their working days say — which is what the flag is for.


#
# A template is a set of opinions, not a full configuration: it writes the
# settings it has a view on and leaves the rest as they were. That is why
# applying a second one on top of a first does not undo it.


# --- What the routes need on top of the rules ----------------------------

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


#
# One question, computed on every call rather than kept in a column. A rule
# added here takes effect everywhere at once, and there is no flag that can
# fall out of step with the thing it describes.
#
# The sentences are the server's, and so is the window each one names: it is
# the side that knows which job type is missing what.


