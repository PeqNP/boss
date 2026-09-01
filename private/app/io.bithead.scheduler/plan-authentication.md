# Scheduler — Authentication & Authorization Plan

Companion to [`plan.md`](plan.md). That document says what the app does; this
one says who may do it, and records where the design stands.

Sections marked **Open** are unresolved and are the place to resume.

---

## Why this document exists

`plan.md` carries a Roles & Access table naming four roles and how each is
identified. Stage 1 then lists every controller with its endpoint signatures,
and the role never travels with them — so Stage 4 generated 106 routes with
nothing to derive a guard from.

The plan states, of a guest, that "every route in this app answers 401 for
them". That sentence was written as fact, and 36 routes answer 200.

The lesson is recorded in [`process.md`](../../../docs/prompt/process.md): a
plan names each page's audience, and each Stage 1 endpoint carries its ACL
name, its audience, and its scoping rule. Reviewing that list at the end of
Stage 1 is where a route serving two audiences is found, while it is still
three lines in a document.

---

## Where the routes stand

95 routes, by what protects them:

| Count | State |
|---|---|
| 68 | `@require_acl(...)` or `@require_admin()`, business in the path, query scoped |
| 5 | `@require_user()` — `/me`, `/my/*`, `/signup`, `/reconcile` |
| 22 | open by design — the kiosk, appointment lookup by code, `/operator/me`, `/contact-fields` |
| **0** | **reachable by anyone that should not be** |

### What it was

36 routes took a record id from the URL and asked nothing. Verified at the
time against the running dev service with no cookie and no header:

```
GET    /employee/1  ->  {"id":1,"firstName":"Rosa","lastName":"Alvarez", ...}
PUT    /employee/1  ->  {"success":true}      # renamed
DELETE /employee/1  ->  {"success":true}      # removed
```

Authentication was half the fix. A signed-in operator of one business would
still have reached another's records by trying ids, so each of the 36 got the
business in its path and its query scoped in the same edit.

Two more were found later, and were a different fault: `PUT
/business/{id}/job/{id}` and `GET /business/{id}/stripe/products` named
`boss_user: User` with no decorator to supply it, so FastAPI read it as
something to parse and answered 422 to everybody. Not open — dead.
`bin/check-routes` now reports that shape.

---

## What the ACL machinery already does

Established by reading the source.

**`require_acl(feature)` exists and enforces.**
[`server.py:385`](../../lib/server.py) registers the feature at import and calls
`verify_user(request, bundle_id, feature)`.

**Verification widens up the tree.**
[`acl+service.swift:165`](../../../server/bosslib/Sources/bosslib/API/acl/acl+service.swift)
tries each path in turn and returns on the first grant held:

```
python,io.bithead.scheduler,appointment,r
python,io.bithead.scheduler,appointment
python,io.bithead.scheduler
python
```

A grant at any level covers everything beneath it. Feature names allow one dot,
so the tree is `app -> feature -> permission`.

**Registration keeps ids for names that stay.** `saveAcl` finds or creates by
path, so an unchanged name keeps its id across a deploy. A renamed one is
deleted, and `deleteAcl` cascades:

```swift
delete from "acl"          where id in ids
delete from "acl_items"    where acl_id in ids    // every user's grant
delete from "app_licenses" where acl_id in ids    // every user's license
```

**Sessions survive a restart.** `user_sessions` is a table and a JWT is signed
and self-contained, so restarting either service leaves everyone signed in.

Together those two say what a rename does: sessions survive, the JWT carries
the old id, the id is gone, and the holder gets 403 while still appearing
signed in until they next sign in. **Names stay fixed once published** — the
same discipline that already applies to feature names.

**Grants live in the JWT, snapshotted at sign-in.**
[`account+service.swift:416`](../../../server/bosslib/Sources/bosslib/API/account/account+service.swift)
reads `userApps` and `userAcl` when minting. `verifyAccessToken` returns that
token rather than re-minting.

**An app license gates everything.** `verifyAccess` refuses a caller whose JWT
lacks the license before ACLs are consulted.

**Nothing grants an ACL or a license from Python.** No service-callable
endpoint, no helper in `lib/server.py`.

**`api.py` names each module after its bundle.**
[`api.py:40`](../../api.py) — a route's `__module__` is `io.bithead.scheduler`,
a rule's is `io.bithead.scheduler.lib`.

---

## Settled

