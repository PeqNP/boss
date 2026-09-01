#
# Scheduler — the people a business schedules, and when each of them works.
#
# An employee record exists before the person has a BOSS account: somebody is
# added to the schedule long before they sign in, and an operator links the
# account later. The record is what holds the work; the account only says who
# reaches it.
#
# A working day is a template — the hours they are normally available — and
# time off is what is carved out of it.
#

from typing import Dict, List, Optional

from .. import db
from ..model import *
from .exception import Blocked, ValidationError
from .time import day_of_week, overlaps, to_minutes
from .transform import _employee, _job_type


def create_employee(
    business_id: int,
    first_name: str,
    last_name: str,
    include_in_schedule: bool = True,
    can_manage_own_schedule: bool = False
) -> Employee:
    first_name = (first_name or "").strip()
    if not first_name:
        raise ValidationError("An employee needs a first name.")
    last_name = (last_name or "").strip()
    employee_id = db.insert_employee(
        business_id,
        first_name,
        last_name,
        1 if include_in_schedule else 0,
        1 if can_manage_own_schedule else 0
    )
    return Employee(
        id=employee_id,
        businessId=business_id,
        firstName=first_name,
        lastName=last_name,
        includeInSchedule=include_in_schedule,
        canManageOwnSchedule=can_manage_own_schedule
    )


def allow_job_type(employee_id: int, job_type_id: int) -> None:
    """Say this employee can perform this work."""
    db.link_employee_to_job_type(job_type_id, employee_id)


def _check_span(start_time: str, end_time: str, what: str) -> None:
    if to_minutes(end_time) <= to_minutes(start_time):
        raise ValidationError(f"A {what} has to end after it starts.")


def add_working_day(
    business_id: int,
    employee_id: int,
    day_of_week: int,
    start_time: str,
    end_time: str
) -> EmployeeSchedule:
    """Add a day this employee works. Returns the day that was added.

    The added one rather than the whole list: the list is ordered by weekday,
    so the newest is not the last, and a caller that took the last would report
    a different day than it created.
    """
    if day_of_week not in range(7):
        raise ValidationError("A working day is one of the seven.")
    _check_span(start_time, end_time, "working day")
    if db.get_employee(business_id, employee_id) is None:
        raise ValidationError("That employee no longer exists.")

    day_id = db.insert_employee_schedule(
        employee_id,
        day_of_week,
        start_time,
        end_time
    )
    row = db.get_schedule_day(day_id)
    return EmployeeSchedule(
        id=row.id,
        employeeId=row.employee_id,
        dayOfWeek=row.day_of_week,
        startTime=row.start_time,
        endTime=row.end_time
    )


def get_working_days(employee_id: int) -> List[EmployeeSchedule]:
    return [EmployeeSchedule(
        id=r.id,
        employeeId=r.employee_id,
        dayOfWeek=r.day_of_week,
        startTime=r.start_time,
        endTime=r.end_time
    )
            for r in db.get_employee_schedule(employee_id)]


def add_time_off(
    employee_id: int,
    date: str,
    start_time: str,
    end_time: str
) -> EmployeeTimeOff:
    """A stretch of one day this employee is not available."""
    window_id = db.insert_employee_time_off(
        employee_id,
        date,
        start_time,
        end_time
    )
    return EmployeeTimeOff(
        id=window_id,
        employeeId=employee_id,
        date=date,
        startTime=start_time,
        endTime=end_time
    )


def get_employees(business_id: int) -> List[Employee]:
    return [_employee(r) for r in db.get_employees(business_id)]


def get_employee(business_id: int, employee_id: int) -> Optional[Employee]:
    row = db.get_employee(business_id, employee_id)
    return _employee(row) if row is not None else None


def update_employee(
    business_id: int,
    employee_id: int,
    first_name: str,
    last_name: str,
    include_in_schedule: Optional[bool] = None,
    can_manage_own_schedule: Optional[bool] = None
) -> Optional[Employee]:
    current = get_employee(business_id, employee_id)
    if current is None:
        raise ValidationError("That employee no longer exists.")
    if not first_name or not first_name.strip():
        raise ValidationError("An employee needs a first name.")
    if not last_name or not last_name.strip():
        raise ValidationError("An employee needs a last name.")

    db.update_employee(
        employee_id,
        first_name.strip(),
        last_name.strip(),
        1 if (current.includeInSchedule if include_in_schedule is None
        else include_in_schedule) else 0,
        1 if (current.canManageOwnSchedule if can_manage_own_schedule is None
        else can_manage_own_schedule) else 0
    )
    return get_employee(business_id, employee_id)


