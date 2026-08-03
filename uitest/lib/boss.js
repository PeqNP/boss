// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Helpers for driving Bithead OS from Playwright.
 *
 * BOSS is a single page that renders every window into the desktop, so tests
 * do not navigate between URLs. They boot the OS once, then open applications
 * through the OS itself. Opening an app via `os.openApplication` rather than
 * clicking a desktop icon keeps a test focused on what it is actually
 * verifying instead of on how the app happened to be launched.
 */

import { expect } from "@playwright/test";

/**
 * Take a super user session before BOSS loads.
 *
 * `bootBOSS` alone is signed in as nobody — every private route answers 401.
 * Anything behind `@require_admin()` needs user 1, and an app that gates its
 * menus on `isAdmin` will not even render those screens to click. The dev
 * server issues a super-user cookie from `/debug/sign-in` (dev builds only), and
 * `page.request` shares the browser context's cookie jar — so requesting it
 * before `page.goto` means BOSS boots already authenticated.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function signInAsAdmin(page) {
  const response = await page.request.get("/debug/sign-in");
  expect(response.ok(), "/debug/sign-in is only available in a dev build").toBe(true);
}

/**
 * The non-admin identity every operator flow runs as.
 *
 * Two identities are the only way to test a rule about *who* did something —
 * that a block a manager raised is not the operator's to clear, that a unit
 * one operator holds is not another's to complete. An admin driving both sides
 * proves the buttons work and nothing about the rule.
 */
export const OPERATOR = {
  email: "operator@bithead.io",
  password: "Password1!",
  fullName: "Dana Operator"
};

/**
 * Create the operator account if it is not already there.
 *
 * `POST /account/user` is the admin route, which sets a password directly and
 * marks the account verified — so no email round-trip. Must be called from a
 * page holding an admin session.
 *
 * This writes to the BOSS database, which the app-level reset never touches,
 * so the account survives between runs and this is a no-op after the first.
 *
 * @param {import('@playwright/test').Page} page - An admin's page
 */
export async function ensureOperator(page) {
  const listed = await (await page.request.get("/account/users")).json();
  if ((listed.users || []).some((user) => user.name === OPERATOR.email)) {
    return;
  }
  const created = await page.request.post("/account/user", {
    data: { ...OPERATOR, verified: true, enabled: true }
  });
  expect(created.ok(), `could not create the operator account: ${await created.text()}`)
    .toBe(true);
}

/**
 * Take an operator session before BOSS loads.
 *
 * The counterpart to `signInAsAdmin`: same cookie jar, same timing, a user who
 * is not user 1 — so every `@require_admin()` route answers 403 and the app's
 * admin menus are never rendered.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function signInAsOperator(page) {
  const response = await page.request.post("/account/signin", {
    data: { email: OPERATOR.email, password: OPERATOR.password }
  });
  expect(response.ok(),
         "the operator account must exist — call `ensureOperator` from an admin page first")
    .toBe(true);
}

/**
 * Release any line the caller is still holding.
 *
 * An app whose `applicationDidStart` resumes a held line will open that screen
 * instead of the one under test, and a resource left checked out blocks the
 * next run from taking it. A spec that needs a clean launch calls this before
 * `bootBOSS`.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} api - The app's API prefix
 */
export async function leaveHeldLine(page, api) {
  const me = await (await page.request.get(`${api}/me`)).json();
  if (me.activeLine) {
    await page.request.post(`${api}/line/${me.activeLine.lineId}/leave`);
  }
}

/**
 * Load BOSS and wait until the OS has finished booting.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function bootBOSS(page) {
  await page.goto("/");

  // `index.html` declares `let os = new OS()` at the top level of a classic
  // script. A top-level `let` creates a global *declarative* binding, not a
  // property of `window` — so `window.os` is undefined and `os` must be
  // referenced bare. The try/catch covers the temporal dead zone before that
  // script has run.
  await page.waitForFunction(() => {
    try {
      return os.isLoaded() === true;
    }
    catch {
      return false;
    }
  });

  await dismissWelcome(page);
  await expectSignedIn(page);
}

/**
 * Fail here, and say so, if BOSS is asking anyone to sign in.
 *
 * A rejected session puts the OS into its Sign In modal, whose overlay then
 * swallows every click on the desktop behind it. Without this the run reports
 * a thirty-second timeout on whatever the next test happened to click — a
 * production menu, a button — and names something that was never the problem.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function expectSignedIn(page) {
  const signIn = page.locator(".ui-modal", { hasText: "Sign In" });
  await expect(signIn,
               "BOSS is showing its Sign In modal, so a request was answered 401 — "
               + "the session this test signed in with was rejected, and nothing "
               + "behind the modal is clickable")
    .toHaveCount(0);
}

/**
 * Close the Welcome window shown to guests.
 *
 * `startOS` signs an unauthenticated visitor in as a guest and then opens
 * Welcome, which sits above the desktop and swallows clicks meant for the
 * application under test. It appears after `isLoaded()` becomes true, so it
 * is waited for rather than checked once.
 *
 * @param {import('@playwright/test').Page} page
 */
