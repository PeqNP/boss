// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Minting a session for whoever is already signed in.
 *
 * A session carries the apps and roles it was minted with. An app that grants
 * a license or a role to the user who is signed in changes nothing about that
 * user's current session, so every route guarded by the new role refuses them
 * until they sign in again.
 *
 * `POST /account/session` is that sign-in without the password. Scheduler is
 * the app used here because its signup grants both a license and a role in one
 * call; the behaviour under test belongs to BOSS.
 */

import { test, expect } from "@playwright/test";
import { signInAsAdmin, ensureAccount, account, signInAs } from "../lib/boss.js";
import { resetDatabase } from "../lib/seed.js";

const API = "/api/io.bithead.scheduler";

/** The apps and roles the caller's session names. */
async function claims(page) {
  const cookie = (await page.context().cookies())
    .find((c) => c.name === "accessToken");
  expect(cookie, "the caller holds no session").toBeTruthy();
  const payload = JSON.parse(
    Buffer.from(cookie.value.split(".")[1], "base64").toString());
  return { apps: payload.apps || [], roles: payload.roles || [] };
}

test.describe("boss session", () => {
  test("mint a session naming a role granted since sign-in", async ({ page }) => {
    await signInAsAdmin(page);
    await resetDatabase(page);
    // A name nobody has held. `resetDatabase` empties the app's database and
    // never BOSS's, so an account reused between runs already holds the role
    // this test grants, and there is nothing left to prove.
    const owner = account(`minted-${Date.now()}`);
    await ensureAccount(page, owner);
    await signInAs(page, owner);

    expect((await claims(page)).roles, "a new account holds a role").toEqual([]);

    const signup = await page.request.post(`${API}/signup`,
      { data: { name: "Fresh Cuts", timezone: "America/Los_Angeles" } });
    expect(signup.ok(), `signup failed: ${await signup.text()}`).toBe(true);
    const businessId = (await signup.json()).businessId;

    // The grant reached BOSS and the session predates it, so the route the
    // grant was for still refuses them.
    expect((await claims(page)).roles).toEqual([]);
    const before = await page.request.get(`${API}/business/${businessId}/customers`);
    expect(before.status(), "the session already named the new role").toBe(401);

    const minted = await page.request.post("/account/session");
    expect(minted.ok(), `could not mint a session: ${await minted.text()}`)
      .toBe(true);

    const after = await claims(page);
    expect(after.roles.length, "the minted session names no role")
      .toBeGreaterThan(0);
    expect(after.apps.length, "the minted session names no app")
      .toBeGreaterThan(0);

    const reached = await page.request.get(`${API}/business/${businessId}/customers`);
    expect(reached.ok(),
           `the operator still cannot reach their own business: ${await reached.text()}`)
      .toBe(true);
  });

  test("refuse to mint a session for nobody", async ({ page }) => {
    const stranger = await page.context().browser()
      .newContext({ ignoreHTTPSErrors: true });
    const anon = await stranger.newPage();

    const minted = await anon.request.post("/account/session");
    expect(minted.ok(), "a caller with no session was given one").toBe(false);
    await stranger.close();
  });
});
