#
# Scheduler — the operator's view of the work, and the work that repeats.
#
# A month, a week, a day: the same appointments read at three widths. The
# routes narrow by who is asking — an operator gets the business, an employee
# gets the jobs they are on — so one calendar serves both.
#
# A recurrence is an arrangement rather than a booking. Nothing is held until
# it is materialised, which happens on a schedule as the horizon moves.
#

import json

from datetime import date as _date, datetime, timedelta
from typing import Dict, List, Optional

from .. import db
from ..model import *
from .availability import (_duration_minutes, _next_day, employees_free_at,
                           get_available_slots)
from .code import _job_code
from .job_type import get_job_type
from .transform import _business
from .employee import _crew_for
from .exception import ValidationError
from .kiosk import _month_bounds
from .time import _end_time, day_of_week, display_date, display_time, to_minutes


def _display_week_day(date: str) -> str:
    """`Sun 7/12`, as a week column heads itself."""
    when = datetime.strptime(date, "%Y-%m-%d")
    return f"{DAY_ABBREVIATIONS[day_of_week(date)]} {when.month}/{when.day}"


DAY_ABBREVIATIONS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def _week_start(date: str) -> str:
    """The Sunday of the week this date falls in."""
    when = datetime.strptime(date, "%Y-%m-%d")
    return (when - timedelta(days=day_of_week(date))).strftime("%Y-%m-%d")


def _initials(row: "db.EmployeeRow") -> str:
    return f"{row.first_name[:1]}{row.last_name[:1]}".upper()


def get_schedule_month(
    business_id: int,
    year: int,
    month: int,
    employee_id: Optional[int] = None
) -> ScheduleMonth:
    """How busy each day of a month is.

    Only the days with work on them. The screen draws a grid of every day and
    fills in what it is given, so an empty day is an absence rather than a zero.
    """
    start, end = _month_bounds(year, month)
    counts: Dict[str, int] = {}
    for row in _for_employee(
        db.get_scheduled_jobs(business_id, start, end),
        employee_id
    ):
        counts[row.scheduled_date] = counts.get(row.scheduled_date, 0) + 1
    return ScheduleMonth(
        year=year,
        month=month,
        # In date order because the rows arrive in date order and a dict keeps
        # what it was given.
        days=[Day(date=date, jobCount=count) for date, count in counts.items()]
    )


def get_schedule_week(
    business_id: int,
    date: str,
    employee_id: Optional[int] = None
) -> ScheduleWeek:
    """Seven days from the Sunday, whatever day was asked about.

    Always seven, empty ones included: the week is a row of columns, and a day
    left out would close the gap and mislabel every column after it.
    """
    start = _week_start(date)
    end = (datetime.strptime(
        start,
        "%Y-%m-%d"
    ) + timedelta(days=6)).strftime("%Y-%m-%d")

    rows = _for_employee(
        db.get_scheduled_jobs(business_id, start, end),
        employee_id
    )
    crew = _crew_for([r.id for r in rows])

    days = []
    for offset in range(7):
        on = (datetime.strptime(start, "%Y-%m-%d")
              + timedelta(days=offset)).strftime("%Y-%m-%d")
        days.append(ScheduleWeekDay(
            date=on,
            displayDate=_display_week_day(on),
            jobs=[
                ScheduleWeekJob(
                    id=r.id,
                    jobCode=r.job_code,
                    jobType=r.job_type_name,
                    startTime=r.scheduled_time,
                    endTime=_end_time(r.scheduled_time, r.duration_minutes),
                    employeeInitials=[_initials(e) for e in crew.get(r.id, [])],
                    status=r.status
                )
                for r in rows if r.scheduled_date == on
            ],
        ))
    return ScheduleWeek(weekStart=start, days=days)