**Vocabulary.** Super admin is the BOSS super user. Operator and business owner
are the same person. Employee is the person doing the work.

**A path names the resource; a decorator names who may reach it.** Done and
committed. `bin/check-routes` reports a handler that reached a guard in the
last commit and reaches none now, keyed on the function so a rename carries the
guard along.

**One business per email.** A user operates or works for exactly one business.
Opening a second business means a second BOSS account, as does working for a
second employer — which is how a company email already works in practice.

This is the decision the rest rests on. It makes a role a property of the
**user** rather than of a user-in-a-business, so BOSS's existing per-user grant
model fits with no changes to what a grant is.

**The business id is in the path, and checked.** An admin acts on a business
they are no member of, so an admin can derive nothing — and an admin has to
reach anything an operator needs help with, or there is no way to service them.

That makes one route set for both, with `is_working_for_business(business_id,
user)` deciding: true for the operator or employee of that business, true for
the super admin, false otherwise.

A caller naming the business is safe because the check reads it. The value the
caller supplies names the record; the check settles whether they may have it.

**Being a customer is separate, and many.** A user may be a customer of any
number of businesses under one email. `customers` is already per-business with
`business_id` and `user_id`, and `find_or_create_customer` matches within a
business by user, then email, then phone.

**A customer stays signed in across kiosks.** Navigating from one business's
kiosk to another keeps the BOSS session, and each business matches its own
customer record to that user.

**One membership table.** `employees` gains `role`; `business_users` goes.
See § Membership.

**A route naming a feature names its roles.** An app with no roles yet uses
`require_acl` as it always worked; once it has any, every route naming a
feature names who reaches it, and `default` says broadly reachable out loud.
`bin/check-routes` reports a route that names a feature and no role in an app
that has roles.

**A route names the roles that reach it, on its own decorator.** Everything
about a route stays on the route, so there is nothing to keep in step with
anything else — a role → endpoint mapping held apart would name routes as
strings, and nothing would hold those strings to the `@router` decorators.

Roles are an `Enum`, and the decorator takes members rather than strings:

```python
class Role(str, Enum):
    OPERATOR = "Operator"
    EMPLOYEE = "Employee"


@router.get("/business/{business_id}/employee/{employee_id}", response_model=Employee)
@require_acl("employee.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
@handled
async def get_employee(business_id: int, employee_id: int, request: Request, role: str):
```

A misspelled member is an `AttributeError` when the module imports, which is
the whole of the typo question.

The value is the label Settings shows. BOSS assigns the id, the way it does for
a permission, and a name that stays the same keeps the id it was given.

An app's roles accumulate as its decorators import and register together with
its features — `register_acl` gains them, and `ACLApp` carries them alongside
`features`. An app naming none receives a `default` role holding every
permission.

**Settings assigns roles rather than permissions.** The roles an app declares,
each showing its permissions, plus a `default` role showing all of them. A
permission may belong to several roles.

This narrows what the ACL used to allow, deliberately. Individual permissions
stop being assignable, and a new role means a deploy. An app needing a
permission nobody's role holds creates a role for it.

**A role change takes effect at the next sign-in.** The operator tells the
employee to sign out and back in.

**A license grant derives its bundle from the calling module.**
`sys._getframe(1).f_globals["__name__"]`, normalised to the first three
segments. A convenience rather than a boundary — every private app shares one
process — so ownership is enforced by a static check in `bin/`.

**Licenses are granted on creation.** Creating a business grants the operator a
license; creating an employee grants theirs.

**A customer sees their history for the business whose kiosk they are in.**
`/my/appointments` survives as a kiosk route, scoped to that business. One view
across every business a person is a customer of is a later question.

**License ownership is enforced statically.** A check that an app names only its
own bundle when granting.

**The customer surface is the kiosk.** The desktop carries admin, operator, and
employee. Everything a customer sees is the kiosk, reached the way a website
is. `CustomerDashboard` moves into the kiosk and `Application.html` loses its
`role === "customer"` branch.

**Every page names its audience.** Recorded in
[`plan.md` § Who reaches each page](plan.md).

---

## Absence is not removal

`createAclCatalog` treats a registration as the complete truth: anything in the
catalogue and absent from the payload is deleted, and `deleteAcl` cascades to
`acl_items` and `app_licenses`. Absence has three causes, and only one of them
is somebody deciding to remove something.