def delete_employee(business_id: int, employee_id: int) -> None:
    """Remove somebody who never worked here.

    Refused once an appointment names them: the appointment is still real and
    says who is coming. Taking them out of the schedule is what stops them
    being given more work.
    """
    if get_employee(business_id, employee_id) is None:
        raise ValidationError("That employee no longer exists.")
    assigned = db.count_jobs_for_employee(employee_id)
    if assigned:
        raise Blocked(
            "This employee cannot be deleted while they are assigned to"
            " appointments. Take them out of the schedule instead.",
            [f"{assigned} appointment(s)"]
        )
    db.delete_employee(employee_id)


def get_employee_job_types(employee_id: int) -> List[JobType]:
    """The work this employee is allowed to be given."""
    return [_job_type(r) for r in db.get_job_types_for_employee(employee_id)]


def set_employee_job_types(
    employee_id: int,
    job_type_ids: List[int]
) -> List[JobType]:
    """Replace what this employee may be given, wholesale.

    Sent as the whole list rather than as additions and removals: the form
    shows every job type at once, and a difference computed here cannot
    disagree with what was on screen.
    """
    db.clear_job_types_for_employee(employee_id)
    for job_type_id in job_type_ids:
        db.link_employee_to_job_type(job_type_id, employee_id)
    return get_employee_job_types(employee_id)


def update_working_day(
    schedule_id: int,
    day_of_week: int,
    start_time: str,
    end_time: str
) -> Optional[EmployeeSchedule]:
    if day_of_week not in range(7):
        raise ValidationError("A working day is one of the seven.")
    _check_span(start_time, end_time, "working day")
    if db.get_schedule_day(schedule_id) is None:
        raise ValidationError("That working day no longer exists.")

    db.update_schedule_day(schedule_id, day_of_week, start_time, end_time)
    row = db.get_schedule_day(schedule_id)
    return EmployeeSchedule(
        id=row.id,
        employeeId=row.employee_id,
        dayOfWeek=row.day_of_week,
        startTime=row.start_time,
        endTime=row.end_time
    )


def delete_working_day(schedule_id: int) -> None:
    db.delete_schedule_day(schedule_id)


def get_time_off(employee_id: int) -> List[EmployeeTimeOff]:
    return [EmployeeTimeOff(
        id=r.id,
        employeeId=r.employee_id,
        date=r.date,
        startTime=r.start_time,
        endTime=r.end_time
    )
            for r in db.get_all_time_off(employee_id)]


def update_time_off(
    window_id: int,
    date: str,
    start_time: str,
    end_time: str
) -> Optional[EmployeeTimeOff]:
    _check_span(start_time, end_time, "time-off window")
    if db.get_time_off_window(window_id) is None:
        raise ValidationError("That time-off window no longer exists.")

    db.update_time_off(window_id, date, start_time, end_time)
    row = db.get_time_off_window(window_id)
    return EmployeeTimeOff(
        id=row.id,
        employeeId=row.employee_id,
        date=row.date,
        startTime=row.start_time,
        endTime=row.end_time
    )


def delete_time_off(window_id: int) -> None:
    db.delete_time_off(window_id)


def is_employee_available(
    employee_id: int,
    date: str,
    time: str,
    duration_minutes: int,
    buffer_minutes: int = 0
) -> bool:
    """Whether this employee could take on a stretch of a day."""
    row = db.get_employee_anywhere(employee_id)
    if row is None or not row.include_in_schedule:
        return False

    start = to_minutes(time)
    end = start + duration_minutes + buffer_minutes
    weekday = day_of_week(date)

    shifts = [(to_minutes(s.start_time), to_minutes(s.end_time))
              for s in db.get_employee_schedule(employee_id)
              if s.day_of_week == weekday]
    if not any(shift[0] <= start and end <= shift[1] for shift in shifts):
        return False

    away = [(to_minutes(t.start_time), to_minutes(t.end_time))
            for t in db.get_employee_time_off(employee_id, date)]
    if any(overlaps(start, end, *window) for window in away):
        return False

    committed = db.get_booked_intervals([employee_id], date)
    for interval in committed:
        held = to_minutes(interval.scheduled_time)
        if overlaps(
            start,
            end,
            held,
            held + interval.duration_minutes + buffer_minutes
        ):
            return False
    return True


def _crew_for(job_ids: List[int]) -> Dict[int, list]:
    """Who is on each of these jobs, in one query rather than one per job."""
    crew: Dict[int, list] = {}
    for row in db.get_employees_for_jobs(job_ids):
        crew.setdefault(row.job_id, []).append(row)
    return crew
