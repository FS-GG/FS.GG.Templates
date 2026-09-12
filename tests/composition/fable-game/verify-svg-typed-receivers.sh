#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?qualification output directory is required}"
rendering_revision=c654a33bb206c6f3aa0a3adb310231a0d54aec63
templates_revision=6a66e0a31c33feab4c8f650709b585df6ac3d4c4
older_templates_revision=565ad45d2dda386e9d1673071cc0b424cfd02be6
sdd_version=1.7.0
wizard_version=0.11.1
scene_version=0.29.0
template_version=0.11.0
older_template_version=0.10.0
template_public_sha=41fa91ba1674a4c1140c4054d4e76cff00cd514462dcdb3d9b3e3cdfa22ba4d9
older_template_public_sha=69cbed30447e6bd4d221e0ce78060c8245d2744fc3993b4c27368aeeb48d11c8
quint_sha=939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f
lmt_sha=37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10
: "${QUINT_BIN:?set QUINT_BIN to qualified Quint 0.32.0}"
: "${LMT_BIN:?set LMT_BIN to qualified lmt}"

fail() { echo "svg-typed-receivers: $*" >&2; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
fable_api_sha() { unzip -p "$1" 'fable/*.fsi' | sha256sum | cut -d' ' -f1; }
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }
[[ -x "$QUINT_BIN" && "$(sha "$QUINT_BIN")" == "$quint_sha" ]] || fail 'Quint object mismatch'
[[ -x "$LMT_BIN" && "$(sha "$LMT_BIN")" == "$lmt_sha" ]] || fail 'lmt object mismatch'
[[ "$($QUINT_BIN --version)" == 0.32.0 ]] || fail 'Quint version mismatch'

rm -rf "$out"
mkdir -p "$out/feed" "$out/build" "$out/packages" "$out/http" "$out/tools" "$out/homes/tool" "$out/homes/clean" "$out/homes/retained" "$out/homes/sdd-none" "$out/homes/wizard"
export NUGET_PACKAGES="$out/packages"
export NUGET_HTTP_CACHE_PATH="$out/http"

