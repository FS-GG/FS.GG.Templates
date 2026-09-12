#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?packet output directory is required}"
rendering_revision=c4e50dcb239ccb62453cdd47505f1a8d1095814e
older_templates_revision=d19fc1d48647edfebad4a706db64648017fead65
template_version=0.11.0-preview.1
scene_version=0.29.0-preview.1
rm -rf "$out"; mkdir -p "$out/feed" "$out/build" "$out/homes/current" "$out/homes/old"
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }
sha() { sha256sum "$1" | cut -d' ' -f1; }
fable_api_sha() { unzip -p "$1" 'fable/*.fsi' | sha256sum | cut -d' ' -f1; }

git clone --quiet https://github.com/FS-GG/FS.GG.Rendering.git "$out/build/rendering"
git -C "$out/build/rendering" checkout --quiet "$rendering_revision"
dotnet pack "$out/build/rendering/src/Scene/Scene.fsproj" -c Release -o "$out/feed" -p:Version="$scene_version" >/dev/null
dotnet pack "$out/build/rendering/src/KeyboardInput/KeyboardInput.fsproj" -c Release -o "$out/feed" -p:Version="$scene_version" >/dev/null
dotnet pack "$out/build/rendering/src/Scene.SvgBrowser/Scene.SvgBrowser.fsproj" -c Release -o "$out/feed" -p:Version="$scene_version" >/dev/null
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/feed" -p:Version="$template_version" >/dev/null

mkdir -p "$out/build/old-source"
if ! git -C "$root" cat-file -e "$older_templates_revision^{commit}" 2>/dev/null; then
  git -C "$root" fetch --quiet --depth=1 origin "$older_templates_revision"
fi
git -C "$root" archive "$older_templates_revision" | tar -x -C "$out/build/old-source"
dotnet pack "$out/build/old-source/FS.GG.Templates.csproj" -c Release -o "$out/build" -p:Version=0.10.0-baseline.1 >/dev/null
rm -rf "$out/build/rendering" "$out/build/old-source"

template_package="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
DOTNET_CLI_HOME="$out/homes/current" dotnet new install "$template_package" --force >/dev/null
DOTNET_CLI_HOME="$out/homes/current" dotnet new fs-gg-fable-game -n PreviewFresh -o "$out/fresh" --svgFoundation true --lifecycle none >/dev/null
cat > "$out/NuGet.Config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.Scene*"/><package pattern="FS.GG.UI.KeyboardInput"/><package pattern="FS.GG.Workspace.Template"/></packageSource><packageSource key="nuget"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
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

