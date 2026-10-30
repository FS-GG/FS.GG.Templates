import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";

const hasAnySvgPlayer = existsSync("../SvgFoundation/SvgFoundation.fsproj");
const isLegacySvgPreview = existsSync("../SvgFoundation/LegacyPreview.props");
const hasSvgPlayer = hasAnySvgPlayer && !isLegacySvgPreview;
const hasStudio = existsSync("../SvgFoundation/Studio/Studio.fsproj") && !isLegacySvgPreview;
const hasTacticalExample = existsSync("../SvgFoundation/Examples/Tactical/scene.json") && !isLegacySvgPreview;
const hasArcadeExample = existsSync("../SvgFoundation/Examples/Arcade/scene.json") && !isLegacySvgPreview;
const hasExternalAuthorityReference = existsSync("../SvgFoundation/Examples/ExternalAuthority/reference.json")
  && !isLegacySvgPreview
  && (process.env.FsGgExternalReferenceCandidate === "true"
    || readFileSync("../SvgFoundation/SvgFoundation.fsproj", "utf8").includes(">true</FsGgExternalReferenceCandidate>"));
const hasDurableLocalSave = existsSync("../SvgFoundation/Examples/FourD/LocalSaveReplayCodec.fs");
const hasFourDReference = existsSync("../SvgFoundation/Examples/FourD/reference.json") && !isLegacySvgPreview;

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
    await contextA.addInitScript(() => {
      const nativeWebSocket = window.WebSocket;
      const sockets: WebSocket[] = [];
      (window as unknown as { __fsggAuthoritySockets: WebSocket[] }).__fsggAuthoritySockets = sockets;
      window.WebSocket = new Proxy(nativeWebSocket, {
        construct(target, argumentsList) {
          const socket = Reflect.construct(target, argumentsList) as WebSocket;
          sockets.push(socket);
          return socket;
        }
      });
    });
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
    await expect.poll(() => pageA.evaluate(() => {
      const host = document.querySelector("#foundation-continuous-host");
      const hazard = document.querySelector('[data-scene-object-id="hazard"] rect');
      return host !== null && hazard !== null
        && hazard.getAttribute("x") === host.getAttribute("data-authority-hazard-x")
        && hazard.getAttribute("y") === host.getAttribute("data-authority-hazard-y");
    })).toBe(true);
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
    await arenaA.press("a");
    await expect.poll(async () => Number(await arenaA.getAttribute("data-authority-tick"))).toBeGreaterThan(beforeBlockedTick);
    await expect(arenaA).toHaveAttribute("data-authority-self-row", "5");
    await expect(arenaA).toHaveAttribute("data-authority-self-col", "9");
    await expect(arenaB).toHaveAttribute("data-authority-snapshot", new RegExp(`${playerA}:9,5`));
    col = 9;
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
    let burstRow = Number(await arenaA.getAttribute("data-authority-self-row"));
    while (burstRow > 0) await move("w", "row", --burstRow);
    await arenaA.press("w");
    await arenaA.press("s");
    await expect(arenaA).toHaveAttribute("data-authority-self-row", String(burstRow + 1));
    for (let press = 0; press < 4; press += 1) await arenaA.press("s");
    const afterBurstRow = burstRow + 5;
    await expect(arenaA).toHaveAttribute("data-authority-self-row", String(afterBurstRow));
    await expect(arenaB).toHaveAttribute("data-authority-snapshot", new RegExp(`${playerA}:${burstCol},${afterBurstRow}`));

    const diagnosticsBeforeReconnect = diagnostics.length;
    const expectedBeforeReconnect = expectedConsole.length;
    await arenaA.evaluate(element => {
      element.focus();
      const sockets = (window as unknown as { __fsggAuthoritySockets: WebSocket[] }).__fsggAuthoritySockets;
      const socket = sockets.at(-1);
      if (!socket) throw new Error("authority socket unavailable for controlled reconnect");
      const send = socket.send.bind(socket);
      let closedAtFirstSend = false;
      socket.send = data => {
        send(data);
        if (!closedAtFirstSend) {
          closedAtFirstSend = true;
          socket.close(4000, "controlled reconnect after first queued send");
        }
      };
      for (let press = 0; press < 4; press += 1) {
        element.dispatchEvent(new KeyboardEvent("keydown", { key: "s", code: "KeyS", bubbles: true }));
        element.dispatchEvent(new KeyboardEvent("keyup", { key: "s", code: "KeyS", bubbles: true }));
      }
    });
    await expect.poll(() => pageA.evaluate(() =>
      (window as unknown as { __fsggAuthoritySockets: WebSocket[] }).__fsggAuthoritySockets.length)).toBeGreaterThan(1);
    await expect(arenaA).toHaveAttribute("data-authority-status", "synchronized", { timeout: 15_000 });
    const reconnectedTick = Number(await arenaA.getAttribute("data-authority-tick"));
    await expect.poll(async () => Number(await arenaA.getAttribute("data-authority-tick"))).toBeGreaterThan(reconnectedTick + 1);
    const settledReconnectRow = Number(await arenaA.getAttribute("data-authority-self-row"));
    expect(settledReconnectRow).toBeGreaterThanOrEqual(afterBurstRow);
    expect(settledReconnectRow).toBeLessThanOrEqual(afterBurstRow + 1); // At most the already-admitted command may commit.
    const settledReconnectTick = Number(await arenaA.getAttribute("data-authority-tick"));
    await expect.poll(async () => Number(await arenaA.getAttribute("data-authority-tick"))).toBeGreaterThan(settledReconnectTick + 2);
    await expect(arenaA).toHaveAttribute("data-authority-self-row", String(settledReconnectRow));
    const socketGenerations = await pageA.evaluate(() =>
      (window as unknown as { __fsggAuthoritySockets: WebSocket[] }).__fsggAuthoritySockets.length);
    const controlledReconnectDiagnostics = diagnostics.slice(diagnosticsBeforeReconnect);
    const controlledReconnectConsole = expectedConsole.splice(expectedBeforeReconnect);
    expect(controlledReconnectDiagnostics.length).toBeGreaterThan(0);
    expect(controlledReconnectDiagnostics.every(item =>
      item.kind === "console" && /^info: \[.+] Information: Connection disconnected\.$/.test(item.detail))).toBe(true);
    diagnostics.splice(diagnosticsBeforeReconnect, controlledReconnectDiagnostics.length);
    await testInfo.attach("controlled-transport-reconnect", {
      body: Buffer.from(JSON.stringify({ staleInputsReplayed: false, socketGenerations, diagnostics: controlledReconnectDiagnostics, expectedConsole: controlledReconnectConsole }, null, 2)),
      contentType: "application/json"
    });
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
  const authoredPixels = await page.locator("#generated-authoring-studio--scene").screenshot();
  await page.getByRole("button", { name: "Play edited arena step" }).click();
  await expect(studio).toHaveAttribute("data-workspace-mode", "play");
  const farPlayed = await snapshot();
  expect(farPlayed.activePlayPreview).toBe(true);
  expect(farPlayed.playSourceHash).toBe(transformed.contentHash);
  expect(farPlayed.playCollision).toBe(false);
  expect(farPlayed.playHealth).toBe(3);
  const previewPixels = await page.locator("#generated-authoring-studio--scene").screenshot();
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
  await page.addInitScript(() => {
    const open = indexedDB.open.bind(indexedDB);
    indexedDB.open = ((name: string, version?: number) => {
      const request = version === undefined ? open(name) : open(name, version);
      if (name !== "FableGameWorkspaceNamespace-svg-studio") return request;
      const delayed = new Proxy(request, {
        get(target, property) { return Reflect.get(target, property, target); },
        set(target, property, value) {
          if (property === "onsuccess") {
            target.onsuccess = event => {
              (window as any).releaseStudioDatabase = () => value.call(delayed, event);
            };
            return true;
          }
          return Reflect.set(target, property, value, target);
        }
      });
      return delayed;
    }) as typeof indexedDB.open;
  });
  await page.goto("http://127.0.0.1:5200/");
  const studio = page.locator("#svg-authoring-studio");
  const starter = page.getByRole("button", { name: "Open starter game" });
  await expect.poll(() => page.evaluate(() => typeof (window as any).releaseStudioDatabase)).toBe("function");
  await expect(starter).toBeDisabled();
  await page.evaluate(() => (window as any).releaseStudioDatabase());
  await expect(page.locator("#generated-scene-status")).toContainText("No persisted scene");
  await expect(starter).toBeEnabled();
  await starter.click();
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

