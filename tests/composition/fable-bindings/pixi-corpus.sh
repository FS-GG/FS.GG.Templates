#!/usr/bin/env bash
# The PixiJS corpus of the fs-gg-fable-bindings template (FS.GG.Templates#808).
#
# Run by tests/composition/fable-bindings/run.sh after the Babylon leg, against the SAME installed
# template archive: `--npmPackage=pixi.js --npmVersion 8.22.0` delivers the corpora/pixi/ files over
# the Babylon root files. This leg proves the evidence classes the Babylon leg proves, on that
# product: locked restore, doctor, drift (including the transitive negative), the side-effect
# negative control, Node imports of every entry point, the Fable-emitted 2D journey in Node and in
# Chromium, candidate stability, and a packed clean consumer with the exact npm integrity.
#
#   usage: pixi-corpus.sh <work directory>      (DOTNET_CLI_HOME already holds the installed template)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="${1:?usage: pixi-corpus.sh <work directory>}"
product="$WORK/pixi-product"
PIXI_INTEGRITY='sha512-QbTANHMZ751MIjLiLSUSM8a7LNMWwMIf0KbRCqlW+SPS9hNLfSVS+cl1O2SEp9g1K/wyLzj/OJHv+1TUfiPr/w=='

dotnet new fs-gg-fable-bindings -o "$product" --name AcmePixi --productName AcmePixi --rootNamespace AcmePixi --npmPackage=pixi.js --npmVersion 8.22.0 --bindingTarget browser >/dev/null
if dotnet new fs-gg-fable-bindings -o "$WORK/pixi-rejected" --name Rejected --npmPackage=other --npmVersion 1.0.0 >/dev/null 2>&1; then echo "unqualified corpus unexpectedly accepted" >&2; exit 1; fi

# ── The Pixi corpus replaced the Babylon files; nothing of the overlay mechanism leaks ────────
for f in corpus.json declaration-lock.json binding-plan.json coverage-and-drift.json generated-candidates/declaration-analysis.json generated-candidates/PixiBindings.generated.fs generated-candidates/PixiBindings.proposal.md package.json package-lock.json src/AcmePixi/AcmePixi.fsproj src/AcmePixi/Bindings.fs src/AcmePixi/packages.lock.json tests/AcmePixi.CompileTests/Program.fs tests/AcmePixi.CompileTests/packages.lock.json runtime/browser/index.html runtime/node/smoke.mjs runtime/node/without-loader.mjs scripts/browser-smoke.mjs; do test -f "$product/$f" || { echo "pixi product is missing $f" >&2; exit 1; }; done
test ! -e "$product/corpora" || { echo "the corpora/ overlay directory reached the product" >&2; exit 1; }
if ls "$product"/generated-candidates/BabylonBindings.* >/dev/null 2>&1; then echo "Babylon candidates reached the Pixi product" >&2; exit 1; fi
if grep -rqiF 'babylon' "$product" --include='*.fs' --include='*.fsproj' --include='*.json' --include='*.mjs' --include='*.html' --include='*.md' --exclude-dir=node_modules --exclude-dir=xantham --exclude-dir=.agents --exclude-dir=.git --exclude=package-lock.json --exclude=declaration-analysis.json; then
  grep -rniF 'babylon' "$product" --include='*.fs' --include='*.fsproj' --include='*.json' --include='*.mjs' --include='*.html' --include='*.md' --exclude-dir=node_modules --exclude-dir=xantham --exclude-dir=.agents --exclude-dir=.git --exclude=package-lock.json --exclude=declaration-analysis.json | head >&2
  echo "the Pixi product still names Babylon" >&2; exit 1
