#!/usr/bin/env node
// Read-only Xantham upstream watch (FS.GG.Templates#751, carried from #725 / FBX-07).
//
// Compares live, metadata-only upstream facts against the committed baseline
// templates/fs-gg-fable-bindings/xantham/watch-baseline.json and reports whether anything changed.
//
// Reads (nothing else): the nuget.org flat-container index of every baseline package, the nuspec of
// every version NOT in the baseline, and the upstream default-branch HEAD commit. It never downloads
// a package, never checks out or restores upstream, and never executes fetched content: fetched text
// is only JSON-parsed or pattern-matched, and every value that reaches the summary or the issue body
// is first validated against a strict shape, so a hostile response cannot inject markup or markers.
//
// Signals: a version not in the baseline; a netstandard2.x target-framework group on
// xantham.fable.core.ts; an upstream HEAD different from the baseline.
//
// Any fetch, size, parse or shape failure throws and exits non-zero. It is never reported as "no change".
// The baseline is read-only here: this script has no code path that writes it.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const MARKER = "<!-- fsgg:fbx-07-watch -->";
export const NUGET_BASE = "https://api.nuget.org/v3-flatcontainer";
export const UPSTREAM_API = "https://api.github.com/repos";
export const MAX_BYTES = 1024 * 1024;       // 1 MiB per response
export const REQUEST_TIMEOUT_MS = 30_000;
export const WATCHED_GROUP_PACKAGE = "xantham.fable.core.ts";
export const PACKAGE_IDS = ["xantham", "xantham.fable.core", "xantham.fable.core.ts", "xantham.fable.node", "xantham.typescript.wire"];

