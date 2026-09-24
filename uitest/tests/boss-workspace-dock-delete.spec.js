// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Delete on a dock icon.
 *
 * The menu calls DELETE for that bundle. The icon leaves, a reload keeps it
 * gone, and an app that was never on the desktop is still not there.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { desktopIds, dockIds, prepareOwner, putWorkspace, reloadWorkspace,
         USER_DESKTOP, USER_DOCK } from "../lib/workspace.js";

const LEAN = "io.bithead.lean-visualizer";
const MUSIC = "io.bithead.music";

test("Delete removes a dock icon and keeps it gone", async ({ page }) => {
  const userId = await prepareOwner(page);
  await putWorkspace(
    page,
    userId,
    USER_DESKTOP,
    USER_DOCK.concat(LEAN)
  );
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();

  const removed = page.waitForResponse((response) => {
    return response.request().method() === "DELETE"
      && response.url().includes(`/workspace/dock/${userId}/${LEAN}`);
  });
  await page.locator(`[id="DockButton_${LEAN}"]`).click({ button: "right" });
  await page.locator(".ui-context-menu .ui-popup-choice", { hasText: "Delete" })
    .click();
  expect((await removed).ok(), "the dock Delete was refused").toBe(true);
  await expect(page.locator(`[id="DockButton_${LEAN}"]`)).toHaveCount(0);
  await expect(page.locator("#os-dock")).toBeVisible();

  await reloadWorkspace(page);
  expect(await dockIds(page)).toEqual(USER_DOCK);
  expect(await desktopIds(page)).not.toContain(MUSIC);
});
