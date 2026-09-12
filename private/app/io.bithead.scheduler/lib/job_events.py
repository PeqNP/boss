#
# Scheduler — who hears that a job was booked, cancelled, or moved.
#
# One set of people: the operators of the business, the crew when there is
# one, otherwise the in-schedule employees who can do that type. The calendar,
# the today list, and the banner all use it.
#

from typing import List, Sequence

from .. import db
from ..model import *
from .employee import _crew_for
from .exception import ValidationError
from .membership import is_operator_role
from .time import display_date, display_time


JOB_CHANGED_EVENT = "io.bithead.scheduler.job.changed"

_KINDS = {
    "booked": "booked —",
    "cancelled": "cancelled —",
    "moved": "moved to",
}


def _user_ids(rows: Sequence[db.EmployeeRow]) -> List[int]:
    """Account ids, once each, skipping anyone with no BOSS account."""
    seen = set()
    ids = []
    for row in rows:
        if row.user_id is None or row.user_id in seen:
            continue
        seen.add(row.user_id)
        ids.append(row.user_id)
    return ids


def jobs_visible_to_employee(
    employee_id: int,
    rows: Sequence
) -> List:
    """The jobs in `rows` this employee may see.

    Assigned to them, or unassigned of a type they can perform while they are
    in the schedule. A colleague's assigned job is not theirs. Each row names
    `id` and `job_type_id`.
    """
    employee = db.get_employee_anywhere(employee_id)
    if employee is None:
        return []
    crew = _crew_for([r.id for r in rows])
    allowed = {j.id for j in db.get_job_types_for_employee(employee_id)}
    in_schedule = bool(employee.include_in_schedule)
    visible = []
    for row in rows:
        assigned = [c.employee_id for c in crew.get(row.id, [])]
        if employee_id in assigned:
            visible.append(row)
        elif not assigned and in_schedule and row.job_type_id in allowed:
            visible.append(row)
    return visible


def employee_sees_job(employee_id: int, job_id: int) -> bool:
    """Whether this employee may open this job."""
    job = db.get_scheduled_job(job_id)
    if job is None:
        return False
    return bool(jobs_visible_to_employee(employee_id, [job]))


def staff_who_see_job(job_id: int) -> List[int]:
    """BOSS account ids who see this job, and who get the banner for it."""
    job = db.get_scheduled_job(job_id)
    if job is None:
        raise ValidationError("That appointment no longer exists.")
    staff = db.get_employees(job.business_id)
    operators = [e for e in staff if is_operator_role(e.role)]
    crew_ids = set(db.get_job_employee_ids(job_id))
    if crew_ids:
        assigned = [e for e in staff if e.id in crew_ids]
        return _user_ids(operators + assigned)
    eligible = db.get_employees_for_job_type(job.job_type_id)
    return _user_ids(operators + eligible)


def job_change_notice(job_id: int, kind: str) -> JobChangeNotice:
    """Recipients, event payload, and banner copy for a job change."""
    phrase = _KINDS.get(kind)
    if phrase is None:
        raise ValidationError("That is not a change the staff are told about.")
    job = db.get_scheduled_job(job_id)
    if job is None:
        raise ValidationError("That appointment no longer exists.")
    job_type = db.get_job_type(job.business_id, job.job_type_id)
    name = job_type.name if job_type is not None else "Appointment"
    when = f"{display_date(job.scheduled_date)} {display_time(job.scheduled_time)}"
    return JobChangeNotice(
        eventName=JOB_CHANGED_EVENT,
        userIds=staff_who_see_job(job_id),
        payload={
            "jobId": str(job.id),
            "kind": kind,
            "date": job.scheduled_date,
            "businessId": str(job.business_id),
        },
        title=name,
        body=f"{name} {phrase} {when}",
        kind=kind,
    )
