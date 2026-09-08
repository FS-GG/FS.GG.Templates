import { createHash } from "node:crypto";
import { readFile, realpath, lstat, stat } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";

export const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
export const hashFile = async path => sha256(await readFile(path));

export const parseArgs = argv => {
  const values = new Map();
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) throw new Error(`unexpected argument: ${key}`);
    if (i + 1 >= argv.length || argv[i + 1].startsWith("--")) throw new Error(`${key} requires a value`);
    values.set(key.slice(2), argv[++i]);
  }
  return values;
};

export const resolveInside = (root, candidate, label) => {
  if (typeof candidate !== "string" || candidate.length === 0 || isAbsolute(candidate)) throw new Error(`${label} must be a non-empty workspace-relative path`);
  const full = resolve(root, candidate);
  const rel = relative(root, full);
  if (rel === ".." || rel.startsWith(`..${sep}`)) throw new Error(`${label} escapes the workspace: ${candidate}`);
  return full;
};

export const rejectSymlinkPath = async (root, target) => {
  const rel = relative(root, target);
  let cursor = root;
  for (const part of rel.split(sep).filter(Boolean)) {
    cursor = resolve(cursor, part);
    try {
      if ((await lstat(cursor)).isSymbolicLink()) throw new Error(`refusing symlink in generated output path: ${cursor}`);
    } catch (error) {
      if (error.code === "ENOENT") return;
      throw error;
    }
  }
  const canonicalRoot = await realpath(root);
  if (await realpath(target).catch(() => null)) {
    const canonicalTarget = await realpath(target);
    if (relative(canonicalRoot, canonicalTarget).startsWith("..")) throw new Error("generated output resolves outside its root");
  }
};

