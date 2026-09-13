import { chromium, firefox, webkit } from "@playwright/test";

const family = process.argv[2];
const address = process.argv[3];
const kind = { chromium, firefox, webkit }[family];
if (!kind || !address) throw new Error("usage: node svg-runtime-player-observe.mjs <chromium|firefox|webkit> <address>");
const external = family === "chromium" ? process.env.PLAYWRIGHT_EXECUTABLE_PATH : family === "firefox" ? process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH : process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH;
const browser = await kind.launch({ headless: true, executablePath: external || undefined });

try {
  const page = await browser.newPage();
  await page.addInitScript(() => {
    window.__svgRuntimePadButtons = [false];
    Object.defineProperty(navigator, "getGamepads", {
      configurable: true,
      value: () => [{ index: 0, buttons: window.__svgRuntimePadButtons.map(pressed => ({ pressed })) }]
    });
  });
  await page.goto(address, { waitUntil: "networkidle" });
  const scope = page.locator("#foundation-continuous-host");
  await scope.waitFor();
  await scope.focus();
  const revision = async () => Number(await scope.getAttribute("data-player-revision"));
  const x = async () => Number(await scope.getAttribute("data-player-x"));
  const y = async () => Number(await scope.getAttribute("data-player-y"));
  const waitCommand = command => page.waitForFunction(expected => document.querySelector("#foundation-continuous-host")?.getAttribute("data-last-game-command") === expected, command, { timeout: 5000 });

  const x0 = await x();
  await page.keyboard.press("d");
  await waitCommand("game.move-right");
  await page.waitForFunction(previous => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-x")) > previous, x0);
  const keyboardX = await x();

  await scope.locator('[data-fsgg-input-action="move-right"]').click();
  await waitCommand("game.move-right");
  const pointerRevision = await revision();

  await scope.locator('[data-fsgg-input-action="move-left"]').evaluate(button => {
    button.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 41, pointerType: "touch" }));
    button.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 41, pointerType: "touch" }));
  });
  await waitCommand("game.move-left");
  const touchRevision = await revision();

  await page.evaluate(() => { window.__svgRuntimePadButtons[0] = true; });
  await page.evaluate(() => window.dispatchEvent(new Event("gamepadconnected")));
  await waitCommand("game.move-up");
  await page.evaluate(() => { window.__svgRuntimePadButtons[0] = false; });
  const gamepadY = await y();

  await scope.locator('[data-fsgg-input-action="pause"]').click();
  await waitCommand("game.pause");
  const pausedRevision = await revision();
  await page.waitForTimeout(80);
  if (await revision() !== pausedRevision) throw new Error("paused authority continued advancing");
  await scope.locator('[data-fsgg-input-action="step"]').click();
  await waitCommand("game.step");
  await page.waitForFunction(previous => Number(document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-revision")) > previous, pausedRevision);
  const steppedRevision = await revision();

  await scope.locator('[data-fsgg-input-action="reset"]').click();
  await waitCommand("game.reset");
  await page.waitForFunction(() => document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-x") === "12");
  const resetHealth = Number(await scope.getAttribute("data-player-health"));

  for (let i = 0; i < 2; i++) await scope.locator('[data-fsgg-input-action="lose"]').click();
  await page.waitForFunction(() => document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-outcome") === "lost");
  await scope.locator('[data-fsgg-input-action="restart"]').click();
  await waitCommand("game.restart");
  await page.waitForFunction(() => document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-outcome") === "playing");
  await scope.locator('[data-fsgg-input-action="win"]').click();
  await page.waitForFunction(() => document.querySelector("#foundation-continuous-host")?.getAttribute("data-player-outcome") === "won");
  const score = Number(await scope.getAttribute("data-player-score"));

  if (!(keyboardX > x0 && touchRevision >= pointerRevision && steppedRevision > pausedRevision && resetHealth === 2 && score === 100)) {
    throw new Error(JSON.stringify({ x0, keyboardX, pointerRevision, touchRevision, gamepadY, pausedRevision, steppedRevision, resetHealth, score }));
  }
  console.log(JSON.stringify({ family, result: "passed", journey: "generated-continuous-player", keyboardX, pointerRevision, touchRevision, gamepadY, pausedRevision, steppedRevision, resetHealth, score }));
} finally {
  await browser.close();
}
