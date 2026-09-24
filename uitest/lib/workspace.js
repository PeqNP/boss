// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * A clean workspace for one signed-in account.
 *
 * The account survives a reset. The database does not: each spec empties
 * `workspace.sqlite3` and lets the first load write the starting list, or
 * puts a list there with `PUT` when the screen is not what the spec is proving.
 */

import { expect } from "@playwright/test";
import { account, bootBOSS, ensureAccount, signInAsAdmin } from "./boss.js";

export const OWNER = account("workspace");

export const GUEST_DESKTOP = [
  "io.bithead.json-formatter",
  "io.bithead.tutorial",
  "io.bithead.lean-visualizer",
  "io.bithead.wordy"
];

export const USER_DESKTOP = [
  "io.bithead.json-formatter",
  "io.bithead.tutorial",
  "io.bithead.scheduler",
  "io.bithead.wordy"
];

export const USER_DOCK = ["io.bithead.scheduler"];

const API = "/api/io.bithead.boss";

/**
 * Empty this app's database and recreate the guest seed.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function resetWorkspace(page) {
  const response = await page.request.get(
    "/api/debug/uitests/reset?bundle=io.bithead.boss"
  );
  expect(response.ok(),
         `could not reset the workspace: ${await response.text()}`).toBe(true);
}

/**
 * Sign in as the workspace account, after a reset.
 *
 * The admin session is only used to create the account. The cookie that
 * remains is the owner's.
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<number>} The owner's user id
 */
export async function prepareOwner(page) {
  await signInAsAdmin(page);
  await ensureAccount(page, OWNER);
  await resetWorkspace(page);
  const response = await page.request.post("/account/signin", {
    data: { email: OWNER.email, password: OWNER.password }
  });
  const text = await response.text();
  expect(response.ok(), `could not sign in ${OWNER.email}: ${text}`).toBe(true);
  const body = JSON.parse(text);
  expect(body.error, JSON.stringify(body.error)).toBeUndefined();
  expect(body.user?.id, "the session named no user").toBeTruthy();
  return body.user.id;
}

/**
 * Boot as a guest, on a freshly seeded database.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function bootGuest(page) {
  await signInAsAdmin(page);
  await resetWorkspace(page);
  await page.context().clearCookies();
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();
}

/**
 * The bundle ids painted on one surface, left to right.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} selector
 * @param {string} prefix
 * @returns {Promise<string[]>}
 */
async function surfaceIds(page, selector, prefix) {
  return page.locator(selector).evaluateAll((els, start) => {
    return els.map((el) => el.id.slice(start.length));
  }, prefix);
}

/**
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<string[]>}
 */
export async function desktopIds(page) {
  await expect(page.locator(".desktop-icon").first()).toBeVisible();
  return surfaceIds(page, ".desktop-icon", "desktop-icon-");
}

/**
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<string[]>}
 */
export async function dockIds(page) {
  return surfaceIds(page, "#os-dock .app-icon", "DockButton_");
}

/**
 * Replace the owner's lists. Names are filled by the server on the next read.
 *
 * @param {import('@playwright/test').Page} page
 * @param {number} userId
 * @param {string[]} desktop
 * @param {string[]} dock
 */
export async function putWorkspace(page, userId, desktop, dock) {
  const link = (bundleId) => ({ bundleId, name: bundleId, icon: "icon.svg" });
  const response = await page.request.put(`${API}/workspace/${userId}`, {
    data: {
      desktop: desktop.map(link),
      dock: dock.map(link)
    }
  });
  expect(response.ok(), `could not save the workspace: ${await response.text()}`)
    .toBe(true);
}

/**
 * Reload and wait until the desktop has been painted again.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function reloadWorkspace(page) {
  await page.reload();
  await page.locator(".desktop-icon").first().waitFor();
}
