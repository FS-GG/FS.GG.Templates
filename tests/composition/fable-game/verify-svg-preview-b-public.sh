#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?empty output directory required}"
[[ ! -e "$out" ]]
mkdir -p "$out/feed"
template="$out/feed/FS.GG.Workspace.Template.0.12.0.nupkg"
curl -fsSL --retry 12 --retry-all-errors --retry-delay 10 \
  "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.12.0/fs.gg.workspace.template.0.12.0.nupkg" \
  -o "$template"
[[ -f "$template" ]]
rendering_version=0.30.0
game_version=0.15.0
audio_version=0.6.0
mkdir -p "$out/home" "$out/packages" "$out/http" "$out/tools"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
dotnet new install "$template" --force >/dev/null
dotnet new fs-gg-fable-game -n PresentReceiver -o "$out/direct" --lifecycle none --svgFoundation true >/dev/null
for expected in "$rendering_version" "$game_version" "$audio_version"; do grep -F "$expected" "$out/direct/SvgFoundation/SvgFoundation.fsproj" >/dev/null; done
for flag in FsGgSvgInputCandidate FsGgSvgRuntimeCandidate FsGgSvgPresentCandidate; do grep -F ">true</$flag>" "$out/direct/SvgFoundation/SvgFoundation.fsproj" >/dev/null; done
test -f "$out/direct/SvgFoundation/PresentationPlayer.fs"

dotnet tool install FS.GG.SDD.Cli --version 1.7.0 --tool-path "$out/tools/sdd" --configfile "$out/NuGet.Config" --no-cache >/dev/null
sdd="$out/tools/sdd/fsgg-sdd"
scaffold() {
  local name="$1" lifecycle="$2" destination="$out/$1"; mkdir -p "$destination/.fsgg"; cp "$root/providers/fable-game.providers.yml" "$destination/.fsgg/providers.yml"
  python3 - "$destination/.fsgg/providers.yml" "$template" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); p.write_text(p.read_text().replace('source: FS.GG.Workspace.Template::0.12.0',f'source: {Path(sys.argv[2]).resolve()}'))
PY
  params=(--param productName=PresentReceiver --param rootNamespace=PresentReceiver --param svgFoundation=true)
  [[ "$lifecycle" == omitted ]] || params+=(--param lifecycle="$lifecycle")
  "$sdd" scaffold --root "$destination" --provider fable-game --no-update --json "${params[@]}" >"$out/$name.json"
  jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  test -f "$destination/SvgFoundation/PresentationPlayer.fs"
}
scaffold sdd-none none; scaffold sdd-default omitted; scaffold sdd-typed typed-sdd

curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.11.0/fs.gg.workspace.template.0.11.0.nupkg" -o "$out/feed/FS.GG.Workspace.Template.0.11.0.nupkg"
dotnet new install "$out/feed/FS.GG.Workspace.Template.0.11.0.nupkg" --force >/dev/null
dotnet new fs-gg-fable-game -n RetainedReceiver -o "$out/retained" --lifecycle none --svgFoundation true >/dev/null
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
SVG_SCENE_ORCA_OBSERVATION="$out/orca-authoring.json" \
  bash "$root/tests/composition/fable-game/observe-svg-authoring-orca.sh" \
    http://127.0.0.1:8143/ "$out/orca-authoring.json"
SVG_SCENE_ORCA_OBSERVATION="$out/orca-input.json" \
  bash "$root/tests/composition/fable-game/observe-svg-input-orca.sh" \
    http://127.0.0.1:8143/ "$out/orca-input.json"
jq -e '.result=="passed" and .process.name=="orca"' "$out/orca-authoring.json" "$out/orca-input.json" >/dev/null
browser_evidence_sha="$(cat "$out"/*-present.json "$out"/*-authoring.json "$out"/*-input.json | sha256sum | cut -d' ' -f1)"
orca_evidence_sha="$(cat "$out/orca-authoring.json" "$out/orca-input.json" | sha256sum | cut -d' ' -f1)"
jq -n --arg templateSha "$(sha256sum "$template" | cut -d' ' -f1)" --arg browserEvidenceSha "$browser_evidence_sha" --arg orcaEvidenceSha "$orca_evidence_sha" --slurpfile c "$out/chromium-present.json" --slurpfile f "$out/firefox-present.json" --slurpfile w "$out/webkit-present.json" '{schema:"fsgg.svg-preview-b.public-qualification/v1",template:{version:"0.12.0",source:"nuget.org",sha256:$templateSha},publicProducers:{rendering:"0.30.0",game:"0.15.0",audio:"0.6.0"},routes:{direct:"passed",sdd17:{none:"passed",default:"passed",typedProfile2:"passed"},wizard0111Adopter:"passed",retained011:"passed"},browser:{chromium:$c[0],firefox:$f[0],webkit:$w[0],authoringInputEvidenceSha256:$browserEvidenceSha,orcaEvidenceSha256:$orcaEvidenceSha},presentation:{animation:"passed",reducedMotion:"passed",gestureAudio:"passed",liveCueSeekPolicy:"passed",autosaveRecovery:"passed",reload:"passed",archive:"passed"},adopter:{collision:"refused-without-write",interruption:"rolled-back",rollback:"byte-identical",authoredFiles:"preserved"},publication:true,producerDistribution:"public-nuget-only",release:"B"}' >"$out/qualification.json"
echo "svg-preview-b-public: passed; evidence=$out/qualification.json"
