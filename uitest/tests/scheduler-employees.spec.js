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
         docAction } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler employees", () => {
  let businessId;

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
           "it: opening the window created a draft, and leaving took it away")
      .toBe(before);
  });
});
