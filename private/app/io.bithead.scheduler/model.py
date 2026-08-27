#
# Scheduler — domain models
#
# What the app reasons about, and what the client receives. There is no third
# family for the wire: a domain model's shape is already dictated by the screen
# that reads it, so `lib.py` returns these and routes hand them straight to
# FastAPI.
#
# camelCase throughout, which is our convention. The storage shapes are
# `db.py`'s row models, and `lib.py` converts. A column rename is a storage
# decision and stops there; a label a screen wants is a presentation decision
# and never becomes a column.
#
# Dates are `YYYY-MM-DD` and times are `HH:MM`, both in the business's own
# timezone — a business opens at nine o'clock wherever it is.
#

from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, List, Optional


class Model(BaseModel):
    """Every model here, so a narrower one can be read off a wider one.

    `from_attributes` lets a model validate straight from another object's
    attributes. That is what makes one model buildable from another without
    naming every field:

        WorkingDay.model_validate(schedule, from_attributes=True)
        AdminEmployeeTimeOff(timeOff=lib.get_time_off(employee_id))

    The second is the one that matters — a narrow model nested inside an
    envelope accepts the wider model directly, so the comprehension that copied
    field for field is not needed.

    At the top level of a route it is needed even less: `response_model=` runs
    the same narrowing on whatever the handler returns, so a route returning a
    wider model gets the declared shape for free. Copy fields by hand only when
    the shapes genuinely differ — a flat model feeding a nested one, or a value
    the route computes.
    """
    model_config = ConfigDict(from_attributes=True)


# --- Records -------------------------------------------------------------

class Business(Model):
    id: int
    name: str
    phone: Optional[str] = None
    timezone: str
    # reserved | unlimited — whether choosing a time takes it from anyone else.
    slotMode: str
    slotIncrementMinutes: int
    cutoffDays: int
    minBookingNoticeHours: int
    minChangeNoticeMinutes: int
    bufferMinutes: int
    isActive: bool


class BusinessHours(Model):
    dayOfWeek: int          # 0 = Sunday
    openTime: str
    closeTime: str
    isClosed: bool


class JobType(Model):
    id: int
    businessId: int
    name: str
    minEmployees: int
    isActive: bool


class JobTypeSize(Model):
    id: int
    jobTypeId: int
    name: str
    durationMinutes: int
    cost: float
    sortOrder: int


class Employee(Model):
    id: int
    businessId: int
    firstName: str
    lastName: str
    includeInSchedule: bool
    canManageOwnSchedule: bool


class EmployeeSchedule(Model):
    id: int
    employeeId: int
    dayOfWeek: int          # 0 = Sunday
    startTime: str
    endTime: str


class EmployeeTimeOff(Model):
    id: int
    employeeId: int
    date: str
    startTime: str
    endTime: str


# --- What the kiosk reads ------------------------------------------------

class Slot(Model):
    """A time a customer may choose.

    `date` and `time` are what the booking is made against. `displayDate` is
    what the row reads, which the server decides — "ASAP" for a time inside the
    next increment, a written-out date otherwise — because working out which
    time counts as soon needs the clock and the business's increment, and
    neither belongs to the screen.
    """
    date: str
    time: str
    displayDate: str
    displayTime: str
    # Who would do the work. Empty under `unlimited`, where nobody is allocated.
    employeeIds: List[int] = []


# --- Responses -----------------------------------------------------------
#
# One per shape a route returns, and the nested shapes those hold. Named here
# in Stage 2 so Stage 4 has something to build against, and derived from the
# Stage 1 stub responses the controllers were written against — so a field a
# screen reads and a field a route sends are the same field, or the mismatch is
# reported rather than rendering blank.
#
# A screen's shape is not the domain record above: `JobTypeOption` is what a
# kiosk needs to draw a tile, and it is smaller than `JobType`. That is why
# both exist, and why a response model never takes a record's name.
#
# Several routes share a shape and share the model: 31 write routes answer
# `Success` and six answer `Created`. The comments above each model say which
# routes it serves.
#
# Types are what the stubs showed. A field the stub returned as `None` is
# optional; everything else is required.

