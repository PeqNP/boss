// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * F2 — Authoring a production line.
 *
 * The deepest nesting in the app: a line holds operations, an operation holds
 * sections, and each level is a separate window saving back into the one
 * behind it. It also covers the preview, which is the only screen that renders
 * text the server interpolated — the client holds no interpolation code at all.
 */

import { test, expect } from "@playwright/test";
import {
  bootBOSS, signInAsAdmin, openApplication, windowByTitle, leaveHeldLine,
  named, component, action, clickMenuItem, settled, selectPopupOption,
  popupOffset, POPUP_ANCHOR
} from "../lib/boss.js";
import { API, resetDatabase, seedPool } from "../lib/seed.js";

const PRODUCTION = "io.bithead.production";
const POOL = "Test card";
const LINE = "CR-One Reader";

test.describe.configure({ mode: "serial" });

test.describe("Production — authoring a production line", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await signInAsAdmin(page);
    // Otherwise the app resumes that line on launch and opens the wrong screen.
    await leaveHeldLine(page, API);

    await resetDatabase(page);

    // The pool this line will require. Seeded through the API — F1 already
    // covers building one by hand, and doing it again here would only make
    // this flow slower to run and slower to read.
    await seedPool(page, POOL);

    await bootBOSS(page);
    await openApplication(page, PRODUCTION);
    await clickMenuItem(page, "production-menu", "Production Lines");
  });

  test.afterAll(async () => {
    await page.close();
  });

  test("a line is created with columns and a required pool @line", async () => {
    const lines = windowByTitle(page, "Production Lines");
    await expect(lines).toBeVisible();
    await action(lines, "addProductionLine").click();

    const line = windowByTitle(page, "Production Line");
    // Not `toBeVisible`: the form is on screen while it is still creating the
    // draft, and the name it loads would overwrite whatever was typed first.
    await settled(line);
    await named(line, "input", "line-name").fill(LINE);

    for (const column of ["Location", "Group", "Asset"]) {
      await named(line, "input", "new-column").fill(column);
      await action(line, "addColumn").click();
    }
    await expect(component(line, "ui-list-box", "columns").locator(".option"))
      .toHaveCount(3);

    await selectPopupOption(line, "pool-picker", POOL);
    await action(line, "addPool").click();
    await expect(component(line, "ui-list-box", "pools").locator(".option", {
      hasText: POOL
    })).toBeVisible();

    await action(line, "save").click();
    await expect(component(lines, "ui-list-box", "production-lines").locator(".option", {
      hasText: LINE
    })).toBeVisible();
  });

  test("an operation is added to the line @line", async () => {
    const lines = windowByTitle(page, "Production Lines");
    await component(lines, "ui-list-box", "production-lines")
      .locator(".option", { hasText: LINE }).click();
    await action(lines, "editProductionLine").click();

    const line = windowByTitle(page, "Production Line");
    await expect(named(line, "input", "line-name")).toHaveValue(LINE);

    await action(line, "addOperation").click();
    const operation = windowByTitle(page, "Operation");
    await settled(operation);
    await named(operation, "input", "operation-name").fill("Scan reader");
    await action(operation, "save").click();

    await expect(component(line, "ui-list-box", "operations").locator(".option", {
      hasText: "Scan reader"
    })).toBeVisible();
  });

  test("sections are added to the operation @line", async () => {
    const line = windowByTitle(page, "Production Line");
    await component(line, "ui-list-box", "operations")
      .locator(".option", { hasText: "Scan reader" }).click();
    await action(line, "editOperation").click();

    const operation = windowByTitle(page, "Operation");
    await expect(operation).toBeVisible();

    // A description carrying tokens. What they render to is asserted below.
    await action(operation, "addSection").click();
    let section = windowByTitle(page, "Section");
    await selectPopupOption(section, "section-type", "Description");
    await named(section, "textarea", "section-body")
      .fill("Scan {work_unit.Asset} with {pool." + POOL + "}");
    await action(section, "save").click();

    // A required input, which is what an operator fills in.
    await action(operation, "addSection").click();
    section = windowByTitle(page, "Section");
    await selectPopupOption(section, "section-type", "Text input");
    await named(section, "input", "section-name").fill("serial");
    await named(section, "input", "section-label").fill("Serial");
    await named(section, "input", "section-required").check();
    await action(section, "save").click();

    await expect(component(operation, "ui-list-box", "sections").locator(".option"))
      .toHaveCount(2);
  });

  test("a section is edited from the operation that holds it @line", async () => {
    const operation = windowByTitle(page, "Operation");
    const sections = component(operation, "ui-list-box", "sections").locator(".option");

    await sections.filter({ hasText: "text" }).click();
    await action(operation, "editSection").click();

    // Opens on what was saved, not on a blank form — this is an edit, and the
    // section's own controller loads it.
    const section = windowByTitle(page, "Section");
    await settled(section);
    await expect(named(section, "input", "section-label")).toHaveValue("Serial");

    await named(section, "input", "section-label").fill("Serial number");
    await action(section, "save").click();

    // The list behind it re-read the operation rather than keeping the label
    // it was showing.
    await expect(sections.filter({ hasText: "Serial number" })).toHaveCount(1);
    await expect(sections).toHaveCount(2);
  });

  test("a pop-up inside a modal anchors to its control @line", async () => {
    // A modal is centred with `translateX(-50%)`. A `position: fixed` choices
    // layer would take that transform as its containing block and open offset
    // by the modal's own position — so this is asserted wherever a pop-up
    // lives inside one. The scrollable-window case is covered by the Tutorial.
    await action(windowByTitle(page, "Operation"), "addSection").click();
    const section = windowByTitle(page, "Section");
    const menu = '.ui-modal .ui-popup-menu:has(select[name="section-type"])';
    await page.locator(`${menu} .ui-popup-label`).click();
    expect(await popupOffset(page, menu)).toEqual(POPUP_ANCHOR);
    await action(section, "cancel").click();
  });

  test("the preview renders what the server interpolated @line", async () => {
    const operation = windowByTitle(page, "Operation");
    await operation.locator("summary", { hasText: "Preview" }).click();

    const body = named(operation, "div", "preview-body");
    // Placeholders, and no token left unresolved — proof the text came back
    // rendered rather than being interpolated in the browser.
    await expect(body).toContainText("«Asset»");
    await expect(body).toContainText(`«${POOL}»`);
    await expect(body).not.toContainText("{");
  });
});
