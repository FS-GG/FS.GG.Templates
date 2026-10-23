// Offline tests for the scheduled Xantham watch (FS.GG.Templates#751). No network: fetch and gh are faked.
import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import { MARKER, MAX_BYTES, NUGET_BASE, PACKAGE_IDS, UPSTREAM_API, fetchText, renderIssueBody, renderSummary, validateBaseline, watch } from "../../scripts/xantham-watch.mjs";

const root = resolve(import.meta.dirname, "../..");
const baseline = JSON.parse(readFileSync(join(root, "templates/fs-gg-fable-bindings/xantham/watch-baseline.json"), "utf8"));
validateBaseline(baseline);
const HEAD = baseline.upstream.head;
const other = "1".repeat(40);

const nuspec = (id, version, groups) => `<?xml version="1.0"?><package><metadata><id>${id}</id><version>${version}</version><dependencies>${groups.map(g => `<group targetFramework="${g}"></group>`).join("")}</dependencies></metadata></package>`;
// A fetch fake serving the baseline world; `over` replaces or adds routes, `fail` makes a route fail.
const world = ({ indexes = {}, nuspecs = {}, head = HEAD, failing = [], raw = {} } = {}) => async (url) => {
  if (failing.some(f => url.includes(f))) return new Response("nope", { status: 503 });
  if (url in raw) return raw[url];
  if (url === `${UPSTREAM_API}/${baseline.upstream.repository}/commits/HEAD`) return new Response(`${head}\n`);
  for (const id of PACKAGE_IDS) {
    if (url === `${NUGET_BASE}/${id}/index.json`) return new Response(JSON.stringify({ versions: indexes[id] ?? baseline.packages[id].versions }));
    const m = url.match(new RegExp(`^${NUGET_BASE}/${id}/([^/]+)/${id}\\.nuspec$`));
    if (m) return nuspecs[`${id}@${m[1]}`] ? new Response(nuspecs[`${id}@${m[1]}`]) : new Response("missing", { status: 404 });
  }
  throw new Error(`unexpected URL ${url}`);
};

// 1. Unchanged world: "no change", no signal, no issue body needed.
{
  const result = await watch(baseline, world());
  assert.equal(result.status, "no-change"); assert.deepEqual(result.signals, []);
  assert.match(renderSummary(result), /Result: no change/);
}

// 2. A new version is a signal and its nuspec groups are recorded.
{
  const result = await watch(baseline, world({ indexes: { xantham: [...baseline.packages.xantham.versions, "0.2.0"] }, nuspecs: { "xantham@0.2.0": nuspec("xantham", "0.2.0", ["net10.0"]) } }));
  assert.equal(result.status, "signal");
  assert.deepEqual(result.signals.map(s => s.kind), ["new-version"]);
  assert.deepEqual(result.signals[0].targetFrameworkGroups["0.2.0"], ["net10.0"]);
}

// 3. A netstandard2.x group on xantham.fable.core.ts is its own signal (several spellings); on another package it is not.
for (const group of ["netstandard2.1", ".NETStandard2.0", "netstandard2.1".toUpperCase()]) {
  const result = await watch(baseline, world({ indexes: { "xantham.fable.core.ts": [...baseline.packages["xantham.fable.core.ts"].versions, "0.2.0"] }, nuspecs: { "xantham.fable.core.ts@0.2.0": nuspec("xantham.fable.core.ts", "0.2.0", ["net8.0", group]) } }));
  assert.deepEqual(result.signals.map(s => s.kind), ["new-version", "netstandard-group"], group);
  assert.deepEqual(result.signals[1].groups, [group]);
}
{
  const result = await watch(baseline, world({ indexes: { "xantham.fable.core": [...baseline.packages["xantham.fable.core"].versions, "0.2.0"] }, nuspecs: { "xantham.fable.core@0.2.0": nuspec("xantham.fable.core", "0.2.0", ["netstandard2.1"]) } }));
  assert.deepEqual(result.signals.map(s => s.kind), ["new-version"], "netstandard on a non-watched package is only a new-version signal");
}

// 4. An upstream HEAD different from the baseline is a signal.
{
  const result = await watch(baseline, world({ head: other }));
  assert.deepEqual(result.signals, [{ kind: "upstream-head-changed", baseline: HEAD, observed: other }]);
}

// 5. A removed baseline version is informational only.
{
  const result = await watch(baseline, world({ indexes: { xantham: baseline.packages.xantham.versions.slice(1) } }));
  assert.equal(result.status, "no-change"); assert.equal(result.notes.length, 1);
}