fi
dotnet fsi "$ROOT/scripts/generate-skill-manifest.fsx" --assert-product "$product" --template fs-gg-fable-bindings
jq -e '.id == "pixi-2d-renderer" and .npmArtifacts == [{"name":"pixi.js","version":"8.22.0"}] and .declarationEntryPoints == ["pixi.js/lib/index.d.ts","pixi.js/lib/events/init.d.ts"] and .candidateStem == "PixiBindings"' "$product/corpus.json" >/dev/null
jq -e '.dependencies == {"pixi.js":"8.22.0"}' "$product/package.json" >/dev/null
jq -e '.package == "pixi.js@8.22.0" and (.files | length) == 688 and (.files | all(.sha256 | test("^[0-9a-f]{64}$"))) and (.externalModules | sort) == ["*.frag","*.vert","*.wgsl","@pixi/colord","earcut","eventemitter3","tiny-lru"] and (.nonDeclarationAssets | length) == 23' "$product/declaration-lock.json" >/dev/null
jq -e --arg integrity "$PIXI_INTEGRITY" '.packages["node_modules/pixi.js"] | .version == "8.22.0" and .integrity == $integrity' "$product/package-lock.json" >/dev/null
grep -Fq 'ImportAll("pixi.js/events")' "$product/src/AcmePixi/Bindings.fs"
grep -Fq 'GENERATED CANDIDATE — NOT COMPILED' "$product/generated-candidates/PixiBindings.generated.fs"
python3 - "$product" <<'PY_PIXI_PROJECT'
import json, pathlib, sys, xml.etree.ElementTree as ET
product = pathlib.Path(sys.argv[1])
project = ET.parse(product / 'src/AcmePixi/AcmePixi.fsproj').getroot()
assert project.findtext('./PropertyGroup/FablePackageType') == 'binding', 'binding package type'
assert 'fable-javascript' in project.findtext('./PropertyGroup/PackageTags', '').split(';'), 'JavaScript target'
npm = project.findall('./PropertyGroup/NpmDependencies/NpmPackage')
assert {e.get('Name'): e.get('Version') for e in npm} == {'pixi.js': '8.22.0'} and len(npm) == 1, 'exact Femto metadata'
PY_PIXI_PROJECT

# ── Locked restore, doctor, drift, side-effect control, imports, Fable-emitted journey ────────
(cd "$product" && git init -q && git config user.email test@example.invalid && git config user.name test && git add generated-candidates && git commit -qm baseline \
  && npm ci --ignore-scripts >/dev/null && npm run doctor >/dev/null && npm run check:drift >/dev/null && npm run test:side-effect-control >/dev/null && npm run test:imports >/dev/null \
  && dotnet tool restore >/dev/null && npm run compile:fable >/dev/null && npm run test:runtime | tee "$WORK/pixi-runtime.log" | grep -Fq 'curated Pixi binding compile smoke passed')
grep -Fq 'headless workload sprites=1000 children=1000 bounds=398x248 tickerFrames=61' "$WORK/pixi-runtime.log"
# Cost shape (performance-first): a binding call is emitted as the native member call itself, with no
# wrapper layer, no closure and no allocation of its own, and the binding ships no JavaScript module.
emitted="$product/runtime/fable-dist/Program.js"
grep -Fq 'world.addChild(s);' "$emitted"
grep -Fq 's.position.set(((i % columns) * 10), (~~(i / columns) * 10));' "$emitted"
grep -Fq 's.tint = (65793 * (i % 255));' "$emitted"
test -z "$(find "$product/runtime/fable-dist/src" -name '*.js' -print -quit 2>/dev/null)" || { echo "the binding emitted a JavaScript module of its own" >&2; exit 1; }
solution="$(find "$product" -maxdepth 1 -name '*.slnx' -print -quit)"
dotnet restore "$solution" --locked-mode >/dev/null
dotnet build "$solution" --no-restore >/dev/null

# ── Chromium: the same emitted program, plus a real WebGL Application ─────────────────────────
(cd "$product" && npm run test:browser | tee "$WORK/pixi-browser.log" | grep -Fxq 'Pixi browser smoke passed')
grep -Fq 'browser workload stageChildren=3' "$WORK/pixi-browser.log"
grep -E '^\[page log\] webgl device=' "$WORK/pixi-browser.log"
# Opt-in hardware run (a host with a GPU): FSGG_BROWSER_GPU_ARGS holds the Chromium flags, for example
# "--headless=new --use-angle=vulkan --enable-features=Vulkan --ignore-gpu-blocklist". The same
# emitted program must pass on a device that is not SwiftShader, and the device is recorded.
if [[ -n "${FSGG_BROWSER_GPU_ARGS:-}" ]]; then
  (cd "$product" && BROWSER_SMOKE_ARGS="$FSGG_BROWSER_GPU_ARGS" npm run test:browser | tee "$WORK/pixi-browser-gpu.log" | grep -Fxq 'Pixi browser smoke passed')
  grep -E '^\[page log\] webgl device=' "$WORK/pixi-browser-gpu.log"
  if grep -Fqi 'swiftshader' "$WORK/pixi-browser-gpu.log"; then echo "the hardware run used SwiftShader" >&2; exit 1; fi
fi
# The driver fails (not hangs) on a page that never reports, and on a page that reports something else.
if (cd "$product" && node scripts/browser-smoke.mjs --expect 'never reported' --timeout 15000 >/dev/null 2>&1); then echo "browser driver accepted an unexpected result" >&2; exit 1; fi

