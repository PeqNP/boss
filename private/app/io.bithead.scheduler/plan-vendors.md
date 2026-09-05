# Scheduler — Vendors

The original [`plan.md`](plan.md) is finished. This is the contract for taking
email, SMS, and payment out of Swift and into this app, so a UI test can walk
OTP and deposit without a carrier account.

## Identity

- **Bundle ID:** `io.bithead.scheduler`
- **Backend:** Python. The SMTP catalog choice hands appointment mail to
  Swift on `POST /private/smtp/send`, which uses `boss.config.smtp`.
  Mailtrap sends from Python. SMS and card charges stay in this app.
- **Public:** `public/boss/app/io.bithead.scheduler/controller/Vendors.html`,
  `BusinessConfig.html` (Payment tab), kiosk deposit and OTP steps
- **Private:** `private/app/io.bithead.scheduler/lib/vendor/`
- **Test:** `private/tests/test_scheduler.py` (vendor groups),
  `uitest/tests/scheduler-platform.spec.js`, `scheduler-kiosk.spec.js`
- **Replaces:** `server/web/Sources/App/Routes/Private/Vendor.swift`,
  `POST /private/vendor/{channel}/send`, `lib.server.send_message` as the
  delivery path

## Roles & Access

| Actor | Told by | Scope | Reaches | Narrowed by |
|---|---|---|---|---|
| Super admin | BOSS user id 1 | the platform | which vendor each channel uses, and its credentials | — |
| Operator | `employees.role = operator` | the one they run | Connect Stripe for that business; products and payment links of it | `stripe_account_id` on the business |
| Customer | no account | named in the path | OTP and deposit on the kiosk | a configured vendor, and a job type that asks for one |
| UI test | development sender / mock payment | the same as a customer | OTP codes via `/debug/last-message`; a paid deposit via `/debug/pay/{jobId}` | `debug.is_enabled()` |

### Who reaches each page

| Page | Reached by |
|---|---|
| `Vendors` | Super admin, Admin menu |
| `BusinessConfig` Payment | Operator |
| `SchedulerKiosk` `step-otp`, `step-deposit` | a customer on a job type that asks for them |

```
GET  /vendor/{channel}              -> ChannelVendors
    acl:   (super admin)
    who:   Super admin
    scope: require_admin

PUT  /vendor/{channel}              -> ChannelVendors
    acl:   (super admin)
    who:   Super admin
    scope: require_admin
    body:  VendorChoice (id + config)

GET  /business/{id}/stripe/products -> Products
    acl:   config.r
    who:   Operator
    scope: is_working_for_business

GET  /business/{id}/config/stripe/connect -> ConnectUrl
    acl:   config.w
    who:   Operator
    scope: is_working_for_business

GET  /business/{id}/config/stripe/callback -> ConfigStripeCallback
    acl:   config.w
    who:   Operator
    scope: is_working_for_business

GET  /business/{id}/job/{id}/payment-link -> JobPaymentLink
    acl:   job.r
    who:   Operator, Employee
    scope: is_working_for_business

POST /webhooks/payment              -> Success
    acl:   none (Stripe or the mock)
    who:   the payment vendor
    scope: signature (real) or debug (mock)
```

`GET /vendors` remains as the list the Vendors window loads in one go: one
`ChannelVendors` per channel. `GET /vendor/{channel}` is the same row.

## Deep-link routing

No new scheme. `Vendors` stays on the Admin menu. Setup tasks that name
`SuperAdminVendors` still open `Vendors`. Setup tasks that name Payment still
open `BusinessConfig` at `payment`.

## Stage 1 — UI/UX

### `Vendors`

A document. Super admin. One fieldset per channel (Email, SMS, Payment). Each
fieldset: a pop-up of that channel's vendors, then the fields the chosen
vendor declares. Fields are built with `os.ui.makeTextField` when the choice
changes. Secret fields use `type: password`. Saved values are never sent back;
a secret that already has a value shows a placeholder "unchanged" and an empty
submit leaves the stored value.

