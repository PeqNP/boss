#
# Scheduler — a storage row, as the domain says it.
#
# `db.py` answers in the shape the table has, snake_case and integers for
# booleans. Every model a screen reads is built here, once per concept, so a
# column rename is a storage decision that stops at this file.
#
# See `python.md` § Models for why the transformation lives in one place
# rather than beside each caller.
#

from typing import List, Optional

from .. import db
from ..model import *
from .time import display_date, display_time

# Underscored because they are `lib`'s and nobody else's — a route builds no
# model from a row. Named here because `import *` passes over them otherwise,
# and every module in this package builds its answers from these.
__all__ = ["_business", "_hours", "_job_type", "_size", "_employee"]


def _business(row: db.BusinessRow) -> Business:
    return Business(
        id=row.id,
        name=row.name,
        phone=row.phone,
        timezone=row.timezone,
        slotMode=row.slot_mode,
        slotIncrementMinutes=row.slot_increment_minutes,
        cutoffDays=row.cutoff_days,
        minBookingNoticeHours=row.min_booking_notice_hours,
        minChangeNoticeMinutes=row.min_change_notice_minutes,
        bufferMinutes=row.buffer_minutes,
        isActive=bool(row.is_active)
    )


def _hours(row: db.BusinessHoursRow) -> BusinessHours:
    return BusinessHours(
        dayOfWeek=row.day_of_week,
        openTime=row.open_time,
        closeTime=row.close_time,
        isClosed=bool(row.is_closed)
    )


def _job_type(row: db.JobTypeRow) -> JobType:
    return JobType(
        id=row.id,
        businessId=row.business_id,
        name=row.name,
        minEmployees=row.min_employees,
        isActive=bool(row.is_active)
    )


def _size(row: db.JobTypeSizeRow) -> JobTypeSize:
    return JobTypeSize(
        id=row.id,
        jobTypeId=row.job_type_id,
        name=row.name,
        durationMinutes=row.duration_minutes,
        cost=row.cost,
        sortOrder=row.sort_order
    )


def _employee(row: db.EmployeeRow) -> Employee:
    return Employee(
        id=row.id,
        businessId=row.business_id,
        userId=row.user_id,
        firstName=row.first_name,
        lastName=row.last_name,
        includeInSchedule=bool(row.include_in_schedule),
        canManageOwnSchedule=bool(row.can_manage_own_schedule)
    )
