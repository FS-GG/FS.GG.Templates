import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";

const hasSvgPlayer = existsSync("../SvgFoundation/SvgFoundation.fsproj");
const hasStudio = existsSync("../SvgFoundation/Studio/Studio.fsproj");

type BrowserDiagnostic = { kind: "console" | "pageerror" | "requestfailed"; detail: string };
const expectedConsolePatterns = [
  /^info: \[.+] Information: Normalizing '\/hub\/game' to 'http:\/\/127\.0\.0\.1:5100\/hub\/game'\.$/,
  /^info: \[.+] Information: WebSocket connected to ws:\/\/127\.0\.0\.1:5100\/hub\/game\?id=.+\.$/
];

function observe(page: Page, diagnostics: BrowserDiagnostic[], expected: string[]): void {
  page.on("console", message => {
    const detail = `${message.type()}: ${message.text()}`;
    if (expectedConsolePatterns.some(pattern => pattern.test(detail))) expected.push(detail);
    else diagnostics.push({ kind: "console", detail });
  });
  page.on("pageerror", error => diagnostics.push({ kind: "pageerror", detail: error.message }));
  page.on("requestfailed", request => diagnostics.push({ kind: "requestfailed", detail: `${request.method()} ${request.url()}: ${request.failure()?.errorText ?? "unknown failure"}` }));
}

