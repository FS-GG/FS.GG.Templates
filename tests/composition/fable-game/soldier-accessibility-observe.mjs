// Container-qualified accessible-alternative and focus observer for the actual
// generated soldier player (SVG-COHERENCE-01.5).
//
// Observation routes, all against the real player page served by the generated
// ASP.NET server on the task-owned origin:
//   - the browser accessibility tree via CDP Accessibility.getFullAXTree and
//     getPartialAXTree (what an assistive technology is offered), and
//     Playwright ariaSnapshot (cross-browser structure);
//   - trusted keyboard input through CDP (Tab, Enter, Space), not DOM click();
//   - axe-core as SCREENING only: violations are recorded and never accepted or
//     refused as a conformance claim;
//   - causal controls: each mutation removes one accessible property and the
//     observer must refuse on the exact assertion that depends on it.
//
// This is not physical-input, screen-reader or assistive-technology evidence;
// the Orca observer (soldier-input-orca.py) is the separate AT-SPI/speech route.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const args = process.argv.slice(2);
const option = (name, fallback) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : fallback; };
const baseUrl = option("base-url");
const outPath = option("out");
const moduleRoot = option("module-root", process.env.PLAYWRIGHT_MODULE_ROOT);
const axePath = option("axe");
const family = option("family", "chromium");
const executable = option("executable", process.env.PLAYWRIGHT_EXECUTABLE_PATH);
const mode = option("mode", "all"); // all | observe | controls
const deadlineMs = Number(option("deadline-ms", "420000"));
if (!baseUrl || !outPath || !moduleRoot) throw new Error("--base-url, --out and --module-root are required");
const require = createRequire(path.join(moduleRoot, "noop.cjs"));
const { chromium, firefox, webkit } = require("@playwright/test");
const started = Date.now();
const expired = () => Date.now() - started > deadlineMs;
const entry = new URL("soldier-player/index.html", baseUrl).href;

const COMMANDS = [
  "Select focused soldier", "Focus next soldier", "Focus previous soldier", "Move selected soldier",
  "Change selected pose", "Change selected appearance", "Spawn soldier", "Remove selected soldier",
  "Pan to offscreen soldiers", "Revise soldier definitions", "Export full soldier world", "Dispose soldier reference",
];
const ROSTER_NAME = /^soldier-[\w-]+, (Blue|Amber), (Ready|March|Kneel), health \d+$/;

// ---------- accessibility tree helpers ----------
const prop = (node, name) => (node.properties ?? []).find((p) => p.name === name)?.value?.value;
const roleOf = (node) => node.role?.value ?? "";
const nameOf = (node) => node.name?.value ?? "";
async function fullTree(cdp) {
  const { nodes } = await cdp.send("Accessibility.getFullAXTree");
  const byId = new Map(nodes.map((n) => [n.nodeId, n]));
  const live = nodes.filter((n) => !n.ignored);
  const descendants = (root) => {
    const out = []; const stack = [...(root.childIds ?? [])];
    while (stack.length) { const n = byId.get(stack.pop()); if (!n) continue; out.push(n); stack.push(...(n.childIds ?? [])); }
    return out;
  };
  return { nodes, byId, live, descendants };
}
async function focusedAx(cdp, session) {
  const { result } = await cdp.send("Runtime.evaluate", { expression: "document.activeElement" });
  if (!result.objectId) return null;
  const { nodes } = await cdp.send("Accessibility.getPartialAXTree", { objectId: result.objectId, fetchRelatives: false });
  const node = nodes.find((n) => !n.ignored) ?? nodes[0];
  return node ? { role: roleOf(node), name: nameOf(node), focused: prop(node, "focused") === true, focusable: prop(node, "focusable") === true } : null;
}