#   DELETE /admin/customer/{customer_id}/note/{note_id}
#   DELETE /admin/employee-schedule/{schedule_id}
#   DELETE /admin/employee/{employee_id}
#   DELETE /admin/employee/{employee_id}/time-off/{window_id}
#   … and 27 more
class Success(Model):
    success: bool


#   GET /admin/config
#   GET /admin/config
#
# A business's settings, whole. The scheduling rules read `Business`, which is
# the handful of fields they need; this is what the owner is shown.
class BusinessConfig(Model):
    businessId: int
    name: str
    phone: str
    addressLine1: str
    addressLine2: str
    city: str
    state: str
    zip: str
    ownerName: str
    description: str
    siteUrl: str
    timezone: str
    slotIncrementMinutes: int
    cutoffDays: int
    minBookingNoticeHours: int
    minChangeNoticeMinutes: int
    bufferMinutes: int
    slotMode: str
    operatingHours: List[BusinessHours] = []
    reminderEnabled: bool
    confirmBySms: bool
    confirmByEmail: bool
    completionMode: str
    allowCustomerEmployeeSelection: bool
    notifyEmployees: bool
    publicUrl: str


#   GET /admin/config/stripe/connect
class AdminConfigStripeConnect(Model):
    connectUrl: str


#   GET /admin/config/templates
#   GET /superadmin/templates
#
# `BusinessTemplate` carries the settings the template fills in, which is what
# the Business Type tab applies. A second shape without them was declared here
# and never used.
class AdminConfigTemplates(Model):
    templates: List["BusinessTemplate"] = []


#   GET /admin/contact-fields
#   GET /superadmin/contact-fields
class AdminContactFields(Model):
    fields: List[ContactFieldType] = []


class AdminCustomerAppointment(Model):
    id: int
    jobCode: str
    jobType: str
    scheduledDate: str
    displayDate: str
    displayTime: str
    status: str


class Note(Model):
    id: int
    note: str
    createdBy: str
    date: str


#   GET /admin/customer/{customer_id}
class AdminCustomer(Model):
    id: int
    firstName: str
    lastName: str
    phone: str
    email: str
    addressLine1: str
    addressLine2: str
    city: str
    state: str
    zip: str
    hasBossAccount: bool
    notes: List[Note] = []
    appointments: List[AdminCustomerAppointment] = []


class Customer(Model):
    id: int
    firstName: str
    lastName: str
    phone: str
    email: str
    hasBossAccount: bool


#   GET /admin/customers
class AdminCustomers(Model):
    customers: List[Customer] = []


#   GET /admin/dashboard
class AdminDashboard(Model):
    businessId: int
    slotMode: str
    jobsToday: int
    jobsThisWeek: int
    revenueThisMonth: float
    upcomingJobs: int
    unassignedJobs: int
    unassignedConflicts: int


class AdminEmployeeJobType(Model):
    id: int
    name: str


class TimeOff(Model):
    id: int
    date: str
    startTime: str
    endTime: str


#   GET /admin/employee/{employee_id}
class AdminEmployee(Model):
    id: int
    # `null` until they are invited to BOSS.
    userId: Optional[int] = None
    firstName: str
    lastName: str
    includeInSchedule: bool
    canManageOwnSchedule: bool
    scheduleTemplate: List[WorkingDay] = []
    timeOff: List[TimeOff] = []
    jobTypes: List[AdminEmployeeJobType] = []


#   GET /admin/employee/{employee_id}/time-off
class AdminEmployeeTimeOff(Model):
    timeOff: List[TimeOff] = []


#   GET /admin/employees
class AdminEmployees(Model):
    employees: List[Employee] = []


class Holiday(Model):
    id: int
    name: str
    date: str
    selected: bool


#   GET /admin/holidays
class AdminHolidays(Model):
    year: int
    holidays: List[Holiday] = []


class Icon(Model):
    id: int
    filename: str
    isSystem: bool
    url: str


#   GET /admin/icons
class AdminIcons(Model):
    icons: List[Icon] = []


class AdminJobTypeEmployee(Model):
    id: int
    firstName: str
    lastName: str


class JobTypeSizeDetail(Model):
    id: int
    name: str
    durationMinutes: int
    cost: float
    sortOrder: int


