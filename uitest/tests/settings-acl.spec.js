// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Granting access from the Settings ACL screen.
 *
 * A user is granted a role, never a permission — so the screen ticks roles and
 * shows what each one holds underneath, read only. What it posts has to match
 * what `/account/assign-acl` takes, and neither side is reachable from the
 * Swift tests: the screen talks to the route, and the route reads the roles
 * the Python service registered when it started.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, bootBOSS, openApplication, openController, windowByTitle,
         account, ensureAccount, settled } from "../lib/boss.js";

const BUNDLE = "io.bithead.scheduler";

/** The ACL window, opened against `who` the way Settings opens it. */
async function openACL(page, user) {
  await openApplication(page, "io.bithead.settings");
  await openController(page, "io.bithead.settings", "ACL", user);
  const win = windowByTitle(page, "ACL");
  await expect(win).toBeVisible();
  return win;
}

/**
 * The row for one role.
 *
 * Matched on the label rather than the row's text: `hasText` is a
 * case-insensitive substring, and a role's own features are listed inside the
 * row — so asking for "Employee" also finds the Operator row, which holds
 * `employee: d, r, w`.
 */
function roleRow(page, win, name) {
  const exact = new RegExp(`^\\s*${name}\\s*$`);
  return win.locator(".acl-role")
    .filter({ has: page.locator("label", { hasText: exact }) });
}

/** Choose an app from the list box, which is what draws the roles. */
async function selectApp(win, bundleId) {
  await win.locator(".ui-list-box-apps .option", { hasText: bundleId })
    .first().click();
  await settled(win);
}

test.describe("settings acl", () => {
  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await bootBOSS(page);
  });

  test("a role is ticked, and what it holds is shown beneath it", async ({ page }) => {
    const who = account("acl-reader");
    await ensureAccount(page, who);
    const users = await (await page.request.get("/account/users")).json();
    const user = users.users.find((u) => u.name === who.email);

    const win = await openACL(page, user);
    await selectApp(win, BUNDLE);

    // The scheduler declares these on its routes; both must be offered.
    await expect(roleRow(page, win, "Operator")).toHaveCount(1);
    await expect(roleRow(page, win, "Employee")).toHaveCount(1);

    const operator = roleRow(page, win, "Operator");

    // it: says what the role holds, one line per feature
    const lines = operator.locator(".acl-role-feature");
    expect(await lines.count()).toBeGreaterThan(0);
    for (const text of await lines.allTextContents()) {
      expect(text, "it: reads `<feature>: <permissions>`").toMatch(/^\S.*: \S/);
    }

    // it: a permission is not something to tick — the role is granted whole
    await expect(operator.locator(".acl-role-feature input")).toHaveCount(0);
    await expect(operator.locator("input[type=checkbox]")).toHaveCount(1);
  });

  test("ticking a role grants it, and unticking takes it back", async ({ page }) => {
    const who = account("acl-grantee");
    await ensureAccount(page, who);
    const users = await (await page.request.get("/account/users")).json();
    const user = users.users.find((u) => u.name === who.email);

    const held = async () => {
      const response = await page.request.post("/account/user-acl", {
        data: { userId: parseInt(user.id), bundleId: BUNDLE }
      });
      return (await response.json()).roles;
    };

    let win = await openACL(page, user);
    await selectApp(win, BUNDLE);
    const operator = roleRow(page, win, "Operator");
    await operator.locator("input[type=checkbox]").check();
    await win.locator("button.default", { hasText: "Save" }).click();
    await expect(win).toBeHidden();

    const granted = await held();
    expect(granted.length, "it: the grant reached BOSS").toBe(1);

    // it: comes back ticked, so what is on screen is what is held
    win = await openACL(page, user);
    await selectApp(win, BUNDLE);
    const again = roleRow(page, win, "Operator");
    await expect(again.locator("input[type=checkbox]")).toBeChecked();

    await again.locator("input[type=checkbox]").uncheck();
    await win.locator("button.default", { hasText: "Save" }).click();
    await expect(win).toBeHidden();

    expect(await held(), "it: unticking takes the role away").toEqual([]);
  });
});
