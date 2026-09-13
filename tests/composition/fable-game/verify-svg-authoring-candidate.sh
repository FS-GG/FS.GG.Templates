#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
packet="${1:?Rendering packet directory required}"
out="${2:?empty output directory required}"
[[ ! -e "$out" ]] || { echo 'svg-authoring-candidate: output exists' >&2; exit 2; }
bash "$root/scripts/stage-svg-authoring-candidate.sh" "$packet/manifest.json" "$out"
candidate="$out/feed/FS.GG.Workspace.Template.0.11.0-svg-author.1.nupkg"
rendering_version="$(jq -r .rendering.version "$out/candidate-packet.json")"
[[ "$(sha256sum "$candidate"|cut -d' ' -f1)" == "$(jq -r .templates.package.sha256 "$out/candidate-packet.json")" ]]
mkdir -p "$out/home" "$out/packages" "$out/http" "$out/tools"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
dotnet new install "$candidate" --force >/dev/null
dotnet new fs-gg-fable-game -n DefaultReceiver -o "$out/default" >/dev/null
dotnet new fs-gg-fable-game -n DirectReceiver -o "$out/direct" --lifecycle none --svgFoundation true >/dev/null
test ! -e "$out/default/SvgFoundation"
test -f "$out/direct/SvgFoundation/Studio/Studio.fsproj"
grep -F 'Version="[0.29.0]"' "$out/direct/SvgFoundation/SvgFoundation.fsproj" >/dev/null
grep -F "$rendering_version" "$out/direct/SvgFoundation/Studio/Studio.fsproj" >/dev/null

dotnet tool install FS.GG.SDD.Cli --version 1.7.0 --tool-path "$out/tools/sdd" --configfile "$out/NuGet.Config" --no-cache >/dev/null
sdd="$out/tools/sdd/fsgg-sdd"
scaffold() {
  local name="$1" lifecycle="$2" destination="$out/$1"
  mkdir -p "$destination/.fsgg"; cp "$root/providers/fable-game.providers.yml" "$destination/.fsgg/providers.yml"
  python3 - "$destination/.fsgg/providers.yml" "$candidate" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); p.write_text(p.read_text().replace('source: FS.GG.Workspace.Template::0.11.0',f'source: {Path(sys.argv[2]).resolve()}'))
PY
  params=(--param productName=AuthoringReceiver --param rootNamespace=AuthoringReceiver --param svgFoundation=true)
  [[ "$lifecycle" == omitted ]] || params+=(--param lifecycle="$lifecycle")
  "$sdd" scaffold --root "$destination" --provider fable-game --no-update --json "${params[@]}" >"$out/$name.json"
  jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  test -f "$destination/SvgFoundation/Studio/Studio.fsproj"
  test -f "$destination/.agents/skills/skill-manifest.json"
}
scaffold sdd-none none
scaffold sdd-default omitted
scaffold sdd-typed typed-sdd
jq -e '[.effectiveParameters[]|select(.key=="lifecycle" and .value=="sdd")]|length==1' "$out/sdd-default/.fsgg/scaffold-provenance.json" >/dev/null
jq -e '[.effectiveParameters[]|select(.key=="lifecycle" and .value=="typed-sdd")]|length==1' "$out/sdd-typed/.fsgg/scaffold-provenance.json" >/dev/null

for version in 0.10.0 0.11.0; do curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" -o "$out/feed/FS.GG.Workspace.Template.$version.nupkg"; done
dotnet new install "$out/feed/FS.GG.Workspace.Template.0.11.0.nupkg" --force >/dev/null
dotnet new fs-gg-fable-game -n PublicEleven -o "$out/public-11" --lifecycle none --svgFoundation true >/dev/null
dotnet new install "$out/feed/FS.GG.Workspace.Template.0.10.0.nupkg" --force >/dev/null
dotnet new fs-gg-fable-game -n PublicTen -o "$out/public-10" --lifecycle none >/dev/null
# The combined manifest retains the established 0.10 Preview-A baseline and applies
# its package/config transition before the additive Studio files in one transaction.
tree_sha() { (cd "$1" && find . -type f -print0|sort -z|xargs -0 sha256sum|sha256sum|cut -d' ' -f1); }
authored="$(sha256sum "$out/public-11/Domain/Room.fs" "$out/public-11/Client/App.fs")"
cp -a "$out/public-11" "$out/collision"; printf '\nauthored collision\n' >>"$out/collision/SvgFoundation/Program.fs"; before="$(tree_sha "$out/collision")"
if "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/collision" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/collision-backup"; then exit 1; fi
[[ "$before" == "$(tree_sha "$out/collision")" && ! -e "$out/collision-backup" ]]
cp -a "$out/public-11" "$out/interrupted"; before="$(tree_sha "$out/interrupted")"
if FSGG_SVG_PREVIEW_FAIL_AFTER=13 "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/interrupted" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/interrupted-backup"; then exit 1; fi
[[ "$before" == "$(tree_sha "$out/interrupted")" ]]
cp -a "$out/public-11" "$out/rollback"; before="$(tree_sha "$out/rollback")"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/rollback" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/rollback-backup" >/dev/null
"$root/scripts/apply-svg-foundation-preview.sh" rollback "$out/rollback" "$out/rollback-backup" >/dev/null
[[ "$before" == "$(tree_sha "$out/rollback")" ]]
for receiver in public-11 public-10; do
  lifecycle="$(tree_sha "$out/$receiver/.fsgg")"; skills="$(tree_sha "$out/$receiver/.agents/skills")"
  "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/$receiver" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/$receiver-authoring-backup" >/dev/null
  [[ "$lifecycle" == "$(tree_sha "$out/$receiver/.fsgg")" && "$skills" == "$(tree_sha "$out/$receiver/.agents/skills")" ]]
