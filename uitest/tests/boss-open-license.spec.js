// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Opening an app asks for a license only when the bundle says it requires one.
 *
 * Scheduler does not. Lean Visualizer does. The private suite already decides
 * who holds a license. This proves the opener calls the check, shows the
 * refusal, and does not build the app.
 */

import { test, expect } from "@playwright/test";
import { account, bootBOSS, ensureAccount, openApplication, signInAs,
         signInAsAdmin, windowByTitle } from "../lib/boss.js";

const SCHEDULER = "io.bithead.scheduler";
const LEAN = "io.bithead.lean-visualizer";
const WHO = account("open-license");

/**
 * POSTs to the license check made while `fn` runs.
 *
 * @param {import('@playwright/test').Page} page
 * @param {() => Promise<void>} fn
 * @returns {Promise<number>}
 */
async function licenseCallsDuring(page, fn) {
  let count = 0;
  const onRequest = (request) => {
    if (request.method() === "POST" && request.url().includes("/account/app-license")) {
      count += 1;
    }
  };
  page.on("request", onRequest);
  try {
    await fn();
  }
  finally {
    page.off("request", onRequest);
  }
  return count;
}

/**
 * Lean Visualizer's place in the ACL tree.
 *
 * @param {import('@playwright/test').Page} page - An admin session
 */
async function leanAcl(page) {
  const tree = await (await page.request.get("/account/acl-tree")).json();
  const app = (tree.tree?.apps || []).find((item) => item.name === LEAN);
  expect(app, "Lean Visualizer is not in the ACL tree").toBeTruthy();
  const employee = app.roles.find((role) => role.name === "Employee");
  const admin = app.roles.find((role) => role.name === "Admin");
  expect(employee, "the Employee role was not registered").toBeTruthy();
  return { employee, admin };
}

/**
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<number>}
 */
async function userId(page) {
  const listed = await (await page.request.get("/account/users")).json();
  const user = (listed.users || []).find((item) => item.name === WHO.email);
  expect(user, `${WHO.email} was not created`).toBeTruthy();
  return parseInt(user.id, 10);
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {number} id
 * @param {boolean} issueLicense
 * @param {{employee: {id: number}, admin: {id: number}|undefined}} acl
 */
async function setLicense(page, id, issueLicense, acl) {
  const granted = await page.request.post("/account/assign-acl", {
    data: {
      userId: id,
      bundleId: LEAN,
      issueLicense: issueLicense,
      addRoles: issueLicense ? [acl.employee.id] : [],
      removeRoles: issueLicense
        ? (acl.admin ? [acl.admin.id] : [])
        : [acl.employee.id].concat(acl.admin ? [acl.admin.id] : [])
    }
  });
  expect(granted.ok(), await granted.text()).toBe(true);
}

test("an app that does not require a license opens without asking", async ({ page }) => {
  await signInAsAdmin(page);
  await bootBOSS(page);

  const calls = await licenseCallsDuring(page, async () => {
    await openApplication(page, SCHEDULER);
  });
  expect(calls).toBe(0);
  const loaded = await page.evaluate(
    (id) => os.application(id) !== null,
    SCHEDULER
  );
  expect(loaded).toBe(true);
});

test("an account without a license is told and the app is not opened", async ({ page }) => {
  await signInAsAdmin(page);
  await ensureAccount(page, WHO);
  const id = await userId(page);
  const acl = await leanAcl(page);
  await setLicense(page, id, false, acl);
  await signInAs(page, WHO);
  await bootBOSS(page);

  const outcome = await page.evaluate(async (id) => {
    let progress = false;
    const observer = new MutationObserver(() => {
      if ((document.body.innerText || "").includes("Loading application")) {
        progress = true;
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    await os.openApplication(id);
    observer.disconnect();
    if ((document.body.innerText || "").includes("Loading application")) {
      progress = true;
    }
    return {
      progress: progress,
      loaded: os.application(id) !== null
    };
  }, LEAN);

  await expect(page.locator(".ui-modal .message")).toHaveText(
    "You do not have a license to use Lean Visualizer."
  );
  expect(outcome.progress).toBe(false);
  expect(outcome.loaded).toBe(false);
});

test("a license lets the account open the app, and a second open does not ask", async ({ page }) => {
  await signInAsAdmin(page);
  await ensureAccount(page, WHO);
  const id = await userId(page);
  const acl = await leanAcl(page);
  await setLicense(page, id, true, acl);
  await signInAs(page, WHO);
  await bootBOSS(page);

  const first = await licenseCallsDuring(page, async () => {
    await openApplication(page, LEAN);
  });
  expect(first).toBe(1);
  await expect(windowByTitle(page, "Capacity report")).toBeVisible();

  const second = await licenseCallsDuring(page, async () => {
    await openApplication(page, LEAN);
  });
  expect(second).toBe(0);
});
