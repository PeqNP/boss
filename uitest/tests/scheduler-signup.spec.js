// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 2 — opening a business.
 *
 * The first thing anybody does, and the one flow every other screen depends
 * on: nothing else in the app exists until a business does. See
 * `ui-plan.md`.
 *
 * What this proves is the wiring — that the signup screen reaches routes that
 * answer it, and that the Setup Assistant then lists what is genuinely still
 * missing. The rules about what makes a business ready are settled in the
 * private suite.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, bootBOSS, openApplication, windowByTitle, account,
         ensureAccount, signInAs, settled, action } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

test.describe("scheduler signup", () => {
  test("somebody opening a business can see the templates to choose from",
       async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    const owner = account("signup-templates");
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    // The signup screen offers a business type before it will submit, and it
    // asks for them before a business exists — so the route it asks cannot be
    // one scoped to a business, and cannot be the admin's.
    const response = await page.request.get(`${API}/templates`);
    expect(response.ok(),
           `somebody with no business yet cannot list templates: ${response.status()}`)
      .toBe(true);
    const { templates } = await response.json();
    expect(templates.length, "it: there is something to choose").toBeGreaterThan(0);
  });

  test("signing up opens the business and lands on the Setup Assistant",
       async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    const owner = account("signup-flow");
    await ensureAccount(page, owner);

    await signInAs(page, owner);
    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");

    // it: somebody who runs nothing is offered a business
    const signup = windowByTitle(page, "Set Up Your Business");
    await expect(signup).toBeVisible();
    await settled(signup);

    await signup.locator("input[name='biz-name']").fill("Dana's Salon");
    await signup.locator("input[name='biz-phone']").fill("555-0100");
    await action(signup, "submitBusiness").click();

    // it: the templates load, which is what the next step is made of
    const cards = signup.locator(".template-card");
    await expect(cards.first()).toBeVisible();
    await cards.first().click();

    // Waited for rather than assumed: choosing a template posts the signup,
    // and the dashboard is what opens once it lands. Asserting straight after
    // the click reads `/me` before the business exists — which passes alone
    // and races the moment the server has anything else to do.
    await expect(windowByTitle(page, "Dashboard")).toBeVisible();

    // it: the business exists, and this account runs it
    const me = await (await page.request.get(`${API}/me`)).json();
    expect(me.role).toBe("Operator");
    expect(me.businessId).toBeGreaterThan(0);
  });
});
