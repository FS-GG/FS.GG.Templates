import { expect, test, type Locator, type Page } from "@playwright/test";

// FS.GG.Templates#840: the generated game is PLAYABLE on SVG, Pixi and Babylon. The real game page (`/`, index.html) is
// driven with real pointer and keyboard input against the published authority server: on each backend a move is
// played by a pointer press on a cell, by the keyboard and by the accessible mirror, and the player switches between
// the backends at run time with the game state kept. A move is observed where the game keeps it, in the cell the
// authoritative snapshot puts the player in (the DOM grid's `data-occupant`), not in anything the renderer drew.
//
// Run with the rest of `npm run test:renderers` (build.sh does).

type Backend = "svg" | "pixi" | "babylon";
const backends: Backend[] = ["svg", "pixi", "babylon"];
const cellSize = 20; // Client/Renderers.fs: the 400 x 240 Scene over the 20 x 12 arena

test.setTimeout(180_000);

type Cell = { col: number; row: number };

// A player who disconnects leaves the room, so a test's player does not crowd the next test's.
test.afterEach(async ({ page }) => {
  await page.locator("#disconnect").click({ timeout: 2_000 }).catch(() => undefined);
  await page.waitForTimeout(300);
});

/** Join the room as a new player. Players who left stay for the server's two-minute session lifetime, so a player can
 *  spawn boxed in by the ones earlier journeys left behind: join again (a new player spawns on the next free cell). */
async function openGame(page: Page): Promise<string> {
  page.on("pageerror", (error) => test.info().annotations.push({ type: "pageerror", description: error.message }));
  for (let attempt = 0; attempt < 8; attempt++) {
    await page.goto("/");
    await expect(page.locator("#player-id")).not.toBeEmpty({ timeout: 30_000 });
    const id = (await page.locator("#player-id").textContent()) as string;
    await expect(page.locator(`[data-occupant="${id}"]`)).toHaveCount(1, { timeout: 30_000 });
    // Until the first authoritative snapshot the client knows only itself.
    await expect(page.locator("#status")).toContainText("synchronized", { timeout: 30_000 });
    if ((await neighbourOf(page, await ownCell(page, id))) !== null) {
      test.info().annotations.push({ type: "player", description: id });
      return id;
    }
  }
  throw new Error("every player spawned boxed in");
}

async function ownCell(page: Page, id: string): Promise<Cell> {
  const [col, row] = ((await page.locator(`[data-occupant="${id}"]`).getAttribute("data-cell")) as string).split("-").map(Number);
  return { col, row };
}

async function choose(page: Page, backend: Backend | "grid"): Promise<void> {
  await page.locator("#renderer-backend").selectOption(backend);
  if (backend === "grid") {
    await expect(page.locator("#renderer-stage")).toBeHidden();
    await expect(page.locator("#arena")).toBeVisible();
    await expect(page.locator("#renderer-stage canvas, #renderer-stage svg")).toHaveCount(0);
  } else {
    await expect(page.locator("#arena")).toBeHidden();
    await expect(surface(page, backend)).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("#renderer-backend")).toHaveValue(backend);
  }
}

/** The element a backend draws on, and nothing else is drawing: exactly one backend holds the stage. */
function surface(page: Page, backend: Backend): Locator {
  return page.locator(`#renderer-stage [data-renderer="${backend}"]:not([data-scene-controls])`);
}

async function exactlyOneBackend(page: Page, backend: Backend): Promise<void> {
  for (const other of backends) {
    await expect(page.locator(`#renderer-stage [data-renderer="${other}"]:not([data-scene-controls])`)).toHaveCount(other === backend ? 1 : 0);
  }
}

/** The viewport point at the centre of a cell of the board `backend` draws. The board is unscaled (400 x 240 CSS pixels). */
async function pointOf(page: Page, backend: Backend, cell: Cell): Promise<{ x: number; y: number }> {
  const box = await surface(page, backend).boundingBox();
  expect(box, `${backend} has a box`).not.toBeNull();
  const { x, y, width, height } = box as { x: number; y: number; width: number; height: number };
  expect([width, height], "the board is not CSS-scaled").toEqual([400, 240]);
  return { x: x + cell.col * cellSize + cellSize / 2, y: y + cell.row * cellSize + cellSize / 2 };
}

