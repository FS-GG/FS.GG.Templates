import { expect, test } from "@playwright/test";

// GAME-RENDER-ADOPT-01.10 (FS.GG.Templates#834): the game passes FS.GG.Game.Render's conformance kit on all three
// backends. renderers.html runs `RendererConformance.run` on `Renderers.conformance` (Client/Renderers.fs) against the
// SVG, Pixi and Babylon surfaces in this browser, reading each backend's output back from the page (the SVG DOM, a
// canvas pixel) and its resources from the page's own books (SVG roots, canvases, WebGL contexts, Babylon engines,
// Pixi applications). Client/Conformance.fs lists the game states it runs on.
//
// Run with `npm run test:renderers` after `cd ../Client && npm run build` (build.sh does both).

// The kit's requirements for three backends in FS.GG.Game 0.18.0; a later kit may only add to them.
const kitRequirements = 73;

test("the game's renderers pass the conformance kit on SVG, Pixi and Babylon", async ({ page }, testInfo) => {
  test.setTimeout(240_000);
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => problems.push(`requestfailed: ${request.url()}: ${request.failure()?.errorText ?? "unknown"}`));

  await page.goto("/renderers.html");
  await page.waitForSelector("body[data-conformance]", { timeout: 200_000 });

  const result = await page.evaluate(() => {
    const pre = document.getElementById("conformance-result");
    return {
      verdict: document.body.getAttribute("data-conformance"),
      checks: Number(pre?.getAttribute("data-checks")),
      failures: Number(pre?.getAttribute("data-failures")),
      lines: (pre?.textContent ?? "").split("\n")
    };
  });

  // The kit's own count and every line it reported, kept with the run.
  console.log(`renderer conformance: ${result.checks} checks, ${result.failures} failures`);
  await testInfo.attach("conformance-report", { body: result.lines.join("\n"), contentType: "text/plain" });

  const failed = result.lines.filter((line) => line.startsWith("FAIL "));
  expect(failed, `failed checks:\n${failed.join("\n")}`).toEqual([]);
  expect(result.failures).toBe(0);
  expect(result.verdict).toBe("pass");

  // The kit actually ran: every section, on every backend, plus this page's own four checks (the kit ran its requirements, the stage is empty afterwards, the start path).
  expect(result.checks).toBeGreaterThanOrEqual(kitRequirements + 4);
  for (const section of ["subject", "registry", "round-trip", "switch", "dispose", "late failure", "present failure"]) {
    expect(result.lines.some((line) => line.startsWith(`PASS kit: ${section}`)), `no passing ${section} check`).toBe(true);
  }
  for (const backend of ["svg", "pixi", "babylon"]) {
    expect(result.lines.some((line) => line.startsWith("PASS kit: round-trip") && line.includes(backend)), `no passing round-trip check on ${backend}`).toBe(true);
  }
  expect(result.lines).toContain("PASS start: offers all three backends and switches at runtime with the state kept");
  expect(problems).toEqual([]);
});