#   GET /admin/job-type/{job_type_id}
class AdminJobType(Model):
    id: int
    name: str
    iconId: Optional[int] = None
    minEmployees: int
    paymentRequired: bool
    depositRequired: bool
    depositType: Optional[str] = None
    depositAmount: Optional[float] = None
    depositNonrefundable: bool
    # Stripe's own ids, which are strings: `prod_...`, `price_...`.
    stripeProductId: Optional[str] = None
    stripePriceId: Optional[str] = None
    isActive: bool
    sizes: List[JobTypeSizeDetail] = []
    attributes: List[JobTypeAttribute] = []
    contactFields: List[JobTypeContactField] = []
    employees: List[AdminJobTypeEmployee] = []


#   GET /admin/job-types
class JobTypeOption(Model):
    """A job type as a list or a menu reads it."""
    id: int
    name: str
    minEmployees: int
    isActive: bool


class AdminJobTypes(Model):
    jobTypes: List[JobTypeOption] = []


class AdminJobAttribute(Model):
    name: str
    value: str


class AdminJobCustomer(Model):
    id: int
    firstName: str
    lastName: str
    phone: str
    email: str
    addressLine1: str
    city: str
    state: str
    zip: str


class Size(Model):
    id: int
    name: str
    durationMinutes: int
    cost: float


#   GET /admin/job/{job_id}
class AdminJob(Model):
    id: int
    jobCode: str
    jobType: Optional[AdminEmployeeJobType] = None
    size: Optional[Size] = None
    scheduledDate: str
    scheduledTime: str
    durationMinutes: int
    status: str
    paymentStatus: str
    locked: bool
    failedCodeAttempts: int
    isRecurring: bool
    employees: List[AdminJobTypeEmployee] = []
    customer: Optional[AdminJobCustomer] = None
    attributes: List[AdminJobAttribute] = []
    transactions: List[Payment] = []


#   GET /admin/job/{job_id}/payment-link
class AdminJobPaymentLink(Model):
    jobId: int
    amount: float
    paymentLinkUrl: str
    jobCode: str


class AppointmentEmployee(Model):
    firstName: str
    lastInitial: str


class Job(Model):
    id: int
    jobCode: str
    jobType: str
    customerName: str
    scheduledDate: str
    scheduledTime: str
    displayDate: str
    displayTime: str
    status: str
    paymentStatus: str
    employees: List[AppointmentEmployee] = []


#   GET /admin/jobs
class AdminJobs(Model):
    jobs: List[Job] = []
    total: int


class AdminJobsUnassignedJob(Model):
    id: int
    jobCode: str
    jobType: str
    customerName: str
    scheduledDate: str
    scheduledTime: str
    displayDate: str
    displayTime: str
    isRecurring: bool


#   GET /admin/jobs/unassigned
class AdminJobsUnassigned(Model):
    jobs: List[AdminJobsUnassignedJob] = []


class AdminScheduleDayJob(Model):
    id: int
    jobCode: str
    jobType: str
    customerName: str
    startTime: str
    endTime: str
    startMinuteOffset: int
    durationMinutes: int
    employees: List[AppointmentEmployee] = []
    overlapColumn: int
    overlapTotal: int
    status: str
    paymentStatus: str


#   GET /admin/schedule/day
class AdminScheduleDay(Model):
    date: str
    jobs: List[AdminScheduleDayJob] = []


class Day(Model):
    date: str
    jobCount: int


#   GET /admin/schedule/month
class AdminScheduleMonth(Model):
    year: int
    month: int
    days: List[Day] = []


class AdminScheduleWeekJob(Model):
    """One appointment in a week column, which is narrow.

    The crew arrives as initials rather than as names: a column holds a few
    characters, and `AK, BT` is what fits.
    """
    id: int
    jobCode: str
    jobType: str
    startTime: str
    endTime: str
    employeeInitials: List[str] = []
    status: str


class AdminScheduleWeekDay(Model):
    date: str
    displayDate: str
    jobs: List[AdminScheduleWeekJob] = []


#   GET /admin/schedule/week
class AdminScheduleWeek(Model):
    weekStart: str
    days: List[AdminScheduleWeekDay] = []


class DefaultPrice(Model):
    id: str
    unitAmount: int
    currency: str


