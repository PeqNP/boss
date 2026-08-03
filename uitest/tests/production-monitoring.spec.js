// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F6 — Monitoring a running job.
 *
 * The read-only half of the dashboard, and the widest set of reads in the app:
 * a filtered list, a detail screen assembled from four separate collections,
 * and a file download. Every one of these consumes a list or an object the
 * server shaped, so this is where a response read at the wrong level — the
 * envelope instead of the array — shows up as an empty screen.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, leaveHeldLine,
  named, component, action, clickMenuItem, closeWindow, selectPopupOption, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob, seedFailedUnit } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const NOTES = "Reader would not scan";

test.describe.configure({ mode: "serial" });

test.describe("Production — monitoring a job", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    await resetDatabase(page);
    await leaveHeldLine(page, API);

    // Three units, one of them failed: enough for a filter to have something
    // to narrow, and for requeue to have something to act on.
    const { jobId, poolId } = await seedStartedJob(page, { name: JOB, units: 3 });
    await seedFailedUnit(page, jobId, poolId, NOTES);

    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Jobs");

    const jobs = windowByTitle(page, "Jobs");
    await settled(jobs);
    await component(jobs, "ui-list-box", "jobs").locator(".option", { hasText: JOB }).click();
    await action(jobs, "showProgress").click();
    await settled(windowByTitle(page, "Job Progress"));
  });

  test.afterAll(async () => {
    await page.close();
  });

  /** The work unit rows currently listed. */
  function units(dashboard) {
    return component(dashboard, "ui-list-box", "work-units").locator(".option");
  }

  test("nothing is listed until a filter is chosen @monitor", async () => {
    const dashboard = windowByTitle(page, "Job Progress");

    // The filter opens on its prompt, which carries no value — so the list
    // starts empty rather than guessing what the admin wanted to see.
    await expect(units(dashboard)).toHaveCount(0);

    await selectPopupOption(dashboard, "unit-filter", "All");
    await expect(units(dashboard)).toHaveCount(3);
    // Each row says what state it is in and who holds it.
    await expect(units(dashboard).filter({ hasText: "failed" })).toHaveCount(1);
    await expect(units(dashboard).filter({ hasText: "unassigned" })).toHaveCount(3);
  });

  test("filtering narrows the list to one state @monitor", async () => {
    const dashboard = windowByTitle(page, "Job Progress");

    await selectPopupOption(dashboard, "unit-filter", "Failed");
    await expect(units(dashboard)).toHaveCount(1);

    await selectPopupOption(dashboard, "unit-filter", "Pending");
    await expect(units(dashboard)).toHaveCount(2);

    await selectPopupOption(dashboard, "unit-filter", "Complete");
    await expect(units(dashboard)).toHaveCount(0);
  });

  test("a unit's detail carries its input, resources, and log @monitor", async () => {
    const dashboard = windowByTitle(page, "Job Progress");
    await selectPopupOption(dashboard, "unit-filter", "Failed");
    await units(dashboard).first().click();
    await action(dashboard, "showWorkUnit").click();

    const unit = windowByTitle(page, "Work Unit");
    await settled(unit);

    await expect(named(unit, "span", "unit-state")).toHaveText("failed");
    // The columns the CSV declared, read back off the unit.
    await expect(named(unit, "div", "unit-input")).toContainText("Asset");
    await expect(named(unit, "div", "unit-input")).toContainText("AST-9901");
    // What was checked out to work it — recorded at the moment it failed, so
    // the record survives the resource going back in the pool.
    await expect(named(unit, "div", "unit-resources")).toContainText("Card 1");
    // The per-operation log, including the note that is the only account of
    // what went wrong.
    await expect(named(unit, "div", "unit-operations")).toContainText("Scan reader");
    await expect(named(unit, "div", "unit-operations")).toContainText(NOTES);

    await closeWindow(unit);
  });

  test("only a failed unit can be requeued @monitor", async () => {
    const dashboard = windowByTitle(page, "Job Progress");

    await selectPopupOption(dashboard, "unit-filter", "Pending");
    await units(dashboard).first().click();
    // A pending unit has nothing to clear, so requeue is not offered — but it
    // can still be read.
    await expect(named(dashboard, "button", "requeue-btn")).toBeDisabled();
    await expect(named(dashboard, "button", "open-unit-btn")).toBeEnabled();

    await selectPopupOption(dashboard, "unit-filter", "Failed");
    await units(dashboard).first().click();
    await expect(named(dashboard, "button", "requeue-btn")).toBeEnabled();
  });

  test("requeueing clears the failure and the list reflects it @monitor", async () => {
    const dashboard = windowByTitle(page, "Job Progress");

    await named(dashboard, "button", "requeue-btn").click();
    // Requeueing discards recorded progress, so it asks first.
    const confirm = page.locator(".ui-modal", { hasText: "Requeue this work unit?" });
    await expect(confirm).toBeVisible();
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();

    // The filter is still `Failed`, and there is no longer anything failed.
    await expect(units(dashboard)).toHaveCount(0);

    await selectPopupOption(dashboard, "unit-filter", "Pending");
    await expect(units(dashboard)).toHaveCount(3);
  });

  test("the job exports as a downloadable file @monitor", async () => {
    const dashboard = windowByTitle(page, "Job Progress");

    // Asserting the download, not its bytes: the export's contents are the
    // server's business and are covered there. What the screen is responsible
    // for is that the button produces a file at all, with the name the server
    // chose rather than one the browser invented.
    const download = page.waitForEvent("download");
    await action(dashboard, "exportCsv").click();
    expect((await download).suggestedFilename()).toMatch(/\.csv$/);
  });
});
