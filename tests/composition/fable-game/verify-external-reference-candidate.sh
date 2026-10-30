#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
producer="${1:?Rendering source checkout or absent external-package input root required}"
producer_feed="${2:?packed Rendering source feed required}"
version="${3:?isolated Rendering candidate version required}"
out="${4:?empty qualification directory required}"
expected_source="${5:-097e228388375bf27a03ac008627e4a038686c53}"
input_mode="${6:-candidate}"
templates_package="${7:-}"
templates_package_sha="${8:-}"
current_stage="${9:-}"
[[ "$#" -le 9 ]]
[[ -z "$current_stage" || "$input_mode" == current-public-composition && ( "$current_stage" == current-source-stage || "$current_stage" == current-at-full ) ]]
[[ -z "$templates_package" && -z "$templates_package_sha" || -n "$templates_package" && "$templates_package_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "external template package requires exact path and SHA256" >&2; exit 1; }
[[ "$input_mode" == candidate || "$input_mode" == public || "$input_mode" == font-disposal || "$input_mode" == current-public-composition ]] || { echo "unknown input mode" >&2; exit 1; }
if [[ "$input_mode" == public ]]; then
  [[ "$version" == 0.32.4 && "$expected_source" == 4ede04be66cedffc8551cd14045bab714aa358a7 ]]
  [[ -z "${FsGgSvgInputVersion:-}" && -z "${FsGgSvgAuthoringVersion:-}" ]] || { echo "public defaults cannot be overridden" >&2; exit 1; }
fi
if [[ "$input_mode" == font-disposal ]]; then
  [[ "$version" == 0.32.3 && "$expected_source" == 4ec6eafbbbf02264db9b0db4780c590abe0bf9cd && -z "$templates_package" ]]
  [[ -z "${FsGgSvgInputVersion:-}" && -z "${FsGgSvgAuthoringVersion:-}" && -z "${FSGG_SVG_AUTHORING_VERSION:-}" ]]
fi
if [[ "$input_mode" == current-public-composition ]]; then
  if [[ "$current_stage" == current-at-full ]]; then
    python3 -B "$root/tests/composition/fable-game/current-reference-at-caller.py" guard
  else
    python3 "$root/tests/composition/fable-game/current-composition-observations.py" --check-admission
  fi
  [[ "$current_stage" == current-source-stage || "$current_stage" == current-at-full ]]
  [[ -n "$templates_package" && "${FSGG_REFERENCE_PROVIDER_TOOL_DLL:-}" = /* && -f "$FSGG_REFERENCE_PROVIDER_TOOL_DLL" ]] || { echo "current composition requires its qualified typed owner and exact template archive" >&2; exit 1; }
  [[ -z "${FsGgSvgInputVersion:-}" && -z "${FsGgSvgAuthoringVersion:-}" && -z "${FSGG_SVG_AUTHORING_VERSION:-}" ]]
fi
[[ "$expected_source" =~ ^[0-9a-f]{40}$ && "$version" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ && "$version" != 0.31.0 ]]
[[ ! -e "$out" ]]
if [[ -z "$templates_package" ]]; then
  [[ "$(git -C "$producer" rev-parse HEAD)" == "$expected_source" ]]
  [[ -z "$(git -C "$producer" status --porcelain --untracked-files=no)" ]]
fi
mkdir -p "$out"/{feed,home,packages,http}
out="$(realpath "$out")"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
if [[ "$input_mode" == current-public-composition ]]; then
  # The separate admitted runtime profile must qualify/bind this actual typed owner.
  sha256sum "$FSGG_REFERENCE_PROVIDER_TOOL_DLL" >"$out/current-composition-owner.sha256"
  dotnet "$FSGG_REFERENCE_PROVIDER_TOOL_DLL" current-composition-plan >"$out/current-composition-plan.json"
  python3 "$root/tests/composition/fable-game/current-composition-observations.py" inputs "$out/current-composition-plan.json" "$version" "$expected_source" "$templates_package_sha"
fi
# Each CLR stage is sequential; compilation must fit the integrator's live allocation.
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1
if [[ "$input_mode" == public || "$input_mode" == current-public-composition ]]; then
  rmdir "$out/feed"
  if [[ "$input_mode" == current-public-composition ]]; then
    python3 "$root/tests/composition/fable-game/current-composition-observations.py" staged-feed "$out/current-composition-plan.json" "$producer_feed" "$out/feed"
  else
    python3 "$root/tests/composition/fable-game/external-reference-public.py" "$producer_feed/release-custody.json" "$out/feed"
  fi
  if [[ "$input_mode" == current-public-composition ]]; then
    python3 "$root/tests/composition/fable-game/current-composition-observations.py" public-readback "$out/current-composition-plan.json" "$out/feed/public-readback.json"
  fi
else
  for id in FS.GG.UI.Scene FS.GG.UI.KeyboardInput FS.GG.UI.Scene.SvgBrowser; do
    cp "$producer_feed/$id.$version.nupkg" "$out/feed/"
  done
fi
if [[ -n "$templates_package" && "$input_mode" != current-public-composition ]]; then
  python3 "$root/tests/composition/fable-game/external-reference-template-package.py" rendering "$out/feed" "$version" "$expected_source" "$out/producer-package-input.json"
fi
python3 - "$producer" "$out/feed" "$version" "$templates_package" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,sys
source,feed=map(Path,sys.argv[1:3]); version=sys.argv[3]; external=bool(sys.argv[4])
rows=[]
source_entries=[]
for package in sorted(feed.glob('*.nupkg')):
    rows.append({'name':package.name,'sha256':hashlib.sha256(package.read_bytes()).hexdigest()})
with ZipFile(feed/f'FS.GG.UI.Scene.SvgBrowser.{version}.nupkg') as archive:
    for name in ('SvgExternalSessionHost.fs','SvgExternalSessionHost.fsi','SvgInputHost.fs','SvgInputHost.fsi'):
        raw=archive.read('fable/'+name)
        if not external: assert raw==(source/'src/Scene.SvgBrowser'/name).read_bytes(), name
        source_entries.append({'path':'fable/'+name,'sha256':hashlib.sha256(raw).hexdigest()})
    profile='fable-compatibility/compatibility-profile.v1.json'
    if not external: assert archive.read(profile)==(source/'src/Scene.SvgBrowser/Fable/compatibility-profile.v1.json').read_bytes()
    source_entries.append({'path':profile,'sha256':hashlib.sha256(archive.read(profile)).hexdigest()})
(feed.parent/'producer-archives.json').write_text(json.dumps(rows,indent=2)+'\n')
(feed.parent/'producer-source-entries.json').write_text(json.dumps(source_entries,indent=2)+'\n')
PY
if [[ "$input_mode" == public || "$input_mode" == current-public-composition ]]; then
  printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' > "$out/NuGet.Config"
else
cat > "$out/NuGet.Config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.Scene"/><package pattern="FS.GG.UI.Scene.SvgBrowser"/><package pattern="FS.GG.UI.KeyboardInput"/></packageSource><packageSource key="public"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
CONFIG
fi
template_scope_args=()
if [[ -n "$templates_package" ]]; then
  # An external archive is a distinct candidate input; no producer pack/projection/source lookup.
  # Keep generated builds outside either producer's automatic MSBuild source hierarchy.
  python3 - "$out" "$root" "$producer" <<'PYBOUNDARY'
from pathlib import Path
import sys
output,controller,rendering=map(lambda value:Path(value).resolve(),sys.argv[1:])
assert not output.is_relative_to(controller) and not output.is_relative_to(rendering), 'external package output must be outside producer roots'
PYBOUNDARY
  if [[ "$input_mode" == current-public-composition ]]; then
    python3 - "$out/current-composition-plan.json" "$out/template-package-input.json" "$out/producer-package-input.json" <<'CURRENT_INPUTS'
import json,sys
from pathlib import Path
plan=json.loads(Path(sys.argv[1]).read_text());template=plan['template'];rendering=plan['rendering']
Path(sys.argv[2]).write_text(json.dumps({'producerRevision':template['sourceCommit'],'version':template['version'],'archiveSha256':template['sha256'],'installedAcceptance':False,'feedQualification':'actual download not established by supplied archive identity'})+'\n')
Path(sys.argv[3]).write_text(json.dumps({'producerRevision':rendering['sourceCommit'],'version':rendering['version']})+'\n')
CURRENT_INPUTS
    mapfile -t selected < <(python3 - "$out/current-composition-plan.json" <<'CURRENT_IDENTITY'
import json,sys
p=json.load(open(sys.argv[1]))['template']
for key in ('id','version','sourceCommit'):print(p[key])
CURRENT_IDENTITY
)
    dotnet "$FSGG_REFERENCE_PROVIDER_TOOL_DLL" published-tool-check --archive "$templates_package" --sha256 "$templates_package_sha" --package-id "${selected[0]}" --version "${selected[1]}" --source-revision "${selected[2]}" >"$out/template-typed-identity.log"
  else
  python3 "$root/tests/composition/fable-game/external-reference-template-package.py" inspect \
    "$templates_package" "$templates_package_sha" "$out/template-package-input.json"
  fi
  mkdir "$out/template" "$out/template-hive"
  if [[ "$input_mode" == current-public-composition ]]; then
    archive="$out/template/$(basename "$templates_package")"
  else
    archive="$out/template/FS.GG.Workspace.Template.0.18.3.nupkg"
  fi
  cp "$templates_package" "$archive"
  printf '%s  %s\n' "$templates_package_sha" "$archive" | sha256sum --check --strict
  dotnet new install "$archive" --force --debug:custom-hive "$out/template-hive" >"$out/template-install.log" 2>&1
  template_scope_args=(--debug:custom-hive "$out/template-hive" --debug:disable-sdk-templates --no-update-check)
else
  # Preserve the existing source-built candidate and its canonical checked Python projection.
  . "$root/tests/composition/fable-game/svg-source-python-fixture.sh"
  prepare_svg_source_python_fixture "$root" "$out"
  dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/template" -m:1 -p:UseSharedCompilation=false >"$out/templates-pack.log" 2>&1
  mapfile -t archives < <(find "$out/template" -maxdepth 1 -name '*.nupkg' -type f)
  [[ "${#archives[@]}" == 1 ]]
  dotnet new install "${archives[0]}" --force >"$out/template-install.log" 2>&1
fi
product_name=ExternalReference
bundle=complete
lifecycle=none
if [[ "$input_mode" == current-public-composition ]]; then
  mapfile -t selection < <(python3 - "$out/current-composition-plan.json" <<'CURRENT_SELECTION'
import json,sys
p=json.load(open(sys.argv[1]))['selection']
for key in ('productName','bundle','lifecycle'):print(p[key])
for key in ('externalReference','wasmPolicyExample'):print(str(p[key]).lower())
CURRENT_SELECTION
)
  product_name="${selection[0]}";bundle="${selection[1]}";lifecycle="${selection[2]}"
fi
dotnet new fs-gg-fable-game -n "$product_name" -o "$out/complete" --bundle "$bundle" --lifecycle "$lifecycle" "${template_scope_args[@]}" >"$out/complete-generate.log" 2>&1
dotnet new fs-gg-fable-game -n DefaultPlayer -o "$out/player" "${template_scope_args[@]}" >"$out/player-generate.log" 2>&1
if [[ -n "$templates_package" ]]; then
  python3 "$root/tests/composition/fable-game/external-reference-template-package.py" generated \
    "$out/complete" "$out/template-generated-independent.json"
  printf '%s  %s\n' "$templates_package_sha" "$archive" | sha256sum --check --strict
fi
if [[ "$input_mode" == current-public-composition ]]; then
  python3 "$root/tests/composition/fable-game/current-composition-observations.py" lock "$out/current-composition-plan.json" "$out/complete"
  dotnet "$FSGG_REFERENCE_PROVIDER_TOOL_DLL" current-composition-receiver-check --archive "$archive" --receiver "$out/complete" --route direct --lifecycle "$lifecycle" --bundle "$bundle" --product-name "$product_name" >"$out/current-composition-receiver.log"
fi
[[ -f "$out/complete/SvgFoundation/Examples/ExternalAuthority/reference.json" ]]
[[ -f "$out/complete/SvgFoundation/Examples/FourD/reference.json" ]]
[[ ! -e "$out/player/SvgFoundation/Examples/ExternalAuthority" && ! -e "$out/player/SvgFoundation/Examples/FourD" ]]
grep -F 'ExternalAuthorityReference.install ()' "$out/complete/SvgFoundation/Program.fs" >/dev/null
# Candidate resolution changes only generated private locks. Public mode tests the
# shipped defaults and checked lockfiles with public-only resolution.
cp "$out/NuGet.Config" "$out/complete/NuGet.config"
export FsGgExternalReferenceCandidate=true
if [[ "$input_mode" == current-public-composition ]]; then
  export FsGgExternalReferenceCandidate="${selection[3]}" FsGgWasmPolicyExample="${selection[4]}"
fi
export NUGET_PACKAGES="$out/complete/.nuget/packages"
if [[ "$input_mode" == public || "$input_mode" == current-public-composition ]]; then
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
  if [[ "$input_mode" != current-public-composition ]]; then
  python3 - "$out/complete/.nuget/packages" "$root/tests/composition/fable-game" "$producer_feed/release-custody.json" <<'PYCACHE'
import importlib.util,json,sys
from pathlib import Path
cache,helpers,custody=map(Path,sys.argv[1:]);spec=importlib.util.spec_from_file_location('public_input',helpers/'external-reference-public.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows={r['id']:r for r in json.loads(custody.read_text())['archives']}
for identity,sha in module.PUBLIC_SHA256.items():
    folder=cache/identity.lower()/module.VERSION;module.validate_archive(folder/(identity.lower()+'.'+module.VERSION+'.nupkg'),identity,sha,rows[identity])
    assert json.loads((folder/'.nupkg.metadata').read_text())['contentHash']==module.LOCK_HASH[identity]
PYCACHE
  else
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
  fi
else
  export FsGgSvgInputVersion="$version"
  dotnet restore "$out/complete/SvgFoundation/SvgFoundation.fsproj" --force-evaluate -p:RestoreLockedMode=false --configfile "$out/NuGet.Config" -p:FsGgSvgInputVersion="$version" >"$out/receiver-restore.log" 2>&1
fi
if [[ "$input_mode" == current-public-composition ]]; then
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
else
(cd "$out/complete" && dotnet tool restore --configfile "$out/NuGet.Config" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache) >"$out/fable-build.log" 2>&1
fi
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
if [[ "$input_mode" == current-public-composition ]]; then
  python3 "$root/tests/composition/fable-game/current-composition-observations.py" assets "$out/current-composition-plan.json" "$out/complete"
fi
if [[ "$input_mode" == public || "$input_mode" == current-public-composition ]]; then
  (cd "$out/complete" && bash Protocol.Tests/cross-runtime/run-cross-runtime.sh) >"$out/public-codec-build.log" 2>&1
  (cd "$out/complete" && bash SvgFoundation/Studio/build.sh) >"$out/public-studio-build.log" 2>&1
  dotnet run --project "$out/complete/SvgFoundation/Examples/Tactical/TacticalCompatibility.Tests.fsproj" --no-restore >"$out/public-tactical-build.log" 2>&1
  cp "$out/NuGet.Config" "$out/player/NuGet.config"
  dotnet restore "$out/player/SvgFoundation/SvgFoundation.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/public-player-restore.log" 2>&1
fi
if [[ "$input_mode" == font-disposal ]]; then
  # Only generated private locks change; canonical Studio build keeps its real
  # Fable targetDir, vendor/font/worker assets and npm/Vite launch graph.
  export FsGgSvgAuthoringVersion="$version" FSGG_SVG_AUTHORING_VERSION="$version" FSGG_SVG_CANDIDATE_FEED="$out/feed"
  dotnet restore "$out/complete/SvgFoundation/Studio/Studio.fsproj" --force-evaluate -p:RestoreLockedMode=false --configfile "$out/NuGet.Config" -p:FsGgSvgAuthoringVersion="$version" >"$out/studio-restore.log" 2>&1
  (cd "$out/complete" && bash SvgFoundation/Studio/build.sh) >"$out/studio-build.log" 2>&1
  python3 - "$out" "$version" <<'PYSTUDIO'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]); version=sys.argv[2]
assets=json.loads((root/'complete/SvgFoundation/Studio/obj/project.assets.json').read_text())
assert {Path(v).resolve() for v in assets['packageFolders']}=={(root/'complete/.nuget/packages').resolve()}
for name in ('FS.GG.UI.Scene','FS.GG.UI.KeyboardInput','FS.GG.UI.Scene.SvgBrowser'):
    assert assets['libraries'][name+'/'+version]['type']=='package'
    cached=root/'complete/.nuget/packages'/name.lower()/version/(name.lower()+'.'+version+'.nupkg')
    assert hashlib.sha256(cached.read_bytes()).digest()==hashlib.sha256((root/'feed'/(name+'.'+version+'.nupkg')).read_bytes()).digest()
assert all(v['type']!='project' for k,v in assets['libraries'].items() if k.startswith('FS.GG.UI.'))
PYSTUDIO
fi
dotnet restore "$out/complete/Server/Server.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/server-restore.log" 2>&1
dotnet publish "$out/complete/Server/Server.fsproj" -c Release --no-restore -m:1 -p:UseSharedCompilation=false -o "$out/complete/artifacts/authority-server" >"$out/server-publish.log" 2>&1
(cd "$out/complete/Browser.Tests" && npm ci) >"$out/npm-browser.log" 2>&1
if [[ "$input_mode" == current-public-composition ]]; then
  python3 - "$root" "$out" <<'CURRENT_CONFIG'
import hashlib,json,runpy,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:]);plan=json.loads((out/'current-composition-plan.json').read_text())
selector=runpy.run_path(str(root/'tests/composition/fable-game/current-composition-observations.py'))['selector'](plan)
files=sorted({row["file"] for row in plan["browsers"]["cases"]})
config='import { defineConfig } from "@playwright/test";\nimport maintained from "./playwright.config";\nexport default defineConfig({...maintained,testMatch:'+json.dumps(files)+',workers:'+str(plan["browsers"]["workers"])+',retries:'+str(plan["browsers"]["retries"])+',grep:new RegExp('+json.dumps(selector)+')});\n'
(out/'complete/Browser.Tests/current-composition.generated.config.ts').write_text(config)
# Preserve the actual source-stage inputs before any browser executes. The local
# runner binds these original bytes after its own reports and custody join pass.
receiver=out/'complete/SvgFoundation'
entries=[{'path':p.relative_to(receiver).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(receiver.rglob('*')) if p.is_file() and not {'node_modules','obj','bin'}.intersection(p.parts)]
assert entries
(out/'current-source-inputs.json').write_text(json.dumps({'receiver':entries,'templatePackageInput':json.loads((out/'template-package-input.json').read_text()),'producerArchives':json.loads((out/'producer-archives.json').read_text()),'producerSourceEntries':json.loads((out/'producer-source-entries.json').read_text()),'publicReadback':json.loads((out/'feed/public-readback.json').read_text())},indent=2)+'\n')
(out/'current-source-stage.json').write_text(json.dumps({'disposition':'source-passed','browserExecuted':False,'whole4818Acceptance':False})+'\n')
CURRENT_CONFIG
  if [[ "$current_stage" == current-source-stage ]]; then exit 0; fi
fi
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$out/browsers}"
(cd "$out/complete/Browser.Tests" && npx playwright install chromium firefox webkit) >"$out/browser-install.log" 2>&1
selector="$(python3 - "$root" "$input_mode" "$out/current-composition-plan.json" <<'PYSELECT'
import runpy,sys
if sys.argv[2]=='current-public-composition':
    import json
    print(runpy.run_path(sys.argv[1]+'/tests/composition/fable-game/current-composition-observations.py')['selector'](json.load(open(sys.argv[3]))))
else:print(runpy.run_path(sys.argv[1]+'/tests/composition/fable-game/external-reference-orca.py')['browser_selector'](sys.argv[2]))
PYSELECT
)"
families=(chromium firefox webkit)
browser_args=(--workers=1)
if [[ "$input_mode" == current-public-composition ]]; then
  mapfile -t families < <(python3 - "$out/current-composition-plan.json" <<'CURRENT_BROWSERS'
import json,sys
for family in json.load(open(sys.argv[1]))['browsers']['families']:print(family)
CURRENT_BROWSERS
)
  mapfile -t browser_settings < <(python3 - "$out/current-composition-plan.json" <<'CURRENT_BROWSER_SETTINGS'
import json,sys
p=json.load(open(sys.argv[1]))['browsers']
for key in ('workers','retries'):print(p[key])
CURRENT_BROWSER_SETTINGS
)
  browser_args=(--workers="${browser_settings[0]}" --retries="${browser_settings[1]}")
fi
for family in "${families[@]}"; do
  (cd "$out/complete/Browser.Tests" && PLAYWRIGHT_BROWSER_FAMILY="$family" npm test -- --grep "$selector" "${browser_args[@]}") >"$out/$family-browser.log" 2>&1
  cp "$out/complete/Browser.Tests/test-results/browser.json" "$out/$family-browser.json"
  python3 - "$out/$family-browser.json" "$root" "$input_mode" "$out/current-composition-plan.json" "$family" <<'PY'
import json,runpy,sys
if sys.argv[3]=='current-public-composition':
    runpy.run_path(sys.argv[2]+'/tests/composition/fable-game/current-composition-observations.py')['validate_report'](json.load(open(sys.argv[1])),json.load(open(sys.argv[4])),sys.argv[5])
else:runpy.run_path(sys.argv[2]+'/tests/composition/fable-game/external-reference-orca.py')['validate_browser_report'](json.load(open(sys.argv[1])),sys.argv[3])
PY
done
python3 - "$root" "$producer" "$out" "$version" "$producer_feed" "$input_mode" "$templates_package" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
root,producer,out=map(Path,sys.argv[1:4]); version=sys.argv[4]
def git(path,field): return subprocess.check_output(['git','-C',str(path),'rev-parse',field],text=True).strip()
def hashes(path): return [{'path':p.relative_to(path).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(path.rglob('*')) if p.is_file() and 'node_modules' not in p.parts and 'obj' not in p.parts and 'bin' not in p.parts]
template_input=json.loads((out/'template-package-input.json').read_text()) if sys.argv[7] else None
rendering_input=json.loads((out/'producer-package-input.json').read_text()) if template_input else None
producer_identity={'revision':rendering_input['producerRevision'],'tree':None} if rendering_input else {'revision':git(producer,'HEAD'),'tree':git(producer,'HEAD^{tree}')}
template_identity={'revision':template_input['producerRevision'],'tree':None} if template_input else {'revision':git(root,'HEAD'),'tree':git(root,'HEAD^{tree}')}
packet={'schema':'fsgg.external-reference-source-qualification/1','disposition':'passed','templates':template_identity,'producer':{'inputCustody':json.loads((Path(sys.argv[5])/'ROOT-CUSTODY.json').read_text()) if (Path(sys.argv[5])/'ROOT-CUSTODY.json').exists() else None,'custodyManifestSha256':hashlib.sha256((Path(sys.argv[5])/'release-custody.json').read_bytes()).hexdigest() if (Path(sys.argv[5])/'release-custody.json').exists() else None,**producer_identity,'candidateVersion':version,'archives':json.loads((out/'producer-archives.json').read_text()),'sourceEntries':json.loads((out/'producer-source-entries.json').read_text())},'environment':{'dotnet':subprocess.check_output(['dotnet','--info'],text=True),'node':subprocess.check_output(['node','--version'],text=True).strip(),'npm':subprocess.check_output(['npm','--version'],text=True).strip(),'fableLoadedVersion':(out/'fable-version.log').read_text().strip(),'fableLogSha256':hashlib.sha256((out/'fable-build.log').read_bytes()).hexdigest()},'receiver':hashes(out/'complete/SvgFoundation'),'browserFamilies':['chromium','firefox','webkit'],'browserReports':hashes(out/'complete/Browser.Tests/test-results'),'browserReportSha256':{family:hashlib.sha256((out/(family+'-browser.json')).read_bytes()).hexdigest() for family in ['chromium','firefox','webkit']},'qualificationMode':sys.argv[6],'passedPerFamily':len(json.loads((out/'current-composition-plan.json').read_text())['browsers']['cases']) if sys.argv[6]=='current-public-composition' else 15 if sys.argv[6]=='font-disposal' else 8,'skipped':0,'domAutomation':True,'actualScreenReader':'not-observed','publication':False,'installedAcceptance':False,'renderingInputSource':'nuget.org' if sys.argv[6] in ('public','current-public-composition') else 'candidate','renderingPublicInputsQualified':sys.argv[6] in ('public','current-public-composition'),'templatesInputSource':'source-built-candidate','publicReadback':json.loads((out/'feed/public-readback.json').read_text()) if sys.argv[6] in ('public','current-public-composition') else None}
if sys.argv[6]=='font-disposal':
    import runpy
    packet['studioFontCases']=runpy.run_path(str(root/'tests/composition/fable-game/external-reference-orca.py'))['FONT_CASE_TITLES']
if sys.argv[6]=='public':
    packet['schema']='fsgg.external-reference-public-input-qualification/1'
    packet['producer']['publishedVersion']=packet['producer'].pop('candidateVersion')
if template_input:
    packet['schema']='fsgg.external-reference-template-package-qualification/1'
    packet['templatesInputSource']='external-package-candidate'
    packet['templatePackageInput']=template_input
    packet['renderingPackageInput']=rendering_input
    packet['renderingProducerSourceUnavailable']=not (producer/'.git').exists() and not (producer/'src').exists()
    packet['renderingSourceCorrespondence']='reused exact original packaged-entry hashes; no producer tree read in this mode'
    packet['templateGeneratedIndependent']=json.loads((out/'template-generated-independent.json').read_text())
    packet['templateProducerSourceUnavailable']=not (root/'FS.GG.Templates.csproj').exists() and not (root/'templates').exists()
    # Local immutable package installation does not establish released-feed installed adoption.
    assert packet['installedAcceptance'] is False and template_input['installedAcceptance'] is False
if sys.argv[6]=='current-public-composition':
    import runpy
    actual=json.loads((Path(sys.argv[5])/'public-readback.json').read_text())
    runpy.run_path(str(root/'tests/composition/fable-game/current-composition-observations.py'))['validate_public_readback'](json.loads((out/'current-composition-plan.json').read_text()),actual)
    assert all(row['payloadMatched'] is True for row in actual['records'])
    assert actual['custodySha256']==packet['producer']['custodyManifestSha256']
    packet['actualProducerCustodyReadback']=True
    packet['actualScreenReader']='not-observed'
    packet['schema']='fsgg.current-composition-source-qualification/1'
    packet['currentCompositionPlan']=json.loads((out/'current-composition-plan.json').read_text())
    packet['templatesInputSource']='exact-current-public-archive'
    packet['localSaveStorage']='synthetic-in-memory'
    packet['durableSaveAcceptance']=False
    packet['actualAT']=False
    packet['providerMatrixAcceptance']=False
    packet['nativeImeAcceptance']=False
    packet['whole4817Acceptance']=False
    packet['whole4818Acceptance']=False
(out/'qualification.json').write_text(json.dumps(packet,indent=2)+'\n')
PY
printf 'external-reference-candidate: passed; evidence=%s/qualification.json\n' "$out"