test("two SVG arena clients observe the same authoritative move", async ({ browser, request }, testInfo: TestInfo) => {
  test.skip(!hasSvgPlayer, "legacy non-SVG composition");
  const diagnostics: BrowserDiagnostic[] = [];
  const expectedConsole: string[] = [];
  const preflight = await request.get("/");
  expect(preflight.status()).toBe(200);
  expect(await preflight.text()).toContain("Cooperative SVG arena");
  const cueResponse = await request.get("/movement-cue.wav");
  expect(cueResponse.status()).toBe(200);
  const cue = await cueResponse.body();
  const cueRate = cue.readUInt32LE(24);
  expect(cueRate).toBe(8000);
  expect((cue.length - 44) / cueRate).toBeGreaterThanOrEqual(0.1);
  expect([...cue.subarray(44)].reduce((energy, sample) => energy + Math.abs(sample - 128), 0)).toBeGreaterThan(1000);
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  try {
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();
    observe(pageA, diagnostics, expectedConsole);
    observe(pageB, diagnostics, expectedConsole);
    await pageA.goto("/");
    await pageB.goto("/");
    await expect(pageA.locator("#foundation-grid-host, #foundation-tactical-compatibility, #svg-authoring-studio")).toHaveCount(0);
    await expect(pageA.getByRole("button", { name: /win|take damage|single step|exercise failed autosave/i })).toHaveCount(0);
    const arenaA = pageA.locator("#foundation-continuous-host");
    const arenaB = pageB.locator("#foundation-continuous-host");
    await expect(arenaA).toHaveAttribute("data-authority-status", "synchronized");
    await expect(arenaB).toHaveAttribute("data-authority-status", "synchronized");
    await expect(arenaA).toHaveAttribute("data-authority-player-count", "2");
    await expect(arenaB).toHaveAttribute("data-authority-player-count", "2");
    const playerA = await arenaA.getAttribute("data-authority-player-id");
    const playerB = await arenaB.getAttribute("data-authority-player-id");
    expect(playerA).toBeTruthy();
    expect(playerB).toBeTruthy();
    expect(playerA).not.toEqual(playerB);
    await pageA.locator("#foundation-audio-unlock").click();
    await expect(arenaA).toHaveAttribute("data-audio-ready-assets", "1");
    await expect(pageA.locator('[data-scene-object-id="player"]')).toBeVisible();
    await expect(pageA.locator(`[data-scene-object-id="peer:${playerB}"]`)).toBeVisible();
    await expect(pageB.locator(`[data-scene-object-id="peer:${playerA}"]`)).toBeVisible();
    const hazardRect = pageA.locator('[data-scene-object-id="hazard"] rect');
    await expect(hazardRect).toHaveAttribute("x", await arenaA.getAttribute("data-authority-hazard-x") ?? "");
    await expect(hazardRect).toHaveAttribute("y", await arenaA.getAttribute("data-authority-hazard-y") ?? "");
    const startCol = Number(await arenaA.getAttribute("data-authority-self-col"));
    const startRow = Number(await arenaA.getAttribute("data-authority-self-row"));
    await arenaA.focus();
    await arenaA.press("s");
    await expect(arenaA).toHaveAttribute("data-audio-effect-dispatched", "true");
    const committed = `${playerA}:${startCol},${startRow + 1}`;
    await expect(arenaA).toHaveAttribute("data-authority-snapshot", new RegExp(committed));
    await expect(arenaB).toHaveAttribute("data-authority-snapshot", new RegExp(committed));
    await expect(arenaA).toHaveAttribute("data-player-x", String(startCol * 11));
    await expect(arenaA).toHaveAttribute("data-player-y", String((startRow + 1) * 10));

    const move = async (key: string, axis: "col" | "row", expected: number): Promise<void> => {
      await arenaA.press(key);
      await expect(arenaA).toHaveAttribute(`data-authority-self-${axis}`, String(expected));
    };
    let col = startCol;
    let row = startRow + 1;
    while (row < 8) await move("s", "row", ++row);
    for (let attempt = 0; attempt < 30 && Number(await arenaA.getAttribute("data-player-health")) === 3; attempt += 1) {
      const hazardCol = Number(await arenaA.getAttribute("data-authority-hazard-col"));
      if (col < hazardCol) await move("d", "col", ++col);
      else if (col > hazardCol) await move("a", "col", --col);
      else await pageA.waitForTimeout(250);
    }
    await expect.poll(async () => Number(await arenaA.getAttribute("data-player-health"))).toBeLessThan(3);
    await expect.poll(async () => Number(await arenaB.getAttribute("data-player-health"))).toBeLessThan(3);
    while (row > 2) await move("w", "row", --row);
    while (col < 5) await move("d", "col", ++col);
    while (col > 5) await move("a", "col", --col);
    await arenaA.press("e");
    await expect(arenaA).toHaveAttribute("data-player-score", "100");
    await expect(arenaB).toHaveAttribute("data-player-score", "100");
    await expect(arenaB).toHaveAttribute("data-player-collected", "true");

    while (row < 5) await move("s", "row", ++row);
    while (col < 16) await move("d", "col", ++col);
    await arenaA.press("e");
    await expect(arenaA).toHaveAttribute("data-player-outcome", "won");
    await expect(arenaB).toHaveAttribute("data-player-outcome", "won");
    await arenaA.press("r");
    await expect(arenaA).toHaveAttribute("data-player-outcome", "playing");
    await expect(arenaB).toHaveAttribute("data-player-outcome", "playing");
    await expect(arenaA).toHaveAttribute("data-player-score", "0");
    await expect(arenaB).toHaveAttribute("data-player-score", "0");
  } finally {
    await testInfo.attach("browser-diagnostics", { body: Buffer.from(JSON.stringify({ diagnostics, expectedConsole }, null, 2)), contentType: "application/json" });
    await contextA.close();
    await contextB.close();
  }
  expect(expectedConsole.filter(message => message.includes("Normalizing"))).toHaveLength(2);
  expect(expectedConsole.filter(message => message.includes("WebSocket connected"))).toHaveLength(2);
  expect(diagnostics).toEqual([]);
});

