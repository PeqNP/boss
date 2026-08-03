// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F8 — Joining a line.
 *
 * The operator's way in, and the only screen where two people compete for the
 * same thing. A pool holds physical supplies — one card, one operator — so
 * joining is a claim, and the screen has to show what is still free rather
 * than what exists.
 *
 * The job here is seeded with a single card on purpose: once it is taken, the
 * next person to ask is told why they cannot join and offered nothing to
 * click.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, action, clickMenuItem, selectPopupOption,
  settled
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const CARD = "Card 1";

test.describe.configure({ mode: "serial" });

test.describe("Production — joining a line", () => {
  let admin;
  let operator;
  // The picker is named for its pool, so the test needs the id the seed made
  // rather than assuming a fresh database always hands out 1.
  let poolId;

  test.beforeAll(async ({ browser }) => {
    admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    // One card in the pool: the whole point of the last test.
    ({ poolId } = await seedStartedJob(admin, { name: JOB, units: 3 }));

    operator = await browser.newPage();
    await signInAsOperator(operator);
    await leaveHeldLine(operator, API);
    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);
  });

  test.afterAll(async () => {
    await operator?.close();
    await admin?.close();
  });

  /** Rows in an Active Jobs window. */
  function jobRows(page) {
    return named(windowByTitle(page, "Active Jobs"), "table", "jobs-table")
      .locator("tbody tr");
  }

  test("an operator opens on the jobs they could work @join", async () => {
    // No admin menus: the app strips them for anyone who is not user 1, and
    // an operator with no line opens straight onto Active Jobs.
    const jobs = windowByTitle(operator, "Active Jobs");
    await settled(jobs);

    const row = jobRows(operator).filter({ hasText: JOB });
    await expect(row).toHaveCount(1);
    // Three units imported, none worked.
    await expect(row).toContainText("3");
    await expect(row.locator("button", { hasText: "Join" })).toBeEnabled();
  });

  test("joining lists the pool and what is still free @join", async () => {
    await jobRows(operator).filter({ hasText: JOB })
      .locator("button", { hasText: "Join" }).click();

    const join = windowByTitle(operator, "Join Line");
    await settled(join);
    await expect(named(join, "span", "job-name")).toContainText(JOB);

    // One picker per required pool, built after render through the component
    // factory — so this also proves the factory produces a working menu.
    const picker = join.locator(".ui-popup-menu");
    await expect(picker).toHaveCount(1);
    await expect(picker).toContainText("Test card");
  });

  test("choosing a resource puts the operator on the floor @join", async () => {
    const join = windowByTitle(operator, "Join Line");
    await selectPopupOption(join, `pool-${poolId}`, CARD);
    await action(join, "join").click();

    // The claim succeeded, so the floor screen opens with work in hand.
    const floor = windowByTitle(operator, "Manufacturing Line");
    await settled(floor);
    await expect(join).toHaveCount(0);
  });

  test("an operator already on a line is offered Resume, not Join @join", async () => {
    // Back to the list they came from, which the join refreshed behind them.
    const jobs = windowByTitle(operator, "Active Jobs");
    const row = jobRows(operator).filter({ hasText: JOB });

    await expect(named(jobs, "p", "held-notice")).toContainText(JOB);
    await expect(row.locator("button", { hasText: "Resume" })).toBeVisible();
    await expect(row.locator("button", { hasText: /^Join$/ })).toHaveCount(0);
  });

  test("a job whose only card is taken cannot be joined @join", async () => {
    // The admin asks for the same job. Nothing is left in the pool, and this
    // is not something they can resolve by trying again.
    await bootBOSS(admin);
    await openApplication(admin, PRODUCTION);
    await clickMenuItem(admin, "production-menu", "Active Jobs");
    await settled(windowByTitle(admin, "Active Jobs"));

    await jobRows(admin).filter({ hasText: JOB })
      .locator("button", { hasText: "Join" }).click();

    const join = windowByTitle(admin, "Join Line");
    await settled(join);

    // The server's own reason, shown as written: which pool, and why it is
    // unavailable — "taken or out of service" is not the same problem as an
    // empty pool, and the operator is owed the difference.
    await expect(named(join, "div", "blocked-notice"))
      .toContainText("Every resource in Test card is taken or out of service");
    // And no way to try anyway.
    await expect(named(join, "button", "join-btn")).toHaveCount(0);
  });
});
