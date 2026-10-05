import { test, expect, type Page } from "@playwright/test";
import { existsSync } from "node:fs";

const candidate = existsSync("../SvgFoundation/Examples/SoldierReference/reference.json")
  && process.env.FsGgExternalReferenceCandidate === "true";
type Soldier = { id: string; x: number; y: number; facing: number; health: number; faction: string; pose: string };
type State = { revision: number; definitionRevision: number; soldiers: Soldier[] };
const state = async (page: Page): Promise<State> => JSON.parse(await page.locator("#soldier-reference-state").textContent() ?? "null");
const control = (page: Page, name: string) => page.locator("#soldier-reference").getByRole("button", { name, exact: true });
async function mount(page: Page) {
  await page.goto("/");
  await expect(page.locator("#soldier-reference")).toHaveCount(0);
  await page.getByRole("button", { name: "Mount soldier reference", exact: true }).click();
  await expect(page.locator("#soldier-reference")).toHaveAttribute("data-world-count", "100");
  await expect(page.locator("#soldier-reference svg")).toHaveCount(1);
}
async function select(page: Page, id: string) {
  await page.locator(`[data-soldier-id="${id}"]`).click();
  await expect(page.locator("#soldier-reference")).toHaveAttribute("data-selected", id);
}

test("soldier reference actual entry composes local authority and equivalent accessible commands", async ({ page }) => {
  test.skip(!candidate, "requires explicit packed producer candidate");
  await mount(page);
  const root = page.locator("#soldier-reference");
  await select(page, "soldier-0000");
  const before = await state(page);
  await page.evaluate(() => {
    (window as any).__soldierNodes = {
      definition: document.querySelector("#soldier-reference symbol"),
      instance: document.querySelector('[data-fsgg-element-id="soldier-0000-art"]'),
      untouched: document.querySelector('[data-fsgg-element-id="soldier-0001-art"]'),
      roster: document.querySelector('[data-soldier-id="soldier-0001"]')
    };
  });
  await root.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(async () => (await state(page)).soldiers[0].x).toBe(before.soldiers[0].x + 16);
  const moved = await state(page);
  expect(moved.soldiers[0].facing).toBe(before.soldiers[0].facing + 5);
  expect(moved.soldiers.slice(1)).toEqual(before.soldiers.slice(1));
  expect(await page.evaluate(() => {
    const old = (window as any).__soldierNodes;
    return old.definition === document.querySelector("#soldier-reference symbol")
      && old.instance === document.querySelector('[data-fsgg-element-id="soldier-0000-art"]')
      && old.untouched === document.querySelector('[data-fsgg-element-id="soldier-0001-art"]')
      && old.roster === document.querySelector('[data-soldier-id="soldier-0001"]');
  })).toBe(true);
  await control(page, "Move selected soldier").click();
  await expect.poll(async () => (await state(page)).soldiers[0].x).toBe(before.soldiers[0].x + 32);
  await control(page, "Change selected pose").click();
  await expect.poll(async () => (await state(page)).soldiers[0].pose).toBe("March");
  await control(page, "Change selected appearance").click();
  await expect.poll(async () => (await state(page)).soldiers[0].faction).toBe("Amber");
  expect((await state(page)).soldiers[0].health).toBe(90);
  // Paint-aware document HitTest receives coordinates normalized by the SVG CTM.
  await page.locator('[data-fsgg-element-id="soldier-0001-art"]').click();
  await expect(root).toHaveAttribute("data-selected", "soldier-0001");
  const revision = (await state(page)).revision;
  await control(page, "Focus next soldier").click();
  await control(page, "Pan to offscreen soldiers").click();
  expect((await state(page)).revision).toBe(revision);
  await expect(root).toHaveAttribute("data-focused", "soldier-0002");
  const note = page.getByRole("textbox", { name: "Soldier reference note" });
  await note.focus(); await note.dispatchEvent("compositionstart");
  await note.press("ArrowRight"); await note.fill("兵士 note"); await note.dispatchEvent("compositionend");
  expect((await state(page)).revision).toBe(revision);
  await expect(note).toHaveValue("兵士 note");
  await control(page, "Pause soldiers").click();
  await expect(root).toHaveAttribute("data-status", "Paused");
  await control(page, "Animate 10% soldiers").click();
  const paused = await state(page);
  await page.waitForTimeout(80);
  expect(await state(page)).toEqual(paused);
  await control(page, "Step soldiers").click();
  await expect.poll(async () => (await state(page)).revision).toBe(paused.revision + 1);
  expect((await state(page)).soldiers.filter((soldier, index) => soldier.x !== paused.soldiers[index].x)).toHaveLength(10);
  await control(page, "Resume soldiers").click();
  await expect.poll(async () => (await state(page)).revision).toBeGreaterThan(paused.revision + 1);
  await control(page, "Stop soldier motion").click();
  await control(page, "Reset soldiers").click();
  await expect.poll(async () => (await state(page)).revision).toBe(0);
});

