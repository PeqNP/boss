// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F10 — Failing a unit.
 *
 * A failure is the one thing on the floor that produces no product and must
 * still produce a record. The note is that record — the only account of what
 * went wrong — so the screen refuses to send the failure without one rather
 * than letting the server reject it after the fact.
 *
 * The other half is the round trip: the unit leaves the operator's hands and
 * turns up on the manager's dashboard as something to deal with.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, component, action, clickMenuItem,
  closeWindow, selectPopupOption, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob, seedOperatorOnLine } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const FIRST_UNIT = "AST-9901";
const SECOND_UNIT = "AST-9902";
const NOTES = "Reader would not power on";

test.describe.configure({ mode: "serial" });

test.describe("Production — failing a unit", () => {
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
  });

  test.afterAll(async () => {
    await operator?.close();
    await admin?.close();
  });

  const floor = () => windowByTitle(operator, "Manufacturing Line");

  test("failing without a note is refused before it is sent @fail", async () => {
    await expect(named(floor(), "span", "unit-label")).toContainText(FIRST_UNIT);
    await named(floor(), "button", "fail-btn").click();

    // The screen asks for the note itself. Nothing was posted, so there is no
    // confirmation to answer — just the reason.
    const alert = operator.locator(".ui-modal", { hasText: "describe what went wrong" });
    await expect(alert).toBeVisible();
    await alert.locator("button", { hasText: /^OK$/ }).first().click();

    // Still holding the same unit.
    await expect(named(floor(), "span", "unit-label")).toContainText(FIRST_UNIT);
  });

  test("failing with a note moves the operator on @fail", async () => {
    // The required serial is still empty, and stays that way: a step is failed
    // precisely because it could not be completed, so completion's rules
    // cannot gate it.
    await expect(named(floor(), "div", "sections").locator('input[type="text"]'))
      .toHaveValue("");

    await named(floor(), "textarea", "notes").fill(NOTES);
    await named(floor(), "button", "fail-btn").click();

    // The unit leaves the queue, so it is confirmed first.
    const confirm = operator.locator(".ui-modal", { hasText: "Fail this work unit?" });
    await expect(confirm).toBeVisible();
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();

    // The next unit arrives, with a clean note field — the note belonged to
    // the failure, not to the operator.
    await expect(named(floor(), "span", "unit-label")).toContainText(SECOND_UNIT);
    await expect(named(floor(), "textarea", "notes")).toHaveValue("");
  });

  test("the dashboard picks it up as a failure @fail", async () => {
    await bootBOSS(admin);
    await openApplication(admin, PRODUCTION);
    await clickMenuItem(admin, "production-menu", "Jobs");

    const jobs = windowByTitle(admin, "Jobs");
    await settled(jobs);
    await component(jobs, "ui-list-box", "jobs").locator(".option", { hasText: JOB }).click();
    await action(jobs, "showProgress").click();

    const dashboard = windowByTitle(admin, "Job Progress");
    await settled(dashboard);

    await selectPopupOption(dashboard, "unit-filter", "Failed");
    const units = component(dashboard, "ui-list-box", "work-units").locator(".option");
    await expect(units).toHaveCount(1);
    await expect(units).toContainText(FIRST_UNIT);
  });

  test("the operator's account of it survives to the record @fail", async () => {
    const dashboard = windowByTitle(admin, "Job Progress");
    await component(dashboard, "ui-list-box", "work-units").locator(".option").first().click();
    await action(dashboard, "showWorkUnit").click();

    const unit = windowByTitle(admin, "Work Unit");
    await settled(unit);

    await expect(named(unit, "span", "unit-state")).toHaveText("failed");
    // The note, verbatim. Not who wrote it: a failed unit records nobody —
    // see the finding in `ui-plan.md`.
    await expect(named(unit, "div", "unit-operations")).toContainText(NOTES);
    await expect(named(unit, "div", "unit-resources")).toContainText("Card 1");

    await closeWindow(unit);
  });
});
