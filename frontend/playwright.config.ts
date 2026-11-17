import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests for the whole hiring flow. They need the full site running:
 *   API on http://127.0.0.1:8000 (test database, seeded with backend/scripts/e2e_seed.py)
 *   website on E2E_BASE_URL (default http://127.0.0.1:3000)
 * See docs/TESTING.md. Never point these at the real database: they create accounts.
 */
const executablePath = process.env.E2E_CHROME || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: executablePath ? { executablePath } : undefined,
  },
  projects: [{ name: "chrome", use: { ...devices["Desktop Chrome"] } }],
});
