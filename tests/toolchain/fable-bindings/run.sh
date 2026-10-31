#!/usr/bin/env bash
# Reproducible qualification gate for declaration-to-curated-Fable workflow.
#
# Prerequisites: SDK, Node and npm at the pins below, jq, network for npm/NuGet restore, and
# FSGG_PYTHON_COORDINATION_ROOT naming a checkout of FS-GG/FS.GG.Coordination at the commit
# recorded in eng/portable-workspace/python-fixture-source.json. The Xantham step
# (xantham-second-runtime.sh) packs FS.GG.Templates.csproj, and that pack refuses to run
# without it. The composition workflow checks out the same fixture.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SPIKE="$ROOT/spikes/fable-bindings"
DOC="$ROOT/docs/fable-bindings-toolchain.md"

# Exact toolchain pins (docs/fable-bindings-toolchain.md). The Fable tool and Fable.Core
# selections are read from the spike's own manifests so the consumer below cannot drift
# onto an older pair than the library it consumes.
# global.json pins 10.0.403 with rollForward latestPatch, so admit exactly what it admits:
# a 10.0.4xx SDK whose patch is at least 03.
sdk="$(cd "$SPIKE" && dotnet --version)"
[[ "$sdk" =~ ^10\.0\.4([0-9][0-9])$ ]] && (( 10#${BASH_REMATCH[1]} >= 3 )) || { echo "SDK $sdk is not admitted by spikes/fable-bindings/global.json (10.0.403, latestPatch)" >&2; exit 1; }
jq -e '.sdk.version == "10.0.403" and .sdk.rollForward == "latestPatch"' "$SPIKE/global.json" >/dev/null
test "$(node --version)" = "v26.13.0"
test "$(npm --version)" = "12.2.1"
fable_version="$(jq -r '.tools.fable.version' "$SPIKE/.config/dotnet-tools.json")"
core_version="$(sed -n 's/.*Include="Fable.Core" Version="\([^"]*\)".*/\1/p' "$SPIKE/Directory.Packages.props")"
test "$fable_version" = "5.26.0"
test "$core_version" = "5.6.1"
grep -Fq "| Fable tool / Fable.Core | $fable_version / $core_version |" "$DOC"
test -f "$SPIKE/package-lock.json"
test -f "$SPIKE/declaration-lock.json"
grep -Fq '"@babylonjs/core": "9.33.1"' "$SPIKE/package.json"
jq -e '.npmArtifacts == [{"name":"@babylonjs/core","version":"9.33.1"},{"name":"@babylonjs/loaders","version":"9.33.1"}]' "$SPIKE/corpus.json" >/dev/null
grep -Fq 'sha512-NoIfREw4QeoXzRPpXnbUpmxxPIjuRi9iS4xFDbPgXHiLwCeHSI13DJHF8YB2gKHp6rA6T5R7BAevPvWHklvXWQ==' "$SPIKE/package-lock.json"
grep -Fq 'Glutinum.Template@1.1.1' "$DOC"
grep -Fq 'ts2fable is legacy comparison input only' "$DOC"
grep -Fq 'can never overwrite' "$DOC"
grep -Fq 'advance the' "$DOC"

(cd "$SPIKE" && npm ci --ignore-scripts >/dev/null && npm run check:drift && npm run test:runtime)

# Fable compilation is the emitted-import proof; Node executes that exact output.
(cd "$SPIKE" && dotnet tool restore >/dev/null && dotnet fable runtime/RuntimeSmoke.fsproj --outDir runtime/dist --noCache >/dev/null && node runtime/dist/Program.js)

candidate="$SPIKE/generated-candidates/BabylonBindings.generated.fs"
proposal="$SPIKE/generated-candidates/BabylonBindings.proposal.md"
before="$(sha256sum "$SPIKE/src/BabylonBindings.fs" "$SPIKE/declaration-lock.json")"
(cd "$SPIKE" && npm run generate:candidate >/dev/null)
after="$(sha256sum "$SPIKE/src/BabylonBindings.fs" "$SPIKE/declaration-lock.json")"
test "$before" = "$after"
test -f "$candidate"
test -f "$proposal"
git -C "$ROOT" ls-files --error-unmatch "spikes/fable-bindings/generated-candidates/BabylonBindings.generated.fs" "spikes/fable-bindings/generated-candidates/BabylonBindings.proposal.md" >/dev/null
git -C "$ROOT" diff --exit-code -- "spikes/fable-bindings/generated-candidates/"

# A tiny fixture proves the lock follows relative declaration imports/exports.
fixture="$(mktemp -d)"
consumer=""
trap 'rm -rf "$fixture" ${consumer:+"$consumer"}' EXIT
mkdir -p "$fixture/node_modules/example"
printf '%s\n' 'import "./side.js"; export {};' > "$fixture/node_modules/example/entry.d.ts"
printf '%s\n' 'export declare const original: string;' > "$fixture/node_modules/example/side.d.ts"
node "$SPIKE/scripts/lock-declarations.mjs" --declarations-root "$fixture/node_modules" --entry example/entry.d.ts --lock "$fixture/lock.json" --write >/dev/null
printf '%s\n' 'export declare const changed: string;' > "$fixture/node_modules/example/side.d.ts"
if node "$SPIKE/scripts/lock-declarations.mjs" --declarations-root "$fixture/node_modules" --entry example/entry.d.ts --lock "$fixture/lock.json"; then
  echo "transitive declaration drift unexpectedly passed" >&2
  exit 1
fi
bash "$ROOT/tests/toolchain/fable-bindings/closure-scanner-fixture.sh" "$SPIKE/scripts/lock-declarations.mjs"

# Install the packed Fable library and npm runtime in a clean consumer root.
consumer="$(mktemp -d)"
mkdir -p "$consumer/app" "$consumer/feed"
dotnet build "$SPIKE/BabylonBindings.fsproj" -c Release --no-restore >/dev/null
dotnet pack "$SPIKE/BabylonBindings.fsproj" -c Release --no-restore -o "$consumer/feed" >/dev/null
printf '%s\n' '<configuration><packageSources><clear /><add key="local" value="'"$consumer"'/feed" /><add key="nuget.org" value="https://api.nuget.org/v3/index.json" /></packageSources></configuration>' > "$consumer/app/NuGet.Config"
printf '%s\n' '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>netstandard2.1</TargetFramework><RestorePackagesWithLockFile>true</RestorePackagesWithLockFile></PropertyGroup><ItemGroup><Compile Include="Program.fs" /><PackageReference Include="Qualification.BabylonBindings" Version="0.0.1-spike" /><PackageReference Include="Fable.Core" Version="'"$core_version"'" /></ItemGroup></Project>' > "$consumer/app/Consumer.fsproj"
printf '%s\n' 'open Qualification.Babylon' 'let engine = nullEngine ()' 'let scene = scene engine' 'let _ = box "consumer-box" scene' 'initialiseLoader ()' 'printfn "consumer passed"' > "$consumer/app/Program.fs"
printf '%s\n' '{"private":true,"type":"module","dependencies":{"@babylonjs/core":"9.33.1","@babylonjs/loaders":"9.33.1"}}' > "$consumer/app/package.json"
dotnet restore "$consumer/app/Consumer.fsproj" --configfile "$consumer/app/NuGet.Config" >/dev/null
(cd "$consumer/app" && npm install --ignore-scripts >/dev/null)
grep -Fq 'sha512-NoIfREw4QeoXzRPpXnbUpmxxPIjuRi9iS4xFDbPgXHiLwCeHSI13DJHF8YB2gKHp6rA6T5R7BAevPvWHklvXWQ==' "$consumer/app/package-lock.json"
dotnet tool install Fable --tool-path "$consumer/fable" --version "$fable_version" >/dev/null
"$consumer/fable/fable" "$consumer/app/Consumer.fsproj" --outDir "$consumer/app/dist" --noCache >/dev/null
node "$consumer/app/dist/Program.js"

echo "PASS Fable declaration closure, tracked candidate, and isolated NuGet/npm consumer gate"
bash "$ROOT/tests/toolchain/fable-bindings/xantham-run.sh"