for (const failure of ["open", "load"] as const) {
  test(`Studio remains playable when startup persistence ${failure} fails`, async ({ page }) => {
    test.skip(!hasStudio, "selected composition has no Studio");
    await page.addInitScript(kind => {
      if (kind === "open") {
        const open = indexedDB.open.bind(indexedDB);
        indexedDB.open = ((name: string, version?: number) => {
          if (name === "FableGameWorkspaceNamespace-svg-studio") {
            throw new DOMException("injected open failure", "SecurityError");
          }
          return version === undefined ? open(name) : open(name, version);
        }) as typeof indexedDB.open;
      } else {
        const get = IDBObjectStore.prototype.get;
        IDBObjectStore.prototype.get = function (key) {
          if (key === "project:continuous-arena") {
            throw new DOMException("injected read failure", "UnknownError");
          }
          return get.call(this, key);
        };
      }
    }, failure);
    await page.goto("http://127.0.0.1:5200/");
    await expect(page.locator("#generated-scene-status")).toContainText("Persistence refused: DatabaseError");
    const starter = page.getByRole("button", { name: "Open starter game" });
    await expect(starter).toBeEnabled();
    await starter.click();
    await expect(page.locator("#generated-scene-status")).toContainText("Starter playable game opened");
  });
}

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

    // Start the terminal journey from a known state; the preceding input-source
    // checks intentionally move the player and may already touch the hazard.
    await page.getByRole("button", { name: "Arcade restart" }).click();
    await expect(arcade).toHaveAttribute("data-x", "12");
    await expect(arcade).toHaveAttribute("data-y", "54");
    await expect(arcade).toHaveAttribute("data-health", "2");
    await expect(arcade).toHaveAttribute("data-outcome", "playing");
    await arcade.focus();
    await page.keyboard.down("s");
    await expect.poll(async () => Number(await arcade.getAttribute("data-y")), { timeout: 3000, intervals: [10] }).toBeGreaterThan(75);
    await page.keyboard.up("s");
    await page.keyboard.down("a");
    await expect.poll(async () => Number(await arcade.getAttribute("data-x")), { timeout: 3000 }).toBeLessThan(55);
    await page.keyboard.up("a");
    await page.keyboard.down("d");
    await expect.poll(async () => Number(await arcade.getAttribute("data-health")), { timeout: 4000 }).toBe(1);
    await page.keyboard.up("d");
    // Leave the contact band before seeking a second entry. Horizontal travel
    // on this safe row cannot accidentally consume the remaining health.
    await page.keyboard.down("w");
    await expect.poll(async () => Number(await arcade.getAttribute("data-y")), { timeout: 3000, intervals: [10] }).toBeLessThan(60);
    await page.keyboard.up("w");
    const damagedX = Number(await arcade.getAttribute("data-x"));
    if (damagedX < 108) {
      await page.keyboard.down("d");
      await expect.poll(async () => Number(await arcade.getAttribute("data-x")), { timeout: 3000, intervals: [10] }).toBeGreaterThanOrEqual(108);
      await page.keyboard.up("d");
    } else if (damagedX > 112) {
      await page.keyboard.down("a");
      await expect.poll(async () => Number(await arcade.getAttribute("data-x")), { timeout: 3000, intervals: [10] }).toBeLessThanOrEqual(112);
      await page.keyboard.up("a");
    }
    const secondContactX = Number(await arcade.getAttribute("data-x"));
    await expect.poll(async () => {
      const hazardX = Number(await arcade.getAttribute("data-hazard-x"));
      return hazardX >= secondContactX - 4 && hazardX <= secondContactX + 4;
    }, { timeout: 3000, intervals: [10] }).toBe(true);
    await page.keyboard.down("s");
    try {
      await expect(arcade).toHaveAttribute("data-outcome", "lost", { timeout: 5000 });
    } catch (error) {
      const before = await arcade.evaluate(element => ({
        health: element.getAttribute("data-health"), outcome: element.getAttribute("data-outcome"),
        x: Number(element.getAttribute("data-x")), y: Number(element.getAttribute("data-y")),
        hazardX: Number(element.getAttribute("data-hazard-x"))
      }));
      await page.waitForTimeout(34);
      const after = await arcade.evaluate(element => ({
        x: Number(element.getAttribute("data-x")), y: Number(element.getAttribute("data-y"))
      }));
      await testInfo.attach("arcade-loss-state.json", {
        body: JSON.stringify({ ...before, velocityDelta: { x: after.x - before.x, y: after.y - before.y } }, null, 2),
        contentType: "application/json"
      });
      throw error;
    }
    await page.keyboard.up("s");
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

