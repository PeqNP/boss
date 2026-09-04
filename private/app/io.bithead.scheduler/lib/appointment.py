#
# Scheduler — an appointment after it is made.
#
# Moving it, cancelling it, finishing it, and letting the customer back in to
# do the first two. A customer proves who they are with a job code and a code
# sent to the contact they gave; six wrong codes locks the appointment to them
# for good, and the operator still changes it from the admin screens.
#
# `as_operator` is what separates the two callers. A customer is held to the
# business's change window and to the lock; an operator is held to neither.
#

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .. import db
from ..model import *
from .code import _access_handle, _hash_code, _mask
from .employee import _crew_for
from .exception import *
from .business import get_business
from .money import _business_job, get_payments
from .notify import send, sender
from .time import _end_time, _stamp, display_date, display_time


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


ACCESS_CODE_MINUTES = 30


ACCESS_CODE_LENGTH = 6


# Live statuses. A cancelled or completed appointment has nothing to get back
# into, and saying so beats sending a code that leads nowhere.
ACTIVE_STATUSES = ("pending", "confirmed")


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

    send(channel, destination, code)
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


def appointment_for_handle(
    handle: str,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
    """The appointment a verified customer holds this handle for.

    `None` when the handle opens nothing, which is every caller who has not
    proved who they are. The routes answer that with a 404 rather than a
    refusal: an appointment id is a small integer and a handle is not, so a
    refusal that distinguished them would say which ids are real.
    """
    job = db.get_job_by_access_handle(handle)
    return None if job is None else get_appointment(job.id, now=now)


def verify_appointment_access(
    job_code: str,
    code: str,
    now: Optional[datetime] = None
) -> AppointmentAccess:
    """Check a code and hand back what opens the appointment.

    A code opens the appointment once. Spending it on success is what stops a
    code shared or intercepted from being a standing key.

    What comes back is a handle rather than the appointment's id, because the
    routes that read, move and cancel it take the handle. An id would let
    anybody who can count reach an appointment they never proved was theirs.
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
    # What the customer carries from here. Minted rather than reused, so a
    # handle from an earlier verification stops opening the appointment.
    handle = _access_handle()
    db.set_job_access_handle(job.id, handle)
    opened = get_appointment(job.id, now=now)
    return AppointmentAccess(
        accessHandle=handle,
        jobCode=opened.jobCode,
        locked=opened.locked,
        businessPhone=opened.businessPhone
    )


MAX_ACCESS_ATTEMPTS = 6


ACCESS_ATTEMPT_WINDOW_SECONDS = 60


def _refuse_if_locked(job) -> None:
    if db.get_job_locked_date(job.id) is not None:
        business = db.get_business_config(job.business_id)
        raise AppointmentLocked(
            "This appointment is locked. Please contact the business to make"
            " a change.",
            business_phone=business.phone if business else None
        )


def _lock_and_notify(job, moment: str) -> None:
    """Shut the door and tell the customer it happened."""
    db.lock_job(job.id, moment)
    if sender() is None:
        return
    # Every channel they gave, not the preferred one: this is the message that
    # explains why nothing works any more, and it should be hard to miss.
    for row in db.get_job_contact(job.id):
        if row.field_type in ("phone", "email") and row.value.strip():
            send(
                "sms" if row.field_type == "phone" else "email",
                row.value,
                "Your appointment has been locked after too many"
                " incorrect verification attempts. Please contact the"
                " business to make a change."
            )


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
    channel, destination = _contact_channel(job_id)
    if channel is not None:
        send(channel, destination, message)


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


def cancel_job(
    business_id: int,
    job_id: int,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
    """Cancel an appointment from the business's side.

    The change-notice window does not apply.
    """
    _business_job(business_id, job_id)
    return cancel_appointment(job_id, as_operator=True, now=now)


def complete_job(
    business_id: int,
    job_id: int,
    now: Optional[datetime] = None
) -> Optional[Appointment]:
    """Mark work done, and send the customer a receipt."""
    row = _business_job(business_id, job_id)
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
            complete_job(row.business_id, row.id, now=now)
            finished += 1
    return finished
