#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="${1:?repo-relative JUnit report path required}"
WORK_ID=001-bindings-lifecycle
TITLE='Fable bindings lifecycle'
export DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

command -v fsgg-sdd >/dev/null || { echo "fsgg-sdd is required" >&2; exit 1; }
command -v fsgg-fsharp-surface >/dev/null || { echo "fsgg-fsharp-surface is required" >&2; exit 1; }
run() { fsgg-sdd "$@" --root "$ROOT" --work "$WORK_ID" --title "$TITLE"; }

# SDD 1.0.1 requires a Governance-owned public-surface receipt before it can certify
# public-impact F# work. The producer owns the stable readiness path and evaluates the exact
# generated library project; redirecting stdout only discards its duplicate terminal projection.
fsgg-fsharp-surface --root "$ROOT" --project src/AcmeBindings/AcmeBindings.fsproj >/dev/null

fsgg-sdd init --root "$ROOT" >"$ROOT/reports/sdd-init.json"
run charter >"$ROOT/reports/sdd-charter.json"
run specify --input $'value: maintain a verified Fable binding package\nscope: one pinned Babylon binding workspace\nrequirement: execute the pinned runtime and reject declaration drift' >"$ROOT/reports/sdd-specify.json"
run clarify >"$ROOT/reports/sdd-clarify.json"
run checklist >"$ROOT/reports/sdd-checklist.json"
run plan >"$ROOT/reports/sdd-plan.json"
node "$ROOT/scripts/author-sdd-lifecycle.mjs" plan "$ROOT/work/$WORK_ID/plan.md"
run tasks >"$ROOT/reports/sdd-tasks.json"
run analyze >"$ROOT/reports/sdd-analyze.json"
run evidence >"$ROOT/reports/sdd-evidence-scaffold.json"
node "$ROOT/scripts/author-sdd-lifecycle.mjs" evidence "$ROOT/work/$WORK_ID/evidence.yml" "$REPORT"
run evidence --from-test-report "$REPORT" >"$ROOT/reports/sdd-evidence.json"
run verify >"$ROOT/reports/sdd-verify.json"
run ship >"$ROOT/reports/sdd-ship.json"

# `init` deliberately seeds the lifecycle skills first; reconcile any newer supported
# skill surface and require doctor to observe a coherent generated workspace.
fsgg-sdd upgrade --root "$ROOT" --yes >"$ROOT/reports/sdd-upgrade.json"
fsgg-sdd doctor --root "$ROOT" >"$ROOT/reports/sdd-doctor.json"

jq -e '.outcome == "succeeded" and .verification.status == "verificationReady" and .verification.evidenceObservedCount > 0' "$ROOT/reports/sdd-verify.json" >/dev/null
jq -e '.outcome == "succeeded" and .ship.disposition == "shipReady"' "$ROOT/reports/sdd-ship.json" >/dev/null
jq -e '.outcome == "noChange" and .doctor.isCoherent == true' "$ROOT/reports/sdd-doctor.json" >/dev/null
test -f "$ROOT/readiness/$WORK_ID/governance-handoff.json"
echo "fable-bindings SDD lifecycle passed"
