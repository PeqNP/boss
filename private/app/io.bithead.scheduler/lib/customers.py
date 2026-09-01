#
# Scheduler — the people a business books work for.
#
# A customer record belongs to one business: somebody who has used two shops
# has a record at each, and an account signing in claims whichever were left
# unclaimed. Matching one to a booking is the delicate part — an account is
# certain where a typed email is a guess — and `find_or_create_customer` is
# where that judgement lives.
#

from datetime import datetime
from typing import List, Optional

from .. import db
from ..model import *
from .convert import _job_type, _size
from .errors import ValidationError
from .times import display_date, display_time


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


def create_customer(
    business_id: int,
    first_name: str,
    last_name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    user_id: Optional[int] = None
) -> Customer:
    """Record somebody this business has served."""
    if not first_name.strip():
        raise ValidationError("Please provide a first name.")
    customer_id = db.insert_customer(
        business_id,
        first_name.strip(),
        last_name.strip(),
        phone,
        email,
        user_id
    )
    return _customer(db.get_customer(business_id, customer_id))


def get_customers(
    business_id: int,
    term: Optional[str] = None
) -> List[Customer]:
    return [_customer(r) for r in db.get_customers(business_id, term)]


def get_customer(
    business_id: int,
    customer_id: int
) -> Optional[CustomerDetail]:
    """One customer, with what has been written down and what they have booked."""
    row = db.get_customer(business_id, customer_id)
    if row is None:
        return None
    return CustomerDetail(
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
            CustomerAppointment(
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


def update_customer(
    business_id: int,
    customer_id: int,
    details: dict
) -> Optional[CustomerDetail]:
    """Change a customer's contact details.

    Refused outright when a BOSS account owns them: the account holder
    maintains their own details, and an operator editing them would be writing
    over somebody else's record of themselves.
    """
    row = db.get_customer(business_id, customer_id)
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
    return get_customer(business_id, customer_id)


def _phone_digits(phone: str) -> str:
    """A phone number reduced to what identifies it.

    The punctuation goes, and so does anything before the last ten digits —
    the same person writes `(555) 234-5678` one time and `+1 555 234 5678` the
    next, and a country code is not what tells two people apart.
    """
    return "".join(c for c in phone if c.isdigit())[-10:]


def find_or_create_customer(
    business_id: int,
    contact: Dict[str, str],
    user_id: Optional[int] = None
) -> Customer:
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
        candidate = db.find_customer_by_phone_digits(
            business_id,
            _phone_digits(phone)
        )
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
            found = db.get_customer(business_id, found.id)
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
    if db.get_customer_anywhere(customer_id) is None:
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


def add_customer_note(
    business_id: int,
    customer_id: int,
    note: str,
    user_id: int
) -> Note:
    """Write something down about a customer."""
    row = db.get_customer(business_id, customer_id)
    if row is None:
        raise ValidationError("That customer no longer exists.")
    if not note.strip():
        raise ValidationError("Please write the note.")
    note_id = db.insert_customer_note(
        customer_id,
        row.business_id,
        note.strip(),
        user_id
    )
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


def create_job_type(
    business_id: int,
    name: str,
    min_employees: int = 1
) -> JobType:
    return get_job_type(
        business_id,
        db.insert_job_type(business_id, name, min_employees)
    )


def get_job_type(business_id: int, job_type_id: int) -> Optional[JobType]:
    row = db.get_job_type(business_id, job_type_id)
    return _job_type(row) if row is not None else None




def add_job_type_size(
    job_type_id: int,
    name: str,
    duration_minutes: int,
    cost: float
) -> JobTypeSize:
    """A size is what carries the duration and the price."""
    return _size(db.get_job_type_size(
        db.insert_job_type_size(
            job_type_id,
            name,
            duration_minutes,
            cost,
            db.next_size_sort_order(job_type_id)
        )
    ))
