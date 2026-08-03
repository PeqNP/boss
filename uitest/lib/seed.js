// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Building a world for a Production test to run in.
 *
 * Everything here goes through the app's own API rather than its screens. The
 * API enforces the rules, so seeded data is valid by construction — a started
 * job really has a frozen version, a work unit really came from a CSV. It is
 * also fast: a full seed runs in well under a second, where the same path
 * through the UI is dozens of clicks that some other flow already covers.
 *
 * Reset first and every spec is self-sufficient. That matters more than it
 * sounds: the suite runs with one worker against one server and one database,
 * so a file that depended on another having run could not be run on its own —
 * which is exactly what anyone does when something breaks.
 */

import { expect } from "@playwright/test";

export const API = "/api/io.bithead.production";
const DEBUG = "/api/debug/uitests";

/**
 * Empty every app's database.
 *
 * Development builds only. `GET /debug/uitests/memory` is its counterpart for
 * the BOSS database — users and sessions — and neither touches the other.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function resetDatabase(page) {
  const response = await page.request.get(`${DEBUG}/reset`);
  expect(response.ok(),
         "/api/debug/uitests/reset is development-only, and needs the Python service restarted "
         + "after it was added").toBe(true);
}

/**
 * Save the current state so a later test can return to it.
 *
 * Restoring leaves the snapshot itself intact, so one state can be recovered
 * as often as a file needs — reach it once, then branch from it.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name
 */
export async function saveSnapshot(page, name) {
  expect((await page.request.put(`${DEBUG}/snapshot/${name}`)).ok()).toBe(true);
}

/**
 * Return to a saved state.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name
 */
export async function restoreSnapshot(page, name) {
  expect((await page.request.get(`${DEBUG}/snapshot/${name}`)).ok()).toBe(true);
}

async function post(page, path, data) {
  const response = await page.request.post(API + path, { data });
  expect(response.ok(), `POST ${path} failed: ${await response.text()}`).toBe(true);
  return response.json();
}

/**
 * A pool holding one resource per name given.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name
 * @param {string[]} resources
 * @returns {Promise<number>} The pool id
 */
export async function seedPool(page, name = "Test card", resources = ["Card 1"]) {
  const pool = await post(page, "/pool", { name });
  for (const [index, resource] of resources.entries()) {
    await post(page, `/pool/${pool.poolId}/resource`,
               { name: resource, value: `1234${index}`, inService: true });
  }
  return pool.poolId;
}

/**
 * A production line with one operation: a description carrying tokens, and a
 * required serial number. Enough for an operator to have something to read and
 * something to fill in.
 *
 * `steps: 2` adds a second operation with a required checkbox, so a unit takes
 * more than one handover to finish.
 *
 * @returns {Promise<{lineId: number, operationId: number}>}
 */
export async function seedProductionLine(
    page, { name = "CR-One Reader", poolIds = [], withOptions = false, steps = 1 } = {}) {
  const line = await post(page, "/production-line", {
    name,
    columns: ["Location", "Group", "Asset"],
    poolIds
  });
  const operation = await post(page, `/production-line/${line.lineId}/operation`,
                               { name: "Scan reader" });
  const pool = poolIds.length ? " with {pool.Test card}" : "";
  await post(page, `/operation/${operation.operationId}/section`, {
    type: "description", body: `Scan {work_unit.Asset}${pool}`
  });
  await post(page, `/operation/${operation.operationId}/section`, {
    type: "text", name: "serial", label: "Serial", required: true
  });
  // A second operation is what makes "the next step" mean anything: one step
  // completes the whole unit, so a single-operation line cannot show a handover.
  if (steps >= 2) {
    const verify = await post(page, `/production-line/${line.lineId}/operation`,
                              { name: "Verify label" });
    await post(page, `/operation/${verify.operationId}/section`, {
      type: "description", body: "Check the label on {work_unit.Asset}"
    });
    await post(page, `/operation/${verify.operationId}/section`, {
      type: "checkbox", name: "verified", label: "Label is correct", required: true
    });
  }
  if (withOptions) {
    // Renders as a pop-up sized `100%`, which is the one control wide enough
    // to push the manufacturing screen sideways if its borders are counted
    // outside its width.
    await post(page, `/operation/${operation.operationId}/section`, {
      type: "options", name: "result", label: "Result", options: ["Pass", "Fail"]
    });
  }
  return { lineId: line.lineId, operationId: operation.operationId };
}

