// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Dragging a desktop icon saves the new order.
 *
 * The drop is the wiring. A reload paints the order the server kept.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { desktopIds, prepareOwner, reloadWorkspace, USER_DESKTOP }
  from "../lib/workspace.js";

test("a desktop drag is still the order after a reload", async ({ page }) => {
  await prepareOwner(page);
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();
  expect(await desktopIds(page)).toEqual(USER_DESKTOP);

  const saved = page.waitForResponse((response) => {
    return response.request().method() === "PUT"
      && response.url().includes("/workspace/");
  });
  const icons = page.locator(".desktop-icon");
  await icons.nth(0).dragTo(icons.nth(2));
  expect((await saved).ok(), "the drag did not save").toBe(true);

  const order = await desktopIds(page);
  expect(order).not.toEqual(USER_DESKTOP);
  await reloadWorkspace(page);
  expect(await desktopIds(page)).toEqual(order);
});