def _for_employee(rows: list, employee_id: Optional[int]) -> list:
    """The jobs this employee is on.

    `None` leaves the rows as they are, which is what an operator sees. An
    employee's calendar reads the same routes as the operator's, so the caller
    is what narrows them.
    """
    if employee_id is None:
        return rows
    crew = _crew_for([r.id for r in rows])
    return [r for r in rows
            if any(c.employee_id == employee_id
                   for c in crew.get(r.id, []))]


def _lay_out(jobs: List[tuple]) -> Dict[int, tuple]:
    """Which column each appointment takes, and how many share its group.

    Appointments running at the same time are drawn side by side, so each needs
    a column and the width to divide. A group is every appointment reachable
    from another by overlapping — three appointments in a chain all take a
    third of the width, which keeps the grid honest as one is added.

    Takes `(id, start, end)` in start order; returns `id -> (column, total)`.
    """
    layout: Dict[int, tuple] = {}

    def settle(members):
        """Place one group, then give every member the group's width."""
        columns: List[int] = []          # when each column is next free
        placed = []
        for job_id, start, end in members:
            column = next(
                (i for i, free in enumerate(columns) if free <= start),
                len(columns)
            )
            if column == len(columns):
                columns.append(end)
            else:
                columns[column] = end
            placed.append((job_id, column))
        for job_id, column in placed:
            layout[job_id] = (column, len(columns))

    group: List[tuple] = []
    group_ends = 0
    for job_id, start, end in jobs:
        # A gap with nothing running across it closes the group: what follows
        # overlaps none of it, and divides the width afresh.
        if group and start >= group_ends:
            settle(group)
            group, group_ends = [], 0
        group.append((job_id, start, end))
        group_ends = max(group_ends, end)
    if group:
        settle(group)
    return layout


def get_schedule_day(
    business_id: int,
    date: str,
    employee_id: Optional[int] = None
) -> ScheduleDay:
    """One day, laid out so two appointments at once can both be seen."""
    rows = _for_employee(
        db.get_scheduled_jobs(business_id, date, date),
        employee_id
    )
    crew = _crew_for([r.id for r in rows])
    layout = _lay_out([
        (r.id, to_minutes(r.scheduled_time),
         to_minutes(r.scheduled_time) + r.duration_minutes)
        for r in rows
    ])

    return ScheduleDay(
        date=date,
        jobs=[
            ScheduleDayJob(
                id=r.id,
                jobCode=r.job_code,
                jobType=r.job_type_name,
                customerName=" ".join(
                part for part in (r.first_name, r.last_name) if part),
                startTime=r.scheduled_time,
                endTime=_end_time(r.scheduled_time, r.duration_minutes),
                startMinuteOffset=to_minutes(r.scheduled_time),
                durationMinutes=r.duration_minutes,
                employees=[AppointmentEmployee(
                    firstName=e.first_name,
                    lastInitial=e.last_name[:1]
                )
                for e in crew.get(r.id, [])],
                overlapColumn=layout[r.id][0],
                overlapTotal=layout[r.id][1],
                status=r.status,
                paymentStatus=r.payment_status
            )
            for r in rows
        ],
    )


def get_unassigned_jobs(business_id: int) -> List[JobsUnassignedJob]:
    """Live appointments with nobody on them, for Needs Attention."""
    return [
        JobsUnassignedJob(
            id=r.id,
            jobCode=r.job_code,
            jobType=r.job_type_name,
            customerName=" ".join(
            part for part in (r.first_name, r.last_name) if part),
            scheduledDate=r.scheduled_date,
            scheduledTime=r.scheduled_time,
            displayDate=display_date(r.scheduled_date),
            displayTime=display_time(r.scheduled_time),
            isRecurring=bool(r.is_recurring)
        )
        for r in db.get_unassigned_jobs(business_id)
    ]


