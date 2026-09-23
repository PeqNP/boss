// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The capacity report.
 *
 * Dashboards opens the report, and the tables are the report response.
 * The eight-week arithmetic stays in the private suite. An operator with
 * no stored weeks is enough to prove the row is read: zeros, in the
 * column order the board's rate is built from.
 *
 * The live board is put back when the test ends.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, bootBOSS, openApplication, windowByTitle,
         clickMenuItem, closeAll } from "../lib/boss.js";

const BUNDLE = "io.bithead.lean-visualizer";
const API = `/api/${BUNDLE}`;

const PILLARS = [
  "Growth / Acquisition",
  "New Features / Retention",
  "Tech Debt / Stability",
  "Process Efficiency / Cost Savings",
  "Unassigned"
];

const FIXTURE = {
  operators: [{ id: "op-ada", name: "Ada Lane", trackId: "tr-platform" }],
  tracks: [{ id: "tr-platform", name: "Platform", enabled: true, feature: null }],
  backlog: [{
    kind: "feature",
    id: "feat-door",
    issueKey: "FR-9001",
    name: "Paint the door",
    units: 3,
    completedUnits: 1,
    manualEstWeeks: 0,
    done: false,
    color: "#336699",
    pinnedTrackId: null,
    jiraIssueType: "Epic"
  }],
  releases: [],
  weeklyNotes: {}
};

/** The board as it was before this file replaced it. */
let original = null;

/**
 * @param {import('@playwright/test').APIResponse} response
 * @param {string} what
 * @returns {Promise<object>}
 */
async function body(response, what) {
  const text = await response.text();
  expect(response.ok(), `${what}: HTTP ${response.status()} — ${text}`).toBe(true);
  return JSON.parse(text);
}

/** @param {import('@playwright/test').Page} page */
async function readModel(page) {
  return body(await page.request.get(`${API}/model`), "GET /model");
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {number} revision
 * @param {object} state
 */
async function writeModel(page, revision, state) {
  return body(await page.request.put(`${API}/model`, { data: { revision, state } }),
              "PUT /model");
}

test.describe("the capacity report @window", () => {
  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    const model = await readModel(page);
    original = model.state;
    await writeModel(page, model.revision, FIXTURE);
  });

  test.afterEach(async ({ page }) => {
    await closeAll(page, [BUNDLE]);
    if (original === null) {
      return;
    }
    const current = await readModel(page);
    await writeModel(page, current.revision, original);
    original = null;
  });

  test("the report shows the operator, the rates, and every pillar", async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, BUNDLE);
    await expect(windowByTitle(page, "Board")).toBeVisible();
    await clickMenuItem(page, "go-menu", "Capacity report");

    const report = windowByTitle(page, "Capacity report");
    await expect(report.locator("table[name='rates'] th")).toHaveText([
      "Operator", "Planned", "Rate", "Unplanned", "Rate", "Total Rate", "Weeks"
    ]);
    const ada = report.locator("table[name='rates'] tbody tr", { hasText: "Ada Lane" });
    await expect(ada.locator("td")).toHaveText([
      "Ada Lane", "0", "0.00", "0", "0.00", "0.00", "0"
    ]);

    const pillars = report.locator("table[name='open-pillars'] tbody tr");
    await expect(pillars).toHaveCount(PILLARS.length);
    for (let index = 0; index < PILLARS.length; index++) {
      const name = PILLARS[index];
      const count = name === "Unassigned" ? "1" : "0";
      const share = name === "Unassigned" ? "100%" : "0%";
      await expect(pillars.nth(index).locator("td")).toHaveText([name, count, share]);
    }

    await expect(report.locator("button[name='checkpoint']")).toBeVisible();
  });
});