const VERSION_RE = /^[0-9]+(\.[0-9]+){1,3}(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$/;
const GROUP_RE = /^[0-9A-Za-z.+-]{1,40}$/;
const SHA_RE = /^[0-9a-f]{40}$/;
const REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const NETSTANDARD_RE = /^\.?netstandard\d/i;

const fail = message => { throw new Error(`xantham-watch: ${message}`); };

async function readBounded(response, url) {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_BYTES) fail(`${url}: response declares ${declared} bytes (limit ${MAX_BYTES})`);
  if (!response.body) fail(`${url}: response has no body`);
  const chunks = [];
  let total = 0;
  for await (const chunk of response.body) {
    total += chunk.length;
    if (total > MAX_BYTES) fail(`${url}: response exceeds ${MAX_BYTES} bytes`);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

export async function fetchText(fetchImpl, url, headers = {}) {
  let response;
  try {
    response = await fetchImpl(url, { headers, signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  } catch (error) {
    fail(`${url}: fetch failed: ${error?.message ?? error}`);
  }
  if (!response.ok) fail(`${url}: HTTP ${response.status}`);
  return readBounded(response, url);
}

const versionOf = (value, where) => {
  if (typeof value !== "string" || value.length > 64 || !VERSION_RE.test(value)) fail(`${where}: not a version: ${JSON.stringify(String(value).slice(0, 80))}`);
  return value;
};

export function validateBaseline(baseline) {
  if (baseline?.schemaVersion !== 1) fail("baseline schemaVersion must be 1");
  const packages = baseline.packages;
  if (typeof packages !== "object" || packages === null) fail("baseline.packages is required");
  if (JSON.stringify(Object.keys(packages).sort()) !== JSON.stringify([...PACKAGE_IDS].sort())) fail(`baseline.packages must be exactly ${PACKAGE_IDS.join(", ")}`);
  for (const id of PACKAGE_IDS) {
    const versions = packages[id]?.versions;
    if (!Array.isArray(versions) || versions.length === 0) fail(`baseline ${id}.versions must be a non-empty array`);
    versions.forEach(v => versionOf(v, `baseline ${id}`));
  }
  const groups = packages[WATCHED_GROUP_PACKAGE].targetFrameworkGroups;
  if (typeof groups !== "object" || groups === null) fail(`baseline ${WATCHED_GROUP_PACKAGE}.targetFrameworkGroups is required`);
  for (const version of packages[WATCHED_GROUP_PACKAGE].versions) {
    if (!Array.isArray(groups[version])) fail(`baseline ${WATCHED_GROUP_PACKAGE} has no target-framework groups for ${version}`);
    groups[version].forEach(g => { if (!GROUP_RE.test(g)) fail(`baseline group for ${version} is malformed`); });
  }
  const upstream = baseline.upstream;
  if (!REPO_RE.test(upstream?.repository ?? "")) fail("baseline.upstream.repository must be owner/name");
  if (!SHA_RE.test(upstream?.head ?? "")) fail("baseline.upstream.head must be a 40-hex commit");
  return baseline;
}

export function parseIndex(text, id) {
  let parsed;
  try { parsed = JSON.parse(text); } catch { fail(`${id}: index is not JSON`); }
  if (!Array.isArray(parsed?.versions)) fail(`${id}: index has no versions array`);
  return parsed.versions.map(v => versionOf(v, `${id} index`));
}

export function parseNuspecGroups(text, id, version) {
  const declared = /<version>\s*([^<\s]+)\s*<\/version>/i.exec(text)?.[1];
  if (!declared || declared.toLowerCase() !== version.toLowerCase()) fail(`${id} ${version}: nuspec does not declare that version`);
  const groups = [];
  for (const match of text.matchAll(/<group\b[^>]*?\btargetFramework\s*=\s*"([^"]*)"/gi)) {
    if (!GROUP_RE.test(match[1])) fail(`${id} ${version}: malformed targetFramework group`);
    if (!groups.includes(match[1])) groups.push(match[1]);
  }
  return groups;
}

export async function watch(baseline, fetchImpl, { token } = {}) {
  validateBaseline(baseline);
  const signals = [];
  const notes = [];
  const observed = { packages: {}, upstreamHead: null };

  for (const id of PACKAGE_IDS) {
    const indexUrl = `${NUGET_BASE}/${id}/index.json`;
    const live = parseIndex(await fetchText(fetchImpl, indexUrl), id);
    const known = new Set(baseline.packages[id].versions);
    const added = live.filter(v => !known.has(v));
    const removed = baseline.packages[id].versions.filter(v => !live.includes(v));
    const groups = {};
    for (const version of added) {
      groups[version] = parseNuspecGroups(await fetchText(fetchImpl, `${NUGET_BASE}/${id}/${version}/${id}.nuspec`), id, version);
    }
    observed.packages[id] = { versions: live, addedGroups: groups };
    if (added.length) signals.push({ kind: "new-version", package: id, versions: added, targetFrameworkGroups: groups });
    if (removed.length) notes.push(`${id}: baseline version(s) no longer listed: ${removed.join(", ")} (informational; not a signal)`);
    if (id === WATCHED_GROUP_PACKAGE) {
      for (const version of added) {
        const netstandard = groups[version].filter(g => NETSTANDARD_RE.test(g));
        if (netstandard.length) signals.push({ kind: "netstandard-group", package: id, version, groups: netstandard });
      }
    }
  }

  const repo = baseline.upstream.repository;
  // `Accept: application/vnd.github.sha` makes the commits/HEAD endpoint (the default branch's tip)
  // return only the 40-hex commit id; the default JSON form embeds the whole file diff and exceeds
  // the 1 MiB response bound on large commits.
  const headers = { accept: "application/vnd.github.sha", "x-github-api-version": "2022-11-28", ...(token ? { authorization: `Bearer ${token}` } : {}) };
  const head = (await fetchText(fetchImpl, `${UPSTREAM_API}/${repo}/commits/HEAD`, headers)).trim();
  if (!SHA_RE.test(head)) fail("upstream HEAD response is not a 40-hex commit id");
  observed.upstreamHead = head;
  if (head !== baseline.upstream.head) signals.push({ kind: "upstream-head-changed", baseline: baseline.upstream.head, observed: head });

  return { schemaVersion: 1, status: signals.length ? "signal" : "no-change", signals, notes, observed };
}

const bullet = signal => {
  if (signal.kind === "new-version") {
    return `- New version(s) of \`${signal.package}\` not in the baseline: ${signal.versions.map(v => `\`${v}\` (groups: ${signal.targetFrameworkGroups[v].map(g => `\`${g}\``).join(", ") || "none"})`).join(", ")}`;
  }
  if (signal.kind === "netstandard-group") return `- \`${signal.package}\` ${signal.version} declares a netstandard group: ${signal.groups.map(g => `\`${g}\``).join(", ")}`;
  return `- Upstream default-branch HEAD changed: baseline \`${signal.baseline}\`, observed \`${signal.observed}\``;
};

