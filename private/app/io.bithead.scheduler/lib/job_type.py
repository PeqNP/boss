#
# Scheduler — the work a business offers, and what it asks before doing it.
#
# A job type is the service a customer picks: its sizes, how long each takes
# and what it costs, the attributes that describe the work, and the contact
# fields the kiosk collects for it.
#
# A job type is created as a draft and named by the save that follows, which
# is also what makes it active — so a half-filled form reaches no customer.
#

import json

from typing import List, Optional

from .. import db
from ..model import *
from .exception import Blocked, ValidationError
from .transform import _job_type, _size


def get_business_holidays(
    business_id: int,
    year: int,
    country_code: str = "US"
) -> List[Holiday]:
    """The year's holidays, and which of them this business closes on."""
    observed = set(db.get_observed_holiday_ids(business_id, year))
    return [
        Holiday(id=r.id, name=r.name, date=r.date, selected=r.id in observed)
        for r in db.get_system_holidays(year, country_code)
    ]


def set_business_holidays(
    business_id: int,
    year: int,
    holiday_ids: List[int],
    country_code: str = "US"
) -> List[Holiday]:
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


def _business_job_type(business_id: int, job_type_id: int) -> "db.JobTypeRow":
    """The job type, if this business offers it. Refused otherwise.

    A job type id off a screen is only meaningful under the business that
    screen was opened for. The business is what the caller was admitted for,
    so a job type read any other way is one they were never admitted to.
    """
    row = db.get_job_type(business_id, job_type_id)
    if row is None:
        raise ValidationError("That job type no longer exists.")
    return row


def _business_size(business_id: int, size_id: int) -> "db.JobTypeSizeRow":
    """The size, if it belongs to a job type this business offers."""
    row = db.get_job_type_size(size_id)
    if row is None:
        raise ValidationError("That size no longer exists.")
    _business_job_type(business_id, row.job_type_id)
    return row


def _business_attribute(
    business_id: int,
    attribute_id: int
) -> "db.JobTypeAttributeRow":
    """The question, if it belongs to a job type this business offers."""
    row = db.get_job_type_attribute(attribute_id)
    if row is None:
        raise ValidationError("That question no longer exists.")
    _business_job_type(business_id, row.job_type_id)
    return row


def _business_contact_field(
    business_id: int,
    field_id: int
) -> "db.JobTypeContactFieldRow":
    """The contact field, if it belongs to a job type this business offers."""
    row = db.get_job_type_contact_field(field_id)
    if row is None:
        raise ValidationError("That contact field no longer exists.")
    _business_job_type(business_id, row.job_type_id)
    return row


def get_job_type_detail(
    business_id: int,
    job_type_id: int
) -> Optional[JobTypeDetail]:
    """Everything the JobType window draws, in one answer.

    The window opens on a draft it has just created and hangs three lists off
    it, so it reads them together — a screen assembling this from four calls
    draws in four stages.
    """
    if db.get_job_type(business_id, job_type_id) is None:
        return None
    row = db.get_job_type_detail(job_type_id)
    if row is None:
        return None
    return JobTypeDetail(
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
        employees=[JobTypeEmployee(
            id=e.id,
            firstName=e.first_name,
            lastName=e.last_name
        )
                   for e in db.get_employees_for_job_type(job_type_id)],
    )


ATTRIBUTE_TYPES = ("text", "number", "dropdown", "checkbox")


# The one kind that is nothing without its choices.
CHOICE_TYPES = ("dropdown",)


def _attribute(row: "db.JobTypeAttributeRow") -> JobTypeAttribute:
    return JobTypeAttribute(
        id=row.id,
        name=row.name,
        attributeType=row.attribute_type,
        options=json.loads(row.options_json) if row.options_json else [],
        isRequired=bool(row.is_required),
        sortOrder=row.sort_order
    )


def _check_attribute(
    name: str,
    attribute_type: str,
    options: Optional[List[Any]]
) -> str:
    """The rules every attribute obeys, whether it is new or being changed."""
    if not name.strip():
        raise ValidationError("Please name the question.")
    if attribute_type not in ATTRIBUTE_TYPES:
        raise ValidationError(
            f"A question is one of: {', '.join(ATTRIBUTE_TYPES)}.")
    if attribute_type in CHOICE_TYPES and not options:
        raise ValidationError("Please give the choices this question offers.")
    return json.dumps(options) if options else None


