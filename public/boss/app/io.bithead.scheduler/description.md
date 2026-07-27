# Scheduler

Scheduler is a multi-tenant SaaS scheduling platform for service businesses. It allows business operators to manage employees, job types, and appointments, while providing customers with a public-facing booking flow.

## Key Surfaces

- **Kiosk** — A full-screen, public-facing scheduling flow. Customers select a job type, choose a date/time, provide contact info, and confirm their appointment. The kiosk runs in a browser and hides all BOSS OS chrome. It is accessed via a universal link (`https://bithead.io/a/scheduler/{businessId}`).
- **Operator Admin** — A BOSS desktop app for business operators to manage their schedule (month/week/day calendar), employees, job types, customers, and financial reports.
- **Employee Portal** — A read-only BOSS desktop app for employees to view their daily, weekly, and monthly schedule and job details.
- **Customer Portal** — A BOSS desktop view for registered customers to view upcoming appointments and cancel or reschedule.
- **Super Admin** — A restricted panel for platform administrators to manage all businesses, system contact field types, holidays, vendor integrations, schedule timeout, and business templates.

## Motivation

Most scheduling SaaS products are generic and hard to white-label. Scheduler is designed as a first-class BOSS application — it follows the same UI conventions as the rest of the platform, integrates with the BOSS authentication system, and provides a kiosk mode that makes it invisible as a software product to the customer.