class Product(Model):
    id: str
    name: str
    defaultPrice: Optional[DefaultPrice] = None


#   GET /admin/stripe/products
class AdminStripeProducts(Model):
    products: List[Product] = []


class AppointmentBusiness(Model):
    name: str
    phone: str


#   GET /appointment/{appointment_id}
class AppointmentDetail(Model):
    """`Appointment` as its screen reads it — nested, and keyed by what it draws.

    Not the domain record of the same idea further down: that one is flat and
    carries the rule about whether changes are still open. This is the shape
    the route returns.
    """
    id: int
    jobCode: str
    jobType: Optional[AdminEmployeeJobType] = None
    size: Optional[Size] = None
    scheduledDate: str
    scheduledTime: str
    displayDate: str
    displayTime: str
    businessId: int
    business: Optional[AppointmentBusiness] = None
    employees: List[AppointmentEmployee] = []
    status: str
    locked: bool
    changesClosed: bool


class CustomerAppointmentsAppointment(Model):
    id: int
    jobCode: str
    business: str
    jobType: str
    scheduledDate: str
    scheduledTime: str
    displayDate: str
    displayTime: str
    employees: List[AppointmentEmployee] = []
    status: str


#   GET /customer/appointments
class CustomerAppointments(Model):
    upcomingCount: int
    appointments: List[CustomerAppointmentsAppointment] = []


#   GET /employee/profile
class EmployeeProfile(Model):
    employeeId: int
    firstName: str
    lastName: str
    canManageOwnSchedule: bool
    scheduleTemplate: List[WorkingDay] = []
    timeOff: List[TimeOff] = []
    jobTypes: List[AdminEmployeeJobType] = []


class CoWorker(Model):
    firstName: str
    lastName: str


class EmployeeTodayJobCustomer(Model):
    firstName: str
    lastName: str
    phone: str
    addressLine1: str
    city: str
    state: str


class EmployeeTodayJob(Model):
    id: int
    jobCode: str
    jobType: str
    startTime: str
    endTime: str
    displayTime: str
    customer: Optional[EmployeeTodayJobCustomer] = None
    coWorkers: List[CoWorker] = []
    attributes: List[AdminJobAttribute] = []
    status: str


#   GET /employee/today
class EmployeeToday(Model):
    date: str
    displayDate: str
    jobs: List[EmployeeTodayJob] = []
    canManageOwnSchedule: bool


#   GET /kiosk/{business_id}
class Kiosk(Model):
    businessId: int
    name: str
    phone: str
    description: str
    slotIncrementMinutes: int
    cutoffDays: int
    minBookingNoticeHours: int
    minChangeNoticeMinutes: int
    allowCustomerEmployeeSelection: bool
    scheduleTimeoutMinutes: int
    slotMode: str
    operatingHours: List[BusinessHours] = []
    configured: bool


#   GET /kiosk/{business_id}/calendar
class KioskCalendar(Model):
    year: int
    month: int
    availableDays: List[int] = []


class KioskDaySlotsSlot(Model):
    time: str
    displayTime: str


#   GET /kiosk/{business_id}/day-slots
class KioskDaySlots(Model):
    date: str
    slots: List[KioskDaySlotsSlot] = []


#   GET /kiosk/{business_id}/employees
class KioskEmployees(Model):
    employees: List[AdminJobTypeEmployee] = []


class KioskJobTypesJobTypeAttribute(Model):
    id: int
    name: str
    attributeType: str
    isRequired: bool


class KioskJobTypesJobTypeContactField(Model):
    id: int
    name: str
    fieldType: str
    isRequired: bool
    requireOtp: bool


class KioskJobTypesJobType(Model):
    id: int
    name: str
    iconUrl: Optional[str] = None
    sizes: List[Size] = []
    contactFields: List[KioskJobTypesJobTypeContactField] = []
    attributes: List[KioskJobTypesJobTypeAttribute] = []
    depositRequired: bool


#   GET /kiosk/{business_id}/job-types
class KioskJobTypes(Model):
    jobTypes: List[KioskJobTypesJobType] = []


class KioskSlot(Model):
    date: str
    time: str
    displayDate: str
    displayTime: str


#   GET /kiosk/{business_id}/slots
class KioskSlots(Model):
    slots: List[KioskSlot] = []


