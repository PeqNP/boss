// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Delete on a desktop icon.
 *
 * The menu is the wiring: it calls DELETE for that bundle, the icon leaves,
 * and a reload does not bring it back. Scheduler stays in the dock.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { desktopIds, dockIds, prepareOwner, putWorkspace, reloadWorkspace,
         USER_DESKTOP, USER_DOCK } from "../lib/workspace.js";

const MUSIC = "io.bithead.music";

test("Delete removes a desktop icon and keeps it gone", async ({ page }) => {
  const userId = await prepareOwner(page);
  await putWorkspace(page, userId, USER_DESKTOP.concat(MUSIC), USER_DOCK);
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();

  const removed = page.waitForResponse((response) => {
    return response.request().method() === "DELETE"
      && response.url().includes(`/workspace/desktop/${userId}/${MUSIC}`);
  });
  await page.locator(`[id="desktop-icon-${MUSIC}"]`).click({ button: "right" });
  await page.locator(".ui-context-menu .ui-popup-choice", { hasText: "Delete" })
    .click();
  expect((await removed).ok(), "the desktop Delete was refused").toBe(true);
  await expect(page.locator(`[id="desktop-icon-${MUSIC}"]`)).toHaveCount(0);

  await reloadWorkspace(page);
  expect(await desktopIds(page)).not.toContain(MUSIC);
  expect(await dockIds(page)).toEqual(USER_DOCK);
});