async function dismissWelcome(page) {
  const welcome = page.locator(".ui-window, .ui-modal").filter({
    has: page.locator(".title span", { hasText: "Welcome" })
  });
  try {
    await welcome.waitFor({ state: "visible", timeout: 5_000 });
  }
  catch {
    // Already signed in, so no Welcome window was shown.
    return;
  }
  await welcome.locator(".close-button").click();
  await welcome.waitFor({ state: "detached" });
}

/**
 * Open an installed application and wait for its container to exist.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} bundleId - e.g. `io.bithead.tutorial`
 */
export async function openApplication(page, bundleId) {
  // `os` is a global declarative binding, not `window.os` — see `bootBOSS`.
  await page.evaluate((id) => os.openApplication(id), bundleId);
  await expect(page.locator(`#app-container-${cssEscape(bundleId)}`)).toBeAttached();
}

/**
 * The window or modal whose title reads `title`.
 *
 * BOSS windows carry no stable ID, so the title is the reliable handle.
 *
 * Both kinds are matched, and the title is found by class alone: a window
 * wraps its title in `.top > .title > span`, while a modal declares a bare
 * `.title` at the root. A caller asking for "the thing titled Pools" does not
 * care which it is, and would otherwise silently miss every modal.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} title
 * @returns {import('@playwright/test').Locator}
 */
export function windowByTitle(page, title) {
  // Anchored, because `hasText` with a string matches a substring — and this
  // OS is full of near-identical pairs. Asking for "Pool" would also return
  // "Pools", and the two windows are open at the same time.
  const exact = new RegExp(`^\\s*${title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`);
  return page.locator(".ui-window, .ui-modal").filter({
    has: page.locator(".title", { hasText: exact })
  });
}

/**
 * Open an OS bar menu and choose one of its items.
 *
 * `styleUIMenu` replaces each `<option>` with a `.ui-popup-choice` div that
 * forwards clicks to the original option's `onclick`, and the menu carries a
 * `ui-menu-<select name>` class. The choices are hidden until the label is
 * clicked, so the menu is opened first — which is what a user does anyway.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} menuName - The `<select>` name, e.g. `production-menu`
 * @param {string} label - The item's visible text
 */
export async function clickMenuItem(page, menuName, label) {
  const menu = page.locator(`.ui-menu-${cssEscape(menuName)}`);
  await menu.locator(".ui-menu-label").click();
  // Anchored: `hasText` matches a substring, so asking for `Jobs` would also
  // find `Active Jobs` — and menus in this app are full of such pairs.
  const exact = new RegExp(`^\\s*${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`);
  await menu.locator(".ui-popup-choice", { hasText: exact }).first().click();
}

/**
 * The button that runs a given controller function.
 *
 * A window often holds several buttons reading `Add` — one per fieldset — so
 * the label alone is ambiguous. Every BOSS button routes through a named
 * controller function, and `onclick` carries that name: it is unique, and it
 * says what the button is for rather than what it happens to read.
 *
 * Where an element has no such handle, give it a `test-id` and use
 * `page.getByTestId`.
 *
 * @param {import('@playwright/test').Locator} win
 * @param {string} functionName - e.g. `addOperation`
 * @returns {import('@playwright/test').Locator}
 */
export function action(win, functionName) {
  return win.locator(`button[onclick*="${functionName}("]`);
}

/**
 * Choose an option from a pop-up menu, the way a user does.
 *
 * `styleUIPopupMenu` hides the real `<select>` and renders the choices as
 * divs, so the menu is opened by clicking its label and the choice is clicked
 * by its text.
 *
 * @param {import('@playwright/test').Locator} win
 * @param {string} name - The `<select>` name
 * @param {string} label - The option's visible text
 */
