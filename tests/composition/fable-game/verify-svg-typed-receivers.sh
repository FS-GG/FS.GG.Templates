#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?qualification output directory is required}"
rendering_revision=815783987fbf1d6f2e8165e2ae31ddf0bf61db2d
older_templates_revision=d19fc1d48647edfebad4a706db64648017fead65
sdd_version=1.7.0
scene_version=0.4.0-preview.1
template_version=0.11.0-preview.1
quint_sha=939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f
lmt_sha=37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10
: "${QUINT_BIN:?set QUINT_BIN to qualified Quint 0.32.0}"
: "${LMT_BIN:?set LMT_BIN to qualified lmt}"

fail() { echo "svg-typed-receivers: $*" >&2; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }
[[ -x "$QUINT_BIN" && "$(sha "$QUINT_BIN")" == "$quint_sha" ]] || fail 'Quint object mismatch'
[[ -x "$LMT_BIN" && "$(sha "$LMT_BIN")" == "$lmt_sha" ]] || fail 'lmt object mismatch'
[[ "$($QUINT_BIN --version)" == 0.32.0 ]] || fail 'Quint version mismatch'

rm -rf "$out"
mkdir -p "$out/feed" "$out/build" "$out/packages" "$out/http" "$out/tools" "$out/homes/tool" "$out/homes/clean" "$out/homes/retained"
export NUGET_PACKAGES="$out/packages"
export NUGET_HTTP_CACHE_PATH="$out/http"

git clone --quiet https://github.com/FS-GG/FS.GG.Rendering.git "$out/build/rendering"
git -C "$out/build/rendering" checkout --quiet "$rendering_revision"
[[ "$(git -C "$out/build/rendering" rev-parse HEAD)" == "$rendering_revision" ]] || fail 'Rendering source drifted'
dotnet pack "$out/build/rendering/src/Scene/Scene.fsproj" -c Release -o "$out/feed" -p:Version="$scene_version" >/dev/null
dotnet pack "$out/build/rendering/src/Scene.SvgBrowser/Scene.SvgBrowser.fsproj" -c Release -o "$out/feed" -p:Version="$scene_version" >/dev/null
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/feed" -p:Version="$template_version" >/dev/null
mkdir -p "$out/build/old-source"
if ! git -C "$root" cat-file -e "$older_templates_revision^{commit}" 2>/dev/null; then
  git -C "$root" fetch --quiet --depth=1 origin "$older_templates_revision"
fi
git -C "$root" archive "$older_templates_revision" | tar -x -C "$out/build/old-source"
dotnet pack "$out/build/old-source/FS.GG.Templates.csproj" -c Release -o "$out/feed" -p:Version=0.10.0-baseline.1 >/dev/null

cat >"$out/Public.NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
cat >"$out/Candidate.NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.Scene*"/><package pattern="FS.GG.Workspace.Template"/></packageSource><packageSource key="nuget"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
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
  local destination="$1" package="$2"
  mkdir -p "$destination/.fsgg"
  cp "$root/providers/fable-game.providers.yml" "$destination/.fsgg/providers.yml"
  python3 - "$destination/.fsgg/providers.yml" "$package" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); package = Path(sys.argv[2]).resolve()
text = p.read_text()
text = text.replace('source: FS.GG.Workspace.Template::0.10.0', f'source: {package}')
p.write_text(text)
PY
}

scaffold() {
  local destination="$1" package="$2" report="$3"
  local receiver_name="$(basename "$destination")"
  pin_provider "$destination" "$package"
  DOTNET_CLI_HOME="$out/homes/$receiver_name" "$cli" scaffold --root "$destination" --provider fable-game --no-update --json \
    --param productName=TypedReceiver --param rootNamespace=TypedReceiver \
    --param lifecycle=typed-sdd --param svgFoundation=true >"$report"
  jq -e '.outcome == "succeeded" and .scaffold.providerInvoked == true' "$report" >/dev/null
  jq -e '[.effectiveParameters[] | select(.key == "lifecycle" and .value == "typed-sdd")] | length == 1' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  jq -e '[.effectiveParameters[] | select(.key == "svgFoundation" and (.value == "true" or .value == true))] | length == 1' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  test -f "$destination/.agents/skills/skill-manifest.json"
}

current_package="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
old_package="$out/feed/FS.GG.Workspace.Template.0.10.0-baseline.1.nupkg"
scaffold "$out/clean" "$current_package" "$out/clean-scaffold.json"
scaffold "$out/retained" "$old_package" "$out/retained-scaffold.json"

