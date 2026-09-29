import { expect, test } from "@playwright/test";

let browserErrors;

test.beforeEach(async ({ page }) => {
  browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  await page.goto("/tic-tac-toe/");
});

test.afterEach(() => {
  expect(browserErrors).toEqual([]);
});

function cell(page, index) {
  const row = Math.floor(index / 3) + 1;
  const column = (index % 3) + 1;
  return page.getByRole("button", { name: new RegExp(`Row ${row}, column ${column}`) });
}

async function playByPointer(page, indices) {
  for (const index of indices) await cell(page, index).click();
}

test("pointer players can win as X and O, refused moves preserve the board, and restart resets focus", async ({ page }) => {
  const status = page.getByRole("status");
  const restart = page.getByRole("button", { name: "Restart" });
  await expect(status).toHaveText("X to play.");
  await expect(cell(page, 0)).toHaveAccessibleName("Row 1, column 1, empty");

  await cell(page, 4).click();
  await expect(status).toHaveText("O to play.");
  await restart.click();
  await expect(status).toHaveText("X to play.");
  await expect(cell(page, 0)).toBeFocused();

  await cell(page, 0).click();
  await expect(cell(page, 0)).toHaveAccessibleName("Row 1, column 1, X");
  const afterFirstMove = await page.locator("[data-cell]").allTextContents();
  await cell(page, 0).press("Enter");
  expect(await page.locator("[data-cell]").allTextContents()).toEqual(afterFirstMove);
  await playByPointer(page, [3, 1, 4, 2]);
  await expect(status).toHaveText("X wins!");

  const afterWin = await page.locator("[data-cell]").allTextContents();
  await cell(page, 8).press("Space");
  expect(await page.locator("[data-cell]").allTextContents()).toEqual(afterWin);
  await expect(cell(page, 8)).toHaveAttribute("aria-disabled", "true");

  await restart.click();
  await expect(cell(page, 0)).toBeFocused();
  await playByPointer(page, [0, 3, 1, 4, 8, 5]);
  await expect(status).toHaveText("O wins!");
  await expect(cell(page, 5)).toHaveAccessibleName("Row 2, column 3, O");
});

test("a complete keyboard-only game draws and remains usable at 320 pixels", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  await page.keyboard.press("Tab");
  await expect(cell(page, 0)).toBeFocused();
  expect(await cell(page, 0).evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe("none");

  let current = 0;
  const moves = [0, 1, 2, 4, 3, 5, 7, 6, 8];
  for (const [moveNumber, target] of moves.entries()) {
    while (current < target) {
      await page.keyboard.press("Tab");
      current += 1;
    }
    while (current > target) {
      await page.keyboard.press("Shift+Tab");
      current -= 1;
    }
    await page.keyboard.press(moveNumber % 2 === 0 ? "Enter" : "Space");
  }

  await expect(page.getByRole("status")).toHaveText("Draw game.");
  await expect(page.locator("[data-cell]:not(:empty)")).toHaveCount(9);
});
