# App Store

## Identity

- **Bundle ID**: `io.bithead.app-store`
- **Backend**: Python. See [`process.md` § One app, one backend](../../../docs/prompt/process.md).
- **Status**: planned. Nothing is built.

## What it is for

The application that gates the use of applications. It issues licenses to users, and a license is what says somebody may use an app at all.

Today a license is granted by whichever app has a reason to grant one — Scheduler issues its own when somebody opens a business, and an operator issues one to an employee whose account they link. That works while there are a handful of apps and one person deciding. It does not answer who may install an app they have never used, which is what this is for.

## What a license means

BOSS already holds licenses: `app_licenses` ties a user to an `ACLType.app` record, and `issueAppLicense` is idempotent — a second grant to the same user returns the first. This app does not replace that. It is the surface that decides who gets one.

**The system does not know whether an app is free.** A license is held or it is not; what it cost is between the store and whoever paid. Nothing in BOSS branches on price.

## Which apps appear here

An app declares whether it needs a license in its own `application.json`:

```json
{
  "application": {
    "licensed": true
  }
}
```

Absent means `false`: an app requires no license until it says otherwise, so adding the requirement is a deliberate act rather than something every new app inherits.

**Only apps with `licensed: true` are listed and managed here.** An app that needs no license has nothing to buy, nothing to revoke, and no reason to appear.

Settings reads the same flag: the **Issue license** checkbox is disabled for an app that requires none, and says so.

## What still has to be decided

### The backend is not gated yet

The license check runs in `application-manager.js`, in the browser. A signed-in user who never opens the app can still call its API — the routes check `@require_acl`, which is about *roles*, and a role says nothing about holding a license.

So an app that requires a license is only gated at the window. That is acceptable while nothing is sold, and is the first thing this app has to fix: **if an app requires a license, its API refuses a caller who holds none.**

That check has to happen in the private API, which means the private API has to know what `application.json` says. Today nothing on the Python side reads a bundle's manifest.

### Where the license is read from

Two options, and the choice is open:

**In the token, like roles.** The JWT already carries `apps` and `roles`, and `verifyAccess` expands a role from memory rather than querying. A license claim would cost nothing per request.

**Queried per request.** Revoking a license may need to take effect immediately — somebody's card is declined, or a licence is withdrawn — and a claim in a token lasts until the holder signs in again. Roles have the same property and it is tolerable there, because a role is granted by somebody who can also take it back and wait. A revoked license may not be.

Undecided. It turns on how quickly a revocation has to bite.

### The admin is exempt

`verifyAccess` returns early for a super user, and `/account/app-license` answers `valid: true` for one. That stays: whoever runs the platform reaches everything, which is what makes support possible.

## Related

- [`plan-authentication.md` was retired](../io.bithead.scheduler/plan.md) — its work is done, and the roles it built are what `@require_acl` reads.
- Scheduler's `active` flag on a business does the same job as a license, for the operator's own account. Once an app can ask whether a user holds a license, that flag has no separate reason to exist.
