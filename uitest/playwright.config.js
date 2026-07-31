// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import { defineConfig, devices } from "@playwright/test";

/**
 * BOSS runs behind nginx with a self-signed certificate in development, so
 * certificate errors are ignored. Override the host with BOSS_URL when the
 * server is somewhere else:
 *
 *   BOSS_URL=http://localhost:8080 npm test
 */
const BASE_URL = process.env.BOSS_URL || "https://localhost";

export default defineConfig({
  testDir: "./tests",
  // A failing UI test is usually a real failure, not a flake. Retrying hides
  // that. Turn it on only if the suite proves genuinely flaky.
  retries: 0,
  // Serial by default: these tests drive a single running BOSS server, and
  // parallel workers would fight over shared application state.
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    ignoreHTTPSErrors: true,
    // Artifacts only for failures, so a passing run leaves nothing behind.
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
