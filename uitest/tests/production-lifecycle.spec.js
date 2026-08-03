// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F5 — Starting and stopping a job.
 *
 * Starting is the moment a job stops being editable paperwork and becomes
 * something operators are held to: it pins the production line's version and
 * freezes it. Stopping pauses everyone on it. Both are single buttons whose
 * only feedback is a screen redrawing, so what this proves is that each screen
 * reads its state back from the server rather than from what the button did.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, leaveHeldLine,
  named, component, action, clickMenuItem, closeWindow, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedPool, seedProductionLine, seedJob } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const EMPTY_JOB = "Nothing To Run";

test.describe.configure({ mode: "serial" });

test.describe("Production — job lifecycle", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    await resetDatabase(page);
    await leaveHeldLine(page, API);

    const poolId = await seedPool(page);
    const { lineId } = await seedProductionLine(page, { poolIds: [poolId] });
    await seedJob(page, lineId, { name: JOB });
    // The same line, so the only difference between the two jobs is whether
    // anything was imported into them.
    await seedJob(page, lineId, { name: EMPTY_JOB, units: 0 });

    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Jobs");
  });

  test.afterAll(async () => {
    await page.close();
  });

  /** Select a job in the Jobs list. */
  async function selectJob(name) {
    const jobs = windowByTitle(page, "Jobs");
    await settled(jobs);
    await component(jobs, "ui-list-box", "jobs").locator(".option", { hasText: name }).click();
    return jobs;
  }

  /** The value of one of the dashboard's stat tiles. */
  function stat(dashboard, label) {
    return dashboard.locator(".prod-stat")
      .filter({ has: page.locator(".prod-stat-label", { hasText: new RegExp(`^${label}$`) }) })
      .locator(".prod-stat-value");
  }

  test("a job that has never run has no progress to show @lifecycle", async () => {
    const jobs = await selectJob(JOB);

    // Nothing has been produced, so the dashboard is not offered. Editing is,
    // which is the other half of the same rule: a job is paperwork until it
    // starts.
    await expect(named(jobs, "button", "progress-btn")).toBeDisabled();
    await expect(named(jobs, "button", "edit-btn")).toBeEnabled();
    await expect(named(jobs, "button", "toggle-btn")).toHaveText("Start");
  });

  test("starting a job opens its dashboard @lifecycle", async () => {
    const jobs = windowByTitle(page, "Jobs");
    await named(jobs, "button", "toggle-btn").click();

    // Starting takes the admin straight to the screen they will be watching.
    const dashboard = windowByTitle(page, "Job Progress");
    await settled(dashboard);
    await expect(named(dashboard, "span", "job-state")).toHaveText("Active");
    await expect(named(dashboard, "button", "toggle-btn")).toHaveText("Stop");

    // Both units are imported and none has been touched.
    await expect(stat(dashboard, "Total")).toHaveText("2");
    await expect(stat(dashboard, "Pending")).toHaveText("2");
    await expect(stat(dashboard, "Operators")).toHaveText("0");

    // And the list behind it re-read the job rather than leaving it as it was.
    await expect(named(jobs, "button", "toggle-btn")).toHaveText("Stop");
    await expect(named(jobs, "button", "edit-btn")).toBeDisabled();
  });

  test("stopping is confirmed before it pauses anyone @lifecycle", async () => {
    const dashboard = windowByTitle(page, "Job Progress");
    await named(dashboard, "button", "toggle-btn").click();

    // Stopping pauses every operator on the job, so it asks first.
    const confirm = page.locator(".ui-modal", { hasText: "Stop this job?" });
    await expect(confirm).toBeVisible();
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();

    // Written from the reloaded job, not from the click.
    await expect(named(dashboard, "span", "job-state")).toHaveText("Inactive");
    await expect(named(dashboard, "button", "toggle-btn")).toHaveText("Start");

    await closeWindow(dashboard);
  });

  test("a job with no work units cannot be started @lifecycle", async () => {
    const jobs = await selectJob(EMPTY_JOB);
    await named(jobs, "button", "toggle-btn").click();

    // The refusal is the server's, surfaced as a message rather than a screen
    // that quietly stays put.
    const error = page.locator(".ui-modal", { hasText: "Failed to start the job" });
    await expect(error).toBeVisible();
    await error.locator("button", { hasText: /^OK$/ }).first().click();

    // No dashboard: nothing started, so there is nothing to watch.
    await expect(windowByTitle(page, "Job Progress")).toHaveCount(0);
    await expect(named(jobs, "button", "toggle-btn")).toHaveText("Start");
  });
});
