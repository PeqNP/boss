#
# Scheduler — holding a time, and turning the hold into an appointment.
#
# A kiosk session is a hold: the customer picked a time and is filling in the
# rest, and the time is theirs until they finish or the hold lapses. Confirming
# is what makes it an appointment and tells them it is booked.
#
# A contact detail is verified before it is trusted — a code goes to what they
# typed, and only a field that can receive one can be verified at all.
#

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .. import db
from ..model import *
from .code import _hash_code, _job_code, _mask
from .customer import find_or_create_customer, link_job_to_customer
from .exception import *
from .availability import _duration_minutes
from .business import get_business
from .notify import channel_for, send, set_sender
from .platform import get_schedule_timeout_minutes
from .time import _stamp, display_date, display_time


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


MAX_OTP_ATTEMPTS = 3


OTP_LENGTH = 6


def send_otp(
    session_token: str,
    channel: str,
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

    send(channel, destination, code)
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
                send(channel, contact.value, message)
                out.append(Delivery(
                    channel=channel,
                    sentTo=_mask(channel, contact.value)
                ))
                break
    return out


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
