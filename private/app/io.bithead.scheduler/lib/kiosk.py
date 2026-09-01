#
# Scheduler — what a customer standing at the kiosk is shown.
#
# The kiosk asks for no account and is the whole of the customer surface. Each
# of these answers one step of the booking: which services, which people, which
# days have anything open, and which times on the day they picked.
#
# Narrower than what an operator sees, deliberately. `KioskEmployee` carries no
# `employeeIds` against a slot — telling a customer who is free at every time
# they did not choose is not theirs to know.
#

from datetime import date as _date, datetime, timedelta
from typing import List, Optional

from .. import db
from ..model import *
from .availability import get_available_slots
from .business import get_operating_hours, get_setup
from .employee import get_employees
from .job_type import (get_job_types, get_job_type_attributes,
                       get_job_type_contact_fields, get_job_type_sizes)
from .platform import get_schedule_timeout_minutes
from .time import display_date, display_time


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
