#
# Scheduler — Stub API
#
# All endpoints return hard-coded fixture data.
# Replace each stub body with real logic in Stage 4.
#

from datetime import datetime, timedelta, timezone

from functools import wraps

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from lib.model import User
from lib.server import get_user, require_user

from . import lib
from .db import start_database
from .model import *

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


@router.get("/me", response_model=MeResponse)
async def get_me(request: Request):
    # TODO: resolve from BOSS session; stub returns operator.
    return MeResponse(role="operator", businessId=1)


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


@router.get("/kiosk/{business_id}/calendar")
async def get_kiosk_calendar(
    business_id: int, request: Request,
    jobTypeId: int = 0, sizeId: int = 0, employeeId: Optional[int] = None,
    month: int = 7, year: int = 2026
):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}/calendar
    return {
        "year": year,
        "month": month,
        "availableDays": [28, 29, 30, 31]
    }


@router.get("/kiosk/{business_id}/day-slots")
async def get_kiosk_day_slots(
    business_id: int, request: Request,
    jobTypeId: int = 0, sizeId: int = 0, employeeId: Optional[int] = None, date: str = ""
):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}/day-slots
    return {
        "date": date,
        "slots": [
            {"time": "08:00", "displayTime": "8:00 AM"},
            {"time": "08:15", "displayTime": "8:15 AM"},
            {"time": "09:00", "displayTime": "9:00 AM"},
            {"time": "10:30", "displayTime": "10:30 AM"},
            {"time": "14:00", "displayTime": "2:00 PM"}
        ]
    }


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


@router.get("/operator/me")
async def get_operator_me(request: Request, businessId: Optional[int] = None):
    # TODO: verify operator role for kiosk close-button logic.
    #
    # `isOperator` decides whether the kiosk shows its close button, and it is
    # true for two people: whoever owns this business — a `business_users`
    # record for this `businessId` — and a BOSS platform super admin, always.
    #
    # It is false for everyone else, including an operator of a *different*
    # business. Owning some business is not owning this one, and the kiosk
    # hides the menu bar and the dock: anyone who gets this button can walk
    # out of the kiosk and into BOSS.
    return {"isOperator": True, "businessId": businessId or 1}


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
        jobType=AdminEmployeeJobType(id=a.jobTypeId, name=a.jobTypeName),
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

@router.get("/customer/appointments", response_model=CustomerAppointments)
@require_user()
@handled
async def get_customer_appointments(boss_user: User, request: Request):
    # Across every business. A customer record belongs to one business, and
    # somebody who has used two has two records — gathered by the account.
    return lib.get_customer_appointments(boss_user.id)


# ---------------------------------------------------------------------------
# MARK: Operator: Dashboard
# ---------------------------------------------------------------------------

@router.get("/admin/setup", response_model=SetupResponse)
@handled
async def get_setup(request: Request):
    # The one place that decides whether a business can take a booking.
    # Nothing is stored: it is computed each time it is asked, so a rule added
    # here takes effect everywhere at once and no column can fall out of step
    # with the thing it describes.
    #
    # Two callers, one answer: the app on launch, to decide where to put the
    # operator, and `SetupAssistant`, which lists the tasks and opens what each
    # one names. `GET /kiosk/{businessId}` asks the same question and shows the
    # customer only the boolean.
    return lib.get_setup(_operator_business(request))


@router.get("/admin/dashboard", response_model=AdminDashboard)
@handled
async def get_dashboard(request: Request):
    board = lib.get_dashboard(_operator_business(request))
    if board is None:
        raise HTTPException(status_code=404, detail="That business no longer exists.")
    return board


# ---------------------------------------------------------------------------
# MARK: Operator: Schedule
# ---------------------------------------------------------------------------

@router.get("/admin/schedule/month", response_model=AdminScheduleMonth)
@handled
async def get_schedule_month(request: Request, year: int = 2026, month: int = 1):
    # Only the days with work on them. The screen draws the grid and fills in
    # what it is given, so an empty day is an absence rather than a zero.
    return lib.get_schedule_month(_operator_business(request), year, month)


