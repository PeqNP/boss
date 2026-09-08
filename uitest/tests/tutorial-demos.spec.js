// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Tutorial demo windows that are not the Example catalog.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, openApplication, openController, windowByTitle, settled, named,
  clickMenuItem
} from "../lib/boss.js";

const TUTORIAL = "io.bithead.tutorial";

test.describe("Tutorial — demos", () => {
  test.beforeEach(async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, TUTORIAL);
    await settled(windowByTitle(page, "UI Components"));
  });

  test("keys reports the last key @keys", async ({ page }) => {
    await openController(page, TUTORIAL, "Keys");
    const win = windowByTitle(page, "Keys");
    await expect(win).toBeVisible();
    await named(win, "div", "key-display").click();
    await page.keyboard.press("A");
    await expect(named(win, "div", "key-display")).toHaveText("A");
  });

  test("settings swaps pages from the list @settings", async ({ page }) => {
    await openController(page, TUTORIAL, "Settings");
    const win = windowByTitle(page, "Settings");
    await expect(win).toBeVisible();
    await win.locator(".settings-nav .option", { hasText: "Schedule" }).click();
    await expect(win.locator("[name='tab-schedule']")).toBeVisible();
    await expect(win.locator("[name='tab-general']")).toBeHidden();
  });

  test("network GET writes a result @network", async ({ page }) => {
    await openController(page, TUTORIAL, "Network");
    const win = windowByTitle(page, "Network");
    await named(win, "button", "get-heartbeat").click();
    await expect(named(win, "p", "network-result"))
      .not.toHaveText("No request yet.");
  });

  test("events receive a ping @events", async ({ page }) => {
    await openController(page, TUTORIAL, "Events");
    const win = windowByTitle(page, "Events");
    await named(win, "button", "send-event").click();
    await expect(named(win, "p", "event-display")).toHaveText("ping");
  });

  test("singleton focuses the same window @singleton", async ({ page }) => {
    await openController(page, TUTORIAL, "Singleton");
    await openController(page, TUTORIAL, "Singleton");
    await expect(windowByTitle(page, "Singleton")).toHaveCount(1);
  });

  test("a pinned window stays in the corner and collapses @pinned", async ({ page }) => {
    await clickMenuItem(page, "demos-menu", "Pinned window");

    const desktop = await page.locator("#desktop").boundingBox();
    const topWin = windowByTitle(page, "Getting started");
    const bottomWin = windowByTitle(page, "Bottom right");

    await expect(topWin).toBeVisible();
    await expect(topWin).toHaveClass(/pin-top-right/);
    await expect(topWin.locator("label.checkbox")).toHaveCount(4);

    await expect(bottomWin).toBeVisible();
    await expect(bottomWin).toHaveClass(/pin-bottom-right/);
    await expect(bottomWin.locator("p")).toHaveText("Pinned window on bottom right.");

    const topBox = await topWin.boundingBox();
    const osBar = await page.locator("#os-bar").boundingBox();
    expect(topBox.y - (osBar.y + osBar.height)).toBeCloseTo(10, 0);
    expect((desktop.x + desktop.width) - (topBox.x + topBox.width)).toBeCloseTo(10, 0);

    const bottomBox = await bottomWin.boundingBox();
    expect((desktop.y + desktop.height) - (bottomBox.y + bottomBox.height)).toBeCloseTo(10, 0);
    expect((desktop.x + desktop.width) - (bottomBox.x + bottomBox.width)).toBeCloseTo(10, 0);

    const before = await topWin.boundingBox();
    await topWin.locator(".collapse-button").click();
    await expect(topWin).toHaveClass(/collapsed/);
    await expect(topWin.locator(":scope > .container")).toBeHidden();
    const collapsed = await topWin.boundingBox();
    expect(collapsed.width).toBeCloseTo(before.width, 0);
    await topWin.locator(".collapse-button").click();
    await expect(topWin.locator(":scope > .container")).toBeVisible();
  });
});
