# Scheduler

A multi-tenant scheduling app for service businesses. Customers book from a public kiosk; operators run the business from the desktop.

## Who

| Actor | What they do |
|---|---|
| Super admin | Every business, holidays, vendors |
| Operator | One business: staff, job types, calendar, customers, money |
| Employee | Their own schedule; their working days and job types when allowed |
| Customer | Book, look up, change or cancel, without an account |

## What happens

A customer opens the kiosk from a public URL, picks a service and a time, and leaves a contact. They get a job code to come back. The first page they land on carries the business's tag line; a logo may hang to the left of the name. An operator opens the business, sets hours and job types, puts people on the schedule, takes payment, and on Theme sets how the kiosk looks — tag line, logo, and the type for each named part of the page. An employee sees the work assigned to them.

## Out of scope

A signed-in customer on the desktop. The kiosk is the whole customer surface. The kiosk's look does not change the BOSS desktop; unloading the kiosk restores Chicago and Geneva. Font licences for anything the operator uploads are theirs.
