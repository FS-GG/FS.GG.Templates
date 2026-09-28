#!/usr/bin/env bash
# Qualify Xantham from a materialized fs-gg-fable-bindings workspace.
set -euo pipefail

product="${1:?usage: installed-xantham-qualification.sh PRODUCT [EVIDENCE_JSON] [--live-assessment]}"
evidence="${2:-}"
assessment_mode="${3:-}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

test -f "$product/xantham/toolchain-lock.json"
test -f "$product/scripts/run-xantham.mjs"
maintained_files=("$product/src/BindingsProduct/Bindings.fs" "$product/declaration-lock.json" "$product/binding-plan.json" "$product/coverage-and-drift.json")
if [[ ! -f "${maintained_files[0]}" ]]; then
  maintained_files[0]="$(find "$product/src" -mindepth 2 -maxdepth 2 -name '*.fs' -print -quit)"
fi
maintained_before="$(sha256sum "${maintained_files[@]}")"

(cd "$product" && npm run xantham:prepare >/dev/null)

ambient="$work/ambient"
compiler_version="$(jq -r '.compiler.version' "$product/xantham/toolchain-lock.json")"
conflicting="$ambient/.cache/xantham/$compiler_version/node_modules/@typescript/typescript-linux-x64/lib/tsc"
mkdir -p "$(dirname "$conflicting")"
printf '#!/usr/bin/env sh\necho Version 0.0.0-conflict\n' >"$conflicting"
chmod +x "$conflicting"
cli_version="$(jq -r '.cli.version' "$product/xantham/toolchain-lock.json")"
cli_assembly="$product/.nuget/xantham-tools/bin/.store/xantham/$cli_version/xantham/$cli_version/tools/net10.0/any/xantham.dll"
HOME="$ambient" env -u XANTHAM_TSGO_EXE dotnet "$cli_assembly" tsc version | grep -Fq "$conflicting"

(cd "$product" && HOME="$ambient" node scripts/generate-candidate.mjs --backend xantham --config xantham/ansi-regex.json >/dev/null)
proposal=("$product/generated-candidates/xantham/proposal/AnsiRegex.fs" "$product/generated-candidates/xantham/proposal/manifest.json" "$product/generated-candidates/xantham/proposal/symbols.jsonl")
first="$(sha256sum "${proposal[@]}")"
positive_report="$(find "$product/generated-candidates/xantham/runs" -mindepth 2 -maxdepth 2 -name run-report.json -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
compiler_sha="$(jq -r '.compiler.linuxX64Sha256' "$product/xantham/toolchain-lock.json")"
jq -e --arg compiler_sha "$compiler_sha" '
  .status == "proposal-ready" and .verification.reportSchema == "pass" and
  .verification.limits == "pass" and .verification.imports == "pass" and
  .verification.selectedSymbols == "pass" and .verification.fsharpCompile == "pass" and
  .verification.fableCompile == "not-run" and .verification.runtime == "not-run" and
  .maintainedWorkspace.unchanged == true and .findings.counts.widened == 0 and
  .findings.counts.escape == 0 and .process.limitTriggered == null and
  .process.compilerCache.sha256 == $compiler_sha
' "$positive_report" >/dev/null

(cd "$product" && node scripts/generate-candidate.mjs --backend xantham --config xantham/ansi-regex.json >/dev/null)
test "$first" = "$(sha256sum "${proposal[@]}")"
test "$maintained_before" = "$(sha256sum "${maintained_files[@]}")"

fable="$product/.nuget/xantham-tools/fable/fable"
if [[ ! -x "$fable" ]]; then dotnet tool install Fable --version 5.13.0 --tool-path "$product/.nuget/xantham-tools/fable" >/dev/null; fi
"$fable" "$product/xantham/qualification/Runtime.fsproj" --outDir "$product/.nuget/xantham-tools/pilot/runtime-dist" --noCache >/dev/null
grep -Eq '^import [A-Za-z0-9_]+ from "ansi-regex";' "$product/.nuget/xantham-tools/pilot/runtime-dist/Program.js"
node "$product/.nuget/xantham-tools/pilot/runtime-dist/Program.js" | grep -Fq 'PASS Xantham ANSI candidate default import, omitted options, option constructor, controls and onlyFirst'

