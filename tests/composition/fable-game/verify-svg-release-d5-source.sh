#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?empty output directory required}"
sdd_version=2.1.0
: "${QUINT_BIN:?set QUINT_BIN to qualified Quint 0.32.0}"
: "${LMT_BIN:?set LMT_BIN to qualified lmt}"
[[ ! -e "$out" ]]
mkdir -p "$out/feed" "$out/home" "$out/packages" "$out/http" "$out/tools"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
fail() { echo "svg-release-d5-source: $*" >&2; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[[ -x "$QUINT_BIN" && "$(sha "$QUINT_BIN")" == 939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f ]] || fail 'Quint object mismatch'
[[ -x "$LMT_BIN" && "$(sha "$LMT_BIN")" == 37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10 ]] || fail 'lmt object mismatch'
config="$out/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
# shellcheck source=tests/composition/fable-game/svg-source-python-fixture.sh
. "$root/tests/composition/fable-game/svg-source-python-fixture.sh"
prepare_svg_source_python_fixture "$root" "$out"
package_properties="$(dotnet msbuild "$root/FS.GG.Templates.csproj" -nologo -getProperty:PackageId -getProperty:Version)"
package_id="$(jq -er '.Properties.PackageId | select(. == "FS.GG.Workspace.Template")' <<<"$package_properties")"
package_version="$(jq -er '.Properties.Version | select(test("^[0-9A-Za-z][0-9A-Za-z.+-]*$"))' <<<"$package_properties")"
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/feed" >"$out/pack.log"
mapfile -t packages < <(find "$out/feed" -maxdepth 1 -type f -name '*.nupkg' -print)
[[ "${#packages[@]}" == 1 ]] || fail "expected exactly one source candidate, found ${#packages[@]}"
package="${packages[0]}"
[[ "$(basename "$package")" == "$package_id.$package_version.nupkg" ]] || fail "source candidate filename does not match producer properties"
package_sha="$(sha "$package")"
source_revision="$(git -C "$root" rev-parse HEAD)"
dotnet run --project "$root/src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj" -c Release -- \
  published-tool-check --archive "$package" --sha256 "$package_sha" --package-id "$package_id" \
  --version "$package_version" --source-revision "$source_revision" >/dev/null
python3 - "$package" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import json,sys
archive=Path(sys.argv[1])
with ZipFile(archive) as z:
    entries={p:json.loads(z.read(p)) for p in z.namelist() if p.endswith('fs-gg-fable-game/.template.config/template.json') or p.endswith('fs-gg-fable-game-legacy/.template.config/template.json')}
    assert len(entries)==2, entries.keys()
    for path,data in entries.items():
        expected='sdd' if 'legacy' in path else 'typed-sdd'
        assert data['symbols']['lifecycle']['defaultValue']==expected, (path,expected)
        assert [x['choice'] for x in data['symbols']['lifecycle']['choices']]==['none','sdd','typed-sdd','spec-kit']
PY
python3 "$root/tests/composition/lib/lifecycle-contract.py" --root "$root" --self-test >"$out/lifecycle-contract.log"
dotnet tool install FS.GG.SDD.Cli --version "$sdd_version" --tool-path "$out/tools/sdd" --configfile "$config" --no-cache >"$out/sdd-install.log"
sdd="$out/tools/sdd/fsgg-sdd"
"$sdd" --version >"$out/sdd-version.log"
installed_sdd_version="$(cat "$out/sdd-version.log")"
[[ "$installed_sdd_version" == "$sdd_version" ]] || fail "installed SDD version mismatch: expected $sdd_version, observed $installed_sdd_version"
dotnet new install "$package" --force >"$out/template-install.log"

# Raw dotnet new proves the omitted SVG Player product. The SDD-owned root
# lifecycle is qualified separately through the provider below.
dotnet new fs-gg-fable-game -n D5Raw -o "$out/raw" >"$out/raw.log"
test -f "$out/raw/SvgFoundation/SvgFoundation.fsproj"
test ! -e "$out/raw/SvgFoundation/Studio"
grep -F 'Cooperative SVG arena' "$out/raw/SvgFoundation/index.html" >/dev/null

provider="$out/provider.yml"
cp "$root/providers/fable-game.providers.yml" "$provider"
python3 - "$provider" "$package" "$package_id::$package_version" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); package=Path(sys.argv[2]).resolve(); expected=sys.argv[3]
text=p.read_text(); needle=f"source: {expected}"
if text.count(needle) != 1:
    raise SystemExit(f"{p}: expected exactly one current Templates source {expected}")
