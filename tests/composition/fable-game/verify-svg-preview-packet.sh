#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?packet output directory is required}"
rendering_revision=c654a33bb206c6f3aa0a3adb310231a0d54aec63
templates_revision=6a66e0a31c33feab4c8f650709b585df6ac3d4c4
older_templates_revision=565ad45d2dda386e9d1673071cc0b424cfd02be6
template_version=0.11.0
older_template_version=0.10.0
scene_version=0.29.0
template_public_sha=41fa91ba1674a4c1140c4054d4e76cff00cd514462dcdb3d9b3e3cdfa22ba4d9
older_template_public_sha=69cbed30447e6bd4d221e0ce78060c8245d2744fc3993b4c27368aeeb48d11c8
rm -rf "$out"; mkdir -p "$out/feed" "$out/build" "$out/homes/current" "$out/homes/old"
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }
sha() { sha256sum "$1" | cut -d' ' -f1; }
fable_api_sha() { unzip -p "$1" 'fable/*.fsi' | sha256sum | cut -d' ' -f1; }

tagged="$(git ls-remote https://github.com/FS-GG/FS.GG.Rendering.git refs/tags/v${scene_version} | cut -f1)"
[[ "$tagged" == "$rendering_revision" ]] || { echo "Rendering v${scene_version} tag drifted: $tagged" >&2; exit 1; }
templates_tagged="$(git ls-remote https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/fs-gg-templates/v${template_version}^{}" | cut -f1)"
[[ "$templates_tagged" == "$templates_revision" ]] || { echo "Templates v${template_version} tag drifted: $templates_tagged" >&2; exit 1; }
older_templates_tagged="$(git ls-remote https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/fs-gg-templates/v${older_template_version}^{}" | cut -f1)"
[[ "$older_templates_tagged" == "$older_templates_revision" ]] || { echo "Templates v${older_template_version} tag drifted: $older_templates_tagged" >&2; exit 1; }
for id in FS.GG.UI.Scene FS.GG.UI.KeyboardInput FS.GG.UI.Scene.SvgBrowser; do
  lower="${id,,}"
  curl --fail --location --retry 3 \
    "https://api.nuget.org/v3-flatcontainer/$lower/$scene_version/$lower.$scene_version.nupkg" \
    --output "$out/feed/$id.$scene_version.nupkg"
done
for version in "$template_version" "$older_template_version"; do
  curl --fail --location --retry 3 \
    "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" \
    --output "$out/feed/FS.GG.Workspace.Template.$version.nupkg"
done

template_package="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
[[ "$(sha "$template_package")" == "$template_public_sha" ]] || { echo 'Templates 0.11.0 public archive drifted' >&2; exit 1; }
[[ "$(sha "$out/feed/FS.GG.Workspace.Template.$older_template_version.nupkg")" == "$older_template_public_sha" ]] || { echo 'Templates 0.10.0 public archive drifted' >&2; exit 1; }
DOTNET_CLI_HOME="$out/homes/current" dotnet new install "$template_package" --force >/dev/null
DOTNET_CLI_HOME="$out/homes/current" dotnet new fs-gg-fable-game -n PreviewFresh -o "$out/fresh" --svgFoundation true --lifecycle none >/dev/null
cat > "$out/NuGet.Config" <<CONFIG
<configuration><packageSources><clear/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
CONFIG
export NUGET_PACKAGES="$out/packages"
dotnet restore "$out/fresh/SvgFoundation/SvgFoundation.fsproj" --configfile "$out/NuGet.Config" >/dev/null
dotnet tool restore --tool-manifest "$out/fresh/.config/dotnet-tools.json" --configfile "$out/NuGet.Config" >/dev/null
dotnet restore "$out/fresh/PreviewFresh.slnx" --locked-mode --configfile "$out/NuGet.Config" >/dev/null
dotnet build "$out/fresh/PreviewFresh.slnx" --no-restore >/dev/null
(cd "$out/fresh" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache >/dev/null)
test ! -e "$out/fresh/work"; test ! -e "$out/fresh/readiness"
if grep -REn 'ProjectReference|<Link>' "$out/fresh/SvgFoundation/"*.fsproj; then echo 'source edge in fresh preview' >&2; exit 1; fi

