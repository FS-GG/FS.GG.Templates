import { defineConfig } from "@playwright/test";

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;

export default defineConfig({
  testDir: ".",
  reporter: [["junit", { outputFile: "../artifacts/test-results/browser.junit.xml" }]],
  use: {
    baseURL: "http://127.0.0.1:5100",
    launchOptions: executablePath ? { executablePath } : {}
  },
  webServer: {
    command: "dotnet Server.dll --urls http://127.0.0.1:5100",
    cwd: "../artifacts/publish",
    url: "http://127.0.0.1:5100/",
    reuseExistingServer: false
  }
});