export async function selectPopupOption(win, name, label) {
  const menu = component(win, "ui-popup-menu", name);
  // Forms in this OS are long, and the choices open next to their control —
  // so a menu near the bottom opens its list past the fold, and the click
  // fails as "outside of the viewport" rather than as anything informative.
  // Centring leaves room for the list to open downwards.
  await menu.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await menu.locator(".ui-popup-label").click();
  // Substring, unlike `windowByTitle` and `clickMenuItem`: a choice carries
  // decoration a caller should not have to spell out — a line's version, a
  // count — so anchoring would break every one of them. No `.first()` though,
  // which leaves Playwright's strict mode to raise when a label is ambiguous
  // rather than silently taking whichever came first.
  const choice = menu.locator(".ui-popup-choices > div", { hasText: label });
  // The list grows with the data, so a choice can sit past the fold even when
  // the control does not.
  await choice.scrollIntoViewIfNeeded();
  await choice.click();
}

/**
 * How far a pop-up's choices sit from the control that opened them.
 *
 * The choices are drawn in the browser's top layer, which keeps them clear of
 * an ancestor that clips (a scrollable window body) and of an ancestor with a
 * `transform` (a modal is centred with `translateX(-50%)`, which would
 * otherwise become the containing block for a `position: fixed` layer and
 * offset the list by the modal's own position).
 *
 * A correctly anchored menu returns the component's own 1px inset.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} menuSelector - CSS for the `.ui-popup-menu`
 * @returns {Promise<{dx: number, dy: number}>}
 */
export async function popupOffset(page, menuSelector) {
  return page.evaluate((selector) => {
    const menu = document.querySelector(selector);
    const label = menu.querySelector(".ui-popup-label").getBoundingClientRect();
    const sub = menu.querySelector(".sub-container").getBoundingClientRect();
    return { dx: Math.round(sub.x - label.x), dy: Math.round(sub.y - label.bottom) };
  }, menuSelector);
}

/** The offset a correctly anchored pop-up reports. */
export const POPUP_ANCHOR = { dx: -1, dy: 1 };

/**
 * Elements whose content is wider than they are.
 *
 * A control sized `100%` that renders even 2px wider than its parent scrolls
 * the whole view sideways, which on a floor terminal is unusable.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} root - CSS for the container to search within
 * @returns {Promise<string[]>}
 */
