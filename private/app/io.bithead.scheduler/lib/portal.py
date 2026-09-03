#
# Scheduler — what an employee sees of their own day.
#
# The schedule routes narrow by who is asking, so this is the same work read
# through the employee's own record: what they have been given, one day at a
# time, and what they may say about themselves.
#

from datetime import datetime
from typing import List, Optional

from .. import db
from ..model import *
from .employee import (get_employee, get_employee_job_types, get_time_off,
                       get_working_days, set_employee_job_types)
from .exception import ValidationError
from .time import _end_time, display_date, display_time


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
        scheduleTemplate=get_working_days(row.business_id, row.id),
        timeOff=get_time_off(row.business_id, row.id),
        jobTypes=[EmployeeJobType(id=j.id, name=j.name)
                  for j in get_employee_job_types(row.business_id, row.id)],
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

    set_employee_job_types(row.business_id, row.id, job_type_ids)
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