**No vendor** remains the first option. Saving it clears the channel.

`GET /vendor/{channel}` is the catalog. `PUT /vendor/{channel}` is the choice.

### `BusinessConfig` Payment

Connect is a button, not a field. It stays disabled until the platform has
chosen a payment vendor. Once connected, the tab shows the account id the
vendor returned.

### Kiosk

`step-otp` and `step-deposit` already exist. They become reachable when setup
is configured: an email or SMS vendor chosen, and a payment vendor plus a
connected business, respectively.

### Documents

`Vendors` stays a document (Cancel/Save; no Delete). Fieldsets are not
documents.

## Stage 2 — Data Model

The **catalog is code**, not rows. Hard-coded ids:

| Channel | Id | Name |
|---|---|---|
| email | `smtp` | SMTP |
| email | `mailtrap` | Mailtrap |
| sms | `twilio` | Twilio |
| payment | `stripe` | Stripe |

In development, each channel also offers `mock`. Production does not.

`vendor_configs` stores the choice: `vendor_name` is the id above,
`config_json` is the credentials the user typed. The catalog is not stored.
A row whose `vendor_name` is no longer in the catalog is treated as unchosen.

### Fields the catalog declares

Each field: `key`, `label`, `kind` (`text` / `password` / `number`),
`secret` (values never returned), optional `default`.

**smtp** — BOSS's own SMTP account. No fields. Swift sends.

**mailtrap** — SMTP to Mailtrap.

- `host` text, default `sandbox.smtp.mailtrap.io`
- `port` number, default `2525`
- `username` text
- `password` password, secret
- `fromEmail` text
- `fromName` text

**twilio**

- `accountSid` text
- `authToken` password, secret
- `fromNumber` text

**stripe** — platform keys. Connect still stores `businesses.stripe_account_id`.

- `secretKey` password, secret
- `publishableKey` text
- `webhookSecret` password, secret

**mock** — no fields.

### Network models

```
ChannelVendors
    channel: str
    chosen: str | null
    vendors: [VendorOffer]
    config: dict            # non-secret values of the chosen vendor
    configuredKeys: [str]   # stored keys, including secrets, never values

VendorOffer
    id: str
    name: str
    fields: [VendorField]

VendorField
    key: str
    label: str
    kind: str
    secret: bool
    default: str | null

VendorChoice
    id: str | null
    config: dict

EmailMessage     to, subject, body
SmsMessage       to, body
SendResult       sent: bool, reason: str

PaymentProduct   id, name, priceId, unitAmount, currency
JobCharge        businessId, jobId, amount, currency, returnUrl
PaymentNotice    jobId, amount, providerRef
```

The protocol takes these models. An adapter builds the vendor's wire format
from them. Callers never pass a Stripe-shaped dict.

## Stage 3 — TDD

### `test_vendor_catalog`

- `describe: email` → offers `smtp` and `mailtrap`; in development, `mock`
- `describe: payment` → offers `stripe`; in development, `mock`
- `describe: a channel the platform has none of` → refused
- `describe: secrets` → `GET` names keys and never values

### `test_vendor_choice`

- `describe: choose SMTP` → chosen is `smtp`, no config
- `describe: choose mailtrap with host and username` → chosen is `mailtrap`, keys listed
- `describe: save a secret then GET` → the value is not in the response
- `describe: save again with empty password` → the stored password is unchanged
- `describe: choose none` → chosen is null, sending is a no-op

### `test_email_send` / `test_sms_send`

- `describe: mock` → `SendResult.sent` is true, `last_sent` holds the message
- `describe: no vendor chosen` → `sent` is false and a reason, no exception
- `describe: SMTP` → asks Swift and never raises
- `describe: mailtrap with no password` → `sent` is false and a reason

### `test_payment_vendor`