# ── Drift: a changed transitive declaration reds the gate, restoring the pin greens it ─────────
printf '\n// upstream drift acceptance mutation\n' >> "$product/node_modules/pixi.js/lib/ticker/Ticker.d.ts"
if (cd "$product" && npm run check:drift >/dev/null 2>&1); then echo "pixi.js declaration drift unexpectedly passed" >&2; exit 1; fi
(cd "$product" && npm ci --ignore-scripts >/dev/null && npm run check:drift >/dev/null)
# A mixin reached only through a /// <reference path> is part of the hashed closure.
printf '\n// reference mixin drift mutation\n' >> "$product/node_modules/pixi.js/lib/scene/graphics/GraphicsMixins.d.ts"
if (cd "$product" && npm run check:drift >/dev/null 2>&1); then echo "pixi.js reference-mixin drift unexpectedly passed" >&2; exit 1; fi
(cd "$product" && npm ci --ignore-scripts >/dev/null && npm run check:drift >/dev/null)
# The scanner's edge, asset and external-module rules hold for the product's own script.
bash "$ROOT/tests/toolchain/fable-bindings/closure-scanner-fixture.sh" "$product/scripts/lock-declarations.mjs"

# ── Candidates are stable and review-visible ───────────────────────────────────────────────────
before="$(sha256sum "$product/src/AcmePixi/Bindings.fs" "$product/declaration-lock.json")"
(cd "$product" && npm run generate:candidate >/dev/null)
test "$before" = "$(sha256sum "$product/src/AcmePixi/Bindings.fs" "$product/declaration-lock.json")"
git -C "$product" diff --exit-code -- generated-candidates

# ── The doctor keeps corpus, pair and curation coherent ────────────────────────────────────────
mutate_doctor() { # <file> <jq filter or sed expression kind> ...  (restores the file afterwards)
  local file="$1" label="$2"; shift 2
  cp "$product/$file" "$WORK/pixi-doctor.orig"
  "$@"
  if cmp -s "$product/$file" "$WORK/pixi-doctor.orig"; then echo "doctor mutation '$label' did not apply" >&2; exit 1; fi
  if (cd "$product" && npm run doctor >/dev/null 2>&1); then echo "doctor accepted: $label" >&2; exit 1; fi
  cp "$WORK/pixi-doctor.orig" "$product/$file"
}
retarget() { jq "$1" "$WORK/pixi-doctor.orig" > "$product/$2"; }
mutate_doctor coverage-and-drift.json 'a recorded external module without a curation row' retarget '.externalModules |= map(select(.module != "eventemitter3"))' coverage-and-drift.json
mutate_doctor coverage-and-drift.json 'an external module curated at another version' retarget '(.externalModules[] | select(.module == "earcut") | .version) = "0.0.1"' coverage-and-drift.json
mutate_doctor coverage-and-drift.json 'an external module curated at another integrity' retarget '(.externalModules[] | select(.module == "tiny-lru") | .integrity) = "sha512-AAAA"' coverage-and-drift.json
mutate_doctor coverage-and-drift.json 'an external module with no reason' retarget '(.externalModules[] | select(.module == "@pixi/colord") | .reason) = ""' coverage-and-drift.json
mutate_doctor corpus.json 'a corpus pin that disagrees with package.json' retarget '.npmArtifacts[0].version = "8.22.1"' corpus.json
mutate_doctor scaffold-provenance.json 'a requested pair that is not the delivered corpus' retarget '.requestedCorpus.npmVersion = "9.33.1"' scaffold-provenance.json
mutate_doctor src/AcmePixi/AcmePixi.fsproj 'Femto NpmDependencies at another version' sed -i 's|<NpmPackage Name="pixi.js" Version="8.22.0" />|<NpmPackage Name="pixi.js" Version="8.22.1" />|' "$product/src/AcmePixi/AcmePixi.fsproj"
(cd "$product" && npm run doctor >/dev/null)
# An asked-for pair that the template cannot deliver fails the product's own doctor.
dotnet new fs-gg-fable-bindings -o "$WORK/pixi-mismatch" --name Mismatch --npmPackage=pixi.js --npmVersion 9.33.1 >/dev/null
(cd "$WORK/pixi-mismatch" && npm ci --ignore-scripts >/dev/null)
if (cd "$WORK/pixi-mismatch" && npm run doctor >/dev/null 2>&1); then echo "doctor accepted pixi.js with the Babylon version" >&2; exit 1; fi

