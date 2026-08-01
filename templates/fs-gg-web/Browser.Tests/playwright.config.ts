import { defineConfig } from "@playwright/test";

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;

export default defineConfig({
  testDir: ".",
  reporter: [["junit", { outputFile: "../artifacts/test-results/browser.junit.xml" }]],
  use: {
    baseURL: "http://127.0.0.1:5000",
    launchOptions: executablePath ? { executablePath } : {}
  },
  webServer: {
    command: "dotnet ../artifacts/publish/WebWorkspace.Server.dll --contentRoot . --urls http://127.0.0.1:5000",
    url: "http://127.0.0.1:5000/api/message",
    reuseExistingServer: false
  }
});
