#
# Scheduler — Stub API
#
# All endpoints return hard-coded fixture data.
# Replace each stub body with real logic in Stage 4.
#

from datetime import datetime, timedelta, timezone

from functools import wraps

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from lib.model import User
from enum import Enum

from lib.server import (get_user, grant_license, grant_role, require_acl,
                        require_admin, require_user, revoke_role)

from . import lib
from .db import start_database
from .model import *

class Role(str, Enum):
    """Who a caller is to the business named in the path.

    The value is the label BOSS shows in Settings. `employees.role` holds the
    lower-case form, which is what `Me.role` carries to the client.
    """
    OPERATOR = "Operator"
    EMPLOYEE = "Employee"


router = APIRouter(prefix="/api/io.bithead.scheduler")

# How long a kiosk holds a slot while the customer fills in the rest. The real
# value is per-install, from `system_config.schedule_timeout_minutes` — which is
# what `GET /superadmin/timeout` reads and writes.
SESSION_TIMEOUT_MINUTES = 10


def _expires_in(minutes):
    """When a lock taken now would expire, as the client reads it.

    Computed rather than written down. A fixed timestamp is in the past by the
    time anyone runs this, and the kiosk answers a lock that has already
    expired by asking the customer whether they are still there — every time,
    immediately.
    """
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return expires.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# MARK: Appointment lookup — mock credentials
# ---------------------------------------------------------------------------
#
# Stage 1 has no database, so the two lookup flows run off two fixed values.
# `AAAAAA` is the job code that exists, `111111` is the verification code that
# works, and anything else takes the error path. Nothing is counted and nothing
# is remembered between requests — the thresholds and the penalties they lead
# to are Stage 4's, and the plan holds the rules.

MOCK_JOB_CODE = "AAAAAA"
MOCK_VERIFICATION_CODE = "111111"
MOCK_BUSINESS_PHONE = "(555) 867-5309"


# ---------------------------------------------------------------------------
# MARK: Shared models
# ---------------------------------------------------------------------------

class MeResponse(BaseModel):
    role: str           # operator | employee | customer | superadmin | none
    businessId: Optional[int] = None
    employeeId: Optional[int] = None



# ---------------------------------------------------------------------------
# MARK: System / role
# ---------------------------------------------------------------------------

# What each refusal means over HTTP. Rules raise rather than return, so a
# caller cannot ignore them, and they know nothing about status codes — this is
# the single place that translation happens.
#
# 404 is the appointment that is not there. 409 is a request understood and
# refused because of the state of something else. 410 is a thing that existed
# and has gone. 429 is the caller being asked to stop.
REFUSALS = [
    (lib.JobNotFound, 404),
    (lib.Blocked, 409),
    (lib.SessionExpired, 410),
    (lib.CodeExpired, 410),
    (lib.CodeSpent, 410),
    (lib.CallerBlocked, 429),
    (lib.OTPMaxAttemptsExceeded, 429),
    (lib.AppointmentLocked, 423),
    (lib.AppointmentInactive, 409),
    (lib.NoContactChannel, 409),
    (lib.OTPInvalid, 400),
    (lib.CodeInvalid, 400),
    (lib.InvalidDateRange, 400),
    (lib.ValidationError, 400),
]


