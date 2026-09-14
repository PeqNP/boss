# Session Memory — Scheduler

Day Queue Stage 3 is in: completing emits `job.changed` kind `completed`. Look at Queue while marking a job complete from another window. Stage 8 UI tests wait. Live job updates redraw the Dashboard and calendar when a job is booked, cancelled, moved, or completed. Mock vendors are offered only when `env` is `dev`. US holidays fill from `python-holidays` when a year is empty. Contact field types are code in `lib/contact_fields.py`. A customer has one `name`. Employees still have first and last name. A Stripe product, payment, and deposit are chosen on a job-type size; its price fills the size's cost and is snapshotted onto the job at hold. Verification is one flag on the job type. Confirmation channels live on the Notifications tab. Every stage of `plan.md` is finished. A kiosk Theme tab sets tag line, logo, and tokens via the BOSS font picker. Faces come from `GET /api/io.bithead.boss/fonts`. CSS variables on `.kiosk-page` clear when the kiosk unloads. Schema is 1.0.0.

## Watch out for

- An operator finds a staff account through `GET .../business/{id}/users?email=`. Python asks `POST /private/users`. `/account/users` still answers only the caller, or everyone if they are the super admin.
- Write-off is `POST .../job/{id}/write-off`. The button sits with Record Payment and asks before it sends.
- Appointment mail, SMS, and card charges go through `lib/vendor/`. The catalog is code; the choice and credentials are stored in `vendor_configs`. SMTP hands mail to `POST /private/smtp/send`.
- Development records messages for `/debug/last-message`. A mock payment is `GET /debug/pay/{jobId}`.

## Open

- Restart Python so `GET /fonts`, Theme `weight`, and a Connect return without a payment vendor land, and so 1.0.0 recreates without `business_fonts`. Hard-refresh so the leftover `?code=` is dropped. Then re-run `verify a phone` and `pay a deposit`. Agents do not start or restart the service.
