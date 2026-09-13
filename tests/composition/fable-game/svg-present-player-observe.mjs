import { chromium, firefox, webkit } from "@playwright/test";

const family = process.argv[2];
const address = process.argv[3];
const kind = { chromium, firefox, webkit }[family];
if (!kind || !address) throw new Error("usage: node svg-present-player-observe.mjs <chromium|firefox|webkit> <address>");
const external = family === "chromium" ? process.env.PLAYWRIGHT_EXECUTABLE_PATH : family === "firefox" ? process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH : process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH;
const browser = await kind.launch({ headless: true, executablePath: external || undefined });

const attr = async (scope, name) => scope.getAttribute(name);
const numberAttr = async (scope, name) => Number(await attr(scope, name));
const waitAttr = (page, name, predicate) => page.waitForFunction(({ name, predicate }) => {
  const value = document.querySelector("#foundation-continuous-host")?.getAttribute(name);
  return predicate === "present" ? value !== null : predicate.startsWith("prefix:") ? value?.startsWith(predicate.slice(7)) : value === predicate;
}, { name, predicate }, { timeout: 7000 });

try {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(address, { waitUntil: "networkidle" });
  const scope = page.locator("#foundation-continuous-host");
  await scope.waitFor();
  await waitAttr(page, "data-persistence-ready", "true");

  await page.locator("#foundation-audio-unlock").click();
  await page.waitForFunction(() => ["Unlocked", "Running"].includes(document.querySelector("#foundation-continuous-host")?.getAttribute("data-audio-status")), undefined, { timeout: 7000 });
  await page.waitForFunction(() => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-audio-ready-assets")) === 1, undefined, { timeout: 7000 });

  const x0 = await numberAttr(scope, "data-player-x");
  await scope.locator('[data-fsgg-input-action="move-right"]').click();
  await page.waitForFunction(previous => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-x")) > previous, x0);
  await waitAttr(page, "data-live-cue-count", "1");
  await page.waitForFunction(() => document.querySelector("#foundation-continuous-host")?.getAttribute("data-audio-event")?.includes("EffectDispatched"), undefined, { timeout: 7000 });
  const firstCueCount = await numberAttr(scope, "data-live-cue-count");
  await waitAttr(page, "data-autosave-status", "Clean");
  const firstSavedX = await numberAttr(scope, "data-player-x");
  await scope.focus();
  await page.keyboard.press("p");
  await waitAttr(page, "data-last-game-command", "game.pause");

  await scope.focus();
  await page.keyboard.press("d");
  await waitAttr(page, "data-last-game-command", "game.move-right");
  const seekObservation = await page.locator("#foundation-animation-seek").evaluate(button => {
    const scope = document.querySelector("#foundation-continuous-host");
    const before = Number(scope?.getAttribute("data-live-cue-count") || "0");
    button.click();
    return { before, after: Number(scope?.getAttribute("data-live-cue-count") || "0") };
  });
  const cueCountBeforeSeek = seekObservation.before;
  if (seekObservation.after !== cueCountBeforeSeek) throw new Error(`seek synchronously replayed a cue: ${cueCountBeforeSeek} -> ${seekObservation.after}`);
  await page.waitForTimeout(280);
  const cueCountAfterSeek = await numberAttr(scope, "data-live-cue-count");
  if (cueCountAfterSeek !== cueCountBeforeSeek) throw new Error(`seek replayed a cue: ${cueCountBeforeSeek} -> ${cueCountAfterSeek}`);
  await waitAttr(page, "data-autosave-status", "Clean");
  const preFailureX = await numberAttr(scope, "data-player-x");

  await page.locator("#foundation-fail-save").click();
  await waitAttr(page, "data-autosave-status", "prefix:Failed");
  await page.locator("#foundation-load").click();
  await page.waitForFunction(() => document.querySelector("#foundation-persistence-status")?.textContent === "Game loaded");
  await page.waitForFunction(expected => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-x")) === expected, preFailureX);

  await scope.focus();
  await page.keyboard.press("a");
  await waitAttr(page, "data-last-game-command", "game.move-left");
  await waitAttr(page, "data-autosave-status", "Clean");
  const recoveredX = await numberAttr(scope, "data-player-x");
  const recoveredScore = await numberAttr(scope, "data-player-score");
  await page.locator("#foundation-export").click();
  await page.waitForFunction(() => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-archive-length")) > 0);
  const archiveLength = await numberAttr(scope, "data-archive-length");
  await scope.locator('[data-fsgg-input-action="win"]').evaluate(button => {
    button.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 77, pointerType: "mouse" }));
    button.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 77, pointerType: "mouse" }));
  });
  await waitAttr(page, "data-last-game-command", "game.win");
  await page.waitForFunction(previous => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-score")) > previous, recoveredScore);
  await waitAttr(page, "data-autosave-status", "Clean");
  await page.locator("#foundation-import").click();
  await page.waitForFunction(() => document.querySelector("#foundation-persistence-status")?.textContent === "Game loaded");
  await page.waitForFunction(expected => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-score")) === expected, recoveredScore);

  await page.reload({ waitUntil: "networkidle" });
  const reloaded = page.locator("#foundation-continuous-host");
  await reloaded.waitFor();
  await waitAttr(page, "data-persistence-ready", "true");
  await page.locator("#foundation-load").click();
  await page.waitForFunction(() => document.querySelector("#foundation-persistence-status")?.textContent === "Game loaded");
  await page.waitForFunction(expected => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-score")) === expected, recoveredScore);

  const reducedContext = await browser.newContext({ reducedMotion: "reduce" });
  const reducedPage = await reducedContext.newPage();
  await reducedPage.goto(address, { waitUntil: "networkidle" });
  const reducedScope = reducedPage.locator("#foundation-continuous-host");
  await reducedScope.focus();
  await reducedPage.keyboard.press("d");
  await reducedPage.waitForFunction(() => document.querySelector("#foundation-continuous-host")?.getAttribute("data-last-game-command") === "game.move-right");
  await reducedPage.waitForFunction(() => {
    const player = document.querySelector("#foundation-continuous-host [data-scene-object-id='player']");
    return player?.getAttribute("transform")?.includes("translate(0 0)") && player?.getAttribute("opacity") === "1";
  });
  const reducedCueCount = Number((await reducedScope.getAttribute("data-live-cue-count")) || "0");
  if (reducedCueCount !== 0) throw new Error(`reduced motion emitted a decorative cue: ${reducedCueCount}`);
  await reducedContext.close();

  console.log(JSON.stringify({ family, result: "passed", journey: "generated-presentation-player", audio: "gesture-unlocked-and-cued", firstSavedX, preFailureX, recoveredX, recoveredScore, firstCueCount, cueCountBeforeSeek, cueCountAfterSeek, archiveLength, reload: "restored", reducedMotion: "settled-without-cue" }));
  await context.close();
} finally {
  await browser.close();
}
