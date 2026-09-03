// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 9 — an appointment as the operator works it.
 *
 * Where a job is moved, given to somebody, finished, and paid for. Each of
 * those is a write the screen has to read back: what was collected against an
 * appointment is what the business is owed, and a payment that reported
 * success without landing is the one failure nobody notices until the money is
 * counted.
 *
 * What a payment means — deposit, part payment, written off — is settled in
 * the private suite. See `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled, action,
         docAction, selectPopupOption, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

/** Tomorrow, which every rule here leaves alone. */
function tomorrow() {
  const when = new Date();
  when.setDate(when.getDate() + 1);
  const month = String(when.getMonth() + 1).padStart(2, "0");
  const day = String(when.getDate()).padStart(2, "0");
  return `${when.getFullYear()}-${month}-${day}`;
}

test.describe("scheduler job", () => {
  let businessId;
  let jobId;
  let what;

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
    what = await readyToBook(page, businessId);
    jobId = await book(page, businessId, what, tomorrow(), "10:00");

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /** What the server holds for this appointment. */
  async function job(page) {
    const response = await page.request.get(
      `${API}/business/${businessId}/job/${jobId}`);
    expect(response.ok(), `could not read the job: ${await response.text()}`)
      .toBe(true);
    return response.json();
  }

  async function openJob(page) {
    await openController(page, "io.bithead.scheduler", "Job", jobId);
    const win = windowByTitle(page, "Job");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  test("reschedule job", async ({ page }) => {
    const win = await openJob(page);

    await win.locator("input[name='scheduled-date']").fill("2026-12-24");
    await win.locator("input[name='scheduled-time']").fill("09:30");
    await docAction(win, "save").click();

    // The save must reach the server, not just update the screen.
    await expect.poll(async () => (await job(page)).scheduledDate,
                      { message: "the save never reached the server" })
      .toBe("2026-12-24");
    expect((await job(page)).scheduledTime).toBe("09:30");
  });

  test("add payment", async ({ page }) => {
    const win = await openJob(page);

    await win.locator("input[name='payment-amount']").fill("25");
    await selectPopupOption(win, "payment-method", "Cash");
    await action(win, "addPayment").click();

    await expect(win.locator("[name='payment-status']")).not.toBeEmpty();

    await expect
      .poll(async () => (await job(page)).transactions.length,
            { message: "the payment reported success and landed nowhere" })
      .toBe(1);
  });

  test("cancel job", async ({ page }) => {
    const win = await openJob(page);

    await win.locator("button[name='cancel-job-btn']").click();
    await page.locator(".ui-modal", { hasText: "Cancel this appointment?" })
      .locator("button", { hasText: "OK" }).click();

    await expect.poll(async () => (await job(page)).status,
                      { message: "the cancellation never reached the server" })
      .toBe("cancelled");
  });

  test("reject empty payment", async ({ page }) => {
    const win = await openJob(page);

    await win.locator("input[name='payment-amount']").fill("0");
    await selectPopupOption(win, "payment-method", "Cash");
    await action(win, "addPayment").click();

    // The alert is the assertion. The server refuses a zero payment too, so an
    // empty transaction list passes even with the screen's own check deleted.
    await expect(page.locator(".ui-modal, .ui-window")
                     .filter({ hasText: "amount that was paid" })).toBeVisible();
    expect((await job(page)).transactions.length).toBe(0);
  });

  test("reject payment without method", async ({ page }) => {
    const win = await openJob(page);

    await win.locator("input[name='payment-amount']").fill("25");
    await action(win, "addPayment").click();

    // Same as above: the alert is the part only this screen does.
    expect((await job(page)).transactions.length).toBe(0);
    await expect(page.locator(".ui-modal, .ui-window")
                     .filter({ hasText: "how it was paid" })).toBeVisible();
  });
});
