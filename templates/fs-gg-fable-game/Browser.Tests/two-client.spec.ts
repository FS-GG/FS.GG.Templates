import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";

const hasAnySvgPlayer = existsSync("../SvgFoundation/SvgFoundation.fsproj");
const isLegacySvgPreview = existsSync("../SvgFoundation/LegacyPreview.props");
const hasSvgPlayer = hasAnySvgPlayer && !isLegacySvgPreview;
const hasStudio = existsSync("../SvgFoundation/Studio/Studio.fsproj") && !isLegacySvgPreview;
const hasTacticalExample = existsSync("../SvgFoundation/Examples/Tactical/scene.json") && !isLegacySvgPreview;
const hasArcadeExample = existsSync("../SvgFoundation/Examples/Arcade/scene.json") && !isLegacySvgPreview;

type BrowserDiagnostic = { kind: "console" | "pageerror" | "requestfailed"; detail: string };
type StartupObservation = {
  synchronizedMs: number;
  domContentLoadedMs: number;
  firstPlayInteractionMs: number;
  transferredBytes: number;
  resourceCount: number;
  scriptCount: number;
};

function startupBudgetViolations(value: StartupObservation): string[] {
  return [
    value.synchronizedMs < 5000 ? undefined : "synchronized-ms",
    value.domContentLoadedMs < 5000 ? undefined : "dom-content-loaded-ms",
    value.firstPlayInteractionMs < 5000 ? undefined : "first-play-interaction-ms",
    value.transferredBytes < 2_000_000 ? undefined : "transferred-bytes",
    value.resourceCount < 64 ? undefined : "resource-count",
    value.scriptCount <= 4 ? undefined : "script-count"
  ].filter((item): item is string => item !== undefined);
}
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
  test.setTimeout(45_000);
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
    const otherClientFrames: string[] = [];
    pageB.on("websocket", socket => socket.on("framereceived", event => otherClientFrames.push(String(event.payload))));
    observe(pageA, diagnostics, expectedConsole);
    observe(pageB, diagnostics, expectedConsole);
    const bootstrapResponse = pageA.waitForResponse(response => response.url().endsWith("/api/bootstrap") && response.request().method() === "POST");
    await pageA.goto("/");
    const ownerBootstrap = JSON.parse(await (await bootstrapResponse).text());
    const ownerCapability = ownerBootstrap.sessionCapability as string;
    expect(ownerCapability.length).toBeGreaterThan(16); // Intentionally disclosed once to its owning client.
    await pageB.goto("/");
    await expect(pageA.locator("#foundation-grid-host, #foundation-tactical-compatibility, #svg-authoring-studio")).toHaveCount(0);
    await expect(pageA.getByRole("button", { name: /win|take damage|single step|exercise failed autosave/i })).toHaveCount(0);
    const arenaA = pageA.locator("#foundation-continuous-host");
    const arenaB = pageB.locator("#foundation-continuous-host");
    await expect(arenaA).toHaveAttribute("data-authority-status", "synchronized");
    await expect(arenaB).toHaveAttribute("data-authority-status", "synchronized");
    const startup = await pageA.evaluate(() => {
      const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
      const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
      return {
        synchronizedMs: performance.now(),
        domContentLoadedMs: navigation.domContentLoadedEventEnd,
        transferredBytes: resources.reduce((total, resource) => total + resource.transferSize, 0),
        resourceCount: resources.length,
        scriptCount: resources.filter(resource => resource.initiatorType === "script").length
      };
    });
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
    const startupObservation: StartupObservation = {
      ...startup,
      firstPlayInteractionMs: await pageA.evaluate(() => performance.now())
    };
    expect(startupBudgetViolations(startupObservation)).toEqual([]);
    expect(startupBudgetViolations({
      synchronizedMs: 5000, domContentLoadedMs: 5000, firstPlayInteractionMs: 5000,
      transferredBytes: 2_000_000, resourceCount: 64, scriptCount: 5
    })).toEqual(["synchronized-ms", "dom-content-loaded-ms", "first-play-interaction-ms", "transferred-bytes", "resource-count", "script-count"]);
    await testInfo.attach("chromium-startup-resource-budget", {
      body: Buffer.from(JSON.stringify({
        observation: startupObservation,
        conditions: {
          browser: browser.browserType().name(), browserVersion: browser.version(),
          host: "published ASP.NET authority with production static-player artifact on loopback",
          cache: "new isolated browser contexts; no preflight in either measured page",
          bundle: "selected current SVG player; Studio served separately and excluded from player closure",
          viewportCssPixels: { width: 1280, height: 720 }
        },
        controlledFailure: "all six boundary-valued fields rejected"
      }, null, 2)),
      contentType: "application/json"
    });

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
    // Leave the moving hazard row immediately. The wall covers the row-4
    // crossing at column 10; observe that collision from safe row 5, then use
    // the open collectible column.
    while (row > 5) await move("w", "row", --row);
    while (col < 10) await move("d", "col", ++col);
    while (col > 10) await move("a", "col", --col);
    const beforeBlockedTick = Number(await arenaA.getAttribute("data-authority-tick"));
    await arenaA.press("w");
    await expect.poll(async () => Number(await arenaA.getAttribute("data-authority-tick"))).toBeGreaterThan(beforeBlockedTick);
    await expect(arenaA).toHaveAttribute("data-authority-self-row", "5");
    await expect(arenaB).toHaveAttribute("data-authority-snapshot", new RegExp(`${playerA}:10,5`));
    while (col < 5) await move("d", "col", ++col);
    while (col > 5) await move("a", "col", --col);
    while (row > 2) await move("w", "row", --row);
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
    const burstCol = Number(await arenaA.getAttribute("data-authority-self-col"));
    const burstRow = Number(await arenaA.getAttribute("data-authority-self-row"));
    for (let press = 0; press < 4; press += 1) await arenaA.press("s");
    await expect(arenaA).toHaveAttribute("data-authority-self-row", String(burstRow + 4));
    await expect(arenaB).toHaveAttribute("data-authority-snapshot", new RegExp(`${playerA}:${burstCol},${burstRow + 4}`));
    await pageA.locator("#foundation-export").click();
    await expect(pageA.locator("#foundation-persistence-status")).toContainText("Archive exported");
    await expect(arenaA).toHaveAttribute("data-archive-length", /[1-9][0-9]*/);
    await expect(arenaA).toHaveAttribute("data-archive-capability-excluded", "true");
    await expect(arenaA).toHaveAttribute("data-audio-capability-excluded", "true");
    expect((await pageA.locator("svg").first().evaluate(element => element.outerHTML)).includes(ownerCapability)).toBe(false);
    expect((await pageB.locator("body").innerText()).includes(ownerCapability)).toBe(false);
    expect(otherClientFrames.length).toBeGreaterThan(0);
    expect(otherClientFrames.some(frame => frame.includes(ownerCapability))).toBe(false);
    await testInfo.attach("authority-disclosure-boundary", {
      body: Buffer.from(JSON.stringify({ ownerResponse: "intentionally-disclosed", otherClientFrameCount: otherClientFrames.length, otherClientFramesExcluded: true, svgExcluded: true, audioExcluded: true, archiveExcluded: true }, null, 2)),
      contentType: "application/json"
    });
  } finally {
    await testInfo.attach("browser-diagnostics", { body: Buffer.from(JSON.stringify({ diagnostics, expectedConsole }, null, 2)), contentType: "application/json" });
    await contextA.close();
    await contextB.close();
  }
  expect(expectedConsole.filter(message => message.includes("Normalizing"))).toHaveLength(2);
  expect(expectedConsole.filter(message => message.includes("WebSocket connected"))).toHaveLength(2);
  expect(diagnostics).toEqual([]);
});