// ---------- page helpers ----------
const domActive = (page) => page.evaluate(() => {
  const a = document.activeElement;
  return a ? { tag: a.tagName.toLowerCase(), id: a.id || null, soldier: a.getAttribute("data-soldier-id"), text: (a.textContent || "").trim().slice(0, 120), label: a.getAttribute("aria-label") } : null;
});
const state = (page) => page.evaluate(() => JSON.parse(document.getElementById("soldier-reference-state")?.textContent ?? "null"));
const attr = (page, name) => page.evaluate((n) => document.getElementById("soldier-reference")?.getAttribute(n) ?? null, name);
async function waitFor(page, fn, arg, label, timeout = 10000) {
  try { await page.waitForFunction(fn, arg, { timeout }); } catch (e) { throw new Error(`wait failed: ${label}`); }
}
// Gate waits return false on timeout so a refused control is recorded as a failed
// assertion, never as an observer error.
async function tryWait(page, fn, arg, timeout = 5000) {
  try { await page.waitForFunction(fn, arg, { timeout }); return true; } catch { return false; }
}
async function keyboardActivate(page, name, key = "Enter") {
  const ok = await page.evaluate((n) => {
    const m = [...document.querySelectorAll("#soldier-reference button")].filter((b) => b.textContent === n);
    if (m.length !== 1) return false; m[0].focus(); return document.activeElement === m[0];
  }, name);
  if (!ok) throw new Error(`control not uniquely focusable: ${name}`);
  await page.keyboard.press(key);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0))));
}
async function openPlayer(page, cdp) {
  await page.goto(entry);
  await waitFor(page, () => (document.querySelector("[data-authority-status]")?.getAttribute("data-authority-status") ?? "") === "synchronized", null, "authority synchronized", 30000);
  // The real entry control, activated with trusted keyboard input.
  await page.evaluate(() => document.getElementById("mount-soldier-reference").focus());
  await page.keyboard.press("Enter");
  await waitFor(page, () => document.getElementById("soldier-reference")?.getAttribute("data-world-count") === "100", null, "initial mount");
  await cdp.send("Accessibility.enable");
}

// ---------- assertions: each returns {id, passed, detail} ----------
// `gate` assertions must hold. `finding` assertions record a known open gap in the
// current player (an accessibility improvement the generated source does not yet
// make); they never pass or refuse the run, but a finding that starts to hold is
// reported `resolved` so it can be promoted to a gate rather than silently lost.
const pass = (id, detail, kind) => ({ id, kind, passed: true, detail });
const fail = (id, detail, kind) => ({ id, kind, passed: false, detail });
const rec = (id, ok, detail) => (ok ? pass(id, detail, "gate") : fail(id, detail, "gate"));
const finding = (id, ok, detail) => (ok ? pass(id, detail, "finding") : fail(id, detail, "finding"));

async function observeStructure(page, cdp) {
  const tree = await fullTree(cdp);
  const out = [];
  const panel = tree.live.filter((n) => roleOf(n) === "region" && nameOf(n) === "Equipped soldier reference");
  out.push(rec("panel-region-name", panel.length === 1, { found: panel.length }));
  out.push(rec("panel-focusable", panel.length === 1 && prop(panel[0], "focusable") === true, {}));
  const scope = panel.length === 1 ? tree.descendants(panel[0]).filter((n) => !n.ignored) : [];
  const heading = scope.filter((n) => roleOf(n) === "heading" && nameOf(n) === "Equipped soldier reference" && prop(n, "level") === 2);
  out.push(rec("panel-heading-level-2", heading.length === 1, { found: heading.length }));
  out.push(rec("note-textbox-name", scope.filter((n) => roleOf(n) === "textbox" && nameOf(n) === "Soldier reference note").length === 1, {}));
  const status = scope.filter((n) => roleOf(n) === "status");
  out.push(rec("status-live-polite", status.length >= 1 && status.every((n) => prop(n, "live") === "polite"), { found: status.length, live: status.map((n) => prop(n, "live")) }));
  const buttons = scope.filter((n) => roleOf(n) === "button");
  const roster = buttons.filter((n) => ROSTER_NAME.test(nameOf(n)));
  const commandNodes = buttons.filter((n) => !ROSTER_NAME.test(nameOf(n)));
  const names = commandNodes.map(nameOf);
  const missing = COMMANDS.filter((c) => !names.includes(c));
  out.push(rec("command-buttons-present", missing.length === 0, { missing, commandButtons: names.length }));
  out.push(rec("command-names-unique-nonempty", names.every((n) => n.trim() !== "") && new Set(names).size === names.length, { commandButtons: names.length, unique: new Set(names).size }));
  const disabled = commandNodes.filter((n) => prop(n, "disabled") === true || prop(n, "focusable") !== true).map(nameOf);
  out.push(rec("command-buttons-focusable-enabled", disabled.length === 0, { disabled }));
  const worldCount = Number(await attr(page, "data-world-count"));
  const rosterNames = roster.map(nameOf);
  out.push(rec("roster-alternatives-complete", roster.length === worldCount, { rosterButtons: roster.length, worldCount }));
  out.push(rec("roster-names-unique", new Set(rosterNames).size === rosterNames.length, { unique: new Set(rosterNames).size, total: rosterNames.length }));
  out.push(rec("roster-names-nonempty-descriptive", scope.filter((n) => roleOf(n) === "button" && nameOf(n).trim() === "").length === 0, {}));
  out.push(rec("roster-pressed-state-exposed", roster.length > 0 && roster.every((n) => ["true", "false"].includes(String(prop(n, "pressed")))), {}));
  const group = scope.filter((n) => nameOf(n) === "Soldier roster" && ["group", "list", "region", "navigation", "toolbar", "radiogroup"].includes(roleOf(n)));
  out.push(finding("roster-group-named", group.length === 1, { found: group.length, roles: scope.filter((n) => nameOf(n) === "Soldier roster").map(roleOf) }));
  // Every soldier painted in the SVG has exactly one roster button, and the reverse.
  const canvas = await page.evaluate(() => {
    const svg = document.querySelector("#soldier-reference [data-soldier-canvas] svg");
    if (!svg) return null;
    const art = [...svg.querySelectorAll("[data-fsgg-element-id]")].map((e) => e.getAttribute("data-fsgg-element-id")).filter((id) => /^soldier-.+-art$/.test(id)).map((id) => id.slice(0, -4));
    const roster = [...document.querySelectorAll("#soldier-reference [data-soldier-id]")].map((e) => e.getAttribute("data-soldier-id"));
    const rosterSet = new Set(roster), artSet = new Set(art);
    return { art: artSet.size, roster: rosterSet.size, artWithoutRoster: [...artSet].filter((id) => !rosterSet.has(id)).slice(0, 5), rosterWithoutArt: [...rosterSet].filter((id) => !artSet.has(id)).slice(0, 5) };
  });
  out.push(rec("svg-canvas-has-roster-alternative", canvas !== null && canvas.art > 0 && canvas.art === canvas.roster && canvas.artWithoutRoster.length === 0 && canvas.rosterWithoutArt.length === 0 && roster.length === worldCount, { canvas, axRoster: roster.length }));
  return out;
}