git clone --quiet https://github.com/FS-GG/FS.GG.Rendering.git "$out/build/rendering"
git -C "$out/build/rendering" checkout --quiet "$rendering_revision"
[[ "$(git -C "$out/build/rendering" rev-parse HEAD)" == "$rendering_revision" ]] || fail 'Rendering source drifted'
[[ "$(git ls-remote https://github.com/FS-GG/FS.GG.Rendering.git refs/tags/v${scene_version} | cut -f1)" == "$rendering_revision" ]] || fail 'Rendering release tag drifted'
[[ "$(git ls-remote https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/fs-gg-templates/v${template_version}^{}" | cut -f1)" == "$templates_revision" ]] || fail 'Templates release tag drifted'
[[ "$(git ls-remote https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/fs-gg-templates/v${older_template_version}^{}" | cut -f1)" == "$older_templates_revision" ]] || fail 'Templates retained-baseline tag drifted'
curl --fail --location --retry 3 \
  "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/fs-gg-templates/v${older_template_version}/providers/fable-game.providers.yml" \
  --output "$out/build/fable-game-${older_template_version}.providers.yml"
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
[[ "$(sha "$out/feed/FS.GG.Workspace.Template.$template_version.nupkg")" == "$template_public_sha" ]] || fail 'Templates 0.11.0 public archive drifted'
[[ "$(sha "$out/feed/FS.GG.Workspace.Template.$older_template_version.nupkg")" == "$older_template_public_sha" ]] || fail 'Templates 0.10.0 public archive drifted'

cat >"$out/Public.NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
cat >"$out/Candidate.NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF

cli=''
for attempt in 1 2 3; do
  tool_dir="$out/tools/sdd-$attempt"
  if DOTNET_CLI_HOME="$out/homes/tool" dotnet tool install FS.GG.SDD.Cli --version "$sdd_version" --tool-path "$tool_dir" --configfile "$out/Public.NuGet.Config" --no-cache; then
    cli="$tool_dir/fsgg-sdd"; break
  fi
  echo "svg-typed-receivers: public SDD install attempt $attempt failed" >&2
  [[ "$attempt" == 3 ]] || sleep 10
done
[[ -x "$cli" ]] || fail 'public SDD installation failed'
"$cli" --version | tee "$out/sdd-version.txt"
grep -F "$sdd_version" "$out/sdd-version.txt" >/dev/null || fail 'public SDD version mismatch'

if ! env HTTP_PROXY=http://127.0.0.1:1 HTTPS_PROXY=http://127.0.0.1:1 ALL_PROXY=http://127.0.0.1:1 NO_PROXY=127.0.0.1,localhost \
  "$cli" typed-sdd provision --cache "$out/cache" --quint "$QUINT_BIN" --lmt "$LMT_BIN" >"$out/provision.json"; then
  cat "$out/provision.json" >&2; fail 'exact profile-2 provision failed'
fi
jq -e '.outcome == "succeeded" and .profile == "fsgg-quint-profile/2"' "$out/provision.json" >/dev/null

pin_provider() {
  local destination="$1" package="$2" descriptor="$3"
  mkdir -p "$destination/.fsgg"
  cp "$descriptor" "$destination/.fsgg/providers.yml"
  python3 - "$destination/.fsgg/providers.yml" "$package" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); package = Path(sys.argv[2]).resolve()
text = p.read_text()
text = text.replace('source: FS.GG.Workspace.Template::0.11.0', f'source: {package}')
p.write_text(text)
PY
}

scaffold() {
  local destination="$1" package="$2" report="$3" lifecycle="$4" include_svg="$5" descriptor="$6"
  local receiver_name="$(basename "$destination")"
  local params=(--param productName=TypedReceiver --param rootNamespace=TypedReceiver --param lifecycle="$lifecycle")
  [[ "$include_svg" == true ]] && params+=(--param svgFoundation=true)
  pin_provider "$destination" "$package" "$descriptor"
  DOTNET_CLI_HOME="$out/homes/$receiver_name" "$cli" scaffold --root "$destination" --provider fable-game --no-update --json \
    "${params[@]}" >"$report"
  jq -e '.outcome == "succeeded" and .scaffold.providerInvoked == true' "$report" >/dev/null
  jq -e --arg lifecycle "$lifecycle" '[.effectiveParameters[] | select(.key == "lifecycle" and .value == $lifecycle)] | length == 1' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  if [[ "$include_svg" == true ]]; then
    jq -e '[.effectiveParameters[] | select(.key == "svgFoundation" and (.value == "true" or .value == true))] | length == 1' \
      "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  fi
  test -f "$destination/.agents/skills/skill-manifest.json"
}

current_package="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
old_package="$out/feed/FS.GG.Workspace.Template.$older_template_version.nupkg"
scaffold "$out/clean" "$current_package" "$out/clean-scaffold.json" typed-sdd true "$root/providers/fable-game.providers.yml"
scaffold "$out/retained" "$old_package" "$out/retained-scaffold.json" typed-sdd false "$out/build/fable-game-${older_template_version}.providers.yml"
scaffold "$out/sdd-none" "$current_package" "$out/sdd-none-scaffold.json" none true "$root/providers/fable-game.providers.yml"

wizard_dir="$out/tools/wizard"
DOTNET_CLI_HOME="$out/homes/tool" dotnet tool install FS.GG.NewSddWorkspace --version "$wizard_version" \
  --tool-path "$wizard_dir" --configfile "$out/Public.NuGet.Config" --no-cache >/dev/null
PATH="$(dirname "$cli"):$PATH" DOTNET_CLI_HOME="$out/homes/wizard" "$wizard_dir/new-sdd-workspace" \
  "$out/wizard" WizardReceiver --template fable-game --lifecycle none \
  --ref "fs-gg-templates/v${template_version}" --pinned --no-governance --no-coordination >"$out/wizard-scaffold.log"
test ! -e "$out/wizard/SvgFoundation"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/sdd-none" "$out/wizard" \
  "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/wizard-adoption-backup" >"$out/wizard-adoption.log"
test -f "$out/wizard/SvgFoundation/PreviewDocument.fs"
jq -e '[.effectiveParameters[] | select(.key == "lifecycle" and .value == "none")] | length == 1' \
  "$out/wizard/.fsgg/scaffold-provenance.json" >/dev/null
jq -e '.status == "pending"' "$out/wizard/.fsgg/workspace-initialization.json" >/dev/null

authored_before="$(sha256sum "$out/retained/Domain/Room.fs" "$out/retained/Client/App.fs")"
lifecycle_before="$(tree_sha "$out/retained/.fsgg")"
skills_before="$(tree_sha "$out/retained/.agents/skills")"
retained_before="$(tree_sha "$out/retained")"
cp -a "$out/retained" "$out/conflict"
mkdir -p "$out/conflict/SvgFoundation"
printf 'authored collision\n' >"$out/conflict/SvgFoundation/TacticalCompatibility.fs"
conflict_before="$(tree_sha "$out/conflict")"
if "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/clean" "$out/conflict" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/conflict-backup" >"$out/conflict.log" 2>&1; then
  fail 'retained collision unexpectedly applied'
fi
[[ "$conflict_before" == "$(tree_sha "$out/conflict")" ]] || fail 'collision refusal modified retained workspace'
grep -F 'preview adoption conflict: SvgFoundation/TacticalCompatibility.fs' "$out/conflict.log" >/dev/null
[[ ! -e "$out/conflict-backup" ]] || fail 'collision refusal created a backup/write artifact'
cp -a "$out/retained" "$out/interrupted"
interrupted_before="$(tree_sha "$out/interrupted")"
if FSGG_SVG_PREVIEW_FAIL_AFTER=4 "$root/scripts/apply-svg-foundation-preview.sh" apply "$out/clean" "$out/interrupted" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/interrupted-backup" >"$out/interrupted.log" 2>&1; then
  fail 'interrupted retained adoption unexpectedly succeeded'
fi
[[ "$interrupted_before" == "$(tree_sha "$out/interrupted")" ]] || fail 'interrupted adoption was not rolled back atomically'
grep -F 'injected interruption after 4 managed files; rollback completed' "$out/interrupted.log" >/dev/null
cp -a "$out/retained" "$out/rollback-probe"
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/clean" "$out/rollback-probe" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/rollback-backup" >"$out/rollback-apply.log"
"$root/scripts/apply-svg-foundation-preview.sh" rollback "$out/rollback-probe" "$out/rollback-backup" >"$out/rollback.log"
[[ "$retained_before" == "$(tree_sha "$out/rollback-probe")" ]] || fail 'explicit rollback did not restore retained workspace bytes'
"$root/scripts/apply-svg-foundation-preview.sh" apply "$out/clean" "$out/retained" "$root/scripts/svg-foundation-preview-baseline.manifest" "$out/adoption-backup" >"$out/adoption.log"
[[ "$authored_before" == "$(sha256sum "$out/retained/Domain/Room.fs" "$out/retained/Client/App.fs")" ]] || fail 'retained authored files changed'
[[ "$lifecycle_before" == "$(tree_sha "$out/retained/.fsgg")" ]] || fail 'retained lifecycle provenance changed'
[[ "$skills_before" == "$(tree_sha "$out/retained/.agents/skills")" ]] || fail 'installed skills were refreshed during adoption'

for receiver in clean retained sdd-none wizard; do
  (cd "$out/$receiver" && bash ./build.sh >"$out/$receiver-root-build.log" 2>&1) || {
    tail -n 160 "$out/$receiver-root-build.log" >&2
    fail "$receiver root build/test/browser entry failed"
  }
  dotnet restore "$out/$receiver/SvgFoundation/SvgFoundation.fsproj" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  (cd "$out/$receiver" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache >/dev/null)
  mkdir -p "$out/$receiver/models/svg-foundation"
  cp "$out/build/rendering/models/svg-foundation/retained-interaction.md" "$out/$receiver/models/svg-foundation/"
  cp "$out/build/rendering/models/svg-foundation/retained-interaction.bindings.json" "$out/$receiver/models/svg-foundation/"
  cp "$out/build/rendering/models/svg-foundation/retained-interaction.traces.tsv" "$out/$receiver/models/svg-foundation/"
  cp "$out/build/rendering/models/svg-foundation/document-interaction.traces.tsv" "$out/$receiver/models/svg-foundation/"
done

observe_foundation() {
  local receiver="$1" port="$2" server_pid
  cp "$root/tests/composition/fable-game/svg-preview-observe.mjs" "$out/$receiver/Browser.Tests/"
  (cd "$out/$receiver/SvgFoundation" && python3 -m http.server "$port" --bind 127.0.0.1 >"$out/$receiver-foundation-server.log" 2>&1) &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' RETURN
  for _ in {1..40}; do curl -fsS "http://127.0.0.1:$port/" >/dev/null && break; sleep .25; done
  (cd "$out/$receiver/Browser.Tests" && node svg-preview-observe.mjs "http://127.0.0.1:$port/") >"$out/$receiver-foundation-browser.json"
  kill "$server_pid"; wait "$server_pid" 2>/dev/null || true
  trap - RETURN
}
observe_foundation clean 8131
observe_foundation retained 8132
observe_foundation sdd-none 8133
observe_foundation wizard 8134

# The retained journey deliberately changes the bounded pointer domain and updates every explicit
# source range. This is a semantic revision with refreshed bindings, rather than an implementation repair.
python3 - "$out/retained/models/svg-foundation/retained-interaction.md" "$out/retained/models/svg-foundation/retained-interaction.bindings.json" <<'PY'
from pathlib import Path
import json, sys
source = Path(sys.argv[1]); bindings = Path(sys.argv[2])
text = source.read_text().replace('nondet pointerId = 1.to(2).oneOf()', 'nondet pointerId = 1.to(3).oneOf()')
source.write_text('<!-- SVG-QUAL-01.3 semantic revision: widen the bounded pointer domain. -->\n' + text)
data = json.loads(bindings.read_text())
for row in data['exports'] + data['actions']:
    row['source']['start']['line'] += 1
    row['source']['end']['line'] += 1
bindings.write_text(json.dumps(data, indent=2) + '\n')
PY

offline() { env HTTP_PROXY=http://127.0.0.1:1 HTTPS_PROXY=http://127.0.0.1:1 ALL_PROXY=http://127.0.0.1:1 NO_PROXY=127.0.0.1,localhost "$@"; }
author_inspect() {
  local receiver="$1" session="$2"
  if ! offline "$cli" typed-sdd author --root "$out/$receiver" --work svg-qual-01-3 \
    --title 'Typed SVG retained receiver qualification' --agent codex --session "$session" \
    --backend quint-specification-v1 --cache "$out/cache" --profile fsgg-quint-profile/2 \
    --source models/svg-foundation/retained-interaction.md \
    --bindings models/svg-foundation/retained-interaction.bindings.json >"$out/$receiver-author.json"; then
    cat "$out/$receiver-author.json" >&2; fail "$receiver installed author failed"
  fi
  if ! offline "$cli" typed-sdd inspect --root "$out/$receiver" --work svg-qual-01-3 >"$out/$receiver-inspect.json"; then
    cat "$out/$receiver-inspect.json" >&2; fail "$receiver installed inspect failed"
  fi
  jq -e '.outcome == "succeeded"' "$out/$receiver-inspect.json" >/dev/null
}
author_inspect clean clean-current-semantics
author_inspect retained retained-semantic-revision
[[ "$(sha "$out/clean/readiness/svg-qual-01-3/quint/retainedInteraction.qnt")" != "$(sha "$out/retained/readiness/svg-qual-01-3/quint/retainedInteraction.qnt")" ]] || fail 'semantic revision did not refresh extracted model'
[[ "$(sha "$out/clean/readiness/svg-qual-01-3/quint/profile-bindings.json")" != "$(sha "$out/retained/readiness/svg-qual-01-3/quint/profile-bindings.json")" ]] || fail 'semantic revision did not refresh generated bindings'

for receiver in clean retained; do
  qnt="$out/$receiver/readiness/svg-qual-01-3/quint/retainedInteraction.qnt"
  "$QUINT_BIN" typecheck "$qnt" >"$out/$receiver-quint-typecheck.log"
  "$QUINT_BIN" test "$qnt" --main retainedInteractionTest >"$out/$receiver-quint-test.log"
done
for run in a b; do
  mkdir -p "$out/retained-traces-$run"
  "$QUINT_BIN" run "$out/retained/readiness/svg-qual-01-3/quint/retainedInteraction.qnt" \
    --main retainedInteraction --invariant retainedStateSafe --max-steps 12 --max-samples 32 \
    --n-traces 32 --seed=0x0123456789abcdef --backend=typescript \
    --out-itf "$out/retained-traces-$run/trace_{seq}.itf.json" --verbosity 0 >"$out/retained-quint-run-$run.log"
  python3 "$out/build/rendering/tests/svg-foundation/extract-retained-traces.py" "$out/retained-traces-$run.tsv" "$out/retained-traces-$run"/*.itf.json
done
cmp "$out/retained-traces-a.tsv" "$out/retained-traces-b.tsv" >/dev/null || fail 'semantic-change model corpus was nondeterministic'
awk -F '\t' 'NR > 1 && ($3 == "CapturePointer" || $3 == "ReleasePointer") && $5 == 3 { found=1 } END { exit !found }' "$out/retained-traces-a.tsv" \
  || fail 'semantic-change corpus did not exercise the widened pointer domain'
cp "$out/retained-traces-a.tsv" "$out/retained/models/svg-foundation/retained-interaction.traces.tsv"

prepare_consumer() {
  local receiver="$1"
  mkdir -p "$out/$receiver/Qualification/DotNet" "$out/$receiver/Qualification/Fable" "$out/$receiver/readiness/svg-qual-01-3/correspondence"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/Replay.fs" "$out/$receiver/Qualification/DotNet/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/Replay.fs" "$out/$receiver/Qualification/Fable/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/DocumentRoundTrip.fs" "$out/$receiver/Qualification/DotNet/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/DocumentRoundTrip.fs" "$out/$receiver/Qualification/Fable/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/DocumentReplay.fs" "$out/$receiver/Qualification/DotNet/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/DocumentReplay.fs" "$out/$receiver/Qualification/Fable/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/DotNet/"{DotNet.fsproj,Program.fs} "$out/$receiver/Qualification/DotNet/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/Fable/"{Fable.fsproj,Program.fs} "$out/$receiver/Qualification/Fable/"
  python3 - "$out/$receiver/Qualification/DotNet/DotNet.fsproj" "$out/$receiver/Qualification/Fable/Fable.fsproj" "$scene_version" <<'PY'
from pathlib import Path
import sys

for name in sys.argv[1:3]:
    project = Path(name)
    text = project.read_text()
    old = 'PackageReference Include="FS.GG.UI.Scene" Version="0.29.0-preview.1"'
    new = f'PackageReference Include="FS.GG.UI.Scene" Version="[{sys.argv[3]}]"'
    if text.count(old) != 1:
        raise SystemExit(f'{project}: expected one Rendering preview pin, found {text.count(old)}')
    project.write_text(text.replace(old, new))
PY
}

replay_consumer() {
  local receiver="$1"
  local evidence="$out/$receiver/readiness/svg-qual-01-3/correspondence"
  dotnet restore "$out/$receiver/Qualification/DotNet/DotNet.fsproj" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  dotnet build "$out/$receiver/Qualification/DotNet/DotNet.fsproj" --no-restore >/dev/null
  dotnet run --project "$out/$receiver/Qualification/DotNet/DotNet.fsproj" --no-build -- \
    "$out/$receiver/models/svg-foundation/retained-interaction.traces.tsv" "$evidence/dotnet.tsv" \
    "$evidence/dotnet-document.txt" "$evidence/dotnet-export.svg" \
    "$out/$receiver/models/svg-foundation/document-interaction.traces.tsv" "$evidence/dotnet-document.tsv" >"$evidence/dotnet.log"
  dotnet restore "$out/$receiver/Qualification/Fable/Fable.fsproj" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  if [[ ! -x "$out/tools/fable/fable" ]]; then
    dotnet tool install fable --version 5.17.0 --tool-path "$out/tools/fable" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  fi
  "$out/tools/fable/fable" "$out/$receiver/Qualification/Fable/Fable.fsproj" --outDir "$out/$receiver/Qualification/javascript" --noCache >/dev/null
  node "$out/$receiver/Qualification/javascript/Program.js" \
    "$out/$receiver/models/svg-foundation/retained-interaction.traces.tsv" "$evidence/fable.tsv" \
    "$evidence/fable-document.txt" "$evidence/fable-export.svg" \
    "$out/$receiver/models/svg-foundation/document-interaction.traces.tsv" "$evidence/fable-document.tsv" >"$evidence/fable.log"
  cmp "$evidence/dotnet.tsv" "$evidence/fable.tsv" >/dev/null || fail "$receiver .NET/Fable first divergence"
  cmp "$evidence/dotnet-document.tsv" "$evidence/fable-document.tsv" >/dev/null || fail "$receiver .NET/Fable document reducer first divergence"
  cmp "$evidence/dotnet-document.txt" "$evidence/fable-document.txt" >/dev/null || fail "$receiver .NET/Fable document serialization drift"
  cmp "$evidence/dotnet-export.svg" "$evidence/fable-export.svg" >/dev/null || fail "$receiver .NET/Fable SVG export drift"
  grep -F 'action-mapping-mutant=killed stale-acceptance-mutant=killed' "$evidence/dotnet.log" >/dev/null
  grep -F 'action-mapping-mutant=killed stale-acceptance-mutant=killed' "$evidence/fable.log" >/dev/null
  for mutant in wrong-order stale-revision-acceptance invalid-reference-acceptance lost-capture non-atomic-edit; do
    grep -F "name=$mutant killed-at=DOCUMENT-TRACE-DIVERGENCE" "$evidence/dotnet.log" >/dev/null
    grep -F "name=$mutant killed-at=DOCUMENT-TRACE-DIVERGENCE" "$evidence/fable.log" >/dev/null
  done
}

for receiver in clean retained sdd-none wizard; do prepare_consumer "$receiver"; replay_consumer "$receiver"; done

# An implementation-only repair reuses the accepted authority and trace corpus.
clean_authority_before="$(tree_sha "$out/clean/readiness/svg-qual-01-3/quint")"
printf '\n// implementation-only diagnostic repair; no semantic authority change\n' >>"$out/clean/Qualification/DotNet/Program.fs"
replay_consumer clean
[[ "$clean_authority_before" == "$(tree_sha "$out/clean/readiness/svg-qual-01-3/quint")" ]] || fail 'implementation repair rewrote semantic authority'

# Installed CLI refusal controls.
cp -a "$out/clean" "$out/stale-bindings"
sed -i '1i<!-- stale range mutation -->' "$out/stale-bindings/models/svg-foundation/retained-interaction.md"
if offline "$cli" typed-sdd author --root "$out/stale-bindings" --work stale --title stale --agent codex --session stale \
  --backend quint-specification-v1 --cache "$out/cache" --profile fsgg-quint-profile/2 \
  --source models/svg-foundation/retained-interaction.md --bindings models/svg-foundation/retained-interaction.bindings.json >"$out/stale-bindings.json"; then
  fail 'stale bindings unexpectedly authored'
fi
grep -F 'typedSdd.v2.compilationFailed' "$out/stale-bindings.json" >/dev/null || fail 'stale binding diagnostic drifted'

mkdir -p "$out/wrong-profile/models/svg-foundation"
cp "$out/build/rendering/models/svg-foundation/retained-interaction."{md,bindings.json} "$out/wrong-profile/models/svg-foundation/"
if offline "$cli" typed-sdd author --root "$out/wrong-profile" --work wrong-profile --title wrong-profile --agent codex --session wrong-profile \
  --backend quint-specification-v1 --cache "$out/cache" --profile fsgg-quint-profile/1 \
  --source models/svg-foundation/retained-interaction.md --bindings models/svg-foundation/retained-interaction.bindings.json >"$out/wrong-profile.json"; then
  manifest="$out/wrong-profile/readiness/wrong-profile/typed-authority.json"
  jq -e '.profileIdentity == "fsgg-quint-profile/1" and .backend == "quint-specification-v1"' "$manifest" >/dev/null \
    || fail 'wrong-profile output did not disclose its actual identity'
  if jq -e '.profileIdentity == "fsgg-quint-profile/2"' "$manifest" >/dev/null; then
    fail 'wrong profile unexpectedly satisfied the receiver contract'
  fi
  jq -n --arg observed "$(jq -r .profileIdentity "$manifest")" \
    '{outcome:"refused",requiredProfile:"fsgg-quint-profile/2",observedProfile:$observed,reason:"receiver-profile-mismatch"}' \
    >"$out/wrong-profile-refusal.json"
else
  jq -e '.outcome == "failed"' "$out/wrong-profile.json" >/dev/null
fi

cp "$QUINT_BIN" "$out/wrong-quint"; printf x >>"$out/wrong-quint"; chmod +x "$out/wrong-quint"
if offline "$cli" typed-sdd provision --cache "$out/wrong-cache" --quint "$out/wrong-quint" --lmt "$LMT_BIN" >"$out/wrong-tools.json"; then
  fail 'wrong tool object unexpectedly provisioned'
fi
jq -e '.outcome == "blocked" and any(.diagnostics[]; .id == "typedSdd.provision.objectMismatch")' "$out/wrong-tools.json" >/dev/null

scene_package="$out/feed/FS.GG.UI.Scene.$scene_version.nupkg"
keyboard_package="$out/feed/FS.GG.UI.KeyboardInput.$scene_version.nupkg"
browser_package="$out/feed/FS.GG.UI.Scene.SvgBrowser.$scene_version.nupkg"
templates_source="$templates_revision"
jq -n --arg templates "$templates_source" --arg rendering "$rendering_revision" --arg older "$older_templates_revision" \
  --arg scene "$(sha "$scene_package")" --arg keyboard "$(sha "$keyboard_package")" --arg browser "$(sha "$browser_package")" --arg template "$(sha "$current_package")" \
  --arg sceneFableApi "$(fable_api_sha "$scene_package")" --arg keyboardFableApi "$(fable_api_sha "$keyboard_package")" \
  --arg browserFableApi "$(fable_api_sha "$browser_package")" \
  --arg cleanAuthority "$(tree_sha "$out/clean/readiness/svg-qual-01-3/quint")" \
  --arg retainedAuthority "$(tree_sha "$out/retained/readiness/svg-qual-01-3/quint")" \
  --arg cleanProjection "$(sha "$out/clean/readiness/svg-qual-01-3/correspondence/dotnet.tsv")" \
  --arg retainedProjection "$(sha "$out/retained/readiness/svg-qual-01-3/correspondence/dotnet.tsv")" \
  --arg cleanDocumentProjection "$(sha "$out/clean/readiness/svg-qual-01-3/correspondence/dotnet-document.tsv")" \
  --arg retainedDocumentProjection "$(sha "$out/retained/readiness/svg-qual-01-3/correspondence/dotnet-document.tsv")" \
  --arg cleanCorpus "$(sha "$out/clean/models/svg-foundation/retained-interaction.traces.tsv")" \
  --arg retainedCorpus "$(sha "$out/retained/models/svg-foundation/retained-interaction.traces.tsv")" \
  --arg documentCorpus "$(sha "$out/clean/models/svg-foundation/document-interaction.traces.tsv")" \
  --argjson cleanBrowser "$(cat "$out/clean-foundation-browser.json")" --argjson retainedBrowser "$(cat "$out/retained-foundation-browser.json")" \
  --argjson noneBrowser "$(cat "$out/sdd-none-foundation-browser.json")" --argjson wizardBrowser "$(cat "$out/wizard-foundation-browser.json")" \
  '{schema:"fsgg.svg-typed-receivers/4",sources:{templates:$templates,rendering:$rendering,olderTemplate:$older},sdd:{package:"FS.GG.SDD.Cli",version:"1.7.0",source:"https://api.nuget.org/v3/index.json",backend:"quint-specification-v1",profile:"fsgg-quint-profile/2",authorInspect:"offline-passed"},wizard:{package:"FS.GG.NewSddWorkspace",version:"0.11.1",source:"nuget.org",route:"fable-game none then bounded SVG adopter"},artifacts:{scene:{version:"0.29.0",source:"nuget.org",sha256:$scene,fableApiSha256:$sceneFableApi},keyboardInput:{version:"0.29.0",source:"nuget.org",sha256:$keyboard,fableApiSha256:$keyboardFableApi},svgBrowser:{version:"0.29.0",source:"nuget.org",sha256:$browser,fableApiSha256:$browserFableApi},template:{version:"0.11.0",source:"nuget.org",sha256:$template},olderTemplate:{version:"0.10.0",source:"nuget.org"},distribution:"public-nuget-only",releaseOrder:["FS.GG.UI.Scene","FS.GG.UI.KeyboardInput","FS.GG.UI.Scene.SvgBrowser","FS.GG.Workspace.Template"],archiveRetention:"exact public producer bytes and interface hashes uploaded"},corpora:{retainedTransitions:192,documentTransitions:192,relationship:"retained subject plus additive document-interaction expansion",documentSha256:$documentCorpus},journeys:{clean:{selection:"lifecycle=typed-sdd,svgFoundation=true",rootBuildTestBrowser:"passed",foundationBrowser:$cleanBrowser,model:{tests:"passed",corpusSha256:$cleanCorpus},authoritySha256:$cleanAuthority,projectionSha256:$cleanProjection,documentProjectionSha256:$cleanDocumentProjection,result:"passed"},retained:{base:"public Templates 0.10.0",adoption:"bounded-package-config-delta",rootBuildTestBrowser:"passed",foundationBrowser:$retainedBrowser,semanticChange:"pointer domain 1..2 to 1..3 with refreshed source bindings",model:{tests:"passed",boundedRun:"passed",steps:12,traces:32,seed:"0x0123456789abcdef",deterministic:"passed",newPointerWitness:3,corpusSha256:$retainedCorpus},authoritySha256:$retainedAuthority,projectionSha256:$retainedProjection,documentProjectionSha256:$retainedDocumentProjection,authoredFiles:"unchanged",lifecycle:"typed-sdd-preserved",ownerGuidance:"preserved",installedSkills:"unchanged-no-backfill",result:"passed"},sddNone:{selection:"lifecycle=none,svgFoundation=true",rootBuildTestBrowser:"passed",foundationBrowser:$noneBrowser,result:"passed"},wizard:{selection:"fable-game,lifecycle=none",adoption:"released Templates bounded SVG adopter",rootBuildTestBrowser:"passed",foundationBrowser:$wizardBrowser,result:"passed"},implementationRepair:"reused-current-semantics-and-replayed",collision:"reported-without-write",interruptedAdoption:"refused-and-byte-identical-rollback",explicitRollback:"byte-identical"},refusals:{wrongTools:"passed",wrongProfile:"passed",staleBindings:"passed"},apiComparison:{assembly:"Rendering 0.29.0 release gates passed",fable:"public producer interface digests retained per package",result:"compatible-public-producer"},authority:{enginePublication:"verified",templatePublication:"verified",installedPublicQualification:"passed",defaultActivation:"unchanged"}}' >"$out/svg-typed-receivers.json"
jq -e '.journeys.clean.result == "passed" and .journeys.retained.result == "passed" and .journeys.sddNone.result == "passed" and .journeys.wizard.result == "passed" and .refusals.wrongTools == "passed" and .artifacts.keyboardInput.version == "0.29.0" and .authority.installedPublicQualification == "passed" and .corpora.retainedTransitions == 192 and .corpora.documentTransitions == 192' "$out/svg-typed-receivers.json" >/dev/null
echo "svg-typed-receivers: clean=passed retained=passed controls=passed evidence=$out/svg-typed-receivers.json"
