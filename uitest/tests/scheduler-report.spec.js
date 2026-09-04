// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 11 — what the business took over a period.
 *
 * The figures an owner reads to decide whether the quarter went well, so each
 * one is asserted against what was actually booked and paid rather than
 * against the answer the same route gives. A deposit is named apart from
 * revenue: it is held against work still to come, and an owner counting one
 * figure would be counting takings they may yet have to return.
 *
 * The appointments are booked for tomorrow, which is not always in the quarter
 * the screen opens on. The period is chosen on screen before the figures are
 * read, so this holds on the last day of a quarter as well as the first.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled,
         selectPopupOption, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book, cancelAppointment } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

/** What one "Standard" appointment costs, from `readyToBook`. */
const COST = 40;

function tomorrow() {
  const when = new Date();
  when.setDate(when.getDate() + 1);
  const month = String(when.getMonth() + 1).padStart(2, "0");
  const day = String(when.getDate()).padStart(2, "0");
  return `${when.getFullYear()}-${month}-${day}`;
}

/** The year and quarter a `YYYY-MM-DD` falls in. */
function periodOf(date) {
  const [year, month] = date.split("-").map(Number);
  return { year, quarter: Math.floor((month - 1) / 3) + 1 };
}

test.describe("scheduler financial report", () => {
  let businessId;
  let booked;
  let paidJob;

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
    booked = tomorrow();

    // Three appointments on one day: one paid and finished, one cancelled, one
    // left open. Every figure on the screen has something to be wrong about.
    paidJob = await book(page, businessId, what, booked, "09:00");
    const cancelled = await book(page, businessId, what, booked, "11:00");
    await book(page, businessId, what, booked, "13:00");

    const paid = await page.request.post(
      `${API}/business/${businessId}/job/${paidJob}/payment`,
      { data: { amount: COST, method: "cash" } });
    expect(paid.ok(), `could not record a payment: ${await paid.text()}`)
      .toBe(true);

    const done = await page.request.post(
      `${API}/business/${businessId}/job/${paidJob}/complete`);
    expect(done.ok(), `could not complete the job: ${await done.text()}`)
      .toBe(true);

    await cancelAppointment(page, businessId, cancelled);

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  async function openReport(page) {
    await openController(page, "io.bithead.scheduler", "FinancialReport");
    const win = windowByTitle(page, "Financial Report");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  /** Drive the screen to the period the appointments were booked in. */
  async function loadBookedPeriod(win) {
    const { year, quarter } = periodOf(booked);
    await selectPopupOption(win, "period", "Quarterly");
    await selectPopupOption(win, "year", String(year));
    await selectPopupOption(win, "quarter", `Q${quarter}`);
    await win.locator("button", { hasText: "Load" }).click();
    await expect(win.locator("[name='report-period']"))
      .toHaveText(`Q${quarter} ${year}`);
  }

  test("open financial report", async ({ page }) => {
    const win = await openReport(page);

    // The screen opens on the period the server chose, with no parameters
    // sent — one clock rather than two.
    const now = new Date();
    const quarter = Math.floor(now.getMonth() / 3) + 1;
    await expect(win.locator("[name='report-period']"))
      .toHaveText(`Q${quarter} ${now.getFullYear()}`);

    // The year menu is filled from the years this business has appointments
    // in, so a business with nothing booked still has a year to select.
    await expect(win.locator("[name='year']"))
      .toContainText(String(now.getFullYear()));
  });

  test("report figures", async ({ page }) => {
    const win = await openReport(page);
    await loadBookedPeriod(win);

    await expect(win.locator("[name='revenue']")).toHaveText(`$${COST}.00`);
    await expect(win.locator("[name='jobs-completed']")).toHaveText("1");
    await expect(win.locator("[name='jobs-cancelled']")).toHaveText("1");

    // Nothing was taken as a deposit and nothing was given up on. Both read
    // zero rather than repeating the revenue, which is what an owner counting
    // one figure twice would see.
    await expect(win.locator("[name='deposits']")).toHaveText("$0.00");
    await expect(win.locator("[name='write-offs']")).toHaveText("$0.00");
  });

  test("empty period", async ({ page }) => {
    const win = await openReport(page);
    const { year } = periodOf(booked);

    // A quarter the appointments are not in. Every figure is zero, which is
    // what proves the figures above came from the period and not from the
    // business as a whole.
    const { quarter } = periodOf(booked);
    const empty = quarter === 1 ? 4 : quarter - 1;
    await selectPopupOption(win, "period", "Quarterly");
    await selectPopupOption(win, "year", String(year));
    await selectPopupOption(win, "quarter", `Q${empty}`);
    await win.locator("button", { hasText: "Load" }).click();

    await expect(win.locator("[name='report-period']"))
      .toHaveText(`Q${empty} ${year}`);
    await expect(win.locator("[name='revenue']")).toHaveText("$0.00");
    await expect(win.locator("[name='jobs-completed']")).toHaveText("0");
    await expect(win.locator("[name='jobs-cancelled']")).toHaveText("0");
  });

  test("switch to a full year", async ({ page }) => {
    const win = await openReport(page);
    const { year } = periodOf(booked);

    await selectPopupOption(win, "period", "Yearly");
    await selectPopupOption(win, "year", String(year));

    // The quarter menu goes when it means nothing, rather than staying on
    // screen showing a quarter the figures do not cover.
    await expect(win.locator("[name='quarter-select']")).toBeHidden();

    await win.locator("button", { hasText: "Load" }).click();
    await expect(win.locator("[name='report-period']"))
      .toHaveText(`Full Year ${year}`);
    await expect(win.locator("[name='revenue']")).toHaveText(`$${COST}.00`);
  });

  test("export the report as csv", async ({ page }) => {
    const win = await openReport(page);
    await loadBookedPeriod(win);

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      win.locator("button", { hasText: "Export CSV" }).click()
    ]);
    expect(download.suggestedFilename()).toBe("financial-report.csv");

    const stream = await download.createReadStream();
    const chunks = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }
    const rows = Buffer.concat(chunks).toString("utf8").trim().split("\n");

    expect(rows[0]).toBe(
      "Job Code,Date,Service,Status,Payment Status,Cost,Paid");

    // One row per appointment in the period, and the paid one carries what was
    // paid. A header alone downloads whether or not anything was booked.
    expect(rows.length, "a row per appointment, after the header").toBe(4);
    const paidRow = rows.slice(1).find((r) => r.includes("completed"));
    expect(paidRow, "the finished appointment is not in the export")
      .toBeTruthy();
    expect(paidRow.endsWith(`${COST}.00,${COST}.00`),
           `the export does not carry what was paid: ${paidRow}`).toBe(true);
  });
});
