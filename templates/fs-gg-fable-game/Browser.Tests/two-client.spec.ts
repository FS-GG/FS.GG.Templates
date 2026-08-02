import { expect, test } from "@playwright/test";

// The Playwright two-client scenario #348's acceptance names: two independent browser
// *contexts* (not two tabs sharing storage/cookies -- two genuinely separate clients,
// each with its own bootstrap identity), exercising one plain-HTTP typed
// request/response call (the bootstrap fetch each page performs on load) and one
// SignalR real-time flow (client A's input, broadcast to client B as an authoritative
// snapshot) end to end against the real published server.
test("two independent browser contexts see each other's authoritative moves over SignalR", async ({ browser }) => {
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  try {
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

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

    // Client A drives one authoritative move: a click dispatches CellClicked, which
    // sends a SignalR "input" message; the server (RoomAuthority, GameHub) is the sole
    // authority that decides whether it is applied and broadcasts the resulting
    // snapshot to the whole room, including client B.
    await pageA.locator(`[data-cell="${targetCol}-${targetRow}"]`).click();

    // Client B never talked to client A directly -- this assertion only passes if the
    // server's SignalR broadcast actually reached client B's independent connection.
    await expect(pageB.locator(`[data-occupant="${playerIdA}"]`)).toHaveAttribute("data-cell", `${targetCol}-${targetRow}`);
    // The move is authoritative, so client A's own view reflects the same committed
    // position too (not merely its own optimistic preview).
    await expect(pageA.locator(`[data-occupant="${playerIdA}"]`)).toHaveAttribute("data-cell", `${targetCol}-${targetRow}`);
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
