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
 * Load BOSS and wait until the OS has finished booting.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function bootBOSS(page) {
  await page.goto("/");
  // `os.isLoaded()` is the OS's own readiness signal, so this waits on the
  // real thing rather than on a timeout.
  await page.waitForFunction(() => window.os?.isLoaded?.() === true);
}

/**
 * Open an installed application and wait for its container to exist.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} bundleId - e.g. `io.bithead.tutorial`
 */
export async function openApplication(page, bundleId) {
  await page.evaluate((id) => window.os.openApplication(id), bundleId);
  await expect(page.locator(`#app-container-${cssEscape(bundleId)}`)).toBeAttached();
}

/**
 * The window whose title bar reads `title`.
 *
 * BOSS windows carry no stable ID, so the title is the reliable handle.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} title
 * @returns {import('@playwright/test').Locator}
 */
export function windowByTitle(page, title) {
  return page.locator(".ui-window").filter({
    has: page.locator(".top .title span", { hasText: title })
  });
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
 * Escape a bundle ID for use in a CSS selector — the dots would otherwise
 * read as class selectors.
 *
 * @param {string} value
 * @returns {string}
 */
function cssEscape(value) {
  return value.replace(/\./g, "\\.");
}
