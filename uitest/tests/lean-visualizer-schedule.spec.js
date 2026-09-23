// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The schedule.
 *
 * File > Schedule draws the track and the feature sitting on it, and a
 * release line only when that release falls inside the chart. Which
 * releases are in the next 180 days is decided on the screen. The
 * duration arithmetic stays in the private suite.
 *
 * The live board is put back when the test ends.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, bootBOSS, openApplication, windowByTitle,
         clickMenuItem, closeAll } from "../lib/boss.js";

const BUNDLE = "io.bithead.lean-visualizer";
const API = `/api/${BUNDLE}`;

/**
 * A local calendar day, as `YYYY-MM-DD`. Noon avoids a midnight crossing.
 *
 * @param {number} offset
 * @returns {string}
 */
function isoDaysFromToday(offset) {
  const value = new Date();
  value.setHours(12, 0, 0, 0);
  value.setDate(value.getDate() + offset);
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${value.getFullYear()}-${month}-${day}`;
}

const FEATURE = {
  kind: "feature",
  id: "feat-door",
  issueKey: "FR-9001",
  name: "Paint the door",
  units: 3,
  completedUnits: 1,
  manualEstWeeks: 1,
  done: false,
  color: "#336699",
  pinnedTrackId: null,
  jiraIssueType: "Epic"
};

const FIXTURE = {
  operators: [{ id: "op-ada", name: "Ada Lane", trackId: "tr-platform" }],
  tracks: [{ id: "tr-platform", name: "Platform", enabled: true, feature: FEATURE }],
  backlog: [],
  releases: [
    { id: "rel-soon", version: "9.9.1", date: isoDaysFromToday(14) },
    { id: "rel-old", version: "9.9.0", date: isoDaysFromToday(-14) }
  ],
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

test.describe("the schedule @window", () => {
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

  test("the schedule shows the track, its feature, and a release inside the chart", async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, BUNDLE);
    await expect(windowByTitle(page, "Board")).toBeVisible();
    await clickMenuItem(page, "file-menu", "Schedule");

    const schedule = windowByTitle(page, "Schedule");
    const row = schedule.locator("table[name='tracks'] tbody tr");
    await expect(row.locator("td").nth(0)).toHaveText("Platform");
    await expect(row.locator("td").nth(2)).toHaveText("Paint the door");
    await expect(schedule.locator(".release-flag")).toContainText("9.9.1");
    await expect(schedule.locator(".gantt")).not.toContainText("9.9.0");
  });
});
