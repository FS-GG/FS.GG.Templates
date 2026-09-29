import { defineConfig } from '@playwright/test';

const port = Number(process.env.ENROLLMENT_APP_PORT ?? 4197);
export default defineConfig({
  testDir: '.',
  testMatch: ['**/todo/*.spec.mjs', '**/tic-tac-toe/*.spec.mjs', '**/snake/*.spec.mjs', '**/hello-world/*.spec.mjs'],
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  reporter: [['list'], ['junit', { outputFile: '.artifacts/browser-results.xml' }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
    headless: true,
    launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {},
    trace: 'retain-on-failure'
  },
  webServer: {
    command: 'node scripts/serve.mjs',
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: false,
    timeout: 15_000
  }
});