async function observeKeyboard(page, cdp) {
  const out = [];
  // Real Tab traversal from the panel. Every control must be reached by Tab, and
  // the AX-focused node must be the DOM-focused element at every stop.
  await page.evaluate(() => document.getElementById("soldier-reference").focus());
  const visited = []; let syncMismatch = 0; let guard = 0;
  const expectedStops = await page.evaluate(() => [...document.querySelectorAll("#soldier-reference button")].length + 2);
  while (guard++ < expectedStops + 10) {
    await page.keyboard.press("Tab");
    const dom = await domActive(page);
    const inside = await page.evaluate(() => !!document.activeElement?.closest("#soldier-reference"));
    if (!inside) break;
    const ax = await focusedAx(cdp);
    const domName = dom.label ?? dom.text;
    if (!ax || !ax.focused || (ax.name || "") !== domName) syncMismatch++;
    visited.push(dom.soldier ? `roster:${dom.soldier}` : dom.text || dom.label || dom.tag);
  }
  const visitedSet = new Set(visited);
  const unreachedCommands = COMMANDS.filter((c) => !visitedSet.has(c));
  out.push(rec("tab-reaches-every-command", unreachedCommands.length === 0, { unreached: unreachedCommands, stops: visited.length }));
  const rosterTotal = await page.evaluate(() => document.querySelectorAll("#soldier-reference [data-soldier-id]").length);
  const rosterVisited = visited.filter((v) => v.startsWith("roster:")).length;
  out.push(rec("tab-reaches-every-roster-button", rosterVisited === rosterTotal, { visited: rosterVisited, total: rosterTotal }));
  out.push(rec("ax-focus-matches-dom-focus", syncMismatch === 0, { mismatches: syncMismatch, stops: visited.length }));

  // Keyboard-only equivalents of the pointer journey.
  await page.evaluate(() => document.querySelector('#soldier-reference [data-soldier-id="soldier-0000"]').focus());
  await page.keyboard.press("Enter");
  await tryWait(page, () => document.getElementById("soldier-reference").getAttribute("data-selected") === "soldier-0000");
  const before = await state(page);
  const pressedAfter = await page.evaluate(() => document.querySelector('#soldier-reference [data-soldier-id="soldier-0000"]').getAttribute("aria-pressed"));
  out.push(rec("keyboard-select-roster", pressedAfter === "true", { pressed: pressedAfter }));
  {
    const tree = await fullTree(cdp);
    const panel = tree.live.find((n) => roleOf(n) === "region" && nameOf(n) === "Equipped soldier reference");
    const axPressed = panel ? tree.descendants(panel).filter((n) => !n.ignored && roleOf(n) === "button" && ROSTER_NAME.test(nameOf(n)) && String(prop(n, "pressed")) === "true").map(nameOf) : [];
    const domPressed = await page.evaluate(() => [...document.querySelectorAll('#soldier-reference button[aria-pressed="true"]')].map((b) => b.textContent));
    out.push(rec("roster-pressed-matches-dom-after-selection", axPressed.length === 1 && domPressed.length === 1 && axPressed[0] === domPressed[0] && /^soldier-0000, /.test(axPressed[0]), { ax: axPressed, dom: domPressed }));
  }
  await keyboardActivate(page, "Move selected soldier", "Space");
  await tryWait(page, (x) => JSON.parse(document.getElementById("soldier-reference-state").textContent).soldiers[0].x === x, before.soldiers[0].x + 16);
  const afterMove = await state(page);
  out.push(rec("keyboard-command-moves-selected", afterMove.soldiers[0].x === before.soldiers[0].x + 16 && afterMove.soldiers.slice(1).every((s, i) => s.x === before.soldiers[i + 1].x), {}));
  const label = await page.evaluate(() => document.querySelector('#soldier-reference [data-soldier-id="soldier-0000"]').textContent);
  out.push(rec("roster-name-follows-state", /^soldier-0000, /.test(label), { label }));
  const statusText = await page.evaluate(() => document.querySelector("#soldier-reference output[aria-live]").textContent);
  // Remove: focus must transfer to a surviving named control and be announced.
  await keyboardActivate(page, "Remove selected soldier", "Enter");
  await tryWait(page, () => document.getElementById("soldier-reference").getAttribute("data-world-count") === "99");
  const active = await domActive(page);
  const ax = await focusedAx(cdp);
  out.push(rec("removal-focus-transfers-to-survivor", active?.soldier === "soldier-0001" && ax?.focused === true && /^soldier-0001, /.test(ax?.name ?? ""), { active, ax }));
  const live = await page.evaluate(() => document.querySelector("#soldier-reference output[aria-live]").textContent);
  // Written to the live region (DOM text changed). Whether Orca speaks it is gated by the Orca observer.
  out.push(rec("removal-written-to-live-region", /Focused soldier removed/.test(live) && live !== statusText, { live }));
  return out;
}

