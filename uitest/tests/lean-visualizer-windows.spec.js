// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The windows the board opens.
 *
 * Releases and Save Checkpoint take their lists from the board. Tasks shows
 * the week the board asked for. Finished work offers a year of 2026 or
 * later. A note and a virtual feature are written through the board and
 * are still there after it is opened again.
 *
 * Save Checkpoint is not clicked. Saving one calls Jira. Finished work
 * is answered by the test stand-in, not by Jira. The live board is put
 * back when the test ends.
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

const FIXTURE = {
  operators: [{ id: "op-ada", name: "Ada Lane", trackId: null }],
  tracks: [],
  backlog: [],
  releases: [
    { id: "rel-old", version: "9.9.0", date: isoDaysFromToday(-14) },
    { id: "rel-today", version: "9.9.2", date: isoDaysFromToday(0) },
    { id: "rel-soon", version: "9.9.1", date: isoDaysFromToday(14) }
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

/** @param {import('@playwright/test').Page} page */
async function openBoard(page) {
  await bootBOSS(page);
  await openApplication(page, BUNDLE);
  const board = windowByTitle(page, "Board");
  await expect(board.locator("[data-role='operator-name']")).toHaveText("Ada Lane");
  return board;
}

test.describe("windows the board opens @window", () => {
  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    const standIn = await page.request.put(`/api/debug/uitests/jira/${BUNDLE}`, {
      data: { fixture: "finished-work-empty" }
    });
    expect(standIn.ok(), await standIn.text()).toBe(true);
    const model = await readModel(page);
    original = model.state;
    await writeModel(page, model.revision, FIXTURE);
  });

  test.afterEach(async ({ page }) => {
    await page.request.delete(`/api/debug/uitests/jira/${BUNDLE}`);
    await closeAll(page, [BUNDLE]);
    if (original === null) {
      return;
    }
    const current = await readModel(page);
    await writeModel(page, current.revision, original);
    original = null;
  });

  test("releases, checkpoint, tasks, finished work, a note, and a virtual feature", async ({ page }) => {
    test.setTimeout(120_000);
    const board = await openBoard(page);

    await clickMenuItem(page, "file-menu", "Releases");
    const releases = windowByTitle(page, "Manage Releases");
    const versions = releases.locator("input[data-role='version']");
    await expect(versions).toHaveCount(2);
    await expect(versions.nth(0)).toHaveValue("9.9.2");
    await expect(versions.nth(1)).toHaveValue("9.9.1");
    await releases.getByRole("button", { name: "Cancel" }).click();
    await expect(releases).toBeHidden();

    await clickMenuItem(page, "file-menu", "Save Checkpoint");
    const checkpoint = windowByTitle(page, "Save Checkpoint");
    const choices = checkpoint.locator(".ui-list-box");
    await expect(choices).toContainText("9.9.0");
    await expect(choices).toContainText("9.9.2");
    await expect(choices).not.toContainText("9.9.1");
    await checkpoint.getByRole("button", { name: "Cancel" }).click();
    await expect(checkpoint).toBeHidden();

    const week = await board.locator("span[name='week-label']").textContent();
    await board.getByRole("button", { name: "View Tasks" }).click();
    const tasks = windowByTitle(page, "Tasks Included In Units / Week");
    await expect(tasks.locator("span[name='week']")).toContainText(week.trim());
    await tasks.getByRole("button", { name: "Close" }).click();

    await clickMenuItem(page, "file-menu", "Finished work");
    const finished = windowByTitle(page, "Finished Work");
    await expect.poll(async () => Number(await finished.locator("select[name='year']").inputValue()))
      .toBeGreaterThanOrEqual(2026);
    await expect(finished.locator("table[name='finished']")).toContainText("No finished work for this year.");
    await finished.getByRole("button", { name: "Close" }).click();

    await board.getByRole("button", { name: "Add Notes" }).click();
    const notes = windowByTitle(page, "Notes");
    await notes.locator("textarea[name='note']").fill("Hold the portal review.");
    await notes.getByRole("button", { name: "Save" }).click();
    await expect(notes).toBeHidden();
    await expect.poll(async () => {
      const model = await readModel(page);
      return Object.values(model.state.weeklyNotes || {}).join("\n");
    }).toContain("Hold the portal review.");

    await closeAll(page, [BUNDLE]);
    const again = await openBoard(page);
    await again.getByRole("button", { name: "Add Notes" }).click();
    await expect(windowByTitle(page, "Notes").locator("textarea[name='note']"))
      .toHaveValue("Hold the portal review.");
    await windowByTitle(page, "Notes").getByRole("button", { name: "Cancel" }).click();

    await again.getByRole("button", { name: "Add virtual work unit" }).click();
    const virtual = windowByTitle(page, "Virtual work unit");
    await virtual.locator("input[name='name']").fill("Nightly queue");
    await virtual.locator("textarea[name='jql']").fill("project = SUP");
    await virtual.getByRole("button", { name: "Save" }).click();
    await expect(virtual).toBeHidden();
    await expect(again.locator("table[name='backlog']")).toContainText("Nightly queue");

    await closeAll(page, [BUNDLE]);
    const restored = await openBoard(page);
    await expect(restored.locator("table[name='backlog']")).toContainText("Nightly queue");
  });
});