#   GET /operator/me
class OperatorMe(Model):
    isOperator: bool
    businessId: int


#   GET /superadmin/business/{business_id}
class SuperadminBusiness(Model):
    id: int
    name: str
    ownerName: str
    phone: str
    addressLine1: str
    city: str
    state: str
    zip: str
    timezone: str
    isActive: bool
    createDate: str


class SuperadminBusinessesBusiness(Model):
    id: int
    name: str
    ownerName: str
    isActive: bool
    createDate: str


#   GET /superadmin/businesses
class SuperadminBusinesses(Model):
    businesses: List[SuperadminBusinessesBusiness] = []


class CountryHoliday(Model):
    id: int
    name: str
    date: str


class Country(Model):
    countryCode: str
    countryName: str
    holidays: List[CountryHoliday] = []


#   GET /superadmin/holidays
class SuperadminHolidays(Model):
    year: int
    countries: List[Country] = []


#   GET /superadmin/holidays/years
class SuperadminHolidaysYears(Model):
    years: List[int] = []


#   GET /superadmin/timeout
class SuperadminTimeout(Model):
    timeoutMinutes: int


class Config(Model):
    fromEmail: str
    fromName: str


class Vendor(Model):
    type: str
    currentVendor: str
    registeredVendors: List[Any] = []
    config: Optional[Config] = None


#   GET /superadmin/vendors
class SuperadminVendors(Model):
    vendors: List[Vendor] = []


#   POST /admin/config/stripe/callback
class AdminConfigStripeCallback(Model):
    stripeAccountId: str
    success: bool


#   POST /admin/customer/{customer_id}/notes
#   POST /admin/employee
#   POST /admin/job-type
#   POST /superadmin/businesses
#   … and 2 more
class Created(Model):
    id: int


#   POST /admin/employee/{employee_id}/schedule
class WorkingDay(Model):
    id: int
    dayOfWeek: int
    startTime: str
    endTime: str


#   POST /admin/employee/{employee_id}/time-off


#   POST /admin/icons
class AdminIconsPost(Model):
    id: int
    url: str


#   POST /admin/job-type/{job_type_id}/attribute
class JobTypeAttribute(Model):
    id: int
    name: str
    attributeType: str
    options: List[Any] = []
    isRequired: bool
    sortOrder: int


#   POST /admin/job-type/{job_type_id}/contact-field
class JobTypeContactField(Model):
    id: int
    contactFieldTypeId: int
    name: str
    fieldType: str
    isRequired: bool
    requireOtp: bool
    sortOrder: int


#   POST /admin/job-type/{job_type_id}/size


#   POST /admin/job/{job_id}/payment
class AdminJobPayment(Model):
    success: bool
    newPaymentStatus: str


#   POST /admin/jobs/assign
class AdminJobsAssign(Model):
    assigned: int
    unassigned: int


#   POST /appointment/lookup
class Delivery(Model):
    sentTo: str
    channel: str


#   POST /appointment/lookup/verify
class AppointmentLookupVerify(Model):
    verified: bool
    # Absent on a wrong code: nothing was opened, so there is nothing to name.
    appointmentId: Optional[int] = None
    attemptsRemaining: Optional[int] = None
    locked: bool = False
    businessPhone: Optional[str] = None


class ConfirmationSentTo(Model):
    sms: str
    email: Optional[str] = None


#   POST /kiosk/session/{session_id}/confirm
class KioskSessionConfirm(Model):
    jobId: int
    jobCode: str
    stripePaymentUrl: Optional[str] = None
    confirmationSentTo: Optional[ConfirmationSentTo] = None


#   POST /kiosk/session/{session_id}/otp/send
class KioskSessionOtpSend(Model):
    sent: bool


#   POST /kiosk/session/{session_id}/otp/verify
class OtpResult(Model):
    verified: bool
    attemptsRemaining: int


#   POST /kiosk/{business_id}/session
class KioskSession(Model):
    sessionId: str
    jobId: int
    expiresAt: str
    timeoutMinutes: int


#   POST /signup
class Signup(Model):
    businessId: int
    operatorId: int


#   POST /superadmin/holidays/refresh
class SuperadminHolidaysRefresh(Model):
    success: bool
    count: int


