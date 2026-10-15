// Browser-only functional adapter. All state changes go through the mounted UI.
// DOM activation is synthetic functional input, never trusted physical-input/AT evidence.
export async function runSoldierCase(w, kind, options) {
  const doc = w.document, assertions = [], details = { kind };
  const check = (name, condition) => { if (!condition) throw new Error(`soldier ${kind}: ${name}`); assertions.push({ name, passed: true }); };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const delay = (ms) => new Promise((resolve) => w.setTimeout(resolve, ms));
  const wait = async (predicate, name) => {
    while (!predicate()) { if (options.expired()) throw new Error(`soldier deadline: ${name}`); await delay(10); }
  };
  const root = () => doc.getElementById("soldier-reference");
  const state = () => JSON.parse(doc.getElementById("soldier-reference-state")?.textContent ?? "null");
  const exported = () => doc.getElementById("soldier-reference-export")?.textContent;
  const button = (name, owner = root()) => {
    const matches = [...owner.querySelectorAll("button")].filter((node) => node.textContent === name);
    check(`unique real control ${name}`, matches.length === 1); return matches[0];
  };
  const click = async (name) => { button(name).click(); await new Promise((done) => w.requestAnimationFrame(done)); await delay(0); };
  const attribute = (name) => root().getAttribute(name);
  const select = async (id) => {
    const node = root().querySelector(`[data-soldier-id="${id}"]`);
    check(`real roster ${id}`, !!node); node.click(); await wait(() => attribute("data-selected") === id, "selection");
  };
  const mount = async () => {
    check("actual Program mount control", !!doc.getElementById("mount-soldier-reference"));
    check("fresh real player frame", !root());
    await wait(() => {
      const status = doc.querySelector("[data-authority-status]")?.getAttribute("data-authority-status") ?? "";
      if (/bootstrap failed|authority error/.test(status)) throw new Error(`Actual player authority startup failed: ${status}`);
      return status === "synchronized";
    }, "actual bootstrap/hub synchronization");
    check("real generated bootstrap/hub synchronized", true);
    doc.getElementById("mount-soldier-reference").click();
    await wait(() => root()?.getAttribute("data-world-count") === "100", "initial mount");
    check("actual SVG mounted", root().querySelectorAll("svg").length === 1);
    check("source-bound representative asset", "sha256:" + attribute("data-asset-sha256") === options.assetSha256);
  };
  let retained, failure, cleanup = { owned: null, frameDisposed: false };
  try {
    await mount(); retained = root();
    if (kind === "soldier-local") {
      await select("soldier-0000"); const before = state();
      const nodes = ["#soldier-reference symbol", '[data-fsgg-element-id="soldier-0000-art"]', '[data-fsgg-element-id="soldier-0001-art"]', '[data-soldier-id="soldier-0001"]'].map((selector) => [selector, doc.querySelector(selector)]);
      root().focus();
      for (const type of ["keydown", "keyup"]) root().dispatchEvent(new w.KeyboardEvent(type, { key: "ArrowRight", code: "ArrowRight", bubbles: true }));
      await wait(() => state().soldiers[0].x === before.soldiers[0].x + 16, "semantic keyboard route");
      check("keyboard semantic move/rotation", state().soldiers[0].facing === before.soldiers[0].facing + 5);
      check("untouched product state", same(state().soldiers.slice(1), before.soldiers.slice(1)));
      check("definitions/instances/untouched roster retained", nodes.every(([selector, node]) => node && doc.querySelector(selector) === node));
      await click("Move selected soldier"); await wait(() => state().soldiers[0].x === before.soldiers[0].x + 32, "accessible move projection"); check("accessible equivalent move", state().soldiers[0].x === before.soldiers[0].x + 32);
      await click("Change selected pose"); await wait(() => state().soldiers[0].pose === "March", "pose projection"); check("pose command", state().soldiers[0].pose === "March");
      await click("Change selected appearance"); await wait(() => state().soldiers[0].faction === "Amber", "appearance projection"); check("appearance command", state().soldiers[0].faction === "Amber" && state().soldiers[0].health === 90);
      const art = doc.querySelector('[data-fsgg-element-id="soldier-0001-art"]');
      const bounds = art.getBoundingClientRect();
      check("painted full asset target", bounds.width > 0 && bounds.height > 0);
      art.dispatchEvent(new w.PointerEvent("pointerup", { clientX: bounds.x + bounds.width / 2, clientY: bounds.y + bounds.height / 2, pointerId: 1, button: 0, bubbles: true }));
      await wait(() => attribute("data-selected") === "soldier-0001", "paint-aware transformed pointer route");
      check("same semantic pointer selection", attribute("data-focused") === "soldier-0001");
      const revision = state().revision;
      await click("Focus next soldier"); await click("Pan to offscreen soldiers");
      check("focus/camera presentation only", state().revision === revision && attribute("data-focused") === "soldier-0002");
      const note = doc.querySelector('[aria-label="Soldier reference note"]'); note.focus();
      note.dispatchEvent(new w.CompositionEvent("compositionstart", { bubbles: true }));
      note.dispatchEvent(new w.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, isComposing: true }));
      note.value = "兵士 note"; note.dispatchEvent(new w.Event("input", { bubbles: true }));
      note.dispatchEvent(new w.CompositionEvent("compositionend", { bubbles: true }));
      check("native editor/IME exclusion", state().revision === revision && note.value === "兵士 note");
      await click("Pause soldiers"); check("paused", attribute("data-status") === "Paused");
      await click("Animate 10% soldiers"); const paused = state(); await delay(80);
      check("paused motion stays fixed", same(state(), paused));
      await click("Step soldiers"); await wait(() => state().revision === paused.revision + 1, "single step");
      check("single step exactly ten soldiers", state().soldiers.filter((soldier, index) => soldier.x !== paused.soldiers[index].x).length === 10);
      await click("Resume soldiers"); await wait(() => state().revision > paused.revision + 1, "resume");
      await click("Stop soldier motion"); await click("Reset soldiers"); await wait(() => state().revision === 0, "reset projection");
      check("reset", state().revision === 0);
    } else if (kind === "soldier-external") {
      await click("Use external soldier authority");
      check("local owner retired", attribute("data-retired-authority-owned") === "0" && attribute("data-retired-svg-connected") === "false" && attribute("data-local-owned") === "0");
      await click("Connect soldier authority"); await click("Complete soldier snapshot"); await select("soldier-0000");
      await click("Move selected soldier"); await click("Change selected pose");
      check("receipts separate from presentation", attribute("data-receipts") === "1:accepted,2:accepted" && state().revision === 0);
      await click("Request soldier burst"); await click("Complete soldier snapshot"); await click("Complete soldier snapshot");
      check("ordered accepted presentation", state().revision === 2);
      const baseline = state(), baselineExport = exported();
      await click("Request cached soldier snapshot"); await click("Complete soldier snapshot");
      check("cached snapshot refused", same(state(), baseline) && /Rejected/.test(attribute("data-last-outcome")));
      await click("Fail next soldier presentation"); await click("Move selected soldier"); await click("Complete soldier snapshot");
      check("failed callback retains state/export", same(state(), baseline) && exported() === baselineExport && attribute("data-callback-failure") === "true");
      await click("Request soldier burst"); await click("Complete soldier snapshot");
      check("same revision refuses after failed callback", same(state(), baseline) && exported() === baselineExport && /non-increasing-revision:3:3/.test(attribute("data-last-outcome")));
      await click("Move selected soldier"); await click("Complete soldier snapshot");
      check("queued older reply remains fenced", same(state(), baseline));
      await click("Complete soldier snapshot"); check("newer revision recovers", state().revision === 4);
      const accepted = state(), acceptedExport = exported();
      await click("Refuse next soldier replacement"); await click("Move selected soldier"); await click("Complete soldier snapshot");
      check("failed replacement retains state/export", same(state(), accepted) && exported() === acceptedExport && /replacement refused/i.test(attribute("data-refusal")));
      await click("Disconnect soldier authority"); await click("Move selected soldier");
      check("disconnected command refused", /6:rejected/.test(attribute("data-receipts")));
      await click("Connect soldier authority"); await click("Complete soldier snapshot");
      check("same epoch retains authority baseline", same(state(), accepted) && exported() === acceptedExport && /non-increasing-revision:5:5/.test(attribute("data-last-outcome")));
      await click("Move selected soldier"); await click("Replace soldier authority"); await click("Complete oldest soldier snapshot");
      check("stale epoch reply refused", same(state(), accepted));
      await click("Complete soldier snapshot");
      check("changed epoch resets revision", state().revision === 0 && attribute("data-gateway-epoch") === "soldier-epoch-replacement:1");
    } else if (/^soldier-population-(1|100|250|500|1000)$/.test(kind)) {
      const count = Number(kind.split("-").at(-1)); await click(`Load ${count} soldiers`);
      check("independent population reset", state().soldiers.length === count && attribute("data-world-count") === String(count));
      for (const percentage of [10, 50, 100]) {
        const before = state(); await click(`Update ${percentage}% soldiers`); await wait(() => state().revision === before.revision + 1, "independent update projection");
        const ranked = before.soldiers.map((soldier) => ({ soldier, rank: [...soldier.id].reduce((value, char) => (value * 31 + char.charCodeAt(0)) % 100003, 1729) })).sort((a, b) => a.rank - b.rank || a.soldier.id.localeCompare(b.soldier.id));
        const order = new Map(ranked.map((value, index) => [value.soldier.id, index]));
        const expected = before.soldiers.map((soldier) => {
          const index = order.get(soldier.id);
          return index >= Math.floor(count * percentage / 100) ? soldier : { ...soldier, x: soldier.x + 1 + index % 7, y: soldier.y + 1 + index % 5, facing: (soldier.facing + 3 + index % 11) % 360, pose: index % 2 === 0 ? "March" : "Kneel" };
        });
        check(`exact ${percentage}% state/identity/order oracle`, state().revision === before.revision + 1 && same(state().soldiers, expected));
      }
    } else if (kind === "soldier-churn") {
      await click("Load 2000 world / 200 visible"); await select("soldier-0000"); await click("Pan to offscreen soldiers");
      check("offscreen focus retained", attribute("data-focused") === "soldier-0000");
      await click("Remove selected soldier");
      check("removal focus transfer", attribute("data-focused") === "soldier-0001" && doc.activeElement === root().querySelector('[data-soldier-id="soldier-0001"]'));
      await click("Spawn soldier"); check("churn world count", attribute("data-world-count") === "2000");
      await click("Revise soldier definitions"); await wait(() => state().definitionRevision === 2, "definition projection"); check("definition revision", state().definitionRevision === 2);
      let fullDownload = null;
      const originalClick = w.HTMLAnchorElement.prototype.click;
      w.HTMLAnchorElement.prototype.click = function () { if (this.download === "soldier-world.svg") fullDownload = { filename: this.download, href: this.href }; return originalClick.call(this); };
      try { await click("Export full soldier world"); } finally { w.HTMLAnchorElement.prototype.click = originalClick; }
      const svg = exported();
      check("real full-world export control", fullDownload?.filename === "soldier-world.svg" && fullDownload.href.startsWith("blob:"));
      details.fullExport = { sha256: options.hash(svg), uses: (svg.match(/<use\b/g) ?? []).length, symbols: (svg.match(/<symbol\b/g) ?? []).length };
      check("complete 2000-use six-symbol export", (svg.match(/<use\b/g) ?? []).length === 2000 && (svg.match(/<symbol\b/g) ?? []).length === 6 && svg.includes("soldier-1999"));
      await click("Dispose soldier reference");
      check("panel disposed", !root());
      const counters = ["data-input-owned", "data-retired-authority-owned", "data-adapter-listeners", "data-svg-count"];
      check("zero disposed owners", counters.every((name) => retained.getAttribute(name) === "0"));
      doc.getElementById("mount-soldier-reference").click(); await wait(() => root()?.getAttribute("data-world-count") === "100", "remount");
      check("fresh remount", root().querySelectorAll("svg").length === 1); retained = root();
    } else throw new Error(`Unknown soldier case ${kind}`);
    details.finalStateSha256 = options.hash(JSON.stringify(state()));
    details.finalWorldCount = state().soldiers.length;
  } catch (error) { failure = error; }
  finally {
    try {
      if (root()) {
        retained = root(); const detached = button("Move selected soldier");
        await click("Dispose soldier reference"); const before = retained.outerHTML; detached.click();
        check("detached control inert", retained.outerHTML === before && !root());
      }
      const counters = ["data-input-owned", "data-retired-authority-owned", "data-adapter-listeners", "data-svg-count"];
      cleanup.owned = retained && counters.every((name) => retained.getAttribute(name) === "0") ? 0 : null;
      check("zero reported owned resources", cleanup.owned === 0);
    } catch (error) { cleanup.error = error.message; if (!failure) failure = error; }
  }
  if (failure) { failure.cleanup = cleanup; failure.observations = { kind, details, assertions: [...assertions, { name: failure.message, passed: false }], skipped: false, retried: false, flaky: false, cleanup }; throw failure; }
  return { kind, details, assertions, skipped: false, retried: false, flaky: false, cleanup };
}
