import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
const studioServer = existsSync("../SvgFoundation/Studio/Studio.fsproj") ? [{
  command: "../../Client/node_modules/.bin/vite --config vite.config.js --host 127.0.0.1 --port 5200",
  cwd: "../SvgFoundation/Studio",
  url: "http://127.0.0.1:5200/",
  reuseExistingServer: false
}] : [];

export default defineConfig({
  testDir: ".",
  reporter: [
    ["junit", { outputFile: "../artifacts/test-results/browser.junit.xml" }],
    ["json", { outputFile: "test-results/browser.json" }]
  ],
  use: {
    baseURL: "http://127.0.0.1:5100",
    launchOptions: executablePath ? { executablePath } : {}
  },
  webServer: [
    {
      command: "dotnet Server.dll --urls http://127.0.0.1:5100",
      cwd: "../artifacts/authority-server",
      url: "http://127.0.0.1:5100/",
      reuseExistingServer: false
    },
    ...studioServer
  ]
});
