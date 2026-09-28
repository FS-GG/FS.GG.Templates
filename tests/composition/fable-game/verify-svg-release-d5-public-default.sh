#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
pins="$(realpath "${1:?public pins JSON required}")"
out="$(realpath -m "${2:?new absolute evidence directory required}")"
helper="$root/tests/composition/fable-game/d5-public-pins.py"
python3 "$helper" "$pins"
[[ "${3:-}" != --preflight-only ]] || exit 0
fail() { echo "svg-release-d5-public-default: $*" >&2; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
download() { curl --fail --silent --show-error --location --retry 3 "$1" --output "$2"; }
: "${QUINT_BIN:?qualified Quint 0.32.0 required}"
: "${LMT_BIN:?qualified lmt required}"
[[ -x "$QUINT_BIN" && "$(sha "$QUINT_BIN")" == 939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f ]] || fail 'Quint identity mismatch'
[[ -x "$LMT_BIN" && "$(sha "$LMT_BIN")" == 37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10 ]] || fail 'lmt identity mismatch'
[[ ! -e "$out" ]] || fail 'evidence directory must not exist'
mkdir -p "$out/feed" "$out/home" "$out/packages" "$out/http" "$out/tools"
cp "$pins" "$out/pins.json"
pins="$out/pins.json"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
# Work outside all source checkouts. Every package source is either nuget.org
# or our checksum-verified downloads from nuget.org, never a sibling build.
cd "$out"
config="$out/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
mode="$(jq -r .mode "$pins")"
template_version="$(jq -r .templates.version "$pins")"
template_commit="$(jq -r .templates.sourceCommit "$pins")"
tag="fs-gg-templates/v$template_version"
git ls-remote --tags https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/$tag" "refs/tags/$tag^{}" >"$out/tag-refs.log"
python3 - "$out/tag-refs.log" "$tag" "$template_commit" <<'PY'
from pathlib import Path
import sys
refs={ref:sha for sha,ref in (line.split() for line in Path(sys.argv[1]).read_text().splitlines())}
tag='refs/tags/'+sys.argv[2]
assert refs.get(tag+'^{}',refs.get(tag))==sys.argv[3], 'release tag does not identify pinned package source'
PY
fetch_package() {
  local key="$1" id="$2" version expected lower archive
  version="$(jq -r --arg key "$key" '.[$key].version' "$pins")"
  expected="$(jq -r --arg key "$key" '.[$key].sha256' "$pins")"
  lower="${id,,}"
  archive="$out/feed/$id.$version.nupkg"
  download "https://api.nuget.org/v3-flatcontainer/$lower/$version/$lower.$version.nupkg" "$archive"
  [[ "$(sha "$archive")" == "$expected" ]] || fail "$key public archive mismatch"
  python3 "$helper" "$pins" --archive "$archive" --key "$key"
}
fetch_package templates FS.GG.Workspace.Template
fetch_package sdd FS.GG.SDD.Cli
[[ "$mode" != full ]] || fetch_package wizard FS.GG.NewSddWorkspace
package="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
provider="$out/public-provider.yml"
download "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$template_commit/providers/fable-game.providers.yml" "$provider"
download "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$tag/providers/fable-game.providers.yml" "$out/tag-provider.yml"
cmp "$provider" "$out/tag-provider.yml"
[[ "$(sha "$provider")" == "$(jq -r .templates.providerSha256 "$pins")" ]] || fail 'provider identity mismatch'
grep -Fx "    source: FS.GG.Workspace.Template::$template_version" "$provider" >/dev/null
python3 - "$provider" <<'PY'
from pathlib import Path
import re,sys
assert re.search(r'(?m)^      - key: lifecycle\n        required: false\n        default: typed-sdd$',Path(sys.argv[1]).read_text())
PY
check_installed_archive() {
  local name="$1" version="$2" tool_dir="$3" key="$4" installed
  installed="$tool_dir/.store/$name/$version/$name/$version/$name.$version.nupkg"
  [[ -f "$installed" && "$(sha "$installed")" == "$(jq -r --arg key "$key" '.[$key].sha256' "$pins")" ]] || fail "$key installed archive differs from public pin"
}
dotnet tool install FS.GG.SDD.Cli --version 2.0.2 --tool-path "$out/tools/sdd" --configfile "$config" --add-source "$out/feed" --no-cache >"$out/sdd-install.log"
check_installed_archive fs.gg.sdd.cli 2.0.2 "$out/tools/sdd" sdd
sdd="$out/tools/sdd/fsgg-sdd"
[[ "$("$sdd" --version)" == 2.0.2 ]] || fail 'installed SDD identity mismatch'
export PATH="$out/tools/sdd:$PATH"
dotnet new install "$package" --force >"$out/template-install.log"
dotnet new fs-gg-fable-game -n D5Raw -o "$out/raw" >"$out/raw.log"
test -f "$out/raw/SvgFoundation/SvgFoundation.fsproj"
test ! -e "$out/raw/SvgFoundation/Studio"
grep -F 'Cooperative SVG arena' "$out/raw/SvgFoundation/index.html" >/dev/null

check_lifecycle() {
  local destination="$1" expected="$2"
  jq -e --arg expected "$expected" '[.effectiveParameters[]|select(.key=="lifecycle" and .value==$expected)]|length==1' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  jq -e '.generator.id=="FS.GG.SDD.Artifacts" and .generator.version=="2.0.2"' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
}
scaffold() {
  local name="$1" lifecycle="$2" bundle="${3:-player}" legacy="${4:-false}" destination expected
  destination="$out/$name"
  mkdir -p "$destination/.fsgg"
  cp "$provider" "$destination/.fsgg/providers.yml"
  local -a args=(--param "productName=D5${name//-/}" --param "rootNamespace=D5${name//-/}" --param "bundle=$bundle")
  [[ "$lifecycle" == omitted ]] || args+=(--param "lifecycle=$lifecycle")
  [[ "$legacy" == false ]] || args+=(--param svgFoundation=false)
  "$sdd" scaffold --root "$destination" --provider fable-game --no-update --json "${args[@]}" >"$out/$name.json"
  jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  expected="$lifecycle"; [[ "$expected" != omitted ]] || expected=typed-sdd
  check_lifecycle "$destination" "$expected"
  if [[ "$legacy" == true ]]; then
    test ! -e "$destination/SvgFoundation"
    test -f "$destination/Server/Server.fsproj"
  else
    test -f "$destination/SvgFoundation/SvgFoundation.fsproj"
  fi
}
scaffold omitted omitted
for lifecycle in none sdd typed-sdd spec-kit; do scaffold "$lifecycle" "$lifecycle"; done
scaffold complete typed-sdd complete
scaffold legacyOmitted omitted player true
scaffold legacySdd sdd player true
test -f "$out/complete/SvgFoundation/Examples/Tactical/scene.json"
test -f "$out/complete/SvgFoundation/Examples/Arcade/scene.json"
test ! -e "$out/omitted/SvgFoundation/Studio"
python3 - "$out" <<'PY'
from pathlib import Path
import json,sys
out=Path(sys.argv[1])
def params(name):
    p=json.loads((out/name/'.fsgg/scaffold-provenance.json').read_text())
    return {x['key']:x['value'] for x in p['effectiveParameters'] if x['key'] not in ('productName','rootNamespace')}
assert params('omitted')==params('typed-sdd')
PY

receivers=(omitted)
locked_receivers=(raw omitted none sdd typed-sdd spec-kit legacyOmitted legacySdd)
if [[ "$mode" == full ]]; then
  dotnet tool install FS.GG.NewSddWorkspace --version 0.12.0 --tool-path "$out/tools/wizard" --configfile "$config" --add-source "$out/feed" --no-cache >"$out/wizard-install.log"
  check_installed_archive fs.gg.newsddworkspace 0.12.0 "$out/tools/wizard" wizard
  wizard="$out/tools/wizard/new-sdd-workspace"
  for lifecycle in omitted none sdd typed-sdd spec-kit; do
    name="wizard-$lifecycle"
    args=("$out/$name" "D5${name//-/}" --template fable-game --bundle player --ref "$tag" --pinned --no-governance --no-coordination)
    [[ "$lifecycle" == omitted ]] || args+=(--lifecycle "$lifecycle")
    "$wizard" "${args[@]}" >"$out/$name.log"
    expected="$lifecycle"; [[ "$expected" != omitted ]] || expected=typed-sdd
    check_lifecycle "$out/$name" "$expected"
    test -f "$out/$name/SvgFoundation/SvgFoundation.fsproj"
    locked_receivers+=("$name")
  done
  receivers+=(wizard-omitted)
fi

"$sdd" typed-sdd provision --cache "$out/cache" --quint "$QUINT_BIN" --lmt "$LMT_BIN" >"$out/provision.json"
jq -e '.outcome=="succeeded"' "$out/provision.json" >/dev/null
for receiver in "${receivers[@]}"; do
  destination="$out/$receiver"
  mkdir -p "$destination/models"
  cp -a "$out/complete/models/svg-arena" "$destination/models/"
  "$sdd" typed-sdd author --root "$destination" --work d5-default --title 'Public D.5 default receiver' \
    --agent composition --session public-default --cache "$out/cache" --profile fsgg-quint-profile/2 \
    --source models/svg-arena/arena-rules.md --bindings models/svg-arena/arena-rules.bindings.json >"$out/$receiver-author.json"
  jq -e '.outcome=="succeeded" and .classification=="quint-specification-v1"' "$out/$receiver-author.json" >/dev/null
  "$sdd" typed-sdd inspect --root "$destination" --work d5-default >"$out/$receiver-inspect.json"
  jq -e '.outcome=="succeeded" and .classification=="quint-specification-v1"' "$out/$receiver-inspect.json" >/dev/null
  python3 - "$destination" <<'PY'
from pathlib import Path
from hashlib import sha256
import json,sys
root=Path(sys.argv[1]); authority=json.loads((root/'readiness/d5-default/typed-authority.json').read_text())
assert authority['backend']=='quint-specification-v1' and authority['profileIdentity']=='fsgg-quint-profile/2'
assert authority['packageIdentity']=='FS.GG.SDD.Artifacts/2.0.2'
for artifact in authority['artifacts']:
    assert sha256((root/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
bindings=root/'models/svg-arena/arena-rules.bindings.json'
value=json.loads(bindings.read_text()); value['profile']='fsgg-quint-profile/1'
(bindings.parent/'refused.bindings.json').write_text(json.dumps(value)+'\n')
PY
  # Independent bounded simulation of the public authored model, not a claim
  # of exhaustive verification or SDD's full verificationReady lifecycle.
  for invariant in healthBound scoreShape collectedScore wonRequiresCollection terminalOutcome hazardContactImpliesDamage; do
    "$QUINT_BIN" run "$destination/readiness/d5-default/quint/arena-rules.qnt" --main SvgArenaRules \
      --invariant "$invariant" --max-samples 32 --max-steps 12 --seed 0x0123456789abcdef >"$out/$receiver-quint-$invariant.log"
  done
  authority_before="$(sha "$destination/readiness/d5-default/typed-authority.json")"
  if "$sdd" typed-sdd author --root "$destination" --work d5-refused --title 'Public D.5 refusal' \
    --agent composition --session refused --cache "$out/cache" --profile fsgg-quint-profile/2 \
    --source models/svg-arena/arena-rules.md --bindings models/svg-arena/refused.bindings.json >"$out/$receiver-refused.json"; then
    fail "$receiver accepted wrong-profile bindings"
  fi
  jq -e '.outcome=="blocked" and .changedPaths==[] and any(.diagnostics[]; .id=="QUINT-PROFILE-IDENTITY")' "$out/$receiver-refused.json" >/dev/null
  test ! -e "$destination/readiness/d5-refused/typed-authority.json"
  [[ "$(sha "$destination/readiness/d5-default/typed-authority.json")" == "$authority_before" ]] || fail "$receiver refusal changed existing authority"
done

for receiver in "${locked_receivers[@]}"; do
  destination="$out/$receiver"
  solution="$(find "$destination" -maxdepth 1 -name '*.slnx' -print -quit)"
  [[ -n "$solution" ]] || fail "$receiver missing root solution"
  (cd "$destination" && dotnet restore "$solution" --locked-mode --configfile "$config" && dotnet build "$solution" --no-restore) >"$out/$receiver-locked-build.log" 2>&1 || { tail -n 60 "$out/$receiver-locked-build.log" >&2; fail "$receiver locked build"; }
done

python3 - "$out" "$root" <<'PY'
from pathlib import Path
from hashlib import sha256
import json,subprocess,sys
out,source=map(Path,sys.argv[1:]); pins=json.loads((out/'pins.json').read_text())
receivers=['omitted']+(['wizard-omitted'] if pins['mode']=='full' else [])
report={'schema':'fsgg.svg-release-d5.public-default/1','result':'passed','mode':pins['mode'],
        'pins':pins,'packageSource':'nuget.org-only','rawPlayerOmission':'passed',
        'provider':{'omitted':'typed-sdd','explicit':['none','sdd','typed-sdd','spec-kit'],
                    'completeBundle':'passed','legacyFalseOmitted':'typed-sdd','legacyFalseExplicit':'sdd'},
        'wizard':({'omitted':'typed-sdd','explicit':['none','sdd','typed-sdd','spec-kit']} if pins['mode']=='full' else 'pending-not-exercised'),
        'authoredReceivers':receivers,'backend':'quint-specification-v1',
        'authorInspectArtifactHashes':'passed','wrongProfileRefusal':'passed',
        'quintSimulation':{'invariants':6,'samplesPerInvariant':32,'maxSteps':12,'seed':'0x0123456789abcdef','result':'passed','exhaustive':False},
        'verificationBoundary':'compiled authority inspect and sampled invariants; not full SDD verificationReady',
        'lockedBuilds':['raw','omitted','none','sdd','typed-sdd','spec-kit','legacyOmitted','legacySdd']+
                       (['wizard-'+lane for lane in ['omitted','none','sdd','typed-sdd','spec-kit']] if pins['mode']=='full' else []),
        'defaultActivation':'pending-effective-registry-repeat-and-independent-default-readback',
        'source':{'head':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
                  'dirty':bool(subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip())}}
report['evidenceSha256']={str(p.relative_to(out)):sha256(p.read_bytes()).hexdigest()
                        for p in out.glob('*') if p.is_file() and p.suffix in ('.json','.log','.yml')}
report['authoredAuthoritySha256']={name:sha256((out/name/'readiness/d5-default/typed-authority.json').read_bytes()).hexdigest() for name in receivers}
report['toolchainSha256']={'quint':'939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f',
                          'lmt':'37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10'}
report['source']['scriptSha256']=sha256((source/'tests/composition/fable-game/verify-svg-release-d5-public-default.sh').read_bytes()).hexdigest()
(out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
PY
echo "svg-release-d5-public-default: passed ($mode); evidence=$out/qualification.json"