- `describe: mock connect` → business has a `stripe_account_id`, setup task done
- `describe: mock products` → a non-empty list with ids
- `describe: mock payment link` → a URL under this app
- `describe: mock webhook` → `record_payment` with method `stripe`

### `test_setup_with_vendors`

- `describe: OTP job type, no email or SMS vendor` → `configured` is false
- `describe: OTP job type, mock email chosen` → that task is done
- `describe: paid job type, mock payment connected` → Connect Stripe is done

## Stage 4 — Backend Implementation

```
private/app/io.bithead.scheduler/lib/vendor/
    __init__.py     catalog, chosen vendor, dispatch send / payment
    protocol.py     EmailVendor, SmsVendor, PaymentVendor, domain models
    boss_smtp.py    SMTP catalog choice; POST /private/smtp/send
    mailtrap.py
    twilio.py
    stripe.py
    mock.py         development only
```

### Protocols

```python
class EmailVendor(Protocol):
    def send(self, message: EmailMessage) -> SendResult: ...

class SmsVendor(Protocol):
    def send(self, message: SmsMessage) -> SendResult: ...

class PaymentVendor(Protocol):
    def connect_url(self, business_id: int, return_url: str) -> str: ...
    def complete_connect(self, business_id: int, code: str) -> str: ...
    def products(self, business_id: int) -> list[PaymentProduct]: ...
    def payment_link(self, charge: JobCharge) -> str: ...
    def apply_webhook(self, payload: bytes, headers: dict) -> PaymentNotice | None: ...
```

`notify.send` asks the catalog for the chosen email or SMS adapter and calls
`send`. SMTP is the one hop to Swift: `POST /private/smtp/send`.

`start()` in development still records messages for `/debug/last-message`.
That is the mock email/SMS path for OTP in UI tests. The mock payment vendor
is chosen through Vendors (or seeded in test setup) and
`GET /debug/pay/{jobId}` completes a deposit.

### What leaves Swift

Delete `Vendor.swift`. Stop registering it from `PrivateRoute.swift`. Drop
`PrivateForm.SendMessage` if nothing else uses it. `lib.server.send_message`
stops calling `/private/vendor/{channel}/send`.

**Keep** Swift SMTP on account recovery and verify. The scheduler SMTP
vendor uses that same account for appointment mail. Mailtrap is a separate
account, configured on Vendors.

### Webhook

`POST /api/io.bithead.scheduler/webhooks/payment` is public. The payment
adapter verifies the signature. The mock accepts a debug POST with a job id
and records the payment. Open Decision 4 of `plan.md` is this: Python, not
Swift.

## Stage 5 — Integration

- Replace `_send_to_vendor` with catalog dispatch
- Replace Stripe stub handlers with `PaymentVendor` calls
- `get_setup` "Connect a way to send codes" is true when an email or SMS
  vendor is chosen; "Connect Stripe" is true when the payment vendor reports
  the business connected
- Seed: UI tests that need OTP choose mock SMS; those that need deposit
  choose mock payment and connect

## Stage 6 — Grouping

`lib/vendor/` is the group. `notify.py` stays the seam (`set_sender` for tests
that inject a lambda). Production `set_sender` is the catalog dispatcher.

## Stage 8 — UI tests

- `scheduler-platform.spec.js` — choose SMTP, save with no fields; choose
  Mailtrap, fill username, save; secrets absent from GET; fields appear
  when Stripe is selected
- `scheduler-kiosk.spec.js` — seed mock SMS, book a job type that verifies
  a phone, read `/debug/last-message`, type the code
- `scheduler-kiosk.spec.js` — seed mock payment, book a paid job type, follow
  or POST the mock pay URL, confirmation shows paid

## Open Decisions

1. **BOSS account mail stays on Swift SMTP.** Choosing SMTP for this app
   uses that same account for appointment mail. Mailtrap on Vendors is a
   separate account.
2. **Stripe Connect remains per business.** `businesses.stripe_account_id`
   is still what "connected" means.
