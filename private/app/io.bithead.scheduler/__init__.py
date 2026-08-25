#
# Scheduler — Stub API
#
# All endpoints return hard-coded fixture data.
# Replace each stub body with real logic in Stage 4.
#

from datetime import datetime, timedelta, timezone

from functools import wraps

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

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


# ---------------------------------------------------------------------------
# MARK: Kiosk
# ---------------------------------------------------------------------------

@router.get("/kiosk/{business_id}")
async def get_kiosk_config(business_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}
    return {
        "businessId": business_id,
        "name": "Green Thumb Landscaping",
        "phone": "(555) 867-5309",
        "description": "Professional landscaping for residential and commercial properties.",
        "slotIncrementMinutes": 15,
        "cutoffDays": 30,
        "minBookingNoticeHours": 24,
        "minChangeNoticeMinutes": 15,
        "allowCustomerEmployeeSelection": False,
        "scheduleTimeoutMinutes": 10,
        # reserved | unlimited. Under unlimited the kiosk takes no hold, shows
        # no countdown, and every increment between opening and closing is
        # offered — see "Time Slots" in plan.md.
        "slotMode": "reserved",
        # One range per weekday, and a day may be closed. Distinct from employee
        # schedules, which say when people work rather than when the doors are open.
        "operatingHours": [
            {"dayOfWeek": 0, "openTime": "09:00", "closeTime": "17:00", "isClosed": True},
            {"dayOfWeek": 1, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 2, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 3, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 4, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 5, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 6, "openTime": "09:00", "closeTime": "15:00", "isClosed": False}
        ],
        "configured": True
    }


@router.get("/kiosk/{business_id}/employees")
async def get_kiosk_employees(business_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}/employees
    return {
        "employees": [
            {"id": 1, "firstName": "Alice", "lastName": "Kim"},
            {"id": 2, "firstName": "Bob", "lastName": "Torres"}
        ]
    }


@router.get("/kiosk/{business_id}/job-types")
async def get_kiosk_job_types(business_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}/job-types
    return {
        "jobTypes": [
            {
                "id": 1,
                "name": "Lawn Mowing",
                "iconUrl": None,
                "sizes": [
                    {"id": 1, "name": "Small (up to 2000 sq ft)", "durationMinutes": 30, "cost": 50.00},
                    {"id": 2, "name": "Medium (2000–4000 sq ft)", "durationMinutes": 60, "cost": 80.00},
                    {"id": 3, "name": "Large (4000+ sq ft)", "durationMinutes": 120, "cost": 150.00}
                ],
                "contactFields": [
                    {"id": 1, "name": "First Name", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 2, "name": "Last Name", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 3, "name": "Phone", "fieldType": "phone", "isRequired": True, "requireOtp": False},
                    {"id": 4, "name": "Email", "fieldType": "email", "isRequired": False, "requireOtp": False},
                    {"id": 5, "name": "Address Line 1", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 6, "name": "City", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 7, "name": "State", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 8, "name": "Zip", "fieldType": "text", "isRequired": True, "requireOtp": False}
                ],
                # An attribute asks for something the size does not already
                # say. Property size is the size — asking again on the contact
                # form is asking the customer the same question twice.
                "attributes": [
                    {"id": 1, "name": "Gate code", "attributeType": "text", "isRequired": False}
                ],
                "depositRequired": False
            },
            {
                "id": 2,
                "name": "Hedge Trimming",
                "iconUrl": None,
                "sizes": [
                    {"id": 4, "name": "Standard", "durationMinutes": 45, "cost": 65.00}
                ],
                "contactFields": [
                    {"id": 1, "name": "First Name", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 2, "name": "Last Name", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 3, "name": "Phone", "fieldType": "phone", "isRequired": True, "requireOtp": False},
                    {"id": 5, "name": "Address Line 1", "fieldType": "text", "isRequired": True, "requireOtp": False},
                    {"id": 6, "name": "City", "fieldType": "text", "isRequired": True, "requireOtp": False}
                ],
                "attributes": [],
                "depositRequired": False
            }
        ]
    }


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
    return KioskSlots(slots=[
        KioskSlot(date=s.date, time=s.time, displayDate=s.displayDate,
                  displayTime=s.displayTime)
        for s in lib.get_available_slots(business_id, jobTypeId, sizeId or None,
                                         employeeId, limit=limit)
    ])


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