async function observeChurnAndExport(page, cdp) {
  const out = [];
  await keyboardActivate(page, "Load 2000 world / 200 visible", "Enter");
  await waitFor(page, () => document.getElementById("soldier-reference").getAttribute("data-world-count") === "2000", null, "world 2000");
  await page.evaluate(() => document.querySelector('#soldier-reference [data-soldier-id="soldier-0000"]').focus());
  await page.keyboard.press("Enter");
  await waitFor(page, () => document.getElementById("soldier-reference").getAttribute("data-selected") === "soldier-0000", null, "select in churn");
  await keyboardActivate(page, "Pan to offscreen soldiers", "Enter");
  await keyboardActivate(page, "Remove selected soldier", "Enter");
  await tryWait(page, () => document.getElementById("soldier-reference").getAttribute("data-world-count") === "1999");
  const active = await domActive(page); const ax = await focusedAx(cdp);
  out.push(rec("offscreen-removal-focus-transfers", active?.soldier === "soldier-0001" && ax?.focused === true && /^soldier-0001, /.test(ax?.name ?? ""), { active, ax }));
  await keyboardActivate(page, "Spawn soldier", "Enter");
  await tryWait(page, () => document.getElementById("soldier-reference").getAttribute("data-world-count") === "2000");
  const afterSpawn = await domActive(page);
  out.push(rec("spawn-keeps-focus-on-control", afterSpawn?.text === "Spawn soldier", { afterSpawn }));
  const rosterAfter = await page.evaluate(() => document.querySelectorAll("#soldier-reference [data-soldier-id]").length);
  out.push(rec("roster-follows-churn-world", rosterAfter === 2000, { roster: rosterAfter }));
  // Full-world export by keyboard: the download must complete from a real Enter.
  const download = page.waitForEvent("download", { timeout: 6000 }).catch(() => null);
  await keyboardActivate(page, "Export full soldier world", "Enter");
  const file = await download;
  if (file === null) out.push(rec("keyboard-export-full-world", false, { download: "none" }));
  else {
    const body = fs.readFileSync(await file.path(), "utf8");
    const uses = (body.match(/<use\b/g) ?? []).length;
    out.push(rec("keyboard-export-full-world", file.suggestedFilename() === "soldier-world.svg" && uses === 2000, { filename: file.suggestedFilename(), uses, sha256: crypto.createHash("sha256").update(body).digest("hex") }));
  }
  return out;
}