def add_job_type_attribute(
    business_id: int,
    job_type_id: int,
    name: str,
    attribute_type: str,
    options: Optional[List[Any]] = None,
    is_required: bool = False
) -> JobTypeAttribute:
    """Ask the customer one more thing when they book this."""
    _business_job_type(business_id, job_type_id)
    options_json = _check_attribute(name, attribute_type, options)
    attribute_id = db.insert_job_type_attribute(
        job_type_id,
        name.strip(),
        attribute_type,
        options_json,
        1 if is_required else 0,
        # Appended rather than placed: a new question goes at the end of the
        # form, and the operator reorders from the screen if they want it
        # elsewhere.
        db.next_attribute_sort_order(job_type_id)
    )
    return _attribute(db.get_job_type_attribute(attribute_id))


def get_job_type_attributes(job_type_id: int) -> List[JobTypeAttribute]:
    return [_attribute(r) for r in db.get_job_type_attributes(job_type_id)]


def update_job_type_attribute(
    business_id: int,
    attribute_id: int,
    name: str,
    attribute_type: str,
    options: Optional[List[Any]] = None,
    is_required: bool = False
) -> JobTypeAttribute:
    _business_attribute(business_id, attribute_id)
    options_json = _check_attribute(name, attribute_type, options)
    db.set_job_type_attribute(
        attribute_id,
        name.strip(),
        attribute_type,
        options_json,
        1 if is_required else 0
    )
    return _attribute(db.get_job_type_attribute(attribute_id))


def delete_job_type_attribute(business_id: int, attribute_id: int) -> None:
    """Stop asking. Answers already given stay on the jobs that gave them."""
    _business_attribute(business_id, attribute_id)
    db.delete_job_type_attribute(attribute_id)


def _contact_field(row: "db.JobTypeContactFieldRow") -> JobTypeContactField:
    return JobTypeContactField(
        id=row.id,
        contactFieldTypeId=row.contact_field_type_id,
        name=row.name,
        fieldType=row.field_type,
        isRequired=bool(row.is_required),
        requireOtp=bool(row.require_otp),
        sortOrder=row.sort_order
    )


def _check_contact_field(
    job_type_id: int,
    contact_field_type_id: int,
    require_otp: bool,
    field_id: Optional[int] = None
):
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


def add_job_type_contact_field(
    business_id: int,
    job_type_id: int,
    contact_field_type_id: int,
    is_required: bool = True,
    require_otp: bool = False
) -> JobTypeContactField:
    """Ask the customer for one more detail when they book this."""
    _business_job_type(business_id, job_type_id)
    _check_contact_field(job_type_id, contact_field_type_id, require_otp)
    field_id = db.insert_job_type_contact_field(
        job_type_id,
        contact_field_type_id,
        1 if is_required else 0,
        1 if require_otp else 0,
        db.next_contact_field_sort_order(job_type_id)
    )
    return _contact_field(db.get_job_type_contact_field(field_id))


def get_job_type_contact_fields(job_type_id: int) -> List[JobTypeContactField]:
    return [_contact_field(r) for r in db.get_job_type_contact_fields(job_type_id)]


def update_job_type_contact_field(
    business_id: int,
    field_id: int,
    contact_field_type_id: int,
    is_required: bool = True,
    require_otp: bool = False
) -> JobTypeContactField:
    row = _business_contact_field(business_id, field_id)
    _check_contact_field(
        row.job_type_id,
        contact_field_type_id,
        require_otp,
        field_id
    )
    db.set_job_type_contact_field(
        field_id,
        contact_field_type_id,
        1 if is_required else 0,
        1 if require_otp else 0
    )
    return _contact_field(db.get_job_type_contact_field(field_id))


def delete_job_type_contact_field(business_id: int, field_id: int) -> None:
    """Stop asking. Values already given stay on the bookings that gave them."""
    _business_contact_field(business_id, field_id)
    db.delete_job_type_contact_field(field_id)


def reorder_job_type_contact_fields(
    business_id: int,
    job_type_id: int,
    field_ids: List[int]
) -> List[JobTypeContactField]:
    """Ask them in this order.

    The whole order arrives each time, which is what lets the screen move one
    row with a button and send the result. Every field the job type has appears
    exactly once, so a list that has drifted from the screen is refused whole
    and the order stands as it was.
    """
    _business_job_type(business_id, job_type_id)
    current = [r.id for r in db.get_job_type_contact_fields(job_type_id)]
    if sorted(field_ids) != sorted(current):
        raise ValidationError(
            "That order no longer matches this job type's contact fields.")

    for position, field_id in enumerate(field_ids):
        db.set_contact_field_sort_order(field_id, position)
    return get_job_type_contact_fields(job_type_id)


