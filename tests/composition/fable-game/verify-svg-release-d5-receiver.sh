#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?empty evidence directory required}"
[[ ! -e "$out" ]]
mkdir -p "$out/feed" "$out/home" "$out/packages" "$out/http" "$out/tools"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
public=https://api.nuget.org/v3-flatcontainer
template_version=0.14.0
wizard_version=0.11.2
sdd_version=2.0.2
: "${QUINT_BIN:?set QUINT_BIN to qualified Quint 0.32.0}"
template="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
old_template="$out/feed/FS.GG.Workspace.Template.0.13.0.nupkg"
fail() { echo "svg-release-d5-receiver: $*" >&2; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }
download() { curl --fail --silent --show-error --location --retry 12 --retry-all-errors --retry-delay 5 "$1" --output "$2"; }

download "$public/fs.gg.workspace.template/$template_version/fs.gg.workspace.template.$template_version.nupkg" "$template"
download "$public/fs.gg.workspace.template/0.13.0/fs.gg.workspace.template.0.13.0.nupkg" "$old_template"
download "$public/fs.gg.sdd.cli/$sdd_version/fs.gg.sdd.cli.$sdd_version.nupkg" "$out/feed/FS.GG.SDD.Cli.$sdd_version.nupkg"
download "$public/fs.gg.newsddworkspace/$wizard_version/fs.gg.newsddworkspace.$wizard_version.nupkg" "$out/feed/FS.GG.NewSddWorkspace.$wizard_version.nupkg"
[[ "$(sha "$template")" == a5f218d10bbac42b11afcfb401806c8f0f56261cf79876cc76710471d3666563 ]] || fail 'Templates 0.14.0 archive drift'
[[ "$(sha "$old_template")" == ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c ]] || fail 'Templates 0.13.0 archive drift'
[[ -x "$QUINT_BIN" && "$(sha "$QUINT_BIN")" == 939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f ]] || fail 'Quint object mismatch'
python3 - "$out/feed" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import sys,xml.etree.ElementTree as ET
feed=Path(sys.argv[1])
for name,version in [('FS.GG.Workspace.Template','0.14.0'),('FS.GG.SDD.Cli','2.0.2'),('FS.GG.NewSddWorkspace','0.11.2')]:
    archive=feed/f'{name}.{version}.nupkg'
    with ZipFile(archive) as z:
        nuspec=next(x for x in z.namelist() if x.endswith('.nuspec'))
        root=ET.fromstring(z.read(nuspec))
        metadata=next(x for x in root if x.tag.rsplit('}',1)[-1]=='metadata')
        fields={x.tag.rsplit('}',1)[-1]:x.text for x in metadata}
        assert fields['id']==name and fields['version']==version, archive
PY
config="$out/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
dotnet tool install FS.GG.SDD.Cli --version "$sdd_version" --tool-path "$out/tools/sdd" --configfile "$config" --no-cache >"$out/sdd-install.log"
dotnet tool install FS.GG.NewSddWorkspace --version "$wizard_version" --tool-path "$out/tools/wizard" --configfile "$config" --no-cache >"$out/wizard-install.log"
sdd="$out/tools/sdd/fsgg-sdd"
wizard="$out/tools/wizard/new-sdd-workspace"
"$sdd" --version >"$out/sdd-version.log"
grep -F "$sdd_version" "$out/sdd-version.log" >/dev/null || fail 'SDD executable identity mismatch'
dotnet new install "$template" --force >"$out/template-install.log"

# The direct host, public wizard, and SDD provider must all select the same
# released payload while keeping their explicit lifecycle selection visible.
dotnet new fs-gg-fable-game -n D5Direct -o "$out/direct" --bundle complete --lifecycle typed-sdd >"$out/direct.log"
download "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/fs-gg-templates/v$template_version/providers/fable-game.providers.yml" "$out/public-provider.yml"
grep -F "source: FS.GG.Workspace.Template::$template_version" "$out/public-provider.yml" >/dev/null
mkdir -p "$out/provider/.fsgg"
cp "$out/public-provider.yml" "$out/provider/.fsgg/providers.yml"
"$sdd" scaffold --root "$out/provider" --provider fable-game --no-update --json \
  --param productName=D5Provider --param rootNamespace=D5Provider \
  --param bundle=complete --param lifecycle=typed-sdd >"$out/provider.json"
jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/provider.json" >/dev/null
PATH="$out/tools/sdd:$PATH" "$wizard" "$out/wizard" D5Wizard --template fable-game \
  --bundle complete --lifecycle typed-sdd --ref "fs-gg-templates/v$template_version" \
  --pinned --no-governance --no-coordination >"$out/wizard.log"