test("soldier reference external snapshots fence stale replies and preserve failed replacements", async ({ page }) => {
  test.skip(!candidate, "requires explicit packed producer candidate");
  await mount(page);
  const root = page.locator("#soldier-reference");
  await control(page, "Use external soldier authority").click();
  await expect(root).toHaveAttribute("data-retired-authority-owned", "0");
  await expect(root).toHaveAttribute("data-retired-svg-connected", "false");
  await expect(root).toHaveAttribute("data-local-owned", "0");
  await control(page, "Connect soldier authority").click();
  await control(page, "Complete soldier snapshot").click();
  await select(page, "soldier-0000");
  await control(page, "Move selected soldier").click();
  await control(page, "Change selected pose").click();
  await expect(root).toHaveAttribute("data-receipts", "1:accepted,2:accepted");
  expect((await state(page)).revision).toBe(0);
  await control(page, "Request soldier burst").click();
  await control(page, "Complete soldier snapshot").click();
  await control(page, "Complete soldier snapshot").click();
  await expect.poll(async () => (await state(page)).revision).toBe(2);
  const baseline = await state(page);
  await control(page, "Request cached soldier snapshot").click();
  await control(page, "Complete soldier snapshot").click();
  expect(await state(page)).toEqual(baseline);
  await expect(root).toHaveAttribute("data-last-outcome", /Rejected/);
  await control(page, "Fail next soldier presentation").click();
  await control(page, "Move selected soldier").click();
  await control(page, "Complete soldier snapshot").click();
  expect(await state(page)).toEqual(baseline);
  await expect(root).toHaveAttribute("data-callback-failure", "true");
  await control(page, "Request soldier burst").click();
  await control(page, "Complete soldier snapshot").click();
  await expect.poll(async () => (await state(page)).revision).toBe(3);
  // Drain the queued duplicate envelope before exercising a distinct replacement failure.
  await control(page, "Complete soldier snapshot").click();
  const accepted = await state(page);
  const exported = await page.locator("#soldier-reference-export").textContent();
  await control(page, "Refuse next soldier replacement").click();
  await control(page, "Move selected soldier").click();
  await control(page, "Complete soldier snapshot").click();
  expect(await state(page)).toEqual(accepted);
  expect(await page.locator("#soldier-reference-export").textContent()).toBe(exported);
  await expect(root).toHaveAttribute("data-refusal", /replacement refused/i);
  await control(page, "Disconnect soldier authority").click();
  await control(page, "Move selected soldier").click();
  await expect(root).toHaveAttribute("data-receipts", /5:rejected/);
  await control(page, "Connect soldier authority").click();
  await control(page, "Complete soldier snapshot").click();
  await control(page, "Move selected soldier").click();
  await control(page, "Replace soldier authority").click();
  await control(page, "Complete oldest soldier snapshot").click();
  expect((await state(page)).revision).toBe(4);
  await control(page, "Complete soldier snapshot").click();
  await expect.poll(async () => (await state(page)).revision).toBe(0);
  await expect(root).toHaveAttribute("data-gateway-epoch", "soldier-epoch-replacement:1");
});

