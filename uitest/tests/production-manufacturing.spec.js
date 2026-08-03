// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The manufacturing screen — the one an operator stands in front of all shift.
 *
 * F9 will cover working a unit through to completion. This holds the layout
 * regression that came before it: a full-width pop-up must not push the screen
 * sideways. On a floor terminal a horizontal scrollbar is not an annoyance, it
 * is a step the operator cannot reach.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, signInAsAdmin, openApplication, windowByTitle, overflowing } from "../lib/boss.js";
import { API, resetDatabase, seedStartedJob, seedOperatorOnLine } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";

test.describe("Production — the manufacturing screen", () => {
  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    // An `options` section renders a pop-up sized `100%`, which is where the
    // overflow showed. Holding a unit means the app opens straight onto this
    // screen rather than the job list.
    const { jobId } = await seedStartedJob(page, { withOptions: true });
    await seedOperatorOnLine(page, jobId);

    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
  });

  test("nothing makes the screen scroll sideways @mfg-layout", async ({ page }) => {
    await expect(windowByTitle(page, "Manufacturing Line")).toBeVisible();
    // `.ui-popup-container` is `border-box`, so its 1px borders sit inside the
    // declared width. With `content-box` a control sized `100%` renders 2px
    // wider than its parent and the whole view scrolls.
    expect(await overflowing(page, ".mfg-line")).toEqual([]);
  });
});
