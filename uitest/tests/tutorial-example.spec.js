// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The Tutorial's `Example` controller is where every UI component is
 * demonstrated, so exercising it covers the component library in one pass.
 * When a component is added or changed, add it to `Example.html` /
 * `Example.js` and assert it here.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, openApplication, windowByTitle, named, component, selectedValue, hasUIInterface } from "../lib/boss.js";

const TUTORIAL = "io.bithead.tutorial";

test.describe("Tutorial — Example", () => {
  test.beforeEach(async ({ page }) => {
    await bootBOSS(page);
    // The Tutorial's `applicationDidStart` opens Example, so no navigation
    // beyond launching the app is needed.
    await openApplication(page, TUTORIAL);
  });

  test("the Example window renders @window", async ({ page }) => {
    const win = windowByTitle(page, "UI Components");
    await expect(win).toBeVisible();
  });

  test("statically declared components are styled at render @static", async ({ page }) => {
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

    test("each factory returns a styled component @factory", async ({ page }) => {
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

    test("a factory-built popup menu renders its options and reports changes @popup", async ({ page }) => {
      const win = windowByTitle(page, "UI Components");
      const menu = component(win, "ui-popup-menu", "made-popup");

      // The visible label is the popup's own markup, not the <select>. It
      // shows the first option — the menu's prompt — until a choice is made.
      // An empty prompt collapses the menu to zero height, so asserting the
      // text also asserts the component did not collapse.
      await expect(menu.locator(".ui-popup-label")).toHaveText("Select a test card");

      await menu.locator(".ui-popup-label").click();
      await menu.locator(".ui-popup-choices > div", { hasText: "Card 2" }).click();

      // A popup menu reports selection through `select.onchange`, which the
      // controller uses to write its result line.
      await expect(named(win, "p", "made-components-result")).toContainText("Popup menu changed to (2)");
    });

    test("a factory-built list box honors a disabled option @listbox", async ({ page }) => {
      const win = windowByTitle(page, "UI Components");
      const listBox = component(win, "ui-list-box", "made-list");

      const disabled = listBox.locator(".option", { hasText: "Unavailable" });
      await expect(disabled).toHaveClass(/disabled/);

      // The disabled option is first in the list, so auto-selection had to
      // skip past it to land on something selectable.
      expect(await selectedValue(page, "made-list")).toBe("b");

      // Clicking a disabled option must leave the selection untouched.
      await disabled.click();
      expect(await selectedValue(page, "made-list")).toBe("b");

      // An enabled option still reaches the delegate.
      await listBox.locator(".option", { hasText: "Also available" }).click();
      expect(await selectedValue(page, "made-list")).toBe("c");
      await expect(named(win, "p", "made-components-result")).toContainText("List box selected (c)");
    });
  });
});