p.write_text(text.replace(needle, f"source: {package}"))
PY

scaffold() {
  local name="$1" lifecycle="$2" bundle="${3:-player}" destination
  destination="$out/$name"
  mkdir -p "$destination/.fsgg"
  cp "$provider" "$destination/.fsgg/providers.yml"
  local -a args=(--param "productName=D5${name}" --param "rootNamespace=D5${name}" --param "bundle=$bundle")
  [[ "$lifecycle" == omitted ]] || args+=(--param "lifecycle=$lifecycle")
  "$sdd" scaffold --root "$destination" --provider fable-game --no-update --json "${args[@]}" >"$out/$name.json"
  jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  local expected="$lifecycle"
  [[ "$lifecycle" == omitted ]] && expected=typed-sdd
  jq -e --arg expected "$expected" '[.effectiveParameters[]|select(.key=="lifecycle" and .value==$expected)]|length==1' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  test -f "$destination/SvgFoundation/SvgFoundation.fsproj"
}
scaffold omitted omitted
scaffold typed typed-sdd
scaffold sdd sdd
scaffold none none
scaffold spec-kit spec-kit
scaffold complete typed-sdd complete
test -f "$out/complete/SvgFoundation/Examples/Tactical/scene.json"
test -f "$out/complete/SvgFoundation/Examples/Arcade/scene.json"
test ! -e "$out/omitted/SvgFoundation/Studio"

# The retained selector still creates its non-SVG product under this new
# package. Provider defaults are unconditional: the current candidate records typed-sdd for
# omitted lifecycle even when svgFoundation=false, while explicit sdd wins.
legacy_scaffold() {
  local name="$1" lifecycle="$2" destination
  destination="$out/$name"
  mkdir -p "$destination/.fsgg"
  cp "$provider" "$destination/.fsgg/providers.yml"
  local -a args=(--param "productName=D5${name}" --param "rootNamespace=D5${name}" --param svgFoundation=false)
  [[ "$lifecycle" == omitted ]] || args+=(--param "lifecycle=$lifecycle")
  "$sdd" scaffold --root "$destination" --provider fable-game --no-update --json "${args[@]}" >"$out/$name.json"
  jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  local expected="$lifecycle"
  [[ "$lifecycle" == omitted ]] && expected=typed-sdd
  jq -e --arg expected "$expected" '[.effectiveParameters[]|select(.key=="lifecycle" and .value==$expected)]|length==1' \
    "$destination/.fsgg/scaffold-provenance.json" >/dev/null
  test ! -e "$destination/SvgFoundation"
  test -f "$destination/Server/Server.fsproj"
}
legacy_scaffold legacyOmitted omitted
legacy_scaffold legacySdd sdd

python3 - "$out/omitted/.fsgg/scaffold-provenance.json" "$out/typed/.fsgg/scaffold-provenance.json" <<'PY'
from pathlib import Path
import json,sys
a,b=(json.loads(Path(p).read_text()) for p in sys.argv[1:])
def params(v):
    return {x['key']:x['value'] for x in v['effectiveParameters'] if x['key'] not in ('productName','rootNamespace')}
assert params(a)==params(b), (params(a),params(b))
PY

