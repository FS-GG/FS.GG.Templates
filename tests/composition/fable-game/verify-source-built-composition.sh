#!/usr/bin/env bash
# Source stage for the typed DOM composition cases against a Workspace.Template PACKED FROM THE CHECKED-OUT SOURCE.
# Same public Rendering archives, locked graph, Fable/Vite/server builds and plan-bound Playwright config as the
# published-template stage, but the template under test is a local nupkg whose identity the caller recorded. It
# performs no browser run, and its verdict is "source-built": it never claims published or installed acceptance.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
producer_feed="${1:?public Rendering archive directory required}"
out="${2:?empty qualification directory required}"
plan="${3:?typed source-built plan required}"
archive_in="${4:?source-packed template archive required}"
archive_sha="${5:?source-packed template archive SHA256 required}"
[[ "$#" -eq 5 ]]
[[ "$archive_sha" =~ ^[0-9a-f]{64}$ && -f "$archive_in" && -f "$plan" && ! -e "$out" ]]
python3 "$root/tests/composition/fable-game/current-composition-observations.py" --check-admission
[[ "${FSGG_REFERENCE_PROVIDER_TOOL_DLL:-}" = /* && -f "$FSGG_REFERENCE_PROVIDER_TOOL_DLL" ]]
printf '%s  %s\n' "$archive_sha" "$archive_in" | sha256sum --check --strict >/dev/null
mkdir -p "$out"/{feed,home,packages,http}
out="$(realpath "$out")"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1
cp "$plan" "$out/current-composition-plan.json"
read -r version expected_source < <(python3 - "$out/current-composition-plan.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
assert p['template'] == {'origin':'source-built','id':'FS.GG.Workspace.Template'}, 'source-built plan required'
print(p['rendering']['version'], p['rendering']['sourceCommit'])
PY
)
python3 "$root/tests/composition/fable-game/current-composition-observations.py" inputs "$out/current-composition-plan.json" "$version" "$expected_source" "$archive_sha"
rmdir "$out/feed"
python3 "$root/tests/composition/fable-game/current-composition-observations.py" staged-feed "$out/current-composition-plan.json" "$producer_feed" "$out/feed"
python3 "$root/tests/composition/fable-game/current-composition-observations.py" public-readback "$out/current-composition-plan.json" "$out/feed/public-readback.json"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' > "$out/NuGet.Config"
# The package's own identity, read from the archive (the runner also recorded the source commit that produced it).
python3 - "$archive_in" "$out/template-package-input.json" "$archive_sha" <<'PY'
import json,sys
from zipfile import ZipFile
from xml.etree import ElementTree as ET
with ZipFile(sys.argv[1]) as z:
    names=[n for n in z.namelist() if n.endswith('.nuspec')]
    assert len(names)==1
    doc=ET.fromstring(z.read(names[0]))
ns=doc.tag.split('}')[0]+'}'
meta=doc.find(ns+'metadata')
ident=meta.find(ns+'id').text; version=meta.find(ns+'version').text
assert ident=='FS.GG.Workspace.Template'
json.dump({'origin':'source-built','id':ident,'version':version,'archiveSha256':sys.argv[3],'publishedAcceptance':False,'installedAcceptance':False},open(sys.argv[2],'w'))
PY
mkdir "$out/template" "$out/template-hive"
archive="$out/template/$(basename "$archive_in")"
cp "$archive_in" "$archive"
printf '%s  %s\n' "$archive_sha" "$archive" | sha256sum --check --strict
dotnet new install "$archive" --force --debug:custom-hive "$out/template-hive" >"$out/template-install.log" 2>&1
scope=(--debug:custom-hive "$out/template-hive" --debug:disable-sdk-templates --no-update-check)
mapfile -t selection < <(python3 - "$out/current-composition-plan.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))['selection']
for key in ('productName','bundle','lifecycle'):print(p[key])
for key in ('externalReference','wasmPolicyExample'):print(str(p[key]).lower())
PY
)
product_name="${selection[0]}"; bundle="${selection[1]}"; lifecycle="${selection[2]}"
dotnet new fs-gg-fable-game -n "$product_name" -o "$out/complete" --bundle "$bundle" --lifecycle "$lifecycle" "${scope[@]}" >"$out/complete-generate.log" 2>&1
dotnet new fs-gg-fable-game -n DefaultPlayer -o "$out/player" "${scope[@]}" >"$out/player-generate.log" 2>&1
python3 "$root/tests/composition/fable-game/current-composition-observations.py" lock "$out/current-composition-plan.json" "$out/complete"
[[ -f "$out/complete/SvgFoundation/Examples/ExternalAuthority/reference.json" ]]
[[ -f "$out/complete/SvgFoundation/Examples/FourD/reference.json" ]]
[[ ! -e "$out/player/SvgFoundation/Examples/ExternalAuthority" && ! -e "$out/player/SvgFoundation/Examples/FourD" ]]
grep -F 'ExternalAuthorityReference.install ()' "$out/complete/SvgFoundation/Program.fs" >/dev/null
cp "$out/NuGet.Config" "$out/complete/NuGet.config"
export FsGgExternalReferenceCandidate="${selection[3]}" FsGgWasmPolicyExample="${selection[4]}"
export NUGET_PACKAGES="$out/complete/.nuget/packages"
python3 - "$out/complete" "$root/tests/composition/fable-game" <<'PYPUBLIC'
import importlib.util,json,sys
from pathlib import Path
from xml.etree import ElementTree as ET
root,helpers=map(Path,sys.argv[1:]); spec=importlib.util.spec_from_file_location('public_input',helpers/'external-reference-public.py'); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
projects=['SvgFoundation/SvgFoundation.fsproj','SvgFoundation/Studio/Studio.fsproj','SvgFoundation/Examples/Tactical/TacticalCompatibility.Tests.fsproj','Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj','Protocol.Tests/cross-runtime/CodecProbe.Fable/CodecProbe.Fable.fsproj']
for project in projects:
    path=root/project; tree=ET.parse(path)
    for key in ['FsGgSvgInputVersion','FsGgSvgAuthoringVersion']:
        node=tree.find('.//'+key)
        if node is not None: assert node.text==module.VERSION
    for node in tree.findall('.//PackageReference'):
        if node.attrib.get('Include','').startswith('FS.GG.UI.'):
            assert node.attrib['Version'] in ['['+module.VERSION+']','[$(FsGgSvgInputVersion)]','[$(FsGgSvgAuthoringVersion)]']
    module.validate_project_references(tree, project, root)
    lock=json.loads(path.with_name('packages.lock.json').read_text())
    for deps in lock['dependencies'].values():
        for name,row in deps.items():
            if name.startswith('FS.GG.UI.'):
                assert name in module.LOCK_HASH and row['resolved']==module.VERSION and row['contentHash']==module.LOCK_HASH[name]
PYPUBLIC
for project in SvgFoundation/SvgFoundation.fsproj SvgFoundation/Studio/Studio.fsproj SvgFoundation/Examples/Tactical/TacticalCompatibility.Tests.fsproj Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj Protocol.Tests/cross-runtime/CodecProbe.Fable/CodecProbe.Fable.fsproj; do
  dotnet restore "$out/complete/$project" --locked-mode --configfile "$out/NuGet.Config" >>"$out/public-locked-restore.log" 2>&1
done
python3 - "$out/current-composition-plan.json" "$out/complete/.nuget/packages" <<'CURRENT_CACHE'
import json,hashlib,sys
from pathlib import Path
p=json.load(open(sys.argv[1]));cache=Path(sys.argv[2])
for row in p['rendering']['packages']:
    folder=cache/row['id'].lower()/p['rendering']['version']
    archive=folder/(row['id'].lower()+'.'+p['rendering']['version']+'.nupkg')
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==row['sha256']
    assert json.loads((folder/'.nupkg.metadata').read_text())['contentHash']==row['lockContentHash']
CURRENT_CACHE
(cd "$out/complete" && dotnet tool restore --configfile "$out/NuGet.Config") >"$out/fable-restore.log" 2>&1
python3 - "$out/complete/.nuget/packages" <<'CURRENT_FABLE_MEMBERS'
import hashlib,json,os,sys
from pathlib import Path
cache=Path(sys.argv[1]);expected=os.environ['FSGG_COMPOSITION_FABLE_SHA']
entries=[p for p in (cache/'fable').rglob('*.dll') if hashlib.sha256(p.read_bytes()).hexdigest()==expected]
assert len(entries)==1,'actual product Fable core differs'
actual={str(p.relative_to(entries[0].parent)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in entries[0].parent.rglob('*') if p.is_file() and not p.is_symlink()}
assert actual==json.loads(Path(os.environ['FSGG_COMPOSITION_FABLE_MEMBERS']).read_text()),'actual product Fable member closure differs'
CURRENT_FABLE_MEMBERS
(cd "$out/complete" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache) >"$out/fable-build.log" 2>&1
(cd "$out/complete" && dotnet fable --version) >"$out/fable-version.log" 2>&1
(cd "$out/complete/Client" && npm ci) >"$out/npm-client.log" 2>&1
(cd "$out/complete" && ./Client/node_modules/.bin/vite build --config SvgFoundation/vite.config.js) >"$out/vite-build.log" 2>&1
python3 - "$out" "$version" <<'PY'
from pathlib import Path
import json,sys
root=Path(sys.argv[1]); version=sys.argv[2]
assets=json.loads((root/'complete/SvgFoundation/obj/project.assets.json').read_text())
for id in ('FS.GG.UI.Scene','FS.GG.UI.Scene.SvgBrowser','FS.GG.UI.KeyboardInput'):
    assert assets['libraries'][id+'/'+version]['type']=='package', id
assert all(value['type']!='project' for key,value in assets['libraries'].items() if key.startswith('FS.GG.UI.'))
assert {Path(value).resolve() for value in assets['packageFolders']}=={(root/'complete/.nuget/packages').resolve()}
assert 'SvgExternalSessionHost' in (root/'complete/.nuget/packages/fs.gg.ui.scene.svgbrowser'/version/'fable/SvgExternalSessionHost.fs').read_text()
assert any((root/'complete/SvgFoundation/output').rglob('SvgExternalSessionHost.fs.js')), 'external host missing from delivered Fable output'
PY
python3 "$root/tests/composition/fable-game/current-composition-observations.py" assets "$out/current-composition-plan.json" "$out/complete"
(cd "$out/complete" && bash Protocol.Tests/cross-runtime/run-cross-runtime.sh) >"$out/public-codec-build.log" 2>&1
(cd "$out/complete" && bash SvgFoundation/Studio/build.sh) >"$out/public-studio-build.log" 2>&1
dotnet run --project "$out/complete/SvgFoundation/Examples/Tactical/TacticalCompatibility.Tests.fsproj" --no-restore >"$out/public-tactical-build.log" 2>&1
cp "$out/NuGet.Config" "$out/player/NuGet.config"
dotnet restore "$out/player/SvgFoundation/SvgFoundation.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/public-player-restore.log" 2>&1
dotnet restore "$out/complete/Server/Server.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/server-restore.log" 2>&1
dotnet publish "$out/complete/Server/Server.fsproj" -c Release --no-restore -m:1 -p:UseSharedCompilation=false -o "$out/complete/artifacts/authority-server" >"$out/server-publish.log" 2>&1
(cd "$out/complete/Browser.Tests" && npm ci) >"$out/npm-browser.log" 2>&1
python3 - "$root" "$out" <<'CURRENT_CONFIG'
import json,runpy,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:]);plan=json.loads((out/'current-composition-plan.json').read_text())
selector=runpy.run_path(str(root/'tests/composition/fable-game/current-composition-observations.py'))['selector'](plan)
files=sorted({row["file"] for row in plan["browsers"]["cases"]})
config='import { defineConfig } from "@playwright/test";\nimport maintained from "./playwright.config";\nexport default defineConfig({...maintained,testMatch:'+json.dumps(files)+',workers:'+str(plan["browsers"]["workers"])+',retries:'+str(plan["browsers"]["retries"])+',grep:new RegExp('+json.dumps(selector)+')});\n'
(out/'complete/Browser.Tests/current-composition.generated.config.ts').write_text(config)
(out/'current-source-stage.json').write_text(json.dumps({'disposition':'source-passed','origin':'source-built','browserExecuted':False,'publishedAcceptance':False,'whole4818Acceptance':False})+'\n')
CURRENT_CONFIG
