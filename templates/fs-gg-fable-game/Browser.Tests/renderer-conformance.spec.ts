import { expect, test } from "@playwright/test";
import { runKit } from "./renderer-support";

// GAME-RENDER-ADOPT-01.10 and #840: the game passes FS.GG.Game.Render's conformance kit on all three backends,
// including its `interaction` section. renderers.html runs `RendererConformance.run` on `Renderers.conformance`
// (Client/Renderers.fs) against the SVG, Pixi and Babylon surfaces in this browser, reading each backend's output back
// from the page (the SVG DOM, a canvas pixel) and its resources from the page's own books (SVG roots, canvases, WebGL
// contexts, Babylon engines, Pixi applications). The interaction section is driven with real pointer and keyboard input
// through the test driver (renderer-support.ts). Client/Conformance.fs lists the game states it runs on.
//
// Run with `npm run test:renderers` after `cd ../Client && npm run build` (build.sh does both).

// The kit's requirements for three backends in FS.GG.Game 0.18.0: 73 without the `interaction` section and 110 with it
// (the reference game's run); a later kit may only add to them.
const kitRequirements = 110;

test.setTimeout(300_000);

test("the game's renderers pass the conformance kit, interaction included, on SVG, Pixi and Babylon", async ({ page }, testInfo) => {
  const result = await runKit(page);

  // The kit's own count and every line it reported, kept with the run.
  console.log(`renderer conformance: ${result.checks} checks, ${result.failures} failures`);
  await testInfo.attach("conformance-report", { body: result.lines.join("\n"), contentType: "text/plain" });

  const failed = result.lines.filter((line) => line.startsWith("FAIL "));
  expect(failed, `failed checks:\n${failed.join("\n")}`).toEqual([]);
  expect(result.failures).toBe(0);
  expect(result.verdict).toBe("pass");

  // The kit actually ran: every section, on every backend, plus this page's own four checks (the kit ran its requirements,
  // the stage is empty afterwards, the start path).
  expect(result.checks).toBeGreaterThanOrEqual(kitRequirements + 4);
  for (const section of ["subject", "registry", "round-trip", "switch", "dispose", "late failure", "present failure", "interaction"]) {
    expect(result.lines.some((line) => line.startsWith(`PASS kit: ${section}`)), `no passing ${section} check`).toBe(true);
  }
  for (const backend of ["svg", "pixi", "babylon"]) {
    expect(result.lines.some((line) => line.startsWith("PASS kit: round-trip") && line.includes(backend)), `no passing round-trip check on ${backend}`).toBe(true);
    expect(result.lines.some((line) => line.startsWith(`PASS kit: interaction ${backend}`)), `no passing interaction check on ${backend}`).toBe(true);
  }
  expect(result.lines).toContain("PASS start: offers all three backends and switches at runtime with the state kept");
  expect(result.problems).toEqual([]);
});

// Negative control: the same objects with a selection rule that ignores every request. The kit must refuse it on every
// backend, so a pass above is not the kit passing anything.
test("the kit's interaction section refuses a game whose selection rule ignores requests", async ({ page }) => {
  const result = await runKit(page, "?control=ignore-selection");
  expect(result.verdict).toBe("fail");
  const failed = result.lines.filter((line) => line.startsWith("FAIL "));
  for (const backend of ["svg", "pixi", "babylon"]) {
    expect(failed.some((line) => line.startsWith(`FAIL kit: interaction ${backend}`)), `interaction on ${backend} did not fail`).toBe(true);
  }
  // Nothing outside the interaction section regressed: the other sections still pass.
  expect(failed.filter((line) => !line.startsWith("FAIL kit: interaction")), "only interaction checks fail").toEqual([]);
});
