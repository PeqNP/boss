// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The Tutorial's `Example` controller is where every UI component is
 * demonstrated, so exercising it covers the component library in one pass.
 * When a component is added or changed, add it to `Example.html` /
 * `Example.js` and assert it here.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, openApplication, windowByTitle, named, hasUIInterface } from "../lib/boss.js";

const TUTORIAL = "io.bithead.tutorial";

test.describe("Tutorial — Example", () => {
  test.beforeEach(async ({ page }) => {
    await bootBOSS(page);
    // The Tutorial's `applicationDidStart` opens Example, so no navigation
    // beyond launching the app is needed.
    await openApplication(page, TUTORIAL);
  });

  test("the Example window renders", async ({ page }) => {
    const win = windowByTitle(page, "UI Components");
    await expect(win).toBeVisible();
  });

  test("statically declared components are styled at render", async ({ page }) => {
    // A styled component has a `ui` interface. If the render-time styling pass
    // regresses, these are the first things to break.
    expect(await hasUIInterface(page, "option-1")).toBe(true);
    expect(await hasUIInterface(page, "option-6")).toBe(true);
  });

  test.describe("components created after render", () => {
    test.beforeEach(async ({ page }) => {
      const win = windowByTitle(page, "UI Components");
      await named(win, "button", "make-components").click();
    });

    test("each factory returns a styled component", async ({ page }) => {
      const win = windowByTitle(page, "UI Components");

      // The controller reports its own verdict: it checks that every component
      // it built is reachable with a `ui` interface.
      await expect(named(win, "p", "made-components-result")).not.toContainText("FAILED");

      // And verify independently, because a passing self-report is only as
      // good as the check behind it.
      expect(await hasUIInterface(page, "made-popup")).toBe(true);
      expect(await hasUIInterface(page, "made-list")).toBe(true);

      await expect(named(win, "input", "made-text")).toBeVisible();
      await expect(named(win, "input", "made-number")).toHaveAttribute("type", "number");
      await expect(named(win, "input", "made-check")).toHaveAttribute("type", "checkbox");
    });

    test("a factory-built popup menu renders its options and reports changes", async ({ page }) => {
      const win = windowByTitle(page, "UI Components");
      const menu = win.locator(".ui-popup-menu").filter({ has: named(win, "select", "made-popup") });

      // The visible label is the popup's own markup, not the <select>. If the
      // component were merely inserted rather than styled, it would be absent.
      await expect(menu.locator(".ui-popup-label")).toBeVisible();

      await menu.locator(".ui-popup-label").click();
      await menu.locator(".ui-popup-choices > div", { hasText: "Card 2" }).click();

      // A popup menu reports selection through `select.onchange`, which the
      // controller uses to write its result line.
      await expect(named(win, "p", "made-components-result")).toContainText("Popup menu changed to (2)");
    });

    test("a factory-built list box honors a disabled option", async ({ page }) => {
      const win = windowByTitle(page, "UI Components");
      const listBox = win.locator(".ui-list-box").filter({ has: named(win, "select", "made-list") });

      const disabled = listBox.locator(".option", { hasText: "Unavailable" });
      await expect(disabled).toHaveClass(/disabled/);

      // Auto-selection lands on the first enabled option, so the delegate has
      // already fired for it.
      await expect(named(win, "p", "made-components-result")).toContainText("List box selected (a)");

      // Clicking a disabled option must not select it.
      await disabled.click();
      expect(await page.evaluate(
        () => document.querySelector('select[name="made-list"]').ui.selectedValue()
      )).toBe("a");
    });
  });
});
