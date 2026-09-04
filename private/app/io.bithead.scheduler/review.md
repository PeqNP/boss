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
| SMS delivery | `POST /private/vendor/sms/send`, the `Vendor` protocol, and a registry keyed by channel | A carrier account, and a `Vendor` for it. `VendorRegistry.vendors["sms"]` is an empty list |
| Stripe product link on a job type | `GET /business/{id}/stripe/products`, answering `# TODO` | An account, and `stripe_client.py`, which the plan's file layout names and which does not exist |
| Stripe Connect | `GET .../config/stripe/connect` and `.../callback`, answering `?stub=true` and `acct_stub_001` | The same account |
| A payment link on a job | `GET .../job/{id}/payment-link`, answering `https://buy.stripe.com/test_stub_link` | The same account |
| The Stripe webhook | Nothing | `plan.md` Open Decision 4: whether it lands on the Python service through a public proxy rule, or on the Swift server which then calls Python |
| Holidays for a year | `POST /system-holidays/refresh`, reporting the count already seeded | `plan.md` Open Decision 1: which provider |
| The kiosk's OTP step | The whole flow, and `lib/notify.py` recording what would have been sent | An SMS or email vendor. `get_setup` adds "Connect a way to send codes" for a job type that verifies a contact detail, so until one is registered `configured` is false and the kiosk draws `step-not-configured` rather than taking a booking |
| The kiosk's deposit step | The whole flow, and `step-deposit` | A Stripe account. `get_setup` adds "Connect Stripe" for a job type that takes a payment, with the same consequence |

The four stubbed handlers are the only ones in the service that reach no rule.

## Built on the server, missing from a screen

| | What exists | What is missing |
|---|---|---|
| Linking a BOSS account to an employee | `PUT /business/{id}/employee/{id}/account`, wired and tested, and `/account/users` to pick from | The control. `plan.md` § 1.2 says the Employee screen carries a "linked BOSS account (user search)". It does not, so an operator cannot give an employee access to the app |
| Writing off a balance | `lib.write_off_payment`, written and tested | A route, and a control. Nothing calls it, so `payment_status` never becomes `written_off` and the Financial Report's Write-Offs figure can only read $0.00 |

## Waiting on nothing

Behaviour with no spec covering it. Every one is reachable today, and each is
recorded against the flow it belongs to in `ui-plan.md`.

| Flow | Uncovered |
|---|---|
| 4 | Deleting a size, an attribute, or a contact field |
| 5 | Deleting a working day or a time-off window |
| 10 | A customer with a BOSS account, whose details are read-only |
| 12 | Working days and time off edited from the portal |
| 13 | Holidays, and editing a vendor |

The rules behind each are settled in `private/tests/test_scheduler.py`. What is
missing is the screen: that the control reaches the route, and that what comes
back is drawn.

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