def assign_jobs(
    business_id: int,
    job_ids: List[int],
    now: Optional[datetime] = None
) -> JobsAssign:
    """Put somebody free on each appointment chosen.

    Asked of the same availability the kiosk asks, so an appointment is never
    given to somebody the booking screen would have refused. An appointment
    nobody is free for is counted rather than forced onto whoever is nearest —
    the operator is being told there is a conflict to resolve.

    An appointment that already has a crew is left alone. The screen lists only
    unassigned work, so one arriving here is a list that has gone stale.
    """
    assigned = unassigned = 0
    for job_id in job_ids:
        row = db.get_scheduled_job(job_id)
        if row is None or row.business_id != business_id:
            continue
        if db.get_employees_on_job(job_id):
            continue

        free = employees_free_at(
            business_id,
            row.job_type_id,
            row.job_type_size_id,
            row.scheduled_date,
            row.scheduled_time,
            now=now
        )
        if not free:
            unassigned += 1
            continue

        job_type = get_job_type(business_id, row.job_type_id)
        wanted = job_type.minEmployees if job_type else 1
        for employee_id in free[:wanted]:
            db.assign_employee_to_job(job_id, employee_id)
        assigned += 1

    return JobsAssign(assigned=assigned, unassigned=unassigned)


def get_dashboard(
    business_id: int,
    now: Optional[datetime] = None
) -> Optional[Dashboard]:
    """The figures the operator lands on."""
    business_row = db.get_business(business_id)
    if business_row is None:
        return None
    business = _business(business_row)
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")

    week_start = _week_start(today)
    week_end = (datetime.strptime(week_start, "%Y-%m-%d")
                + timedelta(days=6)).strftime("%Y-%m-%d")
    month_start, month_end = _month_bounds(now.year, now.month)

    waiting = db.get_unassigned_jobs(business_id)

    # An appointment nobody is free for is a conflict the operator has to
    # resolve, and it is counted apart from the rest. Asked only under
    # `reserved`: `unlimited` allocates nobody, so every appointment would
    # count and the figure would say nothing.
    conflicts = 0
    if business.slotMode == "reserved":
        conflicts = len([
            r for r in waiting
            if not employees_free_at(
                business_id,
                r.job_type_id,
                r.job_type_size_id,
                r.scheduled_date,
                r.scheduled_time,
                now=now
            )
        ])

    return Dashboard(
        # The kiosk button opens against a business, and the screen already
        # asks this route for everything else it draws.
        businessId=business_id,
        isActive=bool(business_row.is_active),
        # `unlimited` allocates nobody, so the screen hides the panel rather
        # than showing a count that can only ever be the whole list.
        slotMode=business.slotMode,
        jobsToday=db.count_jobs_between(business_id, today, today),
        jobsThisWeek=db.count_jobs_between(business_id, week_start, week_end),
        revenueThisMonth=db.get_revenue_between(
            business_id,
            month_start,
            month_end
        ),
        upcomingJobs=db.count_jobs_between(business_id, today, LAST_DATE),
        unassignedJobs=len(waiting),
        unassignedConflicts=conflicts,
    )


# Far enough out that "upcoming" means everything ahead. A date rather than a
# window: an appointment booked two years from now is still upcoming.
LAST_DATE = "9999-12-31"


def _recurrence_dates(
    recurrence: Recurrence,
    start: str,
    last: str
) -> List[str]:
    """The dates this arrangement falls on, inside a window."""
    dates, date = [], start
    while date <= last:
        weekday = day_of_week(date)
        if recurrence.intervalType == "daily":
            dates.append(date)
        elif weekday in recurrence.daysOfWeek:
            dates.append(date)
        date = _next_day(date)
    return dates


