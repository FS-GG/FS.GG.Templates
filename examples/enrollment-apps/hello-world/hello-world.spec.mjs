import { expect, test } from "@playwright/test";

const viewports = [
  { name: "desktop", width: 1280, height: 720 },
  { name: "narrow", width: 320, height: 568 },
];

for (const { name, width, height } of viewports) {
  test(`renders the application at the ${name} viewport`, async ({ page }) => {
    const runtimeErrors = [];
    const failedRequests = [];
    const responses = new Map();

    page.on("pageerror", (error) => runtimeErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") runtimeErrors.push(message.text());
    });
    page.on("requestfailed", (request) => {
      failedRequests.push(`${request.url()}: ${request.failure()?.errorText ?? "unknown error"}`);
    });
    page.on("response", (response) => {
      responses.set(new URL(response.url()).pathname, response.status());
    });

    await page.setViewportSize({ width, height });
    await page.goto("/hello-world/");

    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { name: "Hello, world!", exact: true })).toBeVisible();
    await expect(page).toHaveTitle("Hello-world browser example");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");

    await page.reload();
    await expect(main.getByRole("heading", { name: "Hello, world!", exact: true })).toBeVisible();

    expect(responses.get("/hello-world/app.js")).toBe(200);
    expect(responses.get("/hello-world/style.css")).toBe(200);
    expect(failedRequests).toEqual([]);
    expect(runtimeErrors).toEqual([]);
  });
}
