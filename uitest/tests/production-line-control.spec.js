// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F7 — Line control from the dashboard.
 *
 * The first flow with two people in it, and the only way to test a rule about
 * *who* acted. Pause, stop, and resume are shared routes: an operator calls
 * them from the floor and a manager calls them from the dashboard, and what
 * separates the two is the origin recorded against the block. A block a
 * manager raised is not the operator's to clear.
 *
 * An admin driving both sides would prove the buttons are wired and nothing
 * about the rule, so this runs two browser contexts — two cookie jars, two
 * identities, both screens live at once.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, component, action, clickMenuItem, settled
} from "../lib/boss.js";
import {
  API, resetDatabase, seedStartedJob, seedOperatorOnLine
} from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const OPERATOR_NAME = "Dana Operator";

test.describe.configure({ mode: "serial" });

test.describe("Production — line control", () => {
  let admin;
  let operator;

  test.beforeAll(async ({ browser }) => {
    // `newPage` gives each its own context, so the two never share a session.
    admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    const { jobId } = await seedStartedJob(admin, { name: JOB });

    // The operator joins and pulls through the API, then launches: the app
    // resumes a held line, so they open straight onto the floor screen.
    operator = await browser.newPage();
    await signInAsOperator(operator);
    await seedOperatorOnLine(operator, jobId);
    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);
    await settled(windowByTitle(operator, "Manufacturing Line"));

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

  /** Every line on the job. Only the operator has one. */
  function lineRows() {
    const dashboard = windowByTitle(admin, "Job Progress");
    return named(dashboard, "table", "lines-table").locator("tbody tr");
  }

  /** The operator's row, found the way a manager finds it: by who it is. */
  function operatorRow() {
    return lineRows().filter({ hasText: OPERATOR_NAME });
  }

  test("the dashboard lists the operator working the line @control", async () => {
    await expect(operatorRow()).toHaveCount(1);
    await expect(operatorRow()).toContainText(/working/i);

    // Selecting the row is what arms the controls; nothing is offered until
    // the manager has said which line they mean.
    const dashboard = windowByTitle(admin, "Job Progress");
    await expect(named(dashboard, "button", "pause-btn")).toBeDisabled();
    await operatorRow().click();
    await expect(named(dashboard, "button", "pause-btn")).toBeEnabled();
    await expect(named(dashboard, "button", "pause-btn")).toHaveText("Pause");
  });

  test("pausing from the dashboard reaches the operator's screen @control", async () => {
    const dashboard = windowByTitle(admin, "Job Progress");
    await named(dashboard, "button", "pause-btn").click();

    await expect(operatorRow()).toContainText(/paused/i);
    // The same button now offers the way back, which is how the dashboard says
    // this block is the manager's.
    await expect(named(dashboard, "button", "pause-btn")).toHaveText("Resume");

    // The operator is told, without having asked. This arrives over the event
    // stream, so it is also the proof that the two screens are connected.
    const blocked = windowByTitle(operator, "Line paused");
    await expect(blocked).toBeVisible();
    await expect(named(blocked, "p", "blocked-body")).toContainText("line manager paused");
  });

  test("the operator is given no way to clear a manager's block @control", async () => {
    const blocked = windowByTitle(operator, "Line paused");

    // Not a refusal they have to run into: the button is not there at all.
    // "Only the origin that raised a block may clear it" is a server rule, and
    // this is the screen agreeing with it rather than testing it.
    await expect(blocked.locator('button[name="clear-btn"]')).toHaveCount(0);
  });

  test("resuming from the dashboard returns the operator to work @control", async () => {
    const dashboard = windowByTitle(admin, "Job Progress");
    await named(dashboard, "button", "pause-btn").click();

    await expect(operatorRow()).toContainText(/working/i);
    await expect(named(dashboard, "button", "pause-btn")).toHaveText("Pause");

    // The block closes on the operator's screen too.
    await expect(windowByTitle(operator, "Line paused")).toHaveCount(0);
  });

  test("stopping a line carries a reason the operator can read @control", async () => {
    const dashboard = windowByTitle(admin, "Job Progress");
    await named(dashboard, "button", "stop-btn").click();

    await expect(operatorRow()).toContainText(/stopped/i);
    await expect(named(dashboard, "button", "stop-btn")).toHaveText("Resume line");
    // A stop is more serious than a pause, so it takes the pause button away
    // rather than letting a manager half-clear it.
    await expect(named(dashboard, "button", "pause-btn")).toBeDisabled();

    const blocked = windowByTitle(operator, "Line stopped");
    await expect(blocked).toBeVisible();
    await expect(named(blocked, "p", "blocked-body")).toContainText("line manager stopped");

    await named(dashboard, "button", "stop-btn").click();
    await expect(operatorRow()).toContainText(/working/i);
  });

  test("removing an operator ends their line @control", async () => {
    const dashboard = windowByTitle(admin, "Job Progress");
    await named(dashboard, "button", "leave-btn").click();

    // Their work unit is released with its progress kept, so this is confirmed.
    const confirm = admin.locator(".ui-modal", { hasText: OPERATOR_NAME });
    await expect(confirm).toBeVisible();
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();

    // The line stays listed rather than disappearing: a line that was worked
    // is history, and it carries the operator's metrics.
    await expect(lineRows()).toHaveCount(1);
    await expect(operatorRow()).toContainText(/left/i);

    // The floor screen closes: there is no line left to work.
    await expect(windowByTitle(operator, "Manufacturing Line")).toHaveCount(0);
  });
});
