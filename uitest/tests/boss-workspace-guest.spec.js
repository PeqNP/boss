// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * What a guest sees, and what they cannot change.
 *
 * The seed itself is the private suite. This proves the desktop paints it,
 * Applications does not offer Add, and a right-click does not open Delete.
 */

import { test, expect } from "@playwright/test";
import { bootGuest, desktopIds, dockIds, GUEST_DESKTOP } from "../lib/workspace.js";

test("a guest sees the seeded desktop and cannot change it", async ({ page }) => {
  await bootGuest(page);

  expect(await desktopIds(page)).toEqual(GUEST_DESKTOP);
  expect(await dockIds(page), "a guest dock has an icon").toEqual([]);

  await page.evaluate(() => os.ui.showInstalledApplications());
  await expect(page.locator("button[name='add-desktop']")).toBeDisabled();
  await expect(page.locator("button[name='add-dock']")).toBeDisabled();
  await page.locator("[id='app-container-io.bithead.applications'] .close-button")
    .click();

  await page.locator(".desktop-icon").first().click({ button: "right" });
  await expect(page.locator(".ui-context-menu")).toHaveCount(0);
});
