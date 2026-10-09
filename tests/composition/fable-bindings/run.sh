#!/usr/bin/env bash
# Template-owned structural proof. Runtime calls require the consumer's selected npm package.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
if [[ "${FSGG_FABLE_BINDINGS_PUBLIC_INSTALLED:-0}" == "1" ]]; then
  exec bash "$ROOT/tests/composition/fable-bindings/verify-public-installed.sh" "${FSGG_FABLE_BINDINGS_PUBLIC_OUT:-}"
fi
WORK="$(mktemp -d)"
. "$ROOT/tests/composition/lib/lifecycle-diagnostics.sh"
trap 'cleanup_lifecycle_product "$WORK" "$?"' EXIT
export DOTNET_CLI_HOME="$WORK/home" DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
mkdir -p "$DOTNET_CLI_HOME"

LANE_REPO_ROOT="$ROOT"
# shellcheck source=tests/composition/lib/lane-package.sh
. "$ROOT/tests/composition/lib/lane-package.sh"
# shellcheck source=tests/composition/lib/lifecycle-matrix.sh
. "$ROOT/tests/composition/lib/lifecycle-matrix.sh"
# The release gate sets FSGG_TEMPLATES_NUPKG to the downloaded, checksum-verified artifact, so this
# lane proves the fable-bindings identity against the bytes that are about to be published rather
# than against a second archive packed here (FS.GG.Templates#349).
PACKAGE="$(lane_package_path "$WORK")"
echo "fable-bindings composition: installing $PACKAGE"
dotnet new install "$PACKAGE" >/dev/null
assert_provider_lifecycle_matrix fable-bindings "$PACKAGE" "$WORK/lifecycle-matrix" productName=MatrixBindings rootNamespace=MatrixBindings
dotnet new fs-gg-fable-bindings -o "$WORK/product" --name AcmeBindings --productName AcmeBindings --rootNamespace AcmeBindings --npmPackage=@babylonjs/core --npmVersion 9.19.0 --bindingTarget browser >/dev/null
if dotnet new fs-gg-fable-bindings -o "$WORK/rejected" --name Rejected --npmPackage other --npmVersion 1.0.0 --bindingTarget node >/dev/null 2>&1; then echo "unqualified corpus unexpectedly accepted" >&2; exit 1; fi

for f in declaration-lock.json binding-plan.json coverage-and-drift.json generated-candidates/declaration-analysis.json package.json .config/dotnet-tools.json src/AcmeBindings/AcmeBindings.fsproj tests/AcmeBindings.CompileTests/AcmeBindings.CompileTests.fsproj samples/Consumer/README.md; do test -f "$WORK/product/$f"; done
# ── Owner-sourced product skills reach the PACKED product (FS.GG.Templates#347) ────────────────
# This REPLACED a `cmp` against `skills/fable-bindings/SKILL.md`, a second checked-in copy of the
# template's own skill file. That pair shared one blob and was kept equal only by the cmp — a
# second source of truth held in place by a test. The catalog is now authored once under
# template/product-skills/ and projected into the packed payload by FS.GG.Templates.csproj, so
# there is no second file left to compare; what has to be proved instead is that the packed
# product actually RECEIVED the declared set. The assertion reads the manifest the product shipped
# and reds on an absent selected skill, a skill the manifest does not select for this template, an
# undeclared (dangling) skill directory, a drifted digest, or a missing/non-canonical manifest.
dotnet fsi "$ROOT/scripts/generate-skill-manifest.fsx" --assert-product "$WORK/product" --template fs-gg-fable-bindings
grep -Fq '"@babylonjs/core": "9.19.0"' "$WORK/product/package.json"
grep -Fq '@babylonjs/core/Engines/nullEngine.d.ts' "$WORK/product/declaration-lock.json"
grep -Fq 'ImportAll("@babylonjs/loaders/glTF/index.js")' "$WORK/product/src/AcmeBindings/Bindings.fs"
grep -Fq 'GENERATED CANDIDATE — NOT COMPILED' "$WORK/product/generated-candidates/BabylonBindings.generated.fs"
grep -Fq 'declarationMergingCandidates' "$WORK/product/generated-candidates/declaration-analysis.json"

