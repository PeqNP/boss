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

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


# --- Records -------------------------------------------------------------

class Business(BaseModel):
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


class BusinessHours(BaseModel):
    dayOfWeek: int          # 0 = Sunday
    openTime: str
    closeTime: str
    isClosed: bool


class JobType(BaseModel):
    id: int
    businessId: int
    name: str
    minEmployees: int
    isActive: bool


class JobTypeSize(BaseModel):
    id: int
    jobTypeId: int
    name: str
    durationMinutes: int
    cost: float


class Employee(BaseModel):
    id: int
    businessId: int
    firstName: str
    lastName: str
    includeInSchedule: bool
    canManageOwnSchedule: bool


class EmployeeSchedule(BaseModel):
    id: int
    employeeId: int
    dayOfWeek: int          # 0 = Sunday
    startTime: str
    endTime: str


class EmployeeTimeOff(BaseModel):
    id: int
    employeeId: int
    date: str
    startTime: str
    endTime: str


# --- What the kiosk reads ------------------------------------------------

class Slot(BaseModel):
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
class Success(BaseModel):
    success: bool


class OperatingHour(BaseModel):
    dayOfWeek: int
    openTime: str
    closeTime: str
    isClosed: bool


#   GET /admin/config
class AdminConfig(BaseModel):
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
    operatingHours: List[OperatingHour] = []
    reminderEnabled: bool
    confirmBySms: bool
    confirmByEmail: bool
    completionMode: str
    allowCustomerEmployeeSelection: bool
    notifyEmployees: bool
    publicUrl: str


#   GET /admin/config/stripe/connect
class AdminConfigStripeConnect(BaseModel):
    connectUrl: str


class Template(BaseModel):
    id: int
    name: str
    description: str
    iconUrl: Optional[str] = None


#   GET /admin/config/templates
#   GET /superadmin/templates
class AdminConfigTemplates(BaseModel):
    templates: List[Template] = []


class Field(BaseModel):
    id: int
    name: str
    fieldType: str
    otpCapable: bool
    sortOrder: int


#   GET /admin/contact-fields
#   GET /superadmin/contact-fields
class AdminContactFields(BaseModel):
    fields: List[Field] = []


class AdminCustomerAppointment(BaseModel):
    id: int
    jobCode: str
    jobType: str
    scheduledDate: str
    displayDate: str
    displayTime: str
    status: str


class Note(BaseModel):
    id: int
    note: str
    createdBy: str
    date: str


#   GET /admin/customer/{customer_id}
class AdminCustomer(BaseModel):
    id: str
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


class Customer(BaseModel):
    id: int
    firstName: str
    lastName: str
    phone: str
    email: str
    hasBossAccount: bool


#   GET /admin/customers
class AdminCustomers(BaseModel):
    customers: List[Customer] = []


#   GET /admin/dashboard
class AdminDashboard(BaseModel):
    businessId: int
    slotMode: str
    jobsToday: int
    jobsThisWeek: int
    revenueThisMonth: float
    upcomingJobs: int
    unassignedJobs: int
    unassignedConflicts: int


class AdminEmployeeJobType(BaseModel):
    id: int
    name: str


class ScheduleTemplate(BaseModel):
    id: int
    dayOfWeek: int
    startTime: str
    endTime: str


class TimeOff(BaseModel):
    id: int
    date: str
    startTime: str
    endTime: str


#   GET /admin/employee/{employee_id}
class AdminEmployee(BaseModel):
    id: str
    userId: int
    firstName: str
    lastName: str
    includeInSchedule: bool
    canManageOwnSchedule: bool
    scheduleTemplate: List[ScheduleTemplate] = []
    timeOff: List[TimeOff] = []
    jobTypes: List[AdminEmployeeJobType] = []


#   GET /admin/employee/{employee_id}/time-off
class AdminEmployeeTimeOff(BaseModel):
    timeOff: List[TimeOff] = []


class AdminEmployeesEmployee(BaseModel):
    id: int
    firstName: str
    lastName: str
    includeInSchedule: bool


