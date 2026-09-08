import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { assessUpdates, validateXanthamCandidate } from "../../../templates/fs-gg-fable-bindings/scripts/lib/xantham.mjs";

const baseline = JSON.parse(await readFile(resolve(import.meta.dirname, "../../../templates/fs-gg-fable-bindings/xantham/toolchain-lock.json"), "utf8"));
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const fixture = ({ versions = {}, head = baseline.inspectedUpstreamRevision, release = 404, files = [], failures = new Set() } = {}) => async url => {
  const id = url.includes("xantham.typescript.wire") ? "wire" : url.includes("xantham.fable.core") ? "support" : url.includes("flatcontainer/xantham/") ? "cli" : url.includes("compare/") ? "compare" : url.includes("commits/master") ? "source" : "release";
  if (failures.has(id)) return json({}, 500);
  if (id === "cli") return json({ versions: versions.cli ?? [baseline.cli.version] });
  if (id === "wire") return json({ versions: versions.wire ?? [baseline.wire.version] });
  if (id === "support") return json({ versions: versions.support ?? [baseline.support.version] });
  if (id === "source") return json({ sha: head });
  if (id === "compare") return json({ files });
  return release === 404 ? json({}, 404) : json({ tag_name: release });
};
const now = () => new Date("2026-09-08T09:30:50.986Z");

const current = await assessUpdates(baseline, fixture(), now);
assert.equal(current.status, "current"); assert.equal(current.compatibility, "qualified"); assert.equal(current.recommendation.disposition, "retain");
assert.match(current.sources.find(row => row.id === "release").note, /no GitHub Release/);

const published = await assessUpdates(baseline, fixture({ versions: { cli: [baseline.cli.version, "0.1.0-alpha.10"] } }), now);
assert.equal(published.status, "updates-found"); assert.equal(published.compatibility, "unqualified"); assert.equal(published.recommendation.disposition, "qualify-update");
assert.equal(published.relevantChanges.find(row => row.source === "cli").published, true);

const sourceOnly = await assessUpdates(baseline, fixture({ head: "1111111111111111111111111111111111111111", files: [{ filename: "src/Xantham.Generator/Render.fs", blob_url: "https://example.invalid/render" }] }), now);
assert.equal(sourceOnly.status, "updates-found"); assert.equal(sourceOnly.recommendation.disposition, "investigate");
assert.match(sourceOnly.recommendation.integrationSteps.join(" "), /source-only/);
assert.deepEqual(sourceOnly.affectedContracts, ["generated-output/findings"]);

const compilerChange = await assessUpdates(baseline, fixture({ head: "2222222222222222222222222222222222222222", files: [{ filename: "src/Xantham.TypeScript.Wire/Library.fs", blob_url: "https://example.invalid/wire" }, { filename: "src/Xantham.Cli/Spec.fs", blob_url: "https://example.invalid/spec" }] }), now);
assert.ok(compilerChange.affectedContracts.includes("compiler/wire")); assert.ok(compilerChange.affectedContracts.includes("CLI/config"));

const partial = await assessUpdates(baseline, fixture({ failures: new Set(["wire", "release"]) }), now);
assert.equal(partial.status, "partial"); assert.equal(partial.compatibility, "unqualified"); assert.equal(partial.recommendation.disposition, "investigate");

const outage = await assessUpdates(baseline, fixture({ failures: new Set(["cli", "wire", "support", "source", "release"]) }), now);
assert.equal(outage.status, "unavailable"); assert.equal(outage.compatibility, "unqualified"); assert.match(outage.knownBlockers.join(" "), /unknown/);

const missingPin = await assessUpdates(baseline, fixture({ versions: { support: [] } }), now);
assert.equal(missingPin.compatibility, "unqualified"); assert.equal(missingPin.recommendation.disposition, "investigate"); assert.match(missingPin.knownBlockers.join(" "), /preparation is blocked/);
await assert.rejects(() => validateXanthamCandidate(resolve(import.meta.dirname, "missing-upstream-reports"), { package: { name: "ansi-regex" }, fsharpModule: "AnsiRegex", lossDispositions: [] }), /missing Xantham output/);
console.log("PASS Xantham assessment distinguishes packages, source-only changes, compatibility gaps, partial retrieval and outage");
