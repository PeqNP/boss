// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F0 — App shell and role gating.
 *
 * The first thing to prove about any app: it launches, `GET /me` decides what
 * the menu offers, and the About modal opens. Everything else in
 * `ui-plan.md` assumes this works.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, signInAsAdmin, openApplication, windowByTitle, clickMenuItem } from "../lib/boss.js";

const PRODUCTION = "io.bithead.production";

function menuOption(page, value) {
  return page.locator(`select[name="production-menu"] option[value="${value}"]`);
}

test.describe("Production — app shell", () => {
  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
  });

  test("the app launches @shell", async ({ page }) => {
    await expect(menuOption(page, "active-jobs")).toBeAttached();
  });

  test("an admin is offered the admin screens @shell", async ({ page }) => {
    // `applicationDidStart` removes these for anyone who is not a super user,
    // so their presence is what proves `GET /me` was read.
    for (const option of ["jobs", "production-lines", "pools"]) {
      await expect(menuOption(page, option)).toBeAttached();
    }
  });

  test("About opens from the menu @shell", async ({ page }) => {
    await clickMenuItem(page, "production-menu", "About Production");
    await expect(windowByTitle(page, "About Production")).toBeVisible();
  });
});