async function observePopulations(page, cdp) {
  const out = [];
  for (const count of [1, 100, 250, 500, 1000]) {
    await keyboardActivate(page, `Load ${count} soldiers`, "Enter");
    await tryWait(page, (c) => document.getElementById("soldier-reference").getAttribute("data-world-count") === String(c), count, 30000);
    const tree = await fullTree(cdp);
    const panel = tree.live.find((n) => roleOf(n) === "region" && nameOf(n) === "Equipped soldier reference");
    const roster = panel ? tree.descendants(panel).filter((n) => !n.ignored && roleOf(n) === "button" && ROSTER_NAME.test(nameOf(n))) : [];
    const unique = new Set(roster.map(nameOf)).size;
    out.push(rec(`population-${count}-roster-exposed-unique`, roster.length === count && unique === count, { exposed: roster.length, unique }));
  }
  return out;
}

async function observeDisposal(page, cdp) {
  const out = [];
  await keyboardActivate(page, "Dispose soldier reference", "Enter");
  const tree = await fullTree(cdp);
  const stale = tree.live.filter((n) => nameOf(n) === "Equipped soldier reference" || ROSTER_NAME.test(nameOf(n)));
  out.push(rec("disposed-panel-absent-from-ax-tree", stale.length === 0, { stale: stale.length }));
  const active = await domActive(page);
  out.push(finding("disposal-focus-returns-to-entry-control", active?.id === "mount-soldier-reference", { active: active && { tag: active.tag, id: active.id } }));
  return out;
}

async function screenWithAxe(page) {
  await page.addScriptTag({ path: axePath });
  const result = await page.evaluate(async () => {
    const r = await window.axe.run(document.getElementById("soldier-reference"), { resultTypes: ["violations", "incomplete"] });
    return { version: window.axe.version,
      violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
      incomplete: r.incomplete.map((v) => ({ id: v.id, nodes: v.nodes.length })), passes: r.passes.length };
  });
  return result;
}

