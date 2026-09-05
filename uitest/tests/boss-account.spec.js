// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Guest account verification.
 *
 * Create Account emails a code and opens Verify Account. The screen's job is
 * to POST `/account/verify-user` and, on success, leave — the info dialog
 * and Sign In are next, not a disabled button on the form that just
 * succeeded. The private suite already covers the code itself.
 */

import { test, expect } from "@playwright/test";
import { bootBOSS, named } from "../lib/boss.js";

/** The Verify Account modal — every account modal is titled Sign In. */
function verifyAccount(page) {
  return page.locator(".ui-modal").filter({
    has: page.locator('button[name="verify-account"]')
  });
}

/** Sign In proper: email and password, not create / verify / recover. */
function signIn(page) {
  return page.locator(".ui-modal").filter({
    has: page.locator('button', { hasText: /^Sign in$/ })
  });
}

test.describe("boss account", () => {
  test("verify account closes and offers sign in @verify", async ({ page }) => {
    await bootBOSS(page);
    await page.evaluate(async () => { await os.ui.showSignIn(); });
    await expect(signIn(page)).toBeVisible();

    await signIn(page).getByText("Verify account").click();
    const verify = verifyAccount(page);
    await expect(verify).toBeVisible();
    await expect(signIn(page)).toHaveCount(0);

    let posted;
    await page.route("**/account/verify-user", async (route) => {
      posted = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        json: {}
      });
    });

    await named(verify, "input", "code").fill("pv1xxo");
    await named(verify, "input", "password").fill("Password1!");
    await named(verify, "input", "retype-password").fill("Password1!");
    await named(verify, "input", "full-name").fill("Pat Verified");
    await named(verify, "button", "verify-account").click();

    await expect(verify, "Verify account stayed open after a successful verify")
      .toHaveCount(0);
    expect(posted, "the form did not POST /account/verify-user").toEqual({
      code: "pv1xxo",
      password: "Password1!",
      fullName: "Pat Verified"
    });

    const info = page.locator(".ui-modal").filter({
      has: page.locator(".info .message")
    });
    await expect(info.locator(".message"))
      .toHaveText(/Your account has been created/);
    await info.locator("button.default").click();

    await expect(signIn(page)).toBeVisible();
    await expect(named(signIn(page), "input", "email")).toBeVisible();
  });
});
