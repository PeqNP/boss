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
 * `bootBOSS` alone signs in as a guest, which is user 2. Anything behind
 * `@require_admin()` needs user 1, and an app that gates its menus on `isAdmin`
 * will not even render those screens to click. The dev server issues a
 * super-user cookie from `/debug/sign-in` (non-release builds only), and
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
  await menu.locator(".ui-popup-choice", { hasText: label }).first().click();
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
  const choice = menu.locator(".ui-popup-choices > div", { hasText: label }).first();
  // The list grows with the data, so a choice can sit past the fold even when
  // the control does not.
  await choice.scrollIntoViewIfNeeded();
  await choice.click();
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