proposal_before="$(sha256sum "${proposal[@]}")"
latest_report() { find "$product/generated-candidates/xantham/runs" -mindepth 2 -maxdepth 2 -name run-report.json -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-; }
failure_config() { jq "$1" "$product/xantham/ansi-regex.json" >"$product/.nuget/$2.json"; }
expect_rejected() {
  local config="$1" jq_test="$2"
  if (cd "$product" && node scripts/generate-candidate.mjs --backend xantham --config ".nuget/$config.json" >/dev/null 2>&1); then echo "$config fixture unexpectedly passed" >&2; exit 1; fi
  jq -e ".status == \"rejected\" and .maintainedWorkspace.unchanged == true and ($jq_test)" "$(latest_report)" >/dev/null
  test "$proposal_before" = "$(sha256sum "${proposal[@]}")"
}

failure_config '.limits.timeoutSeconds = 0.001' timeout
expect_rejected timeout '.process.limitTriggered == "timeout" and .verification.limits == "fail"'
failure_config '.packageDirectory = "../outside"' invalid-path
expect_rejected invalid-path 'any(.diagnostics[]; contains("escapes"))'
failure_config '.xanthamConfig = ".nuget/unmapped.json"' signature
printf '{}\n' >"$product/.nuget/unmapped.json"
expect_rejected signature 'any(.diagnostics[]; contains("unaccepted widened or escape"))'
failure_config '.xanthamConfig = ".nuget/bad-mapping.json"' compile-failure
printf '{"groups":{"typescript/lib":{"map":{"RegExp":"Missing.Type"}}}}\n' >"$product/.nuget/bad-mapping.json"
expect_rejected compile-failure 'any(.diagnostics[]; contains("did not compile"))'

bad_tools="$product/.nuget/xantham-tools-bad"
cp -a "$product/.nuget/xantham-tools" "$bad_tools"
jq '.cliAssemblySha256 = "bad"' "$bad_tools/prepared.json" >"$bad_tools/prepared.tmp"
mv "$bad_tools/prepared.tmp" "$bad_tools/prepared.json"
if (cd "$product" && node scripts/run-xantham.mjs --config xantham/ansi-regex.json --tool-dir .nuget/xantham-tools-bad >/dev/null 2>&1); then echo 'wrong tool fingerprint fixture unexpectedly passed' >&2; exit 1; fi
jq -e '.status == "rejected" and .maintainedWorkspace.unchanged == true and any(.diagnostics[]; contains("CLI assembly fingerprint"))' "$(latest_report)" >/dev/null
test "$proposal_before" = "$(sha256sum "${proposal[@]}")"
test "$maintained_before" = "$(sha256sum "${maintained_files[@]}")"

assessment_status=not-run assessment_compatibility=not-run assessment_disposition=not-run
if [[ "$assessment_mode" == "--live-assessment" ]]; then
  assessment="$product/generated-candidates/xantham/public-installed-assessment.json"
  (cd "$product" && npm run xantham:assess -- --output generated-candidates/xantham/public-installed-assessment.json >/dev/null)
  jq -e '.status == "updates-found" and .compatibility == "unqualified" and .recommendation.disposition == "investigate" and .recommendation.reviewedRelease.disposition == "retain-qualified-baseline" and all(.sources[]; .retrieval == "ok")' "$assessment" >/dev/null
  assessment_status="$(jq -r '.status' "$assessment")"
  assessment_compatibility="$(jq -r '.compatibility' "$assessment")"
  assessment_disposition="$(jq -r '.recommendation.disposition' "$assessment")"
fi

if [[ -n "$evidence" ]]; then
  mkdir -p "$(dirname "$evidence")"
  jq -n --arg status "$assessment_status" --arg compatibility "$assessment_compatibility" --arg disposition "$assessment_disposition" \
    --arg candidate "$(sha256sum "${proposal[0]}" | cut -d' ' -f1)" --arg manifest "$(sha256sum "${proposal[1]}" | cut -d' ' -f1)" --arg symbols "$(sha256sum "${proposal[2]}" | cut -d' ' -f1)" \
    '{schema:"fsgg.fbx-installed-xantham-qualification/1",result:"passed",generation:{status:"proposal-ready",repeatBytes:"identical",candidateSha256:$candidate,manifestSha256:$manifest,symbolsSha256:$symbols,findings:{widened:0,escape:0}},compile:{fsharp:"passed",fable:"passed",node:"passed"},maintainedEvidence:"unchanged",assessment:{status:$status,compatibility:$compatibility,disposition:$disposition},fixtures:{wrongTool:"rejected",conflictingCache:"isolated",signatureLoss:"rejected",pathEscape:"rejected",timeout:"rejected",compileFailure:"rejected"}}' >"$evidence"
fi

echo "PASS installed Xantham proposal-ready, deterministic, compile/Fable/Node executable; negative fixtures rejected"