python3 - "$out" <<'PY'
from pathlib import Path
from hashlib import sha256
import json, sys
out=Path(sys.argv[1]); expected=None
for name in ('direct','provider','wizard'):
    root=out/name
    if name!='direct':
        provenance=json.loads((root/'.fsgg/scaffold-provenance.json').read_text())
        assert any(x['key']=='lifecycle' and x['value']=='typed-sdd' for x in provenance['effectiveParameters']), name
    assert (root/'models/svg-replay/energy-rules.md').is_file(), name
    assert (root/'models/svg-replay/energy-rules.bindings.json').is_file(), name
    assert (root/'models/svg-arena/correspondence.qnt').is_file(), name
    assert (root/'models/svg-tactical/correspondence.qnt').is_file(), name
    assert (root/'SvgFoundation/Examples/Tactical/scene.json').is_file(), name
    assert (root/'SvgFoundation/Examples/Arcade/scene.json').is_file(), name
    manifest=json.loads((root/'.agents/skills/skill-manifest.json').read_text())
    missing=[]
    for row in manifest['skills']:
        body=root/row['resolvablePath']
        if body.is_file(): assert sha256(body.read_bytes()).hexdigest()==row['sha256'], (name,row['id'])
        else: missing.append(row['id'])
    assert missing==['fable-bindings'], (name,missing)
    locks=list(root.rglob('packages.lock.json'))
    assert locks and (root/'Client/package-lock.json').is_file(), name
    if name!='direct':
        typed_skill=(root/'.agents/skills/fs-gg-sdd-typed-author/SKILL.md').read_text()
        assert 'omitted backend is `quint-specification-v1`' in typed_skill, name
    current={p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in
             (root/'models/svg-replay/energy-rules.md',root/'models/svg-replay/energy-rules.bindings.json',
              root/'models/svg-arena/correspondence.qnt',root/'models/svg-tactical/correspondence.qnt')}
    if expected is None: expected=current
    else: assert current==expected, name
PY

# A separate omitted selection demonstrates the pre-OperatingV2 default.
mkdir -p "$out/omitted/.fsgg"
cp "$out/public-provider.yml" "$out/omitted/.fsgg/providers.yml"
"$sdd" scaffold --root "$out/omitted" --provider fable-game --no-update --json \
  --param productName=D5Omitted --param rootNamespace=D5Omitted --param bundle=player >"$out/omitted.log"
jq -e '[.effectiveParameters[]|select(.key=="lifecycle" and .value=="sdd")]|length==1' \
  "$out/omitted/.fsgg/scaffold-provenance.json" >/dev/null

# Retained 0.13.0 typed work receives only the supported complete product
# transaction. Authored content, lifecycle provenance, and local skills survive.
mkdir -p "$out/old-home"
DOTNET_CLI_HOME="$out/old-home" dotnet new install "$old_template" --force >"$out/old-install.log"
download 'https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/fs-gg-templates/v0.13.0/providers/fable-game.providers.yml' "$out/old-provider.yml"
mkdir -p "$out/retained/.fsgg"
cp "$out/old-provider.yml" "$out/retained/.fsgg/providers.yml"
python3 - "$out/retained/.fsgg/providers.yml" "$old_template" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); package=Path(sys.argv[2]).resolve()
value,count=re.subn(r'(?m)^(\s*source:\s*)FS\.GG\.Workspace\.Template::[^\s#]+',
                    lambda m:m.group(1)+str(package),p.read_text())
assert count==1
p.write_text(value)
PY
DOTNET_CLI_HOME="$out/old-home" "$sdd" scaffold --root "$out/retained" --provider fable-game --no-update --json \
  --param productName=D5Retained --param rootNamespace=D5Retained \
  --param lifecycle=typed-sdd --param svgFoundation=true >"$out/retained-create.log"
mkdir -p "$out/retained/authored" "$out/retained/.agents/skills/local-gameplay"
printf '%s\n' '{"level":"retained"}' >"$out/retained/authored/level.json"
printf '%s\n' '# Retained owner guidance' >"$out/retained/.agents/skills/local-gameplay/SKILL.md"
before="$(sha "$out/retained/authored/level.json") $(sha "$out/retained/.agents/skills/local-gameplay/SKILL.md") $(sha "$out/retained/.fsgg/scaffold-provenance.json")"
adopter="$root/scripts/apply-svg-foundation-preview.sh"
manifest="$root/scripts/svg-complete-workspace-baselines.json"
cp -a "$out/retained" "$out/original"
"$adopter" complete-inventory "$out/direct" "$out/retained" "$manifest" \
  "$out/retained-inventory.json" "$out/retained-review.diff" >"$out/retained-inventory.log"
jq -e '.ready==true and (.changes|length)>0 and (.conflicts|length)==0' "$out/retained-inventory.json" >/dev/null
"$adopter" complete-apply "$out/direct" "$out/retained" "$manifest" \
  "$out/retained-inventory.json" "$out/retained-backup" >"$out/retained-apply.log"
