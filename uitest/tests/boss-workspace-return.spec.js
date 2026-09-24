// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Signing out and back.
 *
 * Sign out paints the guest desktop. Signing in again paints the order that
 * was saved, not the guest list.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS } from "../lib/boss.js";
import { desktopIds, GUEST_DESKTOP, OWNER, prepareOwner, putWorkspace,
         USER_DESKTOP, USER_DOCK } from "../lib/workspace.js";

const SAVED = [
  "io.bithead.wordy",
  "io.bithead.json-formatter",
  "io.bithead.tutorial",
  "io.bithead.scheduler"
];

test("sign out shows the guest, and sign in shows the saved order", async ({ page }) => {
  const userId = await prepareOwner(page);
  await putWorkspace(page, userId, SAVED, USER_DOCK);
  await bootBOSS(page);
  await page.locator(".desktop-icon").first().waitFor();
  expect(await desktopIds(page)).toEqual(SAVED);

  await page.evaluate(() => os.logOut());
  const confirm = page.locator(".ui-modal", { hasText: "log out" });
  await confirm.locator("button", { hasText: "OK" }).click();
  await expect(page.locator(`[id="desktop-icon-${GUEST_DESKTOP[2]}"]`))
    .toBeVisible();
  expect(await desktopIds(page)).toEqual(GUEST_DESKTOP);

  const signIn = page.locator(".ui-modal", { hasText: "Sign In" });
  await signIn.locator("input[name='email']").fill(OWNER.email);
  await signIn.locator("input[name='password']").fill(OWNER.password);
  await signIn.locator("button", { hasText: "Sign in" }).click();
  await expect.poll(async () => (await desktopIds(page))[0]).toBe(SAVED[0]);
  expect(await desktopIds(page)).toEqual(SAVED);
  expect(USER_DESKTOP).not.toEqual(SAVED);
});
