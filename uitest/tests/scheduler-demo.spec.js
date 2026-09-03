// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Scheduler, driven end to end at a pace somebody can watch.
 *
 * Run headed. This is here to show the app working rather than to catch a
 * regression — it asserts each window opens and moves on, so what it proves is
 * that the path through them still joins up.
 *
 * It was `_live.spec.js`, which `tests/_*.spec.js` gitignores. That rule is
 * for throwaway probes written to diagnose one visual bug and deleted after
 * (see `README.md` § Diagnosing a visual bug). This is neither throwaway nor
 * a probe, so it was being untracked by accident of its name.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, signInAsAdmin, openApplication, windowByTitle, settled, openController } from "../lib/boss.js";

// Paced so it can be watched rather than measured.
const beat = (page) => page.waitForTimeout(1200);

test("drive the scheduler", async ({ page }) => {
  await signInAsAdmin(page);

  // The Setup Assistant belongs to somebody who runs a business, and the
  // specs that reset the database leave the admin running none. Opened here
  // rather than assumed, so the demo does not depend on what ran before it.
  const API = "/api/io.bithead.scheduler";
  const me = await (await page.request.get(`${API}/me`)).json();
  if (me.role !== "operator") {
    await page.request.post(`${API}/signup`, {
      data: { name: "Dana's Salon", timezone: "America/Los_Angeles" }
    });
  }

  await bootBOSS(page);
  await openApplication(page, "io.bithead.scheduler");
  await page.waitForTimeout(2500);

  const win = windowByTitle(page, "Setup Assistant");
  await expect(win).toBeVisible();
  await settled(win);
  await beat(page);

  // Tap a task — the assistant opens the page that task names. Which task is
  // left depends on how far the business got, so this demo does not ask for a
  // particular one.
  await win.locator(".ui-list-box .option").first().click();
  await beat(page);

  // Business Settings, opened directly: it is the screen this is here to
  // show, and whether a task happens to lead to it depends on the setup state.
  await openController(page, "io.bithead.scheduler", "BusinessConfig");
  const cfg = windowByTitle(page, "Business Settings");
  await expect(cfg).toBeVisible();
  await settled(cfg);
  await beat(page);
  await cfg.locator(".settings-nav .option").filter({ hasText: "Payment" }).click();
  await beat(page);

  // The token menu, filtering server-side as it types.
  await openController(page, "io.bithead.scheduler", "Employee", 1);
  const emp = windowByTitle(page, "Employee");
  await expect(emp).toBeVisible();
  await settled(emp);
  await beat(page);
  await emp.locator(".ui-token-menu-input").click();
  await beat(page);
  await emp.locator(".ui-token-menu-input").type("gut", { delay: 250 });
  await page.waitForTimeout(1500);
  await beat(page);
});