def get_job_types(
    business_id: int,
    term: Optional[str] = None,
    active_only: bool = False
) -> List[JobType]:
    """What the business offers. `active_only` is the customer's view."""
    return [_job_type(r) for r in db.get_job_types(
        business_id,
        term,
        active_only
    )]


def update_job_type(
    business_id: int,
    job_type_id: int,
    name: str,
    min_employees: Optional[int] = None,
    is_active: Optional[bool] = None,
    icon_id: Optional[int] = None,
    payment_required: Optional[bool] = None,
    deposit_required: Optional[bool] = None,
    deposit_type: Optional[str] = None,
    deposit_amount: Optional[float] = None,
    stripe_product_id: Optional[str] = None,
    stripe_price_id: Optional[str] = None
) -> Optional[JobType]:
    current = get_job_type(business_id, job_type_id)
    if current is None:
        raise ValidationError("That job type no longer exists.")
    if not name or not name.strip():
        raise ValidationError("A job type needs a name.")
    people = current.minEmployees if min_employees is None else min_employees
    if people < 1:
        raise ValidationError("A job needs at least one person to do it.")

    db.update_job_type(
        job_type_id,
        name.strip(),
        people,
        1 if (current.isActive if is_active is None else is_active) else 0
    )
    detail = db.get_job_type_detail(job_type_id)
    if detail is not None and any(value is not None for value in (
        icon_id, payment_required, deposit_required, deposit_type,
        deposit_amount, stripe_product_id, stripe_price_id
    )):
        db.set_job_type_payment(
            job_type_id,
            detail.icon_id if icon_id is None else icon_id,
            (
                detail.payment_required if payment_required is None
                else (1 if payment_required else 0)
            ),
            (
                detail.deposit_required if deposit_required is None
                else (1 if deposit_required else 0)
            ),
            detail.deposit_type if deposit_type is None else deposit_type,
            (
                detail.deposit_amount if deposit_amount is None
                else deposit_amount
            ),
            (
                detail.stripe_product_id if stripe_product_id is None
                else stripe_product_id
            ),
            (
                detail.stripe_price_id if stripe_price_id is None
                else stripe_price_id
            )
        )
    return get_job_type(business_id, job_type_id)


def delete_job_type(business_id: int, job_type_id: int) -> None:
    """Remove work the business no longer offers.

    Refused once an appointment names it: the appointment is still real, and
    the customer expects it. Retiring it with `is_active` is what stops it
    being offered without erasing what it was.
    """
    if get_job_type(business_id, job_type_id) is None:
        raise ValidationError("That job type no longer exists.")
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


def update_job_type_size(
    business_id: int,
    size_id: int,
    name: str,
    duration_minutes: int,
    cost: float
) -> Optional[JobTypeSize]:
    if not name or not name.strip():
        raise ValidationError("A size needs a name.")
    if duration_minutes < 1:
        raise ValidationError("A size needs to take some time.")
    if cost < 0:
        raise ValidationError("A size cannot cost less than nothing.")
    _business_size(business_id, size_id)

    db.update_job_type_size(size_id, name.strip(), duration_minutes, cost)
    return _size(db.get_job_type_size(size_id))


def delete_job_type_size(business_id: int, size_id: int) -> None:
    """Remove a size. Refused once an appointment was booked at it."""
    _business_size(business_id, size_id)
    booked = db.count_jobs_for_size(size_id)
    if booked:
        raise Blocked(
            "This size cannot be deleted while appointments are booked at it.",
            [f"{booked} appointment(s)"]
        )
    db.delete_job_type_size(size_id)


def get_job_type(business_id: int, job_type_id: int) -> Optional[JobType]:
    row = db.get_job_type(business_id, job_type_id)
    return _job_type(row) if row is not None else None


def create_job_type(
    business_id: int,
    name: str,
    min_employees: int = 1
) -> JobType:
    return get_job_type(
        business_id,
        db.insert_job_type(business_id, name, min_employees)
    )


def add_job_type_size(
    business_id: int,
    job_type_id: int,
    name: str,
    duration_minutes: int,
    cost: float
) -> JobTypeSize:
    """A size is what carries the duration and the price."""
    _business_job_type(business_id, job_type_id)
    return _size(db.get_job_type_size(
        db.insert_job_type_size(
            job_type_id,
            name,
            duration_minutes,
            cost,
            db.next_size_sort_order(job_type_id)
        )
    ))
