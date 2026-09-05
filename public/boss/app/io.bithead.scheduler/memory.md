# Session Memory — Scheduler

Every stage of `plan.md` is finished. Mock vendors are offered only when `env` is `dev`. US holidays fill from `python-holidays` when a year is empty.

## Watch out for

- An operator finds a staff account through `GET .../business/{id}/users?email=`. Python asks `POST /private/users`. `/account/users` still answers only the caller, or everyone if they are the super admin.
- Write-off is `POST .../job/{id}/write-off`. The button sits with Record Payment and asks before it sends.
- Appointment mail, SMS, and card charges go through `lib/vendor/`. The catalog is code; the choice and credentials are stored in `vendor_configs`. SMTP hands mail to `POST /private/smtp/send`.
- Development records messages for `/debug/last-message`. A mock payment is `GET /debug/pay/{jobId}`.

## Open

- Live Stripe and Twilio keys on Vendors, and a connected Stripe account per business. Mock covers OTP and deposit in development. SMTP uses the BOSS account.
