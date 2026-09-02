// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 7 — a customer letting themselves back in.
 *
 * A job code says which appointment; a code sent to the contact they gave says
 * it is them. Six wrong codes closes the door for good, and the operator still
 * changes the appointment from the admin screens.
 *
 * The code goes to a phone nobody is holding during a test, so the app records
 * what a vendor would have sent — see `lib/notify.py`, wired in development
 * only. Without it the verify step cannot be reached at all. See `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler appointment lookup", () => {
  let businessId;
  let jobCode;

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
    const what = await readyToBook(page, businessId);
    const jobId = await book(page, businessId, what, "2026-12-14", "10:00");

    // The code the customer is given, which is the only thing they hold.
    const job = await (await page.request.get(
      `${API}/business/${businessId}/job/${jobId}`)).json();
    jobCode = job.jobCode;
    expect(jobCode, "the booking carries no job code").toBeTruthy();

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  async function openLookup(page) {
    await openController(page, "io.bithead.scheduler", "AppointmentLookup");
    const win = windowByTitle(page, "Find Your Appointment");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  /** What a vendor would have sent, most recently. Development only. */
  async function lastMessage(page) {
    const response = await page.request.get(`${API}/debug/last-message`);
    expect(response.ok(), "the development recorder is not wired").toBe(true);
    return response.json();
  }

  test("a job code and the code sent for it open the appointment",
       async ({ page }) => {
    const win = await openLookup(page);

    await win.locator("input[name='job-code']").fill(jobCode);
    await win.locator("button", { hasText: "Continue" }).click();

    // it: asks for the code it just sent, and says where it went
    await expect(win.locator("[name='step-verify']")).toBeVisible();
    await expect(win.locator("[name='verify-destination']")).not.toBeEmpty();

    const sent = await lastMessage(page);
    const code = (sent.message.match(/\b\d{4,8}\b/) || [])[0];
    expect(code, `no code in what was sent: ${sent.message}`).toBeTruthy();

    await win.locator("input[name='verify-code']").fill(code);
    await win.locator("button", { hasText: "Verify" }).click();

    // it: the appointment opens, which is the whole point of the code.
    // `Appointment` is a `.ui-kiosk` like the booking flow — it is a customer
    // surface — so it is found by its container rather than by title.
    await expect(page.locator(".ui-kiosk", { hasText: "Your Appointment" }))
      .toBeVisible();
  });

  test("a code that is not the one sent is refused", async ({ page }) => {
    const win = await openLookup(page);

    await win.locator("input[name='job-code']").fill(jobCode);
    await win.locator("button", { hasText: "Continue" }).click();
    await expect(win.locator("[name='step-verify']")).toBeVisible();

    await win.locator("input[name='verify-code']").fill("000000");
    await win.locator("button", { hasText: "Verify" }).click();

    // it: stays on the step and says so — a wrong code is an answer, not an
    // error, and the customer tries again
    await expect(win.locator("[name='step-verify']")).toBeVisible();
    await expect(page.locator(".ui-kiosk", { hasText: "Your Appointment" }))
      .toBeHidden();
  });

  test("a job code nobody holds is refused", async ({ page }) => {
    const win = await openLookup(page);

    await win.locator("input[name='job-code']").fill("ZZZZZZ");
    await win.locator("button", { hasText: "Continue" }).click();

    // it: never reaches the step that asks for a code
    await expect(win.locator("[name='step-verify']")).toBeHidden();
  });
});
