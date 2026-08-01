#!/usr/bin/env bash
# Template-owned structural proof. Runtime calls require the consumer's selected npm package.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export DOTNET_CLI_HOME="$WORK/home" DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
mkdir -p "$DOTNET_CLI_HOME"

dotnet pack "$ROOT/FS.GG.Templates.csproj" -c Release -o "$WORK/feed" >/dev/null
dotnet new install "$WORK/feed"/*.nupkg >/dev/null
dotnet new fs-gg-fable-bindings -o "$WORK/product" --name AcmeBindings --productName AcmeBindings --rootNamespace AcmeBindings --npmPackage=@babylonjs/core --npmVersion 9.19.0 --bindingTarget browser >/dev/null
if dotnet new fs-gg-fable-bindings -o "$WORK/rejected" --name Rejected --npmPackage other --npmVersion 1.0.0 --bindingTarget node >/dev/null 2>&1; then echo "unqualified corpus unexpectedly accepted" >&2; exit 1; fi

for f in declaration-lock.json coverage-and-drift.json package.json src/AcmeBindings/AcmeBindings.fsproj tests/AcmeBindings.CompileTests/AcmeBindings.CompileTests.fsproj samples/Consumer/README.md; do test -f "$WORK/product/$f"; done
cmp "$ROOT/skills/fable-bindings/SKILL.md" "$WORK/product/.agents/skills/fable-bindings/SKILL.md"
grep -Fq '"@babylonjs/core": "9.19.0"' "$WORK/product/package.json"
grep -Fq '@babylonjs/core/Engines/nullEngine.d.ts' "$WORK/product/declaration-lock.json"
grep -Fq 'ImportAll("@babylonjs/loaders/glTF/index.js")' "$WORK/product/src/AcmeBindings/Bindings.fs"
grep -Fq 'GENERATED CANDIDATE — NOT COMPILED' "$WORK/product/generated-candidates/BabylonBindings.generated.fs"

(cd "$WORK/product" && git init -q && git config user.email test@example.invalid && git config user.name test && git add generated-candidates && git commit -qm baseline && npm ci --ignore-scripts >/dev/null && npm run doctor >/dev/null && npm run check:drift >/dev/null && npm run test:runtime >/dev/null)
solution="$(find "$WORK/product" -maxdepth 1 -name '*.slnx' -print -quit)"
dotnet restore "$solution" --locked-mode
dotnet build "$solution" --no-restore
# The generated library must survive the same isolation a real consumer has: a packed nupkg,
# a fresh local feed, a separately installed npm runtime, Fable emission, and Node execution.
consumer="$WORK/consumer"; mkdir -p "$consumer/app" "$consumer/feed"
dotnet build "$WORK/product/src/AcmeBindings/AcmeBindings.fsproj" -c Release >/dev/null
dotnet pack "$WORK/product/src/AcmeBindings/AcmeBindings.fsproj" -c Release --no-build -o "$consumer/feed" >/dev/null
printf '%s\n' '<configuration><packageSources><clear /><add key="local" value="'"$consumer"'/feed" /><add key="nuget.org" value="https://api.nuget.org/v3/index.json" /></packageSources></configuration>' > "$consumer/app/NuGet.Config"
printf '%s\n' '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>netstandard2.1</TargetFramework><RestorePackagesWithLockFile>true</RestorePackagesWithLockFile></PropertyGroup><ItemGroup><Compile Include="Program.fs" /><PackageReference Include="AcmeBindings" Version="0.1.0" /><PackageReference Include="Fable.Core" Version="5.2.0" /></ItemGroup></Project>' > "$consumer/app/Consumer.fsproj"
printf '%s\n' 'open Qualification.Babylon' 'let engine = nullEngine ()' 'let scene = scene engine' 'let _ = box "consumer-box" scene' 'initialiseLoader ()' 'printfn "consumer passed"' > "$consumer/app/Program.fs"
printf '%s\n' '{"private":true,"type":"module","dependencies":{"@babylonjs/core":"9.19.0","@babylonjs/loaders":"9.19.0"}}' > "$consumer/app/package.json"
dotnet restore "$consumer/app/Consumer.fsproj" --configfile "$consumer/app/NuGet.Config" >/dev/null
(cd "$consumer/app" && npm install --ignore-scripts >/dev/null)
grep -Fq 'sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==' "$consumer/app/package-lock.json"
dotnet tool install Fable --tool-path "$consumer/fable" --version 5.13.0 >/dev/null
"$consumer/fable/fable" "$consumer/app/Consumer.fsproj" --outDir "$consumer/app/dist" --noCache >/dev/null
node "$consumer/app/dist/Program.js" | grep -Fq 'consumer passed'
before="$(sha256sum "$WORK/product/src/AcmeBindings/Bindings.fs" "$WORK/product/declaration-lock.json")"
(cd "$WORK/product" && npm run generate:candidate >/dev/null)
test "$before" = "$(sha256sum "$WORK/product/src/AcmeBindings/Bindings.fs" "$WORK/product/declaration-lock.json")"
git -C "$WORK/product" diff --exit-code -- generated-candidates
# A changed declaration lock produces a review-visible tracked candidate diff without modifying src.
printf '\n' >> "$WORK/product/declaration-lock.json"
(cd "$WORK/product" && npm run generate:candidate >/dev/null)
git -C "$WORK/product" diff --quiet -- generated-candidates && { echo "candidate was not review-visible" >&2; exit 1; }

# Real Chromium exercises the browser module imports and the narrow Babylon scene route.
(cd "$WORK/product" && python3 -m http.server 4173 >"$WORK/browser-server.log" 2>&1 & echo $! >"$WORK/browser.pid")
trap 'kill "$(cat "$WORK/browser.pid" 2>/dev/null)" 2>/dev/null || true; rm -rf "$WORK"' EXIT
sleep 1
chromium --headless --no-sandbox --disable-gpu --virtual-time-budget=3000 --dump-dom http://127.0.0.1:4173/runtime/browser/ >"$WORK/browser.html" 2>"$WORK/browser.log"
grep -Fq 'Babylon browser smoke passed' "$WORK/browser.html"

# The closure algorithm also rejects a changed transitive declaration, not just entry points.
fixture="$WORK/fixture"; mkdir -p "$fixture/node_modules/example"
printf '%s\n' 'import "./side.js"; export {};' > "$fixture/node_modules/example/entry.d.ts"
printf '%s\n' 'export declare const original: string;' > "$fixture/node_modules/example/side.d.ts"
node "$WORK/product/scripts/lock-declarations.mjs" --declarations-root "$fixture/node_modules" --entry example/entry.d.ts --lock "$fixture/lock.json" --write >/dev/null
printf '%s\n' 'export declare const changed: string;' > "$fixture/node_modules/example/side.d.ts"
if node "$WORK/product/scripts/lock-declarations.mjs" --declarations-root "$fixture/node_modules" --entry example/entry.d.ts --lock "$fixture/lock.json"; then exit 1; fi
echo 'PASS fable-bindings template executes locked declaration, candidate, Node and real-browser evidence'
