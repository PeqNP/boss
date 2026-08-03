// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F9 — Working a unit through to completion.
 *
 * The loop an operator spends the day in, and the densest screen in the app.
 * Two things it must get right: the instructions arrive already interpolated —
 * the operator sees a serial number, never `{work_unit.Asset}` — and a step
 * with an unanswered required field cannot be completed.
 *
 * The line here has two operations, because one step finishing the whole unit
 * would never show a handover between steps.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, component, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob, seedOperatorOnLine } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const FIRST_UNIT = "AST-9901";
const SECOND_UNIT = "AST-9902";
const CARD_VALUE = "12340";

test.describe.configure({ mode: "serial" });

test.describe("Production — working a unit", () => {
  let operator;

  test.beforeAll(async ({ browser }) => {
    const admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    // Two units, so finishing the first has somewhere to go next.
    const { jobId } = await seedStartedJob(admin, { units: 2, steps: 2 });
    await admin.close();

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
  });

  const floor = () => windowByTitle(operator, "Manufacturing Line");
  const sections = () => named(floor(), "div", "sections");
  const steps = () => component(floor(), "ui-list-box", "steps").locator(".option");

  test("the held unit and its first step are on screen @work", async () => {
    await expect(named(floor(), "span", "unit-label")).toContainText(FIRST_UNIT);

    // Both steps listed; the one being worked is marked, and the one after it
    // cannot be opened — operations run in order.
    await expect(steps()).toHaveCount(2);
    await expect(steps().first()).toContainText("Scan reader");
    await expect(steps().nth(1)).toHaveClass(/disabled/);
  });

  test("instructions arrive interpolated, not as tokens @work", async () => {
    const description = sections().locator(".mfg-section-description");

    // The server resolves tokens against this unit and this operator's
    // checked-out card. `{pool.<name>}` renders the resource's *value* — the
    // number printed on the card — because that is what the operator has to
    // match against the thing in their hand, not the label it was filed under.
    await expect(description).toContainText(FIRST_UNIT);
    await expect(description).toContainText(CARD_VALUE);
    // Nothing was left for the client to substitute.
    await expect(description).not.toContainText("{");
  });

  test("a step with an unanswered required field cannot be completed @work", async () => {
    await expect(named(floor(), "button", "complete-btn")).toBeDisabled();

    // Failing stays available: a step that cannot be done is exactly what the
    // Fail button is for, and demanding the field first would trap the
    // operator on a step they cannot finish.
    await expect(named(floor(), "button", "fail-btn")).toBeEnabled();

    await sections().locator('input[type="text"]').fill("SN-0001");
    await expect(named(floor(), "button", "complete-btn")).toBeEnabled();
  });

  test("completing a step hands over to the next @work", async () => {
    await named(floor(), "button", "complete-btn").click();

    // The first step is ticked and the second is now the one being worked.
    await expect(steps().first()).toContainText("✓");
    await expect(steps().nth(1)).not.toHaveClass(/disabled/);

    // Its own sections are drawn, with its own required field unanswered.
    await expect(sections().locator('input[type="checkbox"]')).toBeVisible();
    await expect(named(floor(), "button", "complete-btn")).toBeDisabled();
    // Still the same unit — a handover between steps, not between units.
    await expect(named(floor(), "span", "unit-label")).toContainText(FIRST_UNIT);
  });

  test("completing the last step pulls the next unit @work", async () => {
    await sections().locator('input[type="checkbox"]').check();
    await expect(named(floor(), "button", "complete-btn")).toBeEnabled();
    await named(floor(), "button", "complete-btn").click();

    // The unit is finished, so the operator is handed the next one rather than
    // being left on a screen with nothing to do.
    await expect(named(floor(), "span", "unit-label")).toContainText(SECOND_UNIT);
    // Back to step one, unanswered.
    await expect(steps().first()).toContainText("Scan reader");
    await expect(steps().first()).not.toContainText("✓");
    await expect(named(floor(), "button", "complete-btn")).toBeDisabled();
  });
});
