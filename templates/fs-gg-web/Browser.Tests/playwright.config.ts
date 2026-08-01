import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  reporter: [["junit", { outputFile: "../artifacts/test-results/browser.junit.xml" }]],
  use: { baseURL: "http://127.0.0.1:5000" },
  webServer: {
    command: "dotnet run --project ../Server/WebWorkspace.Server.fsproj --no-build --urls http://127.0.0.1:5000",
    url: "http://127.0.0.1:5000/api/message",
    reuseExistingServer: false
  }
});