@router.post("/kiosk/session/{session_id}/otp/verify", response_model=KioskSessionOtpVerify)
@handled
async def verify_otp(session_id: str, body: OtpVerifyBody, request: Request):
    result = lib.verify_otp(session_id, body.code)
    return KioskSessionOtpVerify(verified=result.verified,
                                 attemptsRemaining=result.attemptsRemaining)


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
    session = lib.confirm_session(
        session_id,
        contact={c.fieldId: c.value for c in body.contactData},
        attributes={a.fieldId: a.value for a in body.attributeData}
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

@router.post("/appointment/lookup", response_model=AppointmentLookup)
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
    sent = lib.request_appointment_access(body.jobCode.strip().upper(),
                                          caller=caller_of(request))
    return AppointmentLookup(sentTo=sent.sentTo, channel=sent.channel)


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

@router.get("/customer/appointments")
async def get_customer_appointments(request: Request):
    # TODO: GET /api/io.bithead.scheduler/customer/appointments
    return {
        "upcomingCount": 2,
        "appointments": [
            {
                "id": 42,
                "jobCode": "SCH4X2",
                "business": "Green Thumb Landscaping",
                "jobType": "Lawn Mowing",
                "scheduledDate": "2026-07-29",
                "scheduledTime": "09:00",
                "displayDate": "Tuesday, July 29",
                "displayTime": "9:00 AM",
                "employees": [{"firstName": "Alice", "lastInitial": "K"}],
                "status": "confirmed"
            },
            {
                "id": 43,
                "jobCode": "SCH9A1",
                "business": "Green Thumb Landscaping",
                "jobType": "Hedge Trimming",
                "scheduledDate": "2026-08-05",
                "scheduledTime": "10:00",
                "displayDate": "Wednesday, August 5",
                "displayTime": "10:00 AM",
                "employees": [],
                "status": "confirmed"
            }
        ]
    }


# ---------------------------------------------------------------------------
# MARK: Operator: Dashboard
# ---------------------------------------------------------------------------

class SetupTask(BaseModel):
    text: str                       # what is missing, in the operator's words
    controller: str                 # where it is fixed
    section: Optional[str] = None   # which page of it, for a window with pages
    done: bool = False              # whether this one is already satisfied


class SetupResponse(BaseModel):
    configured: bool
    tasks: List[SetupTask]


@router.get("/admin/setup", response_model=SetupResponse)
async def get_setup(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/setup
    #
    # The one place that decides whether a business can take a booking. Nothing
    # is stored: this is computed each time it is asked, so a rule added here
    # takes effect everywhere at once and no column can fall out of step with
    # the thing it describes.
    #
    # Two callers, one answer:
    #   - the app, on launch, to decide where to put the operator
    #   - `SetupAssistant`, which lists them and opens what each one names
    #   - `GET /kiosk/{businessId}`, whose `configured` is this same check —
    #     the customer sees only the boolean, never the tasks
    #
    # What it weighs, and none of it arrives with a new business:
    #   - a business name
    #   - an active job type, with at least one size and at least one contact
    #     field. The field *types* are seeded; this per-job-type selection is
    #     not, and a drafted job type starts empty
    #   - reserved: an employee, scheduled, linked to that job type
    #   - unlimited: at least one open day in operating hours
    #   - an SMS or email vendor, if any contact field requires OTP
    #   - Stripe, if any job type takes a deposit or payment
    #
    # Seeded or defaulted, and therefore not weighed: contact field types,
    # business templates, the schedule timeout, timezone, slot increment,
    # cutoff, booking notice, buffer.
    #
    # Every check is returned, done or not, so `SetupAssistant` can put a
    # checkmark beside one the moment it is finished. `configured` is stated
    # here rather than left for the caller to work out.
    tasks = [
        SetupTask(text="Give your business a name",
                  controller="BusinessConfig", section="general", done=True),
        SetupTask(text="Set the days and hours you are open",
                  controller="BusinessConfig", section="schedule", done=False),
        SetupTask(text='Add a size to "Lawn Mowing"',
                  controller="JobTypes", done=False),
        SetupTask(text='Ask "Lawn Mowing" for a way to contact the customer',
                  controller="JobTypes", done=False),
        SetupTask(text='No employee can perform "Hedge Trimming"',
                  controller="Employees", done=True),
        SetupTask(text='Connect Stripe — "Lawn Mowing" takes a deposit',
                  controller="BusinessConfig", section="payment", done=False)
    ]
    return SetupResponse(configured=all(t.done for t in tasks), tasks=tasks)


@router.get("/admin/dashboard")
async def get_dashboard(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/dashboard
    return {
        # The dashboard opens the kiosk, which is opened against a business.
        # Carried here rather than fetched separately: the screen already asks
        # this route for everything else it draws.
        "businessId": 1,
        # The dashboard hides the unassigned-work panel for an unlimited
        # business, which allocates nobody.
        "slotMode": "reserved",
        "jobsToday": 3,
        "jobsThisWeek": 12,
        "revenueThisMonth": 2450.00,
        "upcomingJobs": 8,
        "unassignedJobs": 2,
        "unassignedConflicts": 1
    }


# ---------------------------------------------------------------------------
# MARK: Operator: Schedule
# ---------------------------------------------------------------------------

@router.get("/admin/schedule/month")
async def get_schedule_month(request: Request, year: int = 2026, month: int = 7):
    # TODO: GET /api/io.bithead.scheduler/admin/schedule/month
    return {
        "year": year,
        "month": month,
        "days": [
            {"date": "2026-07-28", "jobCount": 2},
            {"date": "2026-07-29", "jobCount": 3},
            {"date": "2026-07-30", "jobCount": 1},
            {"date": "2026-07-31", "jobCount": 4}
        ]
    }


@router.get("/admin/schedule/week")
async def get_schedule_week(request: Request, date: str = ""):
    # TODO: GET /api/io.bithead.scheduler/admin/schedule/week
    return {
        "weekStart": "2026-07-27",
        "days": [
            {"date": "2026-07-27", "displayDate": "Sun 7/27", "jobs": []},
            {
                "date": "2026-07-28",
                "displayDate": "Mon 7/28",
                "jobs": [
                    {
                        "id": 42,
                        "jobCode": "SCH4X2",
                        "jobType": "Lawn Mowing",
                        "startTime": "09:00",
                        "endTime": "10:00",
                        "employeeInitials": ["AK", "BT"],
                        "status": "confirmed"
                    }
                ]
            },
            {
                "date": "2026-07-29",
                "displayDate": "Tue 7/29",
                "jobs": [
                    {
                        "id": 43,
                        "jobCode": "SCH9A1",
                        "jobType": "Hedge Trimming",
                        "startTime": "10:00",
                        "endTime": "10:45",
                        "employeeInitials": ["AK"],
                        "status": "confirmed"
                    },
                    {
                        "id": 44,
                        "jobCode": "SCHB77",
                        "jobType": "Lawn Mowing",
                        "startTime": "13:00",
                        "endTime": "14:00",
                        "employeeInitials": ["BT"],
                        "status": "confirmed"
                    }
                ]
            },
            {"date": "2026-07-30", "displayDate": "Wed 7/30", "jobs": []},
            {"date": "2026-07-31", "displayDate": "Thu 7/31", "jobs": []},
            {"date": "2026-08-01", "displayDate": "Fri 8/1", "jobs": []},
            {"date": "2026-08-02", "displayDate": "Sat 8/2", "jobs": []}
        ]
    }


@router.get("/admin/schedule/day")
async def get_schedule_day(request: Request, date: str = ""):
    # TODO: GET /api/io.bithead.scheduler/admin/schedule/day
    return {
        "date": date,
        "jobs": [
            {
                "id": 42,
                "jobCode": "SCH4X2",
                "jobType": "Lawn Mowing",
                "customerName": "Jane Doe",
                "startTime": "09:00",
                "endTime": "10:00",
                "startMinuteOffset": 540,
                "durationMinutes": 60,
                "employees": [
                    {"firstName": "Alice", "lastInitial": "K"},
                    {"firstName": "Bob", "lastInitial": "T"}
                ],
                # Two jobs overlapping each other are both in a group of two.
                "overlapColumn": 0,
                "overlapTotal": 2,
                "status": "confirmed",
                "paymentStatus": "unpaid"
            },
            {
                "id": 43,
                "jobCode": "SCH9A1",
                "jobType": "Hedge Trimming",
                "customerName": "John Smith",
                "startTime": "09:15",
                "endTime": "10:00",
                "startMinuteOffset": 555,
                "durationMinutes": 45,
                "employees": [
                    {"firstName": "Alice", "lastInitial": "K"}
                ],
                "overlapColumn": 1,
                "overlapTotal": 2,
                "status": "confirmed",
                "paymentStatus": "fully_paid"
            }
        ]
    }


@router.get("/admin/employees")
async def get_admin_employees(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/employees
    return {
        "employees": [
            {"id": 1, "firstName": "Alice", "lastName": "Kim", "includeInSchedule": True},
            {"id": 2, "firstName": "Bob", "lastName": "Torres", "includeInSchedule": True},
            {"id": 3, "firstName": "Carol", "lastName": "Lee", "includeInSchedule": False}
        ]
    }


@router.get("/admin/jobs/unassigned")
async def get_unassigned_jobs(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/jobs/unassigned
    return {
        "jobs": [
            {
                "id": 45,
                "jobCode": "SCHD99",
                "jobType": "Lawn Mowing",
                "customerName": "Robert Chen",
                "scheduledDate": "2026-07-30",
                "scheduledTime": "10:00",
                "displayDate": "Thursday, July 30",
                "displayTime": "10:00 AM",
                "isRecurring": False
            },
            {
                "id": 46,
                "jobCode": "SCHE12",
                "jobType": "Hedge Trimming",
                "customerName": "Sandra Wei",
                "scheduledDate": "2026-07-31",
                "scheduledTime": "14:00",
                "displayDate": "Friday, July 31",
                "displayTime": "2:00 PM",
                "isRecurring": False
            },
            {
                "id": 47,
                "jobCode": "SCHF55",
                "jobType": "Lawn Mowing",
                "customerName": "Maria Lopez",
                "scheduledDate": "2026-08-04",
                "scheduledTime": "09:00",
                "displayDate": "Tuesday, August 4",
                "displayTime": "9:00 AM",
                "isRecurring": True
            }
        ]
    }


@router.post("/admin/jobs/assign")
async def assign_jobs(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/jobs/assign
    return {"assigned": 3, "unassigned": 0}


# ---------------------------------------------------------------------------
# MARK: Operator: Jobs
# ---------------------------------------------------------------------------

@router.get("/admin/job/{job_id}")
async def get_admin_job(job_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/job/{jobId}
    return {
        "id": job_id,
        "jobCode": "SCH4X2",
        "jobType": {"id": 1, "name": "Lawn Mowing"},
        "size": {"id": 2, "name": "Medium (2000–4000 sq ft)", "durationMinutes": 60, "cost": 80.00},
        "scheduledDate": "2026-07-29",
        "scheduledTime": "09:00",
        "durationMinutes": 60,
        "status": "confirmed",
        "paymentStatus": "unpaid",
        # Locked to the customer — see POST /appointment/lookup/verify. The
        # count is what the operator's banner names, since they are the one
        # being called about it.
        "locked": False,
        "failedCodeAttempts": 0,
        "isRecurring": False,
        "employees": [
            {"id": 1, "firstName": "Alice", "lastName": "Kim"},
            {"id": 2, "firstName": "Bob", "lastName": "Torres"}
        ],
        "customer": {
            "id": 7,
            "firstName": "Jane",
            "lastName": "Doe",
            "phone": "(555) 234-5678",
            "email": "jane@example.com",
            "addressLine1": "123 Maple St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701"
        },
        "attributes": [
            {"name": "Property Size (sq ft)", "value": "2500"}
        ],
        "transactions": [
            {"id": 1, "amount": 40.00, "method": "stripe", "date": "2026-07-20T14:30:00Z", "collectedBy": "System"}
        ]
    }


@router.put("/admin/job/{job_id}")
async def update_admin_job(job_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/job/{jobId}
    return Success(success=True)


@router.post("/admin/job/{job_id}/complete")
async def complete_job(job_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job/{jobId}/complete
    return Success(success=True)


@router.post("/admin/job/{job_id}/payment")
async def add_payment(job_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job/{jobId}/payment
    return {"success": True, "newPaymentStatus": "fully_paid"}


@router.get("/admin/job/{job_id}/payment-link")
async def get_payment_link(job_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/job/{jobId}/payment-link
    return {
        "jobId": job_id,
        "amount": 80.00,
        "paymentLinkUrl": "https://buy.stripe.com/test_stub_link",
        "jobCode": "SCH4X2"
    }


@router.get("/admin/jobs")
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
    # TODO: GET /api/io.bithead.scheduler/admin/jobs
    return {
        "jobs": [
            {
                "id": 42,
                "jobCode": "SCH4X2",
                "jobType": "Lawn Mowing",
                "customerName": "Jane Doe",
                "scheduledDate": "2026-07-29",
                "scheduledTime": "09:00",
                "displayDate": "Tuesday, July 29",
                "displayTime": "9:00 AM",
                "status": "confirmed",
                "paymentStatus": "unpaid",
                "employees": [{"firstName": "Alice", "lastInitial": "K"}]
            },
            {
                "id": 43,
                "jobCode": "SCH9A1",
                "jobType": "Hedge Trimming",
                "customerName": "John Smith",
                "scheduledDate": "2026-08-05",
                "scheduledTime": "10:00",
                "displayDate": "Wednesday, August 5",
                "displayTime": "10:00 AM",
                "status": "confirmed",
                "paymentStatus": "fully_paid",
                "employees": [{"firstName": "Alice", "lastInitial": "K"}]
            }
        ],
        "total": 2
    }


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
    return AdminJobTypes(jobTypes=[
        JobTypeOption(id=j.id, name=j.name, minEmployees=j.minEmployees,
                      isActive=j.isActive)
        for j in lib.get_job_types(business_id, term=term)
    ])


@router.get("/admin/job-type/{job_type_id}")
async def get_job_type(job_type_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/job-type/{id}
    return {
        "id": job_type_id,
        "name": "Lawn Mowing",
        "iconId": None,
        "minEmployees": 1,
        "paymentRequired": False,
        "depositRequired": False,
        "depositType": None,
        "depositAmount": None,
        "depositNonrefundable": False,
        "stripeProductId": None,
        "stripePriceId": None,
        "isActive": True,
        "sizes": [
            {"id": 1, "name": "Small (up to 2000 sq ft)", "durationMinutes": 30, "cost": 50.00, "sortOrder": 0},
            {"id": 2, "name": "Medium (2000–4000 sq ft)", "durationMinutes": 60, "cost": 80.00, "sortOrder": 1},
            {"id": 3, "name": "Large (4000+ sq ft)", "durationMinutes": 120, "cost": 150.00, "sortOrder": 2}
        ],
        "attributes": [
            {"id": 1, "name": "Property Size (sq ft)", "attributeType": "number", "options": [], "isRequired": True, "sortOrder": 0}
        ],
        # `id` identifies what this job type asks for; `contactFieldTypeId` is
        # the system-wide field it asks for. They are different records.
        "contactFields": [
            {"id": 1, "contactFieldTypeId": 1, "name": "First Name", "fieldType": "text", "isRequired": True, "requireOtp": False, "sortOrder": 0},
            {"id": 2, "contactFieldTypeId": 2, "name": "Last Name", "fieldType": "text", "isRequired": True, "requireOtp": False, "sortOrder": 1},
            {"id": 3, "contactFieldTypeId": 3, "name": "Phone", "fieldType": "phone", "isRequired": True, "requireOtp": False, "sortOrder": 2}
        ],
        "employees": [
            {"id": 1, "firstName": "Alice", "lastName": "Kim"},
            {"id": 2, "firstName": "Bob", "lastName": "Torres"}
        ]
    }


@router.post("/admin/job-type")
async def create_job_type(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job-type
    #
    # The form posts here as it opens, so sizes, attributes, and contact fields
    # have a job type to belong to before anything is named. Until the form
    # saves over it the row is a draft, and leaving the window deletes it.
    return {"id": 3}


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

@router.post("/admin/job-type/{job_type_id}/size")
async def create_job_type_size(job_type_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job-type/{id}/size
    return {"id": 4, "name": "Extra Large", "durationMinutes": 180, "cost": 200.00, "sortOrder": 3}


@router.put("/admin/job-type-size/{size_id}", response_model=AdminJobTypeSize)
@handled
async def update_job_type_size(size_id: int, body: JobTypeSizeBody,
                               request: Request):
    size = lib.update_job_type_size(size_id, body.name, body.durationMinutes,
                                    body.cost)
    return AdminJobTypeSize(id=size.id, name=size.name,
                            durationMinutes=size.durationMinutes,
                            cost=size.cost, sortOrder=0)


@router.delete("/admin/job-type-size/{size_id}", response_model=Success)
@handled
async def delete_job_type_size(size_id: int, request: Request):
    lib.delete_job_type_size(size_id)
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Attributes
# ---------------------------------------------------------------------------

@router.post("/admin/job-type/{job_type_id}/attribute")
async def create_job_type_attribute(job_type_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job-type/{id}/attribute
    return {"id": 2, "name": "Gate code", "attributeType": "text", "options": [], "isRequired": False, "sortOrder": 1}


@router.put("/admin/job-type-attribute/{attribute_id}")
async def update_job_type_attribute(attribute_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/job-type-attribute/{id}
    return {"id": attribute_id, "name": "Gate code", "attributeType": "text", "options": [], "isRequired": False, "sortOrder": 1}


@router.delete("/admin/job-type-attribute/{attribute_id}")
async def delete_job_type_attribute(attribute_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/job-type-attribute/{id}
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Job Type Contact Fields
# ---------------------------------------------------------------------------

@router.post("/admin/job-type/{job_type_id}/contact-field")
async def create_job_type_contact_field(job_type_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job-type/{id}/contact-field
    return {"id": 4, "contactFieldTypeId": 4, "name": "Email", "fieldType": "email",
            "isRequired": True, "requireOtp": False, "sortOrder": 3}


@router.put("/admin/job-type-contact-field/{contact_field_id}")
async def update_job_type_contact_field(contact_field_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/job-type-contact-field/{id}
    return {"id": contact_field_id, "contactFieldTypeId": 4, "name": "Email", "fieldType": "email",
            "isRequired": True, "requireOtp": False, "sortOrder": 3}


@router.delete("/admin/job-type-contact-field/{contact_field_id}")
async def delete_job_type_contact_field(contact_field_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/job-type-contact-field/{id}
    return Success(success=True)


@router.post("/admin/job-type/{job_type_id}/contact-fields/reorder")
async def reorder_job_type_contact_fields(job_type_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job-type/{id}/contact-fields/reorder
    return Success(success=True)


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


@router.get("/admin/contact-fields")
async def get_contact_fields(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/contact-fields
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


# ---------------------------------------------------------------------------
# MARK: Operator: Employees
# ---------------------------------------------------------------------------

@router.get("/admin/employee/{employee_id}")
async def get_employee(employee_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/employee/{id}
    return {
        "id": employee_id,
        "userId": 101,
        "firstName": "Alice",
        "lastName": "Kim",
        "includeInSchedule": True,
        "canManageOwnSchedule": False,
        "scheduleTemplate": [
            {"id": 1, "dayOfWeek": 1, "startTime": "08:00", "endTime": "17:00"},
            {"id": 2, "dayOfWeek": 2, "startTime": "08:00", "endTime": "17:00"},
            {"id": 3, "dayOfWeek": 3, "startTime": "08:00", "endTime": "17:00"},
            {"id": 4, "dayOfWeek": 4, "startTime": "08:00", "endTime": "17:00"},
            {"id": 5, "dayOfWeek": 5, "startTime": "08:00", "endTime": "17:00"}
        ],
        "timeOff": [
            {"id": 1, "date": "2026-07-31", "startTime": "08:00", "endTime": "12:00"}
        ],
        "jobTypes": [
            {"id": 1, "name": "Lawn Mowing"},
            {"id": 2, "name": "Hedge Trimming"}
        ]
    }


@router.post("/admin/employee")
async def create_employee(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/employee
    #
    # The form posts here as it opens, so working days and time off have
    # someone to belong to before anyone is named. Until the form saves over
    # it the row is a draft, and leaving the window deletes it.
    return {"id": 4}


@router.put("/admin/employee/{employee_id}")
async def update_employee(employee_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/employee/{id}
    return Success(success=True)


@router.delete("/admin/employee/{employee_id}")
async def delete_employee(employee_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/employee/{id}
    return Success(success=True)


@router.post("/admin/employee/{employee_id}/schedule")
async def create_employee_schedule(employee_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/employee/{id}/schedule
    return {"id": 6, "dayOfWeek": 6, "startTime": "09:00", "endTime": "13:00"}


@router.put("/admin/employee-schedule/{schedule_id}")
async def update_employee_schedule(schedule_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/employee-schedule/{id}
    return {"id": schedule_id, "dayOfWeek": 1, "startTime": "08:00", "endTime": "17:00"}


@router.delete("/admin/employee-schedule/{schedule_id}")
async def delete_employee_schedule(schedule_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/employee-schedule/{id}
    return Success(success=True)


@router.get("/admin/employee/{employee_id}/time-off")
async def get_employee_time_off(employee_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/employee/{id}/time-off
    return {
        "timeOff": [
            {"id": 1, "date": "2026-07-31", "startTime": "08:00", "endTime": "12:00"}
        ]
    }


@router.post("/admin/employee/{employee_id}/time-off")
async def add_employee_time_off(employee_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/employee/{id}/time-off
    return {"id": 2, "date": "2026-08-14", "startTime": "08:00", "endTime": "12:00"}


@router.put("/admin/employee-time-off/{window_id}")
async def update_employee_time_off(window_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/employee-time-off/{id}
    return {"id": window_id, "date": "2026-08-14", "startTime": "08:00", "endTime": "12:00"}


@router.delete("/admin/employee/{employee_id}/time-off/{window_id}")
async def delete_employee_time_off(employee_id: int, window_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/employee/{id}/time-off/{windowId}
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Business Config
# ---------------------------------------------------------------------------

@router.get("/admin/config")
async def get_config(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/config
    return {
        "businessId": 1,
        "name": "Green Thumb Landscaping",
        "phone": "(555) 867-5309",
        "addressLine1": "456 Garden Blvd",
        "addressLine2": "",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "ownerName": "Maria Garcia",
        "description": "Professional landscaping for residential and commercial properties.",
        "siteUrl": "https://greenthumb.example.com",
        "timezone": "America/Chicago",
        "slotIncrementMinutes": 15,
        "cutoffDays": 30,
        "minBookingNoticeHours": 24,
        "minChangeNoticeMinutes": 15,
        "bufferMinutes": 15,
        "slotMode": "reserved",
        # One range per weekday, and a day may be closed. Distinct from employee
        # schedules, which say when people work rather than when the doors are open.
        "operatingHours": [
            {"dayOfWeek": 0, "openTime": "09:00", "closeTime": "17:00", "isClosed": True},
            {"dayOfWeek": 1, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 2, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 3, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 4, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 5, "openTime": "08:00", "closeTime": "18:00", "isClosed": False},
            {"dayOfWeek": 6, "openTime": "09:00", "closeTime": "15:00", "isClosed": False}
        ],
        "reminderEnabled": True,
        "confirmBySms": True,
        "confirmByEmail": False,
        "completionMode": "auto",
        "allowCustomerEmployeeSelection": False,
        "notifyEmployees": False,
        "publicUrl": "https://bithead.io/a/scheduler/1"
    }


@router.put("/admin/config")
async def update_config(request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/config
    return Success(success=True)


@router.get("/admin/config/stripe/connect")
async def get_stripe_connect_url(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/config/stripe/connect
    return {"connectUrl": "https://connect.stripe.com/oauth/authorize?stub=true"}


@router.post("/admin/config/stripe/callback")
async def handle_stripe_callback(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/config/stripe/callback
    return {"stripeAccountId": "acct_stub_001", "success": True}


@router.get("/admin/config/templates")
async def get_business_templates(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/config/templates
    return {
        "templates": [
            {
                "id": 1,
                "name": "Personal Service",
                "description": "Salons, spas, fitness studios. Clients choose their service provider.",
                "iconUrl": None
            },
            {
                "id": 2,
                "name": "Field Service",
                "description": "Landscaping, cleaning, home repair. Technicians go to the customer.",
                "iconUrl": None
            },
            {
                "id": 3,
                "name": "Healthcare/Wellness",
                "description": "Dental, chiropractic, therapy. Privacy and verification matter.",
                "iconUrl": None
            },
            {
                "id": 4,
                "name": "Pet Services",
                "description": "Grooming, walking, sitting. Mix of at-location and field visits.",
                "iconUrl": None
            },
            {
                "id": 5,
                "name": "General",
                "description": "A flexible starting point for any service business.",
                "iconUrl": None
            }
        ]
    }


# ---------------------------------------------------------------------------
# MARK: Operator: Customers
# ---------------------------------------------------------------------------

@router.get("/admin/customers")
async def get_customers(request: Request, q: Optional[str] = None):
    # TODO: GET /api/io.bithead.scheduler/admin/customers
    return {
        "customers": [
            {"id": 7, "firstName": "Jane", "lastName": "Doe", "phone": "(555) 234-5678", "email": "jane@example.com", "hasBossAccount": False},
            {"id": 8, "firstName": "John", "lastName": "Smith", "phone": "(555) 345-6789", "email": None, "hasBossAccount": True}
        ]
    }


@router.get("/admin/customer/{customer_id}")
async def get_customer(customer_id: int, request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/customer/{id}
    return {
        "id": customer_id,
        "firstName": "Jane",
        "lastName": "Doe",
        "phone": "(555) 234-5678",
        "email": "jane@example.com",
        "addressLine1": "123 Maple St",
        "addressLine2": "",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "hasBossAccount": False,
        "notes": [
            {"id": 1, "note": "Prefers morning appointments.", "createdBy": "Maria", "date": "2026-06-15"}
        ],
        "appointments": [
            {
                "id": 42,
                "jobCode": "SCH4X2",
                "jobType": "Lawn Mowing",
                "scheduledDate": "2026-07-29",
                "displayDate": "Tuesday, July 29",
                "displayTime": "9:00 AM",
                "status": "confirmed"
            }
        ]
    }


@router.put("/admin/customer/{customer_id}")
async def update_customer(customer_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/customer/{id}
    return Success(success=True)


@router.post("/admin/customer/{customer_id}/notes")
async def add_customer_note(customer_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/customer/{id}/notes
    return {"id": 2}


@router.put("/admin/customer/{customer_id}/note/{note_id}")
async def update_customer_note(customer_id: int, note_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}
    return Success(success=True)


@router.delete("/admin/customer/{customer_id}/note/{note_id}")
async def delete_customer_note(customer_id: int, note_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Operator: Financial Report
# ---------------------------------------------------------------------------

@router.get("/admin/reports/financial")
async def get_financial_report(
    request: Request,
    period: str = "quarter",
    year: Optional[int] = None,
    quarter: Optional[int] = None
):
    # TODO: GET /api/io.bithead.scheduler/admin/reports/financial
    from datetime import datetime
    now = datetime.now()
    current_year = now.year
    current_quarter = (now.month - 1) // 3 + 1

    resolved_year = year if year is not None else current_year
    resolved_quarter = quarter if quarter is not None else current_quarter
    available_years = [current_year - 1, current_year, current_year + 1]

    return {
        "period": period,
        "year": resolved_year,
        "quarter": resolved_quarter,
        "selectedPeriod": period,
        "selectedYear": resolved_year,
        "selectedQuarter": resolved_quarter,
        "availableYears": available_years,
        "revenue": 12450.00,
        "depositsCollected": 1200.00,
        "writeOffs": 80.00,
        "jobsCompleted": 48,
        "jobsCancelled": 3
    }


@router.get("/admin/reports/financial/export")
async def export_financial_report(
    request: Request,
    period: str = "quarter",
    year: int = 2026,
    quarter: Optional[int] = 2
):
    # TODO: GET /api/io.bithead.scheduler/admin/reports/financial/export (CSV download)
    from fastapi.responses import Response
    csv = "Period,Revenue,Deposits Collected,Write-Offs,Jobs Completed,Jobs Cancelled\n"
    csv += f"Q{quarter} {year},12450.00,1200.00,80.00,48,3\n"
    return Response(content=csv, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=financial-report.csv"})


# ---------------------------------------------------------------------------
# MARK: Operator: Holidays
# ---------------------------------------------------------------------------

@router.get("/admin/holidays")
async def get_operator_holidays(request: Request, year: int = 2026):
    # TODO: GET /api/io.bithead.scheduler/admin/holidays
    return {
        "year": year,
        "holidays": [
            {"id": 1, "name": "New Year's Day", "date": "2026-01-01", "selected": True},
            {"id": 2, "name": "Independence Day", "date": "2026-07-04", "selected": True},
            {"id": 3, "name": "Thanksgiving Day", "date": "2026-11-26", "selected": False},
            {"id": 4, "name": "Christmas Day", "date": "2026-12-25", "selected": True}
        ]
    }


@router.put("/admin/holidays")
async def update_operator_holidays(request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/holidays
    return Success(success=True)


# ---------------------------------------------------------------------------
# MARK: Employee portal
# ---------------------------------------------------------------------------

@router.get("/employee/profile")
async def get_employee_profile(request: Request):
    # TODO: GET /api/io.bithead.scheduler/employee/profile
    #
    # The signed-in employee's own record. `employeeId` is here because the
    # screen edits its working days and time off through the same routes the
    # operator uses — `/admin/employee/{id}/schedule` and friends — which the
    # service authorises rather than duplicates: an employee with
    # `can_manage_own_schedule` may act on their own record, an operator on
    # anyone in their business.
    return {
        "employeeId": 1,
        "firstName": "Alice",
        "lastName": "Kim",
        "canManageOwnSchedule": True,
        "scheduleTemplate": [
            {"id": 1, "dayOfWeek": 1, "startTime": "08:00", "endTime": "17:00"},
            {"id": 2, "dayOfWeek": 2, "startTime": "08:00", "endTime": "17:00"},
            {"id": 3, "dayOfWeek": 3, "startTime": "08:00", "endTime": "17:00"}
        ],
        "timeOff": [
            {"id": 1, "date": "2026-08-31", "startTime": "08:00", "endTime": "12:00"}
        ],
        "jobTypes": [
            {"id": 1, "name": "Lawn Mowing"}
        ]
    }


@router.put("/employee/profile")
async def update_employee_profile(request: Request):
    # TODO: PUT /api/io.bithead.scheduler/employee/profile
    #
    # Only what an employee owns about themselves: which job types they can
    # perform. Their name, their business, and whether they may manage their
    # own schedule at all are the operator's to set.
    return Success(success=True)


@router.get("/employee/today")
async def get_employee_today(request: Request):
    # TODO: GET /api/io.bithead.scheduler/employee/today
    return {
        "date": "2026-07-26",
        "displayDate": "Sunday, July 26",
        "jobs": [
            {
                "id": 42,
                "jobCode": "SCH4X2",
                "jobType": "Lawn Mowing",
                "startTime": "09:00",
                "endTime": "10:00",
                "displayTime": "9:00 AM – 10:00 AM",
                "customer": {
                    "firstName": "Jane",
                    "lastName": "Doe",
                    "phone": "(555) 234-5678",
                    "addressLine1": "123 Maple St",
                    "city": "Springfield",
                    "state": "IL"
                },
                "coWorkers": [
                    {"firstName": "Bob", "lastName": "Torres"}
                ],
                "attributes": [
                    {"name": "Property Size (sq ft)", "value": "2500"}
                ],
                "status": "confirmed"
            }
        ],
        "canManageOwnSchedule": False
    }


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