#   PUT /admin/employee-schedule/{schedule_id}


#   PUT /admin/employee-time-off/{window_id}


#   PUT /admin/job-type-attribute/{attribute_id}


#   PUT /admin/job-type-contact-field/{contact_field_id}


#   PUT /admin/job-type-size/{size_id}


#   PUT /kiosk/session/{session_id}/extend
class KioskSessionExtend(Model):
    expiresAt: str


class ContactFieldType(Model):
    id: int
    name: str
    fieldType: str
    otpCapable: bool
    sortOrder: int


class BusinessTemplate(Model):
    id: int
    name: str
    description: str
    config: Dict[str, Any] = {}


class JobSession(Model):
    """A customer's hold on a time while they finish scheduling.

    The hold is what stops two customers taking the same time under
    `reserved`. It lapses on its own; nothing has to release it.
    """
    sessionToken: str
    jobId: int
    jobCode: str
    scheduledDate: str
    scheduledTime: str
    # ISO 8601 UTC. The client counts down to this and asks to extend.
    expiresAt: str
    employeeIds: List[int] = []
    # Where the booking confirmation went, once confirmed. Empty means nothing
    # was sent, and the kiosk tells the customer to keep their job code.
    confirmationSentTo: List[Delivery] = []


class Appointment(Model):
    """A booking, as the customer who made it sees it.

    `changesClosed` is the server's answer to whether this customer may still
    move or cancel it. Decided here rather than by the client, which would be
    trusting its own clock about a rule that is the business's.
    """
    id: int
    jobCode: str
    businessId: int
    businessName: str
    businessPhone: Optional[str] = None
    jobTypeId: int
    jobTypeName: str
    sizeId: Optional[int] = None
    sizeName: Optional[str] = None
    cost: Optional[float] = None
    scheduledDate: str
    scheduledTime: str
    displayDate: str
    displayTime: str
    durationMinutes: int
    status: str
    changesClosed: bool
    # Locked to the customer for good, after too many wrong codes. The
    # business still changes it from the admin screens.
    locked: bool = False
    employees: List[str] = []




class Recurrence(Model):
    """A standing arrangement, from which appointments are made as time passes."""
    id: int
    businessId: int
    jobTypeId: int
    jobTypeSizeId: Optional[int] = None
    intervalType: str
    daysOfWeek: List[int] = []
    preferredTime: str
    isActive: bool


class RecurringJob(Model):
    """One appointment a recurrence produced."""
    id: int
    jobCode: str
    scheduledDate: str
    scheduledTime: str
    status: str
    employeeIds: List[int] = []


class Payment(Model):
    """One amount taken against an appointment."""
    id: int
    amount: float
    method: str
    date: str
    collectedBy: Optional[int] = None


class PaymentResult(Model):
    """Where an appointment stands after money moved."""
    jobId: int
    paymentStatus: str
    paidTotal: float
    cost: float


#   GET /admin/reports/financial
class FinancialReport(Model):
    """What a business took over a period, and what it gave up on."""
    # `quarter` or `year`, which is what decides whether the quarter menu shows.
    period: str
    year: int
    quarter: Optional[int] = None
    fromDate: str
    toDate: str
    # The years the screen offers to choose between.
    availableYears: List[int] = []
    revenue: float
    # Held against work still to come, so it is named apart from revenue.
    depositsCollected: float
    writeOffs: float
    jobsCompleted: int
    jobsCancelled: int


# --- Input models --------------------------------------------------------
#
# Request bodies. They are domain models: the client dictates their shape as
# surely as it dictates a response's.

class ContactValue(Model):
    fieldId: int
    value: str


class AttributeValue(Model):
    fieldId: int
    value: Any = None


class KioskSessionBody(Model):
    jobTypeId: int
    sizeId: Optional[int] = None
    employeeId: Optional[int] = None
    scheduledDate: str
    scheduledTime: str


class OtpSendBody(Model):
    fieldType: str


class OtpVerifyBody(Model):
    code: str


class KioskConfirmBody(Model):
    contactData: List[ContactValue] = []
    attributeData: List[AttributeValue] = []


class LookupBody(Model):
    jobCode: str


