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
         signInAs, account } from "../lib/boss.js";
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
