// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 5 — the people a business schedules.
 *
 * An employee record exists before the person has a BOSS account: somebody is
 * added to the schedule long before they sign in. Like a job type it is
 * created as a draft when the window opens, so working days and time off have
 * somebody to belong to before anyone is named.
 *
 * `canManageOwnSchedule` is what puts the calendar and profile on their
 * dashboard, and it was dropped on create until recently — which is the kind
 * of thing only reading the record back catches. See `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled,
         docAction, action, selectPopupOption, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler employees", () => {
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
    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /** The staff, as the operator's own list answers. */
  async function staff(page) {
    const response = await page.request.get(`${API}/business/${businessId}/employees`);
    expect(response.ok()).toBe(true);
    return (await response.json()).employees;
  }

  /** One employee, whole. */
  async function employee(page, id) {
    const response = await page.request.get(
      `${API}/business/${businessId}/employee/${id}`);
    expect(response.ok()).toBe(true);
    return response.json();
  }

  async function openEditor(page) {
    await openController(page, "io.bithead.scheduler", "Employee");
    const win = windowByTitle(page, "Employee");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  test("create employee", async ({ page }) => {
    const win = await openEditor(page);

    await win.locator("input[name='first-name']").fill("Rosa");
    await win.locator("input[name='last-name']").fill("Alvarez");
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await staff(page)).map((e) => e.firstName),
            { message: "the save never reached the server" })
      .toContain("Rosa");

    // The signup wrote the owner's own record, so Rosa is the second.
    const rosa = (await staff(page)).find((e) => e.firstName === "Rosa");
    expect(rosa.lastName).toBe("Alvarez");
  });

  /** A saved employee, and the window still open on them. */
  async function openSaved(page, first = "Rosa") {
    const win = await openEditor(page);
    await win.locator("input[name='first-name']").fill(first);
    await win.locator("input[name='last-name']").fill("Alvarez");
    await docAction(win, "save").click();
    await expect.poll(async () => (await staff(page)).map((e) => e.firstName),
                      { message: "the employee never saved" })
      .toContain(first);
    const saved = (await staff(page)).find((e) => e.firstName === first);
    return { win, employeeId: saved.id };
  }

  test("save a working day", async ({ page }) => {
    const { win, employeeId } = await openSaved(page);

    await action(win, "addScheduleDay").click();
    const modal = windowByTitle(page, "Working Day");
    await expect(modal).toBeVisible();
    await selectPopupOption(modal, "day-of-week", "Tuesday");
    await modal.locator("input[name='start-time']").fill("09:00");
    await modal.locator("input[name='end-time']").fill("17:00");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await employee(page, employeeId)).scheduleTemplate.length,
            { message: "the working day never reached the server" })
      .toBe(1);
    const day = (await employee(page, employeeId)).scheduleTemplate[0];
    expect(day.dayOfWeek, "the day is not the one chosen").toBe(2);
    expect([day.startTime, day.endTime], "the hours are not the ones given")
      .toEqual(["09:00", "17:00"]);
  });

  test("save time off", async ({ page }) => {
    const { win, employeeId } = await openSaved(page);

    await action(win, "addTimeOff").click();
    const modal = windowByTitle(page, "Time Off");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='date']").fill("2026-12-24");
    await modal.locator("input[name='start-time']").fill("08:00");
    await modal.locator("input[name='end-time']").fill("12:00");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await employee(page, employeeId)).timeOff.map((w) => w.date),
            { message: "the time off never reached the server" })
      .toEqual(["2026-12-24"]);
    const window_ = (await employee(page, employeeId)).timeOff[0];
    expect([window_.startTime, window_.endTime], "the hours are not the ones given")
      .toEqual(["08:00", "12:00"]);
  });

  test("save the work an employee may be given", async ({ page }) => {
    // A job type to give them. The employee screen offers what the business
    // has, and a business with none has nothing to hand out.
    const created = await page.request.post(
      `${API}/business/${businessId}/job-type`, { data: { name: "Haircut" } });
    expect(created.ok(), `could not add a job type: ${await created.text()}`)
      .toBe(true);
    const jobTypeId = (await created.json()).id;
    await page.request.put(`${API}/business/${businessId}/job-type/${jobTypeId}`,
                           { data: { name: "Haircut", minEmployees: 1,
                                     isActive: true } });

    const { win, employeeId } = await openSaved(page, "Marco");

    // The menu offers what the business has the moment its input is focused.
    await win.locator(".ui-token-menu-input").click();
    await win.locator(".ui-token-menu-option", { hasText: "Haircut" }).click();
    await expect(win.locator(".ui-token", { hasText: "Haircut" })).toBeVisible();
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await employee(page, employeeId)).jobTypes.map((j) => j.name),
            { message: "the work never reached the server" })
      .toEqual(["Haircut"]);
  });

  test("save canManageOwnSchedule",
       async ({ page }) => {
    const win = await openEditor(page);

    await win.locator("input[name='first-name']").fill("Rosa");
    await win.locator("input[name='last-name']").fill("Alvarez");
    // The flag that puts the calendar and profile on their dashboard.
    await win.locator("input[name='can-manage-own-schedule']").check();
    await docAction(win, "save").click();

    await expect
      .poll(async () => {
        const rosa = (await staff(page)).find((e) => e.firstName === "Rosa");
        return rosa && (await employee(page, rosa.id)).canManageOwnSchedule;
      }, { message: "the flag was answered but never stored" })
      .toBe(true);
  });

  test("discard employee draft", async ({ page }) => {
    const before = (await staff(page)).length;

    const win = await openEditor(page);
    await docAction(win, "cancel").click();
    await expect(win).toBeHidden();

    expect((await staff(page)).length,
           "leaving the window left the draft employee behind")
      .toBe(before);
  });
});
