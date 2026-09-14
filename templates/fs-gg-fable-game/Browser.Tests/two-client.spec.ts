import { expect, test, type Page, type TestInfo } from "@playwright/test";

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
  const diagnostics: BrowserDiagnostic[] = [];
  const expectedConsole: string[] = [];
  const preflight = await request.get("/");
  expect(preflight.status()).toBe(200);
  expect(await preflight.text()).toContain("Cooperative SVG arena");
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
    await expect(pageA.locator('[data-scene-object-id="player"]')).toBeVisible();
    await expect(pageA.locator(`[data-scene-object-id="peer:${playerB}"]`)).toBeVisible();
    await expect(pageB.locator(`[data-scene-object-id="peer:${playerA}"]`)).toBeVisible();
    const startCol = Number(await arenaA.getAttribute("data-authority-self-col"));
    const startRow = Number(await arenaA.getAttribute("data-authority-self-row"));
    await arenaA.focus();
    await arenaA.press("s");
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
    await move("s", "row", ++row);
    while (col < 5) await move("d", "col", ++col);
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

test("Studio edits and plays the retained arena across all workspace modes", async ({ page }) => {
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

  await page.locator("#generated-authoring-studio--workspace-mode-0").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "create");
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "arrange");
  await page.getByRole("button", { name: "Move playable hazard" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Playable hazard moved");
  const edited = await snapshot();
  expect(edited.contentHash).not.toBe(initial.contentHash);
  expect(edited.documentId).toBe(initial.documentId);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "play");
  const played = await snapshot();
  expect(played.playSourceHash).toBe(edited.contentHash);
  expect(played.playCollision).toBe(true);
  expect(played.playHealth).toBe(2);
  expect(Number(played.revision)).toBeGreaterThan(Number(edited.revision));
  await page.locator("#generated-authoring-studio--workspace-mode-3").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "review");
  await page.getByRole("button", { name: "Save and reload scene" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("saved and reloaded");
  const retained = await snapshot();
  expect(retained.contentHash).toBe(played.contentHash);
  expect(retained.sceneId).toBe("continuous-arena");
  expect(retained.documentId).toBe(initial.documentId);
  expect(retained.viewBox).toBe(initial.viewBox);
});