(cd "$out/fresh/Browser.Tests" && npm ci --silent)
browser="${PLAYWRIGHT_EXECUTABLE_PATH:-}"
if [[ -z "$browser" ]]; then (cd "$out/fresh/Browser.Tests" && npx playwright install --only-shell chromium >/dev/null); fi
(cd "$out/fresh/SvgFoundation" && python3 -m http.server 8127 --bind 127.0.0.1 >"$out/server.log" 2>&1) & server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT
for _ in {1..40}; do curl -fsS http://127.0.0.1:8127/ >/dev/null && break; sleep .25; done
curl -fsS http://127.0.0.1:8127/ >/dev/null
cp "$root/tests/composition/fable-game/svg-preview-observe.mjs" "$out/fresh/Browser.Tests/"
(cd "$out/fresh/Browser.Tests" && node svg-preview-observe.mjs http://127.0.0.1:8127/) > "$out/browser-observation.json"
kill "$server_pid"; trap - EXIT

old_package="$out/feed/FS.GG.Workspace.Template.$older_template_version.nupkg"
DOTNET_CLI_HOME="$out/homes/old" dotnet new install "$old_package" --force >/dev/null
DOTNET_CLI_HOME="$out/homes/old" dotnet new fs-gg-fable-game -n RetainedOlder -o "$out/older" --lifecycle none >/dev/null
DOTNET_CLI_HOME="$out/homes/current" dotnet new fs-gg-fable-game -n RetainedOlder -o "$out/current-materialized" --svgFoundation true --lifecycle none >/dev/null
mkdir -p "$out/current-payload"; unzip -q "$template_package" -d "$out/current-payload"
payload="$out/current-payload/content/templates/fs-gg-fable-game"
adoption_source="$out/current-materialized"
authored_before="$(sha256sum "$out/older/Domain/Room.fs" "$out/older/Client/App.fs")"
test -f "$out/older/.agents/skills/skill-manifest.json"
skills_before="$(find "$out/older/.agents/skills" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)"
retained_before="$(tree_sha "$out/older")"
cp -a "$out/older" "$out/conflict"
mkdir -p "$out/conflict/SvgFoundation"
printf 'authored collision\n' > "$out/conflict/SvgFoundation/TacticalCompatibility.fs"
collision_before="$(tree_sha "$out/conflict")"
if "$root/scripts/apply-svg-foundation-preview.sh" apply "$adoption_source" "$out/conflict" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/conflict-backup" >"$out/conflict.log" 2>&1; then echo 'collision unexpectedly applied' >&2; exit 1; fi
test "$collision_before" = "$(tree_sha "$out/conflict")"
grep -q 'preview adoption conflict: SvgFoundation/TacticalCompatibility.fs' "$out/conflict.log"
test ! -e "$out/conflict-backup"
cp -a "$out/older" "$out/interrupted"
interrupted_before="$(tree_sha "$out/interrupted")"
if FSGG_SVG_PREVIEW_FAIL_AFTER=4 "$root/scripts/apply-svg-foundation-preview.sh" apply "$adoption_source" "$out/interrupted" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/interrupted-backup" >"$out/interrupted.log" 2>&1; then echo 'interrupted adoption unexpectedly applied' >&2; exit 1; fi
test "$interrupted_before" = "$(tree_sha "$out/interrupted")"
grep -q 'injected interruption after 4 managed files; rollback completed' "$out/interrupted.log"
cp -a "$out/older" "$out/rollback-probe"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$adoption_source" "$out/rollback-probe" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/rollback-backup" >"$out/rollback-apply.log"
"$root/scripts/apply-svg-foundation-preview.sh" rollback "$out/rollback-probe" "$out/rollback-backup" >"$out/rollback.log"
test "$retained_before" = "$(tree_sha "$out/rollback-probe")"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$adoption_source" "$out/older" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/adoption-backup" >"$out/adoption.log"
test "$authored_before" = "$(sha256sum "$out/older/Domain/Room.fs" "$out/older/Client/App.fs")"
test "$skills_before" = "$(find "$out/older/.agents/skills" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)"
test ! -e "$out/older/work"; test ! -e "$out/older/readiness"
dotnet restore "$out/older/SvgFoundation/SvgFoundation.fsproj" --configfile "$out/NuGet.Config" >/dev/null
dotnet restore "$out/older/SvgFoundation/TacticalCompatibility.Tests.fsproj" --configfile "$out/NuGet.Config" >/dev/null
(cd "$out/older" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache >/dev/null)
dotnet run --project "$out/older/SvgFoundation/TacticalCompatibility.Tests.fsproj" --no-restore >/dev/null

payload_tree="$(cd "$payload" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"
templates_source="$templates_revision"
scene_package="$out/feed/FS.GG.UI.Scene.$scene_version.nupkg"
keyboard_package="$out/feed/FS.GG.UI.KeyboardInput.$scene_version.nupkg"
browser_package="$out/feed/FS.GG.UI.Scene.SvgBrowser.$scene_version.nupkg"
jq -n --arg rendering "$rendering_revision" --arg templates "$templates_source" --arg older "$older_templates_revision" --arg payload "$payload_tree" --argjson browser "$(cat "$out/browser-observation.json")" \
  --arg sceneHash "$(sha "$scene_package")" --arg keyboardHash "$(sha "$keyboard_package")" \
  --arg browserHash "$(sha "$browser_package")" --arg templateHash "$(sha "$template_package")" \
  --arg sceneFableApi "$(fable_api_sha "$scene_package")" --arg keyboardFableApi "$(fable_api_sha "$keyboard_package")" \
  --arg browserFableApi "$(fable_api_sha "$browser_package")" \
  '{schema:"fsgg.svg-scene-preview-a-handoff/3",sources:{rendering:$rendering,templates:$templates,olderTemplateBaseline:$older},artifacts:{scene:{file:"feed/FS.GG.UI.Scene.0.29.0.nupkg",version:"0.29.0",source:"nuget.org",sha256:$sceneHash,fableApiSha256:$sceneFableApi},keyboardInput:{file:"feed/FS.GG.UI.KeyboardInput.0.29.0.nupkg",version:"0.29.0",source:"nuget.org",sha256:$keyboardHash,fableApiSha256:$keyboardFableApi},svgBrowser:{file:"feed/FS.GG.UI.Scene.SvgBrowser.0.29.0.nupkg",version:"0.29.0",source:"nuget.org",sha256:$browserHash,fableApiSha256:$browserFableApi},template:{file:"feed/FS.GG.Workspace.Template.0.11.0.nupkg",version:"0.11.0",source:"nuget.org",sha256:$templateHash,payloadTreeSha256:$payload},olderTemplate:{file:"feed/FS.GG.Workspace.Template.0.10.0.nupkg",version:"0.10.0",source:"nuget.org"}},qualificationInputs:{rendering:"public nuget.org archives and restore graph",template:"public nuget.org archive",olderTemplate:"public nuget.org archive"},selection:"--svgFoundation true --lifecycle none",releaseOrder:[{package:"FS.GG.UI.Scene",owner:"Rendering",status:"published"},{package:"FS.GG.UI.KeyboardInput",owner:"Rendering",status:"published"},{package:"FS.GG.UI.Scene.SvgBrowser",owner:"Rendering",status:"published"},{package:"FS.GG.Workspace.Template",owner:"Templates",status:"published"}],consumerPins:{scene:"[0.29.0]",keyboardInput:"transitive [0.29.0]",svgBrowser:"[0.29.0]",template:"[0.11.0]"},browserObservation:$browser,journeys:{fresh:"passed-build-fable-serve-browser-full-document",retainedUpgrade:"passed-fable-contract",conflict:"reported-without-any-write",interrupted:"refused-and-rolled-back-without-write",explicitRollback:"restored-byte-identical-managed-baseline",authoredFiles:"unchanged",lifecycleSelection:"none-no-lifecycle-state",ownerGuidance:"installed-skill-manifest-retained",installedSkills:"unchanged-no-backfill"},apiComparison:{assembly:"Rendering 0.29.0 release gates passed against the public baseline",fable:"generated consumers compiled against the public archived interfaces whose digests are recorded per package",result:"compatible-public-producer"},authority:{producerPublication:"verified",templatePublication:"verified",installedPublicQualification:"passed",defaultActivation:"unchanged"},archiveRetention:"exact public Rendering and Templates archives, interface hashes and receipt uploaded from the exact-head workflow"}' > "$out/preview-packet.json"
jq -e '.journeys.fresh == "passed-build-fable-serve-browser-full-document" and .authority.installedPublicQualification == "passed" and .artifacts.keyboardInput.version == "0.29.0" and .artifacts.template.source == "nuget.org"' "$out/preview-packet.json" >/dev/null
echo "svg-foundation-preview-packet: fresh-serve=passed retained-upgrade=passed conflict=passed manifest=$out/preview-packet.json"