[[ "$before" == "$(sha "$out/retained/authored/level.json") $(sha "$out/retained/.agents/skills/local-gameplay/SKILL.md") $(sha "$out/retained/.fsgg/scaffold-provenance.json")" ]] || fail 'retained owner or lifecycle content changed'
jq -e '[.effectiveParameters[]|select(.key=="lifecycle" and .value=="typed-sdd")]|length==1' "$out/retained/.fsgg/scaffold-provenance.json" >/dev/null

cp -a "$out/original" "$out/conflict"
printf '%s\n' '// owner edit' >>"$out/conflict/Domain/Room.fs"
conflict_before="$(tree_sha "$out/conflict")"
if "$adopter" complete-inventory "$out/direct" "$out/conflict" "$manifest" \
  "$out/conflict-inventory.json" "$out/conflict-review.diff" >"$out/conflict.log" 2>&1; then
  fail 'authored collision accepted'
fi
[[ "$conflict_before" == "$(tree_sha "$out/conflict")" ]] || fail 'collision changed receiver'
cp -a "$out/original" "$out/interrupted"
interrupted_before="$(tree_sha "$out/interrupted")"
"$adopter" complete-inventory "$out/direct" "$out/interrupted" "$manifest" \
  "$out/interrupted-inventory.json" "$out/interrupted-review.diff" >/dev/null
if FSGG_SVG_COMPLETE_FAIL_AFTER=37 "$adopter" complete-apply "$out/direct" "$out/interrupted" "$manifest" \
  "$out/interrupted-inventory.json" "$out/interrupted-backup" >"$out/interrupted.log" 2>&1; then
  fail 'injected interruption accepted'
fi
[[ "$interrupted_before" == "$(tree_sha "$out/interrupted")" ]] || fail 'interruption did not roll back'
jq -e '.status=="rolled-back"' "$out/interrupted-backup/journal.json" >/dev/null
"$adopter" complete-rollback "$out/retained" "$out/retained-backup" >"$out/rollback.log"
[[ "$(tree_sha "$out/original")" == "$(tree_sha "$out/retained")" ]] || fail 'explicit rollback changed retained bytes'

(cd "$out/direct" && dotnet restore D5Direct.slnx --locked-mode --configfile "$config" && dotnet build D5Direct.slnx --no-restore) >"$out/direct-build.log" 2>&1 || { tail -n 80 "$out/direct-build.log" >&2; fail 'locked direct build'; }
(cd "$out/provider" && dotnet restore D5Provider.slnx --locked-mode --configfile "$config" && dotnet build D5Provider.slnx --no-restore) >"$out/provider-build.log" 2>&1 || { tail -n 80 "$out/provider-build.log" >&2; fail 'locked provider build'; }
(cd "$out/wizard" && dotnet restore D5Wizard.slnx --locked-mode --configfile "$config" && dotnet build D5Wizard.slnx --no-restore) >"$out/wizard-build.log" 2>&1 || { tail -n 80 "$out/wizard-build.log" >&2; fail 'locked wizard build'; }
QUINT_BIN="$QUINT_BIN" bash "$out/direct/scripts/check-svg-arena-model.sh" >"$out/arena-model.log" 2>&1 || { tail -n 80 "$out/arena-model.log" >&2; fail 'arena model and correspondence'; }
QUINT_BIN="$QUINT_BIN" bash "$out/direct/scripts/check-svg-tactical-model.sh" >"$out/tactical-model.log" 2>&1 || { tail -n 80 "$out/tactical-model.log" >&2; fail 'tactical model and correspondence'; }

python3 - "$out" <<'PY'
from pathlib import Path
from hashlib import sha256
import json,sys
out=Path(sys.argv[1]); feed=out/'feed'
(out/'qualification.json').write_text(json.dumps({
  'schema':'fsgg.svg-release-d5.receiver-qualification/v1',
  'result':'passed', 'activation':'pending-OperatingV2',
  'templates':{'version':'0.14.0','source':'nuget.org','sha256':sha256((feed/'FS.GG.Workspace.Template.0.14.0.nupkg').read_bytes()).hexdigest()},
  'wizard':{'version':'0.11.2','source':'nuget.org','sha256':sha256((feed/'FS.GG.NewSddWorkspace.0.11.2.nupkg').read_bytes()).hexdigest()},
  'sdd':{'version':'2.0.2','source':'nuget.org','sha256':sha256((feed/'FS.GG.SDD.Cli.2.0.2.nupkg').read_bytes()).hexdigest(),'generatedBackendGuidance':'quint-specification-v1'},
  'clean':['direct','provider','wizard'],
  'selection':'explicit typed-sdd complete',
  'omittedLifecycle':'sdd',
  'retained':'0.13.0 typed-sdd preserved; collision, interruption and explicit rollback passed',
  'lockedBuild':['direct','provider','wizard'],
  'modelCorrespondence':['arena','tactical']
},indent=2)+'\n')
PY
echo "svg-release-d5-receiver: passed; evidence=$out/qualification.json"
