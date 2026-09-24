// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The first load of a signed-in account.
 *
 * The starting list is decided by the private suite. This proves that load
 * paints it on the desktop and in the dock.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { desktopIds, dockIds, prepareOwner, USER_DESKTOP, USER_DOCK }
  from "../lib/workspace.js";

test("a new account sees the starting desktop and dock", async ({ page }) => {
  await prepareOwner(page);
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();

  expect(await desktopIds(page)).toEqual(USER_DESKTOP);
  expect(await dockIds(page)).toEqual(USER_DOCK);
});