#   GET /admin/employees
class AdminEmployees(BaseModel):
    employees: List[AdminEmployeesEmployee] = []


class Holiday(BaseModel):
    id: int
    name: str
    date: str
    selected: bool


#   GET /admin/holidays
class AdminHolidays(BaseModel):
    year: str
    holidays: List[Holiday] = []


class Icon(BaseModel):
    id: int
    filename: str
    isSystem: bool
    url: str


#   GET /admin/icons
class AdminIcons(BaseModel):
    icons: List[Icon] = []


class AdminJobTypeEmployee(BaseModel):
    id: int
    firstName: str
    lastName: str


class Attribute(BaseModel):
    id: int
    name: str
    attributeType: str
    options: List[Any] = []
    isRequired: bool
    sortOrder: int


class ContactField(BaseModel):
    id: int
    contactFieldTypeId: int
    name: str
    fieldType: str
    isRequired: bool
    requireOtp: bool
    sortOrder: int


class JobTypeSizeDetail(BaseModel):
    id: int
    name: str
    durationMinutes: int
    cost: float
    sortOrder: int


#   GET /admin/job-type/{job_type_id}
class AdminJobType(BaseModel):
    id: str
    name: str
    iconId: Optional[int] = None
    minEmployees: int
    paymentRequired: bool
    depositRequired: bool
    depositType: Optional[str] = None
    depositAmount: Optional[float] = None
    depositNonrefundable: bool
    stripeProductId: Optional[int] = None
    stripePriceId: Optional[int] = None
    isActive: bool
    sizes: List[JobTypeSizeDetail] = []
    attributes: List[Attribute] = []
    contactFields: List[ContactField] = []
    employees: List[AdminJobTypeEmployee] = []


#   GET /admin/job-types
class AdminJobTypes(BaseModel):
    jobTypes: str


class AdminJobAttribute(BaseModel):
    name: str
    value: str


class AdminJobCustomer(BaseModel):
    id: int
    firstName: str
    lastName: str
    phone: str
    email: str
    addressLine1: str
    city: str
    state: str
    zip: str


class Size(BaseModel):
    id: int
    name: str
    durationMinutes: int
    cost: float


class Transaction(BaseModel):
    id: int
    amount: float
    method: str
    date: str
    collectedBy: str


#   GET /admin/job/{job_id}
class AdminJob(BaseModel):
    id: str
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
    transactions: List[Transaction] = []


#   GET /admin/job/{job_id}/payment-link
class AdminJobPaymentLink(BaseModel):
    jobId: int
    amount: float
    paymentLinkUrl: str
    jobCode: str


class AppointmentEmployee(BaseModel):
    firstName: str
    lastInitial: str


class Job(BaseModel):
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
class AdminJobs(BaseModel):
    jobs: List[Job] = []
    total: int


class AdminJobsUnassignedJob(BaseModel):
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
class AdminJobsUnassigned(BaseModel):
    jobs: List[AdminJobsUnassignedJob] = []


#   GET /admin/reports/financial
class AdminReportsFinancial(BaseModel):
    period: str
    year: str
    quarter: str
    selectedPeriod: str
    selectedYear: int
    selectedQuarter: str
    availableYears: str
    revenue: float
    depositsCollected: float
    writeOffs: float
    jobsCompleted: int
    jobsCancelled: int


class AdminScheduleDayJob(BaseModel):
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
class AdminScheduleDay(BaseModel):
    date: str
    jobs: List[AdminScheduleDayJob] = []


class Day(BaseModel):
    date: str
    jobCount: int


#   GET /admin/schedule/month
class AdminScheduleMonth(BaseModel):
    year: str
    month: str
    days: List[Day] = []


class AdminScheduleWeekDay(BaseModel):
    date: str
    displayDate: str
    jobs: List[Any] = []


#   GET /admin/schedule/week
class AdminScheduleWeek(BaseModel):
    weekStart: str
    days: List[AdminScheduleWeekDay] = []


class DefaultPrice(BaseModel):
    id: str
    unitAmount: int
    currency: str


