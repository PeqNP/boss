// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F11 — Revisiting a completed step.
 *
 * The one place the screen has to tell an operator that saving will cost them
 * work. Correcting an early step invalidates everything decided after it, so
 * the later steps are reset and must be walked again — and the operator is
 * told how many before they commit, not after.
 *
 * The unit here has three operations and arrives with two of them done, so
 * there is something for the reset to actually undo.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, component, action, clickMenuItem,
  closeWindow, selectPopupOption, settled
} from "../lib/boss.js";
import {
  API, resetDatabase, seedStartedJob, seedOperatorOnLine, heldWorkUnit,
  seedCompletedStep
} from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const UNIT = "AST-9901";
const ORIGINAL = "SN-0001";
const CORRECTED = "SN-0002";

test.describe.configure({ mode: "serial" });

test.describe("Production — revisiting a completed step", () => {
  let admin;
  let operator;

  test.beforeAll(async ({ browser }) => {
    admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    const { jobId } = await seedStartedJob(admin, { name: JOB, units: 1, steps: 3 });

    operator = await browser.newPage();
    await signInAsOperator(operator);
    await leaveHeldLine(operator, API);
    const lineId = await seedOperatorOnLine(operator, jobId);

    // Two steps behind them, one to go. Walking there through the screen is
    // F9's subject, not this one's.
    const unitId = await heldWorkUnit(operator, lineId);
    await seedCompletedStep(operator, unitId, 1, { serial: ORIGINAL });
    await seedCompletedStep(operator, unitId, 2, { verified2: true });

    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);
    await settled(windowByTitle(operator, "Manufacturing Line"));
  });

  test.afterAll(async () => {
    await operator?.close();
    await admin?.close();
  });

  const floor = () => windowByTitle(operator, "Manufacturing Line");
  const sections = () => named(floor(), "div", "sections");
  const steps = () => component(floor(), "ui-list-box", "steps").locator(".option");

  test("the operator resumes on the step they had reached @revisit", async () => {
    await expect(named(floor(), "span", "unit-label")).toContainText(UNIT);
    await expect(steps()).toHaveCount(3);

    // Two done, and the third is where they are.
    await expect(steps().nth(0)).toContainText("✓");
    await expect(steps().nth(1)).toContainText("✓");
    await expect(steps().nth(2)).toContainText("▶");
  });

  test("reopening a completed step warns before anything is typed @revisit", async () => {
    await steps().nth(0).click();

    // The banner is the warning, and the button changes what it says it will
    // do — both before the operator has touched a field.
    await expect(named(floor(), "div", "revisit-banner"))
      .toContainText("resets every step after it");
    await expect(named(floor(), "button", "complete-btn")).toHaveText("Save changes");

    // What they entered last time is here to correct, not a blank form.
    await expect(sections().locator('input[type="text"]')).toHaveValue(ORIGINAL);
  });

  test("saving says how much work it costs, and is confirmed @revisit", async () => {
    await sections().locator('input[type="text"]').fill(CORRECTED);
    await named(floor(), "button", "complete-btn").click();

    // Two steps follow this one, but only step 2 was ever completed — and the
    // count has to be the work actually being thrown away, not the steps that
    // happen to come later. It must match what the record ends up saying.
    const confirm = operator.locator(".ui-modal", { hasText: "Save this change?" });
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText("1 completed step(s)");
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();

    // Step 1 stands corrected; the two after it are back to being undone, and
    // the operator is put on the first of them rather than left where they were.
    await expect(steps().nth(0)).toContainText("✓");
    await expect(steps().nth(1)).not.toContainText("✓");
    await expect(steps().nth(1)).toContainText("▶");
    await expect(steps().nth(2)).toHaveClass(/disabled/);
  });

  test("the correction is kept as history, not as an overwrite @revisit", async () => {
    await bootBOSS(admin);
    await openApplication(admin, PRODUCTION);
    await clickMenuItem(admin, "production-menu", "Jobs");

    const jobs = windowByTitle(admin, "Jobs");
    await settled(jobs);
    await component(jobs, "ui-list-box", "jobs").locator(".option", { hasText: JOB }).click();
    await action(jobs, "showProgress").click();

    const dashboard = windowByTitle(admin, "Job Progress");
    await settled(dashboard);
    await selectPopupOption(dashboard, "unit-filter", "All");
    await component(dashboard, "ui-list-box", "work-units").locator(".option").first().click();
    await action(dashboard, "showWorkUnit").click();

    const unit = windowByTitle(admin, "Work Unit");
    await settled(unit);

    // Both values survive: what was recorded, and what it was changed to. A
    // unit's history is the point of keeping one.
    const edits = named(unit, "div", "unit-edits");
    await expect(edits).toContainText(ORIGINAL);
    await expect(edits).toContainText(CORRECTED);
    await expect(edits).toContainText("1 later step(s) reset");

    await closeWindow(unit);
  });
});
