import { defineConfig } from "@playwright/test";

// The renderer conformance run (GAME-RENDER-ADOPT-01.10): `npm run test:renderers`, after the client is built
// (`cd Client && npm run build`). It serves Client/dist with `vite preview` and opens renderers.html, which runs the
// FS.GG.Game.Render conformance kit on the game's renderers (Client/Renderers.fs) against the SVG and the two WebGL
// backends. The WebGL backends need a GL context, so Chromium runs with software WebGL (SwiftShader) unless the host provides
// more: PLAYWRIGHT_CHROMIUM_ARGS adds space-separated launch flags (for example a GPU host's ANGLE flags) and
// PLAYWRIGHT_EXECUTABLE_PATH selects the browser, as in playwright.config.ts. Chromium only: it is the browser the
// WebGL surfaces are qualified on, and the other families run the game journeys in playwright.config.ts.
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
const extraArgs = (process.env.PLAYWRIGHT_CHROMIUM_ARGS ?? "").split(/\s+/).filter((flag) => flag.length > 0);

export default defineConfig({
  testDir: ".",
  testMatch: /renderer-conformance\.spec\.ts/,
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
  webServer: {
    command: "../Client/node_modules/.bin/vite preview --host 127.0.0.1 --port 5300 --strictPort",
    cwd: "../Client",
    url: "http://127.0.0.1:5300/renderers.html",
    reuseExistingServer: false
  }
});
