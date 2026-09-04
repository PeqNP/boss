// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 12 — the day as the person doing the work sees it.
 *
 * An employee reaches the same routes an operator does, narrowed to the jobs
 * they are on. So every test here books work for two people and asserts that
 * the colleague's is absent: a screen that draws one job proves nothing about
 * narrowing when only one job exists.
 *
 * `scheduler-access.spec.js` covers linking an account and the calendar
 * opening. This covers what the portal shows once it has.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, ensureAccount,
         account, signInAs, bootBOSS, openApplication, windowByTitle, settled,
         action, docAction, selectPopupOption, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

/** Today, which is the day the dashboard draws with no date given. */
function today() {
  const when = new Date();
  const month = String(when.getMonth() + 1).padStart(2, "0");
  const day = String(when.getDate()).padStart(2, "0");
  return `${when.getFullYear()}-${month}-${day}`;
}

test.describe("scheduler employee portal", () => {
  let businessId;
  let rosaId;
  let rosaJob;
  let colleagueJob;
  let what;

  test.afterEach(async ({ page }) => {
    await closeAll(page);
  });

  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);

    const worker = account("portal-employee");
    await ensureAccount(page, worker);
    const users = await (await page.request.get("/account/users")).json();
    const workerId = users.users.find((u) => u.name === worker.email).id;

    await signInAsOperator(page);
    const signup = await page.request.post(`${API}/signup`, {
      data: { name: "Dana's Salon", timezone: "America/Los_Angeles" }
    });
    expect(signup.ok(), `signup failed: ${await signup.text()}`).toBe(true);
    businessId = (await signup.json()).businessId;

    await signInAsOperator(page);
    // `readyToBook` leaves one employee, Alice Kim, who is the colleague here.
    what = await readyToBook(page, businessId);

    const added = await page.request.post(`${API}/business/${businessId}/employee`, {
      data: { firstName: "Rosa", lastName: "Alvarez", canManageOwnSchedule: true }
    });
    expect(added.ok(), `could not add an employee: ${await added.text()}`).toBe(true);
    rosaId = (await added.json()).id;
    const shaped = await page.request.put(
      `${API}/business/${businessId}/employee/${rosaId}`,
      { data: { firstName: "Rosa", lastName: "Alvarez", includeInSchedule: true,
                canManageOwnSchedule: true, jobTypeIds: [what.jobTypeId] } });
    expect(shaped.ok(), `could not shape the employee: ${await shaped.text()}`)
      .toBe(true);
    for (let day = 0; day < 7; day++) {
      await page.request.post(
        `${API}/business/${businessId}/employee/${rosaId}/schedule`,
        { data: { dayOfWeek: day, startTime: "08:00", endTime: "18:00" } });
    }

    // Two jobs today, one each. The colleague's is what proves the narrowing.
    rosaJob = await book(page, businessId, what, today(), "09:00",
                         { "First Name": "Jane", "Last Name": "Doe",
                           "Phone": "555-0101" });
    colleagueJob = await book(page, businessId, what, today(), "14:00",
                              { "First Name": "Marco", "Last Name": "Ruiz",
                                "Phone": "555-0202" });
    await assign(page, rosaJob, "09:00", [rosaId]);
    await assign(page, colleagueJob, "14:00", [what.employeeId]);

    const linked = await page.request.put(
      `${API}/business/${businessId}/employee/${rosaId}/account`,
      { data: { userId: parseInt(workerId) } });
    expect(linked.ok(), `could not link the account: ${await linked.text()}`)
      .toBe(true);

    // Signed in again, because linking granted the licence and the Employee
    // role and a session carries what it was minted with.
    await signInAs(page, worker);
    const me = await (await page.request.get(`${API}/me`)).json();
    expect(me.role, "the linked account is not an employee").toBe("Employee");

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /** Put an appointment in somebody's hands. */
  async function assign(page, jobId, time, employeeIds) {
    const response = await page.request.put(
      `${API}/business/${businessId}/job/${jobId}`,
      { data: { scheduledDate: today(), scheduledTime: time, employeeIds } });
    expect(response.ok(), `could not assign the job: ${await response.text()}`)
      .toBe(true);
  }

  async function openDashboard(page) {
    const win = windowByTitle(page, "My Schedule");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  test("show today's work", async ({ page }) => {
    const win = await openDashboard(page);

    const cards = win.locator(".emp-job-card");
    await expect(cards).toHaveCount(1);
    await expect(cards).toContainText("Haircut");

    // The customer, because an employee turning up needs somebody to ask for
    // and a number to call.
    await expect(cards).toContainText("Jane Doe");
    await expect(cards).toContainText("555-0101");
  });

  test("show only the employee's own jobs", async ({ page }) => {
    const win = await openDashboard(page);

    // Marco's appointment is on the same day at the same business, held by a
    // colleague. A card count alone passes with the narrowing removed only if
    // nobody else is booked, which is why he is.
    await expect(win.locator(".emp-job-card")).toHaveCount(1);
    await expect(win.locator(".emp-job-card", { hasText: "Marco Ruiz" }))
      .toHaveCount(0);

    const mine = await (await page.request.get(`${API}/my/today`)).json();
    expect(mine.jobs.map((j) => j.id), "the day carries a colleague's job")
      .toEqual([rosaJob]);
  });

  test("open a job from the dashboard", async ({ page }) => {
    const win = await openDashboard(page);

    await win.locator(".emp-job-card").first().click();
    await expect(windowByTitle(page, "Job")).toBeVisible();
  });

  test("save own job types", async ({ page }) => {
    await action(await openDashboard(page), "manageProfile").click();
    const win = windowByTitle(page, "My Profile");
    await expect(win).toBeVisible();
    await settled(win);

    await expect(win.locator("[name='employee-name']")).toContainText("Rosa");

    // The job types are a token menu, so one is dropped by removing its token.
    const token = win.locator(".ui-token", { hasText: "Haircut" });
    await expect(token).toBeVisible();
    await token.locator(".ui-token-remove").click();
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await (await page.request.get(`${API}/my/profile`))
                          .json()).jobTypes.length,
            { message: "the profile never reached the server" })
      .toBe(0);
  });

  /** The employee's own record, as the server holds it. */
  async function profile(page) {
    const response = await page.request.get(`${API}/my/profile`);
    expect(response.ok(), `could not read the profile: ${await response.text()}`)
      .toBe(true);
    return response.json();
  }

  async function openProfile(page) {
    await action(await openDashboard(page), "manageProfile").click();
    const win = windowByTitle(page, "My Profile");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  test("save a working day from the portal", async ({ page }) => {
    const win = await openProfile(page);

    // Rosa already works every day, so this changes one rather than adding a
    // day she has — a test that added one would assert a Saturday exists,
    // which was true before it ran.
    await win.locator(".ui-list-box .option", { hasText: "Sat" }).first().click();
    await action(win, "editScheduleDay").click();
    const modal = windowByTitle(page, "Working Day");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='start-time']").fill("10:00");
    await modal.locator("input[name='end-time']").fill("14:00");
    await action(modal, "save").click();

    // Written through the routes the operator uses, which the service
    // authorises rather than duplicates — so the employee's own edit lands on
    // the same record the operator reads.
    await expect
      .poll(async () => {
        const day = (await profile(page)).scheduleTemplate
          .find((d) => d.dayOfWeek === 6);
        return day && [day.startTime, day.endTime];
      }, { message: "the hours never reached the server" })
      .toEqual(["10:00", "14:00"]);

    // The rest of her week is untouched.
    const monday = (await profile(page)).scheduleTemplate
      .find((d) => d.dayOfWeek === 1);
    expect([monday.startTime, monday.endTime], "another day moved")
      .toEqual(["08:00", "18:00"]);
  });

  test("save time off from the portal", async ({ page }) => {
    const win = await openProfile(page);

    await action(win, "addTimeOff").click();
    const modal = windowByTitle(page, "Time Off");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='date']").fill("2026-12-24");
    await modal.locator("input[name='start-time']").fill("08:00");
    await modal.locator("input[name='end-time']").fill("12:00");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await profile(page)).timeOff.map((w) => w.date),
            { message: "the time off never reached the server" })
      .toEqual(["2026-12-24"]);
  });

  test("refuse a colleague's job", async ({ page }) => {
    // The narrowing is the server's, not the screen's. An employee naming a
    // job they are not on reads nothing, which is what makes the dashboard
    // safe to draw from what it is given.
    const theirs = await page.request.get(
      `${API}/business/${businessId}/job/${colleagueJob}`);
    expect(theirs.status(), "an employee read a job they are not on").toBe(404);

    const mine = await page.request.get(
      `${API}/business/${businessId}/job/${rosaJob}`);
    expect(mine.ok(), `an employee cannot read their own job: ${await mine.text()}`)
      .toBe(true);
  });
});
