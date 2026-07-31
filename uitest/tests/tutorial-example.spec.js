// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * The Tutorial's `Example` controller is where every UI component is
 * demonstrated, so exercising it covers the component library in one pass.
 * When a component is added or changed, add it to `Example.html` /
 * `Example.js` and assert it here.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, openApplication, windowByTitle, named, component, selectedValue, hasUIInterface, bringToFront } from "../lib/boss.js";

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

/**
 * The choices layer is drawn in the browser's top layer, which keeps it clear
 * of two things that otherwise break it: an ancestor that clips (a scrollable
 * window body), and an ancestor with a `transform` (modals are centred with
 * `translateX(-50%)`), which would silently become the containing block for a
 * `position: fixed` layer and offset it by the modal's own position.
 *
 * Both contexts are asserted because a fix for one has broken the other before.
 */
test.describe("popup menu anchoring", () => {
  const OFFSET = { dx: -1, dy: 1 };   // the component's own 1px inset

  async function offsetOf(page, menuSelector) {
    return page.evaluate((sel) => {
      const menu = document.querySelector(sel);
      const label = menu.querySelector(".ui-popup-label").getBoundingClientRect();
      const sub = menu.querySelector(".sub-container").getBoundingClientRect();
      return { dx: Math.round(sub.x - label.x), dy: Math.round(sub.y - label.bottom) };
    }, menuSelector);
  }

  test("stays anchored inside a scrollable window @popup-anchor", async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, "io.bithead.tutorial");
    const win = windowByTitle(page, "UI Components");
    const menu = '.ui-popup-menu:has(select[name="option-6"])';
    await win.locator(menu + " .ui-popup-label").scrollIntoViewIfNeeded();
    await win.locator(menu + " .ui-popup-label").click();
    expect(await offsetOf(page, menu)).toEqual(OFFSET);
  });

  test("stays anchored inside a modal @popup-anchor", async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, "io.bithead.production");
    await page.evaluate(async () => {
      const app = await os.application("io.bithead.production");
      const win = await app.loadController("Section");
      win.ui.show((ctrl) => ctrl.configure({ operationId: 1, sectionId: null }));
    });
    const menu = '.ui-modal .ui-popup-menu:has(select[name="section-type"])';
    await page.locator(menu + " .ui-popup-label").waitFor({ state: "visible" });
    await page.locator(menu + " .ui-popup-label").click();
    expect(await offsetOf(page, menu)).toEqual(OFFSET);
  });
});

/**
 * The control's width comes from `--popup-width` on the menu, defaulting to the
 * standard 160px. Two things are asserted: the default applies with nothing
 * declared, and the control never makes its parent scroll — `.ui-popup-container`
 * is `border-box`, so its 1px borders sit inside the declared width rather than
 * adding 2px and pushing the view sideways.
 */
test.describe("popup menu width", () => {
  test("uses the standard width when nothing is declared @popup-width", async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, "io.bithead.tutorial");
    const win = windowByTitle(page, "UI Components");
    const menu = win.locator('.ui-popup-menu:has(select[name="option-6"])');
    await menu.scrollIntoViewIfNeeded();
    expect(await menu.evaluate((m) =>
      Math.round(m.querySelector(".ui-popup-container").getBoundingClientRect().width)
    )).toBe(160);
  });

  test("does not make its parent scroll sideways @popup-width", async ({ page }) => {
    await bootBOSS(page);
    await openApplication(page, "io.bithead.production");
    await page.evaluate(async () => {
      const app = await os.application("io.bithead.production");
      const win = await app.loadController("ManufacturingLine");
      win.ui.show((ctrl) => ctrl.configure(1));
    });
    // The Jobs window opens with the app and would otherwise sit on top.
    await bringToFront(page, ".mfg-line");
    // Step 2 holds a full-width popup menu, which is where the overflow showed.
    await page.locator(".mfg-steps .option", { hasText: "Configure" }).click();
    const overflowing = await page.evaluate(() =>
      [...document.querySelectorAll(".mfg-line, .mfg-line *")]
        .filter((el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1)
        .map((el) => `${el.tagName.toLowerCase()}.${el.className}`));
    expect(overflowing).toEqual([]);
  });
});
