#
# Scheduler — a business's own settings, and whether it can take a booking.
#
# Everything an operator chooses about how their business runs: its hours, how
# a time is allocated, how much notice a change needs, and what a customer is
# told once they have booked.
#
# `get_setup` is the same settings read as a question — what is still missing
# before a customer could book — which is what the Setup Assistant lists.
#

import json

from typing import Dict, List, Optional

from .. import db
from ..model import *
from .exception import ValidationError
from .transform import _business, _hours, _job_type
from .vendor import channel_chosen, payment_connected


def create_business(
    name: str,
    timezone: str = "UTC",
    slot_mode: str = "reserved"
) -> Business:
    """Start a business. Everything else it needs has a default."""
    return get_business(db.insert_business(name, timezone, slot_mode))


def get_business(business_id: int) -> Optional[Business]:
    row = db.get_business(business_id)
    return _business(row) if row is not None else None


def set_scheduling(
    business_id: int,
    slot_increment_minutes: int,
    cutoff_days: int,
    min_booking_notice_hours: int,
    buffer_minutes: int
) -> Optional[Business]:
    """How far ahead, how soon, and how finely a customer may choose."""
    db.set_business_scheduling(
        business_id,
        slot_increment_minutes,
        cutoff_days,
        min_booking_notice_hours,
        buffer_minutes
    )
    return get_business(business_id)


def set_operating_hours(
    business_id: int,
    day_of_week: int,
    open_time: str,
    close_time: str,
    is_closed: bool = False
) -> List[BusinessHours]:
    """When the business is open on one weekday.

    Under `unlimited` these bound the day. Under `reserved` they say when the
    counter is open, and the employees' own schedules decide what can be
    booked.
    """
    db.set_business_hours(
        business_id,
        day_of_week,
        open_time,
        close_time,
        1 if is_closed else 0
    )
    return get_operating_hours(business_id)


def get_operating_hours(business_id: int) -> List[BusinessHours]:
    return [_hours(r) for r in db.get_business_hours(business_id)]


def close_on_holiday(
    business_id: int,
    name: str,
    date: str,
    country_code: str = "US"
) -> None:
    """Observe a holiday, closing the business for that date."""
    year = int(date[:4])
    holiday_id = db.insert_system_holiday(
        country_code,
        country_code,
        name,
        date,
        year
    )
    db.observe_holiday(business_id, holiday_id, year)


def _task(text, controller, section=None, done=False):
    return SetupTask(
        text=text,
        controller=controller,
        section=section,
        done=done
    )


def get_setup(business_id: int) -> SetupResponse:
    """Everything standing between this business and a booking."""
    business_row = db.get_business(business_id)
    if business_row is None:
        return SetupResponse(configured=False, tasks=[])
    business = _business(business_row)
    reserved = business.slotMode == "reserved"

    tasks = [_task(
        "Give your business a name",
        "BusinessConfig",
        "general",
        bool(business.name and business.name.strip())
    )]

    # Under `unlimited` the hours are the whole answer, so a business with none
    # can offer nothing. Under `reserved` the employees' schedules govern and
    # the hours are shown to the customer, so they are not asked for.
    if not reserved:
        tasks.append(_task(
            "Set the days and hours you are open",
            "BusinessConfig",
            "schedule",
            db.count_open_days(business_id) > 0
        ))

    active = [_job_type(r) for r in db.get_job_types(
        business_id,
        active_only=True
    )]
    tasks.append(_task(
        "Add a service customers can book",
        "JobTypes",
        done=bool(active)
    ))

    for job_type in active:
        tasks.append(_task(
            f'Add a size to "{job_type.name}"',
            "JobTypes",
            done=db.count_job_type_sizes(job_type.id) > 0
        ))
        tasks.append(_task(
            f'Ask "{job_type.name}" for a way to contact the customer',
            "JobTypes",
            done=db.count_job_type_contact_fields(job_type.id) > 0
        ))
        if reserved:
            # Availability comes from employee schedules, so a job type nobody
            # can perform — or nobody works a day for — offers no times ever.
            who = [e for e in db.get_employees_for_job_type(job_type.id)]
            tasks.append(_task(
                f'No employee can perform "{job_type.name}"',
                "Employees",
                done=bool(who)
            ))
            tasks.append(_task(
                f'Give an employee working days for "{job_type.name}"',
                "Employees",
                done=any(db.get_employee_schedule(e.id) for e in who)
            ))
        if db.job_type_requires_otp(job_type.id):
            tasks.append(_task(
                f'Connect a way to send codes — "{job_type.name}" verifies a'
                f' contact detail', "SuperAdminVendors",
                done=channel_chosen("sms") is not None
                or channel_chosen("email") is not None
            ))
        if db.job_type_takes_money(job_type.id):
            tasks.append(_task(
                f'Connect Stripe — "{job_type.name}" takes a payment',
                "BusinessConfig",
                "payment",
                done=payment_connected(business_id)
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
    "templateId": "business_template_id",
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
        templateId=row.business_template_id,
        slotMode=row.slot_mode,
        operatingHours=get_operating_hours(row.id),
        reminderEnabled=bool(row.reminder_enabled),
        confirmBySms=bool(row.confirm_by_sms),
        confirmByEmail=bool(row.confirm_by_email),
        completionMode=row.completion_mode,
        allowCustomerEmployeeSelection=bool(row.allow_customer_employee_selection),
        notifyEmployees=bool(row.notify_employees),
        publicUrl=f"{PUBLIC_URL_BASE}/{row.id}",
        stripeAccountId=db.get_business_stripe_account(row.id),
        paymentVendorChosen=channel_chosen("payment") is not None,
    )


def get_business_config(business_id: int) -> Optional[BusinessConfig]:
    """Everything the Business Settings window shows."""
    row = db.get_business_config(business_id)
    return _config(row) if row is not None else None


def update_business_config(
    business_id: int,
    settings: dict
) -> Optional[BusinessConfig]:
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


TEMPLATE_SETTERS = {
    "slotMode": lambda business_id, value: db.set_business_slot_mode(
        business_id,
        value
    ),
}


def apply_business_template(
    business_id: int,
    template_id: int
) -> Optional[Business]:
    """Write a template's settings onto a business."""
    row = db.get_business_template(template_id)
    if row is None:
        raise ValidationError("That business type is no longer available.")
    business = get_business(business_id)
    if business is None:
        raise ValidationError("That business no longer exists.")

    # Recorded before its settings are written. Only the effects are read
    # anywhere; this is what lets the screen say which type was chosen, which
    # the settings themselves cannot answer — two templates can share them.
    db.set_business_template_id(business_id, template_id)

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
        1 if config.get(
            "allowCustomerEmployeeSelection",
            bool(flags[0])
        ) else 0,
        1 if config.get("notifyEmployees", bool(flags[1])) else 0
    )
    return get_business(business_id)