test("FourD reference composes local session, normalized input, transformed hit testing and settled disposal", async ({ page }) => {
  test.skip(!hasFourDReference, "selected composition has no FourD reference fixture");
  const observeDisposal = async (): Promise<void> => page.evaluate(() => {
    const owner = window as any;
    owner.__fourdDisposedElement = undefined;
    owner.__fourdDetachedMove = [...document.querySelectorAll<HTMLButtonElement>("#fourd-reference button")]
      .find(button => button.textContent === "Move to legal full cell");
    const observer = new MutationObserver(records => {
      for (const record of records) {
        for (const node of record.removedNodes) {
          if (node instanceof HTMLElement && node.id === "fourd-reference") {
            owner.__fourdDisposedElement = node;
            observer.disconnect();
          }
        }
      }
    });
    observer.observe(document.body, { childList: true });
  });
  const disposedSnapshot = async (): Promise<{ inputOwned: string | null; sessionOwned: string | null; commandOrder: string | null } | undefined> =>
    page.evaluate(() => {
      const element = (window as any).__fourdDisposedElement as HTMLElement | undefined;
      return element === undefined ? undefined : {
        inputOwned: element.getAttribute("data-input-owned"),
        sessionOwned: element.getAttribute("data-session-owned"),
        commandOrder: element.getAttribute("data-command-order")
      };
    });
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  await expect(reference).toHaveAttribute("data-fixture-id", "fourd-reference-encounter");
  await expect(reference).toHaveAttribute("data-agent-full-cell", "0:0:0:0");

  // The click uses the actual painted bounds after the Scene camera pan/zoom;
  // FourDReference asks SvgBrowser.HitTest to invert that transform.
  const destination = page.locator('[data-scene-object-id="full-cell:1:1:1:1"]');
  await expect(destination).toBeVisible();
  await destination.scrollIntoViewIfNeeded();
  const bounds = await destination.boundingBox();
  expect(bounds).not.toBeNull();
  // Let Playwright wait for browser scroll/compositor actionability before delivering
  // the same production pointer observation to the transformed retained object.
  await destination.click();
  await expect(reference).toHaveAttribute("data-agent-full-cell", "0:0:0:0");
  await expect(reference).toHaveAttribute("data-last-command-destination", "1:1:1:1");
  await expect(reference).toHaveAttribute("data-command-order", "1");

  // Native editing and an active IME retain Enter instead of dispatching gameplay.
  const note = page.getByRole("textbox", { name: "Encounter note" });
  await note.focus();
  await note.dispatchEvent("compositionstart");
  await note.press("Enter");
  await note.fill("四 dimensional note");
  await note.dispatchEvent("compositionend");
  await expect(note).toHaveValue("四 dimensional note");
  await expect(reference).toHaveAttribute("data-command-order", "1");

  // Keyboard maps to the same semantic command. Ordered admissions remain 1,2
  // while the replaceable projection demand remains a single pending request.
  await reference.focus();
  await page.keyboard.press("Enter");
  await expect(reference).toHaveAttribute("data-command-order", "1,2");
  await expect(reference).toHaveAttribute("data-projection-request-count", "1");
  await page.getByRole("button", { name: "Request projection burst" }).click();
  await expect(reference).toHaveAttribute("data-projection-request-count", "1");

  await reference.focus();
  await page.keyboard.down("h");
  await expect(reference).toHaveAttribute("data-held", "true");
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await expect(reference).toHaveAttribute("data-held", "false");
  await page.keyboard.up("h");

  // Replacing the generation makes the pending prior-generation reply stale.
  const generationBeforeReplace = Number(await reference.getAttribute("data-generation") ?? "0");
  const requestsBeforeReplace = Number(await reference.getAttribute("data-projection-request-count"));
  await page.getByRole("button", { name: "Replace local session" }).click();
  await expect.poll(async () => Number(await reference.getAttribute("data-generation"))).toBeGreaterThan(generationBeforeReplace);
  await page.getByRole("button", { name: "Complete oldest projection" }).click();
  await expect(reference).not.toHaveAttribute("data-applied-revision", /.+/);
  await reference.focus();
  await page.keyboard.press("Enter");
  await expect(reference).toHaveAttribute("data-command-order", "1,2,3");
  await expect.poll(async () => Number(await reference.getAttribute("data-projection-request-count"))).toBeGreaterThan(requestsBeforeReplace);
  await page.getByRole("button", { name: "Complete current projection" }).click();
  await expect(reference).toHaveAttribute("data-applied-revision", "1");

  await observeDisposal();
  await page.getByRole("button", { name: "Dispose FourD reference" }).click();
  await expect(reference).toHaveCount(0);
  await expect.poll(disposedSnapshot).toEqual({ inputOwned: "0", sessionOwned: "0", commandOrder: "1,2,3" });
  await page.evaluate(() => (window as any).__fourdDetachedMove.click());
  await expect.poll(disposedSnapshot).toEqual({ inputOwned: "0", sessionOwned: "0", commandOrder: "1,2,3" });

  // A fresh mount after disposal owns and then settles its resources independently.
  await page.reload();
  const remounted = page.locator("#fourd-reference");
  await expect(remounted).toHaveAttribute("data-agent-full-cell", "0:0:0:0");
  await page.getByRole("button", { name: "Replace local session" }).click();
  await observeDisposal();
  await page.getByRole("button", { name: "Dispose FourD reference" }).click();
  await expect(remounted).toHaveCount(0);
  await expect.poll(disposedSnapshot).toEqual({ inputOwned: "0", sessionOwned: "0", commandOrder: "" });
});