/**
 * A job with work units imported the way an admin sends them — a file,
 * previewed, then committed.
 *
 * @returns {Promise<number>} The job id
 */
export async function seedJob(page, lineId, { name = "July CR-One Run", units = 2 } = {}) {
  const job = await post(page, "/job", {
    name,
    productionLineId: lineId,
    scheduledStart: "2026-07-06",
    scheduledCompletion: "2026-08-14"
  });

  // No units is a real state, not a degenerate one: it is what a job looks
  // like the moment an admin creates it, and what the app refuses to start.
  if (units === 0) {
    return job.jobId;
  }

  const rows = ["Location,Group,Asset"];
  for (let row = 1; row <= units; row++) {
    rows.push(`Bay ${row},Group A,AST-99${String(row).padStart(2, "0")}`);
  }
  const preview = await (await page.request.post(`${API}/job/${job.jobId}/work-units/preview`, {
    multipart: {
      file: { name: "units.csv", mimeType: "text/csv", buffer: Buffer.from(rows.join("\n") + "\n") }
    }
  })).json();
  expect(preview.errors, "the seeded CSV should be valid").toEqual([]);
  await post(page, `/job/${job.jobId}/work-units/commit`, { uploadId: preview.uploadId });

  return job.jobId;
}

/**
 * The common starting point: a pool, a line requiring it, and a running job.
 *
 * Starting the job pins and freezes the line's version, which is what makes a
 * later edit fork — so anything testing versions wants this.
 *
 * @returns {Promise<{poolId, lineId, operationId, jobId}>}
 */
export async function seedStartedJob(page, { withOptions = false, steps = 1, ...job } = {}) {
  const poolId = await seedPool(page);
  const { lineId, operationId } = await seedProductionLine(page, {
    poolIds: [poolId], withOptions, steps
  });
  const jobId = await seedJob(page, lineId, job);
  await post(page, `/job/${jobId}/start`, {});
  return { poolId, lineId, operationId, jobId };
}

/**
 * A work unit the caller pulled and then failed.
 *
 * Failing is the only way a unit reaches a state an admin has to act on, and
 * requeue is the only action offered for it — so anything covering the
 * dashboard's monitoring half needs one of these to exist.
 *
 * The caller leaves the line afterwards, because holding one changes what the
 * app opens on at launch.
 *
 * @param {import('@playwright/test').Page} page
 * @param {number} jobId
 * @returns {Promise<number>} The work unit id
 */
export async function seedFailedUnit(page, jobId, notes = "Reader would not scan") {
  const lineId = await seedOperatorOnLine(page, jobId);
  const state = await (await page.request.get(`${API}/line/${lineId}/state`)).json();
  const unitId = state.workUnit.id;
  await post(page, `/work-unit/${unitId}/operation/1/fail`, {
    values: { serial: "SN-0001" },
    notes
  });
  await post(page, `/line/${lineId}/leave`, {});
  return unitId;
}

/**
 * Put the caller on a line with a work unit in hand.
 *
 * The app resumes a held line on launch, so a spec that seeds this opens
 * straight onto the manufacturing screen with something to work.
 *
 * @returns {Promise<number>} The line id
 */
export async function seedOperatorOnLine(page, jobId) {
  // `join-info` rather than reading the pool directly: this runs as whoever is
  // joining, and an operator is not an admin — the pool routes would answer
  // 403. It is also the operator's own path, so a seeded join arrives the same
  // way the screen would have arrived at it.
  const info = await (await page.request.get(`${API}/job/${jobId}/join-info`)).json();
  expect(info.blocked, "nothing should stand between this user and the job").toEqual([]);
  const joined = await post(page, `/job/${jobId}/join`, {
    resources: info.pools.map((pool) => ({
      poolId: pool.poolId,
      resourceId: pool.resources[0].id
    }))
  });
  await post(page, `/line/${joined.lineId}/pull`, {});
  return joined.lineId;
}