/** A free cell next to `cell` (players who left linger for a while, so a neighbour can be taken): right, left, below, above. */
async function neighbourOf(page: Page, cell: Cell): Promise<Cell | null> {
  const candidates: Cell[] = [
    { col: cell.col + 1, row: cell.row },
    { col: cell.col - 1, row: cell.row },
    { col: cell.col, row: cell.row + 1 },
    { col: cell.col, row: cell.row - 1 }
  ].filter((c) => c.col >= 0 && c.col < 20 && c.row >= 0 && c.row < 12);
  for (const candidate of candidates) {
    const occupant = await page.locator(`[data-cell="${candidate.col}-${candidate.row}"]`).getAttribute("data-occupant");
    if (occupant === null) return candidate;
  }
  return null;
}
const same = (a: Cell, b: Cell) => a.col === b.col && a.row === b.row;
const label = (cell: Cell, who: string) => `Column ${cell.col + 1}, row ${cell.row + 1}: ${who}`;

function mirror(page: Page, backend: Backend): Locator {
  return page.locator(`#renderer-stage [data-scene-controls][data-renderer="${backend}"]`);
}

/** The id of the cell the mirror says is selected, if any (the game state, as the backend shows it). */
async function mirrorSelection(page: Page, backend: Backend): Promise<string | null> {
  const pressed = mirror(page, backend).locator('button[aria-pressed="true"]');
  const count = await pressed.count();
  expect(count, "at most one selected cell").toBeLessThanOrEqual(1);
  return count === 0 ? null : ((await pressed.first().getAttribute("aria-label")) ?? (await pressed.first().textContent()));
}

async function expectMoved(page: Page, id: string, to: Cell): Promise<void> {
  await expect.poll(async () => same(await ownCell(page, id), to), { timeout: 15_000, message: `the player reaches ${JSON.stringify(to)}` }).toBe(true);
}

async function playByPointer(page: Page, id: string, backend: Backend): Promise<Cell> {
  const from = await ownCell(page, id);
  const to = (await neighbourOf(page, from)) as Cell;
  const point = await pointOf(page, backend, to);
  await page.mouse.click(point.x, point.y);
  await expectMoved(page, id, to);
  // The selection is game state: the backend shows the chosen cell (its mirror button is pressed and the status names it).
  await expect.poll(() => mirrorSelection(page, backend)).toContain(label(to, "empty").slice(0, label(to, "").length));
  return to;
}

for (const backend of backends) {
  test(`${backend}: a move is played by a pointer press on a cell`, async ({ page }) => {
    const id = await openGame(page);
    await choose(page, backend);
    await exactlyOneBackend(page, backend);
    const to = await playByPointer(page, id, backend);
    // The surface stays a focusable application and the status names the selection.
    await expect(surface(page, backend)).toHaveAttribute("role", "application");
    await expect(surface(page, backend)).toHaveAttribute("tabindex", "0");
    await expect(mirror(page, backend).locator("[role=status]")).toContainText(`Column ${to.col + 1}, row ${to.row + 1}`);
  });

  test(`${backend}: a move is played by the keyboard, and Escape clears the selection`, async ({ page }) => {
    const id = await openGame(page);
    await choose(page, backend);
    const from = await ownCell(page, id);
    const to = (await neighbourOf(page, from)) as Cell;
    const index = (cell: Cell) => cell.row * 20 + cell.col;
    await surface(page, backend).focus();
    // Arrows move the focus through the cells in row-major order (the published contract), Enter selects the focused one.
    for (let step = 0; step <= index(to); step++) await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Enter");
    await expectMoved(page, id, to);
    expect(await mirrorSelection(page, backend)).not.toBeNull();
    await page.keyboard.press("Escape");
    await expect.poll(() => mirrorSelection(page, backend)).toBeNull();
    // The player stays where the authority put them: clearing a selection is not a move.
    expect(same(await ownCell(page, id), to)).toBe(true);
  });

  test(`${backend}: a move is played through the accessible mirror`, async ({ page }) => {
    const id = await openGame(page);
    await choose(page, backend);
    const to = (await neighbourOf(page, await ownCell(page, id))) as Cell;
    const button = mirror(page, backend).getByRole("button", { name: new RegExp(`^Column ${to.col + 1}, row ${to.row + 1}:`) });
    await button.focus();
    await page.keyboard.press("Enter");
    await expectMoved(page, id, to);
    await expect(button).toHaveAttribute("aria-pressed", "true");
  });
}

