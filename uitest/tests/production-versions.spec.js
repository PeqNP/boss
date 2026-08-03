// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F3 — Versions and fork-on-edit.
 *
 * The contract this proves is the one most likely to corrupt data if it breaks.
 * A job pins a version and freezes it; editing that version forks a copy, which
 * gives every operation and section a new id. A screen still holding the old
 * ids would be writing to a version that history depends on, so any response
 * carrying `forked` has to make the screen reload rather than carry on.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, leaveHeldLine,
  named, component, action, clickMenuItem
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const LINE = "CR-One Reader";

test.describe.configure({ mode: "serial" });

test.describe("Production — versions and fork-on-edit", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    await resetDatabase(page);
    await leaveHeldLine(page, API);

    // A running job is what freezes version 1, and a frozen version is what
    // makes the next edit fork.
    await seedStartedJob(page);

    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Production Lines");
  });

  test.afterAll(async () => {
    await page.close();
  });

  test("a version in use says so @versions", async () => {
    const lines = windowByTitle(page, "Production Lines");
    await component(lines, "ui-list-box", "production-lines")
      .locator(".option", { hasText: LINE }).click();
    await action(lines, "editProductionLine").click();

    const line = windowByTitle(page, "Production Line");
    await expect(line).toBeVisible();
    // The warning is the whole point: an admin should know before they type
    // that saving will branch the line rather than change it.
    await expect(named(line, "span", "version-label"))
      .toContainText("Version 1 — in use by a job");
  });

  test("editing a frozen version forks it @versions", async () => {
    const line = windowByTitle(page, "Production Line");
    const before = await component(line, "ui-list-box", "operations")
      .locator(".option").allInnerTexts();

    await component(line, "ui-list-box", "operations")
      .locator(".option", { hasText: "Scan reader" }).click();
    await action(line, "editOperation").click();

    const operation = windowByTitle(page, "Operation");
    await named(operation, "input", "operation-name").fill("Scan the reader");
    await action(operation, "save").click();

    // The screen reloaded onto version 2 rather than staying on the version a
    // job depends on.
    await expect(named(line, "span", "version-label")).toContainText("Version 2");
    await expect(named(line, "span", "version-label")).not.toContainText("in use");

    const after = await component(line, "ui-list-box", "operations")
      .locator(".option").allInnerTexts();
    expect(after).not.toEqual(before);
    expect(after.join(" ")).toContain("Scan the reader");
  });

  test("history lists both versions, and the frozen one is read-only @versions", async () => {
    const line = windowByTitle(page, "Production Line");
    await action(line, "showHistory").click();

    const history = windowByTitle(page, "Version History");
    await expect(history).toBeVisible();

    const versions = component(history, "ui-list-box", "versions").locator(".option");
    await expect(versions).toHaveCount(2);
    // Version 1 is the one a job pinned, so it carries the job count and is
    // marked frozen; version 2 is the working copy.
    await expect(versions.filter({ hasText: "Version 1" })).toContainText("frozen");
    await expect(versions.filter({ hasText: "Version 1" })).toContainText("1 job(s)");
    await expect(versions.filter({ hasText: "Version 2" })).not.toContainText("frozen");
  });

  test("the job still runs the version it pinned @versions", async () => {
    // The whole reason for forking: a finished work unit must still be
    // readable exactly as its operator saw it.
    const job = await (await page.request.get(`${API}/jobs`)).json();
    const detail = await (await page.request.get(`${API}/job/${job[0].id}`)).json();
    expect(detail.version).toBe(1);
  });
});
