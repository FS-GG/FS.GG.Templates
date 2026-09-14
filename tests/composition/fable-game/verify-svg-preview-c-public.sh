#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?empty output directory required}"
[[ ! -e "$out" ]]
mkdir -p "$out/feed"
template="$out/feed/FS.GG.Workspace.Template.0.13.0.nupkg"
expected_template_sha="ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c"
curl -fsSL --retry 12 --retry-all-errors --retry-delay 10 \
  "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.13.0/fs.gg.workspace.template.0.13.0.nupkg" \
  -o "$template"
[[ "$(sha256sum "$template" | cut -d' ' -f1)" == "$expected_template_sha" ]]
rendering_version=0.31.0
game_version=0.16.0
net_version=0.6.0
audio_version=0.6.0
mkdir -p "$out/home" "$out/packages" "$out/http" "$out/tools"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
# Bind the source qualification to the exact public API mirrors used by Release C.
for spec in \
  fs.gg.ui.scene:0.31.0 fs.gg.ui.scene.svgbrowser:0.31.0 fs.gg.ui.keyboardinput:0.31.0 \
  fs.gg.game.core:0.16.0 fs.gg.net.core:0.6.0 \
  fs.gg.audio.core:0.6.0 fs.gg.audio.webbrowser:0.6.0; do
  id="${spec%:*}"; version="${spec#*:}"
  curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/$id/$version/$id.$version.nupkg" -o "$out/feed/$id.$version.nupkg"
done
python3 - "$out/feed" "$out/public-packages.json" <<'PYPACKAGES'
from pathlib import Path
from hashlib import sha256
import json,sys
feed=Path(sys.argv[1]); output=Path(sys.argv[2])
packages=[]
for archive in sorted(feed.glob('*.nupkg')):
    packages.append({'file':archive.name,'sha256':sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size})
output.write_text(json.dumps({'schema':'fsgg.svg-preview-c.public-package-hashes/v1','source':'nuget.org','packages':packages},indent=2)+'\n')
PYPACKAGES
python3 - "$root/tests/composition/fable-game/svg-preview-c-public-api.json" "$out/feed" <<'PYAPI'
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json,sys
mirror=json.loads(Path(sys.argv[1]).read_text()); feed=Path(sys.argv[2])
assert mirror['schema']=='fsgg.svg-preview-c.public-api-mirror/v1'
assert mirror['candidateOmissions']==[]
for entry in mirror['entries']:
 archive=feed/f"{entry['package'].lower()}.{entry['version']}.nupkg"
 with ZipFile(archive) as z: observed=sha256(z.read(entry['path'])).hexdigest()
 if observed != entry['sha256']: raise SystemExit(f"public API mirror drift: {entry['package']} {entry['path']}")
