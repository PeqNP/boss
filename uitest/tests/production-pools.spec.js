// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F1 — Pools and resources.
 *
 * The first flow that writes anything. It proves the create/edit round trip and
 * the pattern every admin screen in this app repeats: a modal saves, closes,
 * and the list behind it refreshes without a reload.
 *
 * Nothing here asserts a business rule. That a pool name must be unique, or
 * that a referenced pool cannot be renamed, is settled in
 * `private/tests/test_production.py`.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, named, component,
  clickMenuItem, settled
} from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const POOL = "Test card";

function button(win, label) {
  return win.locator("button", { hasText: new RegExp(`^${label}$`) });
}

test.describe.configure({ mode: "serial" });

test.describe("Production — pools and resources", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    await resetDatabase(page);
    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Pools");
  });

  test.afterAll(async () => {
    await page.close();
  });

  test("the pool list renders @pools", async () => {
    await expect(windowByTitle(page, "Pools")).toBeVisible();
  });

  test("a new pool is saved and appears in the list @pools", async () => {
    const pools = windowByTitle(page, "Pools");
    await button(pools, "Add").click();

    const pool = windowByTitle(page, "Pool");
    await settled(pool);
    await named(pool, "input", "pool-name").fill(POOL);
    await button(pool, "Save").click();

    // The list behind it refreshes; nothing reloads the window.
    await expect(component(pools, "ui-list-box", "pools").locator(".option", {
      hasText: POOL
    })).toBeVisible();
  });

  test("a resource is added to the pool @pools", async () => {
    const pools = windowByTitle(page, "Pools");
    await component(pools, "ui-list-box", "pools")
      .locator(".option", { hasText: POOL }).click();
    await button(pools, "Edit").click();

    const pool = windowByTitle(page, "Pool");
    await expect(named(pool, "input", "pool-name")).toHaveValue(POOL);

    await button(pool, "Add").click();
    const resource = windowByTitle(page, "Resource");
    await expect(resource).toBeVisible();
    await named(resource, "input", "resource-name").fill("Card 1");
    await named(resource, "input", "resource-value").fill("12345");
    await button(resource, "Save").click();

    await expect(component(pool, "ui-list-box", "resources").locator(".option", {
      hasText: "Card 1"
    })).toBeVisible();
  });

  test("renaming a pool shows the new name in the list @pools", async () => {
    const pool = windowByTitle(page, "Pool");
    await named(pool, "input", "pool-name").fill("Reader card");
    await button(pool, "Save").click();

    const pools = windowByTitle(page, "Pools");
    await expect(component(pools, "ui-list-box", "pools").locator(".option", {
      hasText: "Reader card"
    })).toBeVisible();
  });
});
