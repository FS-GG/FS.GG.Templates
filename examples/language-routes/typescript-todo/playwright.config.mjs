import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const port = Number(process.env.TYPESCRIPT_TODO_PORT ?? 4215);
const node = process.env.TYPESCRIPT_TODO_NODE ?? process.execPath;
const serve = process.env.TYPESCRIPT_TODO_SERVE_SCRIPT ?? new URL("scripts/serve.mjs", import.meta.url).pathname;
const reportRoot = resolve(process.env.TYPESCRIPT_TODO_REPORT_DIR ?? "test-results");
export default defineConfig({
  testDir: "tests",
  testMatch: "browser.spec.mjs",
  outputDir: resolve(reportRoot, "artifacts"),
  workers: 1,
  timeout: 30_000,
  reporter: [["line"], ["json", { outputFile: resolve(reportRoot, "results.json") }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: "chromium",
    headless: true,
    launchOptions: {
      ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}),
      ...(process.env.TYPESCRIPT_TODO_CHROMIUM_NO_SANDBOX === "1" ? { args: ["--no-sandbox"] } : {}),
    },
  },
  webServer: { command: `${JSON.stringify(node)} ${JSON.stringify(serve)}`, url: `http://127.0.0.1:${port}/`, reuseExistingServer: false },
});