# ── The packed binding survives a genuinely clean consumer ─────────────────────────────────────
consumer="$WORK/pixi-consumer"; mkdir -p "$consumer/app" "$consumer/feed"
dotnet build "$product/src/AcmePixi/AcmePixi.fsproj" -c Release >/dev/null
dotnet pack "$product/src/AcmePixi/AcmePixi.fsproj" -c Release --no-build -o "$consumer/feed" >/dev/null
python3 -I "$ROOT/tests/composition/fable-bindings/inspect-binding-package.py" "$consumer/feed/AcmePixi.0.1.0.nupkg" AcmePixi 0.1.0 AcmePixi.dll --self-test
core_version="$(sed -n 's/.*Include="Fable.Core" Version="\([^"]*\)".*/\1/p' "$product/Directory.Packages.props")"
fable_version="$(jq -r '.tools.fable.version' "$product/.config/dotnet-tools.json")"
[[ "$core_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$fable_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
printf '%s\n' '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>netstandard2.1</TargetFramework><RestorePackagesWithLockFile>true</RestorePackagesWithLockFile></PropertyGroup><ItemGroup><Compile Include="Program.fs" /><PackageReference Include="AcmePixi" Version="0.1.0" /><PackageReference Include="Fable.Core" Version="'"$core_version"'" /></ItemGroup></Project>' > "$consumer/app/Consumer.fsproj"
printf '%s\n' '<configuration><packageSources><clear /><add key="local" value="'"$consumer"'/feed" /><add key="nuget.org" value="https://api.nuget.org/v3/index.json" /></packageSources></configuration>' > "$consumer/app/NuGet.Config"
cat > "$consumer/app/Program.fs" <<'FS_PIXI_CONSUMER'
open Qualification.Pixi

enableEvents ()
if not (eventsRegistered ()) then failwith "packed binding pixi.js/events import did not register the event mixin"
let world: Container = container ()
let square: Sprite = sprite (whiteTexture ())
let shape: Graphics = graphics ()
let label: Text = text "consumer" 0xffffff 16. "monospace"
let clock: Ticker = ticker ()
if isNull world || isNull square || isNull shape || isNull label || isNull clock then
    failwith "packed binding returned a missing native object"
setSize square 8. 8.
setPosition square 3. 4.
rect shape 0. 0. 20. 10.
fill shape 0x3366cc 1.
addChild world square
addChild world shape
addChild world label
if childCount world <> 3 then failwith "packed binding did not add the children"
let bounds = boundsOf square
if rectangleWidth bounds <> 8. || rectangleX bounds <> 3. then failwith "packed binding sprite bounds are wrong"
setEventMode shape "static"
let hits = ref 0
let listener (_: FederatedPointerEvent) = hits.Value <- hits.Value + 1
// `listener` and `step` are module-level functions, so only the returned subscription can remove them.
let tap = onEvent shape "pointertap" listener
emitEvent shape "pointertap" 1 |> ignore
offEvent shape "pointertap" tap
emitEvent shape "pointertap" 1 |> ignore
let frames = ref 0
let step (_: Ticker) = frames.Value <- frames.Value + 1
let tick = addTicker clock step
updateTicker clock 1000.
updateTicker clock 1016.
removeTicker clock tick
updateTicker clock 1032.
if hits.Value <> 1 || frames.Value <> 2 || tickerListenerCount clock <> 0 then failwith "packed binding events or ticker did not run"
printfn "consumer passed"
FS_PIXI_CONSUMER
cp "$product/package.json" "$product/package-lock.json" "$consumer/app/"
(
  export NUGET_PACKAGES="$consumer/packages" DOTNET_CLI_HOME="$consumer/home"
  mkdir -p "$DOTNET_CLI_HOME"
  dotnet restore "$consumer/app/Consumer.fsproj" --configfile "$consumer/app/NuGet.Config" >/dev/null
  (cd "$consumer/app" && npm ci --ignore-scripts >/dev/null)
  grep -Fq "$PIXI_INTEGRITY" "$consumer/app/package-lock.json"
  dotnet tool install Fable --tool-path "$consumer/fable" --version "$fable_version" >/dev/null
  "$consumer/fable/fable" "$consumer/app/Consumer.fsproj" --outDir "$consumer/app/dist" --noCache >/dev/null
  node "$consumer/app/dist/Program.js" | grep -Fq 'consumer passed'
)
echo 'PASS fable-bindings Pixi corpus: locked restore, doctor and curation controls, drift (direct, transitive, reference mixin), events side-effect control, Node imports, Fable-emitted Node and Chromium WebGL journeys, stable candidates, packed clean consumer with the exact npm integrity'