export function renderSummary(result) {
  const lines = ["## Xantham upstream watch", ""];
  lines.push(result.status === "no-change" ? "**Result: no change** against `watch-baseline.json`." : `**Result: ${result.signals.length} signal(s)** against \`watch-baseline.json\`.`, "");
  result.signals.forEach(s => lines.push(bullet(s)));
  if (result.signals.length) lines.push("");
  result.notes.forEach(n => lines.push(`- Note: ${n}`));
  if (result.notes.length) lines.push("");
  lines.push(`Upstream HEAD observed: \`${result.observed.upstreamHead}\`.`);
  for (const [id, row] of Object.entries(result.observed.packages)) lines.push(`- \`${id}\`: ${row.versions.length} version(s), latest listed \`${row.versions.at(-1)}\``);
  return `${lines.join("\n")}\n`;
}

// Deterministic: no run id, time or URL, so an unchanged signal produces an identical body and the
// issue is not re-edited every week.
export function renderIssueBody(result) {
  return [
    MARKER,
    "## FBX-07 watch: upstream Xantham change detected",
    "",
    "The scheduled read-only watch (`.github/workflows/xantham-watch.yml`, FS.GG.Templates#751) found a difference from `templates/fs-gg-fable-bindings/xantham/watch-baseline.json`:",
    "",
    ...result.signals.map(bullet),
    "",
    "This issue is opened or updated by the workflow only; it makes no PR, branch or pin change and adopts nothing. The baseline moves only by a reviewed PR.",
    "",
    "Next action (fdev routine board pass): assess per the `integrationSteps` in `templates/fs-gg-fable-bindings/xantham/release-assessments.json`. A netstandard2.x support asset or a changed ordinary emission reopens compatibility work under #751; qualify the declared runtime/support matrix before any adoption. Whether the generator still emits the unused DOM open can only be learned by running it and is a separately admitted manual reassessment.",
    "",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!["--baseline", "--result", "--issue-body", "--summary"].includes(key) || argv[i + 1] === undefined) fail(`unknown or incomplete argument ${key}`);
    out[key.slice(2)] = argv[i + 1];
  }
  if (!out.baseline) fail("--baseline is required");
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const summaryPath = args.summary ?? process.env.GITHUB_STEP_SUMMARY;
  try {
    const result = await watch(JSON.parse(readFileSync(args.baseline, "utf8")), fetch, { token: process.env.GITHUB_TOKEN });
    const summary = renderSummary(result);
    process.stdout.write(summary);
    if (summaryPath) appendFileSync(summaryPath, summary);
    if (args.result) writeFileSync(args.result, `${JSON.stringify(result, null, 2)}\n`);
    if (args["issue-body"] && result.signals.length) writeFileSync(args["issue-body"], renderIssueBody(result));
    if (process.env.GITHUB_OUTPUT) appendFileSync(process.env.GITHUB_OUTPUT, `signal=${result.signals.length ? "true" : "false"}\nstatus=${result.status}\n`);
  } catch (error) {
    const message = `## Xantham upstream watch\n\n**Result: FAILED, not "no change".** ${String(error?.message ?? error).replace(/[\r\n]+/g, " ")}\n`;
    process.stderr.write(message);
    if (summaryPath) appendFileSync(summaryPath, message);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
