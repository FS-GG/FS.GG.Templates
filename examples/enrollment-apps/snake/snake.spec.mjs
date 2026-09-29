import { expect, test } from "@playwright/test";

const board = (page) => page.getByRole("application", { name: /snake play area/i });
const head = (page) => page.locator(".snake-head");
const coord = async (locator) => ({ x: await locator.getAttribute("data-x"), y: await locator.getAttribute("data-y") });

async function openWithClock(page) {
  await page.clock.install();
  await page.goto("./");
  await expect(page.getByRole("heading", { name: "Snake" })).toBeVisible();
}

async function start(page) {
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(board(page)).toBeFocused();
}

async function steps(page, count, milliseconds = 181) {
  for (let index = 0; index < count; index += 1) await page.clock.runFor(milliseconds);
}

test("real entry starts, moves on its timer, eats, grows, and scores", async ({ page }) => {
  await openWithClock(page);
  await expect(head(page)).toHaveAttribute("data-x", "16");
  await expect(page.locator(".food")).toHaveAttribute("data-x", "20");
  await start(page);
  await steps(page, 4);
  await expect(head(page)).toHaveAttribute("data-x", "20");
  await expect(board(page)).toHaveAttribute("data-length", "4");
  await expect(page.locator("#score-value")).toHaveText("10");
});

test("buffers two turns, rejects reversal, and pauses without fast-forward", async ({ page }) => {
  await openWithClock(page);
  await start(page);
  await board(page).press("ArrowDown");
  await board(page).press("ArrowLeft");
  await board(page).press("ArrowRight");
  await expect(board(page)).toHaveAttribute("data-turns", "2");
  await steps(page, 1);
  await expect.poll(() => coord(head(page))).toEqual({ x: "16", y: "10" });
  await steps(page, 1);
  await expect.poll(() => coord(head(page))).toEqual({ x: "15", y: "10" });

  await board(page).press("Space");
  const stopped = await coord(head(page));
  await page.clock.runFor(5_000);
  await expect.poll(() => coord(head(page))).toEqual(stopped);
  await board(page).press("Space");
  await page.clock.runFor(100);
  await expect.poll(() => coord(head(page))).toEqual(stopped);
  await page.clock.runFor(100);
  await expect.poll(() => coord(head(page))).not.toEqual(stopped);

  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await expect(page.locator("#state-value")).toHaveText("Paused");
  const autoPaused = await coord(head(page));
  await page.clock.runFor(2_000);
  await expect.poll(() => coord(head(page))).toEqual(autoPaused);
});

test("loses at a wall, refuses terminal input, then restarts a second run", async ({ page }) => {
  await openWithClock(page);
  await start(page);
  await steps(page, 20);
  await expect(page.locator("#state-value")).toHaveText("Lost");
  const stopped = await coord(head(page));
  await board(page).press("ArrowUp");
  await page.clock.runFor(1_000);
  await expect.poll(() => coord(head(page))).toEqual(stopped);

  await page.getByRole("button", { name: "Restart", exact: true }).click();
  await page.getByRole("button", { name: "Restart", exact: true }).click();
  await expect(page.locator("#state-value")).toHaveText("Ready");
  await expect(head(page)).toHaveAttribute("data-x", "16");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await steps(page, 1);
  await expect(head(page)).toHaveAttribute("data-x", "17");
});

test("public controls reach deterministic food and a self collision", async ({ page }) => {
  await openWithClock(page);
  await start(page);
  await steps(page, 4);
  await expect.poll(() => coord(head(page))).toEqual({ x: "20", y: "9" });
  await expect(page.locator("#score-value")).toHaveText("10");
  await board(page).press("ArrowDown");
  await steps(page, 1, 175);
  await expect.poll(() => coord(head(page))).toEqual({ x: "20", y: "10" });
  await board(page).press("ArrowLeft");
  await steps(page, 10, 175);
  await expect(page.locator("#score-value")).toHaveText("20");
  await expect(board(page)).toHaveAttribute("data-length", "5");

  await board(page).press("ArrowDown");
  await steps(page, 1, 169);
  await board(page).press("ArrowRight");
  await steps(page, 1, 169);
  await board(page).press("ArrowUp");
  await steps(page, 1, 169);
  await expect(page.locator("#state-value")).toHaveText("Lost");
});

test("small viewport retains keyboard-operable controls and a bounded board", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await page.goto("./");
  await expect(board(page)).toBeVisible();
  const bounds = await board(page).boundingBox();
  expect(bounds.width).toBeLessThanOrEqual(360);
  await page.getByRole("button", { name: "Start", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(board(page)).toBeFocused();
  await board(page).press("p");
  await expect(page.locator("#state-value")).toHaveText("Paused");
});

test("retained real-clock smoke proves the live timer is connected", async ({ page }) => {
  await page.goto("./");
  await start(page);
  await expect(head(page)).toHaveAttribute("data-x", "17", { timeout: 1_500 });
});
