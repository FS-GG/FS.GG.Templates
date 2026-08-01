import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const option = (name) => {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`missing ${name}`);
  return process.argv[index + 1];
};

const expected = option("--expect");
const junitPath = resolve(option("--junit"));
const handoffPath = resolve(option("--handoff"));
if (expected !== "clean" && expected !== "drift") throw new Error("--expect must be clean or drift");

const drift = spawnSync(process.execPath, ["scripts/lock-declarations.mjs", "--check"], {
  cwd: process.cwd(),
  encoding: "utf8",
});
const observed = drift.status === 0 ? "clean" : "drift";
if (observed !== expected) {
  process.stderr.write(drift.stdout ?? "");
  process.stderr.write(drift.stderr ?? "");
  throw new Error(`expected declaration state ${expected}, observed ${observed}`);
}

const failed = observed === "drift";
const failure = failed
  ? '\n    <failure message="declaration drift requires review" />\n  '
  : "";
const junit = `<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="fable-bindings" tests="1" failures="${failed ? 1 : 0}" errors="0" skipped="0">
  <testcase classname="BindingsLifecycle" name="pinned-runtime-and-drift" time="0.001">${failure}</testcase>
</testsuite>
`;

const handoff = {
  schemaVersion: 1,
  contractVersion: "2.0.0",
  evidence: {
    nodes: [
      {
        id: "bindings:upstream-declaration-closure",
        state: failed ? "failed" : "real",
        rationale: failed ? "the pinned declaration closure changed and requires review" : "the pinned closure is unchanged",
      },
    ],
    dependencies: [],
  },
  readiness: {
    shipDisposition: "shippable",
    verificationReadiness: "complete",
    blockingDiagnosticIds: [],
    counts: { blocking: 0, advisory: 0 },
    perViewState: { declarationClosure: failed ? "review-required" : "current" },
  },
  governedReferences: [
    { workItem: "fable-bindings-upstream", paths: ["declaration-lock.json", "src/BindingsProduct/Bindings.fs"] },
  ],
};

mkdirSync(dirname(junitPath), { recursive: true });
mkdirSync(dirname(handoffPath), { recursive: true });
writeFileSync(junitPath, junit);
writeFileSync(handoffPath, `${JSON.stringify(handoff, null, 2)}\n`);
console.log(`lifecycle evidence: ${observed}`);
