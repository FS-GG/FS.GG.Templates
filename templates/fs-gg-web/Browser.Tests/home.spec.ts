import { expect, test } from "@playwright/test";
test("serves the built client and its JSON message", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#message")).toContainText("Hello from");
});
