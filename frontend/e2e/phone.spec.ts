import { expect, test, devices } from "@playwright/test";

// Candidates mostly use phones: the public pages must fit a phone screen without sideways scrolling.
test.use({ viewport: devices["Pixel 7"].viewport, userAgent: devices["Pixel 7"].userAgent, isMobile: true, hasTouch: true });

for (const path of ["/login", "/register", "/forgot-password"]) {
  test(`${path} fits a phone screen`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("button").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}
