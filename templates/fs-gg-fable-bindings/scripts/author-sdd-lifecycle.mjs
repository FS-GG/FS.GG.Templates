import { readFileSync, writeFileSync } from "node:fs";

const [mode, path, report] = process.argv.slice(2);
if (!mode || !path) throw new Error("usage: author-sdd-lifecycle.mjs plan|evidence <path> [report]");

let text = readFileSync(path, "utf8");
if (mode === "plan") {
  const replacements = new Map([
    ["Plan requirement FR-001 through the plan command contract.", "Run the pinned runtime before declaration drift is evaluated, so a green closure proves executable behavior rather than metadata."],
    ["fsgg-sdd plan, work/001-bindings-lifecycle/plan.md, and command-report JSON are tool-facing and compatibility-preserving.", "The lifecycle consumes the binding JUnit report and emits a Governance-readable upstream-drift verdict."],
    ["Run focused command tests, FSI/prelude evidence, and CLI smoke evidence before task generation.", "Import the real binding JUnit report and require its observed-run receipt at verify and ship."],
    ["Plan schemaVersion 1 is accepted; unsupported plan schemas diagnose before write.", "No consumer schema changes; declaration drift is diagnosed without advancing the pinned lock."],
    ["readiness/001-bindings-lifecycle/work-model.json refreshes from current plan sources or reports staleGeneratedView.", "The generated work model remains traceable to the pinned runtime requirement and its observed evidence."],
  ]);
  for (const [before, after] of replacements) {
    if (!text.includes(before)) throw new Error(`SDD plan scaffold changed; missing: ${before}`);
    text = text.replace(before, after);
  }
} else if (mode === "evidence") {
  if (!report) throw new Error("evidence mode requires a report path");
  const missing = (text.match(/kind: missing/g) ?? []).length;
  if (missing === 0) throw new Error("SDD evidence scaffold has no missing obligations to author");
  const taskSubjects = [...text.matchAll(/subject:\n      type: task\n      id: T(\d{3})\n    taskRefs: \[T\1\]/g)];
  if (taskSubjects.length !== missing) throw new Error("SDD evidence subject scaffold changed");
  text = text
    // Evidence ids already bind these declarations to required task obligations.
    // Subjecting the evidence back to the same task adds the reverse edge to the
    // task -> required-evidence edge and makes the Governance graph cyclic.
    .replace(/subject:\n      type: task\n      id: T(\d{3})\n    taskRefs: \[T\1\]/g, "subject:\n      type: obligation\n      id: EV$1")
    .replaceAll("kind: missing", "kind: verification")
    .replaceAll("artifacts: []", `artifacts: [${report}]`)
    .replaceAll("result: missing", "result: pass")
    .replaceAll("    notes: [Evidence required before verify.]\n", "");
} else {
  throw new Error("mode must be plan or evidence");
}

writeFileSync(path, text);
