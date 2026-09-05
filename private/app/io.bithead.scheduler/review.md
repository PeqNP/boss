# Scheduler — Review

Every stage of `plan.md` is finished and every flow of `ui-plan.md` has a spec.
What is left is gathered here, because it was spread across a checklist, a
numbered list of decisions, and the status column of a table — three places, and
none of them a list of work.

Each item says what it is waiting on. **Nothing here blocks the others.**

## Waiting on somebody outside this repo

An account, a credential, or a decision that is not the code's to make.

| | What exists | What is missing |
|---|---|---|
| Holidays for a year | `POST /system-holidays/refresh`, reporting the count already there, and the Holidays screen | `plan.md` Open Decision 1: which provider. `system_holidays` is written only by `close_on_holiday`, which no route exposes, so the table is empty and the screen has nothing to draw |
| A live Stripe / Twilio account | Mock vendors cover OTP and deposit in development. Production adapters are written. SMTP uses the BOSS account. | Platform keys on Vendors, and a connected Stripe account per business |

Vendor, Stripe, OTP, and deposit are [`plan-vendors.md`](plan-vendors.md). The four stubbed handlers are gone.

## Built on the server, missing from a screen

Nothing. Write-off has a route and a control on Job.

## Waiting on nothing

Nothing. Every flow in `ui-plan.md` is covered, and what each one leaves out is
waiting on something above.


## Carried from the build

Warnings that are reported rather than failed, and are worth a decision one way
or the other.

| | Count | Where |
|---|---|---|
| Comments saying why rather than what | 346 | `bin/check-comments` |
| Constants declared below the first function | 53 | `bin/check-format` |
| Storage calls in a test with no `lib` call yet | 27 | `bin/check-tests` |

## What is finished

Recorded so a reader does not go looking. Every Stage 5 endpoint group but the
ones above; all thirteen UI flows; every finding in `ui-plan.md` fixed; Open
Decisions 2, 5, 6 and 7 resolved.
