// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Who the app opens for.
 *
 * An admin lands on the board and an employee lands on the capacity report.
 * The menus are the wiring: a role that can open the wrong window is a menu
 * item left in place, which the private suite never draws.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAs, bootBOSS, openApplication, windowByTitle,
         clickMenuItem, account, ensureAccount, closeAll } from "../lib/boss.js";

const BUNDLE = "io.bithead.lean-visualizer";
const EMPLOYEE = account("lean-employee");

/**
 * The visible items of an OS menu, label excluded.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} name - The `<select>` name
 * @returns {Promise<string[]>}
 */
async function menuLabels(page, name) {
  const choices = page.locator(`.ui-menu-${name} .ui-popup-choice`);
  await expect(choices.first()).toBeAttached();
  return (await choices.allTextContents()).map((text) => text.trim());
}

/**
 * Grant this app's Employee role, and the license that puts the app on
 * the session.
 *
 * A role by itself is refused: access still requires the app in the token.
 * The grant has to happen before `signInAs`, because the token is minted
 * at sign-in.
 *
 * @param {import('@playwright/test').Page} page - An admin's page
 * @param {string|number} userId
 */
async function grantEmployee(page, userId) {
  const tree = await (await page.request.get("/account/acl-tree")).json();
  const apps = tree.tree.apps;
  const app = apps.find((item) => item.name === BUNDLE);
  expect(app, "Lean Visualizer is not in the ACL tree").toBeTruthy();
  const employee = app.roles.find((role) => role.name === "Employee");
  const admin = app.roles.find((role) => role.name === "Admin");
  expect(employee, "the Employee role was not registered").toBeTruthy();

  const granted = await page.request.post("/account/assign-acl", {
    data: {
      userId: parseInt(userId, 10),
      bundleId: BUNDLE,
      issueLicense: true,
      addRoles: [employee.id],
      removeRoles: admin ? [admin.id] : []
    }
  });
  expect(granted.ok(), await granted.text()).toBe(true);
}

test.describe("who opens what @window", () => {
  test.afterEach(async ({ page }) => {
    await closeAll(page, [BUNDLE]);
  });

  test("an admin opens on the board", async ({ page }) => {
    await signInAsAdmin(page);
    await bootBOSS(page);
    await openApplication(page, BUNDLE);

    await expect(windowByTitle(page, "Board")).toBeVisible();
    await expect(menuLabels(page, "go-menu")).resolves.toEqual([
      "Board",
      "Capacity report"
    ]);

    await expect(menuLabels(page, "file-menu")).resolves.toEqual([
      "Sync Feature Requests",
      "Finished work",
      "Releases",
      "Save Checkpoint",
      "Schedule"
    ]);
  });

  test("an employee opens on the capacity report", async ({ page }) => {
    await signInAsAdmin(page);
    await ensureAccount(page, EMPLOYEE);
    const users = await (await page.request.get("/account/users")).json();
    const user = users.users.find((item) => item.name === EMPLOYEE.email);
    expect(user, "the employee account was not created").toBeTruthy();
    await grantEmployee(page, user.id);

    // The role is in the token from here on. The admin session is replaced.
    await signInAs(page, EMPLOYEE);
    const meResponse = await page.request.get(`/api/${BUNDLE}/me`);
    const meText = await meResponse.text();
    expect(meResponse.ok(), `GET /me answered ${meResponse.status()} — ${meText}`).toBe(true);
    const me = JSON.parse(meText);
    expect(me.role, `GET /me did not read the Employee role — ${meText}`).toBe("Employee");

    await bootBOSS(page);
    await openApplication(page, BUNDLE);

    const report = windowByTitle(page, "Capacity report");
    await expect(report).toBeVisible();
    await expect(windowByTitle(page, "Board")).toHaveCount(0);
    await expect(report.locator("button[name='checkpoint']")).toBeHidden();
    await expect(menuLabels(page, "go-menu")).resolves.toEqual([
      "Board",
      "Capacity report",
      "Schedule"
    ]);

    await clickMenuItem(page, "go-menu", "Board");
    const board = windowByTitle(page, "Board");
    await expect(board).toBeVisible();
    await expect(board.locator("[data-write]").filter({ visible: true })).toHaveCount(0);
    await expect(menuLabels(page, "file-menu")).resolves.toEqual([
      "Finished work",
      "Schedule"
    ]);

    await clickMenuItem(page, "go-menu", "Schedule");
    const schedule = windowByTitle(page, "Schedule");
    await expect(schedule).toBeVisible();
    await expect(schedule.locator("button[name='releases']")).toBeHidden();
  });

  test("a guest is refused", async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(() => {
      try {
        return os.isLoaded() === true;
      }
      catch {
        return false;
      }
    });
    await page.evaluate((id) => os.openApplication(id), BUNDLE);

    await expect(page.locator(".ui-modal .message")).toHaveText(
      "You do not have a license to use Lean Visualizer."
    );
    await expect(page.locator("#app-container-io\\.bithead\\.lean-visualizer"))
      .toHaveCount(0);
  });
});
