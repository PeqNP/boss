#
# Scheduler — which business somebody belongs to, and as what.
#
# One `employees` row ties a BOSS account to a business and says whether they
# run it or work for it. One business per account, which is what makes
# `whoami` a single lookup and every scoped route a single question.
#

from typing import Optional

from .. import db
from ..model import *
from .business import (CONFIG_FIELDS, apply_business_template,
                       create_business, update_business_config)
from .exception import ValidationError
from .transform import _employee


def is_operator_role(role: str) -> bool:
    """Whether a role on an `employees` row is the one that runs the business."""
    return role == Role.OPERATOR


def operator_business(user_id: int) -> Optional[int]:
    """The business this user runs, or nothing.

    An employee of a business runs nothing, so this answers for the operator
    alone. `is_working_for_business` is the question a scoped route asks.
    """
    row = db.get_employee_by_user(user_id)
    return (row.business_id if row is not None
            and is_operator_role(row.role) else None)


def is_operator_of(business_id: int, user_id: int) -> bool:
    """Whether this user runs *this* business.

    Owning some business is not owning this one — the kiosk's close button
    hides the menu bar and the dock behind it, so anyone given it can walk out
    of the kiosk and into BOSS.
    """
    row = db.get_employee_for_business(business_id, user_id)
    return row is not None and is_operator_role(row.role)


def employee_record(business_id: int, user_id: Optional[int]):
    """This account's record at this business, or nothing.

    What a route reads to tell an operator from an employee.
    """
    if user_id is None:
        return None
    return db.get_employee_for_business(business_id, user_id)


def is_working_for_business(business_id: int, user_id: Optional[int]) -> bool:
    """Whether this account works for this business, in any role.

    The one question a business-scoped route asks. True for the operator who
    runs it and for anybody employed by it, and the answer a record's own
    business is compared against.
    """
    # SQL agrees today — `user_id = NULL` matches nothing, including the rows
    # of people added before they had an account. It stops agreeing the moment
    # that query is written with `IS`, which would hand every one of those rows
    # to a caller who is nobody.
    if user_id is None:
        return False
    return db.get_employee_for_business(business_id, user_id) is not None


def whoami(user_id: int) -> Me:
    """Which screen the app opens on for this user.

    The desktop carries whoever works for a business. Somebody who works for
    none is offered one — a customer's surface is the kiosk, which asks for no
    account at all, so there is nobody here for a `customer` role to name.
    """
    row = db.get_employee_by_user(user_id)
    if row is None:
        return Me(role=None, businessId=0)
    return Me(role=row.role, businessId=row.business_id)


def sign_up(
    user_id: int,
    details: dict,
    template_id: Optional[int] = None
) -> Signup:
    """Open a business, and make this user its operator.

    The template is applied before the record is written, so a template that
    does not exist leaves nothing behind: the business is created, refused,
    and rolled back by the same failure that would otherwise leave a business
    nobody runs.
    """
    if db.get_employee_by_user(user_id) is not None:
        raise ValidationError("You already work for a business.")

    name = str(details.get("name", "")).strip()
    if not name:
        raise ValidationError("Please provide a business name.")

    if template_id is not None and db.get_business_template(template_id) is None:
        raise ValidationError("That template no longer exists.")

    business = create_business(
        name,
        details.get("timezone") or "UTC",
        "reserved"
    )
    rest = {k: v for k, v in details.items()
            if k != "name" and k in CONFIG_FIELDS and v is not None}
    if rest:
        update_business_config(business.id, rest)
    if template_id is not None:
        apply_business_template(business.id, template_id)

    name_parts = str(details.get("ownerName", "")).strip().split(None, 1)
    operator_id = db.insert_employee_member(
        business.id,
        user_id,
        Role.OPERATOR,
        name_parts[0] if name_parts else "Owner",
        name_parts[1] if len(name_parts) > 1 else ""
    )
    return Signup(businessId=business.id, operatorId=operator_id)