export async function overflowing(page, root) {
  return page.evaluate((selector) =>
    [...document.querySelectorAll(`${selector}, ${selector} *`)]
      .filter((el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1)
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`), root);
}

/**
 * Wait until a window has finished loading its data.
 *
 * A window is on screen before its `viewDidLoad` runs, so it is visible — and
 * fillable — while the fetch that populates it is still in flight. BOSS marks
 * that state with `aria-busy`, and clears it once the load settles.
 *
 * Playwright's own waiting covers clicks, because a loading window sets
 * `pointer-events: none` and a click retries until it lands. It does not cover
 * `fill`, which checks only that a field is visible, enabled, and editable —
 * so typing into an unsettled form succeeds and is then overwritten by the
 * response. Wait here before typing.
 *
 * @param {import('@playwright/test').Locator} win
 */
export async function settled(win) {
  await expect(win).toHaveAttribute("aria-busy", "false");
}

/**
 * Close a window the way its title bar does.
 *
 * Worth doing rather than leaving windows open: `windowByTitle` matches on
 * title, so a second window of the same kind — a second job's dashboard, a
 * second operation — turns every later lookup into a strict-mode violation.
 * Closing also proves the screen tears down without throwing.
 *
 * @param {import('@playwright/test').Locator} win
 */
export async function closeWindow(win) {
  // A window closes from its title bar. A modal has no title bar — it declares
  // a `Close` control of its own — so both are tried, in the order a person
  // would reach for them.
  const titleBar = win.locator(".close-button");
  if (await titleBar.count() > 0) {
    await titleBar.first().click();
  }
  else {
    await win.locator('button[onclick*="close("]').first().click();
  }
  await expect(win).toHaveCount(0);
}

/**
 * A named element inside a window, the way `view.ui.<accessor>` would find it.
 *
 * @param {import('@playwright/test').Locator} win
 * @param {string} tag - e.g. `select`, `input`, `button`, `div`
 * @param {string} name - The element's `name` attribute
 * @returns {import('@playwright/test').Locator}
 */
export function named(win, tag, name) {
  return win.locator(`${tag}[name="${name}"]`);
}

/**
 * The styled wrapper around a named `select` — the `ui-popup-menu` or
 * `ui-list-box` div that holds the component's rendered markup.
 *
 * Uses CSS `:has()`, which is relative by definition. Playwright's
 * `filter({ has })` queries its inner locator relative to each candidate, so
 * passing a locator built from `page` or a window would search for that whole
 * chain *inside* the component and never match.
 *
 * @param {import('@playwright/test').Locator} win
 * @param {string} componentClass - e.g. `ui-popup-menu`, `ui-list-box`
 * @param {string} name - The `select` element's `name`
 * @returns {import('@playwright/test').Locator}
 */
export function component(win, componentClass, name) {
  return win.locator(`.${componentClass}:has(select[name="${name}"])`);
}

/**
 * The value currently selected in a named component.
 *
 * Asserting on state rather than on a transient status message keeps a test
 * from depending on whatever wrote to the page most recently.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name - The `select` element's `name`
 * @returns {Promise<string|undefined>}
 */
export async function selectedValue(page, name) {
  return page.evaluate(
    (n) => document.querySelector(`select[name="${n}"]`)?.ui.selectedValue(),
    name
  );
}

/**
 * Read a component's `ui` interface from the browser.
 *
 * A component built after its window rendered only has `ui` if it went
 * through a factory, so this is how a test proves a component was styled
 * rather than merely inserted.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name - The `select` element's `name`
 * @returns {Promise<boolean>} `true` when the component has its interface
 */
export async function hasUIInterface(page, name) {
  return page.evaluate((n) => {
    const select = document.querySelector(`select[name="${n}"]`);
    return !!select && !!select.ui;
  }, name);
}

/**
 * Bring the window containing `selector` to the front.
 *
 * BOSS renders every window into one desktop, so a window opened earlier can
 * sit on top of the one under test and swallow its clicks. Focusing is
 * deterministic where waiting is not.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} selector - A selector for anything inside the window
 */
export async function bringToFront(page, selector) {
  await page.locator(selector).waitFor({ state: "visible" });
  await page.evaluate((sel) => {
    // `focusWindow` expects the container that carries the `ui` interface —
    // the outer `.ui-container`, not the inner `.ui-window`.
    let node = document.querySelector(sel);
    while (node && !node.ui) {
      node = node.parentElement;
    }
    if (node) {
      os.ui.focusWindow(node);
    }
  }, selector);
}

/**
 * Geometry and layout-governing styles for an element and its ancestors.
 *
 * A component that renders in one context and not another almost always
 * differs in `position`, `overflow`, `z-index`, or a clipped ancestor — none of
 * which are visible in the DOM alone. This walks up from the element so the
 * ancestor doing the damage is in the same output.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} selector - CSS selector for the element to inspect
 * @param {number} [depth] - How many ancestors to include
 * @returns {Promise<object[]>} One entry per element, innermost first
 */
export async function layoutOf(page, selector, depth = 5) {
  return page.evaluate(({ selector, depth }) => {
    const out = [];
    let el = document.querySelector(selector);
    if (!el) {
      return [{ error: `no element matches ${selector}` }];
    }
    for (let i = 0; i <= depth && el && el !== document.documentElement; i++) {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      out.push({
        tag: el.tagName.toLowerCase(),
        class: el.className || null,
        box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        position: s.position,
        display: s.display,
        overflow: `${s.overflowX}/${s.overflowY}`,
        zIndex: s.zIndex,
        transform: s.transform === "none" ? null : s.transform,
        // A clipping or stacking ancestor is the usual culprit when a floating
        // layer stops floating.
        clips: s.overflowX !== "visible" || s.overflowY !== "visible",
        createsStackingContext: s.zIndex !== "auto" || s.transform !== "none" || s.position === "fixed"
      });
      el = el.parentElement;
    }
    return out;
  }, { selector, depth });
}

/**
 * Escape a bundle ID for use in a CSS selector — the dots would otherwise
 * read as class selectors.
 *
 * @param {string} value
 * @returns {string}
 */
function cssEscape(value) {
  return value.replace(/\./g, "\\.");
}