def materialize_recurrences(now: Optional[datetime] = None) -> int:
    """Make the appointments each arrangement is due, inside its cutoff window.

    Runs on a schedule. Returns how many were created, which is nothing on a
    run where the horizon has not moved.

    An appointment nobody is free for is still made, and left unassigned: a
    customer with a standing arrangement expects their slot, and an operator
    would rather see it in Needs Attention than find out it never existed.
    """
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    created = 0

    for row in db.get_active_recurrences():
        recurrence = _recurrence(row)
        business_row = db.get_business(recurrence.businessId)
        if business_row is None:
            continue
        business = _business(business_row)
        last = (now + timedelta(days=business.cutoffDays)).strftime("%Y-%m-%d")

        duration = _duration_minutes(recurrence.jobTypeSizeId)
        for date in _recurrence_dates(recurrence, today, last):
            if db.recurrence_instance_exists(recurrence.id, date):
                continue
            job_id = db.insert_recurring_job(
                _job_code(),
                business.id,
                recurrence.jobTypeId,
                recurrence.jobTypeSizeId,
                date,
                recurrence.preferredTime,
                duration,
                recurrence.id
            )
            for employee_id in _free_for(
                business,
                recurrence,
                date,
                duration,
                now
            ):
                db.assign_employee_to_job(job_id, employee_id)
            created += 1
    return created


def _free_for(
    business: Business,
    recurrence: Recurrence,
    date: str,
    duration: int,
    now: datetime
) -> List[int]:
    """Who could take this instance, or nobody.

    Asked of the same availability the kiosk asks, so a recurrence cannot be
    assigned someone the booking screen would refuse.
    """
    slots = get_available_slots(
        business.id,
        recurrence.jobTypeId,
        recurrence.jobTypeSizeId,
        limit=100,
        from_date=date,
        now=now
    )
    for slot in slots:
        if slot.date == date and slot.time == recurrence.preferredTime:
            return slot.employeeIds
    return []


def _recurrence(row: db.RecurrenceRow) -> Recurrence:
    return Recurrence(
        id=row.id,
        businessId=row.business_id,
        jobTypeId=row.job_type_id,
        jobTypeSizeId=row.job_type_size_id,
        intervalType=row.interval_type,
        daysOfWeek=json.loads(row.days_of_week_json) if row.days_of_week_json else [],
        preferredTime=row.preferred_time,
        isActive=bool(row.is_active)
    )


# What `materialize_recurrences` knows how to work out dates for. The column
# allows more — `biweekly | monthly | custom` — and each is refused on creation
# until it is built, because a recurrence that saves and then quietly books
# nothing is found out by the customer who did not get their appointment.
#
# `biweekly` needs an anchor the schema does not have: with only a window to
# work from, which weeks are "on" depends on when the job happens to run, so
# the same arrangement drifts between runs.
SUPPORTED_INTERVALS = ("daily", "weekly")


def create_recurrence(
    business_id: int,
    job_type_id: int,
    size_id: Optional[int],
    interval_type: str,
    preferred_time: str,
    days_of_week: Optional[List[int]] = None
) -> Recurrence:
    """Set up repeating work. Nothing is booked until it is materialised."""
    if interval_type not in SUPPORTED_INTERVALS:
        raise ValidationError(
            f"Repeating {interval_type} is not available yet."
            f" Please choose {' or '.join(SUPPORTED_INTERVALS)}."
        )
    if interval_type == "weekly" and not days_of_week:
        raise ValidationError("Please choose which days of the week to repeat on.")
    days = json.dumps(days_of_week) if days_of_week else None
    return _recurrence(db.get_recurrence(
        db.insert_recurrence(
            business_id,
            job_type_id,
            size_id,
            interval_type,
            days,
            preferred_time
        )
    ))


def cancel_recurrence(recurrence_id: int) -> Optional[Recurrence]:
    """Stop making new appointments from this arrangement.

    The ones already made stay: customers are expecting them, and an operator
    who wanted them gone cancels them.
    """
    db.set_recurrence_active(recurrence_id, 0)
    row = db.get_recurrence(recurrence_id)
    return _recurrence(row) if row is not None else None


def get_recurring_jobs(recurrence_id: int) -> List[RecurringJob]:
    return [
        RecurringJob(
            id=r.id,
            jobCode=r.job_code,
            scheduledDate=r.scheduled_date,
            scheduledTime=r.scheduled_time,
            status=r.status,
            employeeIds=db.get_job_employee_ids(r.id)
        )
        for r in db.get_jobs_for_recurrence(recurrence_id)
    ]
