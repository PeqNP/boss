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
         openApplication, openController, windowByTitle, settled , closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler appointment lookup", () => {
  let businessId;
  let jobCode;
  let jobId;

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
    const what = await readyToBook(page, businessId);
    jobId = await book(page, businessId, what, "2026-12-14", "10:00");

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

  test("verify appointment access",
       async ({ page }) => {
    const win = await openLookup(page);

    await win.locator("input[name='job-code']").fill(jobCode);
    await win.locator("button", { hasText: "Continue" }).click();

    // The step names where the code was sent, so the customer knows which
    // phone to check.
    await expect(win.locator("[name='step-verify']")).toBeVisible();
    await expect(win.locator("[name='verify-destination']")).not.toBeEmpty();

    const sent = await lastMessage(page);
    const code = (sent.message.match(/\b\d{4,8}\b/) || [])[0];
    expect(code, `no code in what was sent: ${sent.message}`).toBeTruthy();

    await win.locator("input[name='verify-code']").fill(code);
    await win.locator("button", { hasText: "Verify" }).click();

    // Appointment is a `.ui-kiosk` rather than a titled window, so it is found
    // by its container.
    const appointment = page.locator(".ui-kiosk", { hasText: "Your Appointment" });
    await expect(appointment).toBeVisible();

    // Closed the way a customer closes it. Left open, it outlives the test:
    // the next one's setup then times out and tearing the context down takes
    // twenty minutes rather than a second.
    await appointment.locator("button", { hasText: "Close" }).first().click();
    await expect(appointment).toBeHidden();
  });

  test("reject wrong access code", async ({ page }) => {
    const win = await openLookup(page);

    await win.locator("input[name='job-code']").fill(jobCode);
    await win.locator("button", { hasText: "Continue" }).click();
    await expect(win.locator("[name='step-verify']")).toBeVisible();

    await win.locator("input[name='verify-code']").fill("000000");
    await win.locator("button", { hasText: "Verify" }).click();

    // A wrong code keeps the customer on the step to try again. It is not an
    // error.
    await expect(win.locator("[name='step-verify']")).toBeVisible();
    await expect(page.locator(".ui-kiosk", { hasText: "Your Appointment" }))
      .toBeHidden();
  });

  test("refuse an appointment nobody proved was theirs", async ({ page }) => {
    // A browser holding no session, naming the appointment the way the routes
    // used to take it. The verification code is the only way in, so an id has
    // to open nothing — ids are sequential, and this one is real.
    const stranger = await page.context().browser()
      .newContext({ ignoreHTTPSErrors: true });
    const anon = await stranger.newPage();

    const read = await anon.request.get(`${API}/appointment/${jobId}`);
    expect(read.status(), "an id read the appointment").toBe(404);

    const moved = await anon.request.put(
      `${API}/appointment/${jobId}/reschedule`,
      { data: { scheduledDate: "2026-12-15", scheduledTime: "11:00" } });
    expect(moved.status(), "an id moved the appointment").toBe(404);

    const killed = await anon.request.delete(`${API}/appointment/${jobId}`);
    expect(killed.status(), "an id cancelled the appointment").toBe(404);
    await stranger.close();

    // 404 rather than a refusal, so the answer never says which ids are real.
    const job = await (await page.request.get(
      `${API}/business/${businessId}/job/${jobId}`)).json();
    expect(job.status, "the appointment did not survive").toBe("confirmed");
  });

  test("reject unknown job code", async ({ page }) => {
    const win = await openLookup(page);

    await win.locator("input[name='job-code']").fill("ZZZZZZ");
    await win.locator("button", { hasText: "Continue" }).click();

    await expect(win.locator("[name='step-verify']")).toBeHidden();
  });
});