authored_before="$(sha256sum "$out/retained/Domain/Room.fs" "$out/retained/Client/App.fs")"
lifecycle_before="$(tree_sha "$out/retained/.fsgg")"
skills_before="$(tree_sha "$out/retained/.agents/skills")"
cp -a "$out/retained" "$out/conflict"
printf 'authored collision\n' >"$out/conflict/SvgFoundation/TacticalCompatibility.fs"
conflict_before="$(tree_sha "$out/conflict")"
if "$root/scripts/apply-svg-foundation-preview.sh" "$out/clean" "$out/conflict" "$root/scripts/svg-foundation-preview-baseline.manifest" >"$out/conflict.log" 2>&1; then
  fail 'retained collision unexpectedly applied'
fi
[[ "$conflict_before" == "$(tree_sha "$out/conflict")" ]] || fail 'collision refusal modified retained workspace'
grep -F 'preview adoption conflict: SvgFoundation/TacticalCompatibility.fs' "$out/conflict.log" >/dev/null
"$root/scripts/apply-svg-foundation-preview.sh" "$out/clean" "$out/retained" "$root/scripts/svg-foundation-preview-baseline.manifest" >"$out/adoption.log"
[[ "$authored_before" == "$(sha256sum "$out/retained/Domain/Room.fs" "$out/retained/Client/App.fs")" ]] || fail 'retained authored files changed'
[[ "$lifecycle_before" == "$(tree_sha "$out/retained/.fsgg")" ]] || fail 'retained lifecycle provenance changed'
[[ "$skills_before" == "$(tree_sha "$out/retained/.agents/skills")" ]] || fail 'installed skills were refreshed during adoption'

for receiver in clean retained; do
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
done

observe_foundation() {
  local receiver="$1" port="$2" server_pid
  cat >"$out/$receiver/Browser.Tests/svg-foundation-observe.mjs" <<'JS'
import { chromium } from '@playwright/test';
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined;
const browser = await chromium.launch({ headless: true, executablePath });
const page = await browser.newPage();
await page.goto(process.argv[2], { waitUntil: 'networkidle' });
await page.waitForSelector('[data-scene-root-id="foundation-grid"]');
const value = await page.evaluate(() => ({
  roots: [...document.querySelectorAll('[data-scene-root-id]')].map(x => x.getAttribute('data-scene-root-id')),
  selected: document.querySelector('[data-scene-root-id="tactical-compatibility"] [aria-selected="true"]')?.getAttribute('data-scene-object-id'),
  focusable: document.querySelector('[data-scene-root-id="tactical-compatibility"] [tabindex="0"]')?.getAttribute('data-scene-object-id')
}));
if (!value.roots.includes('foundation-continuous') || !value.roots.includes('tactical-compatibility') || value.selected !== 'unit:7' || value.focusable !== 'unit:11') throw new Error(JSON.stringify(value));
console.log(JSON.stringify(value));
await browser.close();
JS
  (cd "$out/$receiver/SvgFoundation" && python3 -m http.server "$port" --bind 127.0.0.1 >"$out/$receiver-foundation-server.log" 2>&1) &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' RETURN
  for _ in {1..40}; do curl -fsS "http://127.0.0.1:$port/" >/dev/null && break; sleep .25; done
  (cd "$out/$receiver/Browser.Tests" && node svg-foundation-observe.mjs "http://127.0.0.1:$port/") >"$out/$receiver-foundation-browser.json"
  kill "$server_pid"; wait "$server_pid" 2>/dev/null || true
  trap - RETURN
}
observe_foundation clean 8131
observe_foundation retained 8132

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
  cp "$out/build/rendering/tests/Scene.PortableConsumers/DotNet/"{DotNet.fsproj,Program.fs} "$out/$receiver/Qualification/DotNet/"
  cp "$out/build/rendering/tests/Scene.PortableConsumers/Fable/"{Fable.fsproj,Program.fs} "$out/$receiver/Qualification/Fable/"
}

replay_consumer() {
  local receiver="$1"
  local evidence="$out/$receiver/readiness/svg-qual-01-3/correspondence"
  dotnet restore "$out/$receiver/Qualification/DotNet/DotNet.fsproj" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  dotnet build "$out/$receiver/Qualification/DotNet/DotNet.fsproj" --no-restore >/dev/null
  dotnet run --project "$out/$receiver/Qualification/DotNet/DotNet.fsproj" --no-build -- \
    "$out/$receiver/models/svg-foundation/retained-interaction.traces.tsv" "$evidence/dotnet.tsv" >"$evidence/dotnet.log"
  dotnet restore "$out/$receiver/Qualification/Fable/Fable.fsproj" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  if [[ ! -x "$out/tools/fable/fable" ]]; then
    dotnet tool install fable --version 5.17.0 --tool-path "$out/tools/fable" --configfile "$out/Candidate.NuGet.Config" >/dev/null
  fi
  "$out/tools/fable/fable" "$out/$receiver/Qualification/Fable/Fable.fsproj" --outDir "$out/$receiver/Qualification/javascript" --noCache >/dev/null
  node "$out/$receiver/Qualification/javascript/Program.js" \
    "$out/$receiver/models/svg-foundation/retained-interaction.traces.tsv" "$evidence/fable.tsv" >"$evidence/fable.log"
  cmp "$evidence/dotnet.tsv" "$evidence/fable.tsv" >/dev/null || fail "$receiver .NET/Fable first divergence"
  grep -F 'action-mapping-mutant=killed stale-acceptance-mutant=killed' "$evidence/dotnet.log" >/dev/null
  grep -F 'action-mapping-mutant=killed stale-acceptance-mutant=killed' "$evidence/fable.log" >/dev/null
}