// ---------- causal controls ----------
// Roster mutations are "sticky": the product re-renders roster text and state on
// every accepted commit, so a one-shot DOM edit could be overwritten before it is
// observed. Each `sticky` function is idempotent and re-applied on every mutation.
const byText = (name) => `[...document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === ${JSON.stringify(name)})`;
const MUTANTS = [
  // phase "structure": accessibility-tree gates only. "keyboard": Tab/focus gates. Others run one journey.
  { name: "remove-panel-accessible-name", phase: "structure", expect: ["panel-region-name"], run: (w) => w.document.getElementById("soldier-reference").removeAttribute("aria-label") },
  { name: "remove-panel-focusability", phase: "structure", expect: ["panel-focusable"], run: (w) => w.document.getElementById("soldier-reference").removeAttribute("tabindex") },
  { name: "demote-panel-heading", phase: "structure", expect: ["panel-heading-level-2"], run: (w) => w.document.querySelector("#soldier-reference h2").setAttribute("aria-level", "3") },
  { name: "remove-note-accessible-name", phase: "structure", expect: ["note-textbox-name"], run: (w) => w.document.querySelector('#soldier-reference input[aria-label]').removeAttribute("aria-label") },
  { name: "silence-live-region", phase: "structure", expect: ["status-live-polite"], run: (w) => w.document.querySelector("#soldier-reference output[aria-live]").setAttribute("aria-live", "off") },
  { name: "hide-command-from-ax-tree", phase: "structure", expect: ["command-buttons-present"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Spawn soldier").setAttribute("aria-hidden", "true"); } },
  { name: "duplicate-command-name", phase: "structure", expect: ["command-names-unique-nonempty"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Focus previous soldier").textContent = "Focus next soldier"; } },
  { name: "disable-command-button", phase: "structure", expect: ["command-buttons-focusable-enabled"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Pause soldiers").disabled = true; } },
  { name: "hide-roster-from-ax-tree", phase: "structure", expect: ["roster-alternatives-complete"], run: (w) => w.document.querySelector('#soldier-reference [aria-label="Soldier roster"]').setAttribute("aria-hidden", "true") },
  { name: "remove-roster-button-name", phase: "structure", expect: ["roster-names-nonempty-descriptive"], sticky: (w) => { const b = w.document.querySelector("#soldier-reference [data-soldier-id]"); if (b && b.textContent !== "") b.textContent = ""; } },
  { name: "duplicate-roster-names", phase: "structure", expect: ["roster-names-unique"], sticky: (w) => { const b = w.document.querySelectorAll("#soldier-reference [data-soldier-id]"); if (b.length > 1 && b[1].textContent !== b[0].textContent) b[1].textContent = b[0].textContent; } },
  { name: "remove-pressed-state", phase: "structure", expect: ["roster-pressed-state-exposed"], sticky: (w) => w.document.querySelectorAll("#soldier-reference [data-soldier-id][aria-pressed]").forEach((b) => b.removeAttribute("aria-pressed")) },
  { name: "drop-last-roster-alternative", phase: "structure", expect: ["roster-alternatives-complete"], sticky: (w) => { const b = w.document.querySelector('#soldier-reference [data-soldier-id="soldier-0099"]'); if (b) b.remove(); } },
  { name: "remove-painted-soldier-art", phase: "structure", expect: ["svg-canvas-has-roster-alternative"], sticky: (w) => { const e = w.document.querySelector('#soldier-reference svg [data-fsgg-element-id="soldier-0005-art"]'); if (e) e.remove(); } },
  { name: "remove-command-from-tab-order", phase: "keyboard", expect: ["tab-reaches-every-command"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Change selected pose").setAttribute("tabindex", "-1"); } },
  { name: "remove-roster-button-from-tab-order", phase: "keyboard", expect: ["tab-reaches-every-roster-button"], sticky: (w) => { const b = w.document.querySelectorAll("#soldier-reference [data-soldier-id]")[3]; if (b && b.getAttribute("tabindex") !== "-1") b.setAttribute("tabindex", "-1"); } },
  { name: "relabel-focused-command-in-ax-tree", phase: "keyboard", expect: ["ax-focus-matches-dom-focus"], run: (w) => { const h = w.document.querySelector("#soldier-reference h2"); h.id = "soldier-heading-control"; [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Spawn soldier").setAttribute("aria-labelledby", "soldier-heading-control"); } },
  { name: "remove-selection-pressed-state", phase: "keyboard", expect: ["keyboard-select-roster", "roster-pressed-matches-dom-after-selection"], sticky: (w) => w.document.querySelectorAll("#soldier-reference [data-soldier-id][aria-pressed]").forEach((b) => b.removeAttribute("aria-pressed")) },
  { name: "block-move-command", phase: "keyboard", expect: ["keyboard-command-moves-selected"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Move selected soldier").addEventListener("click", (e) => e.stopImmediatePropagation(), true); } },
  { name: "drift-roster-label-from-state", phase: "keyboard", expect: ["roster-name-follows-state"], sticky: (w) => { const b = w.document.querySelector('#soldier-reference [data-soldier-id="soldier-0000"]'); if (b && b.textContent !== "unit") b.textContent = "unit"; } },
  { name: "suppress-programmatic-focus-transfer", phase: "keyboard", expect: ["removal-focus-transfers-to-survivor"], armOnRemove: true },
  { name: "clear-live-region-text", phase: "keyboard", expect: ["removal-written-to-live-region"], sticky: (w) => { const o = w.document.querySelector("#soldier-reference output[aria-live]"); if (o && o.textContent !== "") o.textContent = ""; } },
  { name: "suppress-focus-transfer-in-churn", phase: "churn", expect: ["offscreen-removal-focus-transfers"], armOnRemove: true },
  { name: "steal-focus-after-spawn", phase: "churn", expect: ["spawn-keeps-focus-on-control"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Spawn soldier").addEventListener("click", () => setTimeout(() => w.document.activeElement?.blur(), 0)); } },
  { name: "drop-roster-entry-in-churn", phase: "churn", expect: ["roster-follows-churn-world"], sticky: (w) => { const b = w.document.querySelector('#soldier-reference [data-soldier-id="soldier-0500"]'); if (b) b.remove(); } },
  { name: "block-export", phase: "churn", expect: ["keyboard-export-full-world"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Export full soldier world").addEventListener("click", (e) => e.stopImmediatePropagation(), true); } },
  { name: "hide-roster-at-every-population", phase: "populations", expect: [1, 100, 250, 500, 1000].map((n) => `population-${n}-roster-exposed-unique`), run: (w) => w.document.querySelector('#soldier-reference [aria-label="Soldier roster"]').setAttribute("aria-hidden", "true") },
  { name: "block-dispose", phase: "disposal", expect: ["disposed-panel-absent-from-ax-tree"], run: (w) => { [...w.document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Dispose soldier reference").addEventListener("click", (e) => e.stopImmediatePropagation(), true); } },
];

const RESOLUTIONS = [
  { name: "name-the-roster-group", resolves: "roster-group-named", phase: "structure",
    apply: () => document.querySelector('#soldier-reference [aria-label="Soldier roster"]').setAttribute("role", "group") },
  { name: "restore-focus-to-entry-control-on-dispose", resolves: "disposal-focus-returns-to-entry-control", phase: "disposal",
    apply: () => {
      const dispose = [...document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Dispose soldier reference");
      dispose.addEventListener("click", () => setTimeout(() => document.getElementById("mount-soldier-reference").focus(), 0));
    } },
];
const observeDisposalWithFixup = (page, cdp) => observeDisposal(page, cdp);

async function applyMutantAfterSetup(page, mutant) {
  if (mutant.armOnRemove) {
    // `focus()` is also used by the observer's own setup, so suppression is armed
    // only around the product's focus transfer, on the Remove activation.
    await page.evaluate(() => {
      const original = HTMLElement.prototype.focus;
      const remove = [...document.querySelectorAll("#soldier-reference button")].find((b) => b.textContent === "Remove selected soldier");
      remove.addEventListener("click", () => { HTMLElement.prototype.focus = function () {}; setTimeout(() => { HTMLElement.prototype.focus = original; }, 400); }, true);
    });
    return;
  }
  if (mutant.sticky) {
    await page.evaluate(`(() => { const apply = () => (${mutant.sticky.toString()})(window); apply();
      new MutationObserver(apply).observe(document.getElementById("soldier-reference"), { subtree: true, childList: true, characterData: true, attributes: true }); })()`);
    return;
  }
  await page.evaluate(`(${mutant.run.toString()})(window)`);
}

async function withFreshPlayer(browserType, fn) {
  const browser = await browserType.launch({ headless: true, executablePath: family === "chromium" ? executable : undefined, args: family === "chromium" ? ["--force-renderer-accessibility", "--no-sandbox"] : [] });
  try {
    const context = await browser.newContext({ acceptDownloads: true });
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    const cdp = family === "chromium" ? await context.newCDPSession(page) : null;
    return await fn(page, cdp);
  } finally { await browser.close(); }
}

async function runPhase(phase, page, cdp) {
  switch (phase) {
    case "structure": return observeStructure(page, cdp);
    case "keyboard": return observeKeyboard(page, cdp);
    case "churn": return observeChurnAndExport(page, cdp);
    case "populations": return observePopulations(page, cdp);
    case "disposal": return observeDisposal(page, cdp);
    default: throw new Error(`unknown phase ${phase}`);
  }
}
async function runEverything(page, cdp) {
  const results = [];
  for (const phase of ["structure", "keyboard", "churn", "populations", "disposal"]) results.push(...await runPhase(phase, page, cdp));
  return results;
}

const report = { schema: "fsgg.soldier-accessibility-observation/v1", family, entry, startedAt: new Date(started).toISOString(),
  claims: { physicalInput: false, assistiveTechnology: false, axeIsConformanceClaim: false, scope: "container-qualified accessible alternatives and focus in the actual generated player" },
  observe: null, controls: null, screening: null, ariaSnapshot: null, result: "failed" };

try {
  const browserType = { chromium, firefox, webkit }[family];
  if (!browserType) throw new Error(`unsupported family ${family}`);
  if (mode !== "controls") {
    report.observe = await withFreshPlayer(browserType, async (page, cdp) => {
      if (family !== "chromium") {
        await page.goto(entry);
        await waitFor(page, () => (document.querySelector("[data-authority-status]")?.getAttribute("data-authority-status") ?? "") === "synchronized", null, "authority", 30000);
        await page.evaluate(() => document.getElementById("mount-soldier-reference").focus());
        await page.keyboard.press("Enter");
        await waitFor(page, () => document.getElementById("soldier-reference")?.getAttribute("data-world-count") === "100", null, "mount");
        const snapshot = await page.locator("#soldier-reference").ariaSnapshot();
        return { assertions: [], ariaSnapshot: snapshot };
      }
      await openPlayer(page, cdp);
      const assertions = [];
      assertions.push(...await observeStructure(page, cdp));
      report.ariaSnapshot = await page.locator("#soldier-reference").ariaSnapshot();
      report.screening = await screenWithAxe(page);
      assertions.push(...await observeKeyboard(page, cdp));
      assertions.push(...await observeChurnAndExport(page, cdp));
      assertions.push(...await observePopulations(page, cdp));
      assertions.push(...await observeDisposal(page, cdp));
      return { assertions };
    });
  }
  if (family === "chromium" && mode !== "observe") {
    const rows = [];
    // The axe screen itself must be live: an unnamed button is a known violation.
    const axeControl = await withFreshPlayer(chromium, async (page, cdp) => {
      await openPlayer(page, cdp);
      await page.evaluate(() => document.getElementById("soldier-reference").appendChild(document.createElement("button")));
      const result = await screenWithAxe(page);
      return result.violations.some((v) => v.id === "button-name");
    });
    rows.push({ name: "axe-screening-detects-unnamed-button", refused: axeControl, expect: ["axe:button-name"], failed: axeControl ? ["axe:button-name"] : [] });
    for (const mutant of MUTANTS) {
      if (expired()) throw new Error("deadline before controls completed");
      const row = await withFreshPlayer(chromium, async (page, cdp) => {
        await openPlayer(page, cdp);
        await applyMutantAfterSetup(page, mutant);
        let assertions;
        try { assertions = await runPhase(mutant.phase, page, cdp); }
        catch (error) { return { name: mutant.name, kind: "refusal", refused: false, expect: mutant.expect, failed: [`observer-error:${String(error.message).slice(0, 120)}`] }; }
        const failed = assertions.filter((a) => a.kind === "gate" && !a.passed).map((a) => a.id);
        return { name: mutant.name, kind: "refusal", phase: mutant.phase, expect: mutant.expect, failed, refused: mutant.expect.every((id) => failed.includes(id)) };
      });
      rows.push(row);
    }
    // Positive controls: making the product do the missing thing must flip the
    // matching finding to resolved, proving the finding detectors can see it.
    for (const control of RESOLUTIONS) {
      const row = await withFreshPlayer(chromium, async (page, cdp) => {
        await openPlayer(page, cdp);
        await page.evaluate(control.apply);
        const assertions = control.phase === "structure" ? await observeStructure(page, cdp) : await observeDisposalWithFixup(page, cdp);
        const resolved = assertions.filter((a) => a.kind === "finding" && a.passed).map((a) => a.id);
        return { name: control.name, kind: "resolution", expect: [control.resolves], failed: [], resolved, refused: resolved.includes(control.resolves) };
      });
      rows.push(row);
    }
    const baseline = await withFreshPlayer(chromium, async (page, cdp) => { await openPlayer(page, cdp); return (await runEverything(page, cdp)).filter((a) => a.kind === "gate" && !a.passed).map((a) => a.id); });
    report.controls = { rows, baselineFailures: baseline, refused: rows.filter((r) => r.refused).length, total: rows.length };
  }
  const observed = report.observe?.assertions ?? [];
  const gates = observed.filter((a) => a.kind === "gate");
  report.findings = observed.filter((a) => a.kind === "finding").map((a) => ({ id: a.id, state: a.passed ? "resolved" : "open", detail: a.detail }));
  const observeOk = mode === "controls" || (family !== "chromium" ? true : gates.length > 0 && gates.every((a) => a.passed));
  const controlsOk = mode === "observe" || family !== "chromium" || (report.controls.refused === report.controls.total && report.controls.baselineFailures.length === 0);
  report.result = observeOk && controlsOk ? "passed" : "failed";
} catch (error) {
  report.error = String(error?.stack || error);
}
report.finishedAt = new Date().toISOString();
report.elapsedMs = Date.now() - started;
fs.writeFileSync(outPath, JSON.stringify(report, null, 2) + "\n");
const gateRows = (report.observe?.assertions ?? []).filter((a) => a.kind === "gate");
console.log(`soldier-accessibility ${family}: ${report.result}; gates ${gateRows.filter((a) => a.passed).length}/${gateRows.length}; findings open ${(report.findings ?? []).filter((f) => f.state === "open").length}; controls ${report.controls ? `${report.controls.refused}/${report.controls.total}` : "n/a"}`);
process.exit(report.result === "passed" ? 0 : 1);
