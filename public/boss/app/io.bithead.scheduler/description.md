# Scheduler

A multi-tenant scheduling app for service businesses. Customers book from a public kiosk; operators run the business from the desktop.

## Who

| Actor | What they do |
|---|---|
| Super admin | Every business, holidays, vendors, templates, system contact fields |
| Operator | One business: staff, job types, calendar, customers, money |
| Employee | Their own schedule; their working days and job types when allowed |
| Customer | Book, look up, change or cancel, without an account |

## What happens

A customer opens the kiosk from a public URL, picks a service and a time, and leaves a contact. They get a job code to come back. An operator opens the business, sets hours and job types, puts people on the schedule, and takes payment. An employee sees the work assigned to them.

## Out of scope

A signed-in customer on the desktop. The kiosk is the whole customer surface.
