#!/usr/bin/env bash
# Reproducible qualification gate for declaration-to-curated-Fable workflow.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SPIKE="$ROOT/spikes/fable-bindings"
DOC="$ROOT/docs/fable-bindings-toolchain.md"

test "$(dotnet --version)" = "10.0.302"
test "$(node --version)" = "v26.5.0"
test "$(npm --version)" = "12.0.1"
test -f "$SPIKE/package-lock.json"
test -f "$SPIKE/declaration-lock.json"
grep -Fq '"@babylonjs/core": "9.19.0"' "$SPIKE/package.json"
grep -Fq 'sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==' "$SPIKE/package-lock.json"
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
mkdir -p "$fixture/node_modules/example"
printf '%s\n' 'import "./side.js"; export {};' > "$fixture/node_modules/example/entry.d.ts"
printf '%s\n' 'export declare const original: string;' > "$fixture/node_modules/example/side.d.ts"
node "$SPIKE/scripts/lock-declarations.mjs" --declarations-root "$fixture/node_modules" --entry example/entry.d.ts --lock "$fixture/lock.json" --write >/dev/null
printf '%s\n' 'export declare const changed: string;' > "$fixture/node_modules/example/side.d.ts"
if node "$SPIKE/scripts/lock-declarations.mjs" --declarations-root "$fixture/node_modules" --entry example/entry.d.ts --lock "$fixture/lock.json"; then
  echo "transitive declaration drift unexpectedly passed" >&2
  exit 1
fi

# Install the packed Fable library and npm runtime in a clean consumer root.
consumer="$(mktemp -d)"
mkdir -p "$consumer/app" "$consumer/feed"
dotnet build "$SPIKE/BabylonBindings.fsproj" -c Release --no-restore >/dev/null
dotnet pack "$SPIKE/BabylonBindings.fsproj" -c Release --no-restore -o "$consumer/feed" >/dev/null
printf '%s\n' '<configuration><packageSources><clear /><add key="local" value="'"$consumer"'/feed" /><add key="nuget.org" value="https://api.nuget.org/v3/index.json" /></packageSources></configuration>' > "$consumer/app/NuGet.Config"
printf '%s\n' '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>netstandard2.1</TargetFramework><RestorePackagesWithLockFile>true</RestorePackagesWithLockFile></PropertyGroup><ItemGroup><Compile Include="Program.fs" /><PackageReference Include="Qualification.BabylonBindings" Version="0.0.1-spike" /><PackageReference Include="Fable.Core" Version="5.2.0" /></ItemGroup></Project>' > "$consumer/app/Consumer.fsproj"
printf '%s\n' 'open Qualification.Babylon' 'let engine = nullEngine ()' 'let scene = scene engine' 'let _ = box "consumer-box" scene' 'initialiseLoader ()' 'printfn "consumer passed"' > "$consumer/app/Program.fs"
printf '%s\n' '{"private":true,"type":"module","dependencies":{"@babylonjs/core":"9.19.0","@babylonjs/loaders":"9.19.0"}}' > "$consumer/app/package.json"
dotnet restore "$consumer/app/Consumer.fsproj" --configfile "$consumer/app/NuGet.Config" >/dev/null
(cd "$consumer/app" && npm install --ignore-scripts >/dev/null)
grep -Fq 'sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==' "$consumer/app/package-lock.json"
dotnet tool install Fable --tool-path "$consumer/fable" --version 5.13.0 >/dev/null
"$consumer/fable/fable" "$consumer/app/Consumer.fsproj" --outDir "$consumer/app/dist" --noCache >/dev/null
node "$consumer/app/dist/Program.js"

echo "PASS Fable declaration closure, tracked candidate, and isolated NuGet/npm consumer gate"