old_package="$out/build/FS.GG.Workspace.Template.0.10.0-baseline.1.nupkg"
DOTNET_CLI_HOME="$out/homes/old" dotnet new install "$old_package" --force >/dev/null
DOTNET_CLI_HOME="$out/homes/old" dotnet new fs-gg-fable-game -n RetainedOlder -o "$out/older" --svgFoundation true --lifecycle none >/dev/null
DOTNET_CLI_HOME="$out/homes/current" dotnet new fs-gg-fable-game -n RetainedOlder -o "$out/current-materialized" --svgFoundation true --lifecycle none >/dev/null
mkdir -p "$out/current-payload"; unzip -q "$template_package" -d "$out/current-payload"
payload="$out/current-payload/content/templates/fs-gg-fable-game"
adoption_source="$out/current-materialized"
authored_before="$(sha256sum "$out/older/Domain/Room.fs" "$out/older/Client/App.fs")"
test -f "$out/older/.agents/skills/skill-manifest.json"
skills_before="$(find "$out/older/.agents/skills" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)"
retained_before="$(tree_sha "$out/older")"
cp -a "$out/older" "$out/conflict"
printf 'authored collision\n' > "$out/conflict/SvgFoundation/TacticalCompatibility.fs"
collision_before="$(sha256sum "$out/conflict/SvgFoundation/TacticalCompatibility.fs")"
collision_program_before="$(sha256sum "$out/conflict/SvgFoundation/Program.fs")"
if "$root/scripts/apply-svg-foundation-preview.sh" apply "$adoption_source" "$out/conflict" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/conflict-backup" >"$out/conflict.log" 2>&1; then echo 'collision unexpectedly applied' >&2; exit 1; fi
test "$collision_before" = "$(sha256sum "$out/conflict/SvgFoundation/TacticalCompatibility.fs")"
test "$collision_program_before" = "$(sha256sum "$out/conflict/SvgFoundation/Program.fs")"
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
templates_source="$(git -C "$root" rev-parse HEAD)"
scene_package="$out/feed/FS.GG.UI.Scene.$scene_version.nupkg"
keyboard_package="$out/feed/FS.GG.UI.KeyboardInput.$scene_version.nupkg"
browser_package="$out/feed/FS.GG.UI.Scene.SvgBrowser.$scene_version.nupkg"
jq -n --arg rendering "$rendering_revision" --arg templates "$templates_source" --arg older "$older_templates_revision" --arg payload "$payload_tree" --argjson browser "$(cat "$out/browser-observation.json")" \
  --arg sceneHash "$(sha "$scene_package")" --arg keyboardHash "$(sha "$keyboard_package")" \
  --arg browserHash "$(sha "$browser_package")" --arg templateHash "$(sha "$template_package")" \
  --arg sceneFableApi "$(fable_api_sha "$scene_package")" --arg keyboardFableApi "$(fable_api_sha "$keyboard_package")" \
  --arg browserFableApi "$(fable_api_sha "$browser_package")" \
  '{schema:"fsgg.svg-scene-preview-a-handoff/1",sources:{rendering:$rendering,templates:$templates,olderTemplateBaseline:$older},artifacts:{scene:{file:"feed/FS.GG.UI.Scene.0.29.0-preview.1.nupkg",version:"0.29.0-preview.1",sha256:$sceneHash,fableApiSha256:$sceneFableApi},keyboardInput:{file:"feed/FS.GG.UI.KeyboardInput.0.29.0-preview.1.nupkg",version:"0.29.0-preview.1",sha256:$keyboardHash,fableApiSha256:$keyboardFableApi},svgBrowser:{file:"feed/FS.GG.UI.Scene.SvgBrowser.0.29.0-preview.1.nupkg",version:"0.29.0-preview.1",sha256:$browserHash,fableApiSha256:$browserFableApi},template:{file:"feed/FS.GG.Workspace.Template.0.11.0-preview.1.nupkg",version:"0.11.0-preview.1",sha256:$templateHash,payloadTreeSha256:$payload}},requiredLocalFeed:{path:"feed/",publicFallback:"nuget.org for non-FS.GG dependencies",publicationPlan:"Rendering coherent Scene/KeyboardInput/SvgBrowser set, then Templates immutable pins and package, then installed receivers"},selection:"--svgFoundation true --lifecycle none",releaseOrder:[{package:"FS.GG.UI.Scene",owner:"Rendering"},{package:"FS.GG.UI.KeyboardInput",owner:"Rendering"},{package:"FS.GG.UI.Scene.SvgBrowser",owner:"Rendering"},{package:"FS.GG.Workspace.Template",owner:"Templates"}],consumerPins:{scene:"[0.29.0-preview.1]",keyboardInput:"transitive [0.29.0-preview.1]",svgBrowser:"[0.29.0-preview.1]",template:"[0.11.0-preview.1]"},browserObservation:$browser,journeys:{fresh:"passed-build-fable-serve-browser-full-document",retainedUpgrade:"passed-fable-contract",conflict:"reported-without-any-write",interrupted:"refused-and-rolled-back-without-write",explicitRollback:"restored-byte-identical-managed-baseline",authoredFiles:"unchanged",lifecycleSelection:"none-no-lifecycle-state",ownerGuidance:"installed-skill-manifest-retained",installedSkills:"unchanged-no-backfill"},apiComparison:{assembly:"Rendering exact-head ApiCompat gate passed against its published baseline",fable:"generated consumers compiled against the exact archived candidate interfaces whose digests are recorded per package",result:"compatible-candidate"},authority:{localRehearsal:"passed",producerPublication:"pending",templatePublication:"pending",installedPublicQualification:"pending",defaultActivation:"pending"},archiveRetention:"exact candidate archives, interface hashes and receipt uploaded from the exact-head workflow"}' > "$out/preview-packet.json"
jq -e '.journeys.fresh == "passed-build-fable-serve-browser-full-document" and .authority.producerPublication == "pending" and .artifacts.keyboardInput.version == "0.29.0-preview.1"' "$out/preview-packet.json" >/dev/null
echo "svg-foundation-preview-packet: fresh-serve=passed retained-upgrade=passed conflict=passed manifest=$out/preview-packet.json"