test("Local save and replay example preserves synthetic state and settles detached controls", async ({ page }) => {
  test.skip(!hasFourDReference || isLegacySvgPreview, "selected composition has no local save/replay example");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  const status = page.locator("#local-save-replay-status");
  await expect(reference).toHaveAttribute("data-local-agent", "-7:23:-41:89");
  await expect(reference).toHaveAttribute("data-local-accepted", "0");
  await page.getByRole("button", { name: "Synthetic inspect full cell", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-accepted", "1");
  await page.getByRole("button", { name: "Save synthetic local snapshot", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-saved", "true");
  await page.getByRole("button", { name: "Synthetic inspect full cell", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-accepted", "2");
  await page.getByRole("button", { name: "Replay synthetic local recording", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-replay-count", "2");
  await expect(reference).toHaveAttribute("data-local-accepted", "2");
  await expect(status).toContainText("replay preview completed");
  await page.getByRole("button", { name: "Restore synthetic local snapshot", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-accepted", "1");
  await expect(status).toContainText("snapshot restored; new recording epoch");
  await page.getByRole("button", { name: "Replay synthetic local recording", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-replay-count", "1");
  await expect(reference).toHaveAttribute("data-local-agent", "-7:23:-41:89");
  await expect(reference).toHaveAttribute("data-agent-full-cell", "0:0:0:0");

  const disposed = await reference.elementHandle();
  const retainedControls = await reference.locator("button").filter({ hasText: /[Ss]ynthetic/ }).elementHandles();
  expect(retainedControls).toHaveLength(4);
  await page.getByRole("button", { name: "Dispose FourD reference", exact: true }).click();
  await expect(reference).toHaveCount(0);
  const before = await disposed!.evaluate(element => element.outerHTML);
  for (const control of retainedControls) await control.evaluate(element => element.click());
  expect(await disposed!.evaluate(element => element.outerHTML)).toBe(before);
  expect(await disposed!.getAttribute("data-input-owned")).toBe("0");
  expect(await disposed!.getAttribute("data-session-owned")).toBe("0");
});

// These storage probes inspect serialized fixture strings, never cast JavaScript objects into F# snapshots.
const localSaveRecord = async (page: Page): Promise<Record<string, unknown>> =>
  page.evaluate(async () => await new Promise<Record<string, unknown>>((resolve, reject) => {
    const open = indexedDB.open("FableGameWorkspaceNamespace-fourd-reference", 1);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const database = open.result;
      const get = database.transaction("records", "readonly").objectStore("records").get("save:synthetic-fourd-v1");
      get.onerror = () => { database.close(); reject(get.error); };
      get.onsuccess = () => { database.close(); resolve(get.result); };
    };
  }));

const writeLocalSaveRecord = async (page: Page, record: Record<string, unknown>): Promise<void> =>
  page.evaluate(async record => await new Promise<void>((resolve, reject) => {
    const open = indexedDB.open("FableGameWorkspaceNamespace-fourd-reference", 1);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const database = open.result;
      const transaction = database.transaction("records", "readwrite");
      transaction.objectStore("records").put(record);
      transaction.onerror = () => { database.close(); reject(transaction.error); };
      transaction.oncomplete = () => { database.close(); resolve(); };
    };
  }), record);

test("Local synthetic snapshot survives page recreation with lossless uint64 order and typed refusals", async ({ page }) => {
  test.skip(!hasFourDReference || !hasDurableLocalSave, "selected archive has no durable synthetic reference");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  const status = page.locator("#local-save-replay-status");
  const inspect = page.getByRole("button", { name: "Synthetic inspect full cell", exact: true });
  const save = page.getByRole("button", { name: "Save synthetic local snapshot", exact: true });
  const restore = page.getByRole("button", { name: "Restore synthetic local snapshot", exact: true });
  await expect(reference).toHaveAttribute("data-local-storage-ready", "true");
  await inspect.click();
  await save.click();
  await expect(status).toContainText("snapshot saved in browser storage");
  const saved = await localSaveRecord(page);
  await page.reload();
  await expect(reference).toHaveAttribute("data-local-storage-ready", "true");
  await expect(reference).toHaveAttribute("data-local-accepted", "0"); // Loading is explicit.
  await restore.click();
  await expect(reference).toHaveAttribute("data-local-accepted", "1");
  await expect(reference).toHaveAttribute("data-local-agent", "-7:23:-41:89");
  await expect(status).toContainText("snapshot restored; new recording epoch");
  await page.getByRole("button", { name: "Replay synthetic local recording", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-replay-count", "1");

  if (typeof saved.payload !== "string" || typeof saved.payloadHash !== "string") throw new Error("missing typed fixture strings");
  const large = "9007199254740993";
  const largeRecord = { ...saved, payload: saved.payload.replace("1@", large + "@"),
    payloadHash: saved.payloadHash.replace("1@", large + "@") };
  await writeLocalSaveRecord(page, largeRecord);
  await restore.click();
  await expect(status).toContainText("snapshot restored; new recording epoch");
  await expect(reference).toHaveAttribute("data-local-storage-owned", "0");
  await inspect.click();
  await expect(reference).toHaveAttribute("data-local-accepted", "2");
  await save.click();
  await expect(status).toContainText("snapshot saved in browser storage");
  const exact = await localSaveRecord(page);
  expect(exact.payload).toContain("9007199254740993@");
  expect(exact.payload).toContain("9007199254740994@");
  if (typeof exact.payload !== "string") throw new Error("missing serialized snapshot");
  for (const invalid of [
    { ...exact, schemaVersion: 2 },
    { ...exact, payload: exact.payload.replace("fsgg.synthetic.fourd.save/1", "fsgg.synthetic.fourd.save/2") },
    { ...exact, payload: exact.payload + "\nunknown-field" },
    { ...exact, payload: exact.payload.replace("\npure-inspection-fixture\n", "\nwrong-profile\n") }
  ]) {
    await writeLocalSaveRecord(page, invalid);
    await restore.click();
    await expect(status).toContainText("restore refused");
    await expect(reference).toHaveAttribute("data-local-accepted", "2");
  }
  await expect(reference).toHaveAttribute("data-agent-full-cell", "0:0:0:0");
  await expect(reference).toHaveAttribute("data-command-order", "");
});

test("Local synthetic snapshot storage failures and late loads preserve accepted state and settle disposal", async ({ page }) => {
  test.skip(!hasFourDReference || !hasDurableLocalSave, "selected archive has no durable synthetic reference");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  const status = page.locator("#local-save-replay-status");
  await expect(reference).toHaveAttribute("data-local-storage-ready", "true");
  await page.getByRole("button", { name: "Synthetic inspect full cell", exact: true }).click();
  await page.getByRole("button", { name: "Save synthetic local snapshot", exact: true }).click();
  await expect(status).toContainText("snapshot saved in browser storage");
  const saved = await localSaveRecord(page);
  await page.getByRole("button", { name: "Synthetic inspect full cell", exact: true }).click();
  await page.evaluate(() => {
    const put = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (value, key) {
      if (value?.key === "save:synthetic-fourd-v1") throw new DOMException("injected quota failure", "QuotaExceededError");
      return key === undefined ? put.call(this, value) : put.call(this, value, key);
    };
  });
  await page.getByRole("button", { name: "Save synthetic local snapshot", exact: true }).click();
  await expect(status).toContainText("save refused");
  await expect(reference).toHaveAttribute("data-local-accepted", "2");
  expect(await localSaveRecord(page)).toEqual(saved);
  await page.reload(); // Restores the browser API as well as recreating the caller.
  await expect(reference).toHaveAttribute("data-local-storage-ready", "true");
  await page.getByRole("button", { name: "Restore synthetic local snapshot", exact: true }).click();
  await expect(reference).toHaveAttribute("data-local-accepted", "1");
  await page.evaluate(() => {
    const buttons = [...document.querySelectorAll<HTMLButtonElement>("#fourd-reference button")];
    buttons.find(b => b.textContent === "Restore synthetic local snapshot")!.click();
    buttons.find(b => b.textContent === "Synthetic inspect full cell")!.click();
  });
  await expect(status).toContainText("load superseded by accepted local changes");
  await expect(reference).toHaveAttribute("data-local-accepted", "2");

  const settled = await page.evaluate(async () => await new Promise<{ before: string; after: string }>((resolve, reject) => {
    const reference = document.querySelector<HTMLElement>("#fourd-reference")!;
    const get = IDBObjectStore.prototype.get;
    let before = "";
    IDBObjectStore.prototype.get = function (key) {
      const request = get.call(this, key);
      if (key !== "save:synthetic-fourd-v1") return request;
      const delayed: IDBRequest = new Proxy(request, {
        get(target, property) { return Reflect.get(target, property, target); },
        set(target, property, callback) {
          if (property === "onsuccess") {
            target.onsuccess = event => {
              IDBObjectStore.prototype.get = get;
              try { callback.call(delayed, event); resolve({ before, after: reference.outerHTML }); }
              catch (error) { reject(error); }
            };
            return true;
          }
          return Reflect.set(target, property, callback, target);
        }
      });
      return delayed;
    };
    const buttons = [...reference.querySelectorAll<HTMLButtonElement>("button")];
    buttons.find(b => b.textContent === "Restore synthetic local snapshot")!.click();
    buttons.find(b => b.textContent === "Dispose FourD reference")!.click();
    before = reference.outerHTML;
  }));
  expect(settled.after).toBe(settled.before);
  expect(settled.after).toContain('data-local-storage-owned="0"');
  expect(settled.after).toContain('data-local-storage-disposed="true"');
  await expect(reference).toHaveCount(0);
});

// Click through the DOM without moving focus: a real pointer click focuses the button, which would hide whether the
// reference preserved focus across the update it triggers.
const pressWithoutFocus = (page: Page, name: string): Promise<void> =>
  page.evaluate(label => {
    const button = [...document.querySelectorAll<HTMLButtonElement>("#fourd-reference button")]
      .find(candidate => candidate.textContent === label);
    if (button === undefined) throw new Error("missing reference control: " + label);
    button.click();
  }, name);

// Every retained update ends in an applied projection; waiting on its counter proves the update finished before
// focus, values and node identity are asserted, so a late focus-stealing re-render cannot slip past.
const appliedCount = async (reference: Locator): Promise<number> => Number(await reference.getAttribute("data-applied-count") ?? "0");

const markIdentity = (page: Page): Promise<void> =>
  page.evaluate(() => {
    const ids = ["fourd-reference-note", "fourd-reference-options", "fourd-reference-difficulty", "fourd-reference-hints"];
    for (const id of ids) (document.getElementById(id) as any).__identity = id;
    document.querySelectorAll<HTMLInputElement>('input[name="fourd-reference-camera"]')
      .forEach(radio => (radio as any).__identity = "camera:" + radio.value);
  });

const identities = (page: Page): Promise<string[]> =>
  page.evaluate(() => [
    "fourd-reference-note", "fourd-reference-options", "fourd-reference-difficulty", "fourd-reference-hints"
  ].map(id => (document.getElementById(id) as any)?.__identity ?? "recreated:" + id)
    .concat([...document.querySelectorAll<HTMLInputElement>('input[name="fourd-reference-camera"]')]
      .map(radio => (radio as any).__identity ?? "recreated:camera:" + radio.value)));

const expectedIdentities = [
  "fourd-reference-note", "fourd-reference-options", "fourd-reference-difficulty", "fourd-reference-hints",
  "camera:overview", "camera:close"
];

test("FourD reference options panel keeps labelled native controls, tab order and state across retained updates and a session replacement", async ({ page }) => {
  test.skip(!hasFourDReference || isLegacySvgPreview, "selected composition has no FourD reference options panel");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  await expect(reference).toHaveAttribute("data-fixture-id", "fourd-reference-encounter");
  const panel = reference.getByRole("group", { name: "Encounter options", exact: true });
  const difficulty = panel.getByRole("combobox", { name: "Difficulty", exact: true });
  const hints = panel.getByRole("checkbox", { name: "Show hints", exact: true });
  const overview = panel.getByRole("radio", { name: "Overview", exact: true });
  const close = panel.getByRole("radio", { name: "Close focus", exact: true });
  const note = reference.getByRole("textbox", { name: "Encounter note", exact: true });
  const status = reference.locator("#fourd-reference-options-status");

  // Every control is reachable by its accessible name and starts in its documented state.
  await expect(panel.getByRole("group", { name: "Camera", exact: true })).toHaveCount(1);
  await expect(difficulty).toHaveValue("standard");
  await expect(hints).not.toBeChecked();
  await expect(overview).toBeChecked();
  await expect(close).not.toBeChecked();
  await expect(reference).toHaveAttribute("data-option-difficulty", "standard");

  // Document order is tab order: note, then the island's controls (one tab stop for the radio group).
  await note.focus();
  for (const next of [difficulty, hints, overview]) {
    await page.keyboard.press("Tab");
    await expect(next).toBeFocused();
  }
  await page.keyboard.press("Shift+Tab");
  await expect(hints).toBeFocused();

  // Native keyboard operation changes the controls; none of it becomes gameplay input.
  await difficulty.selectOption("severe");
  await hints.focus();
  await page.keyboard.press("Space");
  await expect(hints).toBeChecked();
  await hints.press("Enter");
  await overview.focus();
  await page.keyboard.press("ArrowRight");
  await expect(close).toBeChecked();
  await expect(overview).not.toBeChecked();
  await expect(reference).toHaveAttribute("data-command-order", "");
  await expect(status).toContainText("difficulty severe, hints on, camera close");

  // A retained scene update and then a session replacement run while a control holds focus; the island is never recreated.
  // The reference applies a projection once per revision, so exactly one scene update is driven and awaited, then the replacement.
  await markIdentity(page);
  await hints.focus();
  const appliedBefore = await appliedCount(reference);
  await pressWithoutFocus(page, "Move to legal full cell");
  await expect(reference).toHaveAttribute("data-command-order", "1");
  await pressWithoutFocus(page, "Complete current projection");
  await expect.poll(() => appliedCount(reference)).toBeGreaterThan(appliedBefore);
  const generation = Number(await reference.getAttribute("data-generation") ?? "0");
  await pressWithoutFocus(page, "Replace local session");
  await expect.poll(async () => Number(await reference.getAttribute("data-generation"))).toBeGreaterThan(generation);

  await expect(hints).toBeFocused();
  await expect(hints).toBeChecked();
  await expect(difficulty).toHaveValue("severe");
  await expect(close).toBeChecked();
  await expect(reference).toHaveAttribute("data-option-difficulty", "severe");
  await expect(status).toContainText("difficulty severe, hints on, camera close; revision");
  expect(await identities(page)).toEqual(expectedIdentities);

  // Disposal removes the island's owned listeners: a detached control no longer updates the disposed reference.
  const disposed = await reference.elementHandle();
  const detached = await difficulty.elementHandle();
  await page.getByRole("button", { name: "Dispose FourD reference", exact: true }).click();
  await expect(reference).toHaveCount(0);
  await detached!.evaluate(element => { (element as HTMLSelectElement).value = "calm"; element.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(await disposed!.getAttribute("data-option-difficulty")).toBe("severe");
});

test("FourD reference focus and native editing text survive a retained update and a session replacement", async ({ page }) => {
  test.skip(!hasFourDReference || isLegacySvgPreview, "selected composition has no FourD reference");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  await expect(reference).toHaveAttribute("data-fixture-id", "fourd-reference-encounter");
  const note = reference.getByRole("textbox", { name: "Encounter note", exact: true });
  await markIdentity(page);

  // Text, caret and an active composition live in the native textbox while the scene updates and the session is replaced.
  await note.focus();
  await note.fill("四 dimensional note");
  await note.evaluate(element => (element as HTMLInputElement).setSelectionRange(2, 9));
  await note.dispatchEvent("compositionstart");
  const appliedBefore = await appliedCount(reference);
  await pressWithoutFocus(page, "Move to legal full cell");
  await expect(reference).toHaveAttribute("data-command-order", "1");
  await pressWithoutFocus(page, "Complete current projection");
  await expect.poll(() => appliedCount(reference)).toBeGreaterThan(appliedBefore);
  const generation = Number(await reference.getAttribute("data-generation") ?? "0");
  await pressWithoutFocus(page, "Replace local session");
  await expect.poll(async () => Number(await reference.getAttribute("data-generation"))).toBeGreaterThan(generation);
  // Focus is asserted before and by a page-level keypress: Locator.press would refocus the note and hide a focus steal.
  await expect(note).toBeFocused();
  await page.keyboard.press("Enter");
  await note.dispatchEvent("compositionend");

  await expect(note).toBeFocused();
  await expect(note).toHaveValue("四 dimensional note");
  expect(await note.evaluate(element => [(element as HTMLInputElement).selectionStart, (element as HTMLInputElement).selectionEnd])).toEqual([2, 9]);
  await expect(reference).toHaveAttribute("data-command-order", "1");
  expect(await identities(page)).toEqual(expectedIdentities);

  // Focus on the island's own select and on the reference root also survives further session replacements.
  const difficulty = reference.getByRole("combobox", { name: "Difficulty", exact: true });
  for (const [target, name] of [[difficulty, "select"], [reference, "root"]] as const) {
    await target.focus();
    const before = Number(await reference.getAttribute("data-generation") ?? "0");
    await pressWithoutFocus(page, "Replace local session");
    await expect.poll(async () => Number(await reference.getAttribute("data-generation")), name).toBeGreaterThan(before);
    await expect(target, name).toBeFocused();
  }
  await expect(note).toHaveValue("四 dimensional note");
  expect(await identities(page)).toEqual(expectedIdentities);
});

// The camera group carries the retained scene's pan and zoom as a transform attribute.
const cameraTransform = (target: Locator): Promise<string | null> =>
  target.evaluate(element => element.closest("g[transform]")?.getAttribute("transform") ?? null);

const centre = async (target: Locator): Promise<{ x: number; y: number; width: number }> => {
  await target.scrollIntoViewIfNeeded();
  const bounds = await target.boundingBox();
  expect(bounds).not.toBeNull();
  return { x: bounds!.x + bounds!.width / 2, y: bounds!.y + bounds!.height / 2, width: bounds!.width };
};

test("FourD reference pointer hit testing inverts a wheel zoom and a narrow viewport and still selects the painted target", async ({ page }) => {
  test.skip(!hasFourDReference || isLegacySvgPreview, "selected composition has no FourD reference");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  await expect(reference).toHaveAttribute("data-fixture-id", "fourd-reference-encounter");
  const origin = page.locator('[data-scene-object-id="full-cell:0:0:0:0"]');
  const destination = page.locator('[data-scene-object-id="full-cell:1:1:1:1"]');
  const staleDestination = await centre(destination);
  const originBefore = await centre(origin);
  const transformBefore = await cameraTransform(destination);

  // Real wheel events zoom the retained camera about the pointer, here out and anchored on the origin cell, so the origin stays
  // under the pointer while the destination's paint moves toward it and shrinks.
  await page.mouse.move(originBefore.x, originBefore.y);
  for (let step = 0; step < 4; step++) await page.mouse.wheel(0, 100);
  await expect.poll(() => cameraTransform(destination)).not.toBe(transformBefore);
  const zoomed = await centre(destination);
  expect(zoomed.width).toBeLessThan(staleDestination.width * 0.8);
  expect(Math.hypot(zoomed.x - staleDestination.x, zoomed.y - staleDestination.y)).toBeGreaterThan(zoomed.width / 2);

  // Causal control: the destination's pre-zoom screen point no longer lies on its paint, and a click there selects nothing
  // that moves gameplay. A hit test that ignored the new camera would still resolve the destination there.
  await page.mouse.click(staleDestination.x, staleDestination.y);
  await expect(reference).not.toHaveAttribute("data-hit", "full-cell:1:1:1:1");
  await expect(reference).toHaveAttribute("data-command-order", "");

  // The pointer lands on the zoomed paint of each cell, so the hit test inverted the new camera. The origin cell selects no
  // gameplay command; only the destination admits one.
  const originPoint = await centre(origin);
  await page.mouse.click(originPoint.x, originPoint.y);
  await expect(reference).toHaveAttribute("data-hit", "full-cell:0:0:0:0");
  await expect(reference).toHaveAttribute("data-command-order", "");
  const destinationPoint = await centre(destination);
  await page.mouse.click(destinationPoint.x, destinationPoint.y);
  await expect(reference).toHaveAttribute("data-hit", "full-cell:1:1:1:1");
  await expect(reference).toHaveAttribute("data-command-order", "1");

  // A retained scene update keeps the user's camera, so the painted target and its hit test stay where the user left them.
  const zoomedTransform = await cameraTransform(destination);
  expect(zoomedTransform).not.toBe(transformBefore);
  const appliedBefore = await appliedCount(reference);
  await pressWithoutFocus(page, "Complete current projection");
  await expect.poll(() => appliedCount(reference)).toBeGreaterThan(appliedBefore);
  expect(await cameraTransform(destination)).toBe(zoomedTransform);

  // The same camera in a narrow viewport moves the paint again; the pointer still resolves the painted cell.
  await page.setViewportSize({ width: 320, height: 568 });
  const narrowOrigin = await centre(origin);
  await page.mouse.click(narrowOrigin.x, narrowOrigin.y);
  await expect(reference).toHaveAttribute("data-hit", "full-cell:0:0:0:0");
  const narrowDestination = await centre(destination);
  await page.mouse.click(narrowDestination.x, narrowDestination.y);
  await expect(reference).toHaveAttribute("data-hit", "full-cell:1:1:1:1");
  await expect(reference).toHaveAttribute("data-command-order", "1,2");
});

test("FourD reference held input is released by hidden visibility, focus leaving the reference and disposal", async ({ page }) => {
  test.skip(!hasFourDReference || isLegacySvgPreview, "selected composition has no FourD reference");
  await page.goto("/");
  const reference = page.locator("#fourd-reference");
  await expect(reference).toHaveAttribute("data-fixture-id", "fourd-reference-encounter");
  const hold = async () => {
    await reference.focus();
    await page.keyboard.down("h");
    await expect(reference).toHaveAttribute("data-held", "true");
  };

  // A visibilitychange while the document is still visible is not a loss of input.
  await hold();
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await expect(reference).toHaveAttribute("data-held", "true");
  // A hidden document releases the held action; the late keyup does not hold it again.
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(reference).toHaveAttribute("data-held", "false");
  await page.evaluate(() => { delete (document as unknown as { hidden?: boolean }).hidden; });
  await page.keyboard.up("h");
  await expect(reference).toHaveAttribute("data-held", "false");

  // Focus moving between the reference's own controls keeps the hold; focus leaving the reference releases it.
  await hold();
  await reference.getByRole("textbox", { name: "Encounter note", exact: true }).focus();
  await expect(reference).toHaveAttribute("data-held", "true");
  await page.evaluate(() => (document.activeElement as HTMLElement).blur());
  await expect(reference).toHaveAttribute("data-held", "false");
  await page.keyboard.up("h");

  // Input still works after a release, and disposal while held releases and leaves the disposed element neutral.
  await hold();
  const disposed = await reference.elementHandle();
  await page.getByRole("button", { name: "Dispose FourD reference", exact: true }).click();
  await expect(reference).toHaveCount(0);
  expect(await disposed!.getAttribute("data-held")).toBe("false");
  expect(await disposed!.getAttribute("data-input-owned")).toBe("0");
  await page.keyboard.up("h");
  expect(await disposed!.getAttribute("data-held")).toBe("false");
  expect(await disposed!.getAttribute("data-command-order")).toBe("");
});

test("external authority reference note, caret and focus survive snapshot application, reconnect and authority replacement", async ({ page }) => {
  test.skip(!hasExternalAuthorityReference, "selected composition has no external authority reference");
  await page.goto("/");
  await page.getByRole("button", { name: "Mount external authority reference", exact: true }).click();
  const reference = page.locator("#external-authority-reference");
  const note = reference.getByRole("textbox", { name: "External reference note", exact: true });
  // Click through the DOM without moving focus, so a focus steal by the reference cannot be hidden by the click itself.
  const quiet = (label: string) => reference.evaluate((root, name) => {
    const button = [...root.querySelectorAll<HTMLButtonElement>(":scope > button")].find(candidate => candidate.textContent === name);
    if (button === undefined) throw new Error("missing reference control: " + name);
    button.click();
  }, label);
  await note.evaluate(element => ((element as unknown as { __identity: string }).__identity = "external-note"));
  await note.focus();
  await note.fill("editable 四");
  await note.evaluate(element => (element as HTMLInputElement).setSelectionRange(3, 9));

  const survives = async (stage: string) => {
    await expect(note, stage).toBeFocused();
    await expect(note, stage).toHaveValue("editable 四");
    expect(await note.evaluate(element => [(element as HTMLInputElement).selectionStart, (element as HTMLInputElement).selectionEnd]), stage).toEqual([3, 9]);
    expect(await note.evaluate(element => (element as unknown as { __identity?: string }).__identity), stage).toBe("external-note");
  };
  await quiet("Connect sample authority");
  await quiet("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "1");
  await survives("first snapshot");
  await quiet("Increment external value");
  await quiet("Request external burst");
  await quiet("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "2");
  await survives("second snapshot");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment");

  // An active composition suspends command admission for the whole reference; the same invocation is inert until it ends.
  await note.dispatchEvent("compositionstart");
  await quiet("Increment external value");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment");
  await survives("composing");
  await quiet("Disconnect sample authority");
  await quiet("Connect sample authority");
  await expect(reference).toHaveAttribute("data-preserved-baseline", "true");
  await quiet("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-pending", "false");
  await survives("reconnect");
  await quiet("Replace sample authority");
  await quiet("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-epoch", "epoch-B");
  await survives("authority replacement");

  // Enter in the focused, composing note stays with the note; the island never reaches the command stream.
  await page.keyboard.press("Enter");
  await note.dispatchEvent("compositionend");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment");
  await survives("keypress");

  // After disposal the note is still an ordinary editable textbox and the disposed reference admits nothing from it.
  await quiet("Dispose external reference");
  await expect(reference).toHaveAttribute("data-disposed", "true");
  await note.fill("still editable");
  await note.press("Enter");
  await expect(note).toHaveValue("still editable");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment");
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

test("external authority reference fences captured snapshots and settles commands independently", async ({ page }, testInfo) => {
  test.skip(!hasExternalAuthorityReference,
    "selected composition has no external authority reference");
  await page.goto("/");
  await testInfo.attach("external-reference-browser", {
    body: JSON.stringify({ family: testInfo.project.name, loadedVersion: page.context().browser()?.version() }),
    contentType: "application/json"
  });
  await expect(page.locator("#external-authority-reference")).toHaveCount(0);
  await page.getByRole("button", { name: "Mount external authority reference", exact: true }).click();
  const reference = page.locator("#external-authority-reference");
  const press = (name: string) => reference.getByRole("button", { name, exact: true }).and(reference.locator(":scope > button")).click();
  await expect(reference).toHaveAttribute("data-status", "Disconnected");
  await press("Connect sample authority");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-epoch", "epoch-A");
  await expect(reference).toHaveAttribute("data-applied-revision", "1");
  await press("Increment external value"); // capture rev2
  await press("Reject sample command"); // queue presentation, preserve rejected receipt
  await press("Request external burst");
  await expect(reference).toHaveAttribute("data-gateway-owned", "1");
  await expect(reference).toHaveAttribute("data-queued", "true");
  await expect(reference).toHaveAttribute("data-request-count", "2");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "2");
  await expect(reference).toHaveAttribute("data-request-count", "3");
  await press("Increment external value"); // queued capture remains rev2, authority is now rev3
  await press("Complete current external snapshot"); // duplicate releases slot, drains rev3 demand
  await expect(reference).toHaveAttribute("data-request-count", "4");
  await expect(reference).toHaveAttribute("data-applied-revision", "2");
  await press("Complete oldest external snapshot"); // old acquisition must not paint
  await expect(reference).toHaveAttribute("data-applied-revision", "2");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "3");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment,sample:2:external.reject,sample:3:external.increment");
  await expect(reference).toHaveAttribute("data-receipt-order", "sample:1:accepted,sample:2:rejected,sample:3:accepted");
  await press("Disconnect sample authority");
  await press("Connect sample authority");
  await expect(reference).toHaveAttribute("data-preserved-baseline", "true");
  await press("Complete current external snapshot"); // same authority rev3 rejected
  await expect(reference).toHaveAttribute("data-pending", "false");
  await press("Request cached external snapshot"); // genuine captured rev1 on a current acquisition
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "3");
  await expect(reference).toHaveAttribute("data-pending", "false");
  await press("Increment external value");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "4");
  await press("Request external burst");
  await press("Replace sample authority");
  await press("Complete oldest external snapshot"); // old epoch/generation
  await expect(reference).toHaveAttribute("data-applied-epoch", "epoch-A");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-epoch", "epoch-B");
  await expect(reference).toHaveAttribute("data-applied-revision", "1");
  await expect(reference).toHaveAttribute("data-receipt-order", "sample:1:accepted,sample:2:rejected,sample:3:accepted,sample:4:accepted");
});

test("external authority reference recovers failures and disposes owned resources terminally", async ({ page }) => {
  test.skip(!hasExternalAuthorityReference,
    "selected composition has no external authority reference");
  await page.goto("/");
  await page.getByRole("button", { name: "Mount external authority reference", exact: true }).click();
  const reference = page.locator("#external-authority-reference");
  const press = (name: string) => reference.getByRole("button", { name, exact: true }).and(reference.locator(":scope > button")).click();
  await press("Connect sample authority");
  for (const failure of ["Lose external acquisition", "Cancel external acquisition", "Fail external acquisition"]) {
    await press("Request external burst");
    await press(failure);
    await expect(reference).toHaveAttribute("data-gateway-owned", "1");
  }
  await press("Fail next external presentation");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-callback-failure", "true");
  await press("Increment external value");
  await press("Complete current external snapshot");
  await expect(reference).toHaveAttribute("data-applied-revision", "2");
  await press("Request external burst");
  await reference.evaluate(element => {
    (window as any).__externalButtons = [...element.querySelectorAll<HTMLButtonElement>("button")];
    (window as any).__externalReceipts = element.getAttribute("data-receipt-order");
  });
  await press("Dispose external reference");
  await expect(reference).toHaveAttribute("data-disposed", "true");
  for (const field of ["input", "host", "gateway", "button", "svg"]) {
    await expect(reference).toHaveAttribute(`data-${field}-owned`, "0");
  }
  await expect(reference).toHaveAttribute("data-cancellation-unknown", "false");
  await expect(reference.locator("svg")).toHaveCount(0);
  await page.evaluate(() => (window as any).__externalButtons.forEach((button: HTMLButtonElement) => button.click()));
  await expect(reference).toHaveAttribute("data-disposed", "true");
  await expect(reference).toHaveAttribute("data-receipt-order", await page.evaluate(() => (window as any).__externalReceipts));
});

test("external authority reference uses production keyboard pointer editing and IME input", async ({ page }) => {
  test.skip(!hasExternalAuthorityReference,
    "selected composition has no external authority reference");
  await page.goto("/");
  await page.getByRole("button", { name: "Mount external authority reference", exact: true }).click();
  const reference = page.locator("#external-authority-reference");
  await reference.getByRole("button", { name: "Connect sample authority", exact: true }).click();
  await reference.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("r");
  await expect(reference).toHaveAttribute("data-receipt-order", "sample:1:accepted,sample:2:rejected");
  const note = reference.getByRole("textbox", { name: "External reference note" });
  await note.fill("editable");
  await note.press("Enter");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment,sample:2:external.reject");
  await reference.focus();
  await reference.dispatchEvent("compositionstart");
  await page.keyboard.press("Enter");
  await reference.dispatchEvent("compositionend");
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment,sample:2:external.reject");
  const target = reference.locator('[data-scene-object-id="external.increment"]');
  await target.scrollIntoViewIfNeeded();
  const bounds = await target.boundingBox();
  expect(bounds).not.toBeNull();
  // Production retained SVG hit testing inverts the camera pan and zoom.
  await page.mouse.click(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
  await expect(reference).toHaveAttribute("data-command-order", "sample:1:external.increment,sample:2:external.reject,sample:3:external.increment");
  const revision = await reference.getAttribute("data-authority-revision");
  await page.evaluate(() => {
    window.dispatchEvent(new Event("blur"));
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(reference).toHaveAttribute("data-authority-revision", revision!);
});

// Wrap the real FontFace/load and Blob APIs. The gate delays or rejects delivery
// of a genuine native load; it does not substitute a fake font or renderer.
async function observeStudioFonts(page: Page, mode: "native" | "hold" | "reject") {
  await page.addInitScript(({ mode }) => {
    const nativeFace = window.FontFace;
    const nativeCreate = URL.createObjectURL.bind(URL);
    const nativeRevoke = URL.revokeObjectURL.bind(URL);
    const nativeNow = performance.now.bind(performance);
    const faces: any[] = [], blobs: any[] = [], hashes: Promise<unknown>[] = [];
    let shift = 0;
    Object.defineProperty(performance, "now", { value: () => nativeNow() + shift });
    URL.createObjectURL = blob => {
      const url = nativeCreate(blob);
      if (blob.type === "font/woff2") {
        if (blobs.length >= 8) throw Error("font observation bound");
        const row: any = { url, revoked: false, sha256: null }; blobs.push(row);
        hashes.push(blob.arrayBuffer().then(bytes => crypto.subtle.digest("SHA-256", bytes))
          .then(bytes => row.sha256 = Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("")));
      }
      return url;
    };
    URL.revokeObjectURL = url => {
      nativeRevoke(url); for (const row of blobs) if (row.url === url) row.revoked = true;
    };
    window.FontFace = class extends nativeFace {
      constructor(family: string, source: ConstructorParameters<typeof nativeFace>[1], descriptors?: FontFaceDescriptors) {
        super(family, source, descriptors);
        if (faces.length >= 8) throw Error("font observation bound");
        const row: any = { face: this, nativeLoaded: false, release: null }; faces.push(row);
        const load = this.load.bind(this);
        this.load = () => load().then(face => {
          row.nativeLoaded = true;
          if (mode === "reject") throw Error("controlled Noto load diagnostic");
          if (mode === "hold") return new Promise<FontFace>(resolve => { row.release = () => resolve(face); });
          return face;
        });
      }
    };
    (window as any).__studioFonts = {
      release: async (index: number) => {
        faces[index].release();
        // Observe after native promise reactions, not a premature absent sample.
        await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      },
      expire: () => { shift += 6000; },
      disposalSnapshot: () => ({ present: faces.filter(row => document.fonts.has(row.face)).length,
        allRevoked: blobs.every(row => row.revoked) }),
      snapshot: async () => {
        await Promise.all(hashes);
        return { faces: faces.map(row => ({ nativeLoaded: row.nativeLoaded, present: document.fonts.has(row.face),
          status: row.face.status, family: row.face.family, releasable: row.release !== null })), blobs };
      }
    };
  }, { mode });
}
const studioFontSnapshot = (page: Page) => page.evaluate(() => (window as any).__studioFonts.snapshot());
const notoText = (page: Page) => page.locator("#svg-authoring-studio svg text").filter({ hasText: "Offline Noto" });

async function expectMountedNoto(page: Page) {
  await expect(notoText(page)).toHaveCount(1);
  await expect(notoText(page)).toBeVisible();
  await expect(page.locator('#svg-authoring-studio style[data-fsgg-font-id="noto-sans-latin-400"]')).toHaveCount(0);
  expect(await notoText(page).evaluate(element => getComputedStyle(element).fontFamily)).toContain("Noto Sans");
  const loaded = await page.evaluate(async () => {
    const faces = await document.fonts.load('16px "Noto Sans"', "Offline Noto");
    const canvas = document.createElement("canvas"), context = canvas.getContext("2d")!;
    context.font = '16px "Noto Sans"'; context.fillText("Offline Noto", 0, 20);
    return { loaded: faces.length, available: document.fonts.check('16px "Noto Sans"', "Offline Noto"),
      painted: context.getImageData(0, 0, canvas.width, canvas.height).data.some(value => value !== 0) };
  });
  expect(loaded.loaded).toBeGreaterThan(0); expect(loaded.available).toBe(true); expect(loaded.painted).toBe(true);
  const proof = await studioFontSnapshot(page);
  expect(proof.faces.filter((f: any) => f.present)).toHaveLength(1);
  expect(proof.blobs.at(-1).sha256).toBe("09aee8065d25508f23a4c3d92cd777ac869c52d93fd868a88f025d888a7937d6");
  expect(proof.blobs.at(-1).revoked).toBe(false);
}

test("Studio awaits genuine Noto readiness and retains the mounted font through replacement and redo", async ({ page }, testInfo) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  await observeStudioFonts(page, "native");
  await page.goto("http://127.0.0.1:5200/");
  const verify = page.getByRole("button", { name: "Verify Noto text", exact: true });
  await verify.click();
  await expect(page.locator("#generated-scene-status")).toHaveText("Verified Noto text exported and reopened offline");
  await expectMountedNoto(page);
  await verify.click();
  await expect.poll(async () => (await studioFontSnapshot(page)).faces.length).toBe(2);
  await expect.poll(async () => (await studioFontSnapshot(page)).faces[0].present).toBe(false);
  await expectMountedNoto(page); // Repeated verification replaces rather than duplicates text/resource.
  await page.getByRole("button", { name: "Start blank game", exact: true }).click();
  await expect(notoText(page)).toHaveCount(0);
  await expect.poll(async () => (await studioFontSnapshot(page)).faces.some((f: any) => f.present)).toBe(false);
  expect((await studioFontSnapshot(page)).blobs.every((b: any) => b.revoked)).toBe(true);
  await page.getByRole("button", { name: "Undo scene change", exact: true }).click();
  await expect(page.locator("#generated-scene-status")).toHaveText("Restored Noto text font ready");
  await expectMountedNoto(page);
  await page.getByRole("button", { name: "Redo scene change", exact: true }).click();
  await expect(notoText(page)).toHaveCount(0);
  await expect.poll(async () => (await studioFontSnapshot(page)).faces.some((f: any) => f.present)).toBe(false);
  await page.getByRole("button", { name: "Undo scene change", exact: true }).click();
  await expect(page.locator("#generated-scene-status")).toHaveText("Restored Noto text font ready");
  await expectMountedNoto(page);
  await testInfo.attach("genuine-mounted-font-lifetime", { body: Buffer.from(JSON.stringify(await studioFontSnapshot(page))), contentType: "application/json" });
});

test("Studio does not announce or mount Noto before native readiness is delivered", async ({ page }) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  await observeStudioFonts(page, "hold"); await page.goto("http://127.0.0.1:5200/");
  const before = await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot().contentHash);
  await page.getByRole("button", { name: "Verify Noto text", exact: true }).click();
  await expect.poll(async () => (await studioFontSnapshot(page)).faces[0]?.releasable).toBe(true);
  await expect(page.locator("#generated-scene-status")).toHaveText("Loading verified Noto font");
  await expect(notoText(page)).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot().contentHash)).toBe(before);
  await page.evaluate(() => (window as any).__studioFonts.release(0));
  await expect(page.locator("#generated-scene-status")).toHaveText("Verified Noto text exported and reopened offline");
  await expectMountedNoto(page);
});

test("Studio reports a font diagnostic without committing text and disposes the failed activation", async ({ page }) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  await observeStudioFonts(page, "reject"); await page.goto("http://127.0.0.1:5200/");
  const before = await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot().contentHash);
  await page.getByRole("button", { name: "Verify Noto text", exact: true }).click();
  await expect(page.locator("#generated-scene-status")).toContainText("Noto font load failed: controlled Noto load diagnostic");
  await expect(notoText(page)).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).svgGeneratedStudio.snapshot().contentHash)).toBe(before);
  const proof = await studioFontSnapshot(page); expect(proof.faces[0].present).toBe(false); expect(proof.blobs[0].revoked).toBe(true);
});

for (const cancellation of ["timeout", "replacement"] as const) {
  test(`Studio ${cancellation} prevents a late genuine font load from mounting or leaking`, async ({ page }) => {
    test.skip(!hasStudio, "selected composition has no Studio");
    await observeStudioFonts(page, "hold"); await page.goto("http://127.0.0.1:5200/");
    await page.getByRole("button", { name: "Verify Noto text", exact: true }).click();
    await expect.poll(async () => (await studioFontSnapshot(page)).faces[0]?.releasable).toBe(true);
    if (cancellation === "timeout") {
      await page.evaluate(() => (window as any).__studioFonts.expire());
      await expect(page.locator("#generated-scene-status")).toContainText("Noto font readiness timed out");
    } else await page.getByRole("button", { name: "Start blank game", exact: true }).click();
    const status = await page.locator("#generated-scene-status").textContent();
    await page.evaluate(() => (window as any).__studioFonts.release(0));
    await expect(notoText(page)).toHaveCount(0);
    await expect(page.locator("#generated-scene-status")).toHaveText(status!);
    await expect.poll(async () => (await studioFontSnapshot(page)).faces[0].present).toBe(false);
    expect((await studioFontSnapshot(page)).blobs[0].revoked).toBe(true);
  });
}

test("Studio stale font completion cannot replace or cancel a newer activation", async ({ page }) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  await observeStudioFonts(page, "hold"); await page.goto("http://127.0.0.1:5200/");
  const verify = page.getByRole("button", { name: "Verify Noto text", exact: true });
  await verify.click();
  await expect.poll(async () => (await studioFontSnapshot(page)).faces[0]?.releasable).toBe(true);
  await verify.click();
  await expect.poll(async () => (await studioFontSnapshot(page)).faces[1]?.releasable).toBe(true);
  await page.evaluate(() => (window as any).__studioFonts.release(0));
  await expect(page.locator("#generated-scene-status")).toHaveText("Loading verified Noto font");
  await expect(notoText(page)).toHaveCount(0);
  expect((await studioFontSnapshot(page)).faces.some((f: any) => f.present)).toBe(false);
  await page.evaluate(() => (window as any).__studioFonts.release(1));
  await expect(page.locator("#generated-scene-status")).toHaveText("Verified Noto text exported and reopened offline");
  await expectMountedNoto(page);
});

test("Studio unload releases its mounted native font and Blob", async ({ page }) => {
  test.skip(!hasStudio, "selected composition has no Studio");
  const disposed: { present: number; allRevoked: boolean }[] = [];
  await page.exposeBinding("reportStudioFontDisposal", (_source, proof) => { disposed.push(proof); });
  await observeStudioFonts(page, "native"); await page.goto("http://127.0.0.1:5200/");
  await page.getByRole("button", { name: "Verify Noto text", exact: true }).click();
  await expect(page.locator("#generated-scene-status")).toHaveText("Verified Noto text exported and reopened offline");
  await expectMountedNoto(page);
  // Register after the product's own unload listener, then observe real page close.
  await page.evaluate(() => window.addEventListener("beforeunload", () => {
    (window as any).reportStudioFontDisposal((window as any).__studioFonts.disposalSnapshot());
  }));
  const closed = page.waitForEvent("close"); await page.close({ runBeforeUnload: true }); await closed;
  await expect.poll(() => disposed.length).toBe(1);
  expect(disposed[0]).toEqual({ present: 0, allRevoked: true });
});