@router.get("/admin/schedule/week", response_model=AdminScheduleWeek)
@handled
async def get_schedule_week(request: Request, date: str = ""):
    return lib.get_schedule_week(
        _operator_business(request),
        date or datetime.now().strftime("%Y-%m-%d"))


@router.get("/admin/schedule/day", response_model=AdminScheduleDay)
@handled
async def get_schedule_day(request: Request, date: str = ""):
    return lib.get_schedule_day(
        _operator_business(request),
        date or datetime.now().strftime("%Y-%m-%d"))


@router.get("/admin/jobs/unassigned", response_model=AdminJobsUnassigned)
@handled
async def get_unassigned_jobs(request: Request):
    return AdminJobsUnassigned(jobs=lib.get_unassigned_jobs(_operator_business(request)))


@router.post("/admin/jobs/assign", response_model=AdminJobsAssign)
@handled
async def assign_jobs(request: Request, body: AssignBody):
    return lib.assign_jobs(_operator_business(request), body.jobIds)


# ---------------------------------------------------------------------------
# MARK: Operator: Jobs
# ---------------------------------------------------------------------------

@router.get("/admin/job/{job_id}", response_model=AdminJob)
@handled
async def get_admin_job(job_id: int, request: Request):
    job = lib.get_admin_job(job_id)
    if job is None:
        raise HTTPException(status_code=404,
                            detail="That appointment no longer exists.")
    return job


