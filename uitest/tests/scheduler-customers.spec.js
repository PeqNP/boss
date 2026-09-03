// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Flow 10 — the people a business books work for.
 *
 * A customer record is made by a booking rather than by an operator typing one
 * in, so these tests start at the kiosk and pick the record up afterwards: the
 * list, the search that finds one among many, the detail with what they have
 * booked, and the notes an operator keeps against them.
 *
 * The bookings are made from a browser with no session. A booking made while
 * signed in attaches that account to the customer, and a customer with an
 * account maintains their own contact details — the form shows them and does
 * not offer to change them.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, ensureAccount,
         account, signInAs, bootBOSS, openApplication, openController,
         windowByTitle, settled, action, docAction, closeAll } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";
import { readyToBook, book } from "../lib/scheduler.js";

const API = "/api/io.bithead.scheduler";

/** Tomorrow, which every booking rule leaves alone. */
function tomorrow() {
  const when = new Date();
  when.setDate(when.getDate() + 1);
  const month = String(when.getMonth() + 1).padStart(2, "0");
  const day = String(when.getDate()).padStart(2, "0");
  return `${when.getFullYear()}-${month}-${day}`;
}

test.describe("scheduler customers", () => {
  let businessId;
  let what;

  test.afterEach(async ({ page }) => {
    await closeAll(page);
  });

  test.beforeEach(async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);
    await signInAsOperator(page);
    const response = await page.request.post(`${API}/signup`, {
      data: { name: "Dana's Salon", timezone: "America/Los_Angeles" }
    });
    expect(response.ok(), `signup failed: ${await response.text()}`).toBe(true);
    businessId = (await response.json()).businessId;

    await signInAsOperator(page);
    what = await readyToBook(page, businessId);

    // Two people, so a search has something to leave out.
    const stranger = await page.context().browser()
      .newContext({ ignoreHTTPSErrors: true });
    const anon = await stranger.newPage();
    await book(anon, businessId, what, tomorrow(), "10:00",
               { "First Name": "Jane", "Last Name": "Doe",
                 "Phone": "555-0101" });
    await book(anon, businessId, what, tomorrow(), "13:00",
               { "First Name": "Marco", "Last Name": "Ruiz",
                 "Phone": "555-0202" });
    await stranger.close();

    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    await expect(page.locator(".ui-window")).toBeVisible();
  });

  /** The business's customers, as the server holds them. */
  async function customers(page) {
    const response = await page.request.get(
      `${API}/business/${businessId}/customers`);
    expect(response.ok(), `could not read the customers: ${await response.text()}`)
      .toBe(true);
    return (await response.json()).customers;
  }

  /** The id of the customer whose last name is `lastName`. */
  async function customerId(page, lastName) {
    const found = (await customers(page)).find((c) => c.lastName === lastName);
    expect(found, `the booking recorded no customer called ${lastName}`)
      .toBeTruthy();
    return found.id;
  }

  /** One customer, with their notes and appointments. */
  async function detail(page, id) {
    const response = await page.request.get(
      `${API}/business/${businessId}/customer/${id}`);
    expect(response.ok(), `could not read the customer: ${await response.text()}`)
      .toBe(true);
    return response.json();
  }

  async function openCustomers(page) {
    await openController(page, "io.bithead.scheduler", "Customers");
    const win = windowByTitle(page, "Customers");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  /** The Customer window, opened on whoever is named in the list. */
  async function openCustomer(page, name) {
    const list = await openCustomers(page);
    await list.locator(".ui-list-box .option", { hasText: name }).click();
    await list.locator("button[name='view-btn']").click();
    const win = windowByTitle(page, "Customer");
    await expect(win).toBeVisible();
    await settled(win);
    return win;
  }

  test("list customers", async ({ page }) => {
    const win = await openCustomers(page);

    const options = win.locator(".ui-list-box .option");
    await expect(options).toHaveCount(2);
    await expect(options.filter({ hasText: "Jane Doe" })).toBeVisible();
    await expect(options.filter({ hasText: "Marco Ruiz" })).toBeVisible();

    // The phone is on the row because two people share a name more often than
    // they share a number, and it is what an operator has in front of them.
    await expect(options.filter({ hasText: "555-0101" })).toBeVisible();
  });

  test("search customers", async ({ page }) => {
    const win = await openCustomers(page);

    await win.locator("input[name='search-query']").fill("Marco");
    await expect(win.locator(".ui-list-box .option")).toHaveCount(1);
    await expect(win.locator(".ui-list-box .option")).toContainText("Marco Ruiz");

    // A phone finds them too. It is the mark an operator reads off a missed
    // call, where a name has to be spelled the way it was typed.
    await win.locator("input[name='search-query']").fill("555-0101");
    await expect(win.locator(".ui-list-box .option")).toHaveCount(1);
    await expect(win.locator(".ui-list-box .option")).toContainText("Jane Doe");

    await win.locator("input[name='search-query']").fill("Nobody");
    await expect(win.locator(".ui-list-box .option")).toHaveCount(0);
    await expect(win.locator("button[name='view-btn']")).toBeDisabled();
  });

  test("show customer appointments", async ({ page }) => {
    const win = await openCustomer(page, "Jane Doe");

    await expect(win.locator("input[name='first-name']")).toHaveValue("Jane");
    await expect(win.locator("input[name='phone']")).toHaveValue("555-0101");

    // The appointment this customer holds, and only theirs. Marco booked the
    // same job type on the same day, so a row count alone would pass with the
    // history unscoped.
    const rows = win.locator("table[name='appointments-table'] tbody tr");
    await expect(rows).toHaveCount(1);
    await expect(rows).toContainText("Haircut");
  });

  test("save customer details", async ({ page }) => {
    const win = await openCustomer(page, "Jane Doe");

    await win.locator("input[name='phone']").fill("555-0999");
    await win.locator("input[name='city']").fill("Portland");
    await docAction(win, "save").click();

    await expect.poll(async () => (await detail(page, await customerId(page, "Doe"))).city,
                      { message: "the save never reached the server" })
      .toBe("Portland");
    expect((await detail(page, await customerId(page, "Doe"))).phone)
      .toBe("555-0999");
  });

  test("reject customer without a name", async ({ page }) => {
    const id = await customerId(page, "Doe");
    const win = await openCustomer(page, "Jane Doe");

    await win.locator("input[name='first-name']").fill("");
    await docAction(win, "save").click();

    await expect(win.locator(".ui-window-message"))
      .toContainText("first and last name");
    expect((await detail(page, id)).firstName).toBe("Jane");
  });

  test("add note", async ({ page }) => {
    const id = await customerId(page, "Doe");
    const win = await openCustomer(page, "Jane Doe");

    await action(win, "addNote").click();
    const modal = windowByTitle(page, "Note");
    await expect(modal).toBeVisible();
    await modal.locator("textarea[name='note']").fill("Allergic to the blue dye.");
    await action(modal, "save").click();

    await expect.poll(async () => (await detail(page, id)).notes.map((n) => n.note),
                      { message: "the note never reached the server" })
      .toEqual(["Allergic to the blue dye."]);
    await expect(win.locator(".ui-list-box .option"))
      .toContainText("Allergic to the blue dye.");
  });

  test("reject empty note", async ({ page }) => {
    const id = await customerId(page, "Doe");
    const win = await openCustomer(page, "Jane Doe");

    await action(win, "addNote").click();
    const modal = windowByTitle(page, "Note");
    await expect(modal).toBeVisible();
    await action(modal, "save").click();

    // The alert is the assertion. The server refuses a blank note too, so an
    // empty note list passes even with the modal's own check deleted.
    await expect(page.locator(".ui-modal", { hasText: "Please write the note" }))
      .toBeVisible();
    expect((await detail(page, id)).notes).toEqual([]);
  });

  test("edit note", async ({ page }) => {
    const id = await customerId(page, "Doe");
    const added = await page.request.post(
      `${API}/business/${businessId}/customer/${id}/notes`,
      { data: { note: "Parks in the alley." } });
    expect(added.ok(), `could not write a note: ${await added.text()}`).toBe(true);

    const win = await openCustomer(page, "Jane Doe");
    await win.locator(".ui-list-box .option", { hasText: "Parks in the alley" })
      .click();
    await action(win, "editNote").click();

    const modal = windowByTitle(page, "Note");
    await expect(modal).toBeVisible();
    await expect(modal.locator("textarea[name='note']"))
      .toHaveValue("Parks in the alley.");
    await modal.locator("textarea[name='note']").fill("Parks out front now.");
    await action(modal, "save").click();

    await expect.poll(async () => (await detail(page, id)).notes.map((n) => n.note),
                      { message: "the edit never reached the server" })
      .toEqual(["Parks out front now."]);
  });

  test("delete note", async ({ page }) => {
    const id = await customerId(page, "Doe");
    const added = await page.request.post(
      `${API}/business/${businessId}/customer/${id}/notes`,
      { data: { note: "Pays cash." } });
    expect(added.ok(), `could not write a note: ${await added.text()}`).toBe(true);

    const win = await openCustomer(page, "Jane Doe");
    await win.locator(".ui-list-box .option", { hasText: "Pays cash" }).click();
    await action(win, "editNote").click();

    const modal = windowByTitle(page, "Note");
    await expect(modal).toBeVisible();
    await modal.locator("button[name='delete-btn']").click();
    await page.locator(".ui-modal", { hasText: "Delete this note?" })
      .locator("button", { hasText: "OK" }).click();

    await expect.poll(async () => (await detail(page, id)).notes.length,
                      { message: "the note was not deleted" })
      .toBe(0);
  });

  test("scope notes to the business in the path", async ({ page }) => {
    const id = await customerId(page, "Doe");
    const added = await page.request.post(
      `${API}/business/${businessId}/customer/${id}/notes`,
      { data: { note: "Pays cash." } });
    expect(added.ok(), `could not write a note: ${await added.text()}`).toBe(true);
    const noteId = (await added.json()).id;

    // Somebody else, running their own business. They name their own business
    // in the path — which is theirs to name — and Dana's customer in it. Every
    // other customer route reads the customer through the business, so a
    // caller who does not hold that customer has nothing to reach.
    const stranger = account("rival");
    await signInAsAdmin(page);
    await ensureAccount(page, stranger);
    await signInAs(page, stranger);
    const other = await page.request.post(`${API}/signup`, {
      data: { name: "Cut Above", timezone: "America/Los_Angeles" }
    });
    expect(other.ok(), `signup failed: ${await other.text()}`).toBe(true);
    const otherId = (await other.json()).businessId;

    // Signed in again, because signing up grants the Operator role and a token
    // carries the roles held when it was minted. Without this the routes below
    // refuse a caller with no role at all, and this test would pass without
    // ever reaching the rule it is about.
    await signInAs(page, stranger);
    const asRival = await page.request.get(`${API}/me`);
    expect((await asRival.json()).businessId,
           "the rival is not running their own business").toBe(otherId);

    const edited = await page.request.put(
      `${API}/business/${otherId}/customer/${id}/note/${noteId}`,
      { data: { note: "Owes us money." } });
    expect(edited.ok(), "another business rewrote this customer's note")
      .toBe(false);

    const removed = await page.request.delete(
      `${API}/business/${otherId}/customer/${id}/note/${noteId}`);
    expect(removed.ok(), "another business deleted this customer's note")
      .toBe(false);

    await signInAsOperator(page);
    expect((await detail(page, id)).notes.map((n) => n.note))
      .toEqual(["Pays cash."]);
  });
});