PYAPI
# Reuse the frozen M9 measurement contract only after proving the released Fable sources are
# the exact sources measured on the qualified reference host. The generated receiver is then
# exercised below; shared-runner observations remain diagnostic and add no threshold.
reference="$root/readiness/svg-preview-c-5/rendering-0.31.0-scale-reference.json"
[[ "$(sha256sum "$reference" | cut -d' ' -f1)" == "98ba3cf0a2a1db103ca7ac1711017062bf2c3697d59a0880e376c3629c5953b6" ]]
python3 - "$reference" "$out/feed" <<'PYREFERENCE'
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json,re,sys
receipt=json.loads(Path(sys.argv[1]).read_text()); feed=Path(sys.argv[2])
assert receipt['schema']=='fsgg.svg-scale.performance-qualification/v1'
assert receipt['result']=='pass' and receipt['environment']['mode']=='reference' and receipt['environment']['exactReferenceHost'] is True
assert receipt['measurementContract']['schema']=='fsgg.svg-scale.measurement-contract/v2'
assert receipt['claims']['previewABudgetsMet'] is True and receipt['claims']['scaleBudgetsMet'] is True
manifest={row['path']:row['sha256'].removeprefix('sha256:') for row in receipt['candidate']['sourceManifest']}
archives=[
 (feed/'fs.gg.ui.scene.0.31.0.nupkg','src/Scene/'),
 (feed/'fs.gg.ui.scene.svgbrowser.0.31.0.nupkg','src/Scene.SvgBrowser/'),
 (feed/'fs.gg.ui.keyboardinput.0.31.0.nupkg','src/KeyboardInput/'),
]
for archive,prefix in archives:
 with ZipFile(archive) as package:
  nuspec=next(name for name in package.namelist() if name.endswith('.nuspec'))
  metadata=package.read(nuspec).decode('utf-8-sig')
  if not re.search(r'<repository[^>]+commit="96810c3c66ba888ecd03a0e10fe6374fd88917f9"',metadata):
   raise SystemExit(f'{archive.name}: released source commit mismatch')
  for member in package.namelist():
   if not member.startswith('fable/') or member.endswith('.fsproj'): continue
   relative=member.removeprefix('fable/')
   candidates=(prefix+relative,prefix+'Fable/'+relative)
   source=next((name for name in candidates if name in manifest),None)
   if source is None or sha256(package.read(member)).hexdigest()!=manifest[source]:
    raise SystemExit(f'{archive.name}:{member}: frozen reference subject mismatch')
PYREFERENCE
dotnet new install "$template" --force >/dev/null
dotnet new fs-gg-fable-game -n PresentReceiver -o "$out/direct" --lifecycle none --svgFoundation true >/dev/null
for expected in "$rendering_version" "$game_version" "$audio_version"; do grep -F "$expected" "$out/direct/SvgFoundation/SvgFoundation.fsproj" >/dev/null; done
grep -F ">$game_version</FsGgGameNetworkVersion>" "$out/direct/Directory.Build.props" >/dev/null
grep -F ">$net_version</FsGgNetNetworkVersion>" "$out/direct/Directory.Build.props" >/dev/null
for flag in FsGgSvgInputCandidate FsGgSvgRuntimeCandidate FsGgSvgPresentCandidate FsGgSvgScaleCandidate; do grep -F ">true</$flag>" "$out/direct/SvgFoundation/SvgFoundation.fsproj" >/dev/null; done
test -f "$out/direct/SvgFoundation/PresentationPlayer.fs"
test -f "$out/direct/SvgFoundation/ScalePlayer.fs"
test -f "$out/direct/SvgFoundation/Studio/ReplayStudio.fs"
test -f "$out/direct/Server/NetworkAuthority.fs"
grep -F ">true</FsGgSvgReplayCandidate>" "$out/direct/SvgFoundation/Studio/Studio.fsproj" >/dev/null
grep -F ">true</FsGgSvgNetworkCandidate>" "$out/direct/Directory.Build.props" >/dev/null
if [[ -n "${FSGG_LOCAL_SDK_VERSION:-}" ]]; then
  python3 - "$out/direct/global.json" "$FSGG_LOCAL_SDK_VERSION" <<'PYSDK'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); data=json.loads(p.read_text()); data['sdk']['version']=sys.argv[2]; p.write_text(json.dumps(data,indent=2)+'\n')
PYSDK
fi

dotnet tool install FS.GG.SDD.Cli --version 1.7.0 --tool-path "$out/tools/sdd" --configfile "$out/NuGet.Config" --no-cache >/dev/null
sdd="$out/tools/sdd/fsgg-sdd"
scaffold() {
  local name="$1" lifecycle="$2" destination="$out/$1"; mkdir -p "$destination/.fsgg"; cp "$root/providers/fable-game.providers.yml" "$destination/.fsgg/providers.yml"
  python3 - "$destination/.fsgg/providers.yml" "$template" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1]); package=Path(sys.argv[2]).resolve(); text=p.read_text()
