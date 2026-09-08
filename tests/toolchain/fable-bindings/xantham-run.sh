#!/usr/bin/env bash
# Real positive Xantham/Fable/Node qualification; synthetic configs below inject bounded failures.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PRODUCT="$ROOT/templates/fs-gg-fable-bindings"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

node "$ROOT/tests/toolchain/fable-bindings/xantham-assessment.test.mjs"
(cd "$PRODUCT" && npm run xantham:prepare >/dev/null)
maintained_before="$(sha256sum "$PRODUCT/src/BindingsProduct/Bindings.fs" "$PRODUCT/declaration-lock.json" "$PRODUCT/binding-plan.json" "$PRODUCT/coverage-and-drift.json")"

# A caller cache containing a conflicting fake compiler cannot override the runner's fresh child HOME.
ambient="$WORK/ambient"; conflicting="$ambient/.cache/xantham/7.1.0-dev.20260902.1/node_modules/@typescript/typescript-linux-x64/lib/tsc"
mkdir -p "$(dirname "$conflicting")"
printf '#!/usr/bin/env sh\necho Version 0.0.0-conflict\n' >"$conflicting"
chmod +x "$conflicting"
cli="$PRODUCT/.nuget/xantham-tools/bin/xantham"
compiler="$PRODUCT/.nuget/xantham-tools/compiler/node_modules/@typescript/typescript-linux-x64/lib/tsc"
direct_cache="$(HOME="$ambient" env -u XANTHAM_TSGO_EXE "$cli" tsc version)"
grep -Fq "$conflicting" <<<"$direct_cache"
(cd "$PRODUCT" && HOME="$ambient" node scripts/generate-candidate.mjs --backend xantham --config xantham/ansi-regex.json >/dev/null)
first="$(sha256sum "$PRODUCT/generated-candidates/xantham/proposal/AnsiRegex.fs" "$PRODUCT/generated-candidates/xantham/proposal/manifest.json" "$PRODUCT/generated-candidates/xantham/proposal/symbols.jsonl")"
(cd "$PRODUCT" && node scripts/generate-candidate.mjs --backend xantham --config xantham/ansi-regex.json >/dev/null)
test "$first" = "$(sha256sum "$PRODUCT/generated-candidates/xantham/proposal/AnsiRegex.fs" "$PRODUCT/generated-candidates/xantham/proposal/manifest.json" "$PRODUCT/generated-candidates/xantham/proposal/symbols.jsonl")"
test "$maintained_before" = "$(sha256sum "$PRODUCT/src/BindingsProduct/Bindings.fs" "$PRODUCT/declaration-lock.json" "$PRODUCT/binding-plan.json" "$PRODUCT/coverage-and-drift.json")"

fable="$PRODUCT/.nuget/xantham-tools/fable/fable"
if [[ ! -x "$fable" ]]; then (cd "$ROOT" && dotnet tool install Fable --version 5.13.0 --tool-path "$PRODUCT/.nuget/xantham-tools/fable" >/dev/null); fi
"$fable" "$PRODUCT/xantham/qualification/Runtime.fsproj" --outDir "$PRODUCT/.nuget/xantham-tools/pilot/runtime-dist" --noCache >/dev/null
grep -Eq '^import [A-Za-z0-9_]+ from "ansi-regex";' "$PRODUCT/.nuget/xantham-tools/pilot/runtime-dist/Program.js"
node "$PRODUCT/.nuget/xantham-tools/pilot/runtime-dist/Program.js" | grep -Fq 'PASS Xantham ANSI candidate'

proposal_before="$(sha256sum "$PRODUCT/generated-candidates/xantham/proposal/"*)"
failure_config() { jq "$1" "$PRODUCT/xantham/ansi-regex.json" >"$PRODUCT/.nuget/$2.json"; }
latest_report() { find "$PRODUCT/generated-candidates/xantham/runs" -mindepth 2 -maxdepth 2 -name run-report.json -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-; }
expect_rejected() {
  local config="$1" expected="$2"
  if (cd "$PRODUCT" && node scripts/generate-candidate.mjs --backend xantham --config ".nuget/$config.json" >/dev/null 2>&1); then echo "$config failure unexpectedly passed" >&2; exit 1; fi
  jq -e --arg expected "$expected" '.status == "rejected" and ((.process.limitTriggered == $expected) or any(.diagnostics[]; contains($expected))) and .maintainedWorkspace.unchanged == true' "$(latest_report)" >/dev/null
  test "$proposal_before" = "$(sha256sum "$PRODUCT/generated-candidates/xantham/proposal/"*)"
}
failure_config '.limits.timeoutSeconds = 0.001' timeout
expect_rejected timeout timeout
failure_config '.limits.outputBytes = 1' output
expect_rejected output output
failure_config '.limits.sampledProcessGroupRssBytes = 1' rss
expect_rejected rss sampled-process-group-rss
failure_config '.packageDirectory = "../outside"' invalid-path
expect_rejected invalid-path escapes
failure_config '.runtimeImport = "missing-import"' unresolved-import
expect_rejected unresolved-import 'does not resolve'
failure_config '.xanthamConfig = ".nuget/unmapped.json"' widening
printf '{}\n' >"$PRODUCT/.nuget/unmapped.json"
expect_rejected widening 'unaccepted widened or escape'
failure_config '.xanthamConfig = ".nuget/bad-mapping.json"' compile
printf '{"groups":{"typescript/lib":{"map":{"RegExp":"Missing.Type"}}}}\n' >"$PRODUCT/.nuget/bad-mapping.json"
expect_rejected compile 'did not compile'

bad_tools="$PRODUCT/.nuget/xantham-tools-bad"; cp -a "$PRODUCT/.nuget/xantham-tools" "$bad_tools"
jq '.generatorAssemblySha256 = "bad"' "$bad_tools/prepared.json" >"$bad_tools/prepared.tmp" && mv "$bad_tools/prepared.tmp" "$bad_tools/prepared.json"
if (cd "$PRODUCT" && node scripts/run-xantham.mjs --config xantham/ansi-regex.json --tool-dir .nuget/xantham-tools-bad >/dev/null 2>&1); then echo 'wrong tool fingerprint unexpectedly passed' >&2; exit 1; fi
jq -e '.status == "rejected" and any(.diagnostics[]; contains("generator assembly fingerprint"))' "$(latest_report)" >/dev/null

# Path defense fixture: an existing runs symlink is refused before any tool or fetched code executes.
mini="$WORK/mini"; mkdir -p "$mini/scripts/lib" "$mini/generated-candidates/xantham" "$WORK/outside"
cp "$PRODUCT/scripts/run-xantham.mjs" "$mini/scripts/"; cp "$PRODUCT/scripts/lib/xantham.mjs" "$mini/scripts/lib/"
ln -s "$WORK/outside" "$mini/generated-candidates/xantham/runs"
if node "$mini/scripts/run-xantham.mjs" --config xantham/ansi-regex.json >/dev/null 2>&1; then echo 'runs symlink unexpectedly accepted' >&2; exit 1; fi
test -z "$(find "$WORK/outside" -mindepth 1 -print -quit)"

test "$maintained_before" = "$(sha256sum "$PRODUCT/src/BindingsProduct/Bindings.fs" "$PRODUCT/declaration-lock.json" "$PRODUCT/binding-plan.json" "$PRODUCT/coverage-and-drift.json")"
echo 'PASS optional Xantham candidate is exact, bounded, repeatable, compiling, Fable/Node executable and isolated from maintained bindings'
