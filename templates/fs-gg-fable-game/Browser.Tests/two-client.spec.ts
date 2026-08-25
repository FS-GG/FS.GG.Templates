import { expect, test, type Page, type TestInfo } from "@playwright/test";

type BrowserDiagnostic = { kind: "console" | "pageerror" | "requestfailed"; detail: string };

const expectedConsolePatterns = [
  /^info: \[.+] Information: Normalizing '\/hub\/game' to 'http:\/\/127\.0\.0\.1:5100\/hub\/game'\.$/,
  /^info: \[.+] Information: WebSocket connected to ws:\/\/127\.0\.0\.1:5100\/hub\/game\?id=.+\.$/
];

function observeDiagnostics(page: Page, diagnostics: BrowserDiagnostic[], expectedConsole: string[]): void {
  page.on("console", message => {
    const detail = `${message.type()}: ${message.text()}`;
    if (expectedConsolePatterns.some(pattern => pattern.test(detail))) expectedConsole.push(detail);
    else diagnostics.push({ kind: "console", detail });
  });
  page.on("pageerror", error => diagnostics.push({ kind: "pageerror", detail: error.message }));
  page.on("requestfailed", request => diagnostics.push({
    kind: "requestfailed",
    detail: `${request.method()} ${request.url()}: ${request.failure()?.errorText ?? "unknown failure"}`
  }));
}

async function attachDiagnostics(testInfo: TestInfo, diagnostics: BrowserDiagnostic[], expectedConsole: string[]): Promise<void> {
  await testInfo.attach("browser-diagnostics", {
    body: Buffer.from(JSON.stringify({ diagnostics, expectedConsole }, null, 2)),
    contentType: "application/json"
  });
}