export async function validateXanthamCandidate(rawDir, config) {
  for (const name of ["AnsiRegex.fs", "manifest.json", "symbols.jsonl"]) {
    if (!(await stat(resolve(rawDir, name)).catch(() => null))) throw new Error(`missing Xantham output: ${name}`);
  }
  const manifest = JSON.parse(await readFile(resolve(rawDir, "manifest.json"), "utf8"));
  if (manifest.package !== config.package.name || manifest.module !== config.fsharpModule) throw new Error("Xantham manifest identity does not match config");
  if (manifest.counts.widened !== 0 || manifest.counts.escape !== 0) throw new Error("selected candidate contains unaccepted widened or escape losses");
  const ergonomic = config.lossDispositions.find(row => row.grade === "ergonomic");
  if (!ergonomic || ergonomic.disposition !== "reviewed" || ergonomic.count !== manifest.counts.ergonomic) throw new Error("selected ergonomic losses are not fully accounted for");
  const generatedFs = await readFile(resolve(rawDir, "AnsiRegex.fs"), "utf8");
  for (const needle of ["static member ansiRegex", "static member Create", "abstract onlyFirst", '[<Import("default", "ansi-regex")>]']) {
    if (!generatedFs.includes(needle)) throw new Error(`selected generated signature/import is missing: ${needle}`);
  }
  const symbolRows = (await readFile(resolve(rawDir, "symbols.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
  for (const symbol of ["Options", "ansiRegex"]) if (!symbolRows.some(row => row.name === symbol)) throw new Error(`selected symbol is missing from Xantham provenance: ${symbol}`);
  return { manifest, generatedFs, symbolRows };
}

const prereleaseParts = version => {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/.exec(version);
  if (!match) return null;
  return { core: match.slice(1, 4).map(Number), pre: match[4]?.split(".") ?? [] };
};

export const compareVersions = (left, right) => {
  const a = prereleaseParts(left); const b = prereleaseParts(right);
  if (!a || !b) return left.localeCompare(right);
  for (let i = 0; i < 3; i += 1) if (a.core[i] !== b.core[i]) return a.core[i] - b.core[i];
  if (a.pre.length === 0 || b.pre.length === 0) return a.pre.length === b.pre.length ? 0 : a.pre.length === 0 ? 1 : -1;
  for (let i = 0; i < Math.max(a.pre.length, b.pre.length); i += 1) {
    if (a.pre[i] === undefined || b.pre[i] === undefined) return a.pre[i] === undefined ? -1 : 1;
    if (a.pre[i] === b.pre[i]) continue;
    const an = /^\d+$/.test(a.pre[i]); const bn = /^\d+$/.test(b.pre[i]);
    if (an && bn) return Number(a.pre[i]) - Number(b.pre[i]);
    if (an !== bn) return an ? -1 : 1;
    return a.pre[i].localeCompare(b.pre[i]);
  }
  return 0;
};

const sourceDefinitions = baseline => [
  { id: "cli", kind: "published-package", baseline: baseline.cli.version, url: "https://api.nuget.org/v3-flatcontainer/xantham/index.json" },
  { id: "wire", kind: "published-package", baseline: baseline.wire.version, url: "https://api.nuget.org/v3-flatcontainer/xantham.typescript.wire/index.json" },
  { id: "support", kind: "published-package", baseline: baseline.support.version, url: "https://api.nuget.org/v3-flatcontainer/xantham.fable.core/index.json" },
  { id: "source", kind: "repository-head", baseline: baseline.inspectedUpstreamRevision, url: "https://api.github.com/repos/shayanhabibi/Xantham/commits/master" },
  { id: "release", kind: "repository-release", baseline: baseline.cli.version, url: "https://api.github.com/repos/shayanhabibi/Xantham/releases/latest" }
];

const contractForPath = path => {
  if (/Xantham\.Cli|Schema|xantham-cli/i.test(path)) return "CLI/config";
  if (/TypeScript\.Wire|Wire/i.test(path)) return "compiler/wire";
  if (/Fable\.Core/i.test(path)) return "support";
  if (/Generator|Render|Findings/i.test(path)) return "generated-output/findings";
  if (/package-lock|Spec\.fs/i.test(path)) return "compiler pin";
  return null;
};

export async function assessUpdates(baseline, fetchImpl = fetch, now = () => new Date()) {
  const retrieve = async source => {
    try {
      const response = await fetchImpl(source.url, { headers: { Accept: "application/vnd.github+json", "User-Agent": "FS-GG-Templates-Xantham-assessment" }, signal: AbortSignal.timeout(10000) });
      if (source.id === "release" && response.status === 404) return { ...source, retrieval: "ok", observed: null, updateAvailable: false, note: "The repository publishes no GitHub Release; NuGet remains the package authority." };
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const body = await response.json();
      let observed;
      if (source.kind === "published-package") observed = [...body.versions].sort(compareVersions).at(-1) ?? null;
      else if (source.kind === "repository-head") observed = body.sha;
      else observed = String(body.tag_name ?? "").replace(/^v/, "") || null;
      return { ...source, retrieval: "ok", observed, pinnedAvailable: source.kind === "published-package" ? body.versions.includes(source.baseline) : undefined, updateAvailable: source.kind === "repository-head" ? observed !== source.baseline : observed ? compareVersions(observed, source.baseline) > 0 : false };
    } catch (error) {
      return { ...source, retrieval: "unavailable", observed: null, pinnedAvailable: null, updateAvailable: null, diagnostic: error.message };
    }
  };
  const sources = await Promise.all(sourceDefinitions(baseline).map(retrieve));
  const source = sources.find(item => item.id === "source");
  let changedFiles = [];
  if (source?.retrieval === "ok" && source.updateAvailable) {
    const url = `https://api.github.com/repos/shayanhabibi/Xantham/compare/${baseline.inspectedUpstreamRevision}...${source.observed}`;
    try {
      const response = await fetchImpl(url, { headers: { Accept: "application/vnd.github+json", "User-Agent": "FS-GG-Templates-Xantham-assessment" }, signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const body = await response.json();
      changedFiles = (body.files ?? []).map(file => ({ path: file.filename, url: file.blob_url, contract: contractForPath(file.filename) })).filter(file => file.contract);
      sources.push({ id: "source-diff", kind: "repository-compare", baseline: baseline.inspectedUpstreamRevision, url, retrieval: "ok", observed: source.observed, updateAvailable: changedFiles.length > 0 });
    } catch (error) {
      sources.push({ id: "source-diff", kind: "repository-compare", baseline: baseline.inspectedUpstreamRevision, url, retrieval: "unavailable", observed: source.observed, updateAvailable: null, diagnostic: error.message });
    }
  }
  const requiredSources = sources;
  const available = requiredSources.filter(item => item.retrieval === "ok").length;
  const unavailable = requiredSources.filter(item => item.retrieval !== "ok").length;
  const updates = sources.filter(item => item.updateAvailable === true);
  const missingPins = sources.filter(item => item.kind === "published-package" && item.pinnedAvailable === false);
  const status = available === 0 ? "unavailable" : unavailable > 0 ? "partial" : updates.length > 0 ? "updates-found" : "current";
  const affectedContracts = [...new Set([
    ...updates.filter(item => item.kind === "published-package").map(item => item.id === "cli" ? "CLI/config" : item.id === "wire" ? "compiler/wire" : "support"),
    ...changedFiles.map(file => file.contract)
  ])];
  const relevantChanges = updates.map(item => ({ source: item.id, from: item.baseline, to: item.observed, published: item.kind === "published-package" || item.kind === "repository-release", url: item.url })).concat(changedFiles.map(file => ({ source: "source-diff", path: file.path, affectedContract: file.contract, url: file.url, published: false })));
  const publishedUpdates = updates.filter(item => item.kind === "published-package");
  const sourceOnlyUpdate = updates.some(item => item.id === "source") && publishedUpdates.length === 0;
  const needsInvestigation = updates.length > 0 || missingPins.length > 0 || status === "partial" || status === "unavailable";
  return {
    schemaVersion: 1,
    checkedAt: now().toISOString(),
    baseline,
    baselineSha256: sha256(`${JSON.stringify(baseline, null, 2)}\n`),
    sources,
    status,
    relevantChanges,
    affectedContracts,
    knownBlockers: [
      ...(status === "unavailable" ? ["No primary source could be reached; update availability is unknown."] : status === "partial" ? ["Some primary sources were unavailable; the comparison is incomplete."] : []),
      ...missingPins.map(item => `The exact qualified ${item.id} pin ${item.baseline} is no longer available from its package index; preparation is blocked.`)
    ],
    compatibility: status === "current" && missingPins.length === 0 ? "qualified" : "unqualified",
    recommendation: {
      disposition: publishedUpdates.length > 0 ? "qualify-update" : needsInvestigation ? "investigate" : "retain",
      affectedFiles: ["xantham/toolchain-lock.json", "xantham/ansi-regex.json", "xantham/ansi-regex.xantham.json", "scripts/run-xantham.mjs"],
      qualificationChecks: ["prepare and verify exact CLI/compiler hashes", "repeat ANSI candidate bytes", "compile netstandard2.1", "Fable/Node runtime journey", "conflicting-cache and limit rejection fixtures"],
      integrationSteps: publishedUpdates.length > 0 ? ["Review the linked published packages and source diff by affected contract.", "Change exact pins and hashes in one candidate branch.", "Run the listed qualification checks before accepting the new baseline."] : sourceOnlyUpdate ? ["Review the linked source diff by affected contract.", "Keep installable pins unchanged while the change remains source-only.", "Qualify an exact source build only when the active task requires it, or await a published package before changing package pins."] : ["Keep the exact qualified baseline; repeat the assessment on the next skill load."]
    }
  };
}