// 6. Every failure is a thrown failure, never "no change".
const mustFail = async (name, fetchImpl, pattern) => assert.rejects(() => watch(baseline, fetchImpl), pattern, name);
await mustFail("nuget index 503", world({ failing: ["xantham.typescript.wire/index.json"] }), /HTTP 503/);
await mustFail("upstream HEAD 503", world({ failing: ["commits/HEAD"] }), /HTTP 503/);
await mustFail("new-version nuspec 404", world({ indexes: { xantham: [...baseline.packages.xantham.versions, "0.2.0"] } }), /HTTP 404/);
await mustFail("network error", async () => { throw new Error("ECONNRESET"); }, /fetch failed: ECONNRESET/);
await mustFail("index not JSON", world({ raw: { [`${NUGET_BASE}/xantham/index.json`]: new Response("<html>") } }), /index is not JSON/);
await mustFail("index without versions", world({ raw: { [`${NUGET_BASE}/xantham/index.json`]: new Response("{}") } }), /no versions array/);
await mustFail("hostile version string", world({ indexes: { xantham: [...baseline.packages.xantham.versions, "1.0.0\n<!-- fsgg:fbx-07-watch -->"] } }), /not a version/);
await mustFail("HEAD not a sha", world({ head: "master" }), /not a 40-hex/);
await mustFail("nuspec for a different version", world({ indexes: { xantham: [...baseline.packages.xantham.versions, "0.2.0"] }, nuspecs: { "xantham@0.2.0": nuspec("xantham", "0.3.0", []) } }), /does not declare that version/);
await mustFail("hostile group", world({ indexes: { xantham: [...baseline.packages.xantham.versions, "0.2.0"] }, nuspecs: { "xantham@0.2.0": nuspec("xantham", "0.2.0", ["bad group <!-- fsgg:fbx-07-watch -->"]) } }), /malformed targetFramework/);

// 7. The 1 MiB bound holds for a declared and an undeclared oversize body.
await assert.rejects(() => fetchText(async () => new Response("x".repeat(MAX_BYTES + 1)), "https://example.invalid/big"), /exceeds/);
await assert.rejects(() => fetchText(async () => new Response("x", { headers: { "content-length": String(MAX_BYTES + 1) } }), "https://example.invalid/big"), /declares/);
assert.equal((await fetchText(async () => new Response("x".repeat(MAX_BYTES)), "https://example.invalid/ok")).length, MAX_BYTES);

// 8. The baseline validator refuses a malformed or incomplete baseline.
for (const [name, mutate] of [
  ["wrong schema", b => { b.schemaVersion = 2; }],
  ["missing package", b => { delete b.packages["xantham.fable.node"]; }],
  ["extra package", b => { b.packages.extra = { versions: ["1.0.0"] }; }],
  ["no groups for a version", b => { delete b.packages["xantham.fable.core.ts"].targetFrameworkGroups["0.1.0"]; }],
  ["short head", b => { b.upstream.head = "594f104"; }],
]) {
  const copy = structuredClone(baseline); mutate(copy);
  assert.throws(() => validateBaseline(copy), /xantham-watch/, name);
}
// The committed baseline records the facts #751 names.
assert.equal(baseline.upstream.headShort, "594f104"); assert.ok(HEAD.startsWith("594f104"));
assert.deepEqual(baseline.packages["xantham.fable.core.ts"].targetFrameworkGroups["0.1.0"], ["net8.0"]);

// 9. The issue body is deterministic, starts with the marker, and carries only validated values.
{
  const result = await watch(baseline, world({ head: other }));
  const body = renderIssueBody(result);
  assert.ok(body.startsWith(`${MARKER}\n`)); assert.equal(body, renderIssueBody(result));
  assert.equal(body.split(MARKER).length, 2, "exactly one marker");
}

