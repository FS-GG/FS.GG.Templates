const fs = require("node:fs");
const path = require("node:path");

const [address, output, profile] = process.argv.slice(2);
if (!address || !output || !profile) throw new Error("address, output and profile are required");
const moduleRoot = process.env.PLAYWRIGHT_MODULE_ROOT;
if (!moduleRoot) throw new Error("PLAYWRIGHT_MODULE_ROOT is required");
const { chromium, firefox } = require(path.join(moduleRoot, "@playwright/test"));
const browserFamily = process.env.SVG_ORCA_BROWSER_FAMILY;
const browserType = browserFamily === "chromium" ? chromium : browserFamily === "firefox" ? firefox : null;
if (!browserType) throw new Error(`unsupported browser family: ${browserFamily}`);

function write(value) {
  const temporary = `${output}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`);
  fs.renameSync(temporary, output);
}

(async () => {
  const context = await browserType.launchPersistentContext(profile, {
    headless: false,
    executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH,
    args: browserFamily === "chromium" ? ["--force-renderer-accessibility", "--no-sandbox"] : [],
    env: { ...process.env, MOZ_ENABLE_WAYLAND: "0" }
  });
  const page = context.pages()[0] ?? await context.newPage();
  await page.addInitScript(() => {
    const describe = element => element ? {
      tag: element.tagName.toLowerCase(), id: element.id || null,
      role: element.getAttribute("role"), ariaLabel: element.getAttribute("aria-label"),
      text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 160)
    } : null;
    window.__fsggOrcaDom = { focus: [], keys: [], describe };
    document.addEventListener("focusin", event => {
      window.__fsggOrcaDom.focus.push({ at: performance.now(), target: describe(event.target) });
    }, true);
    document.addEventListener("keydown", event => {
      window.__fsggOrcaDom.keys.push({ at: performance.now(), key: event.key, target: describe(event.target) });
    }, true);
  });
  await page.goto(address);
  await page.getByRole("heading", { name: "Generated SVG scene studio" }).waitFor();
  let stopping = false;
  let sampleSequence = 0;
  const sample = async () => {
    if (stopping) return;
    try {
      const observation = await page.evaluate(() => ({
        documentHasFocus: document.hasFocus(),
        visibilityState: document.visibilityState,
        activeElement: window.__fsggOrcaDom.describe(document.activeElement),
        focus: window.__fsggOrcaDom.focus,
        keys: window.__fsggOrcaDom.keys
      }));
      sampleSequence += 1;
      write({ schema: "fsgg.orca-browser-dom/v1", browserFamily, address, sampleSequence,
        sampledAt: new Date().toISOString(), sampledAtUnixMs: Date.now(), observation });
    } catch (error) {
      write({ schema: "fsgg.orca-browser-dom/v1", browserFamily, address, error: String(error) });
    }
  };
  await sample();
  const timer = setInterval(sample, 250);
  const stop = async () => {
    if (stopping) return;
    stopping = true;
    clearInterval(timer);
    await context.close();
    process.exit(0);
  };
  process.on("SIGTERM", stop);
  process.on("SIGINT", stop);
  await new Promise(() => {});
})().catch(error => {
  write({ schema: "fsgg.orca-browser-dom/v1", browserFamily, address, error: String(error?.stack || error) });
  process.exit(1);
});