// The Playwright two-client scenario #348's acceptance names: two independent browser
// *contexts* (not two tabs sharing storage/cookies -- two genuinely separate clients,
// each with its own bootstrap identity), exercising one plain-HTTP typed
// request/response call (the bootstrap fetch each page performs on load) and one
// SignalR real-time flow (client A's input, broadcast to client B as an authoritative
// snapshot) end to end against the real published server.
test("two keyboard-driven browser contexts see each other's authoritative moves over SignalR", async ({ browser, request }, testInfo) => {
  const diagnostics: BrowserDiagnostic[] = [];
  const expectedConsole: string[] = [];
  const preflight = await request.get("/");
  expect(preflight.status()).toBe(200);
  expect(preflight.headers()["content-type"]).toContain("text/html");
  await testInfo.attach("two-client-preflight", {
    body: Buffer.from(JSON.stringify({ url: preflight.url(), status: preflight.status(), contentType: preflight.headers()["content-type"] })),
    contentType: "application/json"
  });
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  try {
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();
    observeDiagnostics(pageA, diagnostics, expectedConsole);
    observeDiagnostics(pageB, diagnostics, expectedConsole);

    await pageA.goto("/");
    await pageB.goto("/");

    // `#player-id` is populated as soon as the plain-HTTP bootstrap call resolves.
    await expect(pageA.locator("#player-id")).not.toBeEmpty();
    await expect(pageB.locator("#player-id")).not.toBeEmpty();
    const playerIdA = await pageA.locator("#player-id").textContent();
    const playerIdB = await pageB.locator("#player-id").textContent();
    expect(playerIdA).toBeTruthy();
    expect(playerIdB).toBeTruthy();
    expect(playerIdA).not.toEqual(playerIdB);

    // A player's own cell only renders once the server's connect-time resync
    // snapshot (over SignalR) has been received and applied -- so this is the
    // SignalR-leg proof, independent of the HTTP-leg proof above.
    await expect(pageA.locator(`[data-occupant="${playerIdA}"]`)).toBeVisible();
    await expect(pageB.locator(`[data-occupant="${playerIdB}"]`)).toBeVisible();
    await expect(pageA.locator(`[data-occupant="${playerIdB}"]`)).toBeVisible();
    await expect(pageB.locator(`[data-occupant="${playerIdA}"]`)).toBeVisible();

    // Each context also renders its own player as "self" and the other as "other" --
    // proof the two contexts are genuinely independent identities, not one session
    // observed twice.
    await expect(pageA.locator(`[data-occupant="${playerIdA}"]`)).toHaveClass(/self/);
    await expect(pageA.locator(`[data-occupant="${playerIdB}"]`)).toHaveClass(/other/);
    await expect(pageB.locator(`[data-occupant="${playerIdB}"]`)).toHaveClass(/self/);
    await expect(pageB.locator(`[data-occupant="${playerIdA}"]`)).toHaveClass(/other/);
    await expect(pageA.getByRole("status")).toContainText("synchronized");
    await expect(pageA.locator("#presence")).toContainText("Players present: 2");
    const gameGrid = pageA.getByRole("grid", { name: "Game board" });
    await expect(gameGrid).toHaveAttribute("aria-rowcount", "12");
    await expect(gameGrid.getByRole("row")).toHaveCount(12);
    await expect(gameGrid.locator(':scope > [role="row"]')).toHaveCount(12);
    await expect(gameGrid.getByRole("gridcell")).toHaveCount(240);
    for (const row of await gameGrid.getByRole("row").all()) {
      await expect(row.getByRole("gridcell")).toHaveCount(20);
      await expect(row.locator(':scope > [role="gridcell"]')).toHaveCount(20);
    }
    const gridAccessibility = await gameGrid.ariaSnapshot();
    await testInfo.attach("game-grid-accessibility", {
      body: Buffer.from(gridAccessibility),
      contentType: "text/yaml"
    });
    expect(gridAccessibility.split("\n").filter(line => /^- '?row(?:\s|\")/.test(line.trimStart()))).toHaveLength(12);

    const ownCellOnA = pageA.locator(`[data-occupant="${playerIdA}"]`);
    const startCellAttr = await ownCellOnA.getAttribute("data-cell");
    expect(startCellAttr).toBeTruthy();
    const [startCol, startRow] = (startCellAttr as string).split("-").map(Number);
    // Move a row *down*, never sideways: the server assigns spawns row-major starting
    // at row 0, so with exactly two players both start on row 0 in adjacent columns --
    // "one column right" is exactly where the other player may have spawned, and the
    // server (correctly) refuses to move A onto an occupied cell. Moving down is
    // guaranteed unoccupied regardless of which context happened to bootstrap first.
    const targetCol = startCol;
    const targetRow = startRow + 1;

    // Client A drives one authoritative move through the keyboard surface: focus plus
    // Enter dispatches CellClicked, which
    // sends a SignalR "input" message; the server (RoomAuthority, GameHub) is the sole
    // authority that decides whether it is applied and broadcasts the resulting
    // snapshot to the whole room, including client B.
    const targetCell = pageA.locator(`[data-cell="${targetCol}-${targetRow}"]`);
    await ownCellOnA.focus();
    await ownCellOnA.press("ArrowDown");
    await expect(targetCell).toBeFocused();
    await expect(targetCell).toHaveAttribute("aria-label", /empty/);
    await targetCell.press("Enter");

    // Client B never talked to client A directly -- this assertion only passes if the
    // server's SignalR broadcast actually reached client B's independent connection.
    await expect(pageB.locator(`[data-occupant="${playerIdA}"]`)).toHaveAttribute("data-cell", `${targetCol}-${targetRow}`);
    // The move is authoritative, so client A's own view reflects the same committed
    // position too (not merely its own optimistic preview).
    await expect(pageA.locator(`[data-occupant="${playerIdA}"]`)).toHaveAttribute("data-cell", `${targetCol}-${targetRow}`);
    await expect(pageA.locator("#arena")).toHaveAttribute("data-grid-cell-count", "240");
    await expect(pageA.locator("#arena")).toHaveAttribute("data-grid-build-count", "1");
  } finally {
    await attachDiagnostics(testInfo, diagnostics, expectedConsole);
    await contextA.close();
    await contextB.close();
  }
  expect(expectedConsole.filter(message => message.includes("Normalizing"))).toHaveLength(2);
  expect(expectedConsole.filter(message => message.includes("WebSocket connected"))).toHaveLength(2);
  expect(diagnostics, "unexpected browser diagnostics").toEqual([]);
});