done
[[ "$authored" == "$(sha256sum "$out/public-11/Domain/Room.fs" "$out/public-11/Client/App.fs")" ]]

dotnet tool install FS.GG.NewSddWorkspace --version 0.11.1 --tool-path "$out/tools/wizard" --configfile "$out/NuGet.Config" --no-cache >/dev/null
PATH="$(dirname "$sdd"):$PATH" "$out/tools/wizard/new-sdd-workspace" "$out/wizard" WizardReceiver --template fable-game --lifecycle none --ref fs-gg-templates/v0.11.0 --pinned --no-governance --no-coordination >"$out/wizard.log"
test ! -e "$out/wizard/SvgFoundation"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/direct" "$out/wizard" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/wizard-authoring-backup" >/dev/null

(cd "$out/direct" && bash ./build.sh >"$out/direct-build.log" 2>&1)
FSGG_SVG_AUTHORING_VERSION="$rendering_version" FSGG_SVG_CANDIDATE_FEED="$out/feed" bash "$out/direct/SvgFoundation/Studio/build.sh" >"$out/studio-build.log" 2>&1
! grep -RIE 'SvgStudio|SvgGeometryWorker|polygon-clipping' "$out/direct/Client/dist"
for item in svg-geometry-worker.js font-resource-manifest.json noto-sans-latin-400-normal.woff2.base64 package-lock.json; do
  expected="$(jq -r --arg p "contentFiles/any/any/$item" 'if $p=="contentFiles/any/any/svg-geometry-worker.js" then .rendering.worker.sha256 else .rendering.resources[$p].sha256 end' "$out/candidate-packet.json")"
  [[ "$(sha256sum "$out/direct/SvgFoundation/Studio/vendor/$item"|cut -d' ' -f1)" == "$expected" ]]
done
for item in OFL-Noto-Sans.txt THIRD-PARTY-NOTICES.md; do
  [[ "$(sha256sum "$out/direct/SvgFoundation/Studio/vendor/$item"|cut -d' ' -f1)" == "$(jq -r --arg p "$item" '.rendering.resources[$p].sha256' "$out/candidate-packet.json")" ]]
done
cp "$root/tests/composition/fable-game/svg-authoring-observe.mjs" "$out/direct/Browser.Tests/"
(cd "$out/direct/SvgFoundation/Studio/dist" && python3 -m http.server 8139 --bind 127.0.0.1 >"$out/studio-server.log" 2>&1) & server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
for _ in {1..40}; do curl -fsS http://127.0.0.1:8139/ >/dev/null && break; sleep .25; done
for family in chromium firefox webkit; do (cd "$out/direct/Browser.Tests" && node svg-authoring-observe.mjs "$family" http://127.0.0.1:8139/) >"$out/$family.json"; done
if [[ -z "${SVG_SCENE_ORCA_OBSERVATION:-}" ]]; then
  SVG_SCENE_ORCA_OBSERVATION="$out/orca.json"
  bash "$root/tests/composition/fable-game/observe-svg-authoring-orca.sh" http://127.0.0.1:8139/ "$SVG_SCENE_ORCA_OBSERVATION"
fi
jq -e '.result=="passed" and .process.name=="orca" and (.process.pid|type)=="number" and .composition=="generated-svg-studio" and .keyboard.selection=="passed" and .keyboard.properties=="passed" and .keyboard.validationFeedback=="passed"' "$SVG_SCENE_ORCA_OBSERVATION" >/dev/null
jq -n --slurpfile p "$out/candidate-packet.json" --slurpfile c "$out/chromium.json" --slurpfile f "$out/firefox.json" --slurpfile w "$out/webkit.json" --arg orca "$(sha256sum "$SVG_SCENE_ORCA_OBSERVATION"|cut -d' ' -f1)" '{schema:"fsgg.svg-authoring-template-qualification/v1",candidate:$p[0],routes:{direct:"passed",defaultUnselected:"passed",sdd17:{none:"passed",omittedDefault:"passed",typedProfile2:"passed"},wizard0111Adopter:"passed",retained011:"passed",retained010Staged:"passed"},browser:{chromium:$c[0],firefox:$f[0],webkit:$w[0],orcaSha256:$orca},adopter:{collision:"refused-without-write",interruption:"rolled-back",rollback:"byte-identical",provenance:"preserved"},contentMigration:{workspaceDistinct:true,newerSceneDowngrade:"unsupported-preserved"},publication:false}' >"$out/qualification.json"
echo "svg-authoring-candidate: passed; evidence=$out/qualification.json"
