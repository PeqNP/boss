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
         docAction, action, selectPopupOption, closeAll } from "../lib/boss.js";
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

  /** Everything hanging off one job type, as the server holds it. */
  async function detail(page, jobTypeId) {
    const response = await page.request.get(
      `${API}/business/${businessId}/job-type/${jobTypeId}`);
    expect(response.ok(), `could not read the job type: ${await response.text()}`)
      .toBe(true);
    return response.json();
  }

  /** A saved job type, and its window left open on it. */
  async function openSaved(page, name = "Haircut") {
    await openController(page, "io.bithead.scheduler", "JobType");
    const win = windowByTitle(page, "Job Type");
    await expect(win).toBeVisible();
    await settled(win);
    await win.locator("input[name='name']").fill(name);
    await win.locator("input[name='min-employees']").fill("1");
    await win.locator("input[name='is-active']").check();
    await docAction(win, "save").click();
    await expect.poll(async () => (await jobTypes(page)).map((j) => j.name),
                      { message: "the job type never saved" })
      .toContain(name);
    const saved = (await jobTypes(page)).find((j) => j.name === name);
    return { win, jobTypeId: saved.id };
  }

  test("save job type size", async ({ page }) => {
    const { win, jobTypeId } = await openSaved(page);

    await action(win, "addSize").click();
    const modal = windowByTitle(page, "Size");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='size-name']").fill("Long hair");
    await modal.locator("input[name='duration-minutes']").fill("90");
    await modal.locator("input[name='cost']").fill("65");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await detail(page, jobTypeId)).sizes.map((z) => z.name),
            { message: "the size never reached the server" })
      .toEqual(["Long hair"]);
    const size = (await detail(page, jobTypeId)).sizes[0];
    expect(size.durationMinutes, "the size carries the wrong duration").toBe(90);
    expect(size.cost, "the size carries the wrong cost").toBe(65);

    await expect(win.locator(".ui-list-box .option", { hasText: "Long hair" }))
      .toBeVisible();
  });

  test("save job type attribute", async ({ page }) => {
    const { win, jobTypeId } = await openSaved(page);

    await action(win, "addAttribute").click();
    const modal = windowByTitle(page, "Attribute");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='attribute-name']").fill("Gate code");
    await selectPopupOption(modal, "attribute-type", "Text");
    await modal.locator("input[name='attribute-required']").check();
    await action(modal, "save").click();

    await expect
      .poll(async () => (await detail(page, jobTypeId)).attributes.map((a) => a.name),
            { message: "the question never reached the server" })
      .toEqual(["Gate code"]);
    expect((await detail(page, jobTypeId)).attributes[0].isRequired,
           "the question is not required").toBe(true);
  });

  test("save job type contact field", async ({ page }) => {
    const { win, jobTypeId } = await openSaved(page);

    await action(win, "addContactField").click();
    const modal = windowByTitle(page, "Contact Field");
    await expect(modal).toBeVisible();
    await selectPopupOption(modal, "field-type", "Phone");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await detail(page, jobTypeId)).contactFields.map((f) => f.name),
            { message: "the contact field never reached the server" })
      .toEqual(["Phone"]);

    // What the kiosk asks a customer for, which is the point of adding one.
    // The whole job type comes back, contact fields and all, so a customer
    // sees the question the same moment the operator saved it.
    const offering = (await offered(page)).find((j) => j.id === jobTypeId);
    expect(offering, "the job type is not offered at all").toBeTruthy();
    expect(offering.contactFields.map((f) => f.name),
           "the kiosk asks for something else").toEqual(["Phone"]);
  });

  test("reorder job type contact fields", async ({ page }) => {
    const { win, jobTypeId } = await openSaved(page);

    for (const kind of ["First Name", "Phone"]) {
      await action(win, "addContactField").click();
      const modal = windowByTitle(page, "Contact Field");
      await expect(modal).toBeVisible();
      await selectPopupOption(modal, "field-type", kind);
      await action(modal, "save").click();
      await expect(modal).toBeHidden();
    }
    await expect
      .poll(async () => (await detail(page, jobTypeId)).contactFields.length,
            { message: "both fields never landed" })
      .toBe(2);

    // The second, moved above the first. The order is what the kiosk asks in.
    await win.locator(".ui-list-box .option", { hasText: "Phone" }).click();
    await action(win, "moveContactFieldUp").click();

    await expect
      .poll(async () => (await detail(page, jobTypeId)).contactFields.map((f) => f.name),
            { message: "the order never reached the server" })
      .toEqual(["Phone", "First Name"]);
  });

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
