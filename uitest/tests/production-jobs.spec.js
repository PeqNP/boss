// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F4 — Creating a job and importing work units.
 *
 * The only file upload in the app, and the only two-step write: a CSV is
 * previewed and reported on before anything is stored, so an admin confirms
 * what they are about to replace rather than discovering it afterwards.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, leaveHeldLine,
  named, component, action, clickMenuItem, selectPopupOption, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedPool, seedProductionLine } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const LINE = "CR-One Reader";
const JOB = "July CR-One Run";

const VALID_CSV = "Location,Group,Asset\nBay 1,Group A,AST-9901\nBay 2,Group A,AST-9902\n";
const MISSING_COLUMN_CSV = "Location,Group\nBay 1,Group A\n";

function csv(contents) {
  return { name: "units.csv", mimeType: "text/csv", buffer: Buffer.from(contents) };
}

test.describe.configure({ mode: "serial" });

test.describe("Production — jobs and work units", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    await resetDatabase(page);
    await leaveHeldLine(page, API);

    // A line to run the job against. F2 covers authoring one by hand.
    const poolId = await seedPool(page);
    await seedProductionLine(page, { poolIds: [poolId] });

    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Jobs");
  });

  test.afterAll(async () => {
    await page.close();
  });

  test("a job is created against a production line @jobs", async () => {
    const jobs = windowByTitle(page, "Jobs");
    await expect(jobs).toBeVisible();
    await action(jobs, "addJob").click();

    const job = windowByTitle(page, "Job");
    await settled(job);

    // Uploading is refused until the job exists, because the work units have
    // to belong to something.
    await expect(named(job, "button", "upload-btn")).toBeDisabled();
    await expect(named(job, "span", "work-unit-count"))
      .toContainText("Save the job before uploading");

    await named(job, "input", "job-name").fill(JOB);
    await named(job, "input", "scheduled-start").fill("2026-07-06");
    await named(job, "input", "scheduled-completion").fill("2026-08-14");
    await selectPopupOption(job, "production-line", LINE);
    await action(job, "save").click();

    await expect(component(jobs, "ui-list-box", "jobs").locator(".option", {
      hasText: JOB
    })).toBeVisible();
  });

  test("a CSV is previewed before anything is written @jobs", async () => {
    const jobs = windowByTitle(page, "Jobs");
    await component(jobs, "ui-list-box", "jobs").locator(".option", { hasText: JOB }).click();
    await action(jobs, "editJob").click();

    const job = windowByTitle(page, "Job");
    await settled(job);
    await expect(named(job, "input", "job-name")).toHaveValue(JOB);
    await expect(named(job, "button", "upload-btn")).toBeEnabled();

    // The native picker is hidden; setting the files fires the same `change`
    // the visible button would have produced.
    await named(job, "input", "csv-file").setInputFiles(csv(VALID_CSV));

    await expect(named(job, "span", "preview-summary")).toContainText("2");
    await expect(named(job, "div", "preview-errors")).toBeEmpty();
    // Still a preview: the job has no work units until it is committed.
    await expect(named(job, "span", "work-unit-count")).not.toContainText("2 work unit");
  });

  test("committing replaces the job's work units @jobs", async () => {
    const job = windowByTitle(page, "Job");
    await named(job, "button", "commit-btn").click();

    // Replacing is destructive, so it is confirmed first.
    const confirm = page.locator(".ui-modal", { hasText: "Replace all work units" });
    await expect(confirm).toBeVisible();
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();

    await expect(named(job, "span", "work-unit-count")).toContainText("2");
  });

  test("a CSV missing a declared column is reported, not committed @jobs", async () => {
    const job = windowByTitle(page, "Job");
    await named(job, "input", "csv-file").setInputFiles(csv(MISSING_COLUMN_CSV));

    // The line declares Location, Group, and Asset; this file has no Asset.
    await expect(named(job, "div", "preview-errors")).toContainText("Asset");
  });
});
