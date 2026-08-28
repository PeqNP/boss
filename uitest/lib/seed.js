// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Building a world for a test to run in.
 *
 * An app seeds through its own API rather than its screens. The API enforces
 * the rules, so seeded data is valid by construction — a confirmed booking
 * really holds its slot, a started job really has a frozen version. It is also
 * fast: a full seed runs in well under a second, where the same path through
 * the UI is dozens of clicks that some other flow already covers.
 *
 * What lives here is the part every app shares: emptying the databases, and
 * saving a state to come back to. An app's own seeds go beside these, reaching
 * its own `/api/<bundle_id>` routes.
 *
 * Reset first and every spec is self-sufficient. That matters more than it
 * sounds: the suite runs with one worker against one server and one database,
 * so a file that depended on another having run could not be run on its own —
 * which is exactly what anyone does when something breaks.
 */

import { expect } from "@playwright/test";

const DEBUG = "/api/debug/uitests";

/**
 * Empty every app's database.
 *
 * Development builds only. `GET /debug/uitests/memory` is its counterpart for
 * the BOSS database — users and sessions — and neither touches the other.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function resetDatabase(page) {
  const response = await page.request.get(`${DEBUG}/reset`);
  expect(response.ok(),
         "/api/debug/uitests/reset is development-only, and needs the Python service restarted "
         + "after it was added").toBe(true);
}

/**
 * Save the current state so a later test can return to it.
 *
 * Restoring leaves the snapshot itself intact, so one state can be recovered
 * as often as a file needs — reach it once, then branch from it.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name
 */
export async function saveSnapshot(page, name) {
  expect((await page.request.put(`${DEBUG}/snapshot/${name}`)).ok()).toBe(true);
}

/**
 * Return to a saved state.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name
 */
export async function restoreSnapshot(page, name) {
  expect((await page.request.get(`${DEBUG}/snapshot/${name}`)).ok()).toBe(true);
}