for receiver in clean retained; do prepare_consumer "$receiver"; replay_consumer "$receiver"; done

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
browser_package="$out/feed/FS.GG.UI.Scene.SvgBrowser.$scene_version.nupkg"
templates_source="$(git -C "$root" rev-parse HEAD)"
jq -n --arg templates "$templates_source" --arg rendering "$rendering_revision" --arg older "$older_templates_revision" \
  --arg scene "$(sha "$scene_package")" --arg browser "$(sha "$browser_package")" --arg template "$(sha "$current_package")" \
  --arg cleanAuthority "$(tree_sha "$out/clean/readiness/svg-qual-01-3/quint")" \
  --arg retainedAuthority "$(tree_sha "$out/retained/readiness/svg-qual-01-3/quint")" \
  --arg cleanProjection "$(sha "$out/clean/readiness/svg-qual-01-3/correspondence/dotnet.tsv")" \
  --arg retainedProjection "$(sha "$out/retained/readiness/svg-qual-01-3/correspondence/dotnet.tsv")" \
  --arg cleanCorpus "$(sha "$out/clean/models/svg-foundation/retained-interaction.traces.tsv")" \
  --arg retainedCorpus "$(sha "$out/retained/models/svg-foundation/retained-interaction.traces.tsv")" \
  --argjson cleanBrowser "$(cat "$out/clean-foundation-browser.json")" --argjson retainedBrowser "$(cat "$out/retained-foundation-browser.json")" \
  '{schema:"fsgg.svg-typed-receivers/1",sources:{templates:$templates,rendering:$rendering,olderTemplate:$older},sdd:{package:"FS.GG.SDD.Cli",version:"1.7.0",source:"https://api.nuget.org/v3/index.json",backend:"quint-specification-v1",profile:"fsgg-quint-profile/2",authorInspect:"offline-passed"},artifacts:{scene:{version:"0.4.0-preview.1",sha256:$scene},svgBrowser:{version:"0.4.0-preview.1",sha256:$browser},template:{version:"0.11.0-preview.1",sha256:$template},distribution:"local-feed-only",archiveReproducibility:"not-claimed; exact qualification bytes retained and hashed"},journeys:{clean:{selection:"lifecycle=typed-sdd,svgFoundation=true",rootBuildTestBrowser:"passed",foundationBrowser:$cleanBrowser,model:{tests:"passed",corpusSha256:$cleanCorpus},authoritySha256:$cleanAuthority,projectionSha256:$cleanProjection,result:"passed"},retained:{base:"older installed template",adoption:"bounded-package-config-delta",rootBuildTestBrowser:"passed",foundationBrowser:$retainedBrowser,semanticChange:"pointer domain 1..2 to 1..3 with refreshed source bindings",model:{tests:"passed",boundedRun:"passed",steps:12,traces:32,seed:"0x0123456789abcdef",deterministic:"passed",newPointerWitness:3,corpusSha256:$retainedCorpus},authoritySha256:$retainedAuthority,projectionSha256:$retainedProjection,authoredFiles:"unchanged",lifecycle:"typed-sdd-preserved",ownerGuidance:"preserved",installedSkills:"unchanged-no-backfill",result:"passed"},implementationRepair:"reused-current-semantics-and-replayed",collision:"reported-without-write"},refusals:{wrongTools:"passed",wrongProfile:"passed",staleBindings:"passed"},authority:{enginePublication:"pending",templatePublication:"pending",defaultActivation:"unchanged"}}' >"$out/svg-typed-receivers.json"
jq -e '.journeys.clean.result == "passed" and .journeys.retained.result == "passed" and .refusals.wrongTools == "passed"' "$out/svg-typed-receivers.json" >/dev/null
echo "svg-typed-receivers: clean=passed retained=passed controls=passed evidence=$out/svg-typed-receivers.json"