test("Studio edits and plays the retained arena across all workspace modes", async ({ page, browser }, testInfo) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  await page.goto("http://127.0.0.1:5200/");
  const studio = page.locator("#svg-authoring-studio");
  const scene = page.locator("#generated-authoring-studio--scene");
  await scene.focus();
  await expect(scene).toBeFocused();
  const snapshot = async (): Promise<Record<string, unknown>> =>
    page.evaluate(() => (window as unknown as { svgGeneratedStudio: { snapshot(): Record<string, unknown> } }).svgGeneratedStudio.snapshot());
  const initial = await snapshot();
  expect(initial.sceneId).toBe("continuous-arena");
  expect(initial.documentId).toBe("continuous-arena");
  expect(initial.viewBox).toBe("0,0,220,120");
  expect(initial.selectionCount).toBe(1);
  expect(initial.camera).toBe("4,3");

  await page.locator("#generated-authoring-studio--workspace-mode-0").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "create");
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "arrange");
  await page.getByRole("button", { name: "Move playable hazard far away" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("moved far away");
  const edited = await snapshot();
  expect(edited.contentHash).not.toBe(initial.contentHash);
  expect(edited.documentId).toBe(initial.documentId);
  await page.getByRole("button", { name: "Scale and rotate playable hazard" }).click();
  const transformed = await snapshot();
  expect(transformed.contentHash).not.toBe(edited.contentHash);
  const authoredPixels = await page.getByRole("img").screenshot();
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "play");
  const farPlayed = await snapshot();
  expect(farPlayed.activePlayPreview).toBe(true);
  expect(farPlayed.playSourceHash).toBe(transformed.contentHash);
  expect(farPlayed.playCollision).toBe(false);
  expect(farPlayed.playHealth).toBe(3);
  const previewPixels = await page.getByRole("img").screenshot();
  expect(previewPixels.equals(authoredPixels)).toBe(false);
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();
  expect((await snapshot()).activePlayPreview).toBe(false);
  expect((await snapshot()).selectionCount).toBe(1);
  expect((await snapshot()).camera).toBe("4,3");
  await page.getByRole("button", { name: "Move playable hazard into next step" }).click();
  const contactEdit = await snapshot();
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  const played = await snapshot();
  expect(played.playSourceHash).toBe(contactEdit.contentHash);
  expect(played.playCollision).toBe(true);
  expect(played.playHealth).toBe(2);
  expect(played.contentHash).toBe(contactEdit.contentHash);
  expect(played.playCanonicalState).toContain(`v2|2|continuous-arena/${contactEdit.contentHash}|`);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export playable arena content" }).click();
  const download = await downloadPromise;
  const exportedPath = testInfo.outputPath("arena-content.v2.json");
  await download.saveAs(exportedPath);
  const exported = JSON.parse(await readFile(exportedPath, "utf8"));
  expect(exported.contentId).toBe(contactEdit.contentHash ? `continuous-arena/${contactEdit.contentHash}` : "");
  await page.getByRole("button", { name: "Save scene in browser" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("persisted in browser storage");
  await page.locator("#generated-authoring-studio--workspace-mode-3").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "review");
  await page.getByRole("button", { name: "Validate scene round-trip" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("round-trip validated");
  const retained = await snapshot();
  expect(retained.contentHash).toBe(played.contentHash);
  expect(retained.sceneId).toBe("continuous-arena");
  expect(retained.documentId).toBe(initial.documentId);
  expect(retained.viewBox).toBe(initial.viewBox);
  await page.reload();
  await expect(page.locator("#generated-scene-status")).toContainText("Persisted scene loaded");
  const restored = await snapshot();
  expect(restored.contentHash).toBe(played.contentHash);
  expect(restored.documentId).toBe(initial.documentId);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  expect((await snapshot()).playCollision).toBe(false);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  const restoredHit = await snapshot();
  expect(restoredHit.playCollision).toBe(true);
  expect(restoredHit.playHealth).toBe(2);

  const configuredServer = spawn("dotnet", ["Server.dll"], {
    cwd: "../artifacts/authority-server",
    env: { ...process.env, ASPNETCORE_URLS: "http://127.0.0.1:5300", ArenaContentPath: exportedPath },
    stdio: "ignore"
  });
  const configuredA = await browser.newContext();
  const configuredB = await browser.newContext();
  try {
    await expect.poll(async () => fetch("http://127.0.0.1:5300/").then(response => response.status).catch(() => 0)).toBe(200);
    const pageA = await configuredA.newPage();
    const pageB = await configuredB.newPage();
    await pageA.goto("http://127.0.0.1:5300/");
    await pageB.goto("http://127.0.0.1:5300/");
    const arenaA = pageA.locator("#foundation-continuous-host");
    const arenaB = pageB.locator("#foundation-continuous-host");
    await expect(arenaA).toHaveAttribute("data-authority-content-id", exported.contentId);
    await expect(arenaB).toHaveAttribute("data-authority-content-id", exported.contentId);
    await expect(arenaA).toHaveAttribute("data-authority-player-count", "2");
    await expect(pageA.locator('[data-scene-object-id="collectible"] circle')).toHaveAttribute("cx", String(exported.collectibleX));
    await expect(pageA.locator('[data-scene-object-id="goal"] rect')).toHaveAttribute("x", String(exported.goalX));
    await expect(pageA.locator('[data-scene-object-id="hazard"] rect')).toHaveAttribute("x", await arenaA.getAttribute("data-authority-hazard-x") ?? "");
    await arenaB.focus();
    await arenaB.press("s");
    await expect(arenaB).toHaveAttribute("data-authority-self-row", "1");
    await arenaA.focus();
    let configuredCol = Number(await arenaA.getAttribute("data-authority-self-col"));
    let configuredRow = Number(await arenaA.getAttribute("data-authority-self-row"));
    const configuredHazardRow = Number(await arenaA.getAttribute("data-authority-hazard-row"));
    while (configuredRow < configuredHazardRow) { await arenaA.press("s"); configuredRow += 1; await expect(arenaA).toHaveAttribute("data-authority-self-row", String(configuredRow)); }
    while (configuredRow > configuredHazardRow) { await arenaA.press("w"); configuredRow -= 1; await expect(arenaA).toHaveAttribute("data-authority-self-row", String(configuredRow)); }
    for (let attempt = 0; attempt < 30 && Number(await arenaA.getAttribute("data-player-health")) === 3; attempt += 1) {
      const configuredHazardCol = Number(await arenaA.getAttribute("data-authority-hazard-col"));
      if (configuredCol < configuredHazardCol) { await arenaA.press("d"); configuredCol += 1; await expect(arenaA).toHaveAttribute("data-authority-self-col", String(configuredCol)); }
      else if (configuredCol > configuredHazardCol) { await arenaA.press("a"); configuredCol -= 1; await expect(arenaA).toHaveAttribute("data-authority-self-col", String(configuredCol)); }
      else await pageA.waitForTimeout(250);
    }
    await expect.poll(async () => Number(await arenaA.getAttribute("data-player-health"))).toBeLessThan(3);
    await expect.poll(async () => Number(await arenaB.getAttribute("data-player-health"))).toBeLessThan(3);
  } finally {
    await configuredA.close();
    await configuredB.close();
    configuredServer.kill("SIGTERM");
  }
});

test("legacy non-SVG client retains its V1 authoritative journey", async ({ browser }) => {
  test.skip(hasSvgPlayer, "SVG composition uses the V2 arena journey");
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  try {
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();
    await pageA.goto("/");
    await pageB.goto("/");
    await expect(pageA.locator("#player-id")).not.toBeEmpty();
    await expect(pageB.locator("#player-id")).not.toBeEmpty();
    const playerA = await pageA.locator("#player-id").textContent();
    const playerB = await pageB.locator("#player-id").textContent();
    expect(playerA).toBeTruthy();
    expect(playerB).toBeTruthy();
    expect(playerA).not.toBe(playerB);
    const self = pageA.locator(`[data-occupant="${playerA}"]`);
    await expect(pageB.locator(`[data-occupant="${playerA}"]`)).toBeVisible();
    const [col, row] = (await self.getAttribute("data-cell") as string).split("-").map(Number);
    await self.focus();
    await self.press("ArrowDown");
    const target = pageA.locator(`[data-cell="${col}-${row + 1}"]`);
    await target.press("Enter");
    await expect(pageB.locator(`[data-occupant="${playerA}"]`)).toHaveAttribute("data-cell", `${col}-${row + 1}`);
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