def handled(func):
    """Turn a rule's refusal into the status the client expects."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except tuple(kind for kind, _ in REFUSALS) as refused:
            for kind, status in REFUSALS:
                if isinstance(refused, kind):
                    raise HTTPException(status_code=status,
                                        detail={"reason": str(refused)})
            raise
    return wrapper


@router.get("/me", response_model=Me)
@require_user()
@handled
async def get_me(boss_user: User, request: Request):
    # Which screen the app opens on. Somebody who runs no business is a
    # customer — the app has customers who never run anything.
    return lib.whoami(boss_user.id)


@router.post("/reconcile", response_model=Reconciled)
@require_user()
@handled
async def reconcile(boss_user: User, request: Request):
    """Claim every customer record belonging to whoever is signed in.

    Called by the app when it starts and again on `userDidSignIn`, rather than
    pushed from wherever the account was created. The app already knows who is
    signed in and does not have to be told, so there is no callback to deliver,
    authenticate, or retry — and reconciliation happens exactly when somebody
    is there to see the result.

    Safe to call as often as it likes: it claims what is unclaimed, so a second
    call finds nothing and changes nothing.
    """
    if not boss_user.verified:
        # Records are matched on the address, and an unverified one has not
        # been shown to belong to whoever typed it.
        return Reconciled(claimed=0)
    return Reconciled(claimed=lib.reconcile_boss_user(boss_user.id,
                                                      boss_user.email))


# ---------------------------------------------------------------------------
# MARK: Kiosk
# ---------------------------------------------------------------------------

@router.get("/kiosk/{business_id}", response_model=Kiosk)
@handled
async def get_kiosk_config(business_id: int, request: Request):
    # `configured` is the answer, decided on the server. The tasks behind it go
    # to `/admin/setup`, which the operator opens — a customer is shown a door
    # that is open or closed.
    kiosk = lib.get_kiosk(business_id)
    if kiosk is None:
        raise HTTPException(status_code=404, detail="That business no longer exists.")
    return kiosk


@router.get("/kiosk/{business_id}/employees", response_model=KioskEmployees)
@handled
async def get_kiosk_employees(business_id: int, request: Request):
    return KioskEmployees(employees=lib.get_kiosk_employees(business_id))


@router.get("/kiosk/{business_id}/job-types", response_model=KioskJobTypes)
@handled
async def get_kiosk_job_types(business_id: int, request: Request):
    return KioskJobTypes(jobTypes=lib.get_kiosk_job_types(business_id))


@router.get("/kiosk/{business_id}/calendar", response_model=KioskCalendar)
@handled
async def get_kiosk_calendar(
    business_id: int, request: Request,
    jobTypeId: int = 0, sizeId: int = 0, employeeId: Optional[int] = None,
    month: int = 1, year: int = 2026
):
    return lib.get_kiosk_calendar(business_id, jobTypeId, sizeId or None,
                                  employeeId, year=year, month=month)


@router.get("/kiosk/{business_id}/day-slots", response_model=KioskDaySlots)
@handled
async def get_kiosk_day_slots(
    business_id: int, request: Request,
    jobTypeId: int = 0, sizeId: int = 0, employeeId: Optional[int] = None,
    date: str = ""
):
    return lib.get_kiosk_day_slots(business_id, jobTypeId, sizeId or None,
                                   employeeId, date=date)


@router.get("/kiosk/{business_id}/slots", response_model=KioskSlots)
@handled
async def get_kiosk_slots(
    business_id: int, request: Request,
    jobTypeId: int = 0, sizeId: int = 0, employeeId: Optional[int] = None, limit: int = 5
):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}/slots
    #
    # `displayDate` is the row's label, and "ASAP" is one of the things it can
    # say. Use it for a slot falling inside the next increment from now — that
    # is what guarantees the time is today and minutes away. A slot that is
    # merely the first one available is not necessarily soon: a shop closed
    # when someone walks up has a first slot tomorrow, and labelling that ASAP
    # would leave the customer with a time and no day.
    #
    # At most one slot per response, and only under `slot_mode = 'unlimited'`,
    # where the times run from now rather than from opening. The client renders
    # whatever it is given and asks nothing.
    #
    #   {"date": "2026-08-22", "time": "10:10", "displayDate": "ASAP", …}
    # `KioskSlot` is `Slot` without `employeeIds`, and the difference is the
    # point: telling a customer who is free at every time they did not pick is
    # not theirs to know. Nesting narrows it.
    return KioskSlots(slots=lib.get_available_slots(
        business_id, jobTypeId, sizeId or None, employeeId, limit=limit))


@router.post("/kiosk/{business_id}/session", response_model=KioskSession)
@handled
async def create_kiosk_session(business_id: int, body: KioskSessionBody,
                               request: Request):
    # The employees are worked out here rather than taken from the client: the
    # customer chose a time, not a person, and who can do the work at that time
    # is the same question availability already answered.
    employee_ids = lib.employees_free_at(business_id, body.jobTypeId, body.sizeId,
                                         body.scheduledDate, body.scheduledTime,
                                         body.employeeId)
    session = lib.create_job_session(business_id, body.jobTypeId, body.sizeId,
                                     body.scheduledDate, body.scheduledTime,
                                     employee_ids)
    return KioskSession(sessionId=session.sessionToken, jobId=session.jobId,
                        expiresAt=session.expiresAt,
                        timeoutMinutes=lib.get_schedule_timeout_minutes())


@router.put("/kiosk/session/{session_id}/extend", response_model=KioskSessionExtend)
@handled
async def extend_kiosk_session(session_id: str, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/kiosk/session/{sessionId}/extend
    #
    # Extending shifts the expiry a full timeout out from now, rather than
    # adding to whatever was left: the customer asked for more time at this
    # moment, not at the moment the lock was taken.
    return KioskSessionExtend(expiresAt=lib.extend_session(session_id).expiresAt)


@router.post("/kiosk/session/{session_id}/otp/send", response_model=KioskSessionOtpSend)
@handled
async def send_otp(session_id: str, body: OtpSendBody, request: Request):
    lib.send_otp(session_id, lib.contact_value_for(session_id, body.fieldType))
    return KioskSessionOtpSend(sent=True)


@router.post("/kiosk/session/{session_id}/otp/verify", response_model=OtpResult)
@handled
async def verify_otp(session_id: str, body: OtpVerifyBody, request: Request):
    return lib.verify_otp(session_id, body.code)


@router.post("/kiosk/session/{session_id}/confirm", response_model=KioskSessionConfirm)
@handled
async def confirm_kiosk_session(session_id: str, body: KioskConfirmBody,
                                request: Request):
    # TODO: POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/confirm
    #
    # `confirmationSentTo` reports what actually went out, masked. A channel is
    # used only when the business enabled it *and* the customer gave that
    # contact field, so the client cannot work this out from the config — a
    # business that sends email tells a phone-only customer nothing.
    # Who is booking, when BOSS knows. It decides which customer record the
    # booking attaches to — an account is certain where a typed email is a
    # guess — and changes nothing else about the booking.
    user = await _signed_in_user(request)
    session = lib.confirm_session(
        session_id,
        contact={c.fieldId: c.value for c in body.contactData},
        attributes={a.fieldId: a.value for a in body.attributeData},
        user_id=user.id if user else None
    )
    # The domain answer is a list of channels; the screen reads an object with
    # one key per channel, so the shaping happens here.
    sent = {c.channel: c.sentTo for c in session.confirmationSentTo}
    return KioskSessionConfirm(
        jobId=session.jobId, jobCode=session.jobCode, stripePaymentUrl=None,
        confirmationSentTo=ConfirmationSentTo(sms=sent.get("sms"),
                                              email=sent.get("email"))
    )


@router.get("/operator/me", response_model=OperatorMe)
@handled
async def get_operator_me(request: Request, businessId: Optional[int] = None):
    # `isOperator` decides whether the kiosk shows its close button, and it is
    # true for whoever runs *this* business. Owning some other one is not
    # owning this one: the kiosk hides the menu bar and the dock, so anyone
    # given this button can walk out of the kiosk and into BOSS.
    user = await _signed_in_user(request)
    return OperatorMe(
        isOperator=bool(user and businessId
                        and lib.is_operator_of(businessId, user.id)),
        businessId=businessId or 0,
    )


# ---------------------------------------------------------------------------
# MARK: Appointment
# ---------------------------------------------------------------------------

@router.post("/appointment/lookup", response_model=Delivery)
@handled
async def lookup_appointment(body: LookupBody, request: Request):
    # TODO: POST /api/io.bithead.scheduler/appointment/lookup
    #
    # Sends a six-digit code to the phone the customer gave, or their email if
    # they gave no phone; the phone when they gave both. Single use, expiring
    # 30 minutes out, stored hashed in `appointment_access_codes`.
    #
    # 404 for an unknown job code, and the destination comes back masked: a job
    # code is six characters, and whoever typed it has proven nothing yet.
    #
    # A job that is already locked is refused here, before any code is sent.
    #
    # Throttled on `caller_of(request)`: three unknown codes inside a minute
    # blocks that caller for 24 hours, and the block is checked before the job
    # code is looked up, so a valid code is refused too. Call as
    # `lib.request_appointment_access(job_code, caller=caller_of(request))`.
    #
    # Three unknown codes inside a minute blocks the caller for 24 hours: 429,
    # for every code they try rather than the ones they tried. Nothing is
    # locked and nobody is notified — no appointment was identified, so there
    # is no customer to tell.
    return lib.request_appointment_access(body.jobCode.strip().upper(),
                                         caller=caller_of(request))


@router.post("/appointment/lookup/verify", response_model=AppointmentLookupVerify)
@handled
async def verify_appointment_lookup(body: LookupVerifyBody, request: Request):
    # TODO: POST /api/io.bithead.scheduler/appointment/lookup/verify
    #
    # Spends the code on success. An expired or already-used code is an error
    # rather than a `verified: false` — there is nothing left to retry, and the
    # client sends the customer back to the job code.
    #
    # The sixth wrong code inside a minute sets `scheduled_jobs.locked_date` and
    # comes back `locked: true`. That closes the customer's door for good; the
    # operator still changes the appointment from the admin screens.
    # A wrong code is an answer rather than an error: the customer stays on the
    # step and tries again. Everything else — spent, expired, locked — is
    # raised, because there is nothing left to retry.
    job_code = body.jobCode.strip().upper()
    try:
        appointment = lib.verify_appointment_access(job_code, body.code.strip())
    except lib.CodeInvalid:
        peek = lib.get_appointment_by_code(job_code)
        return AppointmentLookupVerify(
            verified=False,
            businessPhone=peek.businessPhone if peek else None
        )
    return AppointmentLookupVerify(
        verified=True, appointmentId=appointment.id, locked=appointment.locked,
        businessPhone=appointment.businessPhone
    )


@router.get("/appointment/{appointment_id}", response_model=AppointmentDetail)
@handled
async def get_appointment_detail(appointment_id: int, request: Request):
    a = lib.get_appointment(appointment_id)
    if a is None:
        raise HTTPException(status_code=404,
                            detail={"reason": "That appointment no longer exists."})
    # The domain model is flat; this screen reads nested objects, so the
    # shaping happens here rather than bending the model to one caller.
    return AppointmentDetail(
        id=a.id, jobCode=a.jobCode,
        jobType=EmployeeJobType(id=a.jobTypeId, name=a.jobTypeName),
        size=None if a.sizeId is None else Size(
            id=a.sizeId, name=a.sizeName, durationMinutes=a.durationMinutes,
            cost=a.cost
        ),
        scheduledDate=a.scheduledDate, scheduledTime=a.scheduledTime,
        displayDate=a.displayDate, displayTime=a.displayTime,
        # The reschedule flow asks this business for its open slots, so the id
        # has to be here — reading it off a response that never carried one is
        # what made "Change Date/Time" open an empty page.
        businessId=a.businessId,
        business=AppointmentBusiness(name=a.businessName, phone=a.businessPhone),
        employees=[AppointmentEmployee(firstName=n.split(" ")[0],
                                       lastInitial=n.split(" ")[-1].rstrip("."))
                   for n in a.employees],
        status=a.status, locked=a.locked, changesClosed=a.changesClosed
    )


@router.put("/appointment/{appointment_id}/reschedule", response_model=Success)
@handled
async def reschedule_appointment(appointment_id: int, body: RescheduleBody,
                                 request: Request):
    lib.reschedule_appointment(appointment_id, body.scheduledDate,
                               body.scheduledTime)
    return Success(success=True)


@router.delete("/appointment/{appointment_id}", response_model=Success)
@handled
async def cancel_appointment(appointment_id: int, request: Request):
    lib.cancel_appointment(appointment_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Customer portal
# ---------------------------------------------------------------------------

@router.get("/my/appointments", response_model=CustomerAppointments)
@require_user()
@handled
async def get_customer_appointments(boss_user: User, request: Request):
    # Across every business. A customer record belongs to one business, and
    # somebody who has used two has two records — gathered by the account.
    return lib.get_customer_appointments(boss_user.id)


# ---------------------------------------------------------------------------
# MARK: Operator: Dashboard
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/setup", response_model=SetupResponse)
@require_acl("setup.r", roles=[Role.OPERATOR])
@handled
async def get_setup(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # The one place that decides whether a business can take a booking.
    # Nothing is stored: it is computed each time it is asked, so a rule added
    # here takes effect everywhere at once and no column can fall out of step
    # with the thing it describes.
    #
    # Two callers, one answer: the app on launch, to decide where to put the
    # operator, and `SetupAssistant`, which lists the tasks and opens what each
    # one names. `GET /kiosk/{businessId}` asks the same question and shows the
    # customer only the boolean.
    return lib.get_setup(business_id)


@router.get("/business/{business_id}/dashboard", response_model=Dashboard)
@require_acl("dashboard.r", roles=[Role.OPERATOR])
@handled
async def get_dashboard(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    board = lib.get_dashboard(business_id)
    if board is None:
        raise HTTPException(status_code=404, detail="That business no longer exists.")
    return board


# ---------------------------------------------------------------------------
# MARK: Operator: Schedule
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/schedule/month", response_model=ScheduleMonth)
@require_acl("schedule.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_schedule_month(business_id: int, boss_user: User, request: Request, year: int = 2026, month: int = 1):
    employee_id = _get_employee_id(business_id, boss_user)
    # Only the days with work on them. The screen draws the grid and fills in
    # what it is given, so an empty day is an absence rather than a zero.
    return lib.get_schedule_month(business_id, year, month, employee_id=employee_id)


@router.get("/business/{business_id}/schedule/week", response_model=ScheduleWeek)
@require_acl("schedule.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_schedule_week(business_id: int, boss_user: User, request: Request, date: str = ""):
    employee_id = _get_employee_id(business_id, boss_user)
    return lib.get_schedule_week(
        business_id,
        date or datetime.now().strftime("%Y-%m-%d"),
        employee_id=employee_id)


@router.get("/business/{business_id}/schedule/day", response_model=ScheduleDay)
@require_acl("schedule.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_schedule_day(business_id: int, boss_user: User, request: Request, date: str = ""):
    employee_id = _get_employee_id(business_id, boss_user)
    return lib.get_schedule_day(
        business_id,
        date or datetime.now().strftime("%Y-%m-%d"),
        employee_id=employee_id)


@router.get("/business/{business_id}/jobs/unassigned", response_model=JobsUnassigned)
@require_acl("job.r", roles=[Role.OPERATOR])
@handled
async def get_unassigned_jobs(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return JobsUnassigned(jobs=lib.get_unassigned_jobs(business_id))


@router.post("/business/{business_id}/jobs/assign", response_model=JobsAssign)
@require_acl("job.w", roles=[Role.OPERATOR])
@handled
async def assign_jobs(business_id: int, boss_user: User, request: Request, body: AssignBody):
    _working_for(business_id, boss_user)
    return lib.assign_jobs(business_id, body.jobIds)


# ---------------------------------------------------------------------------
# MARK: Operator: Jobs
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/job/{job_id}", response_model=JobDetail)
@require_acl("job.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_admin_job(business_id: int, job_id: int, boss_user: User, request: Request):
    employee_id = _get_employee_id(business_id, boss_user)
    job = lib.get_admin_job(business_id, job_id, employee_id=employee_id)
    if job is None:
        raise HTTPException(status_code=404,
                            detail="That appointment no longer exists.")
    return job


@router.put("/business/{business_id}/job/{job_id}", response_model=Success)
async def update_admin_job(business_id: int, job_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # TODO: PUT /api/io.bithead.scheduler/job/{jobId}
    return Success(success=True)


@router.post("/business/{business_id}/job/{job_id}/complete", response_model=Success)
@require_acl("job.w", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def complete_job(business_id: int, job_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.complete_job(job_id)
    return Success(success=True)


@router.post("/business/{business_id}/job/{job_id}/payment", response_model=PaymentResult)
@require_acl("job.w", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def add_payment(business_id: int, job_id: int, boss_user: User, request: Request, body: PaymentBody):
    _working_for(business_id, boss_user)
    return lib.record_payment(job_id, body.amount, body.method,
                              collected_by_user_id=_operator_user(request),
                              note=body.note)


@router.get("/business/{business_id}/job/{job_id}/payment-link", response_model=JobPaymentLink)
@require_acl("job.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_payment_link(business_id: int, job_id: int, boss_user: User, request: Request):
    employee_id = _get_employee_id(business_id, boss_user)
    # Stripe is still a stub — see the Business Settings routes. The shape is
    # the contract `stripe_client.create_payment_link` will have to meet.
    job = lib.get_admin_job(business_id, job_id, employee_id=employee_id)
    if job is None:
        raise HTTPException(status_code=404,
                            detail="That appointment no longer exists.")
    return JobPaymentLink(
        jobId=job.id,
        amount=job.size.cost if job.size else 0.0,
        paymentLinkUrl="https://buy.stripe.com/test_stub_link",
        jobCode=job.jobCode,
    )


@router.get("/business/{business_id}/jobs", response_model=Jobs)
@require_acl("job.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def search_jobs(business_id: int, 
    boss_user: User, request: Request,
    status: Optional[str] = None,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    fromDate: Optional[str] = None,
    toDate: Optional[str] = None,
    jobTypeId: Optional[int] = None,
    employeeId: Optional[int] = None
):
    _working_for(business_id, boss_user)
    jobs = lib.search_jobs(business_id, from_date=fromDate,
                           to_date=toDate, status=status, job_type_id=jobTypeId,
                           name=name, phone=phone, employee_id=employeeId)
    return Jobs(jobs=jobs, total=len(jobs))


# ---------------------------------------------------------------------------
# MARK: Operator: Job Types
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/job-types", response_model=JobTypes)
@require_acl("job-type.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_job_types(business_id: int, boss_user: User, request: Request, term: Optional[str] = None):
    _working_for(business_id, boss_user)
    # TODO: GET /api/io.bithead.scheduler/job-types
    #
    # `term` is what a token menu is typing. The match belongs here rather than
    # in the client: the menu picks a few out of however many there are, and
    # only this side knows how many that is.
    return JobTypes(jobTypes=lib.get_job_types(business_id, term=term))


@router.get("/business/{business_id}/job-type/{job_type_id}", response_model=JobTypeDetail)
@require_acl("job-type.r", roles=[Role.OPERATOR])
@handled
async def get_job_type(business_id: int, job_type_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # `id` on a contact field identifies what this job type asks for;
    # `contactFieldTypeId` is the system-wide field it asks for. Two records.
    job_type = lib.get_job_type_detail(job_type_id)
    if job_type is None:
        raise HTTPException(status_code=404,
                            detail="That job type no longer exists.")
    return job_type


@router.post("/business/{business_id}/job-type", response_model=Created)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def create_job_type(business_id: int, boss_user: User, request: Request, body: JobTypeDraftBody):
    _working_for(business_id, boss_user)
    # The form posts here as it opens, so sizes, attributes, and contact fields
    # have a job type to belong to before anything is named. Until the form
    # saves over it the row is a draft — inactive, so it reaches no customer —
    # and leaving the window deletes it.
    job_type = lib.create_job_type(business_id, body.name)
    return Created(id=job_type.id)


@router.put("/business/{business_id}/job-type/{job_type_id}", response_model=Success)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def update_job_type(business_id: int, job_type_id: int, body: JobTypeBody, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.update_job_type(business_id, job_type_id, body.name, body.minEmployees,
                        body.isActive)
    return Success(success=True)


@router.delete("/business/{business_id}/job-type/{job_type_id}", response_model=Success)
@require_acl("job-type.d", roles=[Role.OPERATOR])
@handled
async def delete_job_type(business_id: int, job_type_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_job_type(business_id, job_type_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Sizes
# ---------------------------------------------------------------------------

@router.post("/business/{business_id}/job-type/{job_type_id}/size", response_model=JobTypeSizeDetail)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def create_job_type_size(business_id: int, job_type_id: int, boss_user: User, request: Request,
                               body: JobTypeSizeBody):
    _working_for(business_id, boss_user)
    return lib.add_job_type_size(job_type_id, body.name, body.durationMinutes,
                                 body.cost)


@router.put("/business/{business_id}/job-type-size/{size_id}", response_model=JobTypeSizeDetail)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def update_job_type_size(business_id: int, size_id: int, body: JobTypeSizeBody,
                               boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # `JobTypeSize` is this plus `jobTypeId`; the declared model narrows it.
    return lib.update_job_type_size(size_id, body.name, body.durationMinutes,
                                    body.cost)


@router.delete("/business/{business_id}/job-type-size/{size_id}", response_model=Success)
@require_acl("job-type.d", roles=[Role.OPERATOR])
@handled
async def delete_job_type_size(business_id: int, size_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_job_type_size(size_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Attributes
# ---------------------------------------------------------------------------

@router.post("/business/{business_id}/job-type/{job_type_id}/attribute", response_model=JobTypeAttribute)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def create_job_type_attribute(business_id: int, job_type_id: int, boss_user: User, request: Request,
                                    body: JobTypeAttributeBody):
    _working_for(business_id, boss_user)
    return lib.add_job_type_attribute(job_type_id, body.name, body.attributeType,
                                      body.options, body.isRequired)


@router.put("/business/{business_id}/job-type-attribute/{attribute_id}", response_model=JobTypeAttribute)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def update_job_type_attribute(business_id: int, attribute_id: int, boss_user: User, request: Request,
                                    body: JobTypeAttributeBody):
    _working_for(business_id, boss_user)
    return lib.update_job_type_attribute(attribute_id, body.name,
                                         body.attributeType, body.options,
                                         body.isRequired)


@router.delete("/business/{business_id}/job-type-attribute/{attribute_id}", response_model=Success)
@require_acl("job-type.d", roles=[Role.OPERATOR])
@handled
async def delete_job_type_attribute(business_id: int, attribute_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_job_type_attribute(attribute_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Contact Fields
# ---------------------------------------------------------------------------

@router.post("/business/{business_id}/job-type/{job_type_id}/contact-field",
             response_model=JobTypeContactField)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def create_job_type_contact_field(business_id: int, job_type_id: int, boss_user: User, request: Request,
                                        body: ContactFieldBody):
    _working_for(business_id, boss_user)
    return lib.add_job_type_contact_field(job_type_id, body.contactFieldTypeId,
                                          body.isRequired, body.requireOtp)


@router.put("/business/{business_id}/job-type-contact-field/{contact_field_id}",
            response_model=JobTypeContactField)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def update_job_type_contact_field(business_id: int, contact_field_id: int, boss_user: User, request: Request,
                                        body: ContactFieldBody):
    _working_for(business_id, boss_user)
    return lib.update_job_type_contact_field(contact_field_id,
                                             body.contactFieldTypeId,
                                             body.isRequired, body.requireOtp)


@router.delete("/business/{business_id}/job-type-contact-field/{contact_field_id}",
               response_model=Success)
@require_acl("job-type.d", roles=[Role.OPERATOR])
@handled
async def delete_job_type_contact_field(business_id: int, contact_field_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_job_type_contact_field(contact_field_id)
    return Success(success=True)


@router.post("/business/{business_id}/job-type/{job_type_id}/contact-fields/reorder",
             response_model=JobTypeContactFields)
@require_acl("job-type.w", roles=[Role.OPERATOR])
@handled
async def reorder_job_type_contact_fields(business_id: int, job_type_id: int, boss_user: User, request: Request,
                                          body: ReorderBody):
    _working_for(business_id, boss_user)
    # The whole order comes back, so the screen redraws from the server rather
    # than from the arrangement it just sent.
    return JobTypeContactFields(
        contactFields=lib.reorder_job_type_contact_fields(job_type_id, body.ids))


@router.get("/business/{business_id}/icons", response_model=Icons)
@require_acl("icon.r", roles=[Role.OPERATOR])
@handled
async def get_icons(business_id: int, boss_user: User, request: Request, type: str = "system"):
    _working_for(business_id, boss_user)
    return Icons(icons=lib.get_icons(business_id, type))


@router.post("/business/{business_id}/icons", response_model=Icon)
@require_acl("icon.w", roles=[Role.OPERATOR])
@handled
async def upload_icon(business_id: int, boss_user: User, request: Request, file: UploadFile = File(...)):
    _working_for(business_id, boss_user)
    # Written to the bundle's public directory, so nginx serves it and a job
    # type can draw it. Refused before it reaches the disk when it is not an
    # image — see `lib/media.py`.
    return lib.add_icon(business_id, file.filename,
                        await file.read())


@router.delete("/business/{business_id}/icons/{icon_id}", response_model=Success)
@require_acl("icon.d", roles=[Role.OPERATOR])
@handled
async def delete_icon(business_id: int, icon_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_icon(business_id, icon_id)
    return Success(success=True)


@router.get("/business/{business_id}/stripe/products")
async def get_stripe_products(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # TODO: GET /api/io.bithead.scheduler/stripe/products
    return {
        "products": [
            {"id": "prod_stub1", "name": "Lawn Mowing — Small", "defaultPrice": {"id": "price_stub1", "unitAmount": 5000, "currency": "usd"}},
            {"id": "prod_stub2", "name": "Lawn Mowing — Medium", "defaultPrice": {"id": "price_stub2", "unitAmount": 8000, "currency": "usd"}},
            {"id": "prod_stub3", "name": "Hedge Trimming", "defaultPrice": {"id": "price_stub3", "unitAmount": 6500, "currency": "usd"}}
        ]
    }


@router.get("/contact-fields", response_model=ContactFields)
@handled
async def get_contact_fields(request: Request):
    # The kinds of detail a job type may ask for. Seeded once per installation
    # and chosen from, so the kiosk can trust that a field marked `otpCapable`
    # can receive a code.
    return ContactFields(fields=lib.get_contact_field_types())


# ---------------------------------------------------------------------------
# MARK: Operator: Employees
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/employees", response_model=Employees)
@require_acl("employee.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_admin_employees(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return Employees(employees=lib.get_employees(business_id))


@router.get("/business/{business_id}/employee/{employee_id}", response_model=EmployeeDetail)
@require_acl("employee.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_employee(business_id: int, employee_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    e = lib.get_employee(business_id, employee_id)
    if e is None:
        raise HTTPException(status_code=404,
                            detail={"reason": "That employee no longer exists."})
    return EmployeeDetail(
        id=e.id, userId=None, firstName=e.firstName, lastName=e.lastName,
        includeInSchedule=e.includeInSchedule,
        canManageOwnSchedule=e.canManageOwnSchedule,
        scheduleTemplate=lib.get_working_days(employee_id),
        timeOff=lib.get_time_off(employee_id),
        jobTypes=[EmployeeJobType(id=j.id, name=j.name)
                  for j in lib.get_employee_job_types(employee_id)]
    )


@router.post("/business/{business_id}/employee", response_model=Employee)
@require_acl("employee.w", roles=[Role.OPERATOR])
@handled
async def admin_create_employee(business_id: int, boss_user: User, request: Request, body: EmployeeBody):
    _working_for(business_id, boss_user)
    # The form posts here as it opens, so working days and time off have
    # someone to belong to before anyone is named. Until the form saves over
    # it the row is a draft, and leaving the window deletes it.
    # The form opens without saying, so the default stands: a draft is in the
    # schedule unless the operator takes it out.
    return lib.create_employee(
        business_id, body.firstName, body.lastName,
        True if body.includeInSchedule is None else body.includeInSchedule)


@router.put("/business/{business_id}/employee/{employee_id}", response_model=Success)
@require_acl("employee.w", roles=[Role.OPERATOR])
@handled
async def update_employee(business_id: int, employee_id: int, body: EmployeeBody, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.update_employee(business_id, employee_id, body.firstName, body.lastName,
                        body.includeInSchedule, body.canManageOwnSchedule)
    # Sent as the whole list rather than as changes, so what is stored is what
    # was on screen.
    if body.jobTypeIds is not None:
        lib.set_employee_job_types(employee_id, body.jobTypeIds)
    return Success(success=True)


@router.delete("/business/{business_id}/employee/{employee_id}", response_model=Success)
@require_acl("employee.d", roles=[Role.OPERATOR])
@handled
async def delete_employee(business_id: int, employee_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_employee(business_id, employee_id)
    return Success(success=True)


@router.put("/business/{business_id}/employee/{employee_id}/account",
            response_model=Employee)
@require_acl("employee.w", roles=[Role.OPERATOR])
@handled
async def link_employee_account(business_id: int, employee_id: int,
                                boss_user: User, request: Request,
                                body: EmployeeAccountBody):
    """Tie a BOSS account to an employee record, or take the tie away.

    `/account/users/details` is the search the operator picks from — see
    `lib.server.get_user_details`.
    """
    _working_for(business_id, boss_user)
    if body.userId is None:
        employee = lib.unlink_employee_from_user(business_id, employee_id)
        if body.previousUserId is not None:
            await revoke_role(body.previousUserId, Role.EMPLOYEE)
        return employee

    employee = lib.link_employee_to_user(business_id, employee_id, body.userId)
    # Granted from the route: both reach BOSS over the network, which `lib`
    # does not do. They land in the employee's token at their next sign-in.
    await grant_license(body.userId)
    await grant_role(body.userId, Role.EMPLOYEE)
    return employee


@router.post("/business/{business_id}/employee/{employee_id}/schedule",
             response_model=WorkingDay)
@require_acl("employee.w", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def create_employee_schedule(business_id: int, employee_id: int, body: WorkingDayBody,
                                   boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # `response_model=WorkingDay` narrows the `EmployeeSchedule` this returns.
    return lib.add_working_day(business_id, employee_id, body.dayOfWeek, body.startTime,
                               body.endTime)


@router.put("/business/{business_id}/employee-schedule/{schedule_id}",
            response_model=WorkingDay)
@require_acl("employee.w", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def update_employee_schedule(business_id: int, schedule_id: int, body: WorkingDayBody,
                                   boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return lib.update_working_day(schedule_id, body.dayOfWeek, body.startTime,
                                  body.endTime)


@router.delete("/business/{business_id}/employee-schedule/{schedule_id}", response_model=Success)
@require_acl("employee.d", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def delete_employee_schedule(business_id: int, schedule_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_working_day(schedule_id)
    return Success(success=True)


@router.get("/business/{business_id}/employee/{employee_id}/time-off",
            response_model=TimeOffs)
@require_acl("employee.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_employee_time_off(business_id: int, employee_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return TimeOffs(timeOff=lib.get_time_off(employee_id))


@router.post("/business/{business_id}/employee/{employee_id}/time-off", response_model=TimeOff)
@require_acl("employee.w", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def add_employee_time_off(business_id: int, employee_id: int, body: TimeOffBody,
                                boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return lib.add_time_off(employee_id, body.date, body.startTime, body.endTime)


@router.put("/business/{business_id}/employee-time-off/{window_id}", response_model=TimeOff)
@require_acl("employee.w", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def update_employee_time_off(business_id: int, window_id: int, body: TimeOffBody,
                                   boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return lib.update_time_off(window_id, body.date, body.startTime, body.endTime)


@router.delete("/business/{business_id}/employee/{employee_id}/time-off/{window_id}",
               response_model=Success)
@require_acl("employee.d", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def delete_employee_time_off(business_id: int, employee_id: int, window_id: int,
                                   boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_time_off(window_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Business Config
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/config", response_model=BusinessConfig)
@require_acl("config.r", roles=[Role.OPERATOR])
@handled
async def get_config(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    config = lib.get_business_config(business_id)
    if config is None:
        # Nothing to configure. Returning `None` under a declared model is a
        # 500 that says only "response validation failed", which points at the
        # model rather than at the missing business.
        raise HTTPException(status_code=404, detail="That business no longer exists.")
    return config


@router.put("/business/{business_id}/config", response_model=BusinessConfig)
@require_acl("config.w", roles=[Role.OPERATOR])
@handled
async def update_config(business_id: int, boss_user: User, request: Request, body: BusinessConfigBody):
    _working_for(business_id, boss_user)

    # Only what the window sent. Every field on the body is optional, so an
    # absent one is a field the owner did not touch — writing `None` for it
    # would clear a setting nobody asked about.
    settings = body.model_dump(exclude_unset=True, exclude={"operatingHours"})

    # Operating hours are seven rows on their own table, not a column, so they
    # are written separately and only when the window sent them.
    if body.operatingHours is not None:
        for hours in body.operatingHours:
            lib.set_operating_hours(business_id, hours.dayOfWeek, hours.openTime,
                                    hours.closeTime, hours.isClosed)

    if not settings:
        return lib.get_business_config(business_id)
    return lib.update_business_config(business_id, settings)


# Stripe Connect is still a stub. `stripe_client.py` and the Swift vendor layer
# it calls are both unwritten, and neither can be until there are credentials to
# exchange. The shapes below are the contract they will have to meet.

@router.get("/business/{business_id}/config/stripe/connect", response_model=ConfigStripeConnect)
@require_acl("config.r", roles=[Role.OPERATOR])
@handled
async def get_stripe_connect_url(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    return ConfigStripeConnect(
        connectUrl="https://connect.stripe.com/oauth/authorize?stub=true")


@router.get("/business/{business_id}/config/stripe/callback", response_model=ConfigStripeCallback)
@require_acl("config.w", roles=[Role.OPERATOR])
@handled
async def handle_stripe_callback(business_id: int, boss_user: User, request: Request, code: str = "", state: str = ""):
    _working_for(business_id, boss_user)
    # Stripe redirects the operator's browser here with `code` and `state`, so
    # this arrives as a GET carrying their session.
    #
    # `state` is the token this app generated before sending them to Stripe and
    # stored against their session. Comparing it on return is what says the
    # exchange began here, and it is checked before `code` is spent.
    return ConfigStripeCallback(stripeAccountId="acct_stub_001", success=True)


@router.get("/business/{business_id}/config/templates", response_model=ConfigTemplates)
@require_acl("config.r", roles=[Role.OPERATOR])
@handled
async def get_business_templates(business_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    # The whole template, settings included: the Business Type tab fills the
    # other tabs in from them before the owner saves, so it needs to see what
    # it is about to write.
    return ConfigTemplates(templates=lib.get_business_templates())


# ---------------------------------------------------------------------------
# MARK: Operator: Customers
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/customers", response_model=Customers)
@require_acl("customer.r", roles=[Role.OPERATOR])
@handled
async def get_customers(business_id: int, boss_user: User, request: Request, q: Optional[str] = None):
    _working_for(business_id, boss_user)
    return Customers(
        customers=lib.get_customers(business_id, q))


@router.get("/business/{business_id}/customer/{customer_id}", response_model=CustomerDetail)
@require_acl("customer.r", roles=[Role.OPERATOR])
@handled
async def get_customer(business_id: int, customer_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    customer = lib.get_customer(business_id, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="That customer no longer exists.")
    return customer


@router.put("/business/{business_id}/customer/{customer_id}", response_model=CustomerDetail)
@require_acl("customer.w", roles=[Role.OPERATOR])
@handled
async def update_customer(business_id: int, customer_id: int, boss_user: User, request: Request,
                          body: CustomerBody):
    _working_for(business_id, boss_user)
    # Only the fields the form sent, for the reason Business Settings gives:
    # an absent field is one nobody touched.
    return lib.update_customer(business_id, customer_id,
                               body.model_dump(exclude_unset=True))


@router.post("/business/{business_id}/customer/{customer_id}/notes", response_model=Note)
@require_acl("customer.w", roles=[Role.OPERATOR])
@handled
async def add_customer_note(business_id: int, customer_id: int, boss_user: User, request: Request, body: NoteBody):
    _working_for(business_id, boss_user)
    return lib.add_customer_note(business_id, customer_id, body.note,
                                 _operator_user(request))


@router.put("/business/{business_id}/customer/{customer_id}/note/{note_id}", response_model=Note)
@require_acl("customer.w", roles=[Role.OPERATOR])
@handled
async def update_customer_note(business_id: int, customer_id: int, note_id: int, boss_user: User, request: Request,
                               body: NoteBody):
    _working_for(business_id, boss_user)
    return lib.update_customer_note(customer_id, note_id, body.note)


@router.delete("/business/{business_id}/customer/{customer_id}/note/{note_id}", response_model=Success)
@require_acl("customer.d", roles=[Role.OPERATOR])
@handled
async def delete_customer_note(business_id: int, customer_id: int, note_id: int, boss_user: User, request: Request):
    _working_for(business_id, boss_user)
    lib.delete_customer_note(customer_id, note_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Financial Report
# ---------------------------------------------------------------------------

@router.get("/business/{business_id}/reports/financial", response_model=FinancialReport)
@require_acl("report.r", roles=[Role.OPERATOR])
@handled
async def get_financial_report(business_id: int, 
    boss_user: User, request: Request,
    period: str = "quarter",
    year: Optional[int] = None,
    quarter: Optional[int] = None
):
    _working_for(business_id, boss_user)
    # The screen opens with no parameters and takes the period it is answered
    # with, so the defaults are decided here — one clock rather than two.
    now = datetime.now()
    return lib.get_financial_report(
        business_id,
        year if year is not None else now.year,
        (quarter if quarter is not None else (now.month - 1) // 3 + 1)
        if period == "quarter" else None,
    )


@router.get("/business/{business_id}/reports/financial/export")
@require_acl("report.r", roles=[Role.OPERATOR])
@handled
async def export_financial_report(business_id: int, 
    boss_user: User, request: Request,
    period: str = "quarter",
    year: Optional[int] = None,
    quarter: Optional[int] = None
):
    _working_for(business_id, boss_user)
    now = datetime.now()
    csv = lib.export_financial_report(
        business_id,
        year if year is not None else now.year,
        (quarter if quarter is not None else (now.month - 1) // 3 + 1)
        if period == "quarter" else None,
    )
    return Response(
        content=csv, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=financial-report.csv"}
    )


# ---------------------------------------------------------------------------
# MARK: Operator: Holidays
# ---------------------------------------------------------------------------

# No controller calls these yet — the Schedule tab has no holidays section. The
# rule they serve is live regardless: a business that observes a holiday offers
# no slots that day, which `get_available_slots` already applies.

@router.get("/business/{business_id}/holidays", response_model=Holidays)
@require_acl("config.r", roles=[Role.OPERATOR])
@handled
async def get_operator_holidays(business_id: int, boss_user: User, request: Request, year: int = 2026):
    _working_for(business_id, boss_user)
    return Holidays(
        year=year,
        holidays=lib.get_business_holidays(business_id, year)
    )


@router.put("/business/{business_id}/holidays", response_model=Holidays)
@require_acl("config.w", roles=[Role.OPERATOR])
@handled
async def update_operator_holidays(business_id: int, boss_user: User, request: Request, body: HolidaysBody):
    _working_for(business_id, boss_user)
    return Holidays(
        year=body.year,
        holidays=lib.set_business_holidays(business_id,
                                           body.year, body.holidayIds)
    )


# ---------------------------------------------------------------------------
# MARK: Employee portal
# ---------------------------------------------------------------------------

@router.get("/my/profile", response_model=EmployeeProfile)
@require_user()
@handled
async def get_employee_profile(boss_user: User, request: Request):
    # `employeeId` is carried because the screen edits its working days and
    # time off through the routes the operator uses — the service authorises
    # rather than duplicates them.
    profile = lib.get_employee_profile(boss_user.id)
    if profile is None:
        raise HTTPException(status_code=404,
                            detail="You are not on this business's staff.")
    return profile


@router.put("/my/profile", response_model=EmployeeProfile)
@require_user()
@handled
async def update_employee_profile(boss_user: User, request: Request,
                                  body: EmployeeProfileBody):
    # Only what an employee owns about themselves. Their name, their business,
    # and whether they may manage their own schedule are the operator's to set.
    return lib.update_employee_profile(boss_user.id, body.jobTypeIds)


@router.get("/my/today", response_model=EmployeeToday)
@require_user()
@handled
async def get_employee_today(boss_user: User, request: Request, date: str = ""):
    today = lib.get_employee_today(boss_user.id, date)
    if today is None:
        raise HTTPException(status_code=404,
                            detail="You are not on this business's staff.")
    return today


# ---------------------------------------------------------------------------
# MARK: Operator Signup
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=Signup)
@require_user()
@handled
async def operator_signup(boss_user: User, request: Request, body: SignupBody):
    signup = lib.sign_up(boss_user.id,
                         body.model_dump(exclude={"templateId"}, exclude_unset=True),
                         body.templateId)
    # Granted from the route rather than the rule: both reach BOSS over the
    # network, which `lib` does not do.
    #
    # The license is what lets them open the app at all, and the role is what
    # the routes read. Both land in their token at the next sign-in.
    await grant_license(boss_user.id)
    await grant_role(boss_user.id, Role.OPERATOR)
    return signup


# ---------------------------------------------------------------------------
# MARK: Super Admin
# ---------------------------------------------------------------------------

@router.get("/businesses", response_model=SuperadminBusinesses)
@require_admin()
@handled
async def superadmin_get_businesses(request: Request, status: Optional[str] = None):
    return SuperadminBusinesses(
        businesses=lib.get_platform_businesses(status or "all"))


@router.get("/business/{business_id}", response_model=BusinessConfig)
@require_admin()
@handled
async def superadmin_get_business(business_id: int, request: Request):
    business = lib.get_platform_business(business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="That business no longer exists.")
    return business


@router.post("/businesses", response_model=BusinessConfig)
@require_admin()
@handled
async def superadmin_create_business(request: Request, body: PlatformBusinessBody):
    return lib.create_platform_business(body.model_dump(exclude_unset=True))


@router.put("/business/{business_id}", response_model=BusinessConfig)
@require_admin()
@handled
async def superadmin_update_business(business_id: int, request: Request,
                                     body: PlatformBusinessBody):
    return lib.update_platform_business(business_id,
                                        body.model_dump(exclude_unset=True))


@router.post("/business/{business_id}/enable",
             response_model=BusinessConfig)
@require_admin()
@handled
async def superadmin_enable_business(business_id: int, request: Request):
    return lib.enable_business(business_id)


@router.post("/business/{business_id}/disable",
             response_model=BusinessConfig)
@require_admin()
@handled
async def superadmin_disable_business(business_id: int, request: Request):
    # The kiosk stops taking bookings and the record stays. A business with
    # appointments behind it is closed this way rather than deleted.
    return lib.disable_business(business_id)


@router.delete("/business/{business_id}", response_model=Success)
@require_admin()
@handled
async def superadmin_delete_business(business_id: int, request: Request):
    lib.delete_business(business_id)
    return Success(success=True)


@router.post("/contact-field", response_model=ContactFieldType)
@require_admin()
@handled
async def superadmin_create_contact_field(request: Request,
                                          body: ContactFieldTypeBody):
    return lib.add_contact_field_type(body.name, body.fieldType, body.otpCapable)


@router.put("/contact-field/{field_id}", response_model=ContactFieldType)
@require_admin()
@handled
async def superadmin_update_contact_field(field_id: int, request: Request,
                                          body: ContactFieldTypeBody):
    return lib.update_contact_field_type(field_id, body.name, body.fieldType,
                                         body.otpCapable)


@router.delete("/contact-field/{field_id}", response_model=Success)
@require_admin()
@handled
async def superadmin_delete_contact_field(field_id: int, request: Request):
    lib.delete_contact_field_type(field_id)
    return Success(success=True)


@router.post("/contact-fields/reorder", response_model=ContactFields)
@require_admin()
@handled
async def superadmin_reorder_contact_fields(request: Request, body: ReorderBody):
    return ContactFields(fields=lib.reorder_contact_field_types(body.ids))


@router.get("/system-holidays/years", response_model=SuperadminHolidaysYears)
@require_admin()
@handled
async def superadmin_get_holiday_years(request: Request):
    # The years the platform has holidays for. Empty until somebody fetches a
    # year, and the screen offers this one and the next in the meantime.
    return SuperadminHolidaysYears(years=lib.get_holiday_years())


@router.get("/system-holidays", response_model=SuperadminHolidays)
@require_admin()
@handled
async def superadmin_get_holidays(request: Request, year: int = 2026):
    return lib.get_platform_holidays(year)


@router.post("/system-holidays/refresh", response_model=SuperadminHolidaysRefresh)
@require_admin()
@handled
async def superadmin_refresh_holidays(request: Request, year: int = 2026):
    # Fetching a year from a holiday API is still a stub, as Stripe is: there
    # is no vendor to call yet. The shape below is the contract it will meet,
    # and the count is what the screen reports.
    return SuperadminHolidaysRefresh(
        success=True, count=len(db.get_holidays_for_year(year)))


@router.get("/timeout", response_model=SuperadminTimeout)
@require_admin()
@handled
async def superadmin_get_timeout(request: Request):
    return SuperadminTimeout(timeoutMinutes=lib.get_schedule_timeout_minutes())


@router.put("/timeout", response_model=SuperadminTimeout)
@require_admin()
@handled
async def superadmin_update_timeout(request: Request, body: SuperadminTimeout):
    # The kiosk draws its countdown from this, so the two agree by taking the
    # same answer rather than by being set to the same number.
    return SuperadminTimeout(
        timeoutMinutes=lib.set_schedule_timeout_minutes(body.timeoutMinutes))


@router.get("/vendors", response_model=SuperadminVendors)
@require_admin()
@handled
async def superadmin_get_vendors(request: Request):
    return SuperadminVendors(vendors=lib.get_vendors())


@router.put("/vendor/{vendor_type}", response_model=Vendor)
@require_admin()
@handled
async def superadmin_update_vendor(vendor_type: str, request: Request,
                                   body: VendorBody):
    return lib.set_vendor(vendor_type, body.vendor, body.config)


@router.get("/templates", response_model=ConfigTemplates)
@require_admin()
@handled
async def superadmin_get_templates(request: Request):
    return ConfigTemplates(templates=lib.get_business_templates())


@router.post("/template", response_model=BusinessTemplate)
@require_admin()
@handled
async def superadmin_create_template(request: Request, body: TemplateBody):
    return lib.add_business_template(body.name, body.description, body.config)


@router.put("/template/{template_id}", response_model=BusinessTemplate)
@require_admin()
@handled
async def superadmin_update_template(template_id: int, request: Request,
                                     body: TemplateBody):
    # The settings a template carries are left as they are: the modal edits
    # the name and the description, and has no field for the rest.
    return lib.update_business_template(template_id, body.name, body.description)


@router.delete("/template/{template_id}", response_model=Success)
@require_admin()
@handled
async def superadmin_delete_template(template_id: int, request: Request):
    lib.delete_business_template(template_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Package lifecycle

# BOSS's super user, who reaches every business.
ADMIN_USER_ID = 1

# ---------------------------------------------------------------------------

async def _operator_business(request: Request) -> int:
    """Which business the signed-in operator is acting for.

    For the routes that name no business. A caller who runs none is refused
    here rather than being served somebody else's work.
    """
    user = await _signed_in_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    business_id = lib.operator_business(user.id)
    if business_id is None:
        raise HTTPException(status_code=403,
                            detail="You do not run a business yet.")
    return business_id


def _get_employee_id(business_id: int, user: User) -> Optional[int]:
    """The caller's employee id at this business, or `None` for an operator.

    An operator sees the business, an employee sees the jobs they are on, and
    both read the same routes — so the id is what the rule narrows by.
    """
    _working_for(business_id, user)
    row = lib.employee_record(business_id, user.id)
    if row is None or row.role == lib.OPERATOR:
        return None
    return row.id


def _working_for(business_id: int, user: User) -> User:
    """Confirm the caller works for the business named in the path.

    `@require_acl` has already said who they are and that their role reaches
    this route. This says the business is one they belong to — an operator
    reaches only their own, and a super admin reaches any.

    Takes the user the decorator injected rather than asking BOSS again: each
    ask is a request to the Swift service.
    """
    # The super admin reaches any business, so they can help an operator with
    # theirs. `lib.server._authenticate_admin` decides the same way.
    if user.id == ADMIN_USER_ID:
        return user
    if not lib.is_working_for_business(business_id, user.id):
        raise HTTPException(status_code=403,
                            detail="You do not work for this business.")
    return user


def _operator_user(request: Request) -> int:
    """Which signed-in user is acting, for the records that name an author.

    The same placeholder `_operator_business` carries, and for the same reason:
    sign-in is not wired through yet, and one line is easier to find than the
    handful of routes that would each have guessed.
    """
    return 1


async def _signed_in_user(request: Request) -> Optional[User]:
    """The BOSS user making this request, when there is one.

    Optional on purpose: the kiosk has to serve somebody who is not signed in,
    and that is the ordinary case. Signed in only sharpens what the booking
    knows about who it is for.

    Only a verified account counts. An unverified address has not been shown to
    belong to whoever typed it, and it is what customer records are matched on.
    """
    try:
        user = await get_user(request)
    except Exception:
        # Not signed in, or BOSS could not say. Neither is an error here — the
        # booking goes ahead as an anonymous one.
        return None
    return user if user is not None and user.verified else None


def caller_of(request: Request) -> str:
    """Who is submitting, for the job code throttle.

    The client IP. It is the only marker an anonymous caller cannot reset — a
    cookie is cleared from a menu — and nginx sets `X-Real-IP` on every
    proxied request.

    Trusting that header is safe only while this service binds to `127.0.0.1`
    and is reachable through nginx alone. Exposed directly, a caller could send
    whatever they liked and the throttle would be decorative.
    """
    return request.headers.get("X-Real-IP") or (
        request.client.host if request.client else "unknown"
    )


def start():
    """Called once by `api.py` when the service loads this app."""
    start_database()


def shutdown():
    pass
