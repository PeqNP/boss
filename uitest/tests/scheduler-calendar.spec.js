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

/** A weekday inside this month, far enough ahead to be bookable. */
function soon() {
  const when = new Date();
  when.setDate(when.getDate() + 3);
  // Kept inside the month the calendar opens on, so no navigating.
  if (when.getMonth() !== new Date().getMonth()) {
    when.setDate(1);
  }
  return when.toISOString().slice(0, 10);
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

  // Pending: switching to the week leaves `[name='week-view']` empty — not a
  // column, not a header, nothing — where the month and the day both draw. The
  // route answers a well-formed week, so this is the view rather than the
  // read. Recorded under Findings in `ui-plan.md`.
  test.fixme("schedule week", async ({ page }) => {
    const win = await openCalendar(page);

    await win.locator("button", { hasText: "Week" }).click();
    await expect(win.locator(".week-col")).toHaveCount(7);

    // Step to the week the booking is in, worked out rather than searched for.
    // Stepping until it appears reads the count before the week has finished
    // drawing, and then navigates past the week that held it.
    const sunday = (d) => {
      const s = new Date(d);
      s.setDate(s.getDate() - s.getDay());
      s.setHours(0, 0, 0, 0);
      return s;
    };
    const ahead = Math.round(
      (sunday(new Date(`${date}T00:00:00`)) - sunday(new Date())) / 604800000);
    for (let week = 0; week < ahead; week++) {
      await win.locator("button[onclick*='navigate(1)']").click();
    }

    // it: draws it in whichever column its day falls in. The seven columns
    // alone prove nothing — they are drawn whether or not anything was booked.
    await expect(win.locator(".week-job:not(.empty)", { hasText: "Haircut" })
                    .first()).toBeVisible();
  });
});
