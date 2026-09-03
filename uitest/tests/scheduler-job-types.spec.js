// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 4 — the work a business offers.
 *
 * A job type is created as a draft the moment the window opens, so its sizes
 * and contact fields have something to belong to before anything is named. The
 * save is what names it and makes it active; leaving without saving deletes
 * it.
 *
 * That is the part worth proving through a browser: a draft nobody finished
 * must not reach a customer, and only the kiosk's own answer says whether it
 * did. See `ui-plan.md`.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled,
         docAction , closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler job types", () => {
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

    // The Operator role reaches the token at the next sign-in.
    await signInAsOperator(page);
    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    // `applicationDidStart` has to have read `/me` before a controller opens.
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /** What the operator's own list holds. */
  async function jobTypes(page) {
    const response = await page.request.get(`${API}/business/${businessId}/job-types`);
    expect(response.ok()).toBe(true);
    return (await response.json()).jobTypes;
  }

  /** What a customer at the kiosk is offered. */
  async function offered(page) {
    const response = await page.request.get(`${API}/kiosk/${businessId}/job-types`);
    expect(response.ok()).toBe(true);
    return (await response.json()).jobTypes;
  }

  test("save job type", async ({ page }) => {
    await openController(page, "io.bithead.scheduler", "JobType");
    const win = windowByTitle(page, "Job Type");
    await expect(win).toBeVisible();
    await settled(win);

    await win.locator("input[name='name']").fill("Haircut");
    await win.locator("input[name='min-employees']").fill("1");
    await win.locator("input[name='is-active']").check();
    // A document's Save writes and stays open; Cancel and Delete are what
    // close it. So the proof is the record, not the window.
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await jobTypes(page)).map((j) => j.name),
            { message: "the save never reached the server" })
      .toContain("Haircut");
    const named = await jobTypes(page);
    expect(named.map((j) => j.name)).toContain("Haircut");

    await expect
      .poll(async () => (await offered(page)).map((j) => j.name),
            { message: "the saved job type never reached the kiosk" })
      .toContain("Haircut");
  });

  test("discard job type draft", async ({ page }) => {
    await openController(page, "io.bithead.scheduler", "JobType");
    const win = windowByTitle(page, "Job Type");
    await expect(win).toBeVisible();
    await settled(win);

    // Opening the window created the draft. Leaving without saving is what
    // has to take it away again.
    await docAction(win, "cancel").click();
    await expect(win).toBeHidden();

    expect(await offered(page), "a draft job type was offered to a customer").toEqual([]);
    expect((await jobTypes(page)).length,
           "the deleted job type is still in the operator's list")
      .toBe(0);
  });
});
