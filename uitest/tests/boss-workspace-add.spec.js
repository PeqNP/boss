// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Applications places an installed app on the desktop or in the dock.
 *
 * The button is the wiring. After it is used, that same button is disabled
 * because the app is already there.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { desktopIds, dockIds, prepareOwner } from "../lib/workspace.js";

/**
 * Choose one installed app in Applications.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} bundleId
 */
async function choose(page, bundleId) {
  await page.evaluate(() => os.ui.showInstalledApplications());
  await page.locator("button[name='add-desktop']").waitFor();
  await page.evaluate((id) => {
    document.querySelector("select[name='applications']").ui.selectValue(id);
  }, bundleId);
}

test("Add places an app on the desktop and in the dock", async ({ page }) => {
  await prepareOwner(page);
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();

  await choose(page, "io.bithead.music");
  const added = page.waitForResponse((response) => {
    return response.request().method() === "PUT"
      && response.url().includes("/workspace/");
  });
  await page.locator("button[name='add-desktop']").click();
  expect((await added).ok(), "Add to Desktop was refused").toBe(true);
  await expect(page.locator("button[name='add-desktop']")).toBeDisabled();
  expect(await desktopIds(page)).toContain("io.bithead.music");

  await choose(page, "io.bithead.lean-visualizer");
  const docked = page.waitForResponse((response) => {
    return response.request().method() === "PUT"
      && response.url().includes("/workspace/");
  });
  await page.locator("button[name='add-dock']").click();
  expect((await docked).ok(), "Add to Dock was refused").toBe(true);
  await expect(page.locator("button[name='add-dock']")).toBeDisabled();
  expect(await dockIds(page)).toContain("io.bithead.lean-visualizer");
});