test("soldier reference bounded population churn focus export and disposal journey", async ({ page }) => {
  test.skip(!candidate, "requires explicit packed producer candidate");
  test.setTimeout(60_000);
  await mount(page);
  const root = page.locator("#soldier-reference");
  // Small screening precedes the representative population; requested counts are functional data.
  for (const count of [1, 100, 250, 500, 1000]) {
    await control(page, `Load ${count} soldiers`).click();
    await expect(root).toHaveAttribute("data-world-count", String(count));
    for (const percentage of [10, 50, 100]) {
      const before = await state(page);
      await control(page, `Update ${percentage}% soldiers`).click();
      await expect.poll(async () => (await state(page)).revision).toBe(before.revision + 1);
      const after = await state(page);
      const ranked = before.soldiers.map(soldier => ({ soldier, rank: [...soldier.id].reduce((value, char) => (value * 31 + char.charCodeAt(0)) % 100003, 1729) }))
        .sort((a, b) => a.rank - b.rank || a.soldier.id.localeCompare(b.soldier.id));
      const order = new Map(ranked.map((value, index) => [value.soldier.id, index]));
      expect(after.soldiers).toEqual(before.soldiers.map(soldier => {
        const index = order.get(soldier.id)!;
        return index >= Math.floor(count * percentage / 100) ? soldier : {
          ...soldier, x: soldier.x + 1 + index % 7, y: soldier.y + 1 + index % 5,
          facing: (soldier.facing + 3 + index % 11) % 360, pose: index % 2 === 0 ? "March" : "Kneel"
        };
      }));
    }
  }
  await control(page, "Load 2000 world / 200 visible").click();
  await select(page, "soldier-0000");
  await control(page, "Pan to offscreen soldiers").click();
  await expect(root).toHaveAttribute("data-focused", "soldier-0000");
  await control(page, "Remove selected soldier").click();
  await expect(root).toHaveAttribute("data-focused", "soldier-0001");
  await expect(page.locator('[data-soldier-id="soldier-0001"]')).toBeFocused();
  await control(page, "Spawn soldier").click();
  await expect(root).toHaveAttribute("data-world-count", "2000");
  await control(page, "Revise soldier definitions").click();
  await expect.poll(async () => (await state(page)).definitionRevision).toBe(2);
  const download = page.waitForEvent("download");
  await control(page, "Export full soldier world").click();
  expect((await download).suggestedFilename()).toBe("soldier-world.svg");
  const svg = await page.locator("#soldier-reference-export").textContent() ?? "";
  expect((svg.match(/<use\b/g) ?? []).length).toBe(2000);
  expect((svg.match(/<symbol\b/g) ?? []).length).toBe(6);
  expect(svg).toContain("soldier-1999");
  await page.evaluate(() => {
    (window as any).__soldierDisposed = document.getElementById("soldier-reference");
    (window as any).__soldierDetachedMove = [...document.querySelectorAll<HTMLButtonElement>("#soldier-reference button")]
      .find(button => button.textContent === "Move selected soldier");
  });
  await control(page, "Dispose soldier reference").click();
  await expect(root).toHaveCount(0);
  expect(await page.evaluate(() => {
    const element = (window as any).__soldierDisposed as HTMLElement;
    (window as any).__soldierDetachedMove.click();
    return ["data-input-owned", "data-retired-authority-owned", "data-adapter-listeners", "data-svg-count"]
      .map(attribute => element.getAttribute(attribute));
  })).toEqual(["0", "0", "0", "0"]);
  await page.getByRole("button", { name: "Mount soldier reference", exact: true }).click();
  await expect(root).toHaveAttribute("data-world-count", "100");
  await expect(root.locator("svg")).toHaveCount(1);
});
