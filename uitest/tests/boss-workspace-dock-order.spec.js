// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Dragging a dock icon saves the new order.
 *
 * The drop is the wiring. A reload paints the order the server kept.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { dockIds, prepareOwner, putWorkspace, reloadWorkspace, USER_DESKTOP,
         USER_DOCK } from "../lib/workspace.js";

const DOCK = USER_DOCK.concat("io.bithead.wordy");

test("a dock drag is still the order after a reload", async ({ page }) => {
  const userId = await prepareOwner(page);
  await putWorkspace(page, userId, USER_DESKTOP, DOCK);
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();
  expect(await dockIds(page)).toEqual(DOCK);

  const saved = page.waitForResponse((response) => {
    return response.request().method() === "PUT"
      && response.url().includes("/workspace/");
  });
  const icons = page.locator("#os-dock .app-icon");
  await icons.nth(0).dragTo(icons.nth(1));
  expect((await saved).ok(), "the drag did not save").toBe(true);

  const order = await dockIds(page);
  expect(order).not.toEqual(DOCK);
  await reloadWorkspace(page);
  expect(await dockIds(page)).toEqual(order);
});