class Product(BaseModel):
    id: str
    name: str
    defaultPrice: Optional[DefaultPrice] = None


#   GET /admin/stripe/products
class AdminStripeProducts(BaseModel):
    products: List[Product] = []


class AppointmentBusiness(BaseModel):
    name: str
    phone: str


#   GET /appointment/{appointment_id}
class AppointmentDetail(BaseModel):
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


class CustomerAppointmentsAppointment(BaseModel):
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
class CustomerAppointments(BaseModel):
    upcomingCount: int
    appointments: List[CustomerAppointmentsAppointment] = []


#   GET /employee/profile
class EmployeeProfile(BaseModel):
    employeeId: int
    firstName: str
    lastName: str
    canManageOwnSchedule: bool
    scheduleTemplate: List[ScheduleTemplate] = []
    timeOff: List[TimeOff] = []
    jobTypes: List[AdminEmployeeJobType] = []


class CoWorker(BaseModel):
    firstName: str
    lastName: str


class EmployeeTodayJobCustomer(BaseModel):
    firstName: str
    lastName: str
    phone: str
    addressLine1: str
    city: str
    state: str


class EmployeeTodayJob(BaseModel):
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
class EmployeeToday(BaseModel):
    date: str
    displayDate: str
    jobs: List[EmployeeTodayJob] = []
    canManageOwnSchedule: bool


#   GET /kiosk/{business_id}
class Kiosk(BaseModel):
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
    operatingHours: List[OperatingHour] = []
    configured: bool


#   GET /kiosk/{business_id}/calendar
class KioskCalendar(BaseModel):
    year: str
    month: str
    availableDays: List[Any] = []


class KioskDaySlotsSlot(BaseModel):
    time: str
    displayTime: str


#   GET /kiosk/{business_id}/day-slots
class KioskDaySlots(BaseModel):
    date: str
    slots: List[KioskDaySlotsSlot] = []


#   GET /kiosk/{business_id}/employees
class KioskEmployees(BaseModel):
    employees: List[AdminJobTypeEmployee] = []


class KioskJobTypesJobTypeAttribute(BaseModel):
    id: int
    name: str
    attributeType: str
    isRequired: bool


class KioskJobTypesJobTypeContactField(BaseModel):
    id: int
    name: str
    fieldType: str
    isRequired: bool
    requireOtp: bool


class KioskJobTypesJobType(BaseModel):
    id: int
    name: str
    iconUrl: Optional[str] = None
    sizes: List[Size] = []
    contactFields: List[KioskJobTypesJobTypeContactField] = []
    attributes: List[KioskJobTypesJobTypeAttribute] = []
    depositRequired: bool


#   GET /kiosk/{business_id}/job-types
class KioskJobTypes(BaseModel):
    jobTypes: List[KioskJobTypesJobType] = []


class KioskSlotsSlot(BaseModel):
    date: str
    time: str
    displayDate: str
    displayTime: str


#   GET /kiosk/{business_id}/slots
class KioskSlots(BaseModel):
    slots: List[KioskSlotsSlot] = []


#   GET /operator/me
class OperatorMe(BaseModel):
    isOperator: bool
    businessId: int


#   GET /superadmin/business/{business_id}
class SuperadminBusiness(BaseModel):
    id: str
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


class SuperadminBusinessesBusiness(BaseModel):
    id: int
    name: str
    ownerName: str
    isActive: bool
    createDate: str


#   GET /superadmin/businesses
class SuperadminBusinesses(BaseModel):
    businesses: List[SuperadminBusinessesBusiness] = []


class CountryHoliday(BaseModel):
    id: int
    name: str
    date: str


class Country(BaseModel):
    countryCode: str
    countryName: str
    holidays: List[CountryHoliday] = []


#   GET /superadmin/holidays
class SuperadminHolidays(BaseModel):
    year: str
    countries: List[Country] = []


#   GET /superadmin/holidays/years
class SuperadminHolidaysYears(BaseModel):
    years: List[Any] = []


#   GET /superadmin/timeout
class SuperadminTimeout(BaseModel):
    timeoutMinutes: int


