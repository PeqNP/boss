// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F12 — Andon: stop, block, clear.
 *
 * The mirror of F7. There a manager stopped the line and the operator was
 * given no way to clear it; here the operator raises the andon and the rule
 * points the other way — a manager cannot clear it either. Whoever stopped the
 * line is the only one who knows it is safe to start again.
 *
 * It is also the one flow driven by a notification rather than a click: the
 * manager's dashboard learns the line came back without anyone refreshing it.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, component, action, clickMenuItem, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob, seedOperatorOnLine } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const OPERATOR_NAME = "Dana Operator";
const REASON = "Reader is jammed";

test.describe.configure({ mode: "serial" });

test.describe("Production — andon", () => {
  let admin;
  let operator;

  test.beforeAll(async ({ browser }) => {
    admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    const { jobId } = await seedStartedJob(admin, { name: JOB, units: 2 });

    operator = await browser.newPage();
    await signInAsOperator(operator);
    await leaveHeldLine(operator, API);
    await seedOperatorOnLine(operator, jobId);
    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);
    await settled(windowByTitle(operator, "Manufacturing Line"));

    // The manager watches while the operator works.
    await bootBOSS(admin);
    await openApplication(admin, PRODUCTION);
    await clickMenuItem(admin, "production-menu", "Jobs");
    const jobs = windowByTitle(admin, "Jobs");
    await settled(jobs);
    await component(jobs, "ui-list-box", "jobs").locator(".option", { hasText: JOB }).click();
    await action(jobs, "showProgress").click();
    await settled(windowByTitle(admin, "Job Progress"));
  });

  test.afterAll(async () => {
    await operator?.close();
    await admin?.close();
  });

  const floor = () => windowByTitle(operator, "Manufacturing Line");
  const dashboard = () => windowByTitle(admin, "Job Progress");

  function operatorRow() {
    return named(dashboard(), "table", "lines-table")
      .locator("tbody tr", { hasText: OPERATOR_NAME });
  }

  test("raising the andon asks for a reason @andon", async () => {
    await clickMenuItem(operator, "file-menu", "Stop Line");

    const stop = windowByTitle(operator, "Stop Line");
    await expect(stop).toBeVisible();
    await named(stop, "textarea", "reason").fill(REASON);
    await action(stop, "stopLine").click();

    // The line is covered, and the operator is told help is coming rather than
    // being left looking at a form they cannot use.
    const blocked = windowByTitle(operator, "Line stopped");
    await expect(blocked).toBeVisible();
    await expect(named(blocked, "p", "blocked-body")).toContainText("on the way");
    // Their own words are read back, so they can see what was reported.
    await expect(named(blocked, "p", "blocked-body")).toContainText(REASON);
  });

  test("the manager sees the stop and the reason for it @andon", async () => {
    await expect(operatorRow()).toContainText(/stopped/i);

    // The reason is the point of an andon: it is what tells the manager which
    // problem they are walking over to.
    await expect(operatorRow()).toContainText(REASON);
  });

  test("a manager cannot clear an andon they did not raise @andon", async () => {
    await operatorRow().click();
    await named(dashboard(), "button", "stop-btn").click();

    // Refused, and told why — "try again later" would be wrong advice, since
    // trying again refuses in exactly the same way.
    const error = admin.locator(".ui-modal", { hasText: "only the operator can resume it" });
    await expect(error).toBeVisible();
    await error.locator("button", { hasText: /^OK$/ }).first().click();

    // And the line really is still stopped.
    await expect(operatorRow()).toContainText(/stopped/i);
    // The operator's screen is still covered.
    await expect(windowByTitle(operator, "Line stopped")).toBeVisible();
  });

  test("the operator clears it, and the dashboard learns without asking @andon", async () => {
    const blocked = windowByTitle(operator, "Line stopped");
    // The button exists here, unlike F7: this block is theirs.
    await named(blocked, "button", "clear-btn").click();

    await expect(blocked).toHaveCount(0);
    // Back to the unit they were holding.
    await expect(named(floor(), "span", "unit-label")).toContainText("AST-9901");

    // Nobody touched the dashboard. It updated because the line announced it.
    await expect(operatorRow()).toContainText(/working/i);
  });
});
