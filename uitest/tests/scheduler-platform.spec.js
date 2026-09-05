// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 13 — what the platform owns rather than any one business.
 *
 * Contact field types, holidays, the hold timeout, vendors and business
 * templates are seeded once and shared by every business, so an edit here
 * reaches all of them. Each screen is opened directly: the Admin menu is
 * covered once, on its own, because every other test would otherwise be
 * asserting the menu rather than the screen.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, bootBOSS,
         openApplication, openController, windowByTitle, settled, action,
         docAction, selectPopupOption, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler platform", () => {
  let businessId;

  test.afterEach(async ({ page }) => {
    await closeAll(page);
  });

  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);

    // A business the admin does not run, so the list has something in it that
    // is not theirs.
    await signInAsOperator(page);
    const signup = await page.request.post(`${API}/signup`, {
      data: { name: "Dana's Salon", timezone: "America/Los_Angeles" }
    });
    expect(signup.ok(), `signup failed: ${await signup.text()}`).toBe(true);
    businessId = (await signup.json()).businessId;

    await signInAsAdmin(page);
    await bootBOSS(page);
    // No window opens: the admin runs no business, and every operator screen
    // acts on one. The Admin menu is how they reach the platform screens, and
    // each test opens the one it is about.
    await openApplication(page, "io.bithead.scheduler");
  });

  async function open(page, controller, title) {
    await openController(page, "io.bithead.scheduler", controller);
    const win = windowByTitle(page, title);
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  /** The platform's contact field types, as the server holds them. */
  async function fields(page) {
    const response = await page.request.get(`${API}/contact-fields`);
    expect(response.ok(), `could not read the fields: ${await response.text()}`)
      .toBe(true);
    return (await response.json()).fields;
  }

  test("show every business", async ({ page }) => {
    const win = await open(page, "Businesses", "Businesses");

    const listed = win.locator(".ui-list-box .option");
    await expect(listed.filter({ hasText: "Dana's Salon" })).toBeVisible();

    // The admin runs nothing. A list narrowed to the caller's own business
    // would be empty here, which is what makes this worth asserting.
    const held = await (await page.request.get(`${API}/me`)).json();
    expect(held.businessId, "the admin runs a business").toBe(0);
  });

  test("save a contact field", async ({ page }) => {
    const win = await open(page, "ContactFields", "Contact Info Fields");
    const before = (await fields(page)).length;

    await action(win, "addField").click();
    const modal = windowByTitle(page, "Contact Field");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='field-name']").fill("Gate Code");
    // A field says what kind of value it holds, which is what decides where a
    // booking's answer is stored and whether a code can be sent to it.
    await selectPopupOption(modal, "field-type", "Text");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await fields(page)).map((f) => f.name),
            { message: "the field never reached the server" })
      .toContain("Gate Code");
    expect((await fields(page)).length).toBe(before + 1);
    await expect(win.locator(".ui-list-box .option", { hasText: "Gate Code" }))
      .toBeVisible();
  });

  test("reject a contact field without a name", async ({ page }) => {
    const win = await open(page, "ContactFields", "Contact Info Fields");
    const before = (await fields(page)).length;

    await action(win, "addField").click();
    const modal = windowByTitle(page, "Contact Field");
    await expect(modal).toBeVisible();
    await action(modal, "save").click();

    // The alert is the assertion. The server refuses a nameless field too, so
    // an unchanged count passes even with the modal's own check deleted.
    await expect(page.locator(".ui-modal", { hasText: "name" }).first())
      .toBeVisible();
    expect((await fields(page)).length).toBe(before);
  });

  test("reorder contact fields", async ({ page }) => {
    const win = await open(page, "ContactFields", "Contact Info Fields");
    const order = (await fields(page)).map((f) => f.name);
    expect(order.length, "there is nothing to reorder").toBeGreaterThan(1);

    // The second one, moved above the first.
    await win.locator(".ui-list-box .option", { hasText: order[1] }).click();
    await action(win, "moveUp").click();

    await expect
      .poll(async () => (await fields(page)).map((f) => f.name)[0],
            { message: "the order never reached the server" })
      .toBe(order[1]);
  });

  test("save the schedule timeout", async ({ page }) => {
    const win = await open(page, "ScheduleTimeout", "Schedule Timeout");

    await win.locator("input[name='timeout-minutes']").fill("17");
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await (await page.request.get(`${API}/timeout`))
                          .json()).timeoutMinutes,
            { message: "the timeout never reached the server" })
      .toBe(17);
  });

  test("save a business template", async ({ page }) => {
    const win = await open(page, "Templates", "Business Templates");

    await action(win, "addTemplate").click();
    const modal = windowByTitle(page, "Business Template");
    await expect(modal).toBeVisible();
    await modal.locator("input[name='template-name']").fill("Dog Grooming");
    // A template is chosen from a grid of cards during signup, where the
    // description is what tells one kind of business from another.
    await modal.locator("textarea[name='description']")
      .fill("Baths, clips and nail trims.");
    await action(modal, "save").click();

    await expect
      .poll(async () => (await (await page.request.get(`${API}/templates`))
                          .json()).templates.map((t) => t.name),
            { message: "the template never reached the server" })
      .toContain("Dog Grooming");
  });

  test("show vendors without credentials", async ({ page }) => {
    const win = await open(page, "Vendors", "Vendor Integrations");

    const sections = win.locator("[name='vendors-container'] fieldset");
    await expect(sections.first()).toBeVisible();

    // A vendor's config holds credentials. Secret values are never sent back,
    // so a password on screen is a leak.
    const vendors = await (await page.request.get(`${API}/vendors`)).json();
    for (const channel of vendors.vendors) {
      expect(channel.config, `${channel.channel} carries secret values`)
        .not.toHaveProperty("password");
      expect(channel.config, `${channel.channel} carries a secret key`)
        .not.toHaveProperty("secretKey");
      expect(channel.config, `${channel.channel} carries an auth token`)
        .not.toHaveProperty("authToken");
    }
  });

  test("save SMTP", async ({ page }) => {
    const win = await open(page, "Vendors", "Vendor Integrations");

    await selectPopupOption(win, "vendor-select-email", "SMTP");
    await expect(win.locator("[name='vendor-fields-email'] input")).toHaveCount(0);
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await (await page.request.get(`${API}/vendors`)).json())
              .vendors.find((v) => v.channel === "email").chosen,
            { message: "the choice never reached the server" })
      .toBe("smtp");
  });

  test("save a vendor choice", async ({ page }) => {
    const win = await open(page, "Vendors", "Vendor Integrations");

    const before = await (await page.request.get(`${API}/vendors`)).json();
    const email = before.vendors.find((v) => v.channel === "email");
    expect(email, "the platform offers no email vendor").toBeTruthy();
    expect(email.chosen, "one is chosen already").toBeFalsy();

    await selectPopupOption(win, "vendor-select-email", "Mailtrap");
    await win.locator("input[name='vendor-field-email-username']")
      .fill("noreply@bithead.io");
    await docAction(win, "save").click();

    await expect
      .poll(async () => (await (await page.request.get(`${API}/vendors`)).json())
              .vendors.find((v) => v.channel === "email").chosen,
            { message: "the choice never reached the server" })
      .toBe("mailtrap");

    const saved = await (await page.request.get(`${API}/vendors`)).json();
    const chosen = saved.vendors.find((v) => v.channel === "email");
    expect(chosen.config, "secrets absent from GET")
      .not.toHaveProperty("password");
  });

  test("show Stripe fields", async ({ page }) => {
    const win = await open(page, "Vendors", "Vendor Integrations");

    await selectPopupOption(win, "vendor-select-payment", "Stripe");
    await expect(win.locator("input[name='vendor-field-payment-secretKey']"))
      .toBeVisible();
    await expect(win.locator("input[name='vendor-field-payment-publishableKey']"))
      .toBeVisible();
  });

  // Holidays are not covered: `system_holidays` is only written by
  // `close_on_holiday`, which no route exposes, and
  // `POST /system-holidays/refresh` reports the count already there rather
  // than fetching a year. The screen has nothing to draw until a provider is
  // connected — see `review.md`.

  test("platform scoping", async ({ page }) => {
    await signInAsOperator(page);

    for (const path of ["/businesses", "/timeout", "/vendors"]) {
      const reached = await page.request.get(`${API}${path}`);
      expect(reached.ok(), `an operator reached ${path}`).toBe(false);
    }

    const added = await page.request.post(`${API}/contact-field`,
                                          { data: { name: "Sneaky" } });
    expect(added.ok(), "an operator added a platform contact field").toBe(false);
  });
});