test("Studio carries one blank-authored arena through play, reload, export, and two-browser authority", async ({ page, browser }, testInfo) => {
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

  await page.getByRole("button", { name: "Start blank game" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Blank playable game started");
  expect((await snapshot()).entities).toBe(0);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Play refused before effects: gameplay role arena");
  await expect(studio).toHaveAttribute("data-workspace-mode", "create");
  let blankExportDownloaded = false;
  page.once("download", () => { blankExportDownloaded = true; });
  await page.getByRole("button", { name: "Export playable arena content" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("playable export refused before download: gameplay role arena");
  await page.waitForTimeout(250);
  expect(blankExportDownloaded).toBe(false);
  expect((await snapshot()).exportedContentJson).toBe("");
  await page.getByRole("button", { name: "Draw playable vector shapes" }).click();
  await page.getByRole("button", { name: "Assign gameplay roles" }).click();
  expect((await snapshot()).entities).toBe(6);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("requires interaction boundary");
  await page.getByRole("button", { name: "Define interaction and win rules" }).click();
  const beforeRoleRebind = await snapshot();
  await page.getByRole("button", { name: "Rebind hazard and goal gameplay roles" }).click();
  const rebound = await snapshot();
  expect(rebound.contentHash).toBe(beforeRoleRebind.contentHash);
  expect(rebound.gameplayContentId).not.toBe(beforeRoleRebind.gameplayContentId);
  expect(rebound.crossContentRestoreRefused).toBe(true);
  await page.getByRole("button", { name: "Rebind hazard and goal gameplay roles" }).click();
  expect((await snapshot()).gameplayContentId).toBe(beforeRoleRebind.gameplayContentId);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "play");
  expect((await snapshot()).playCanonicalState).toContain("continuous-arena/");
  for (let index = 0; index < 4; index++) await page.getByRole("button", { name: "Move edited player right" }).click();
  for (let index = 0; index < 2; index++) await page.getByRole("button", { name: "Move edited player down" }).click();
  await page.getByRole("button", { name: "Interact with edited arena" }).click();
  expect((await snapshot()).playCollected).toBe(true);
  expect((await snapshot()).playScore).toBe(100);
  for (let index = 0; index < 3; index++) await page.getByRole("button", { name: "Move edited player down" }).click();
  for (let index = 0; index < 11; index++) await page.getByRole("button", { name: "Move edited player right" }).click();
  await page.getByRole("button", { name: "Interact with edited arena" }).click();
  expect((await snapshot()).playOutcome).toBe("won");
  const terminalState = (await snapshot()).playCanonicalState;
  await page.getByRole("button", { name: "Move edited player right" }).click();
  expect((await snapshot()).playCanonicalState).toBe(terminalState);
  await page.getByRole("button", { name: "Restart edited arena" }).click();
  expect((await snapshot()).playOutcome).toBe("playing");
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();

  await page.locator("#generated-authoring-studio--workspace-mode-0").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "create");
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "arrange");
  await page.getByRole("button", { name: "Move playable hazard far away" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("moved far away");
  const edited = await snapshot();
  expect(edited.contentHash).not.toBe(initial.contentHash);
  expect(edited.documentId).toBe("authored-arena");
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
  expect((await snapshot()).selectionCount).toBe(0);
  expect((await snapshot()).camera).toBe("4,3");
  await page.getByRole("button", { name: "Move playable hazard into next step" }).click();
  const contactEdit = await snapshot();
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  const played = await snapshot();
  expect(played.playSourceHash).toBe(contactEdit.contentHash);
  expect(played.playCollision).toBe(true);
  expect(played.playHealth).toBe(2);
  expect(played.contentHash).toBe(contactEdit.contentHash);
  expect(played.playCanonicalState).toContain(`v3|3|${contactEdit.gameplayContentId}|`);
  await page.getByRole("button", { name: "Interact with edited arena" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("interaction accepted");
  await page.getByRole("button", { name: "Restart edited arena" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("restarted at round");
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();
  await page.getByRole("button", { name: "Translate arena boundary" }).click();
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Play refused before effects: gameplay arena boundary");
  await page.getByRole("button", { name: "Undo scene change" }).click();
  await page.getByRole("button", { name: "Move player spawn" }).click();
  const spawnEdit = await snapshot();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export playable arena content" }).click();
  const download = await downloadPromise;
  const exportedPath = testInfo.outputPath("arena-content.v3.json");
  await download.saveAs(exportedPath);
  const exported = JSON.parse(await readFile(exportedPath, "utf8"));
  expect(exported.contentId).toBe(spawnEdit.gameplayContentId);
  expect([exported.schemaVersion, exported.spawnCol, exported.spawnRow]).toEqual([3, 2, 1]);
  await page.getByRole("button", { name: "Save scene in browser" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("persisted in browser storage");
  const lastValidHash = (await snapshot()).contentHash;
  const lastValidRecord = await page.evaluate(async () => await new Promise<Record<string, unknown>>((resolve, reject) => {
    const open = indexedDB.open("FableGameWorkspaceNamespace-svg-studio", 1);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const get = open.result.transaction("records", "readonly").objectStore("records").get("project:continuous-arena");
      get.onerror = () => reject(get.error);
      get.onsuccess = () => resolve(get.result);
    };
  }));
  await page.getByRole("button", { name: "Translate arena boundary" }).click();
  expect((await snapshot()).contentHash).not.toBe(lastValidHash);
  await page.getByRole("button", { name: "Load scene from browser" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Persisted scene loaded");
  expect((await snapshot()).contentHash).toBe(lastValidHash);
  for (const kind of ["malformed", "over-complex", "missing-reference"]) {
    const payload = await page.evaluate(kind => (window as any).svgGeneratedStudio.invalidImportPayload(kind), kind);
    await page.evaluate(async ({ record, payload }) => await new Promise<void>((resolve, reject) => {
      const open = indexedDB.open("FableGameWorkspaceNamespace-svg-studio", 1);
      open.onerror = () => reject(open.error);
      open.onsuccess = () => {
        const put = open.result.transaction("records", "readwrite").objectStore("records").put({ ...record, payload });
        put.onerror = () => reject(put.error);
        put.onsuccess = () => resolve();
      };
    }), { record: lastValidRecord, payload });
    await page.getByRole("button", { name: "Load scene from browser" }).click();
    await expect(page.locator("#generated-scene-status")).toContainText("Validation error: persisted scene refused");
    if (kind === "over-complex") await expect(page.locator("#generated-scene-status")).toContainText("list limit");
    expect((await snapshot()).contentHash).toBe(lastValidHash);
  }
  // Restore the accepted bytes before injecting the storage effect failure. The
  // failing normal Save below must leave these bytes unchanged without a repair write.
  await page.evaluate(async record => await new Promise<void>((resolve, reject) => {
    const open = indexedDB.open("FableGameWorkspaceNamespace-svg-studio", 1);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const put = open.result.transaction("records", "readwrite").objectStore("records").put(record);
      put.onerror = () => reject(put.error);
      put.onsuccess = () => resolve();
    };
  }), lastValidRecord);
  await page.getByRole("button", { name: "Translate arena boundary" }).click();
  const unsavedHash = (await snapshot()).contentHash;
  expect(unsavedHash).not.toBe(lastValidHash);
  await page.evaluate(() => {
    const prototype = IDBObjectStore.prototype as any;
    const original = prototype.put;
    prototype.put = function () { throw new DOMException("injected write failure", "UnknownError"); };
    (window as any).restoreStudioPersistence = () => { prototype.put = original; };
  });
  await page.getByRole("button", { name: "Save scene in browser" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Persistence refused: DatabaseError");
  expect((await snapshot()).contentHash).toBe(unsavedHash);
  await page.evaluate(() => (window as any).restoreStudioPersistence());
  const afterFailedSave = await page.evaluate(async () => await new Promise<Record<string, unknown>>((resolve, reject) => {
    const open = indexedDB.open("FableGameWorkspaceNamespace-svg-studio", 1);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const get = open.result.transaction("records", "readonly").objectStore("records").get("project:continuous-arena");
      get.onerror = () => reject(get.error);
      get.onsuccess = () => resolve(get.result);
    };
  }));
  expect(afterFailedSave).toEqual(lastValidRecord);
  await page.getByRole("button", { name: "Load scene from browser" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Persisted scene loaded");
  expect((await snapshot()).contentHash).toBe(lastValidHash);
  const beforeStorageFailure = (await snapshot()).contentHash;
  await page.evaluate(() => (window as any).svgGeneratedStudio.exerciseStorageFailure());
  await expect(page.locator("#generated-scene-status")).toContainText("Persistence refused: QuotaExceeded");
  expect((await snapshot()).contentHash).toBe(beforeStorageFailure);
  await page.locator("#generated-authoring-studio--workspace-mode-3").click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "review");
  await page.getByRole("button", { name: "Replay complete arena recording" }).click();
  await expect(page.locator("#generated-replay-timeline output")).toContainText("arena events");
  await page.getByRole("button", { name: "Seek arena replay checkpoint" }).click();
  await expect(page.locator("#generated-replay-timeline output")).toContainText("Seeked to");
  await page.getByRole("button", { name: "Cancel arena replay safely" }).click();
  await expect(page.locator("#generated-replay-timeline output")).toContainText("Cancelled before event");
  await page.getByRole("button", { name: "Diagnose arena replay divergence" }).click();
  await expect(page.locator("#generated-replay-inspector output")).toContainText("First divergence at event");
  await page.getByRole("button", { name: "Branch and compare arena scenario" }).click();
  await expect(page.locator("#generated-scenario-planner output")).toContainText("scenario cancelled through Planning.cancel");
  await page.getByRole("button", { name: "Explain arena goal rule" }).click();
  await expect(page.locator("#generated-rule-explorer output")).toContainText("arena.collect then arena.goal");
  const review = await snapshot();
  expect((review.replay as { recordedEvents: number }).recordedEvents).toBeGreaterThanOrEqual(4);
  expect((review.replay as { disclosureSafe: boolean }).disclosureSafe).toBe(true);
  await page.getByRole("button", { name: "Validate scene round-trip" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("round-trip validated");
  const retained = await snapshot();
  expect(retained.contentHash).toBe(spawnEdit.contentHash);
  expect(retained.sceneId).toBe("authored-arena");
  expect(retained.documentId).toBe("authored-arena");
  expect(retained.viewBox).toBe(initial.viewBox);
  await page.reload();
  await expect(page.locator("#generated-scene-status")).toContainText("Persisted scene loaded");
  const restored = await snapshot();
  expect(restored.contentHash).toBe(spawnEdit.contentHash);
  expect(restored.documentId).toBe("authored-arena");
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  expect((await snapshot()).playCanonicalState).toContain("studio-player:3:1");

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
    await expect(arenaA).toHaveAttribute("data-authority-self-col", "2");
    await expect(arenaA).toHaveAttribute("data-authority-self-row", "1");
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

test("Studio starter remains an independent playable regression", async ({ page }) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  await page.goto("http://127.0.0.1:5200/");
  const studio = page.locator("#svg-authoring-studio");
  await page.getByRole("button", { name: "Open starter game" }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Starter playable game opened");
  expect((await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot())).selectionCount).toBe(1);
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "play");
  const snapshot = await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot());
  expect(snapshot.playCanonicalState).toContain("v3|3|continuous-arena/");
  await page.locator("#generated-authoring-studio--workspace-mode-1").click();
  const retained = await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot());
  expect(retained.selectionCount).toBe(1);
  expect(retained.camera).toBe("4,3");
});

test("selected tactical and arcade examples load and execute their engine paths", async ({ page }, testInfo: TestInfo) => {
  test.skip(!hasTacticalExample && !hasArcadeExample, "selected composition has no examples");
  await page.addInitScript(() => {
    (window as any).arcadePad = { connected: true, axes: [0, 0], buttons: [{ pressed: false }] };
    Object.defineProperty(navigator, "getGamepads", {
      configurable: true,
      value: () => (window as any).arcadePad.connected ? [{ index: 0, ...(window as any).arcadePad }] : []
    });
  });
  await page.goto("/");
  if (hasTacticalExample) {
    const tactical = page.locator("#selected-tactical-example");
    await expect(tactical).toHaveAttribute("data-source-id", "tactical-planning");
    await expect(tactical).toHaveAttribute("data-source-sha256", "fd3a16eedd57a312f456a0d9851a5d1d40e7af1aea3f621e66a2c37b25873cca");
    await page.getByRole("button", { name: "Compare tactical scenario" }).click();
    await expect(tactical).toHaveAttribute("data-operation", /compare-refused:/);
    await page.getByRole("button", { name: "Cancel tactical scenario" }).click();
    await expect(tactical).toHaveAttribute("data-operation", /cancel-refused:/);
    await page.getByRole("button", { name: "Commit tactical scenario" }).click();
    await expect(tactical).toHaveAttribute("data-operation", /commit-refused:/);
    await page.getByRole("button", { name: "Plan tactical route" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "planned");
    expect(Number(await tactical.getAttribute("data-route-length"))).toBeGreaterThan(1);
    const accepted = await tactical.getAttribute("data-accepted-digest");
    expect(await tactical.getAttribute("data-predicted-digest")).not.toBe(accepted);
    await page.getByRole("button", { name: "Compare tactical scenario" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "compared");
    await expect(tactical).toHaveAttribute("data-comparison-unchanged", "false");
    await page.getByRole("button", { name: "Cancel tactical scenario" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "cancelled");
    await expect(tactical).toHaveAttribute("data-cancel-preserved-accepted", "true");
    expect(await tactical.getAttribute("data-accepted-digest")).toBe(accepted);
    await page.getByRole("button", { name: "Plan tactical route" }).click();
    const before = await tactical.getAttribute("data-unit-col");
    await page.getByRole("button", { name: "Commit tactical scenario" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "committed");
    expect(await tactical.getAttribute("data-unit-col")).not.toBe(before);
    expect(await tactical.getAttribute("data-committed-digest")).toBe(await tactical.getAttribute("data-accepted-digest"));
    await page.getByRole("button", { name: "Review tactical state" }).click();
    await expect(tactical).toHaveAttribute("data-operation", /review:/);
    await page.getByRole("button", { name: "Explain tactical route rule" }).click();
    await expect(tactical).toHaveAttribute("data-operation", /rule: The route uses the authored grid/);
    await expect(tactical).toHaveAttribute("data-rule-causes", /public\.target:/);
    await expect(tactical).toHaveAttribute("data-rule-applies", "true");
    await expect(tactical).toHaveAttribute("data-rule-model-sha256", "a335ae4e9d4d7c494da06402be962053dec585150af208a365970186c683711e");
    await expect(tactical.locator("output")).toContainText("The route uses the authored grid");
    await page.reload();
    await page.getByRole("button", { name: "Plan tactical route" }).click();
    const beforeSimulation = await tactical.getAttribute("data-unit-col");
    await page.getByRole("button", { name: "Simulate tactical step" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "simulated");
    expect(await tactical.getAttribute("data-unit-col")).not.toBe(beforeSimulation);
    const afterFirstSimulation = await tactical.getAttribute("data-unit-col");
    await page.getByRole("button", { name: "Simulate tactical step" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "simulated");
    expect(await tactical.getAttribute("data-unit-col")).not.toBe(afterFirstSimulation);
    await page.getByRole("button", { name: "Review tactical state" }).click();
    await expect(tactical).toHaveAttribute("data-operation", /review:/);
    await page.getByRole("button", { name: "Plan tactical route" }).click();
    await expect(tactical).toHaveAttribute("data-operation", "planned");
    expect(Number(await tactical.getAttribute("data-route-length"))).toBeGreaterThan(1);
  }
  if (hasArcadeExample) {
    const arcade = page.locator("#selected-arcade-example");
    await expect(arcade).toHaveAttribute("data-outcome", "playing");
    await expect(arcade).toHaveAttribute("data-session-id", "continuous-arcade");
    const frameIntervals = await page.evaluate(async () => await new Promise<number[]>(resolve => {
      const values: number[] = [];
      let previous = performance.now();
      const sample = (now: number) => {
        values.push(now - previous);
        previous = now;
        if (values.length >= 120) resolve(values);
        else requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    }));
    const missedFrameRatio = frameIntervals.filter(milliseconds => milliseconds > 25).length / frameIntervals.length;
    await testInfo.attach("chromium-arcade-frame-observation", {
      body: Buffer.from(JSON.stringify({
        sampleCount: frameIntervals.length,
        windowMilliseconds: frameIntervals.reduce((sum, value) => sum + value, 0),
        missedFrameDefinitionMilliseconds: 25,
        missedFrameRatio,
        maximumIntervalMilliseconds: Math.max(...frameIntervals),
        disposition: "measured candidate observation; no release threshold has been established for this workload"
      }, null, 2)),
      contentType: "application/json"
    });
    const stationaryX = Number(await arcade.getAttribute("data-x"));
    const firstHazard = Number(await arcade.getAttribute("data-hazard-x"));
    await expect.poll(async () => Number(await arcade.getAttribute("data-hazard-x"))).not.toBe(firstHazard);
    expect(Number(await arcade.getAttribute("data-x"))).toBe(stationaryX);

    const before = Number(await arcade.getAttribute("data-x"));
    const pointerRight = page.getByRole("button", { name: "Arcade move right" });
    await pointerRight.dispatchEvent("pointerdown", { pointerId: 7, pointerType: "mouse" });
    await expect.poll(async () => Number(await arcade.getAttribute("data-x"))).toBeGreaterThan(before);
    await pointerRight.dispatchEvent("pointerup", { pointerId: 7, pointerType: "mouse" });

    await arcade.focus();
    await page.keyboard.down("d");
    const keyboardStart = Number(await arcade.getAttribute("data-x"));
    await expect.poll(async () => Number(await arcade.getAttribute("data-x"))).toBeGreaterThan(keyboardStart);
    await page.keyboard.up("d");
    await page.waitForTimeout(40);
    const keyboardStopped = Number(await arcade.getAttribute("data-x"));
    await page.waitForTimeout(80);
    expect(Number(await arcade.getAttribute("data-x"))).toBe(keyboardStopped);

    const touchLeft = page.getByRole("button", { name: "Arcade move left" });
    const beforeTouch = Number(await arcade.getAttribute("data-x"));
    await touchLeft.dispatchEvent("pointerdown", { pointerId: 11, pointerType: "touch" });
    await expect.poll(async () => Number(await arcade.getAttribute("data-x"))).toBeLessThan(beforeTouch);
    await touchLeft.dispatchEvent("pointerup", { pointerId: 11, pointerType: "touch" });

    const gamepadStart = Number(await arcade.getAttribute("data-x"));
    await page.evaluate(() => { (window as any).arcadePad.axes = [1, 0]; });
    await expect.poll(async () => Number(await arcade.getAttribute("data-x"))).toBeGreaterThan(gamepadStart);
    await page.evaluate(() => { (window as any).arcadePad.axes = [0, 0]; });
    await page.waitForTimeout(40);
    const neutral = Number(await arcade.getAttribute("data-x"));
    await page.waitForTimeout(80);
    expect(Number(await arcade.getAttribute("data-x"))).toBe(neutral);
    await page.evaluate(() => {
      (window as any).arcadePad.connected = false;
      window.dispatchEvent(new Event("gamepaddisconnected"));
    });
    await page.waitForTimeout(80);
    expect(Number(await arcade.getAttribute("data-x"))).toBe(neutral);
    await expect(arcade).toHaveAttribute("data-gamepad-source-count", "0");

    await arcade.focus();
    await page.keyboard.down("d");
    const blurStart = Number(await arcade.getAttribute("data-x"));
    await expect.poll(async () => Number(await arcade.getAttribute("data-x"))).toBeGreaterThan(blurStart);
    await page.evaluate(() => window.dispatchEvent(new Event("blur")));
    await page.waitForTimeout(50);
    const blurred = Number(await arcade.getAttribute("data-x"));
    await page.waitForTimeout(80);
    expect(Number(await arcade.getAttribute("data-x"))).toBe(blurred);
    await page.keyboard.up("d");

    await page.getByRole("button", { name: "Enable arcade audio" }).click();
    await arcade.focus();
    await page.keyboard.press("d");
    await expect(arcade).toHaveAttribute("data-audio-effect-dispatched", "true");
    await page.getByRole("button", { name: "Arcade pause" }).click();
    await expect(arcade).toHaveAttribute("data-paused", "true");
    const pausedHazard = Number(await arcade.getAttribute("data-hazard-x"));
    const pausedPlayer = Number(await arcade.getAttribute("data-x"));
    const pausedScore = await arcade.getAttribute("data-score");
    const pausedOutcome = await arcade.getAttribute("data-outcome");
    await page.getByRole("button", { name: "Arcade interact" }).click();
    await expect(arcade).toHaveAttribute("data-paused-command", "interact-refused");
    await expect(arcade).toHaveAttribute("data-score", pausedScore as string);
    await expect(arcade).toHaveAttribute("data-outcome", pausedOutcome as string);
    await pointerRight.dispatchEvent("pointerdown", { pointerId: 17, pointerType: "mouse" });
    await page.waitForTimeout(80);
    expect(Number(await arcade.getAttribute("data-hazard-x"))).toBe(pausedHazard);
    expect(Number(await arcade.getAttribute("data-x"))).toBe(pausedPlayer);
    await pointerRight.dispatchEvent("pointerup", { pointerId: 17, pointerType: "mouse" });
    await page.getByRole("button", { name: "Arcade pause" }).click();
    await expect(arcade).toHaveAttribute("data-paused", "false");
    await expect.poll(async () => Number(await arcade.getAttribute("data-hazard-x"))).not.toBe(pausedHazard);

    await arcade.focus();
    await page.keyboard.down("s");
    await expect.poll(async () => Number(await arcade.getAttribute("data-y")), { timeout: 3000, intervals: [10] }).toBeGreaterThan(75);
    await page.keyboard.up("s");
    await page.keyboard.down("a");
    await expect.poll(async () => Number(await arcade.getAttribute("data-x")), { timeout: 3000 }).toBeLessThan(55);
    await page.keyboard.up("a");
    await page.keyboard.down("d");
    await expect.poll(async () => Number(await arcade.getAttribute("data-health")), { timeout: 4000 }).toBe(1);
    await expect.poll(async () => Number(await arcade.getAttribute("data-x")), { timeout: 3000 }).toBeGreaterThan(165);
    await page.keyboard.up("d");
    await page.waitForTimeout(80);
    await page.keyboard.down("a");
    await expect(arcade).toHaveAttribute("data-outcome", "lost", { timeout: 5000 });
    await page.keyboard.up("a");
    const lostX = await arcade.getAttribute("data-x");
    await page.keyboard.press("a");
    await page.getByRole("button", { name: "Arcade interact" }).click();
    await page.waitForTimeout(80);
    await expect(arcade).toHaveAttribute("data-x", lostX as string);
    await expect(arcade).toHaveAttribute("data-health", "0");
    await expect(arcade).toHaveAttribute("data-outcome", "lost");
    await page.getByRole("button", { name: "Arcade restart" }).click();
    await expect(arcade).toHaveAttribute("data-x", "12");
    await expect(arcade).toHaveAttribute("data-health", "2");
    await expect(arcade).toHaveAttribute("data-outcome", "playing");
  }
});

test("current player and Studio remain operable at 320 CSS pixels with reduced motion", async ({ page }) => {
  test.skip(!hasAnySvgPlayer || isLegacySvgPreview, "selected composition has no current SVG UI");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");
  const player = page.locator("#foundation-continuous-host");
  await expect(player).toHaveAttribute("data-motion-preference", "Reduced");
  await expect(player.locator("svg")).toHaveAttribute("aria-label", "Generated continuous SVG game");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  const playerBounds = await player.locator("svg").boundingBox();
  expect(playerBounds).not.toBeNull();
  expect((playerBounds?.width ?? 1000)).toBeLessThanOrEqual(320);
  await page.locator("#foundation-audio-unlock").focus();
  await expect(page.locator("#foundation-audio-unlock")).toBeFocused();
  await page.keyboard.press("Tab");
  const nextKeyboardTarget = await page.evaluate(() => {
    const active = document.activeElement as HTMLElement;
    return { tag: active.tagName, role: active.getAttribute("role"), name: active.getAttribute("aria-label") ?? active.textContent ?? "" };
  });
  expect(nextKeyboardTarget.tag === "BUTTON" || nextKeyboardTarget.role === "button").toBe(true);
  expect(nextKeyboardTarget.name.trim().length).toBeGreaterThan(0);

  if (hasStudio) {
    await page.goto("http://127.0.0.1:5200/");
    const studio = page.locator("#svg-authoring-studio");
    await expect(studio).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    await page.getByRole("button", { name: "Collapse side docks" }).click();
    const studioState = await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot());
    expect(studioState.collapsedPanelCount).toBeGreaterThan(0);
    await page.getByRole("button", { name: "Start blank game" }).focus();
    await expect(page.getByRole("button", { name: "Start blank game" })).toBeFocused();
  }
});

test("legacy non-SVG client retains its V1 authoritative journey", async ({ browser }) => {
  test.skip(hasAnySvgPlayer, "SVG composition uses its selected player journey");
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
