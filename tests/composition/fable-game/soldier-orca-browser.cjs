// Headed browser host for the soldier-player Orca observer. It mirrors
// orca-playwright-browser.cjs (same DOM-sample contract) but waits for the actual
// generated soldier player and samples soldier state. It never performs the
// journey: every key reaches the page through X11 (xdotool), observed by Orca.
//
// SOLDIER_ORCA_MUTANT selects one causal control. Each removes exactly one
// accessible property so the observer must refuse:
//   unnamed-roster-button  first roster button loses its accessible name
//   no-focus-transfer      programmatic focus() becomes a no-op
//   silent-status          the polite status region is switched off
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
const mutant = process.env.SOLDIER_ORCA_MUTANT || "";
if (mutant && !["unnamed-roster-button", "no-focus-transfer", "silent-status"].includes(mutant)) throw new Error(`unknown mutant: ${mutant}`);

function write(value) {
  const temporary = `${output}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`);
  fs.renameSync(temporary, output);
}

(async () => {
  console.error(`${new Date().toISOString()} browser startup: launch ${browserFamily} mutant=${mutant || "none"}`);
  const context = await browserType.launchPersistentContext(profile, {
    headless: false,
    executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH,
    args: browserFamily === "chromium" ? ["--force-renderer-accessibility", "--no-sandbox"] : [],
    env: { ...process.env, MOZ_ENABLE_WAYLAND: "0" }
  });
  const page = context.pages()[0] ?? await context.newPage();
  await page.addInitScript((selectedMutant) => {
    const describe = element => element ? {
      tag: element.tagName.toLowerCase(), id: element.id || null,
      role: element.getAttribute("role"), ariaLabel: element.getAttribute("aria-label"),
      soldier: element.getAttribute("data-soldier-id"),
      text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 160)
    } : null;
    window.__fsggOrcaDom = { focus: [], keys: [], describe };
    document.addEventListener("focusin", event => {
      window.__fsggOrcaDom.focus.push({ at: performance.now(), target: describe(event.target) });
    }, true);
    document.addEventListener("keydown", event => {
      window.__fsggOrcaDom.keys.push({ at: performance.now(), key: event.key, target: describe(event.target) });
    }, true);
    if (selectedMutant === "no-focus-transfer") HTMLElement.prototype.focus = function () {};
    if (selectedMutant === "unnamed-roster-button" || selectedMutant === "silent-status") {
      const apply = () => {
        if (selectedMutant === "unnamed-roster-button") {
          const first = document.querySelector('#soldier-reference [data-soldier-id="soldier-0000"]');
          if (first && first.textContent !== "") first.textContent = "";
        } else {
          const status = document.querySelector("#soldier-reference output[aria-live]");
          if (status && status.getAttribute("aria-live") !== "off") status.setAttribute("aria-live", "off");
        }
      };
      new MutationObserver(apply).observe(document, { subtree: true, childList: true, characterData: true, attributes: true });
    }
  }, mutant);
  console.error(`${new Date().toISOString()} browser startup: navigate`);
  await page.goto(address);
  console.error(`${new Date().toISOString()} browser startup: wait for actual player authority and mount control`);
  await page.waitForFunction(() => (document.querySelector("[data-authority-status]")?.getAttribute("data-authority-status") ?? "") === "synchronized", null, { timeout: 40000 });
  await page.getByRole("button", { name: "Mount soldier reference" }).waitFor();
  console.error(`${new Date().toISOString()} browser startup: player ready`);
  let stopping = false;
  let sampleSequence = 0;
  const sample = async () => {
    if (stopping) return;
    try {
      const observation = await page.evaluate(() => {
        const root = document.getElementById("soldier-reference");
        const state = JSON.parse(document.getElementById("soldier-reference-state")?.textContent ?? "null");
        return {
          documentHasFocus: document.hasFocus(),
          visibilityState: document.visibilityState,
          activeElement: window.__fsggOrcaDom.describe(document.activeElement),
          focus: window.__fsggOrcaDom.focus,
          keys: window.__fsggOrcaDom.keys,
          soldier: root ? {
            selected: root.getAttribute("data-selected"), focused: root.getAttribute("data-focused"),
            worldCount: root.getAttribute("data-world-count"), lastCommand: root.getAttribute("data-last-command"),
            status: (root.querySelector("output[aria-live]")?.textContent ?? ""),
            firstX: state?.soldiers?.[0]?.x ?? null, firstId: state?.soldiers?.[0]?.id ?? null
          } : null
        };
      });
      sampleSequence += 1;
      write({ schema: "fsgg.orca-browser-dom/v1", browserFamily, address, mutant, sampleSequence,
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
  console.error(`${new Date().toISOString()} browser startup/observation failed: ${String(error?.stack || error)}`);
  write({ schema: "fsgg.orca-browser-dom/v1", browserFamily, address, error: String(error?.stack || error) });
  process.exit(1);
});
