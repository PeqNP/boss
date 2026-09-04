# Session Memory — Scheduler

Every stage of `plan.md` is finished. Leftovers are in [`review.md`](../../../../private/app/io.bithead.scheduler/review.md).

The Employee screen has the BOSS account search. Next: how an operator finds an account. `/account/users` lists everyone for the super admin and only the caller for anyone else, so an operator cannot pick a staff account.

## Watch out for

- Linking is `PUT .../employee/{id}/account`, not the employee save. It grants the license and the employee role.
- Unlink sends `userId: null` and `previousUserId`.
- Paths: `public/boss/app/io.bithead.scheduler/controller/Employee.html`, `private/app/io.bithead.scheduler/review.md`

## Open

1. How an operator finds a BOSS account to link. The control is built; the picker has nothing to offer them.
2. Write-off still has no route or control. Vendor, Stripe, and holidays wait on accounts.