class LookupVerifyBody(Model):
    jobCode: str
    code: str


class RescheduleBody(Model):
    scheduledDate: str
    scheduledTime: str


class JobTypeBody(Model):
    name: str
    minEmployees: Optional[int] = None
    isActive: Optional[bool] = None


class JobTypeSizeBody(Model):
    name: str
    durationMinutes: int
    cost: float


class EmployeeBody(Model):
    firstName: str
    lastName: str
    includeInSchedule: Optional[bool] = None
    canManageOwnSchedule: Optional[bool] = None
    jobTypeIds: Optional[List[int]] = None


class WorkingDayBody(Model):
    dayOfWeek: int
    startTime: str
    endTime: str


class TimeOffBody(Model):
    date: str
    startTime: str
    endTime: str


class SetupTask(Model):
    text: str                       # what is missing, in the operator's words
    controller: str                 # where it is fixed
    section: Optional[str] = None   # which page of it, for a window with pages
    done: bool = False              # whether this one is already satisfied


class SetupResponse(Model):
    configured: bool
    tasks: List[SetupTask]


class BusinessConfigBody(Model):
    """One save from Business Settings.

    Every field is optional: the window writes as the owner works, so a save is
    usually one field that just lost focus. Only what is present is written —
    `None` and absent mean the same thing, which is why no field here is
    nullable.
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    ownerName: Optional[str] = None
    description: Optional[str] = None
    siteUrl: Optional[str] = None
    timezone: Optional[str] = None
    slotIncrementMinutes: Optional[int] = None
    cutoffDays: Optional[int] = None
    minBookingNoticeHours: Optional[int] = None
    minChangeNoticeMinutes: Optional[int] = None
    bufferMinutes: Optional[int] = None
    slotMode: Optional[str] = None
    operatingHours: Optional[List[BusinessHours]] = None
    reminderEnabled: Optional[bool] = None
    confirmBySms: Optional[bool] = None
    confirmByEmail: Optional[bool] = None
    completionMode: Optional[str] = None
    allowCustomerEmployeeSelection: Optional[bool] = None
    notifyEmployees: Optional[bool] = None


class HolidaysBody(Model):
    """Which of a year's holidays the business closes on.

    The whole year's choice, every save — a holiday absent from the list is one
    that was unticked.
    """
    year: int
    holidayIds: List[int] = []


class CustomerBody(Model):
    """Contact details from the Customer form.

    Optional throughout: the form saves the fields it has, and an absent one is
    a field nobody touched.
    """
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class NoteBody(Model):
    note: str


class JobTypeAttributeBody(Model):
    """One of the questions a job type asks at booking."""
    name: str
    attributeType: str
    options: List[Any] = []
    isRequired: bool = False


class PaymentBody(Model):
    amount: float
    method: str
    note: Optional[str] = None


#   POST /reconcile
class Reconciled(Model):
    """How many customer records a signed-in user just claimed.

    Usually 0, which is the point: the app calls this every time it loads.
    """
    claimed: int


#   POST /admin/job-type/{job_type_id}/contact-fields/reorder
class JobTypeContactFields(Model):
    contactFields: List[JobTypeContactField] = []


class ContactFieldBody(Model):
    """One detail a job type asks the customer for."""
    contactFieldTypeId: int
    isRequired: bool = True
    requireOtp: bool = False


class ReorderBody(Model):
    """The whole order, as the screen now shows it."""
    ids: List[int] = []


class JobTypeDraftBody(Model):
    """The placeholder name the form opens with."""
    name: str


class AssignBody(Model):
    """The appointments the operator ticked."""
    jobIds: List[int] = []


class EmployeeProfileBody(Model):
    """The work an employee says they take."""
    jobTypeIds: List[int] = []


class ContactFieldTypeBody(Model):
    """One kind of detail every business may ask a customer for."""
    name: str
    fieldType: str
    otpCapable: bool = False


class PlatformBusinessBody(Model):
    """A business record from the platform side.

    Optional throughout, as the operator's own settings body is: the form
    sends what it has, and an absent field is one nobody touched.
    """
    name: Optional[str] = None
    ownerName: Optional[str] = None
    phone: Optional[str] = None
    addressLine1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    timezone: Optional[str] = None
