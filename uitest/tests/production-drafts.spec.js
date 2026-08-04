// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Drafts — creating a record and its children in one sitting.
 *
 * A pool's resources, a line's operations, and an operation's sections all
 * need a parent that exists, because the server mints the id. The forms used
 * to demand a save first, which closed the form and sent the user back in.
 *
 * Now the record is created the moment the form opens, named `Untitled`, and
 * the form is responsible for it until it is saved: cancelling or closing
 * offers to discard it. A draft left behind by a crash is deliberately kept —
 * it is work in progress, and reopening it is how you finish it.
 *
 * Pool is the reference implementation; `ProductionLine` and `Operation`
 * follow the same shape.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, named, component,
  action, clickMenuItem, settled
} from "../lib/boss.js";
import { API, resetDatabase } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const DRAFT = "Untitled";

test.describe.configure({ mode: "serial" });

test.describe("Production — drafts", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    await resetDatabase(page);
    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Pools");
    await settled(windowByTitle(page, "Pools"));
  });

  test.afterAll(async () => {
    await page.close();
  });

  const pools = () => windowByTitle(page, "Pools");
  const pool = () => windowByTitle(page, "Pool");
  const addPool = () => pools().locator("button", { hasText: /^Add$/ }).first();

  /** Every pool the server holds, by name. */
  async function poolNames() {
    const response = await page.request.get(`${API}/pools`);
    return (await response.json()).map((p) => p.name);
  }

  function confirm(text) {
    return page.locator(".ui-modal", { hasText: text });
  }

  test("the record exists as soon as the form opens @draft", async () => {
    await addPool().click();
    await settled(pool());

    // Named, and really there — which is what lets a resource be added to it
    // without saving first.
    await expect(named(pool(), "input", "pool-name")).toHaveValue(DRAFT);
    expect(await poolNames()).toEqual([DRAFT]);

    // The guard that used to stand here is gone.
    await action(pool(), "addResource").click();
    const resource = windowByTitle(page, "Resource");
    await settled(resource);
    await named(resource, "input", "resource-name").fill("Card 1");
    await named(resource, "input", "resource-value").fill("12340");
    await action(resource, "save").click();

    await expect(component(pool(), "ui-list-box", "resources").locator(".option"))
      .toHaveCount(1);
  });

  test("keeping the draft leaves the window open @draft", async () => {
    await action(pool(), "cancel").click();

    // Discarding takes the resource with it, so it asks.
    await expect(confirm("Discard this pool's draft?")).toBeVisible();
    await confirm("Discard this pool's draft?")
      .locator("button", { hasText: /^Cancel$/ }).first().click();

    await expect(pool()).toBeVisible();
    expect(await poolNames()).toEqual([DRAFT]);
  });

  test("the close box asks the same question as Cancel @draft", async () => {
    await pool().locator(".close-button").first().click();

    await expect(confirm("Discard this pool's draft?")).toBeVisible();
    await confirm("Discard this pool's draft?")
      .locator("button", { hasText: /^OK$/ }).first().click();

    await expect(pool()).toHaveCount(0);
    // Gone, along with the resource that belonged to it.
    expect(await poolNames()).toEqual([]);
  });

  test("a second draft is refused while one is in progress @draft", async () => {
    // Pool names are unique, so the earlier draft holds `Untitled`. It is
    // still there to be finished, which is the point.
    await page.request.post(`${API}/pool`, { data: { name: DRAFT } });

    await addPool().click();
    await expect(confirm("There is already a draft in progress")).toBeVisible();
    await confirm("There is already a draft in progress")
      .locator("button", { hasText: /^OK$/ }).first().click();

    // The window steps aside rather than sitting there unusable.
    await expect(pool()).toHaveCount(0);
    expect(await poolNames()).toEqual([DRAFT]);
  });

  test("a saved pool closes without offering to delete it @draft", async () => {
    // Clear the draft the previous test planted through the API — the list
    // behind never heard about it — then make a real pool the way a user
    // would, which refreshes the list on save.
    const [planted] = await (await page.request.get(`${API}/pools`)).json();
    await page.request.delete(`${API}/pool/${planted.id}`);

    await addPool().click();
    await settled(pool());
    await named(pool(), "input", "pool-name").fill("Reader card");
    await action(pool(), "save").click();
    await expect(pool()).toHaveCount(0);

    await component(pools(), "ui-list-box", "pools").locator(".option", { hasText: "Reader card" })
      .click();
    await pools().locator("button", { hasText: /^Edit$/ }).first().click();
    await settled(pool());

    // Closing a record someone was only reading must not offer to destroy it.
    await pool().locator(".close-button").first().click();
    await expect(pool()).toHaveCount(0);
    await expect(page.locator(".ui-modal")).toHaveCount(0);
    expect(await poolNames()).toEqual(["Reader card"]);
  });
});
