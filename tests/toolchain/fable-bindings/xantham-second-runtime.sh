#!/usr/bin/env bash
# Qualify one additional exact npm package through the delivered Xantham runner and real Node runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PRODUCT="$ROOT/templates/fs-gg-fable-bindings"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [[ ! -f "$PRODUCT/.nuget/xantham-tools/prepared.json" ]]; then
  (cd "$PRODUCT" && npm run xantham:prepare >/dev/null)
fi

maintained_before="$(sha256sum "$PRODUCT/src/BindingsProduct/Bindings.fs" "$PRODUCT/declaration-lock.json" "$PRODUCT/binding-plan.json" "$PRODUCT/coverage-and-drift.json")"
(cd "$PRODUCT" && node scripts/generate-candidate.mjs --backend xantham --config xantham/strip-ansi.json >/dev/null)
proposal=(
  "$PRODUCT/generated-candidates/xantham/strip-ansi-proposal/StripAnsi.fs"
  "$PRODUCT/generated-candidates/xantham/strip-ansi-proposal/manifest.json"
  "$PRODUCT/generated-candidates/xantham/strip-ansi-proposal/symbols.jsonl"
)
first="$(sha256sum "${proposal[@]}")"
report="$(find "$PRODUCT/generated-candidates/xantham/runs" -mindepth 2 -maxdepth 2 -name run-report.json -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
jq -e '
  .status == "proposal-ready" and .input.package.name == "strip-ansi" and
  .input.package.version == "7.1.2" and .verification.imports == "pass" and
  .verification.selectedSymbols == "pass" and .verification.fsharpCompile == "pass" and
  .maintainedWorkspace.unchanged == true and .findings.counts.exact == 1 and
  .findings.counts.ergonomic == 0 and .findings.counts.widened == 0 and
  .findings.counts.escape == 0 and .process.limitTriggered == null
' "$report" >/dev/null
(cd "$PRODUCT" && node scripts/generate-candidate.mjs --backend xantham --config xantham/strip-ansi.json >/dev/null)
test "$first" = "$(sha256sum "${proposal[@]}")"

fable="$PRODUCT/.nuget/xantham-tools/fable/fable"
if [[ ! -x "$fable" ]]; then
  dotnet tool install Fable --version 5.13.0 --tool-path "$PRODUCT/.nuget/xantham-tools/fable" >/dev/null
fi
out="$PRODUCT/.nuget/xantham-tools/pilot/strip-ansi-runtime-dist"
"$fable" "$PRODUCT/xantham/qualification/StripAnsi.fsproj" --outDir "$out" --noCache >/dev/null
grep -Fq 'from "strip-ansi"' "$out/StripAnsiProgram.js"
node "$out/StripAnsiProgram.js" | grep -Fq 'PASS Xantham strip-ansi ANSI and plain-text runtime witness'
test "$maintained_before" = "$(sha256sum "$PRODUCT/src/BindingsProduct/Bindings.fs" "$PRODUCT/declaration-lock.json" "$PRODUCT/binding-plan.json" "$PRODUCT/coverage-and-drift.json")"

dotnet pack "$ROOT/FS.GG.Templates.csproj" --nologo -o "$WORK/package" >/dev/null
archive="$(find "$WORK/package" -name 'FS.GG.Workspace.Template.*.nupkg' -print -quit)"
members="$WORK/members.txt"
unzip -Z1 "$archive" >"$members"
for member in \
  content/templates/fs-gg-fable-bindings/xantham/strip-ansi.json \
  content/templates/fs-gg-fable-bindings/xantham/strip-ansi.xantham.json \
  content/templates/fs-gg-fable-bindings/xantham/qualification/StripAnsi.fsproj \
  content/templates/fs-gg-fable-bindings/xantham/qualification/StripAnsiProgram.fs \
  content/templates/fs-gg-fable-bindings/generated-candidates/xantham/strip-ansi-proposal/StripAnsi.fs; do
  grep -Fxq "$member" "$members"
done

echo 'PASS Xantham second npm package is exact, deterministic, Fable/Node executable and packed'
