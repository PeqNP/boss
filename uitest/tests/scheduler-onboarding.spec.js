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
import { signInAsAdmin, ensureAccount, account, signInAs, bootBOSS,
         openApplication, windowByTitle, settled, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler onboarding", () => {
  test.afterEach(async ({ page }) => {
    await closeAll(page);
  });

  test("open a business for somebody who runs none", async ({ page }) => {
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

  test("offer the business types to somebody who runs none", async ({ page }) => {
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

  test("refuse a booking until the business is named", async ({ page }) => {
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