text,count=re.subn(r'(?m)^(\s*source:\s*)FS\.GG\.Workspace\.Template::[^\s#]+(\s*(?:#.*)?)$',lambda m:f'{m.group(1)}{package}{m.group(2)}',text)
if count != 1: raise SystemExit(f'{p}: expected exactly one FS.GG.Workspace.Template source, found {count}')
p.write_text(text)
PY
  params=(--param productName=PresentReceiver --param rootNamespace=PresentReceiver --param svgFoundation=true)
  [[ "$lifecycle" == omitted ]] || params+=(--param lifecycle="$lifecycle")
  "$sdd" scaffold --root "$destination" --provider fable-game --no-update --json "${params[@]}" >"$out/$name.json"
  jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  test -f "$destination/SvgFoundation/PresentationPlayer.fs"
  if [[ "$lifecycle" == typed-sdd ]]; then
    grep -F '"profile": "fsgg-quint-profile/2"' "$destination/models/svg-replay/energy-rules.bindings.json" >/dev/null
  fi
}
scaffold sdd-none none; scaffold sdd-default omitted; scaffold sdd-typed typed-sdd

curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.11.0/fs.gg.workspace.template.0.11.0.nupkg" -o "$out/feed/FS.GG.Workspace.Template.0.11.0.nupkg"
mkdir -p "$out/retained-0.11.0-home"
DOTNET_CLI_HOME="$out/retained-0.11.0-home" dotnet new install "$out/feed/FS.GG.Workspace.Template.0.11.0.nupkg" --force >/dev/null
DOTNET_CLI_HOME="$out/retained-0.11.0-home" dotnet new fs-gg-fable-game -n RetainedReceiver -o "$out/retained" --lifecycle none --svgFoundation true >/dev/null
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }
authored="$(sha256sum "$out/retained/Domain/Room.fs" "$out/retained/Client/App.fs")"
cp -a "$out/retained" "$out/collision"; printf '\nauthored collision\n' >>"$out/collision/SvgFoundation/Program.fs"; before="$(tree_sha "$out/collision")"
if "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/collision" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/collision-backup"; then exit 1; fi
[[ "$before" == "$(tree_sha "$out/collision")" && ! -e "$out/collision-backup" ]]
cp -a "$out/retained" "$out/interrupted"; before="$(tree_sha "$out/interrupted")"
if FSGG_SVG_PREVIEW_FAIL_AFTER=14 "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/interrupted" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/interrupted-backup"; then exit 1; fi
[[ "$before" == "$(tree_sha "$out/interrupted")" ]]
cp -a "$out/retained" "$out/rollback"; before="$(tree_sha "$out/rollback")"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/rollback" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/rollback-backup" >/dev/null
"$root/scripts/apply-svg-foundation-preview.sh" rollback "$out/rollback" "$out/rollback-backup" >/dev/null
[[ "$before" == "$(tree_sha "$out/rollback")" ]]
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/retained" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/retained-backup" >/dev/null
[[ "$authored" == "$(sha256sum "$out/retained/Domain/Room.fs" "$out/retained/Client/App.fs")" ]]

for retained_version in 0.10.0 0.12.0; do
  archive="$out/feed/FS.GG.Workspace.Template.$retained_version.nupkg"
  curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$retained_version/fs.gg.workspace.template.$retained_version.nupkg" -o "$archive"
  retained_home="$out/retained-$retained_version-home"
  DOTNET_CLI_HOME="$retained_home" dotnet new install "$archive" --force >/dev/null
  retained_root="$out/retained-$retained_version"
  if [[ "$retained_version" == 0.10.0 ]]; then
    DOTNET_CLI_HOME="$retained_home" dotnet new fs-gg-fable-game -n RetainedReceiver -o "$retained_root" --lifecycle none >/dev/null
  else
    DOTNET_CLI_HOME="$retained_home" dotnet new fs-gg-fable-game -n RetainedReceiver -o "$retained_root" --lifecycle none --svgFoundation true >/dev/null
  fi
  retained_authored="$(sha256sum "$retained_root/Domain/Room.fs" "$retained_root/Client/App.fs")"
  "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$retained_root" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/retained-$retained_version-backup" >/dev/null
  [[ "$retained_authored" == "$(sha256sum "$retained_root/Domain/Room.fs" "$retained_root/Client/App.fs")" ]]
