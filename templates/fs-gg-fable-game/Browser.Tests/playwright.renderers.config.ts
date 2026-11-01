import { defineConfig } from "@playwright/test";

// The renderer runs (GAME-RENDER-ADOPT-01.10 and #840): `npm run test:renderers`, after the client is built
// (`cd Client && npm run build`) and the authority server is published (build.sh does both). It serves Client/dist with
// `vite preview` in front of that server and runs two specs: renderer-conformance.spec.ts opens renderers.html, which runs
// the FS.GG.Game.Render conformance kit (interaction included) on the game's renderers (Client/Renderers.fs) against all three
// backends, and renderer-journey.spec.ts plays the real game page on each of them. The WebGL backends need a GL
// context, so Chromium runs with software WebGL (SwiftShader) unless the host provides more: PLAYWRIGHT_CHROMIUM_ARGS adds
// space-separated launch flags (for example a GPU host's ANGLE flags) and PLAYWRIGHT_EXECUTABLE_PATH selects the browser,
// as in playwright.config.ts. Chromium only: it is the browser the WebGL surfaces are qualified on, and the other families
// run the game journeys in playwright.config.ts.
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
const extraArgs = (process.env.PLAYWRIGHT_CHROMIUM_ARGS ?? "").split(/\s+/).filter((flag) => flag.length > 0);

export default defineConfig({
  testDir: ".",
  testMatch: /renderer-(conformance|journey)\.spec\.ts/,
  // Playwright empties its output directory when a run starts. The game journeys' report (test-results/browser.json)
  // is kept by this run only because this one writes elsewhere.
  outputDir: "../artifacts/renderer-test-output",
  projects: [{
    name: "chromium",
    use: {
      browserName: "chromium",
      launchOptions: {
        ...(executablePath ? { executablePath } : {}),
        args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", ...extraArgs]
      }
    }
  }],
  reporter: [
    ["junit", { outputFile: "../artifacts/test-results/browser.renderers.chromium.junit.xml" }],
    ["json", { outputFile: "../artifacts/test-results/browser.renderers.json" }]
  ],
  use: {
    baseURL: "http://127.0.0.1:5300"
  },
  // The built client is served by `vite preview`, which forwards /api and the SignalR hub to the authority server
  // started beside it (the same published server the game journeys use, on its own port).
  webServer: [
    {
      command: "dotnet Server.dll --urls http://127.0.0.1:5101",
      cwd: "../artifacts/authority-server",
      url: "http://127.0.0.1:5101/",
      reuseExistingServer: false
    },
    {
      command: "../Client/node_modules/.bin/vite preview --host 127.0.0.1 --port 5300 --strictPort",
      cwd: "../Client",
      url: "http://127.0.0.1:5300/renderers.html",
      env: { FSGG_AUTHORITY: "http://127.0.0.1:5101" },
      reuseExistingServer: false
    }
  ]
});