# The omitted provider is an actual SDD root. Author against the selected installed
# SDD without spelling the backend and inspect its committed v2 authority.
# Player intentionally omits Studio models; a receiver can author one from the
# same candidate's complete-bundle model after clean scaffold.
mkdir -p "$out/omitted/models"
cp -a "$out/complete/models/svg-arena" "$out/omitted/models/"
"$sdd" typed-sdd provision --cache "$out/cache" --quint "$QUINT_BIN" --lmt "$LMT_BIN" >"$out/provision.json"
jq -e '.outcome=="succeeded"' "$out/provision.json" >/dev/null
"$sdd" typed-sdd author --root "$out/omitted" --work d5-default --title 'D.5 default receiver' \
  --agent composition --session clean-start --cache "$out/cache" --profile fsgg-quint-profile/2 \
  --source models/svg-arena/arena-rules.md --bindings models/svg-arena/arena-rules.bindings.json >"$out/author.json"
jq -e '.outcome=="succeeded"' "$out/author.json" >/dev/null
"$sdd" typed-sdd inspect --root "$out/omitted" --work d5-default >"$out/inspect.json"
jq -e '.outcome=="succeeded"' "$out/inspect.json" >/dev/null
jq -e '.backend=="quint-specification-v1" and .profileIdentity=="fsgg-quint-profile/2"' \
  "$out/omitted/readiness/d5-default/typed-authority.json" >/dev/null

python3 - "$out/omitted/models/svg-arena/arena-rules.bindings.json" "$out/omitted/models/svg-arena/refused.bindings.json" <<'PY'
from pathlib import Path
import json,sys
value=json.loads(Path(sys.argv[1]).read_text()); value['profile']='fsgg-quint-profile/1'
Path(sys.argv[2]).write_text(json.dumps(value,indent=2)+'\n')
PY
if "$sdd" typed-sdd author --root "$out/omitted" --work d5-refused --title 'D.5 refusal' \
  --agent composition --session refused --cache "$out/cache" --profile fsgg-quint-profile/2 \
  --source models/svg-arena/arena-rules.md --bindings models/svg-arena/refused.bindings.json >"$out/refused.json"; then
  fail 'wrong-profile bindings were accepted'
fi
test ! -e "$out/omitted/readiness/d5-refused/typed-authority.json"

(cd "$out/omitted" && dotnet restore D5omitted.slnx --locked-mode --configfile "$config" && dotnet build D5omitted.slnx --no-restore) >"$out/locked-build.log" 2>&1 || { tail -n 80 "$out/locked-build.log" >&2; fail 'omitted locked build'; }
(cd "$out/legacyOmitted" && dotnet restore D5legacyOmitted.slnx --locked-mode --configfile "$config" && dotnet build D5legacyOmitted.slnx --no-restore) >"$out/legacy-locked-build.log" 2>&1 || { tail -n 80 "$out/legacy-locked-build.log" >&2; fail 'legacy omitted locked build'; }

python3 - "$package" "$package_version" "$out/qualification.json" "$installed_sdd_version" <<'PY'
from pathlib import Path
from hashlib import sha256
import json,sys
archive=Path(sys.argv[1]); version=sys.argv[2]; report=Path(sys.argv[3]); sdd_version=sys.argv[4]
report.write_text(json.dumps({
  'schema':'fsgg.svg-release-d5.source-candidate/v1',
  'status':'source-candidate-only',
  'templates':{'version':version,'candidateSha256':sha256(archive.read_bytes()).hexdigest(),'publication':'pending'},
  'sdd':{'version':sdd_version,'source':'nuget.org','omittedBackend':'quint-specification-v1'},
  'newFableGameOmission':'typed-sdd',
  'rawPlayer':'passed',
  'provider':{'omitted':'typed-sdd','explicit':['none','sdd','typed-sdd','spec-kit'],'completeBundle':'passed','authorInspect':'passed','refusal':'passed','lockedBuild':'passed','legacyFalseOmitted':'typed-sdd-non-svg-locked-build-passed','legacyFalseExplicitSdd':'passed'},
  'otherProviders':'sdd',
  'wizard':'pending-owner-package-and-public-receiver',
  'defaultActivation':'pending-public-composition-and-registry-readback'
},indent=2)+'\n')
PY
echo "svg-release-d5-source: passed; evidence=$out/qualification.json"
