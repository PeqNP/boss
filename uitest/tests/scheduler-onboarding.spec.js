// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Opening Scheduler for the first time.
 *
 * A business is opened for whoever runs none, unnamed, and `SetupAssistant`
 * asks for the name as the first thing standing between them and a booking.
 * There is no separate screen for creating one: `BusinessConfig` already asks
 * for every field creating one used to.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, ensureAccount,
         account, signInAs, bootBOSS, openApplication, openController,
         windowByTitle, settled, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler onboarding", () => {
  test.afterEach(async ({ page }) => {
    await closeAll(page);
  });

  test("auto-create business", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    // A name nobody has held. `resetDatabase` empties the app's database and
    // never BOSS's, so an account reused between runs already holds the role
    // and the licence this grants.
    const owner = account(`opening-${Date.now()}`);
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    expect((await (await page.request.get(`${API}/me`)).json()).businessId,
           "they run a business before opening the app").toBe(0);

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");

    // The assistant, not a screen for creating a business.
    const assistant = windowByTitle(page, "Setup Assistant");
    await expect(assistant).toBeVisible();
    await settled(assistant);
    await expect(assistant).toContainText("Give your business a name");

    // The session was minted before the business existed. Reaching an
    // operator-only route in this same session is what proves it was minted
    // again — without that every screen below answers 401.
    const me = await (await page.request.get(`${API}/me`)).json();
    expect(me.role, "they are not the operator of what was opened")
      .toBe("Operator");
    const reached = await page.request.get(
      `${API}/business/${me.businessId}/customers`);
    expect(reached.ok(),
           `the new operator cannot reach their own business: ${await reached.text()}`)
      .toBe(true);
  });

  test("business templates", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    const owner = account(`templates-${Date.now()}`);
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    // `BusinessConfig`'s business-type tab offers these, and the operator
    // reaches it the moment their business is opened. So the route cannot be
    // the admin's, and cannot be scoped to a business.
    const response = await page.request.get(`${API}/templates`);
    expect(response.ok(),
           `somebody with a new business cannot list templates: ${response.status()}`)
      .toBe(true);
    const { templates } = await response.json();
    expect(templates.length, "no templates were offered").toBeGreaterThan(0);
  });

  test("list outstanding setup tasks", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    const owner = account(`listing-${Date.now()}`);
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    const win = windowByTitle(page, "Setup Assistant");
    await expect(win).toBeVisible();
    await settled(win);

    const me = await (await page.request.get(`${API}/me`)).json();
    const setup = await (await page.request.get(
      `${API}/business/${me.businessId}/setup`)).json();
    const outstanding = setup.tasks.filter((t) => !t.done);
    expect(outstanding.length, "a new business has nothing outstanding")
      .toBeGreaterThan(0);

    // Every outstanding task, and the count beside them. A screen that drew
    // only the first would still look right with one task left.
    await expect(win.locator(".ui-list-box .option"))
      .toHaveCount(setup.tasks.length);
    await expect(win.locator("[name='remaining']"))
      .toHaveText(outstanding.length === 1
                  ? "1 thing left" : `${outstanding.length} things left`);
    for (const task of outstanding) {
      await expect(win.locator(".ui-list-box .option", { hasText: task.text }))
        .toBeVisible();
    }
  });

  test("open setup task", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    const owner = account(`opening-task-${Date.now()}`);
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    const win = windowByTitle(page, "Setup Assistant");
    await expect(win).toBeVisible();
    await settled(win);

    // The name is the first thing asked for, and `BusinessConfig` is where it
    // is typed. The task carries the tab as well as the window.
    // Each row is an action rather than a choice, so one tap opens it.
    await win.locator(".ui-list-box .option", { hasText: "Give your business a name" })
      .click();

    const settings = windowByTitle(page, "Business Settings");
    await expect(settings).toBeVisible();
    await settled(settings);
    await expect(settings.locator("input[name='biz-name']")).toBeVisible();
  });

  test("say setup is complete", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);
    await signInAsOperator(page);
    const signup = await page.request.post(`${API}/signup`, {
      data: { name: "Dana's Salon", timezone: "America/Los_Angeles" }
    });
    expect(signup.ok(), `signup failed: ${await signup.text()}`).toBe(true);
    const businessId = (await signup.json()).businessId;

    await signInAsOperator(page);
    // Everything a business needs before it can take a booking.
    await readyToBook(page, businessId);
    await expect
      .poll(async () => (await (await page.request.get(
              `${API}/business/${businessId}/setup`)).json()).configured,
            { message: "the business never became ready" })
      .toBe(true);

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    // `applicationDidStart` has to have read `/me` first: the assistant asks
    // for its business the moment it loads, and gets null until it has.
    await expect(page.locator(".ui-window")).toBeVisible();
    await openController(page, "io.bithead.scheduler", "SetupAssistant");
    const win = windowByTitle(page, "Setup Assistant");
    await expect(win).toBeVisible();
    await settled(win);

    // The list gives way once there is nothing to point at.
    await expect(win.locator("[name='ready']")).toBeVisible();
    await expect(win.locator("[name='pending']")).toBeHidden();
  });

  test("reject unnamed business", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    const owner = account(`unnamed-${Date.now()}`);
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();

    const me = await (await page.request.get(`${API}/me`)).json();
    expect(me.businessId, "no business was opened").toBeGreaterThan(0);

    // What a customer is shown. A business nobody has named is not one they
    // can book, so the name is a rule rather than a prompt.
    const kiosk = await (await page.request.get(
      `${API}/kiosk/${me.businessId}`)).json();
    expect(kiosk.configured, "a nameless business takes bookings").toBe(false);
  });
});
