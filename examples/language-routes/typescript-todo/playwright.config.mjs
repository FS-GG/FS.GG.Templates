import { defineConfig } from "@playwright/test";

const port = Number(process.env.TYPESCRIPT_TODO_PORT ?? 4215);
const node = process.env.TYPESCRIPT_TODO_NODE ?? process.execPath;
export default defineConfig({
  testDir: "tests",
  testMatch: "browser.spec.mjs",
  workers: 1,
  timeout: 30_000,
  reporter: "line",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: "chromium",
    headless: true,
    launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {},
  },
  webServer: { command: `${JSON.stringify(node)} scripts/serve.mjs`, url: `http://127.0.0.1:${port}/`, reuseExistingServer: false },
});