# Check the generated project's publication contract before package/runtime work.
python3 - "$WORK/product" "$WORK/binding-package-pins.json" <<'PY_BINDING_PROJECT'
import json, pathlib, re, sys, xml.etree.ElementTree as ET
product = pathlib.Path(sys.argv[1])
project = ET.parse(product / 'src/AcmeBindings/AcmeBindings.fsproj').getroot()
assert project.findtext('./PropertyGroup/FablePackageType') == 'binding', 'binding package type'
assert 'fable-javascript' in project.findtext('./PropertyGroup/PackageTags', '').split(';'), 'JavaScript target'
sdk = [e for e in project.findall('./ItemGroup/PackageReference') if e.get('Include') == 'Fable.Package.SDK']
assert len(sdk) == 1 and sdk[0].get('PrivateAssets') == 'all', 'SDK must be private'
assert set(sdk[0].get('IncludeAssets', '').split(';')) == {'runtime', 'build', 'native', 'contentfiles', 'analyzers', 'buildtransitive'}, 'SDK build assets'
npm = project.findall('./PropertyGroup/NpmDependencies/NpmPackage')
assert len(npm) == 2 and {e.get('Name'): e.get('Version') for e in npm} == {'@babylonjs/core': '9.19.0', '@babylonjs/loaders': '9.19.0'}, 'exact Femto metadata'
central = ET.parse(product / 'Directory.Packages.props').getroot()
core = [e.get('Version') for e in central.findall('./ItemGroup/PackageVersion') if e.get('Include') == 'Fable.Core']
assert len(core) == 1, 'one central Fable.Core selection'
fable = json.loads((product / '.config/dotnet-tools.json').read_text())['tools']['fable']['version']
for version in [core[0], fable]:
    assert isinstance(version, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?', version), 'exact consumer version'
pathlib.Path(sys.argv[2]).write_text(json.dumps({'core': core[0], 'fable': fable}) + '\n')
PY_BINDING_PROJECT

(cd "$WORK/product" && git init -q && git config user.email test@example.invalid && git config user.name test && git add generated-candidates && git commit -qm baseline && npm ci --ignore-scripts >/dev/null && npm run doctor >/dev/null && npm run check:drift >/dev/null && npm run test:side-effect-control >/dev/null && npm run test:imports >/dev/null && dotnet tool restore >/dev/null && npm run compile:fable >/dev/null && npm run test:runtime >/dev/null)
solution="$(find "$WORK/product" -maxdepth 1 -name '*.slnx' -print -quit)"
dotnet restore "$solution" --locked-mode
dotnet build "$solution" --no-restore
# The generated binding must survive a packed archive and a genuinely clean consumer.
# Derive selections from delivered pins instead of the stale independent 5.2.0/5.13.0 pair.
consumer="$WORK/consumer"; mkdir -p "$consumer/app" "$consumer/feed"
dotnet build "$WORK/product/src/AcmeBindings/AcmeBindings.fsproj" -c Release >/dev/null
dotnet pack "$WORK/product/src/AcmeBindings/AcmeBindings.fsproj" -c Release --no-build -o "$consumer/feed" >/dev/null
python3 - "$consumer/feed/AcmeBindings.0.1.0.nupkg" "$WORK/binding-package-pins.json" "$consumer/app" <<'PY_BINDING_ARCHIVE'
import io, json, pathlib, re, sys, xml.etree.ElementTree as ET, zipfile

def inspect_binding_package(package):
    with zipfile.ZipFile(package) as archive:
        entries = archive.namelist()
        assert len(entries) == len(set(entries)), 'duplicate package entry'
        assert 'lib/netstandard2.1/AcmeBindings.dll' in entries, 'compiled binding absent'
        assert not any(n.lower().startswith('fable/') or n.lower().endswith(('.fs', '.fsi', '.fsx')) for n in entries), 'library source payload'
        assert not any('node_modules/' in n.lower() or n.lower().endswith(('.js', '.mjs', '.cjs', '.ts')) for n in entries), 'bundled native npm implementation'
        specs = [n for n in entries if n.lower().endswith('.nuspec')]
        assert len(specs) == 1, 'one package specification'
        root = ET.fromstring(archive.read(specs[0]))
        metadata = next(e for e in root if e.tag.rsplit('}', 1)[-1] == 'metadata')
        assert next(e.text for e in metadata if e.tag.rsplit('}', 1)[-1] == 'id') == 'AcmeBindings', 'package identity'
        assert next(e.text for e in metadata if e.tag.rsplit('}', 1)[-1] == 'version') == '0.1.0', 'package version'
        deps = {e.get('id', '').lower() for e in metadata.iter() if e.tag.rsplit('}', 1)[-1] == 'dependency'}
        assert 'fable.package.sdk' not in deps, 'SDK consumer dependency'
        tags = next(e.text or '' for e in metadata if e.tag.rsplit('}', 1)[-1] == 'tags')
        tags = set(re.split(r'[;\s]+', tags.lower()))
        assert {'fable', 'fable-binding', 'fable-javascript'} <= tags and 'fable-library' not in tags, 'binding tags'

package = pathlib.Path(sys.argv[1])
inspect_binding_package(package)
# The actual inspector must reject both original defect shapes, using mutated archive copies.
with zipfile.ZipFile(package) as archive:
    contents = {n: archive.read(n) for n in archive.namelist()}
for defect in ['library-source', 'sdk-dependency']:
    mutated = dict(contents)
    if defect == 'library-source':
        mutated['fable/Bindings.fs'] = b'// synthetic library payload'
    else:
        name = next(n for n in mutated if n.lower().endswith('.nuspec'))
        root = ET.fromstring(mutated[name])
        metadata = next(e for e in root if e.tag.rsplit('}', 1)[-1] == 'metadata')
        ns = metadata.tag.rsplit('}', 1)[0] + '}' if '}' in metadata.tag else ''
        dependencies = next((e for e in metadata if e.tag.rsplit('}', 1)[-1] == 'dependencies'), None)
        if dependencies is None:
            dependencies = ET.SubElement(metadata, ns + 'dependencies')
        ET.SubElement(dependencies, ns + 'dependency', {'id': 'Fable.Package.SDK', 'version': '1.4.1'})
        mutated[name] = ET.tostring(root)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, body in mutated.items():
            archive.writestr(name, body)
    stream.seek(0)
    try:
        inspect_binding_package(stream)
    except AssertionError:
        pass
    else:
        raise AssertionError('package inspector accepted ' + defect)

pins = json.loads(pathlib.Path(sys.argv[2]).read_text())
app = pathlib.Path(sys.argv[3])
project = ET.Element('Project', {'Sdk': 'Microsoft.NET.Sdk'})
properties = ET.SubElement(project, 'PropertyGroup')
ET.SubElement(properties, 'TargetFramework').text = 'netstandard2.1'
ET.SubElement(properties, 'RestorePackagesWithLockFile').text = 'true'
items = ET.SubElement(project, 'ItemGroup')
ET.SubElement(items, 'Compile', {'Include': 'Program.fs'})
ET.SubElement(items, 'PackageReference', {'Include': 'AcmeBindings', 'Version': '0.1.0'})
ET.SubElement(items, 'PackageReference', {'Include': 'Fable.Core', 'Version': pins['core']})
ET.ElementTree(project).write(app / 'Consumer.fsproj', encoding='unicode')
(app / 'fable-version.txt').write_text(pins['fable'] + '\n')
PY_BINDING_ARCHIVE
printf '%s\n' '<configuration><packageSources><clear /><add key="local" value="'"$consumer"'/feed" /><add key="nuget.org" value="https://api.nuget.org/v3/index.json" /></packageSources></configuration>' > "$consumer/app/NuGet.Config"
cat > "$consumer/app/Program.fs" <<'FS_BINDING_CONSUMER'
open Qualification.Babylon

let engine: Engine = nullEngine ()
let scene: Scene = scene engine
let position: Vector3 = vector3 0. 0. 0.
let direction: Vector3 = vector3 0. 1. 0.
let camera: Camera = freeCamera "consumer-camera" position scene
let light: Light = hemisphericLight "consumer-light" direction scene
let mesh: Box = box "consumer-box" scene
if isNull engine || isNull scene || isNull position || isNull direction ||
   isNull camera || isNull light || isNull mesh then
    failwith "packed binding returned a missing native object"
initialiseLoader ()
if not (loaderRegistered ()) then
    failwith "packed binding glTF loader import did not register the plugin"
printfn "consumer passed"
FS_BINDING_CONSUMER
cp "$WORK/product/package.json" "$WORK/product/package-lock.json" "$consumer/app/"
# Keep the same fresh package cache through restore, tool installation and Fable's own restore.
(
  export NUGET_PACKAGES="$consumer/packages" DOTNET_CLI_HOME="$consumer/home"
  mkdir -p "$DOTNET_CLI_HOME"
  dotnet restore "$consumer/app/Consumer.fsproj" --configfile "$consumer/app/NuGet.Config" >/dev/null
  (cd "$consumer/app" && npm ci --ignore-scripts >/dev/null)
  grep -Fq 'sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==' "$consumer/app/package-lock.json"
  fable_version="$(cat "$consumer/app/fable-version.txt")"
  dotnet tool install Fable --tool-path "$consumer/fable" --version "$fable_version" >/dev/null
  "$consumer/fable/fable" "$consumer/app/Consumer.fsproj" --outDir "$consumer/app/dist" --noCache >/dev/null
  node "$consumer/app/dist/Program.js" | grep -Fq 'consumer passed'
)

# Execute the clean scaffold's actual SDD lifecycle, observed test-report import,
# coherent doctor, provenance, and Governance policy boundary. Governance consumes
# both SDD's lifecycle handoff and this provider's narrow declaration-drift verdict.
command -v fsgg-sdd >/dev/null
command -v fsgg-governance >/dev/null
dotnet new fs-gg-governance -o "$WORK/product" --appName AcmeBindings --defaultProfile strict --force >/dev/null
(cd "$WORK/product" && node scripts/lifecycle-evidence.mjs --expect clean --junit reports/bindings.junit.xml --handoff readiness/002-bindings-upstream-review/governance-handoff.json)
track_bindings_lifecycle_evidence "$WORK/product"
(cd "$WORK/product" && npm run test:lifecycle >/dev/null)
# The governance overlay is applied with --force over the SAME directory, so this re-assertion is
# not a repeat: it proves the overlay does not clobber, truncate, or shadow the producer's skill
# root on its way through.
#
# `--co-tenants` is required HERE and not on the first call because by this point the root is
# SHARED: fsgg-sdd has seeded its `fs-gg-sdd-*` process skills and the five `always` `.github`
# driver skills (registry/driver-skill-manifest.json) into the same `.agents/skills/`. They are
# another producer's correct output, so this producer's manifest must not declare them — but a
# skill belonging to NOBODY still reds, which is the dangling class the glob list preserves.
dotnet fsi "$ROOT/scripts/generate-skill-manifest.fsx" --assert-product "$WORK/product" --template fs-gg-fable-bindings \
  --co-tenants 'fs-gg-sdd-* work-board work-board-best work-board-normal work-roadmap padd-item'
test -f "$WORK/product/.fsgg/scaffold-provenance.json"
jq -e '.governanceConfig.policyPresent == true and .governanceConfig.capabilitiesPresent == true and .readiness.shipDisposition == "shipReady"' "$WORK/product/readiness/001-bindings-lifecycle/governance-handoff.json" >/dev/null
cp "$WORK/product/readiness/001-bindings-lifecycle/governance-handoff.json" "$WORK/product/reports/sdd-governance-handoff.json"
# The SDD handoff itself must be Governance-consumable, not replaced by the
# provider-specific upstream verdict. Its dependency graph is acyclic because
# observed evidence is subject to its obligation, not back to the requiring task.
jq -e '[.evidence.dependencies[] | select(.dependent | startswith("evidence:"))] | length == 0' "$WORK/product/readiness/001-bindings-lifecycle/governance-handoff.json" >/dev/null
fsgg-governance route --root "$WORK/product" --mode gate --json >"$WORK/product/reports/governance-clean.json"
jq -e '.exit.code == 0 and ([.payload.handoff[] | select((.id | contains("sdd-handoff:evidence")) and .blocking == false)] | length) >= 2' "$WORK/product/reports/governance-clean.json" >/dev/null

# Mutating one locked transitive declaration is an executable review/failure path:
# the closure gate fails, SDD refuses to sync a failed run into pass-claiming
# evidence, and Governance blocks that same observed state.
printf '\n// upstream drift acceptance mutation\n' >> "$WORK/product/node_modules/@babylonjs/core/Engines/nullEngine.d.ts"
if (cd "$WORK/product" && npm run check:drift >/dev/null 2>&1); then echo "upstream declaration drift unexpectedly passed" >&2; exit 1; fi
(cd "$WORK/product" && node scripts/lifecycle-evidence.mjs --expect drift --junit reports/bindings.junit.xml --handoff readiness/002-bindings-upstream-review/governance-handoff.json)
set +e
fsgg-governance route --root "$WORK/product" --mode gate --json >"$WORK/product/reports/governance-drift.json"
governance_drift_rc=$?
fsgg-sdd evidence --root "$WORK/product" --work 001-bindings-lifecycle --title 'Fable bindings lifecycle' --sync-observed-run reports/bindings.junit.xml >"$WORK/product/reports/sdd-drift-review.json"
sdd_drift_rc=$?
set -e
test "$sdd_drift_rc" -eq 1
jq -e '.outcome == "blocked" and any(.diagnostics[]; .id == "evidence.observedRunFailed")' "$WORK/product/reports/sdd-drift-review.json" >/dev/null
if [[ "$governance_drift_rc" -ne 2 ]]; then
  jq '{exit, handoff: .payload.handoff}' "$WORK/product/reports/governance-drift.json" >&2
  echo "Governance did not block executable upstream drift (exit $governance_drift_rc)" >&2
  exit 1
fi
jq -e '.exit.category == "governed-blocking" and any(.payload.handoff[]; (.id | contains("sdd-handoff:evidence")) and .blocking == true)' "$WORK/product/reports/governance-drift.json" >/dev/null

# Reinstalling the exact pinned closure restores the green lifecycle boundary.
(cd "$WORK/product" && npm ci --ignore-scripts >/dev/null && npm run check:drift >/dev/null && node scripts/lifecycle-evidence.mjs --expect clean --junit reports/bindings.junit.xml --handoff readiness/002-bindings-upstream-review/governance-handoff.json >/dev/null)
fsgg-sdd evidence --root "$WORK/product" --work 001-bindings-lifecycle --title 'Fable bindings lifecycle' --sync-observed-run reports/bindings.junit.xml >"$WORK/product/reports/sdd-restored.json"
fsgg-governance route --root "$WORK/product" --mode gate --json >"$WORK/product/reports/governance-restored.json"
jq -e '(.outcome == "noChange" or .outcome == "succeeded" or .outcome == "succeededWithWarnings") and .evidence.readiness == "evidenceReady"' "$WORK/product/reports/sdd-restored.json" >/dev/null
jq -e '.exit.code == 0' "$WORK/product/reports/governance-restored.json" >/dev/null

before="$(sha256sum "$WORK/product/src/AcmeBindings/Bindings.fs" "$WORK/product/declaration-lock.json")"
(cd "$WORK/product" && npm run generate:candidate >/dev/null)
test "$before" = "$(sha256sum "$WORK/product/src/AcmeBindings/Bindings.fs" "$WORK/product/declaration-lock.json")"
git -C "$WORK/product" diff --exit-code -- generated-candidates
# A changed declaration lock produces a review-visible tracked candidate diff without modifying src.
printf '\n' >> "$WORK/product/declaration-lock.json"
(cd "$WORK/product" && npm run generate:candidate >/dev/null)
git -C "$WORK/product" diff --quiet -- generated-candidates && { echo "candidate was not review-visible" >&2; exit 1; }

# Real Chromium exercises the browser module imports and the narrow Babylon scene route.
python3 -m http.server 4173 --directory "$WORK/product" >"$WORK/browser-server.log" 2>&1 &
browser_server=$!
trap 'kill "$browser_server" 2>/dev/null || true; rm -rf "$WORK"' EXIT
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
echo 'PASS fable-bindings template executes locked declaration, candidate, NuGet/npm/Fable/Node/Chromium, SDD, doctor, Governance, drift-review and owner-sourced product-skill delivery evidence'
