// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F14 — Deep links.
 *
 * `production://…` is how something outside the app sends someone into it — a
 * notification about a stopped line, a link in a message. The screen it lands
 * on has to suit whoever followed it: the same link handed to an operator and
 * to a manager means two different things, and one of them is not allowed.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, signInAsOperator, ensureOperator, openApplication,
  windowByTitle, leaveHeldLine, named, action, settled
} from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const JOB = "July CR-One Run";
const CARD = "Card 1";

/** Follow a `production://` link the way anything outside the app would. */
function openLink(page, link) {
  return page.evaluate((url) => os.openDeepLink(url), link);
}

test.describe.configure({ mode: "serial" });

test.describe("Production — deep links", () => {
  let admin;
  let operator;
  let jobId;

  test.beforeAll(async ({ browser }) => {
    admin = await browser.newPage();
    await signInAsAdmin(admin);
    await resetDatabase(admin);
    await leaveHeldLine(admin, API);
    await ensureOperator(admin);

    ({ jobId } = await seedStartedJob(admin, { name: JOB, units: 2 }));

    operator = await browser.newPage();
    await signInAsOperator(operator);
    await leaveHeldLine(operator, API);

    await bootBOSS(admin);
    await openApplication(admin, PRODUCTION);
    await bootBOSS(operator);
    await openApplication(operator, PRODUCTION);
  });

  test.afterAll(async () => {
    await operator?.close();
    await admin?.close();
  });

  test("production://jobs opens the running jobs @deeplink", async () => {
    // An admin opens on Jobs, so this is a genuine navigation for them.
    await openLink(admin, "production://jobs");

    const jobs = windowByTitle(admin, "Active Jobs");
    await settled(jobs);
    await expect(named(jobs, "table", "jobs-table")).toContainText(JOB);
  });

  test("production://job/{id} opens the dashboard for a manager @deeplink", async () => {
    await openLink(admin, `production://job/${jobId}`);

    const dashboard = windowByTitle(admin, "Job Progress");
    await settled(dashboard);
    await expect(named(dashboard, "span", "job-name")).toContainText(JOB);
  });

  test("production://line/{id} offers to join when no line is held @deeplink", async () => {
    await openLink(operator, `production://line/${jobId}`);

    // They hold nothing, so the link takes them to the claim rather than to a
    // bench that is not theirs.
    const join = windowByTitle(operator, "Join Line");
    await settled(join);
    await expect(named(join, "span", "job-name")).toContainText(JOB);

    await join.locator(".ui-popup-menu .ui-popup-label").click();
    await join.locator(".ui-popup-choices > div", { hasText: CARD }).click();
    await action(join, "join").click();

    await settled(windowByTitle(operator, "Manufacturing Line"));
  });

  test("the same link resumes the line once it is held @deeplink", async () => {
    // Same URL, different outcome: the link means "take me to my work on this
    // job", and what that is depends on whether they have started.
    await openLink(operator, `production://line/${jobId}`);

    await expect(windowByTitle(operator, "Manufacturing Line")).toBeVisible();
    await expect(windowByTitle(operator, "Join Line")).toHaveCount(0);
    await expect(named(windowByTitle(operator, "Manufacturing Line"), "span", "unit-label"))
      .toContainText("AST-9901");
  });

  test("a manager's link does not open for an operator @deeplink", async () => {
    await openLink(operator, `production://job/${jobId}`);

    // The dashboard reads a route only an admin may call, which now answers
    // 403 rather than 500. The operator is told, and — the part that matters —
    // is shown none of it.
    await expect(operator.locator(".ui-modal", { hasText: "Failed to load" })).toBeVisible();
    await expect(named(windowByTitle(operator, "Job Progress"), "span", "job-name"))
      .toBeEmpty();
  });
});
