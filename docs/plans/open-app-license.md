# Open an app — license check

Stage 3 is in review. `uitest/tests/boss-open-license.spec.js` covers the four proofs. Lean Visualizer is the bundle that sets `licensed`.

The OS refuses to open an app that requires a license when this person does not hold one. It says so by the app's name, and it says so before the app opens. Swift decides whether the license is held. The app asks for that check with `licensed` in `application.json`. Absent, or anything other than `true`, means the check does not run.

## Who

| Actor | What they do |
|---|---|
| Guest | Opens an app. If it requires a license, they see the same refusal as anyone else. |
| Signed-in user | Opens an app they are not licensed for and is told so. Opens an app they are licensed for, or one that does not require a license. |
| Super user | Opens any app. Swift already treats them as licensed. |

## What happens

Someone opens an app that is not already loaded. The OS reads that app's `application.json`. `application.licensed` is the flag. It defaults to false: missing, `false`, or any other value means the app opens with no license call.

When `licensed` is `true`, the OS asks Swift before it shows the loading progress bar and before it builds the application. The call is the one that already exists, `POST /account/app-license`, with the bundle id. Swift answers `valid`.

Swift's answer:

| Situation | `valid` |
|---|---|
| The bundle has no ACL record | `true`. There is no license to hold. |
| The caller is the super user | `true` |
| The caller is a guest, or has no session | `false` |
| The caller has no license row for that ACL | `false` |
| The caller has a license row | `true` |

A guest or a missing session is `valid: false`, not an error. Today `verifyAccess` throws `GuestUserAccessDenied` once the bundle has an ACL, and the OS then says the license could not be loaded. That throw goes away for this route.

When `valid` is false, the OS shows: "You do not have a license to use {name}." `{name}` is `application.name` from the bundle just read. The progress bar does not appear. The app is not added to the loaded set. Nothing of the app's own code runs.

When the request fails for any other reason, the OS still says the license could not be loaded and to try again. That is a different sentence from the refusal.

An app that is already loaded is brought forward with no new check.

## Out of scope

- Renaming `licensed` to `license`. The key `openApplication` reads, and the one documented in `shared.md`, is `licensed`.
- Issuing or revoking a license. Settings and the App Store keep doing that.
- Closing an app whose license is revoked while it is already open.
- Checking a license on every switch back to a loaded app.
- A license for an app that does not set `licensed` to `true`. Scheduler stays openable without one, which is why the flag exists.

## Where it lives

| Piece | File |
|---|---|
| The open path | `public/boss/application-manager.js`, `openApplication` |
| The answer | `server/web/Sources/App/Routes/Account/AccountRoute.swift`, `POST /account/app-license` |
| The flag | `application.licensed` in each app's `application.json` |
| The sentence | `os.ui.showError` |

## Stage 1 — Swift

`POST /account/app-license` keeps its body, `{ bundleId }`, and its response, `{ valid, license }`.

The no-ACL branch and the super-user branch stay: both return `valid: true`.

When the bundle has an ACL and the caller is a guest, has no session, or `verifyAccess` refuses them as a guest, the route returns `valid: false` and `license: null`. It does not throw.

When the caller is signed in and `appLicense` throws because there is no row, the route still returns `valid: false`. A license row still returns `valid: true` with that license.

Other failures from `verifyAccess` — a bad token, a disabled account, an unverified account — still throw. The OS treats those as "could not load the license."

## Stage 2 — The opener

`openApplication` in `application-manager.js`.

An app already in `loadedApps` is switched to, with no license call.

Otherwise the OS loads `application.json` and does not yet show the progress bar and does not yet construct `UIApplication`.

`config.application?.licensed === true` is the only reason to call `POST /account/app-license`. Any other value skips the call and opens the app.

A `valid: false` response shows "You do not have a license to use {name}." and returns. The function does not throw a second error on top of that dialog. The app is not loaded.

A failed request shows "Failed to load license for application ({name}). Please try again later." and returns the same way.

Only a `valid: true` response, or a skipped check, continues into the progress bar and the rest of the open.

## Stage 3 — UI test

One spec, `uitest/tests/boss-open-license.spec.js`. Reset nothing that other apps own. The proof is wiring:

1. An app that does not set `licensed` opens with no `POST /account/app-license`.
2. An app that sets `licensed` to `true`, opened by an account with no license, shows the no-license sentence with the app's name, does not show the loading progress bar, and does not leave the app loaded.
3. The same account, after a license is issued, opens that app.
4. Opening it a second time does not call `POST /account/app-license` again.

Scheduler is the app that must keep opening with no license call. The licensed app is whichever bundle already sets `licensed` to `true`. If none does, the spec says so and stops before inventing a bundle.

## Open decisions

None. Swift answers only when `licensed` is `true`. An already loaded app is not checked again. A guest sees the same no-license sentence.
