import type { Page } from "@playwright/test";

// Shared by renderer-conformance.spec.ts and renderer-journey.spec.ts (GAME-RENDER-ADOPT, FS.GG.Templates#840).

/** The real-input driver the FS.GG.Game.Render conformance kit asks for (`window.__fsggInput`): the kit's `interaction`
 *  section needs trusted pointer and keyboard events and real focus, never synthesised DOM events, so the page asks
 *  the test driver to perform each click, move and key press with Playwright's `page.mouse` and `page.keyboard`.
 *  Call it before `page.goto`. */
export async function installRealInput(page: Page): Promise<void> {
  const keys: Record<string, string> = { " ": "Space" };
  await page.exposeFunction("__fsggInput", async (request: { kind: string; x?: number; y?: number; key?: string }) => {
    switch (request.kind) {
      case "click":
        await page.mouse.click(request.x as number, request.y as number);
        break;
      case "move":
        await page.mouse.move(request.x as number, request.y as number);
        break;
      case "key":
        await page.keyboard.press(keys[request.key as string] ?? (request.key as string));
        break;
      default:
        throw new Error(`unknown input request ${JSON.stringify(request)}`);
    }
  });
}

export type KitVerdict = { verdict: string | null; checks: number; failures: number; lines: string[]; problems: string[] };

/** Open renderers.html (optionally with `?control=...`) and read the kit's verdict from the page. */
export async function runKit(page: Page, query = ""): Promise<KitVerdict> {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => problems.push(`requestfailed: ${request.url()}: ${request.failure()?.errorText ?? "unknown"}`));
  await installRealInput(page);
  await page.goto(`/renderers.html${query}`);
  await page.waitForSelector("body[data-conformance]", { timeout: 220_000 });
  const result = await page.evaluate(() => {
    const pre = document.getElementById("conformance-result");
    return {
      verdict: document.body.getAttribute("data-conformance"),
      checks: Number(pre?.getAttribute("data-checks")),
      failures: Number(pre?.getAttribute("data-failures")),
      lines: (pre?.textContent ?? "").split("\n")
    };
  });
  return { ...result, problems };
}