class Config(BaseModel):
    fromEmail: str
    fromName: str


class Vendor(BaseModel):
    type: str
    currentVendor: str
    registeredVendors: List[Any] = []
    config: Optional[Config] = None


#   GET /superadmin/vendors
class SuperadminVendors(BaseModel):
    vendors: List[Vendor] = []


#   POST /admin/config/stripe/callback
class AdminConfigStripeCallback(BaseModel):
    stripeAccountId: str
    success: bool


#   POST /admin/customer/{customer_id}/notes
#   POST /admin/employee
#   POST /admin/job-type
#   POST /superadmin/businesses
#   … and 2 more
class Created(BaseModel):
    id: int


#   POST /admin/employee/{employee_id}/schedule
class AdminEmployeeSchedule(BaseModel):
    id: int
    dayOfWeek: int
    startTime: str
    endTime: str


#   POST /admin/employee/{employee_id}/time-off
class AdminEmployeeTimeOffPost(BaseModel):
    id: int
    date: str
    startTime: str
    endTime: str


#   POST /admin/icons
class AdminIconsPost(BaseModel):
    id: int
    url: str


#   POST /admin/job-type/{job_type_id}/attribute
class AdminJobTypeAttribute(BaseModel):
    id: int
    name: str
    attributeType: str
    options: List[Any] = []
    isRequired: bool
    sortOrder: int


#   POST /admin/job-type/{job_type_id}/contact-field
class AdminJobTypeContactField(BaseModel):
    id: int
    contactFieldTypeId: int
    name: str
    fieldType: str
    isRequired: bool
    requireOtp: bool
    sortOrder: int


#   POST /admin/job-type/{job_type_id}/size
class AdminJobTypeSize(BaseModel):
    id: int
    name: str
    durationMinutes: int
    cost: float
    sortOrder: int


#   POST /admin/job/{job_id}/payment
class AdminJobPayment(BaseModel):
    success: bool
    newPaymentStatus: str


#   POST /admin/jobs/assign
class AdminJobsAssign(BaseModel):
    assigned: int
    unassigned: int


#   POST /appointment/lookup
class AppointmentLookup(BaseModel):
    sentTo: str
    channel: str


#   POST /appointment/lookup/verify
class AppointmentLookupVerify(BaseModel):
    verified: bool
    appointmentId: int
    attemptsRemaining: int
    locked: bool
    businessPhone: str


class ConfirmationSentTo(BaseModel):
    sms: str
    email: Optional[str] = None


#   POST /kiosk/session/{session_id}/confirm
class KioskSessionConfirm(BaseModel):
    jobId: int
    jobCode: str
    stripePaymentUrl: Optional[str] = None
    confirmationSentTo: Optional[ConfirmationSentTo] = None


#   POST /kiosk/session/{session_id}/otp/send
class KioskSessionOtpSend(BaseModel):
    sent: bool


#   POST /kiosk/session/{session_id}/otp/verify
class KioskSessionOtpVerify(BaseModel):
    verified: bool
    attemptsRemaining: int


#   POST /kiosk/{business_id}/session
class KioskSession(BaseModel):
    sessionId: str
    jobId: int
    expiresAt: str
    timeoutMinutes: int


#   POST /signup
class Signup(BaseModel):
    businessId: int
    operatorId: int


#   POST /superadmin/holidays/refresh
class SuperadminHolidaysRefresh(BaseModel):
    success: bool
    count: int


#   PUT /admin/employee-schedule/{schedule_id}
class AdminEmployeeSchedulePut(BaseModel):
    id: str
    dayOfWeek: int
    startTime: str
    endTime: str


#   PUT /admin/employee-time-off/{window_id}
class AdminEmployeeTimeOffPut(BaseModel):
    id: str
    date: str
    startTime: str
    endTime: str


#   PUT /admin/job-type-attribute/{attribute_id}
class AdminJobTypeAttributePut(BaseModel):
    id: str
    name: str
    attributeType: str
    options: List[Any] = []
    isRequired: bool
    sortOrder: int


