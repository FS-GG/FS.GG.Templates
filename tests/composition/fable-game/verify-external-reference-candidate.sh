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
[[ "$#" -le 8 ]]
[[ -z "$templates_package" && -z "$templates_package_sha" || -n "$templates_package" && "$templates_package_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "external template package requires exact path and SHA256" >&2; exit 1; }
[[ "$input_mode" == candidate || "$input_mode" == public ]] || { echo "unknown input mode" >&2; exit 1; }
if [[ "$input_mode" == public ]]; then
  [[ "$version" == 0.32.1 && "$expected_source" == 6c9f766fdd91483c2de6f061e75589e94852a265 ]]
  [[ -z "${FsGgSvgInputVersion:-}" && -z "${FsGgSvgAuthoringVersion:-}" ]] || { echo "public defaults cannot be overridden" >&2; exit 1; }
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
# Each CLR stage is sequential; compilation must fit the integrator's live allocation.
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1
if [[ "$input_mode" == public ]]; then
  rmdir "$out/feed"
  python3 "$root/tests/composition/fable-game/external-reference-public.py" "$producer_feed/release-custody.json" "$out/feed"
else
  for id in FS.GG.UI.Scene FS.GG.UI.KeyboardInput FS.GG.UI.Scene.SvgBrowser; do
    cp "$producer_feed/$id.$version.nupkg" "$out/feed/"
  done
fi
if [[ -n "$templates_package" ]]; then
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
if [[ "$input_mode" == public ]]; then
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
  python3 "$root/tests/composition/fable-game/external-reference-template-package.py" inspect \
    "$templates_package" "$templates_package_sha" "$out/template-package-input.json"
  mkdir "$out/template" "$out/template-hive"
  cp "$templates_package" "$out/template/FS.GG.Workspace.Template.0.18.3.nupkg"
  archive="$out/template/FS.GG.Workspace.Template.0.18.3.nupkg"
  printf '%s  %s\n' "$templates_package_sha" "$archive" | sha256sum --check --strict
  dotnet new install "$archive" --force --debug:custom-hive "$out/template-hive" >"$out/template-install.log" 2>&1
  template_scope_args=(--debug:custom-hive "$out/template-hive" --debug:disable-sdk-templates --no-update-check --package FS.GG.Workspace.Template)
else
  # Preserve the existing source-built candidate and its canonical checked Python projection.
  . "$root/tests/composition/fable-game/svg-source-python-fixture.sh"
  prepare_svg_source_python_fixture "$root" "$out"
  dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/template" -m:1 -p:UseSharedCompilation=false >"$out/templates-pack.log" 2>&1
  mapfile -t archives < <(find "$out/template" -maxdepth 1 -name '*.nupkg' -type f)
  [[ "${#archives[@]}" == 1 ]]
  dotnet new install "${archives[0]}" --force >"$out/template-install.log" 2>&1
fi
dotnet new fs-gg-fable-game -n ExternalReference -o "$out/complete" --bundle complete --lifecycle none "${template_scope_args[@]}" >"$out/complete-generate.log" 2>&1
dotnet new fs-gg-fable-game -n DefaultPlayer -o "$out/player" "${template_scope_args[@]}" >"$out/player-generate.log" 2>&1
if [[ -n "$templates_package" ]]; then
  python3 "$root/tests/composition/fable-game/external-reference-template-package.py" generated \
    "$out/complete" "$out/template-generated-independent.json"
  printf '%s  %s\n' "$templates_package_sha" "$archive" | sha256sum --check --strict
fi
[[ -f "$out/complete/SvgFoundation/Examples/ExternalAuthority/reference.json" ]]
[[ -f "$out/complete/SvgFoundation/Examples/FourD/reference.json" ]]
[[ ! -e "$out/player/SvgFoundation/Examples/ExternalAuthority" && ! -e "$out/player/SvgFoundation/Examples/FourD" ]]
grep -F 'ExternalAuthorityReference.install ()' "$out/complete/SvgFoundation/Program.fs" >/dev/null
# Candidate resolution changes only generated private locks. Public mode tests the
# shipped defaults and checked lockfiles with public-only resolution.
cp "$out/NuGet.Config" "$out/complete/NuGet.config"
export FsGgExternalReferenceCandidate=true
export NUGET_PACKAGES="$out/complete/.nuget/packages"
if [[ "$input_mode" == public ]]; then
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
        if node is not None: assert node.text=='0.32.1'
    for node in tree.findall('.//PackageReference'):
        if node.attrib.get('Include','').startswith('FS.GG.UI.'):
            assert node.attrib['Version'] in ['[0.32.1]','[$(FsGgSvgInputVersion)]','[$(FsGgSvgAuthoringVersion)]']
    module.validate_project_references(tree, project, root)
    lock=json.loads(path.with_name('packages.lock.json').read_text())
    for deps in lock['dependencies'].values():
        for name,row in deps.items():
            if name.startswith('FS.GG.UI.'):
                assert name in module.LOCK_HASH and row['resolved']=='0.32.1' and row['contentHash']==module.LOCK_HASH[name]
PYPUBLIC
  for project in SvgFoundation/SvgFoundation.fsproj SvgFoundation/Studio/Studio.fsproj SvgFoundation/Examples/Tactical/TacticalCompatibility.Tests.fsproj Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj Protocol.Tests/cross-runtime/CodecProbe.Fable/CodecProbe.Fable.fsproj; do
    dotnet restore "$out/complete/$project" --locked-mode --configfile "$out/NuGet.Config" >>"$out/public-locked-restore.log" 2>&1
  done
  python3 - "$out/complete/.nuget/packages" "$root/tests/composition/fable-game" "$producer_feed/release-custody.json" <<'PYCACHE'
import importlib.util,json,sys
from pathlib import Path
cache,helpers,custody=map(Path,sys.argv[1:]);spec=importlib.util.spec_from_file_location('public_input',helpers/'external-reference-public.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows={r['id']:r for r in json.loads(custody.read_text())['archives']}
for identity,sha in module.PUBLIC_SHA256.items():
    folder=cache/identity.lower()/'0.32.1';module.validate_archive(folder/(identity.lower()+'.0.32.1.nupkg'),identity,sha,rows[identity])
    assert json.loads((folder/'.nupkg.metadata').read_text())['contentHash']==module.LOCK_HASH[identity]
PYCACHE
else
  export FsGgSvgInputVersion="$version"
  dotnet restore "$out/complete/SvgFoundation/SvgFoundation.fsproj" --force-evaluate -p:RestoreLockedMode=false --configfile "$out/NuGet.Config" -p:FsGgSvgInputVersion="$version" >"$out/receiver-restore.log" 2>&1
fi
(cd "$out/complete" && dotnet tool restore --configfile "$out/NuGet.Config" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache) >"$out/fable-build.log" 2>&1
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
if [[ "$input_mode" == public ]]; then
  (cd "$out/complete" && bash Protocol.Tests/cross-runtime/run-cross-runtime.sh) >"$out/public-codec-build.log" 2>&1
  (cd "$out/complete" && bash SvgFoundation/Studio/build.sh) >"$out/public-studio-build.log" 2>&1
  dotnet run --project "$out/complete/SvgFoundation/Examples/Tactical/TacticalCompatibility.Tests.fsproj" --no-restore >"$out/public-tactical-build.log" 2>&1
  cp "$out/NuGet.Config" "$out/player/NuGet.config"
  dotnet restore "$out/player/SvgFoundation/SvgFoundation.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/public-player-restore.log" 2>&1
fi
dotnet restore "$out/complete/Server/Server.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/server-restore.log" 2>&1
dotnet publish "$out/complete/Server/Server.fsproj" -c Release --no-restore -m:1 -p:UseSharedCompilation=false -o "$out/complete/artifacts/authority-server" >"$out/server-publish.log" 2>&1
(cd "$out/complete/Browser.Tests" && npm ci) >"$out/npm-browser.log" 2>&1
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$out/browsers}"
(cd "$out/complete/Browser.Tests" && npx playwright install chromium firefox webkit) >"$out/browser-install.log" 2>&1
for family in chromium firefox webkit; do
  (cd "$out/complete/Browser.Tests" && PLAYWRIGHT_BROWSER_FAMILY="$family" npm test -- --grep 'external authority reference|FourD reference' --workers=1) >"$out/$family-browser.log" 2>&1
  cp "$out/complete/Browser.Tests/test-results/browser.json" "$out/$family-browser.json"
  python3 - "$out/$family-browser.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1])); stats=report['stats']
assert stats['expected']==8 and stats['unexpected']==0 and stats['skipped']==0 and stats['flaky']==0, stats
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
packet={'schema':'fsgg.external-reference-source-qualification/1','disposition':'passed','templates':template_identity,'producer':{'inputCustody':json.loads((Path(sys.argv[5])/'ROOT-CUSTODY.json').read_text()) if (Path(sys.argv[5])/'ROOT-CUSTODY.json').exists() else None,'custodyManifestSha256':hashlib.sha256((Path(sys.argv[5])/'release-custody.json').read_bytes()).hexdigest() if (Path(sys.argv[5])/'release-custody.json').exists() else None,**producer_identity,'candidateVersion':version,'archives':json.loads((out/'producer-archives.json').read_text()),'sourceEntries':json.loads((out/'producer-source-entries.json').read_text())},'environment':{'dotnet':subprocess.check_output(['dotnet','--info'],text=True),'node':subprocess.check_output(['node','--version'],text=True).strip(),'npm':subprocess.check_output(['npm','--version'],text=True).strip(),'fableLoadedVersion':(out/'fable-version.log').read_text().strip(),'fableLogSha256':hashlib.sha256((out/'fable-build.log').read_bytes()).hexdigest()},'receiver':hashes(out/'complete/SvgFoundation'),'browserFamilies':['chromium','firefox','webkit'],'browserReports':hashes(out/'complete/Browser.Tests/test-results'),'browserReportSha256':{family:hashlib.sha256((out/(family+'-browser.json')).read_bytes()).hexdigest() for family in ['chromium','firefox','webkit']},'passedPerFamily':8,'skipped':0,'domAutomation':True,'actualScreenReader':'not-observed','publication':False,'installedAcceptance':False,'renderingInputSource':'nuget.org' if sys.argv[6]=='public' else 'candidate','renderingPublicInputsQualified':sys.argv[6]=='public','templatesInputSource':'source-built-candidate','publicReadback':json.loads((out/'feed/public-readback.json').read_text()) if sys.argv[6]=='public' else None}
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
(out/'qualification.json').write_text(json.dumps(packet,indent=2)+'\n')
PY
printf 'external-reference-candidate: passed; evidence=%s/qualification.json\n' "$out"
