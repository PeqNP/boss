#
# Scheduler — Stub API
#
# All endpoints return hard-coded fixture data.
# Replace each stub body with real logic in Stage 4.
#

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/io.bithead.scheduler")


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
        "allowCustomerEmployeeSelection": False,
        "scheduleTimeoutMinutes": 10,
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
                "attributes": [
                    {"id": 1, "name": "Property Size (sq ft)", "attributeType": "number", "isRequired": True}
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


@router.get("/kiosk/{business_id}/slots")
async def get_kiosk_slots(
    business_id: int, request: Request,
    jobTypeId: int = 0, sizeId: int = 0, employeeId: Optional[int] = None, limit: int = 5
):
    # TODO: GET /api/io.bithead.scheduler/kiosk/{businessId}/slots
    return {
        "slots": [
            {"date": "2026-07-28", "time": "09:00", "displayDate": "Monday, July 28", "displayTime": "9:00 AM"},
            {"date": "2026-07-28", "time": "10:00", "displayDate": "Monday, July 28", "displayTime": "10:00 AM"},
            {"date": "2026-07-29", "time": "08:00", "displayDate": "Tuesday, July 29", "displayTime": "8:00 AM"},
            {"date": "2026-07-29", "time": "13:00", "displayDate": "Tuesday, July 29", "displayTime": "1:00 PM"},
            {"date": "2026-07-30", "time": "11:00", "displayDate": "Wednesday, July 30", "displayTime": "11:00 AM"}
        ]
    }


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


@router.post("/kiosk/{business_id}/session")
async def create_kiosk_session(business_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/kiosk/{businessId}/session
    return {
        "sessionId": "sess_stub_001",
        "jobId": 42,
        "expiresAt": "2026-07-26T20:10:00Z",
        "timeoutMinutes": 10
    }


@router.put("/kiosk/session/{session_id}/extend")
async def extend_kiosk_session(session_id: str, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/kiosk/session/{sessionId}/extend
    return {"expiresAt": "2026-07-26T20:20:00Z"}


@router.post("/kiosk/session/{session_id}/otp/send")
async def send_otp(session_id: str, request: Request):
    # TODO: POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/otp/send
    return {"sent": True}


@router.post("/kiosk/session/{session_id}/otp/verify")
async def verify_otp(session_id: str, request: Request):
    # TODO: POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/otp/verify
    return {"verified": True, "attemptsRemaining": 2}


@router.post("/kiosk/session/{session_id}/confirm")
async def confirm_kiosk_session(session_id: str, request: Request):
    # TODO: POST /api/io.bithead.scheduler/kiosk/session/{sessionId}/confirm
    return {
        "jobId": 42,
        "jobCode": "SCH4X2",
        "stripePaymentUrl": None
    }


@router.get("/operator/me")
async def get_operator_me(request: Request, businessId: Optional[int] = None):
    # TODO: verify operator role for kiosk close-button logic.
    return {"isOperator": True, "businessId": businessId or 1}


# ---------------------------------------------------------------------------
# MARK: Appointment
# ---------------------------------------------------------------------------

@router.get("/appointment/{appointment_id}")
async def get_appointment(appointment_id: str, request: Request):
    # TODO: GET /api/io.bithead.scheduler/appointment/{appointmentId}
    return {
        "id": appointment_id,
        "jobCode": "SCH4X2",
        "jobType": {"id": 1, "name": "Lawn Mowing"},
        "size": {"id": 2, "name": "Medium (2000–4000 sq ft)", "durationMinutes": 60, "cost": 80.00},
        "scheduledDate": "2026-07-29",
        "scheduledTime": "09:00",
        "displayDate": "Tuesday, July 29",
        "displayTime": "9:00 AM",
        "business": {
            "name": "Green Thumb Landscaping",
            "phone": "(555) 867-5309"
        },
        "employees": [
            {"firstName": "Alice", "lastInitial": "K"}
        ],
        "status": "confirmed"
    }


@router.put("/appointment/{appointment_id}/reschedule")
async def reschedule_appointment(appointment_id: str, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/appointment/{appointmentId}/reschedule
    return {"success": True}


@router.delete("/appointment/{appointment_id}")
async def cancel_appointment(appointment_id: str, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/appointment/{appointmentId}
    return {"success": True}


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

@router.get("/admin/dashboard")
async def get_dashboard(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/dashboard
    return {
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
                "overlapColumn": 0,
                "overlapTotal": 1,
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
    return {"success": True}


@router.post("/admin/job/{job_id}/complete")
async def complete_job(job_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job/{jobId}/complete
    return {"success": True}


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

@router.get("/admin/job-types")
async def get_job_types(request: Request):
    # TODO: GET /api/io.bithead.scheduler/admin/job-types
    return {
        "jobTypes": [
            {"id": 1, "name": "Lawn Mowing", "minEmployees": 1, "isActive": True},
            {"id": 2, "name": "Hedge Trimming", "minEmployees": 1, "isActive": True}
        ]
    }


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
            {"id": 1, "name": "Property Size (sq ft)", "attributeType": "number", "isRequired": True, "sortOrder": 0}
        ],
        "contactFields": [
            {"id": 1, "name": "First Name", "fieldType": "text", "isRequired": True, "requireOtp": False, "sortOrder": 0},
            {"id": 2, "name": "Last Name", "fieldType": "text", "isRequired": True, "requireOtp": False, "sortOrder": 1},
            {"id": 3, "name": "Phone", "fieldType": "phone", "isRequired": True, "requireOtp": False, "sortOrder": 2}
        ],
        "employees": [
            {"id": 1, "firstName": "Alice", "lastName": "Kim"},
            {"id": 2, "firstName": "Bob", "lastName": "Torres"}
        ]
    }


@router.post("/admin/job-type")
async def create_job_type(request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/job-type
    return {"id": 3}


@router.put("/admin/job-type/{job_type_id}")
async def update_job_type(job_type_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/job-type/{id}
    return {"success": True}


@router.delete("/admin/job-type/{job_type_id}")
async def delete_job_type(job_type_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/job-type/{id}
    return {"success": True}


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
        "bossUserId": 101,
        "firstName": "Alice",
        "lastName": "Kim",
        "includeInSchedule": True,
        "canManageOwnSchedule": False,
        "scheduleTemplate": [
            {"dayOfWeek": 1, "startTime": "08:00", "endTime": "17:00"},
            {"dayOfWeek": 2, "startTime": "08:00", "endTime": "17:00"},
            {"dayOfWeek": 3, "startTime": "08:00", "endTime": "17:00"},
            {"dayOfWeek": 4, "startTime": "08:00", "endTime": "17:00"},
            {"dayOfWeek": 5, "startTime": "08:00", "endTime": "17:00"}
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
    return {"id": 4}


@router.put("/admin/employee/{employee_id}")
async def update_employee(employee_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/employee/{id}
    return {"success": True}


@router.delete("/admin/employee/{employee_id}")
async def delete_employee(employee_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/employee/{id}
    return {"success": True}


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
    return {"id": 2}


@router.delete("/admin/employee/{employee_id}/time-off/{window_id}")
async def delete_employee_time_off(employee_id: int, window_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/employee/{id}/time-off/{windowId}
    return {"success": True}


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
        "bufferMinutes": 15,
        "reminderEnabled": True,
        "completionMode": "auto",
        "allowCustomerEmployeeSelection": False,
        "notifyEmployees": False,
        "publicUrl": "https://bithead.io/a/scheduler/1"
    }


@router.put("/admin/config")
async def update_config(request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/config
    return {"success": True}


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
    return {"success": True}


@router.post("/admin/customer/{customer_id}/notes")
async def add_customer_note(customer_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/admin/customer/{id}/notes
    return {"id": 2}


@router.put("/admin/customer/{customer_id}/note/{note_id}")
async def update_customer_note(customer_id: int, note_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}
    return {"success": True}


@router.delete("/admin/customer/{customer_id}/note/{note_id}")
async def delete_customer_note(customer_id: int, note_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/admin/customer/{id}/note/{noteId}
    return {"success": True}


# ---------------------------------------------------------------------------
# MARK: Operator: Financial Report
# ---------------------------------------------------------------------------

@router.get("/admin/reports/financial")
async def get_financial_report(
    request: Request,
    period: str = "quarter",
    year: int = 2026,
    quarter: Optional[int] = 2
):
    # TODO: GET /api/io.bithead.scheduler/admin/reports/financial
    return {
        "period": period,
        "year": year,
        "quarter": quarter,
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
    return {"success": True}


# ---------------------------------------------------------------------------
# MARK: Employee portal
# ---------------------------------------------------------------------------

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
    return {"success": True}


@router.post("/superadmin/business/{business_id}/enable")
async def superadmin_enable_business(business_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/business/{id}/enable
    return {"success": True}


@router.post("/superadmin/business/{business_id}/disable")
async def superadmin_disable_business(business_id: int, request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/business/{id}/disable
    return {"success": True}


@router.delete("/superadmin/business/{business_id}")
async def superadmin_delete_business(business_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/superadmin/business/{id}
    return {"success": True}


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
    return {"success": True}


@router.delete("/superadmin/contact-field/{field_id}")
async def superadmin_delete_contact_field(field_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/superadmin/contact-field/{id}
    return {"success": True}


@router.post("/superadmin/contact-fields/reorder")
async def superadmin_reorder_contact_fields(request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/contact-fields/reorder
    return {"success": True}


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
    return {"timeoutMinutes": 10}


@router.put("/superadmin/timeout")
async def superadmin_update_timeout(request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/timeout
    return {"success": True}


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
    return {"success": True}


@router.get("/superadmin/templates")
async def superadmin_get_templates(request: Request):
    # TODO: GET /api/io.bithead.scheduler/superadmin/templates
    return {
        "templates": [
            {"id": 1, "name": "Personal Service", "description": "Salons, spas, fitness studios.", "iconUrl": None},
            {"id": 2, "name": "Field Service", "description": "Landscaping, cleaning, home repair.", "iconUrl": None},
            {"id": 3, "name": "Healthcare/Wellness", "description": "Dental, chiropractic, therapy.", "iconUrl": None},
            {"id": 4, "name": "Pet Services", "description": "Grooming, walking, sitting.", "iconUrl": None},
            {"id": 5, "name": "General", "description": "A flexible starting point for any service business.", "iconUrl": None}
        ]
    }


@router.post("/superadmin/template")
async def superadmin_create_template(request: Request):
    # TODO: POST /api/io.bithead.scheduler/superadmin/template
    return {"id": 6}


@router.put("/superadmin/template/{template_id}")
async def superadmin_update_template(template_id: int, request: Request):
    # TODO: PUT /api/io.bithead.scheduler/superadmin/template/{id}
    return {"success": True}


@router.delete("/superadmin/template/{template_id}")
async def superadmin_delete_template(template_id: int, request: Request):
    # TODO: DELETE /api/io.bithead.scheduler/superadmin/template/{id}
    return {"success": True}


# ---------------------------------------------------------------------------
# MARK: Package lifecycle
# ---------------------------------------------------------------------------

def start():
    pass


def shutdown():
    pass
