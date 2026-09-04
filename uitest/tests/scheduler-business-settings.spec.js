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
         openApplication, openController, windowByTitle, settled , closeAll } from "../lib/boss.js";
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

  // A window left open outlives its test — see `ui-plan.md`.
  test.afterEach(async ({ page }) => {
    await closeAll(page);
  });

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

  test("save business config", async ({ page }) => {
    const win = await openSettings(page);

    const name = win.locator("input[name='biz-name']");
    await name.fill("Dana's Hair Studio");
    // Leaving the field is what saves — there is no Save button.
    await name.blur();
    await expect(win.locator(".ui-window-message")).toContainText("Saved");

    expect((await config(page, businessId)).name).toBe("Dana's Hair Studio");
  });

  test("reject empty business name", async ({ page }) => {
    const win = await openSettings(page);

    const name = win.locator("input[name='biz-name']");
    await name.fill("");
    await name.blur();

    // A rejected save must also leave the stored name alone.
    await expect(win.locator(".ui-window-message"))
      .toContainText("business name is required");
    expect((await config(page, businessId)).name).toBe("Dana's Salon");
  });

  test("remember the business type", async ({ page }) => {
    let win = await openSettings(page, "Business Type");

    await expect(win.locator("[name='selected-template-name']"))
      .toHaveText("None");

    const card = win.locator(".template-card").filter({ hasText: "Pet Services" });
    await expect(card).toBeVisible();
    await card.click();
    await page.locator(".ui-modal", { hasText: "Reconfigure your business" })
      .locator("button", { hasText: "OK" }).click();

    await expect
      .poll(async () => (await config(page, businessId)).templateId,
            { message: "the choice never reached the server" })
      .toBeGreaterThan(0);

    // Reopened, because the window sets that label as the card is clicked. It
    // read `None` again next time until the choice was stored.
    await closeAll(page);
    win = await openSettings(page, "Business Type");
    await expect(win.locator("[name='selected-template-name']"))
      .toHaveText("Pet Services");
  });

  test("save operating hours", async ({ page }) => {
    const win = await openSettings(page, "Schedule");

    // Tuesday, which is row 2 of the week the table draws.
    await win.locator("input[name='hours-open-2']").fill("07:30");
    await win.locator("input[name='hours-close-2']").fill("19:00");
    // Clicked away from, because the panel saves a field when it is left and
    // `Tab` inside a `time` input moves between its hour and minute rather
    // than out of the field.
    await win.locator("input[name='cutoff-days']").click();

    await expect
      .poll(async () => {
        const day = (await config(page, businessId)).operatingHours
          .find((h) => h.dayOfWeek === 2);
        return day && [day.openTime, day.closeTime];
      }, { message: "the hours never reached the server" })
      .toEqual(["07:30", "19:00"]);

    // The rest of the week is untouched. The whole table is sent on every
    // save, so one day's edit writing over another is what this refuses.
    const monday = (await config(page, businessId)).operatingHours
      .find((h) => h.dayOfWeek === 1);
    expect([monday.openTime, monday.closeTime], "another day moved")
      .toEqual(["09:00", "17:00"]);
  });

  test("close a day", async ({ page }) => {
    const win = await openSettings(page, "Schedule");

    await win.locator("input[name='hours-closed-0']").check();

    await expect
      .poll(async () => (await config(page, businessId)).operatingHours
              .find((h) => h.dayOfWeek === 0).isClosed,
            { message: "the closed day never reached the server" })
      .toBe(true);

    // A day the business is shut offers nothing, which is the point of the
    // flag rather than of the hours beside it.
    const slots = await (await page.request.get(
      `${API}/kiosk/${businessId}/calendar?year=2026&month=12`)).json();
    const sundays = (slots.days || []).filter((d) => d.date.endsWith("-06"));
    for (const day of sundays) {
      expect(day.available, `${day.date} is offered on a closed day`)
        .toBe(false);
    }
  });

  test("save slot mode", async ({ page }) => {
    const win = await openSettings(page, "Schedule");

    await win.locator("input[name='slot-mode'][value='unlimited']").check();

    await expect
      .poll(async () => (await config(page, businessId)).slotMode,
            { message: "the slot mode never reached the server" })
      .toBe("unlimited");

    // The note beneath says what hours mean in this mode: under `unlimited`
    // every increment the business is open is offered and nobody is allocated.
    await expect(win.locator("[name='hours-note']")).not.toBeEmpty();
  });

  test("save reminder enabled", async ({ page }) => {
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
