// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F13 — Leaving a line.
 *
 * The operator's own exit, as opposed to F7 where a manager removed them.
 * Leaving is the moment physical things change hands: the card goes back in
 * the drawer and the half-worked unit goes back in the queue. The screen has
 * to say what to carry back, because the operator is about to walk away from
 * the bench and the app is the only thing that knows what they took.
 *
 * The unit here is left half-finished on purpose. Progress is kept, so
 * rejoining must hand back the same unit at the step it had reached — not a
 * fresh one, and not this one from the top.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, component, action, clickMenuItem, settled
} from "../lib/boss.js";
import {
  API, resetDatabase, seedStartedJob, seedOperatorOnLine, heldWorkUnit,
  seedCompletedStep
} from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const POOL = "Test card";
const UNIT = "AST-9901";
const CARD = "Card 1";
const SERIAL = "SN-0001";

test.describe.configure({ mode: "serial" });

test.describe("Production — leaving a line", () => {
  let admin;
  let operator;

  test.beforeAll(async ({ browser }) => {
    admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    // One unit, two steps: the operator leaves partway through it.
    const { jobId } = await seedStartedJob(admin, { name: JOB, units: 1, steps: 2 });

    operator = await browser.newPage();
    await signInAsOperator(operator);
    await leaveHeldLine(operator, API);
    const lineId = await seedOperatorOnLine(operator, jobId);
    const unitId = await heldWorkUnit(operator, lineId);
    await seedCompletedStep(operator, unitId, 1, { serial: SERIAL });

    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);
    await settled(windowByTitle(operator, "Manufacturing Line"));
  });

  test.afterAll(async () => {
    await operator?.close();
    await admin?.close();
  });

  const floor = () => windowByTitle(operator, "Manufacturing Line");
  const steps = () => component(floor(), "ui-list-box", "steps").locator(".option");

  test("leaving says what it costs before it happens @leave", async () => {
    await expect(named(floor(), "span", "unit-label")).toContainText(UNIT);
    await clickMenuItem(operator, "file-menu", "Leave Line");

    // The operator is holding a unit, so the message says so — and says the
    // progress survives, which is the difference between leaving and failing.
    const confirm = operator.locator(".ui-modal", { hasText: "Leave this line?" });
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText("progress kept");
    await confirm.locator("button", { hasText: /^OK$|^Yes$|^Delete$/ }).first().click();
  });

  test("the operator is told what to carry back @leave", async () => {
    // The one thing the app knows and the operator might not: which card they
    // signed out.
    const alert = operator.locator(".ui-modal", { hasText: "Please return" });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(CARD);
    await expect(alert).toContainText(POOL);
    await alert.locator("button", { hasText: /^OK$/ }).first().click();

    // Nothing left to work, so the screen goes.
    await expect(floor()).toHaveCount(0);
  });

  test("the card is back in the pool @leave", async () => {
    await bootBOSS(admin);
    await openApplication(admin, PRODUCTION);
    await clickMenuItem(admin, "production-menu", "Pools");

    const pools = windowByTitle(admin, "Pools");
    await settled(pools);
    await component(pools, "ui-list-box", "pools").locator(".option", { hasText: POOL }).click();
    await action(pools, "editPool").click();

    const pool = windowByTitle(admin, "Pool");
    await settled(pool);

    // Listed without a holder, and so nothing to force back.
    const card = component(pool, "ui-list-box", "resources")
      .locator(".option", { hasText: CARD });
    await expect(card).toHaveCount(1);
    await expect(card).not.toContainText("held by");
    await card.click();
    await expect(named(pool, "button", "return-btn")).toBeDisabled();
  });

  test("rejoining hands back the same unit, where it was left @leave", async () => {
    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);

    // No line held, so they land on the job list rather than the floor.
    const jobs = windowByTitle(operator, "Active Jobs");
    await settled(jobs);
    await named(jobs, "table", "jobs-table").locator("tbody tr", { hasText: JOB })
      .locator("button", { hasText: "Join" }).click();

    const join = windowByTitle(operator, "Join Line");
    await settled(join);
    // The card is free again, so it can be taken a second time.
    await join.locator(".ui-popup-menu .ui-popup-label").click();
    await join.locator(".ui-popup-choices > div", { hasText: CARD }).click();
    await action(join, "join").click();

    await settled(windowByTitle(operator, "Manufacturing Line"));

    // The same unit, at the step it had reached — a partially-worked unit is
    // handed back before a fresh one, and it is not restarted.
    await expect(named(floor(), "span", "unit-label")).toContainText(UNIT);
    await expect(steps().nth(0)).toContainText("✓");
    await expect(steps().nth(1)).toContainText("▶");
  });
});