**An app that fails to import registers nothing.** `api.py` logs the failure
and continues, so the app never calls `register_acl`, never appears in
`REGISTERED_APPS`, and is absent from the payload. Registration then succeeds,
and every ACL for that app, every user's grant, and every user's license are
deleted. The service starts, the log holds one line about a module that failed,
and nothing connects the two.

**A route that stops naming a role** takes the role out of the union the
decorators accumulate, and the grants of it go the same way.

**Something genuinely removed** is the case the deletion was written for.

Three changes separate them. **All three are implemented** in
`server/bosslib`, with tests in `aclTests.swift`.

**Reconcile only what the payload speaks for.** An app absent from a
registration is left as it stands, rather than read as an app with nothing in
it. This alone removes the import-failure case, and it is the smallest change:
`catalogAcl` narrows to the bundles present in `apps`.

**Retire rather than delete.** A row the payload no longer names is marked
inactive and keeps its id, its grants, and its licenses. Verification passes
over an inactive row. A name that comes back is reactivated with everything
intact, which is what makes a rename recoverable and a re-registration free.

**Prune deliberately.** `api.acl.pruneAcl()` destroys retired records and
everything referencing them. `api.acl.retiredAcl()` shows what would go, first.

SQLite hands a freed rowid to the next insert, so a pruned id can be issued
again to something else — and a token minted before the prune would match the
new record until its holder signs in again. One more reason pruning is asked
for rather than reached by a deploy.

*The version number.* The migration is `1.3.0`. A previous `1.3.0` was removed
along with Lean and never reached production, so the number is free — though a
database created while it existed still carries a `versions` row for it, and
skips this migration until that row goes.

---

## Membership

`business_users` and `employees` overlap on `(business_id, user_id)` and differ
everywhere else.

| | `business_users` | `employees` |
|---|---|---|
| Rows | one per operator | one per person who works |
| `user_id` | required | nullable — added before they have a BOSS account |
| Carries | `role` | name, `include_in_schedule`, `can_manage_own_schedule` |
| Referenced by | nothing | `job_employees`, `employee_schedules`, `employee_time_off`, `job_sessions` |

**One table, named `employees`.** An operator is an employee of the business
they run, holding the operator role.

The case that decides it is the solo business: an owner who does the work is
both the operator and someone a job can be assigned to. Two tables give that
person two rows, and `whoami` reads one of them. One table gives them one row —
role Operator, `include_in_schedule` set. Role says what they may do; the flag
says whether they get scheduled.

`employees` is the shape to keep. Its `user_id` is already nullable, which is
how an operator adds someone before they have a BOSS account. Nothing
references `business_users(id)`, so it goes and its `role` column moves across.

**This fixes a live bug.** `whoami` reads `business_users`, which is written
only at operator signup. An employee linked through `employees.user_id` has no
row there and resolves as `customer`, so the `role === "employee"` branch at
`Application.html:166` has never been reachable.

**One business per user** becomes an invariant of this table: a `user_id`
appears at most once across it, which a unique index states.

---

## Routes that sit outside a role

Four routes do not fit "a role reaches this", and each for its own reason.

| Route | ACL | Role |
|---|---|---|
| `GET /config/stripe/connect` | yes | Operator |
| `GET /config/stripe/callback` | yes | Operator |
| `GET /contact-fields` | no | — |
| `GET /config/templates` | no | — |
| future `POST /stripe/webhook` | no | — |

**The Stripe callback carries the operator's session.** It is the OAuth leg of
Stripe Connect: the operator authorises at Stripe, and Stripe redirects *their
browser* back with `code` and `state`. So it arrives as a `GET` with their
cookie, and it writes `stripe_account_id` onto their business — an operator's
route in every sense. It was declared `POST` in Stage 1, before the mechanics
were settled, and nothing ever called it.

Beside the role it needs a `state` token: generated here before the operator is
sent to Stripe, stored against their session, and compared on return. That
comparison is what says the exchange began here, and it happens before `code`
is spent. It lives in the handler.

**The webhook is the one with no BOSS credential.** Stripe's servers call it
directly — no user, no cookie — and it authenticates by signature: Stripe signs
the raw body with the webhook secret and sends `Stripe-Signature`, which the
handler recomputes and compares. `stripe_client.handle_webhook(payload,
sig_header)` in [`plan.md`](plan.md) is that function. A caller that is not a
user reaches nothing in ACL, so it names no role.

