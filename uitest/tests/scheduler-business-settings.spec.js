// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 3 — the settings an operator chooses for their business.
 *
 * The screen writes as the owner works: leaving a field saves it, and so does
 * ticking a box or choosing from a menu. There is no Save button, which is
 * what makes this worth a test — a field wired to nothing looks exactly like a
 * field that saved.
 *
 * What the settings mean is settled in the private suite. What this proves is
 * that each tab reaches the route and that the value comes back. See
 * `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

/** The Business Settings window, open on a tab. */
async function openSettings(page, tab) {
  await openApplication(page, "io.bithead.scheduler");

  // Wait for the app to have read `/me`. `openApplication` returns once the
  // container is attached, which is before `applicationDidStart` has finished
  // — and every controller here reads `getBusinessId()`, which is null until
  // it has.
  await expect(page.locator(".ui-window")).toBeVisible();

  await openController(page, "io.bithead.scheduler", "BusinessConfig");
  const win = windowByTitle(page, "Business Settings");
  await expect(win).toBeVisible();
  await settled(win);
  if (tab) {
    await win.locator(".settings-nav .option", { hasText: tab }).click();
  }
  return win;
}

/** What the server holds for this business. */
async function config(page, businessId) {
  const response = await page.request.get(`${API}/business/${businessId}/config`);
  expect(response.ok(), `could not read the config: ${await response.text()}`)
    .toBe(true);
  return response.json();
}

test.describe("scheduler business settings", () => {
  let businessId;

  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);
    await signInAsOperator(page);
    const response = await page.request.post(`${API}/signup`, {
      data: { name: "Dana's Salon", timezone: "America/Los_Angeles" }
    });
    expect(response.ok(), `signup failed: ${await response.text()}`).toBe(true);
    businessId = (await response.json()).businessId;

    // The Operator role is minted into the token at the next sign-in, so a
    // session opened before the signup carries none — and every route here
    // wants one. See `acl+api.swift` on `assignRole`.
    await signInAsOperator(page);
    await bootBOSS(page);
  });

  test("leaving a text field writes it", async ({ page }) => {
    const win = await openSettings(page);

    const name = win.locator("input[name='biz-name']");
    await name.fill("Dana's Hair Studio");
    // Leaving the field is what saves — there is no Save button.
    await name.blur();
    await expect(win.locator(".ui-window-message")).toContainText("Saved");

    expect((await config(page, businessId)).name).toBe("Dana's Hair Studio");
  });

  test("an empty business name is refused rather than written", async ({ page }) => {
    const win = await openSettings(page);

    const name = win.locator("input[name='biz-name']");
    await name.fill("");
    await name.blur();

    // it: says so, and leaves what was there
    await expect(win.locator(".ui-window-message"))
      .toContainText("business name is required");
    expect((await config(page, businessId)).name).toBe("Dana's Salon");
  });

  test("ticking a box on another tab writes it", async ({ page }) => {
    // Reminders live under Schedule, beside the times they are reckoned from,
    // rather than under Notifications.
    const win = await openSettings(page, "Schedule");

    const reminder = win.locator("input[name='reminder-enabled']");
    const before = (await config(page, businessId)).reminderEnabled;
    await reminder.setChecked(!before);

    await expect
      .poll(async () => (await config(page, businessId)).reminderEnabled,
            { message: "the reminder toggle never reached the server" })
      .toBe(!before);
  });
});
