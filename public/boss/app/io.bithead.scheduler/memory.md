# Session Memory — Scheduler

Every stage of `plan.md` is finished. Leftovers are in [`review.md`](../../../../private/app/io.bithead.scheduler/review.md). Next: write-off — `lib.write_off_payment` exists; it needs a route and a control on Job.

## Watch out for

- An operator finds a staff account through `GET .../business/{id}/users?email=`. Python asks `POST /private/users`. `/account/users` still answers only the caller, or everyone if they are the super admin.
- `GET .../employee/{id}` returns `userId` and `account` (`id` + email) for the picker.
- Linking is `PUT .../employee/{id}/account`, not the employee save.

## Open

See `review.md`. Write-off. Vendor, Stripe, and holidays wait on accounts.