@router.put("/admin/job/{job_id}", response_model=Success)
async def update_admin_job(job_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/job/{jobId}
    return Success(success=True)


@router.post("/admin/job/{job_id}/complete", response_model=Success)
@handled
async def complete_job(job_id: int, request: Request):
    lib.complete_job(job_id)
    return Success(success=True)


@router.post("/admin/job/{job_id}/payment", response_model=PaymentResult)
@handled
async def add_payment(job_id: int, request: Request, body: PaymentBody):
    return lib.record_payment(job_id, body.amount, body.method,
                              collected_by_user_id=_operator_user(request),
                              note=body.note)


@router.get("/admin/job/{job_id}/payment-link", response_model=AdminJobPaymentLink)
@handled
async def get_payment_link(job_id: int, request: Request):
    # Stripe is still a stub — see the Business Settings routes. The shape is
    # the contract `stripe_client.create_payment_link` will have to meet.
    job = lib.get_admin_job(job_id)
    if job is None:
        raise HTTPException(status_code=404,
                            detail="That appointment no longer exists.")
    return AdminJobPaymentLink(
        jobId=job.id,
        amount=job.size.cost if job.size else 0.0,
        paymentLinkUrl="https://buy.stripe.com/test_stub_link",
        jobCode=job.jobCode,
    )


@router.get("/admin/jobs", response_model=AdminJobs)
@handled
async def search_jobs(
    request: Request,
    status: Optional[str] = None,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    fromDate: Optional[str] = None,
    toDate: Optional[str] = None,
    jobTypeId: Optional[int] = None,
    employeeId: Optional[int] = None
):
    jobs = lib.search_jobs(_operator_business(request), from_date=fromDate,
                           to_date=toDate, status=status, job_type_id=jobTypeId,
                           name=name, phone=phone, employee_id=employeeId)
    return AdminJobs(jobs=jobs, total=len(jobs))


# ---------------------------------------------------------------------------
# MARK: Operator: Job Types
# ---------------------------------------------------------------------------

@router.get("/admin/job-types", response_model=AdminJobTypes)
@handled
async def get_job_types(request: Request, term: Optional[str] = None):
    # TODO: GET /api/io.bithead.scheduler/admin/job-types
    #
    # `term` is what a token menu is typing. The match belongs here rather than
    # in the client: the menu picks a few out of however many there are, and
    # only this side knows how many that is.
    business_id = _operator_business(request)
    return AdminJobTypes(jobTypes=lib.get_job_types(business_id, term=term))


@router.get("/admin/job-type/{job_type_id}", response_model=AdminJobType)
@handled
async def get_job_type(job_type_id: int, request: Request):
    # `id` on a contact field identifies what this job type asks for;
    # `contactFieldTypeId` is the system-wide field it asks for. Two records.
    job_type = lib.get_job_type_detail(job_type_id)
    if job_type is None:
        raise HTTPException(status_code=404,
                            detail="That job type no longer exists.")
    return job_type


@router.post("/admin/job-type", response_model=Created)
@handled
async def create_job_type(request: Request, body: JobTypeDraftBody):
    # The form posts here as it opens, so sizes, attributes, and contact fields
    # have a job type to belong to before anything is named. Until the form
    # saves over it the row is a draft — inactive, so it reaches no customer —
    # and leaving the window deletes it.
    job_type = lib.create_job_type(_operator_business(request), body.name)
    return Created(id=job_type.id)


@router.put("/admin/job-type/{job_type_id}", response_model=Success)
@handled
async def update_job_type(job_type_id: int, body: JobTypeBody, request: Request):
    lib.update_job_type(job_type_id, body.name, body.minEmployees, body.isActive)
    return Success(success=True)


@router.delete("/admin/job-type/{job_type_id}", response_model=Success)
@handled
async def delete_job_type(job_type_id: int, request: Request):
    lib.delete_job_type(job_type_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Sizes
# ---------------------------------------------------------------------------

@router.post("/admin/job-type/{job_type_id}/size", response_model=JobTypeSizeDetail)
@handled
async def create_job_type_size(job_type_id: int, request: Request,
                               body: JobTypeSizeBody):
    return lib.add_job_type_size(job_type_id, body.name, body.durationMinutes,
                                 body.cost)


@router.put("/admin/job-type-size/{size_id}", response_model=JobTypeSizeDetail)
@handled
async def update_job_type_size(size_id: int, body: JobTypeSizeBody,
                               request: Request):
    # `JobTypeSize` is this plus `jobTypeId`; the declared model narrows it.
    return lib.update_job_type_size(size_id, body.name, body.durationMinutes,
                                    body.cost)


@router.delete("/admin/job-type-size/{size_id}", response_model=Success)
@handled
async def delete_job_type_size(size_id: int, request: Request):
    lib.delete_job_type_size(size_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Attributes
# ---------------------------------------------------------------------------

@router.post("/admin/job-type/{job_type_id}/attribute", response_model=JobTypeAttribute)
@handled
async def create_job_type_attribute(job_type_id: int, request: Request,
                                    body: JobTypeAttributeBody):
    return lib.add_job_type_attribute(job_type_id, body.name, body.attributeType,
                                      body.options, body.isRequired)


@router.put("/admin/job-type-attribute/{attribute_id}", response_model=JobTypeAttribute)
@handled
async def update_job_type_attribute(attribute_id: int, request: Request,
                                    body: JobTypeAttributeBody):
    return lib.update_job_type_attribute(attribute_id, body.name,
                                         body.attributeType, body.options,
                                         body.isRequired)


@router.delete("/admin/job-type-attribute/{attribute_id}", response_model=Success)
@handled
async def delete_job_type_attribute(attribute_id: int, request: Request):
    lib.delete_job_type_attribute(attribute_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Contact Fields
# ---------------------------------------------------------------------------

@router.post("/admin/job-type/{job_type_id}/contact-field",
             response_model=JobTypeContactField)
@handled
async def create_job_type_contact_field(job_type_id: int, request: Request,
                                        body: ContactFieldBody):
    return lib.add_job_type_contact_field(job_type_id, body.contactFieldTypeId,
                                          body.isRequired, body.requireOtp)


@router.put("/admin/job-type-contact-field/{contact_field_id}",
            response_model=JobTypeContactField)
@handled
async def update_job_type_contact_field(contact_field_id: int, request: Request,
                                        body: ContactFieldBody):
    return lib.update_job_type_contact_field(contact_field_id,
                                             body.contactFieldTypeId,
                                             body.isRequired, body.requireOtp)


@router.delete("/admin/job-type-contact-field/{contact_field_id}",
               response_model=Success)
@handled
async def delete_job_type_contact_field(contact_field_id: int, request: Request):
    lib.delete_job_type_contact_field(contact_field_id)
    return Success(success=True)


@router.post("/admin/job-type/{job_type_id}/contact-fields/reorder",
             response_model=JobTypeContactFields)
@handled
async def reorder_job_type_contact_fields(job_type_id: int, request: Request,
                                          body: ReorderBody):
    # The whole order comes back, so the screen redraws from the server rather
    # than from the arrangement it just sent.
    return JobTypeContactFields(
        contactFields=lib.reorder_job_type_contact_fields(job_type_id, body.ids))


@router.get("/admin/icons")
async def get_icons(request: Request, type: str = "system"):
    # TODO: GET /api/io.bithead.scheduler/admin/icons
    return {
        "icons": [
            {"id": 1, "filename": "calendar.svg", "isSystem": True, "url": "/boss/app/io.bithead.scheduler/image/icons/calendar.svg"},
            {"id": 2, "filename": "scissors.svg", "isSystem": True, "url": "/boss/app/io.bithead.scheduler/image/icons/scissors.svg"},
            {"id": 3, "filename": "leaf.svg", "isSystem": True, "url": "/boss/app/io.bithead.scheduler/image/icons/leaf.svg"},
            {"id": 4, "filename": "wrench.svg", "isSystem": True, "url": "/boss/app/io.bithead.scheduler/image/icons/wrench.svg"}
        ]
    }


@router.post("/admin/icons")
async def upload_icon(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/icons (multipart)
    return {"id": 10, "url": "/upload/io.bithead.scheduler/custom-icon.svg"}


@router.get("/admin/stripe/products")
async def get_stripe_products(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/stripe/products
    return {
        "products": [
            {"id": "prod_stub1", "name": "Lawn Mowing — Small", "defaultPrice": {"id": "price_stub1", "unitAmount": 5000, "currency": "usd"}},
            {"id": "prod_stub2", "name": "Lawn Mowing — Medium", "defaultPrice": {"id": "price_stub2", "unitAmount": 8000, "currency": "usd"}},
            {"id": "prod_stub3", "name": "Hedge Trimming", "defaultPrice": {"id": "price_stub3", "unitAmount": 6500, "currency": "usd"}}
        ]
    }


@router.get("/admin/contact-fields", response_model=AdminContactFields)
@handled
async def get_contact_fields(request: Request):
    # The kinds of detail a job type may ask for. Seeded once per installation
    # and chosen from, so the kiosk can trust that a field marked `otpCapable`
    # can receive a code.
    return AdminContactFields(fields=lib.get_contact_field_types())


# ---------------------------------------------------------------------------
# MARK: Operator: Employees
# ---------------------------------------------------------------------------

@router.get("/admin/employees", response_model=AdminEmployees)
@handled
async def get_admin_employees(request: Request):
    return AdminEmployees(employees=lib.get_employees(_operator_business(request)))


@router.get("/admin/employee/{employee_id}", response_model=AdminEmployee)
@handled
async def get_employee(employee_id: int, request: Request):
    e = lib.get_employee(employee_id)
    if e is None:
        raise HTTPException(status_code=404,
                            detail={"reason": "That employee no longer exists."})
    return AdminEmployee(
        id=e.id, userId=None, firstName=e.firstName, lastName=e.lastName,
        includeInSchedule=e.includeInSchedule,
        canManageOwnSchedule=e.canManageOwnSchedule,
        scheduleTemplate=lib.get_working_days(employee_id),
        timeOff=lib.get_time_off(employee_id),
        jobTypes=[AdminEmployeeJobType(id=j.id, name=j.name)
                  for j in lib.get_employee_job_types(employee_id)]
    )


@router.post("/admin/employee")
async def create_employee(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/employee
    #
    # The form posts here as it opens, so working days and time off have
    # someone to belong to before anyone is named. Until the form saves over
    # it the row is a draft, and leaving the window deletes it.
    return {"id": 4}


@router.put("/admin/employee/{employee_id}", response_model=Success)
@handled
async def update_employee(employee_id: int, body: EmployeeBody, request: Request):
    lib.update_employee(employee_id, body.firstName, body.lastName,
                        body.includeInSchedule, body.canManageOwnSchedule)
    # Sent as the whole list rather than as changes, so what is stored is what
    # was on screen.
    if body.jobTypeIds is not None:
        lib.set_employee_job_types(employee_id, body.jobTypeIds)
    return Success(success=True)


@router.delete("/admin/employee/{employee_id}", response_model=Success)
@handled
async def delete_employee(employee_id: int, request: Request):
    lib.delete_employee(employee_id)
    return Success(success=True)


@router.post("/admin/employee/{employee_id}/schedule",
             response_model=WorkingDay)
@handled
async def create_employee_schedule(employee_id: int, body: WorkingDayBody,
                                   request: Request):
    # `response_model=WorkingDay` narrows the `EmployeeSchedule` this returns.
    return lib.add_working_day(employee_id, body.dayOfWeek, body.startTime,
                               body.endTime)


@router.put("/admin/employee-schedule/{schedule_id}",
            response_model=WorkingDay)
@handled
async def update_employee_schedule(schedule_id: int, body: WorkingDayBody,
                                   request: Request):
    return lib.update_working_day(schedule_id, body.dayOfWeek, body.startTime,
                                  body.endTime)


@router.delete("/admin/employee-schedule/{schedule_id}", response_model=Success)
@handled
async def delete_employee_schedule(schedule_id: int, request: Request):
    lib.delete_working_day(schedule_id)
    return Success(success=True)


@router.get("/admin/employee/{employee_id}/time-off",
            response_model=AdminEmployeeTimeOff)
@handled
async def get_employee_time_off(employee_id: int, request: Request):
    return AdminEmployeeTimeOff(timeOff=lib.get_time_off(employee_id))


@router.post("/admin/employee/{employee_id}/time-off", response_model=TimeOff)
@handled
async def add_employee_time_off(employee_id: int, body: TimeOffBody,
                                request: Request):
    return lib.add_time_off(employee_id, body.date, body.startTime, body.endTime)


@router.put("/admin/employee-time-off/{window_id}", response_model=TimeOff)
@handled
async def update_employee_time_off(window_id: int, body: TimeOffBody,
                                   request: Request):
    return lib.update_time_off(window_id, body.date, body.startTime, body.endTime)


@router.delete("/admin/employee/{employee_id}/time-off/{window_id}",
               response_model=Success)
@handled
async def delete_employee_time_off(employee_id: int, window_id: int,
                                   request: Request):
    lib.delete_time_off(window_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Business Config
# ---------------------------------------------------------------------------

@router.get("/admin/config", response_model=BusinessConfig)
@handled
async def get_config(request: Request):
    config = lib.get_business_config(_operator_business(request))
    if config is None:
        # Nothing to configure. Returning `None` under a declared model is a
        # 500 that says only "response validation failed", which points at the
        # model rather than at the missing business.
        raise HTTPException(status_code=404, detail="That business no longer exists.")
    return config


@router.put("/admin/config", response_model=BusinessConfig)
@handled
async def update_config(request: Request, body: BusinessConfigBody):
    business_id = _operator_business(request)

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

@router.get("/admin/config/stripe/connect", response_model=AdminConfigStripeConnect)
@handled
async def get_stripe_connect_url(request: Request):
    return AdminConfigStripeConnect(
        connectUrl="https://connect.stripe.com/oauth/authorize?stub=true")


@router.post("/admin/config/stripe/callback", response_model=AdminConfigStripeCallback)
@handled
async def handle_stripe_callback(request: Request):
    return AdminConfigStripeCallback(stripeAccountId="acct_stub_001", success=True)


@router.get("/admin/config/templates", response_model=AdminConfigTemplates)
@handled
async def get_business_templates(request: Request):
    # The whole template, settings included: the Business Type tab fills the
    # other tabs in from them before the owner saves, so it needs to see what
    # it is about to write.
    return AdminConfigTemplates(templates=lib.get_business_templates())


# ---------------------------------------------------------------------------
# MARK: Operator: Customers
# ---------------------------------------------------------------------------

@router.get("/admin/customers", response_model=AdminCustomers)
@handled
async def get_customers(request: Request, q: Optional[str] = None):
    return AdminCustomers(
        customers=lib.get_customers(_operator_business(request), q))


@router.get("/admin/customer/{customer_id}", response_model=AdminCustomer)
@handled
async def get_customer(customer_id: int, request: Request):
    customer = lib.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="That customer no longer exists.")
    return customer


@router.put("/admin/customer/{customer_id}", response_model=AdminCustomer)
@handled
async def update_customer(customer_id: int, request: Request,
                          body: CustomerBody):
    # Only the fields the form sent, for the reason Business Settings gives:
    # an absent field is one nobody touched.
    return lib.update_customer(customer_id,
                               body.model_dump(exclude_unset=True))


@router.post("/admin/customer/{customer_id}/notes", response_model=Note)
@handled
async def add_customer_note(customer_id: int, request: Request, body: NoteBody):
    return lib.add_customer_note(customer_id, body.note,
                                 _operator_user(request))


@router.put("/admin/customer/{customer_id}/note/{note_id}", response_model=Note)
@handled
async def update_customer_note(customer_id: int, note_id: int, request: Request,
                               body: NoteBody):
    return lib.update_customer_note(customer_id, note_id, body.note)


@router.delete("/admin/customer/{customer_id}/note/{note_id}", response_model=Success)
@handled
async def delete_customer_note(customer_id: int, note_id: int, request: Request):
    lib.delete_customer_note(customer_id, note_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Financial Report
# ---------------------------------------------------------------------------

@router.get("/admin/reports/financial", response_model=FinancialReport)
@handled
async def get_financial_report(
    request: Request,
    period: str = "quarter",
    year: Optional[int] = None,
    quarter: Optional[int] = None
):
    # The screen opens with no parameters and takes the period it is answered
    # with, so the defaults are decided here — one clock rather than two.
    now = datetime.now()
    return lib.get_financial_report(
        _operator_business(request),
        year if year is not None else now.year,
        (quarter if quarter is not None else (now.month - 1) // 3 + 1)
        if period == "quarter" else None,
    )


@router.get("/admin/reports/financial/export")
@handled
async def export_financial_report(
    request: Request,
    period: str = "quarter",
    year: Optional[int] = None,
    quarter: Optional[int] = None
):
    now = datetime.now()
    csv = lib.export_financial_report(
        _operator_business(request),
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

@router.get("/admin/holidays", response_model=AdminHolidays)
@handled
async def get_operator_holidays(request: Request, year: int = 2026):
    return AdminHolidays(
        year=year,
        holidays=lib.get_business_holidays(_operator_business(request), year)
    )


@router.put("/admin/holidays", response_model=AdminHolidays)
@handled
async def update_operator_holidays(request: Request, body: HolidaysBody):
    return AdminHolidays(
        year=body.year,
        holidays=lib.set_business_holidays(_operator_business(request),
                                           body.year, body.holidayIds)
    )


# ---------------------------------------------------------------------------
# MARK: Employee portal
# ---------------------------------------------------------------------------

@router.get("/employee/profile", response_model=EmployeeProfile)
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


@router.put("/employee/profile", response_model=EmployeeProfile)
@require_user()
@handled
async def update_employee_profile(boss_user: User, request: Request,
                                  body: EmployeeProfileBody):
    # Only what an employee owns about themselves. Their name, their business,
    # and whether they may manage their own schedule are the operator's to set.
    return lib.update_employee_profile(boss_user.id, body.jobTypeIds)


@router.get("/employee/today", response_model=EmployeeToday)
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

@router.post("/signup")
async def operator_signup(request: Request):
    # TODO: POST /api/io.bithead.scheduler/signup
    return {"businessId": 99, "operatorId": 50}


# ---------------------------------------------------------------------------
# MARK: Super Admin
# ---------------------------------------------------------------------------

@router.get("/superadmin/businesses")
async def superadmin_get_businesses(request: Request, status: Optional[str] = None):
    # TODO: GET /api/io.bithead.scheduler/superadmin/businesses
    return {
        "businesses": [
            {"id": 1, "name": "Green Thumb Landscaping", "ownerName": "Maria Garcia", "isActive": True, "createDate": "2026-01-15"},
            {"id": 2, "name": "Sparkle Clean", "ownerName": "David Park", "isActive": True, "createDate": "2026-02-20"},
            {"id": 3, "name": "Cut Above Salon", "ownerName": "Sandra Reyes", "isActive": False, "createDate": "2026-03-01"}
        ]
    }


@router.get("/superadmin/business/{business_id}")
async def superadmin_get_business(business_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/business/{id}
    return {
        "id": business_id,
        "name": "Green Thumb Landscaping",
        "ownerName": "Maria Garcia",
        "phone": "(555) 867-5309",
        "addressLine1": "456 Garden Blvd",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "timezone": "America/Chicago",
        "isActive": True,
        "createDate": "2026-01-15"
    }


@router.post("/superadmin/businesses")
async def superadmin_create_business(request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/businesses
    return {"id": 99}


@router.put("/superadmin/business/{business_id}")
async def superadmin_update_business(business_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/business/{id}
    return Success(success=True)


@router.post("/superadmin/business/{business_id}/enable")
async def superadmin_enable_business(business_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/business/{id}/enable
    return Success(success=True)


@router.post("/superadmin/business/{business_id}/disable")
async def superadmin_disable_business(business_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/business/{id}/disable
    return Success(success=True)


@router.delete("/superadmin/business/{business_id}")
async def superadmin_delete_business(business_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/superadmin/business/{id}
    return Success(success=True)


@router.get("/superadmin/contact-fields")
async def superadmin_get_contact_fields(request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/contact-fields
    return {
        "fields": [
            {"id": 1, "name": "First Name", "fieldType": "text", "otpCapable": False, "sortOrder": 0},
            {"id": 2, "name": "Last Name", "fieldType": "text", "otpCapable": False, "sortOrder": 1},
            {"id": 3, "name": "Phone", "fieldType": "phone", "otpCapable": True, "sortOrder": 2},
            {"id": 4, "name": "Email", "fieldType": "email", "otpCapable": True, "sortOrder": 3},
            {"id": 5, "name": "Address Line 1", "fieldType": "text", "otpCapable": False, "sortOrder": 4},
            {"id": 6, "name": "Address Line 2", "fieldType": "text", "otpCapable": False, "sortOrder": 5},
            {"id": 7, "name": "City", "fieldType": "text", "otpCapable": False, "sortOrder": 6},
            {"id": 8, "name": "State", "fieldType": "text", "otpCapable": False, "sortOrder": 7},
            {"id": 9, "name": "Zip", "fieldType": "text", "otpCapable": False, "sortOrder": 8}
        ]
    }


@router.post("/superadmin/contact-field")
async def superadmin_create_contact_field(request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/contact-field
    return {"id": 10}


@router.put("/superadmin/contact-field/{field_id}")
async def superadmin_update_contact_field(field_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/contact-field/{id}
    return Success(success=True)


@router.delete("/superadmin/contact-field/{field_id}")
async def superadmin_delete_contact_field(field_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/superadmin/contact-field/{id}
    return Success(success=True)


@router.post("/superadmin/contact-fields/reorder")
async def superadmin_reorder_contact_fields(request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/contact-fields/reorder
    return Success(success=True)


@router.get("/superadmin/holidays/years")
async def superadmin_get_holiday_years(request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/holidays/years
    # Returns the years that have been queried and cached from the holiday API.
    # If none exist, returns empty list; controller falls back to current + next year.
    from datetime import datetime
    current_year = datetime.now().year
    return {"years": [current_year, current_year + 1]}


@router.get("/superadmin/holidays")
async def superadmin_get_holidays(request: Request, year: int = 2026):
    # TODO: GET /api/io.bithead.scheduler/superadmin/holidays
    return {
        "year": year,
        "countries": [
            {
                "countryCode": "US",
                "countryName": "United States",
                "holidays": [
                    {"id": 1, "name": "New Year's Day", "date": "2026-01-01"},
                    {"id": 2, "name": "Independence Day", "date": "2026-07-04"},
                    {"id": 3, "name": "Thanksgiving Day", "date": "2026-11-26"},
                    {"id": 4, "name": "Christmas Day", "date": "2026-12-25"}
                ]
            },
            {
                "countryCode": "CA",
                "countryName": "Canada",
                "holidays": [
                    {"id": 5, "name": "Canada Day", "date": "2026-07-01"},
                    {"id": 6, "name": "Remembrance Day", "date": "2026-11-11"}
                ]
            }
        ]
    }


@router.post("/superadmin/holidays/refresh")
async def superadmin_refresh_holidays(request: Request, year: int = 2026):
    # TODO: POST /api/io.bithead.scheduler/superadmin/holidays/refresh
    return {"success": True, "count": 12}


@router.get("/superadmin/timeout")
async def superadmin_get_timeout(request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/timeout
    return {"timeoutMinutes": SESSION_TIMEOUT_MINUTES}


@router.put("/superadmin/timeout")
async def superadmin_update_timeout(request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/timeout
    return Success(success=True)


@router.get("/superadmin/vendors")
async def superadmin_get_vendors(request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/vendors
    return {
        "vendors": [
            {
                "type": "email",
                "currentVendor": "sendgrid",
                "registeredVendors": ["sendgrid", "mailgun"],
                "config": {"fromEmail": "noreply@bithead.io", "fromName": "Scheduler"}
            },
            {
                "type": "sms",
                "currentVendor": None,
                "registeredVendors": ["twilio"],
                "config": {}
            }
        ]
    }


@router.put("/superadmin/vendor/{vendor_type}")
async def superadmin_update_vendor(vendor_type: str, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/vendor/{type}
    return Success(success=True)


@router.get("/superadmin/templates")
async def superadmin_get_templates(request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/templates
    return {
        "templates": [
            {"id": 1, "name": "Personal Service", "description": "Salons, spas, fitness studios.", "iconUrl": None},
            {"id": 2, "name": "Field Service", "description": "Landscaping, cleaning, home repair.", "iconUrl": None},
            {"id": 3, "name": "Healthcare/Wellness", "description": "Dental, chiropractic, therapy.", "iconUrl": None},
            {"id": 4, "name": "Pet Services", "description": "Grooming, walking, sitting.", "iconUrl": None},
            {"id": 5, "name": "General", "description": "A flexible starting point for any service business.", "iconUrl": None},
            {"id": 6, "name": "Food & Drink", "description": "Cafés, bakeries, takeaway. Customers choose a pickup time and you handle the queue.", "iconUrl": None}
        ]
    }


@router.post("/superadmin/template")
async def superadmin_create_template(request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/template
    return {"id": 6}


@router.put("/superadmin/template/{template_id}")
async def superadmin_update_template(template_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/template/{id}
    return Success(success=True)


@router.delete("/superadmin/template/{template_id}")
async def superadmin_delete_template(template_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/superadmin/template/{id}
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Package lifecycle
# ---------------------------------------------------------------------------

def _operator_business(request: Request) -> int:
    """Which business the signed-in operator is acting for.

    A placeholder while sign-in is not yet wired through: every admin route is
    scoped to one business, and this is the single place that decides which, so
    there is one line to change rather than ninety.
    """
    return 1


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
