// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Who reaches what, through the running services.
 *
 * The authorization lives in the route layer: `@require_acl` names the roles,
 * `_working_for` confirms the caller belongs to the business in the path, and
 * the queries carry the business so a record elsewhere is absent. None of that
 * is reachable from the Python tests, which call `lib` directly — and the
 * grants reach BOSS over the network, so they need both services up.
 *
 * These drive the API rather than the screens. The screens are covered
 * elsewhere; what is under test here is the answer a route gives to a caller.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, signInAsOperator, ensureOperator, ensureAccount,
         signInAs, account, bootBOSS, openApplication, windowByTitle,
         action, settled } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

/** A business, opened by whoever is signed in. Signup is the only door. */
async function signUp(page, name) {
  const response = await page.request.post(`${API}/signup`, {
    data: { name, timezone: "America/Los_Angeles" }
  });
  expect(response.ok(), `signup failed: ${await response.text()}`).toBe(true);
  return (await response.json()).businessId;
}

test.describe("scheduler access", () => {
  test("an anonymous caller reaches the kiosk and nothing else", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    // A business to aim at, opened by somebody else.
    const other = account("kiosk-owner");
    await ensureAccount(page, other);
    await signInAs(page, other);
    const businessId = await signUp(page, "Cut Above");

    // A page with no session at all.
    const stranger = await page.context().browser().newContext({ ignoreHTTPSErrors: true });
    const anon = await stranger.newPage();

    const guarded = await anon.request.get(`${API}/business/${businessId}/dashboard`);
    expect(guarded.status(), "it: refuses a caller it cannot identify").toBe(401);

    const employees = await anon.request.get(`${API}/business/${businessId}/employees`);
    expect(employees.status()).toBe(401);

    // it: the kiosk is the surface a customer reaches without an account
    const kiosk = await anon.request.get(`${API}/kiosk/${businessId}`);
    expect(kiosk.ok(), "the kiosk answers a stranger").toBe(true);

    await stranger.close();
  });

  test("an operator reaches their own business and no other", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);

    // A business the operator has nothing to do with.
    const stranger = account("stranger");
    await ensureAccount(page, stranger);
    await signInAs(page, stranger);
    const otherId = await signUp(page, "Somebody Else");

    await signInAsOperator(page);
    const mine = await signUp(page, "Dana's Salon");

    // it: signing up granted the license and the operator role
    const own = await page.request.get(`${API}/business/${mine}/dashboard`);
    expect(own.ok(), `the operator cannot reach their own business: ${await own.text()}`)
      .toBe(true);

    // it: another business is refused, the path naming it being checked
    const other = await page.request.get(`${API}/business/${otherId}/dashboard`);
    expect(other.status(), "it: reaches only the business it belongs to").toBe(403);
  });

  test("a record answers only for the business in the path", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);

    const stranger = account("stranger");
    await ensureAccount(page, stranger);
    await signInAs(page, stranger);
    const otherId = await signUp(page, "Somebody Else");

    await signInAsOperator(page);
    const mine = await signUp(page, "Dana's Salon");

    const added = await page.request.post(`${API}/business/${mine}/employee`, {
      data: { firstName: "Rosa", lastName: "Alvarez" }
    });
    expect(added.ok(), `could not add an employee: ${await added.text()}`).toBe(true);
    const employeeId = (await added.json()).id;

    // it: reads back through the business it belongs to
    const found = await page.request.get(`${API}/business/${mine}/employee/${employeeId}`);
    expect(found.ok()).toBe(true);

    // it: is absent through a business the caller does not belong to, which is
    // refused before the record is even looked for
    const across = await page.request.get(`${API}/business/${otherId}/employee/${employeeId}`);
    expect(across.status()).toBe(403);
  });

  /**
   * Every business-scoped route answers its operator.
   *
   * A route naming `boss_user: User` gets it from its guard. Without one
   * FastAPI reads the parameter as something to parse off the request and
   * answers 422 — to everybody, so the route is not open, it is dead. Two
   * were, and nothing noticed: they are declared, they are unique, and they
   * are never called from a screen yet.
   */
  test("a business-scoped route answers the operator rather than 422", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);
    await signInAsOperator(page);
    const mine = await signUp(page, "Dana's Salon");

    const reached = [
      ["PUT", `${API}/business/${mine}/job/1`],
      ["GET", `${API}/business/${mine}/stripe/products`],
    ];
    for (const [method, url] of reached) {
      const response = await page.request.fetch(url, { method });
      expect(response.status(), `${method} ${url} — the guard supplies boss_user`)
        .not.toBe(422);
    }
  });

  /**
   * The desktop carries admin, operator and employee. A customer's surface is
   * the kiosk, reached the way a website is.
   *
   * Somebody who runs no business used to be called a customer and shown a
   * list of appointments — which is what the admin saw on opening Scheduler,
   * every time. Nobody is a customer on the desktop now: they are offered a
   * business to start.
   */
  test("somebody who runs no business is offered one, not an appointment list",
       async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    const me = await (await page.request.get(`${API}/me`)).json();
    expect(me.role, "it: `customer` is not a thing the desktop knows")
      .not.toBe("customer");

    // it: the route that fed the list is gone with it
    const listed = await page.request.get(`${API}/my/appointments`);
    expect(listed.status()).toBe(404);
  });

  /**
   * An employee and an operator open the same calendar.
   *
   * `EmployeeCalendar` was a second page over the same two routes. It could
   * be, because `schedule/*` narrows by who is asking — so the merged page
   * shows an employee their own jobs without knowing it is doing so, and a
   * page that reads the caller's role would be the wrong shape for this.
   */
  test("an employee opens the schedule the operator opens", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    await ensureOperator(page);

    const worker = account("calendar-employee");
    await ensureAccount(page, worker);
    const users = await (await page.request.get("/account/users")).json();
    const workerId = users.users.find((u) => u.name === worker.email).id;

    await signInAsOperator(page);
    const businessId = await signUp(page, "Dana's Salon");
    // `canManageOwnSchedule` is what puts the calendar button on their
    // dashboard — a separate rule from who the calendar answers, which is what
    // this test is about.
    const added = await page.request.post(`${API}/business/${businessId}/employee`, {
      data: { firstName: "Rosa", lastName: "Alvarez", canManageOwnSchedule: true }
    });
    expect(added.ok(), `could not add an employee: ${await added.text()}`).toBe(true);
    const employeeId = (await added.json()).id;

    const linked = await page.request.put(
      `${API}/business/${businessId}/employee/${employeeId}/account`,
      { data: { userId: parseInt(workerId) } });
    expect(linked.ok(), `could not link the account: ${await linked.text()}`).toBe(true);

    // it: the link granted the license and the employee role
    await signInAs(page, worker);
    const me = await (await page.request.get(`${API}/me`)).json();
    expect(me.role).toBe("employee");
    expect(me.businessId).toBe(businessId);

    // it: and the schedule answers them, narrowed to what they are on
    const day = await page.request.get(
      `${API}/business/${businessId}/schedule/day?date=2026-09-01`);
    expect(day.ok(), `the schedule refused an employee: ${await day.text()}`).toBe(true);

    // it: the dashboard opens the one calendar there is
    await bootBOSS(page);
    await openApplication(page, "io.bithead.scheduler");
    const dashboard = windowByTitle(page, "My Schedule");
    await expect(dashboard).toBeVisible();
    await settled(dashboard);
    await action(dashboard, "manageSchedule").click();
    // Matched on the calendar rather than the title: `ScheduleCalendar`
    // retitles itself to whichever month it opened on, so "Schedule" is gone
    // by the time there is anything to see.
    const calendar = page.locator(".ui-window .cal-month-grid");
    await expect(calendar).toBeVisible();

    // it: the week view came with the merge — `EmployeeCalendar` had none
    const window = page.locator(".ui-window")
      .filter({ has: page.locator(".cal-month-grid") });
    await expect(window.locator("button", { hasText: "Week" })).toBeVisible();
  });

  test("the admin reaches a business they are no member of", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);

    const owner = account("admin-target");
    await ensureAccount(page, owner);
    await signInAs(page, owner);
    const businessId = await signUp(page, "Cut Above");

    // it: helping an operator is the reason the path names the business
    await signInAsAdmin(page);
    const reached = await page.request.get(`${API}/business/${businessId}/dashboard`);
    expect(reached.ok(), `the admin cannot reach it: ${await reached.text()}`).toBe(true);
  });
});