That check sits in the handler rather than a decorator. A decorator carries an
operation many routes share; a check one route needs reads better beside the
thing it protects.

**Read-only platform data sits outside ACL.** `contact_field_types` and
`business_templates` have no `business_id`, carry nobody's records, and answer
every caller identically. `/config/templates` is reached by `OperatorSignup`
before a business exists, so no role could suit it — and a route declaring a
feature has to name one, since `default` is what BOSS supplies to an app that
declared no roles rather than something a route names.

---

## Scoping the 36

With the business derived, the check is that a record belongs to the caller's
business.

**Scope in the query rather than beside it.** Every read and write takes the
business id and filters on it, so a record belonging to another business is
absent rather than refused:

```python
db.get_employee(business_id, employee_id)   # None when it is not theirs
```

The scope is a parameter rather than a line beside the call, so `get_employee`
cannot be reached without one. A record belonging to another business comes
back as `None` and takes the not-found path that already exists — which also
declines to say whether that id exists somewhere else.

Writes take the same shape. `UPDATE ... WHERE id = ? AND business_id = ?`
touches nothing for another business's record, and the rowcount check already
turns that into the same answer.

Parent before child, per
[`python.md` § Parent before child](../../../docs/prompt/python.md).

---

## Open

Nothing. Both items that stood here are settled:

**Registration deleting what it does not see** — a name a registration stops
carrying is retired rather than deleted, and only the apps a payload names are
reconciled at all. `api.acl.pruneAcl()` is how a retired record is destroyed,
and it is asked for. See § Absence is not removal.

**The 36** — tagged, scoped, and covered by `uitest/tests/scheduler-access.spec.js`.

---

## Next, in order

1. ~~Add `roles` to `require_acl` and `register_acl`, the `Enum` requirement,
   and the `default` role.~~ **Done.** An app's roles register with its
   features; BOSS stores them in `acl_roles` and `acl_role_permissions`.

2. ~~**Verify against a role.**~~ **Done.** A user holds a role in
   `acl_role_items`, the JWT carries the roles, and `ACLService` keeps role to
   permissions in memory — so a role expands when the request arrives, and
   retagging a route reaches its holders on the tokens they already have.

3. ~~**Grant a role, and a license, from Python.**~~ **Done.** Signing up
   grants the operator theirs; linking an account grants the employee theirs.
   The bundle is read off the calling module, and `bin/check-services` holds
   an app to its own — an app posting to BOSS itself, reaching
   `/private/acl`, or naming a bundle to `calling_bundle` is reported.

4. ~~**Fold `business_users` into `employees`**~~ **Done.** `employees` carries
   a `role` column, one business per email, and `is_working_for_business` came
   with it.

5. ~~**Put the business id in the path**~~ **Done.** 59 routes moved under
   `/business/{business_id}`, and `SuperadminBusiness` merged into
   `BusinessConfig`.

6. ~~**Tag the routes and scope their queries.**~~ **Done.** 68 routes carry a
   guard, each query takes the business first, and
   `uitest/tests/scheduler-access.spec.js` covers who reaches what.

7. ~~**Retire the permission-to-user relationship.**~~ **Done.** `acl_items` is
   dropped, Settings ticks roles and lists what each holds beneath it, and the
   JWT carries `apps` and `roles` and no `acl` claim.

8. **Move `CustomerDashboard` into the kiosk.**

9. ~~**Write the endpoint authentication rules into**
   [`python.md`](../../../docs/prompt/python.md)~~ **Done.** § Endpoint
   pattern states which decorator a route takes and when a route sits outside
   ACL.

---

## After the plan

Two changes the plan did not anticipate, recorded here because they changed
the shape it describes:

**The catalog is gone.** A path was `<catalog>,<bundle>,<feature>,<permission>`,
the first part naming whichever service registered it. It is now `<bundle>`
onward. An app has one backend — Python, or Swift for a BOSS subsystem — so
the segment only ever held one value per app, while making the same bundle
under two services look like two apps whose roles could not see each other.
See [`process.md` § One app, one backend](../../../docs/prompt/process.md).

**Pruning takes the role's links with it.** `deleteAcl` cleared `acl` and
`app_licenses` and left `acl_role_permissions`. SQLite hands a freed rowid to
the next insert, so a role holding a pruned permission would come to hold
whatever took its place — granting rather than denying.