test("the player switches between the backends and the DOM grid at run time with the game state kept", async ({ page }) => {
  const id = await openGame(page);
  let selected: string | null = null;

  // svg, pixi, babylon, svg, babylon, pixi: a move on each, then back to the grid.
  for (const backend of [...backends, "svg", "babylon", "pixi"] as Backend[]) {
    await choose(page, backend);
    await exactlyOneBackend(page, backend);
    // What the previous backend showed is what this one shows now: the player's cell and the selection.
    if (selected !== null) expect(await mirrorSelection(page, backend)).toBe(selected);
    const to = await playByPointer(page, id, backend);
    selected = await mirrorSelection(page, backend);
    expect(selected).not.toBeNull();
    expect(same(await ownCell(page, id), to)).toBe(true);
  }

  await choose(page, "grid");
  // The grid is the same game: the cell the last backend moved the player to is the one it shows them in.
  const final = await ownCell(page, id);
  await expect(page.locator(`[data-cell="${final.col}-${final.row}"]`)).toHaveAttribute("data-occupant", id);
  await choose(page, "svg");
  expect(await mirrorSelection(page, "svg")).toBe(selected);
});

// Negative controls: the assertions above are what tell a played move from no move.
test("a press outside the board, and on the DOM grid's hidden twin, plays nothing", async ({ page }) => {
  const id = await openGame(page);
  for (const backend of backends) {
    await choose(page, backend);
    const before = await ownCell(page, id);
    const box = (await surface(page, backend).boundingBox()) as { x: number; y: number; width: number; height: number };
    await page.mouse.click(box.x + box.width + 12, box.y + box.height / 2); // right of the board
    await page.mouse.click(box.x + box.width / 2, box.y + box.height + 12); // below it
    await page.waitForTimeout(1500); // longer than a server tick: a stray move would have arrived
    expect(same(await ownCell(page, id), before), `${backend}: the player did not move`).toBe(true);
    expect(await mirrorSelection(page, backend), `${backend}: nothing is selected`).toBeNull();
  }
});

// The cost of carrying all three renderers in the game page, recorded (FS.GG.Game#774, lazy loading, is not available).
test("the game page's JavaScript is recorded and bounded", async ({ page }, testInfo) => {
  const scripts: { url: string; bytes: number }[] = [];
  page.on("response", async (response) => {
    if (response.request().resourceType() === "script" || /\.js(\?|$)/.test(response.url())) {
      const body = await response.body().catch(() => Buffer.alloc(0));
      scripts.push({ url: new URL(response.url()).pathname, bytes: body.length });
    }
  });
  await page.goto("/");
  await expect(page.locator("#player-id")).not.toBeEmpty({ timeout: 30_000 });
  await page.waitForLoadState("networkidle");
  const total = scripts.reduce((sum, script) => sum + script.bytes, 0);
  await testInfo.attach("game-page-scripts", { body: JSON.stringify({ total, scripts }, null, 2), contentType: "application/json" });
  console.log(`game page JavaScript: ${total} bytes in ${scripts.length} files`);
  expect(total).toBeGreaterThan(100_000);
  expect(total, "the game page's JavaScript stays under 4 MB").toBeLessThan(4_000_000);
});
