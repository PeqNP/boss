# BOSS UI Tests

Playwright tests that drive Bithead OS in a real browser.

## Setup (once)

```bash
cd uitest
npm install
npm run install-browsers    # downloads Chromium, ~150MB
```

## Running

The tests drive a **BOSS server that is already running** — they never start
one. The developer owns the service lifecycle; see "Who starts the servers"
below.

```bash
cd uitest
npm test                # headless
npm run test:headed     # watch it drive the browser
npm run test:ui         # Playwright's interactive runner — best for debugging
npm run report          # open the HTML report from the last run
```

The default host is `https://localhost` (nginx, self-signed certificate, which
the config ignores). Point somewhere else with:

```bash
BOSS_URL=http://localhost:8080 npm test
```

## Server lifecycle

The developer starts and stops the Python and Swift services — agents never do,
and never stand up a substitute. See "Running and Validating Locally" in
[`docs/prompt/shared.md`](../docs/prompt/shared.md) for that rule and for which
kinds of change require a restart.

For UI work the short version is: a change under `public/**` needs no restart,
because every test begins with `page.goto("/")`.

## Reporting a failure

Every test carries a tag — `@window`, `@static`, `@factory`, `@popup`, `@listbox` —
so a failure can be named in one word and re-run on its own:

```bash
npx playwright test --grep @popup
```

The UI runner has no "copy error" button. For anything that needs sharing, run
it in the terminal and paste the output, which includes the tag, the file and
line, the failing locator, and expected vs. received:

```bash
npx playwright test --grep @popup --reporter=list 2>&1 | tail -40
```

**Read `error-context.md` first.** Every failure writes one to
`test-results/<test-name>/`, holding an accessibility snapshot of the page at
the moment the assertion failed. It answers "what was actually rendered" far
faster than re-reading the code, and it is the quickest way to tell a broken
component apart from a broken locator. A screenshot, video, and trace sit
beside it.

When that is still not enough, `npm run test:ui` and open the **Trace** tab:
stepping to the failing action shows the DOM at that exact moment.

To add a test, give it a new tag so it can be referred to the same way.

## Diagnosing a visual bug

Playwright can inspect layout and take screenshots, so a visual problem can be
investigated directly rather than described. The workflow:

1. **You describe** the navigation steps and what looks wrong.
2. **A throwaway probe** is written to `tests/_probe.spec.js` (files matching
   `tests/_*.spec.js` are gitignored) that follows those steps, dumps
   `layoutOf(page, selector)` for the suspect element, and takes a screenshot.
3. **The output is read** — the screenshot shows what it looks like; `layoutOf`
   gives the geometry and the styles that govern it (`position`, `overflow`,
   `z-index`, `transform`, and whether any ancestor clips or creates a stacking
   context).
4. **Compare against a working context.** Probing the same component where it
   renders correctly turns "it looks wrong" into an exact offset, which usually
   names the cause outright.
5. **A regression test replaces the probe** once the fix lands.

Opening a window or modal through the OS is more reliable than clicking to it:

```javascript
await openApplication(page, "io.bithead.production");
await page.evaluate(async () => {
  const app = await os.application("io.bithead.production");
  const win = await app.loadController("Section");
  win.ui.show((ctrl) => ctrl.configure({ operationId: 1, sectionId: null }));
});
```

`os.application()` returns only apps that are already open, so call
`openApplication` first.

## Layout

```
uitest/
  playwright.config.js   Base URL, timeouts, artifacts
  lib/boss.js            Helpers for booting the OS and locating windows
  tests/*.spec.js        The tests
```

## Writing a test

BOSS is a single page that renders every window into the desktop, so tests do
not navigate between URLs. Boot the OS once, then open an application through
the OS:

```javascript
import { bootBOSS, openApplication, windowByTitle, named } from "../lib/boss.js";

await bootBOSS(page);
await openApplication(page, "io.bithead.tutorial");

const win = windowByTitle(page, "UI Components");
await named(win, "button", "make-components").click();
```

`bootBOSS` waits on `os.isLoaded()` — the OS's own readiness signal — rather
than on a timeout.

Opening an app with `os.openApplication` instead of clicking its desktop icon
keeps a test focused on what it is verifying rather than on how the app was
launched.

## Adding a component

Every UI component is demonstrated in the Tutorial's `Example` controller, so
the component library can be exercised in one pass. When a component is added
or changed:

1. Add it to `public/boss/app/io.bithead.tutorial/controller/Example.html`
   (markup) and `Example.js` (behavior) — `Example` is a module controller, so
   the two are separate files.
2. Assert it in `tests/tutorial-example.spec.js`.

## Locating elements

Prefer the element's `name` attribute, which is how controllers find things
through `view.ui.<accessor>(name)`. That keeps a test coupled to the same
contract the application code uses, rather than to markup structure.

To verify a component was **styled** and not merely inserted, check that its
`select` has a `ui` interface — `hasUIInterface(page, name)`. Only components
that went through the render-time pass or a `os.ui.make*` factory have one.

Two rules, both learned by getting them wrong:

**`filter({ has })` queries its inner locator relative to each candidate.**
Passing a locator built from `page` or a window makes Playwright search for that
whole chain *inside* the candidate, which never matches. Use CSS `:has()`, which
is relative by definition — that is what `component(win, class, name)` does:

```javascript
// ✓ correct
win.locator('.ui-popup-menu:has(select[name="made-popup"])');

// ✗ wrong — looks for a .ui-window inside the popup menu
win.locator(".ui-popup-menu").filter({ has: named(win, "select", "made-popup") });
```

**Assert on state, not on a status message.** A message can be overwritten by
whatever renders next, so the assertion passes or fails for reasons unrelated to
the behaviour under test. Prefer `selectedValue(page, name)` and
`hasUIInterface(page, name)` over reading a result line.
