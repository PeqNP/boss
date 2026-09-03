// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 8 — the operator's view of the work.
 *
 * A month, a week and a day are the same appointments read at three widths,
 * and the routes narrow by who is asking — so one calendar serves the operator
 * and the employee both. What this proves is that each width draws what was
 * booked and that a day leads to the job.
 *
 * Which appointments belong to a day is settled in the private suite. See
 * `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, clickMenuItem,
         settled , closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

/**
 * A day this week, far enough ahead to be bookable.
 *
 * Inside the week the calendar opens on, so no view has to be navigated to
 * reach it — and formatted locally, because that is how the calendar reckons
 * a day. Formatting in UTC picks the day after, west of Greenwich.
 */
function soon() {
  const when = new Date();
  const sunday = new Date(when);
  sunday.setDate(sunday.getDate() - sunday.getDay());
  // Tomorrow, unless tomorrow is next week; then the last day of this one.
  when.setDate(when.getDate() + 1);
  if (when - sunday >= 7 * 86400000) {
    when.setDate(sunday.getDate() + 6);
  }
  const month = String(when.getMonth() + 1).padStart(2, "0");
  const day = String(when.getDate()).padStart(2, "0");
  return `${when.getFullYear()}-${month}-${day}`;
}

test.describe("scheduler calendar", () => {
  let businessId;
  let date;

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
    date = soon();
    await book(page, businessId, what, date, "10:00");

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /** The calendar, which retitles itself to whatever it is showing. */
  async function openCalendar(page) {
    await openController(page, "io.bithead.scheduler", "ScheduleCalendar");
    const win = page.locator(".ui-window").filter({
      has: page.locator(".cal-month-grid")
    });
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  test("schedule month", async ({ page }) => {
    const win = await openCalendar(page);

    // it: the day carries a count rather than being drawn blank
    const booked = win.locator(".cal-cell.has-jobs");
    await expect(booked).toHaveCount(1);
    await expect(booked).toContainText("1 job");
  });

  test("schedule day",
       async ({ page }) => {
    const win = await openCalendar(page);

    await win.locator(".cal-cell.has-jobs").click();

    // it: the day view draws the appointment
    const job = win.locator(".day-job");
    await expect(job).toHaveCount(1);
    await expect(job).toContainText("Haircut");

    // it: and tapping it opens the job
    await job.click();
    await expect(windowByTitle(page, "Job")).toBeVisible();
  });

  test("schedule week", async ({ page }) => {
    const win = await openCalendar(page);

    await win.locator("button", { hasText: "Week" }).click();
    await expect(win.locator(".week-col")).toHaveCount(7);

    // it: draws it in the column its day falls in, and draws the week Sunday
    // through Saturday with each day once. The seven columns alone prove
    // nothing — they are drawn whether or not anything was booked.
    const headers = await win.locator(".week-col-header").allTextContents();
    expect(new Set(headers).size, "a day is drawn twice").toBe(7);
    await expect(win.locator(".week-job:not(.empty)", { hasText: "Haircut" })
                    .first()).toBeVisible();
  });
});
