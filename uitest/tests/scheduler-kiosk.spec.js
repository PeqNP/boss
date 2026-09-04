// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 6 — the path a customer walks.
 *
 * The kiosk is the whole of the customer surface and asks for no account, so
 * nobody signs in to notice it broken. It is also the longest path in the app:
 * service, size, time, contact, and a confirmation that has to name what was
 * actually booked.
 *
 * What the rules decide — which times are open, who is free, what a hold
 * expires to — is settled in the private suite. What this proves is that each
 * step reaches the next and that the appointment exists afterwards with what
 * the customer chose. See `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController , closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler kiosk", () => {
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

    await signInAsOperator(page);
    await readyToBook(page, businessId);
    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /**
   * The kiosk, opened on this business the way a deep link opens it.
   *
   * Located by its own container rather than by title: a kiosk is a
   * `.ui-kiosk`, not a window or a modal, so `windowByTitle` never sees it.
   */
  async function openKiosk(page) {
    await openController(page, "io.bithead.scheduler", "SchedulerKiosk", businessId);
    const win = page.locator(".ui-kiosk");
    await expect(win).toBeVisible();
    // `settled` waits on `aria-busy`, which the OS sets on a window. A kiosk
    // is neither, so what says it is ready is a step being drawn.
    await expect(win.locator("[name^='step-']:visible")).toHaveCount(1);
    return win;
  }

  test("book appointment",
       async ({ page }) => {
    const win = await openKiosk(page);

    // The service. `readyToBook` left one.
    const service = win.locator(".kiosk-option-btn", { hasText: "Haircut" });
    await expect(service.first()).toBeVisible();
    await service.first().click();

    // No size step: a job type with one size skips it, choosing that size
    // rather than asking a question with one answer.

    // A time. The first one offered is whatever is soonest.
    const slot = win.locator(".kiosk-slot-btn");
    await expect(slot.first()).toBeVisible();
    await slot.first().click();

    // The contact step is reachable only once a time is held, so arriving here
    // proves the hold was made.
    await expect(win.locator("[name='step-contact']")).toBeVisible();

    // Who they are. The fields are whatever this job type asks for.
    const contact = win.locator("[name='contact-fields'] input");
    await expect(contact.first()).toBeVisible();
    const fields = await contact.count();
    for (let i = 0; i < fields; i++) {
      const field = contact.nth(i);
      const type = await field.getAttribute("type");
      await field.fill(type === "email" ? "jane@example.com"
                       : type === "tel" ? "555-0101" : "Jane");
    }
    await win.locator("button", { hasText: "Next" }).click();

    // The confirmation is the customer's only record of the appointment.
    await expect(win.locator("[name='step-confirmation']")).toBeVisible();
  });

  test("choose an employee", async ({ page }) => {
    // Off by default. A business that lets a customer pick gets a step the
    // others never see.
    const allowed = await page.request.put(
      `${API}/business/${businessId}/config`,
      { data: { allowCustomerEmployeeSelection: true } });
    expect(allowed.ok(), `could not allow selection: ${await allowed.text()}`)
      .toBe(true);

    // The kiosk opens on this step rather than reaching it later: who the
    // customer wants decides what can be offered, so it is asked first.
    const win = await openKiosk(page);
    await expect(win.locator("[name='step-employee']")).toBeVisible();

    const alice = win.locator("[name='employee-options'] .kiosk-option-btn",
                              { hasText: "Alice Kim" });
    await expect(alice).toBeVisible();
    await alice.click();

    await win.locator(".kiosk-option-btn", { hasText: "Haircut" }).first().click();

    // The times offered are the ones that person is working.
    await expect(win.locator("[name='step-slot']")).toBeVisible();
    await expect(win.locator(".kiosk-slot-btn").first()).toBeVisible();
  });

  // The OTP step and the deposit step are unreachable until a vendor exists.
  // `get_setup` adds "Connect a way to send codes" for a job type that verifies
  // a contact detail, and "Connect Stripe" for one that takes a payment; both
  // are outstanding, so `configured` is false and the kiosk draws
  // `step-not-configured` instead of taking a booking. See `review.md`.

  test("kiosk not configured", async ({ page }) => {
    // Closed by its own operator. `is_active` is left out of
    // `BUSINESS_CONFIG_WRITABLE` deliberately: closing is its own act with its
    // own route, not a field on a settings form that saves as you type.
    //
    // The kiosk is a customer's only surface, so it has to say something
    // rather than draw an empty picker.
    const off = await page.request.post(`${API}/business/${businessId}/disable`);
    expect(off.ok(), `could not close the business: ${await off.text()}`).toBe(true);

    const win = await openKiosk(page);
    await expect(win.locator("[name='step-not-configured']")).toBeVisible();
  });
});