#   PUT /admin/job-type-contact-field/{contact_field_id}
class AdminJobTypeContactFieldPut(BaseModel):
    id: str
    contactFieldTypeId: int
    name: str
    fieldType: str
    isRequired: bool
    requireOtp: bool
    sortOrder: int


#   PUT /admin/job-type-size/{size_id}
class AdminJobTypeSizePut(BaseModel):
    id: str
    name: str
    durationMinutes: int
    cost: float
    sortOrder: int


#   PUT /kiosk/session/{session_id}/extend
class KioskSessionExtend(BaseModel):
    expiresAt: str


class ContactFieldType(BaseModel):
    id: int
    name: str
    fieldType: str
    otpCapable: bool
    sortOrder: int


class BusinessTemplate(BaseModel):
    id: int
    name: str
    description: str
    config: Dict[str, Any] = {}


class ConfirmationSent(BaseModel):
    """One channel a booking confirmation went out on, masked."""
    channel: str
    sentTo: str


class JobSession(BaseModel):
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
    confirmationSentTo: List[ConfirmationSent] = []


class Appointment(BaseModel):
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


class OtpResult(BaseModel):
    """What the kiosk shows after sending or checking a code."""
    verified: bool
    attemptsRemaining: int


class AccessCodeSent(BaseModel):
    """Where a verification code went, said in a way that confirms without telling.

    `sentTo` is masked: a customer who gave the right job code should recognise
    their own number, and someone who guessed it should learn nothing.
    """
    channel: str
    sentTo: str


class Recurrence(BaseModel):
    """A standing arrangement, from which appointments are made as time passes."""
    id: int
    businessId: int
    jobTypeId: int
    jobTypeSizeId: Optional[int] = None
    intervalType: str
    daysOfWeek: List[int] = []
    preferredTime: str
    isActive: bool


class RecurringJob(BaseModel):
    """One appointment a recurrence produced."""
    id: int
    jobCode: str
    scheduledDate: str
    scheduledTime: str
    status: str
    employeeIds: List[int] = []


class Payment(BaseModel):
    """One amount taken against an appointment."""
    id: int
    amount: float
    method: str
    date: str
    collectedBy: Optional[int] = None


class PaymentResult(BaseModel):
    """Where an appointment stands after money moved."""
    jobId: int
    paymentStatus: str
    paidTotal: float
    cost: float


class JobSearchResult(BaseModel):
    """One row of the operator's job search."""
    id: int
    jobCode: str
    jobTypeName: str
    scheduledDate: str
    scheduledTime: str
    displayDate: str
    displayTime: str
    status: str
    paymentStatus: str


class FinancialReport(BaseModel):
    """What a business took over a period, and what it gave up on."""
    year: int
    quarter: Optional[int] = None
    fromDate: str
    toDate: str
    revenue: float
    writeOffs: float
    jobCount: int


# --- Input models --------------------------------------------------------
#
# Request bodies. They are domain models: the client dictates their shape as
# surely as it dictates a response's.

class ContactValue(BaseModel):
    fieldId: int
    value: str


class AttributeValue(BaseModel):
    fieldId: int
    value: Any = None


class KioskSessionBody(BaseModel):
    jobTypeId: int
    sizeId: Optional[int] = None
    employeeId: Optional[int] = None
    scheduledDate: str
    scheduledTime: str


class OtpSendBody(BaseModel):
    fieldType: str


class OtpVerifyBody(BaseModel):
    code: str


class KioskConfirmBody(BaseModel):
    contactData: List[ContactValue] = []
    attributeData: List[AttributeValue] = []


class LookupBody(BaseModel):
    jobCode: str


class LookupVerifyBody(BaseModel):
    jobCode: str
    code: str


class RescheduleBody(BaseModel):
    scheduledDate: str
    scheduledTime: str


class JobTypeBody(BaseModel):
    name: str
    minEmployees: Optional[int] = None
    isActive: Optional[bool] = None


class JobTypeSizeBody(BaseModel):
    name: str
    durationMinutes: int
    cost: float