// 10. The create-or-update script, against a fake gh that records its calls.
const work = mkdtempSync(join(process.env.TMPDIR ?? root, "xantham-watch-test-"));
try {
  const bin = join(work, "bin"); mkdirSync(bin);
  writeFileSync(join(bin, "gh"), `#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$1 $2" in
  "api repos/FS-GG/test/labels/fbx-07-watch") [[ "\${FAKE_LABEL:-yes}" == yes ]] ;;
  "label create") ;;
  "issue list") cat "$FAKE_LIST" ;;
  "issue view") cat "$FAKE_VIEW" ;;
  "issue create") echo "https://example.invalid/issues/99" ;;
  "issue edit") ;;
  *) echo "unexpected gh $*" >&2; exit 9 ;;
esac
`);
  chmodSync(join(bin, "gh"), 0o755);
  const result = await watch(baseline, world({ head: other }));
  const bodyFile = join(work, "body.md"); writeFileSync(bodyFile, renderIssueBody(result));
  const run = (scenario) => {
    const log = join(work, `${scenario.name}.log`); writeFileSync(log, "");
    writeFileSync(join(work, "list.json"), JSON.stringify(scenario.list));
    writeFileSync(join(work, "view.txt"), scenario.view ?? "");
    const r = spawnSync(join(root, "scripts/xantham-watch-issue.sh"), [scenario.body ?? bodyFile], { encoding: "utf8", env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, GITHUB_REPOSITORY: "FS-GG/test", FAKE_LOG: log, FAKE_LIST: join(work, "list.json"), FAKE_VIEW: join(work, "view.txt"), FAKE_LABEL: scenario.label ?? "yes" } });
    return { status: r.status, stderr: r.stderr, calls: readFileSync(log, "utf8").trim().split("\n").filter(Boolean) };
  };
  const bodyText = renderIssueBody(result);
  const other1 = { number: 7, body: `${MARKER}\nolder signal` }, unrelated = { number: 3, body: "no marker here" };

  let r = run({ name: "none", list: [unrelated] });
  assert.equal(r.status, 0, r.stderr); assert.ok(r.calls.some(c => c.startsWith("issue create ") && c.includes("--label fbx-07-watch")));
  assert.ok(!r.calls.some(c => c.startsWith("pr ") || c.includes("branch")), "no PR or branch effect");
  assert.ok(r.calls.every(c => /^(api|label|issue) /.test(c)), "only api, label and issue calls");

  r = run({ name: "same", list: [other1], view: bodyText });
  assert.equal(r.status, 0, r.stderr); assert.ok(!r.calls.some(c => /^issue (create|edit)/.test(c)), "unchanged signal is not re-edited");

  r = run({ name: "differs", list: [other1, { number: 9, body: `${MARKER}\nlater duplicate` }], view: "stale" });
  assert.equal(r.status, 0, r.stderr); assert.ok(r.calls.some(c => c.startsWith("issue edit 7 ")), "lowest-numbered marker issue is the one updated");
  assert.ok(!r.calls.some(c => c.startsWith("issue create")), "no second issue");

  r = run({ name: "label-missing", list: [], label: "no" });
  assert.equal(r.status, 0, r.stderr); assert.ok(r.calls.some(c => c.startsWith("label create fbx-07-watch")));

  const bad = join(work, "bad.md"); writeFileSync(bad, "no marker\n");
  r = run({ name: "bad-body", list: [], body: bad });
  assert.notEqual(r.status, 0); assert.ok(!r.calls.some(c => c.startsWith("issue create")));
} finally { rmSync(work, { recursive: true, force: true }); }

// 11. Workflow shape: exactly the specified triggers, permissions and bounds; no secrets, no write beyond issues.
{
  const wf = readFileSync(join(root, ".github/workflows/xantham-watch.yml"), "utf8");
  const code = wf.split("\n").filter(l => !l.trim().startsWith("#")).join("\n");
  assert.match(code, /^on:\n  schedule:\n    - cron: "0 6 \* \* 1"[^\n]*\n  workflow_dispatch:\n/m);
  assert.match(code, /^permissions:\n  contents: read\n  issues: write\n\n/m);
  assert.equal((code.match(/^\s+[a-z-]+: (read|write)\s*$/gm) ?? []).length, 2, "no other permission");
  assert.match(code, /timeout-minutes: 5\b/);
  assert.ok(!/secrets\./.test(code), "no secrets");
  assert.ok(!/pull_request|repository_dispatch|push:/.test(code), "no other trigger");
  assert.ok(!/gh pr |git push|git commit|create-pull-request|npm |dotnet |curl |wget /.test(code), "no PR, push, install or ad hoc fetch");
  assert.equal((code.match(/uses: /g) ?? []).length, 1, "only the checkout action");
  assert.match(code, /persist-credentials: false/);
}

console.log("PASS Xantham watch: signals, failure-never-no-change, bounds, deduplicated issue effect, workflow shape");