done

mkdir -p "$out/wizard-home"
DOTNET_CLI_HOME="$out/wizard-home" dotnet new install "$out/feed/FS.GG.Workspace.Template.0.11.0.nupkg" --force >/dev/null
dotnet tool install FS.GG.NewSddWorkspace --version 0.11.1 --tool-path "$out/tools/wizard" --configfile "$out/NuGet.Config" --no-cache >/dev/null
DOTNET_CLI_HOME="$out/wizard-home" PATH="$(dirname "$sdd"):$PATH" "$out/tools/wizard/new-sdd-workspace" "$out/wizard" WizardReceiver --template fable-game --lifecycle none --ref fs-gg-templates/v0.11.0 --pinned --no-governance --no-coordination >"$out/wizard.log"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/wizard" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/wizard-backup" >/dev/null

(cd "$out/direct" && dotnet tool restore >/dev/null)
bash "$out/direct/SvgFoundation/build.sh" >"$out/player-build.log" 2>&1
! grep -RIE 'SvgStudio|SvgGeometryWorker|polygon-clipping|OpenAL|Silk.NET.OpenAL' "$out/direct/SvgFoundation/dist"
bash "$out/direct/SvgFoundation/Studio/build.sh" >"$out/studio-build.log" 2>&1
npm ci --prefix "$out/direct/Browser.Tests" >/dev/null
cp "$root/tests/composition/fable-game/svg-present-player-observe.mjs" "$out/direct/Browser.Tests/"
cp "$root/tests/composition/fable-game/svg-authoring-observe.mjs" "$out/direct/Browser.Tests/"
cp "$root/tests/composition/fable-game/svg-input-observe.mjs" "$out/direct/Browser.Tests/"
(cd "$out/direct/SvgFoundation/dist" && python3 -m http.server 8142 --bind 127.0.0.1 >"$out/server.log" 2>&1) & server=$!
(cd "$out/direct/SvgFoundation/Studio/dist" && python3 -m http.server 8143 --bind 127.0.0.1 >"$out/studio-server.log" 2>&1) & studio_server=$!
trap 'kill "$server" "$studio_server" 2>/dev/null || true' EXIT
for _ in {1..40}; do curl -fsS http://127.0.0.1:8142/ >/dev/null && break; sleep .25; done
for _ in {1..40}; do curl -fsS http://127.0.0.1:8143/ >/dev/null && break; sleep .25; done
for family in chromium firefox webkit; do
  (cd "$out/direct/Browser.Tests" && node svg-present-player-observe.mjs "$family" http://127.0.0.1:8142/) >"$out/$family-present.json"
  (cd "$out/direct/Browser.Tests" && node svg-authoring-observe.mjs "$family" http://127.0.0.1:8143/) >"$out/$family-authoring.json"
  (cd "$out/direct/Browser.Tests" && node svg-input-observe.mjs "$family" http://127.0.0.1:8143/) >"$out/$family-input.json"
done
# Replay/rules and scale use the same installed Studio/Player bytes qualified above.
cp "$root/tests/composition/fable-game/svg-replay-studio-observe-v013.mjs" "$out/direct/Browser.Tests/"
cp "$root/tests/composition/fable-game/svg-scale-observe.mjs" "$out/direct/Browser.Tests/"
cp "$root/tests/composition/fable-game/svg-scale-measure.mjs" "$out/direct/Browser.Tests/"
for family in chromium firefox webkit; do
  (cd "$out/direct/Browser.Tests" && node svg-replay-studio-observe-v013.mjs "$family" http://127.0.0.1:8143/) >"$out/$family-replay.json"
  (cd "$out/direct/Browser.Tests" && node svg-scale-observe.mjs "$family" http://127.0.0.1:8142/ http://127.0.0.1:8143/) >"$out/$family-scale.json"
done
(cd "$out/direct/Browser.Tests" && node svg-scale-measure.mjs http://127.0.0.1:8142/) >"$out/chromium-scale-measurement.json"

# Exercise the public Game/Net authority, two-client reconnect and review path.
dotnet test "$out/direct/Server.Tests/Server.Tests.fsproj" -c Release -p:RestoreLockedMode=true >"$out/network-tests.log"
(cd "$out/direct/Client" && npm ci >/dev/null && npm run build >/dev/null)
dotnet publish "$out/direct/Server/Server.fsproj" -c Release --no-restore -o "$out/network-publish" >/dev/null
cp "$root/tests/composition/fable-game/svg-network-observe.mjs" "$out/direct/Browser.Tests/"
network_server=''
for family in chromium firefox webkit; do
  (cd "$out/network-publish" && exec dotnet Server.dll --urls http://127.0.0.1:5100 >"$out/$family-network-server.log" 2>&1) & network_server=$!
  for _ in {1..80}; do curl -fsS http://127.0.0.1:5100/ >/dev/null && break; sleep .25; done
  (cd "$out/direct/Browser.Tests" && node svg-network-observe.mjs "$family" http://127.0.0.1:5100) >"$out/$family-network.json"
  kill "$network_server"; wait "$network_server" 2>/dev/null || true; network_server=''
done
browser_evidence_sha="$(cat "$out"/*-present.json "$out"/*-authoring.json "$out"/*-input.json "$out"/*-replay.json "$out"/*-scale.json "$out"/*-network.json | sha256sum | cut -d' ' -f1)"
jq -n --arg templateSha "$(sha256sum "$template" | cut -d' ' -f1)" --arg browserEvidenceSha "$browser_evidence_sha" --slurpfile c "$out/chromium-present.json" --slurpfile f "$out/firefox-present.json" --slurpfile w "$out/webkit-present.json" --slurpfile packages "$out/public-packages.json" --slurpfile scaleMeasurement "$out/chromium-scale-measurement.json" --arg scaleReferenceSha "98ba3cf0a2a1db103ca7ac1711017062bf2c3697d59a0880e376c3629c5953b6" '{schema:"fsgg.svg-preview-c.public-qualification/v1",template:{version:"0.13.0",source:"nuget.org",sha256:$templateSha},packageHashes:$packages[0],publicProducers:{rendering:"0.31.0",game:"0.16.0",net:"0.6.0",audio:"0.6.0"},routes:{direct:"passed",sdd17:{none:"passed",default:"passed",typed:"passed"},wizard0111Adopter:"passed",retained010to012:"passed"},browser:{chromium:$c[0],firefox:$f[0],webkit:$w[0],authoringInputEvidenceSha256:$browserEvidenceSha},presentation:{animation:"passed",reducedMotion:"passed",gestureAudio:"passed",liveCueSeekPolicy:"passed",autosaveRecovery:"passed",reload:"passed",archive:"passed"},replay:{equality:"passed",divergence:"passed",rules:"passed",studioOnly:"passed"},network:{authority:"passed",twoBrowser:"passed",reconnect:"passed",review:"passed"},scale:{dense:"passed",worldExtent:"passed",responsive:"passed",accessibility:"passed",chromiumMeasurement:$scaleMeasurement[0],referenceReceiptSha256:$scaleReferenceSha,ownerTimingDisposition:"frozen SVG-SCALE-01 contract rerun on the exact reference host; every released Fable source matched before reuse; installed receiver samples are diagnostic and add no threshold or physical-device claim"},apiMirror:{candidateOmissions:0,status:"passed"},adopter:{collision:"refused-without-write",interruption:"rolled-back",rollback:"byte-identical",authoredFiles:"preserved"},publication:true,producerDistribution:"public-nuget-only",release:"C"}' >"$out/qualification.json"
echo "svg-preview-c-public: passed; evidence=$out/qualification.json"
