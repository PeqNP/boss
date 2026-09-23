// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The board saves and reads back.
 *
 * The rows on screen are whatever `PUT /model` stored. A renamed operator
 * has to survive closing the app, which is the wiring the private suite
 * cannot see: the blur saved, and the next open read the new name.
 *
 * The live board is put back when the test ends. This app is not on the
 * UI reset.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, bootBOSS, openApplication, windowByTitle,
         closeAll } from "../lib/boss.js";

const BUNDLE = "io.bithead.lean-visualizer";
const API = `/api/${BUNDLE}`;

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

/** @param {import('@playwright/test').Page} page */
async function openBoard(page) {
  await bootBOSS(page);
  await openApplication(page, BUNDLE);
  const board = windowByTitle(page, "Board");
  await expect(board.locator("[data-role='operator-name']")).toHaveText("Ada Lane");
  return board;
}

test.describe("the board saves and reads back @window", () => {
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

  test("a saved board shows the operator, the track, and the feature", async ({ page }) => {
    const board = await openBoard(page);
    await expect(board.locator("[data-role='track-name']")).toHaveText("Platform");
    await expect(board.locator("table[name='backlog']")).toContainText("FR-9001: Paint the door");
  });

  test("renaming an operator reads back", async ({ page }) => {
    const board = await openBoard(page);
    const label = board.locator("[data-role='operator-name']");
    await label.click();
    await label.locator("input").fill("Ada Renamed");
    await label.locator("input").press("Enter");
    await expect(board.locator("[data-role='operator-name']")).toHaveText("Ada Renamed");

    await closeAll(page, [BUNDLE]);
    await bootBOSS(page);
    await openApplication(page, BUNDLE);
    const again = windowByTitle(page, "Board");
    await expect(again.locator("[data-role='operator-name']")).toHaveText("Ada Renamed");
  });
});
