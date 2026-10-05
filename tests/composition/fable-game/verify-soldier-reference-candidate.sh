#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
producer="${1:?exact Rendering source checkout required}"
producer_feed="${2:?packed Rendering source feed required}"
version="${3:?isolated Rendering candidate version required}"
out="${4:?empty qualification directory required}"
expected_source="${5:?exact admitted Rendering source revision required}"
expected_manifest="${6:?SHA-256 of root-admitted existing fixture manifest required}"
phase="${7:-compile}"
# This exact source profile is compile-only. Browser/publication admission remains separate.
[[ "$phase" == compile && "$version" == 0.32.0 ]]
[[ "$expected_source" == 237f66bcce46c9e6227a266231342b34367b060c ]]
[[ "$expected_manifest" == d496fe3f69d873d7522d19897bc4a2955f670b958133d481a805141299f2fae1 ]]
[[ ! -e "$out" && "$(git -C "$producer" rev-parse HEAD)" == "$expected_source" ]]
[[ -z "$(git -C "$producer" status --porcelain --untracked-files=no)" ]]
mkdir -p "$out"/{feed,home,packages,http}
out="$(realpath "$out")"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1 DOTNET_CLI_USE_MSBUILD_SERVER=0
python3 - "$producer" "$producer_feed" "$out" "$version" "$expected_source" "$expected_manifest" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
source,feed,out=map(Path,sys.argv[1:4]); version,head,expected_manifest=sys.argv[4:7]
def sha(raw): return hashlib.sha256(raw).hexdigest()
def unique(pairs):
    value={}
    for key,item in pairs:
        if key in value: raise ValueError('duplicate manifest field: '+key)
        value[key]=item
    return value
manifest_path=feed.parent/'Browser/dist/artifact-manifest.json'
manifest_raw=manifest_path.read_bytes()
assert sha(manifest_raw)==expected_manifest, 'fixture manifest digest'
manifest=json.loads(manifest_raw,object_pairs_hook=unique)
assert manifest['schema']=='fsgg.svg-coherence.fixture/v1', 'fixture schema'
assert manifest['artifactId']=='sha256:4385c3b3ef8ac9188d6b28c75582cd5eeabff3227b2bb4d8ef88c1ceacb16ef6', 'fixture artifact identity'
source_manifest=feed.parent/'source-manifest.tsv'
source_raw=source_manifest.read_bytes()
assert manifest['sourceSha256']=='sha256:'+sha(source_raw)=='sha256:fa33c2a5f2de93d2961f9844bad35350d787978c8ba734aa8ac6dbbba8faf393', 'source manifest digest'
assert source_raw==(feed.parent/'source-manifest-after.tsv').read_bytes(), 'producer source drift'
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==head
paths=[]
for line in source_raw.decode().splitlines():
    digest,relative=line.split('\t')
    path=Path(relative)
    assert not path.is_absolute() and '..' not in path.parts and relative not in paths
    assert sha((source/path).read_bytes())==digest, relative
    paths.append(relative)
# Match the existing producer source-manifest.sh inventory, not just a subset of declared rows.
tracked=subprocess.check_output(['git','-C',str(source),'ls-files','-z','--cached','--others','--exclude-standard','--','src/KeyboardInput','src/Scene','src/Scene.SvgBrowser','tests/Scene.SvgBrowser.Tests','tests/Scene.PortableConsumers/DocumentRoundTrip.fs']).decode().split('\0')
excluded={'bin','obj','node_modules','dist'}
actual=sorted(p for p in tracked if p and not excluded.intersection(Path(p).parts) and Path(p).name!='packages.lock.json')
assert paths==actual, 'producer source inventory mismatch'
ids={'FS.GG.UI.Scene':'Scene','FS.GG.UI.KeyboardInput':'KeyboardInput','FS.GG.UI.Scene.SvgBrowser':'Scene.SvgBrowser'}
expected={f'{id}.{version}.nupkg' for id in ids}
packages=manifest['packages']
assert len(packages)==3 and {row['path'] for row in packages}==expected, 'three-package fixture roster'
assert {p.name for p in feed.glob('*.nupkg')}==expected, 'source feed roster'
rows=[]; source_entries=[]
for row in packages:
    archive_path=feed/row['path']
    assert archive_path.is_file() and not archive_path.is_symlink()
    raw=archive_path.read_bytes()
    assert row['sha256']=='sha256:'+sha(raw), row['path']
    with ZipFile(archive_path) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names)), 'duplicate archive entry'
        nuspecs=[name for name in names if '/' not in name and name.endswith('.nuspec')]
        assert len(nuspecs)==1
        metadata=ET.fromstring(archive.read(nuspecs[0]))
        def node(name): return metadata.find('.//{*}'+name)
        id=node('id').text
        assert id in ids and node('version').text==version
        assert node('repository').attrib['commit']==head
        assert node('repository').attrib['url']=='https://github.com/FS-GG/FS.GG.Rendering.git'
        dependencies=[dict(item.attrib) for item in metadata.findall('.//{*}dependency')]
        internal={item['id'] for item in dependencies if item['id'].startswith('FS.GG.UI.')}
        assert internal==({'FS.GG.UI.Scene'} if id.endswith('KeyboardInput') else {'FS.GG.UI.Scene','FS.GG.UI.KeyboardInput'} if id.endswith('SvgBrowser') else set())
        project=source/'src'/ids[id]/'Fable'/f'{id}.fsproj'
        compile_names=[item.attrib['Include'] for item in ET.parse(project).findall('.//Compile')]
        delivered={name for name in names if name.startswith('fable/') and name.endswith(('.fs','.fsi'))}
        assert delivered=={'fable/'+name for name in compile_names}, id+' Fable source roster'
        for name in compile_names:
            entry='fable/'+name
            payload=archive.read(entry)
            assert payload==(source/'src'/ids[id]/name).read_bytes(), id+'/'+name
            source_entries.append({'package':id,'path':entry,'sha256':sha(payload)})
        for entry, source_path in [('fable/'+project.name,project),('fable-compatibility/compatibility-profile.v1.json',project.parent/'compatibility-profile.v1.json')]:
            assert archive.read(entry)==source_path.read_bytes(), id+'/'+entry
    # Copy only after verification, then verify the private receiver copy again.
    destination=out/'feed'/row['path']
    shutil.copyfile(archive_path,destination)
    assert sha(destination.read_bytes())==sha(raw), 'receiver copy differs'
    rows.append({'name':row['path'],'sha256':sha(raw),'repositoryCommit':head})
assert len(source_entries)==38, 'complete admitted Fable source count'
(out/'producer-archives.json').write_text(json.dumps(rows,indent=2)+'\n')
(out/'producer-source-entries.json').write_text(json.dumps(source_entries,indent=2)+'\n')
(out/'producer-fixture-manifest.json').write_bytes(manifest_raw)
(out/'producer-source-manifest.tsv').write_bytes(source_raw)
(out/'producer-fixture-input.json').write_text(json.dumps({'schema':manifest['schema'],'artifactId':manifest['artifactId'],'manifestPath':str(manifest_path),'manifestSha256':expected_manifest,'producerRevision':head,'sourceManifestSha256':sha(source_raw),'archives':rows,'releaseCustody':False,'publication':False,'installedAcceptance':False},indent=2)+'\n')
PY
cat > "$out/NuGet.Config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.Scene"/><package pattern="FS.GG.UI.Scene.SvgBrowser"/><package pattern="FS.GG.UI.KeyboardInput"/></packageSource><packageSource key="public"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
CONFIG
[[ -n "${FSGG_PYTHON_COORDINATION_ROOT:-}" ]]
# Reuse the canonical checked Python projection for a fresh complete Templates archive.
. "$root/tests/composition/fable-game/svg-source-python-fixture.sh"
prepare_svg_source_python_fixture "$root" "$out"
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/template" --disable-build-servers -m:1 -p:UseSharedCompilation=false -p:BuildInParallel=false >"$out/templates-pack.log" 2>&1
mapfile -t archives < <(find "$out/template" -maxdepth 1 -name '*.nupkg' -type f)
[[ "${#archives[@]}" == 1 ]]
dotnet new install "${archives[0]}" --force >"$out/template-install.log" 2>&1
dotnet new fs-gg-fable-game -n SoldierReference -o "$out/complete" --bundle complete --lifecycle none >"$out/complete-generate.log" 2>&1
dotnet new fs-gg-fable-game -n DefaultPlayer -o "$out/player" >"$out/player-generate.log" 2>&1
[[ -f "$out/complete/SvgFoundation/Examples/ExternalAuthority/reference.json" ]]
[[ -f "$out/complete/SvgFoundation/Examples/FourD/reference.json" ]]
[[ ! -e "$out/player/SvgFoundation/Examples/ExternalAuthority" && ! -e "$out/player/SvgFoundation/Examples/FourD" ]]
[[ -f "$out/complete/SvgFoundation/Examples/SoldierReference/reference.json" && -f "$out/complete/SvgFoundation/SoldierReference.fs" && -f "$out/complete/Browser.Tests/soldier-reference.spec.ts" ]]
[[ ! -e "$out/player/SvgFoundation/Examples/SoldierReference" && ! -e "$out/player/SvgFoundation/SoldierReference.fs" && ! -e "$out/player/Browser.Tests/soldier-reference.spec.ts" ]]
grep -F 'SoldierReference.install ()' "$out/complete/SvgFoundation/Program.fs" >/dev/null
# Only this isolated generated receiver gets candidate resolution/locks. Public 0.31.0 and
# checked-in published lockfiles are never overwritten or inserted into an ambient cache.
cp "$out/NuGet.Config" "$out/complete/NuGet.config"
export FsGgSvgInputVersion="$version" FsGgExternalReferenceCandidate=true
# Generated Directory.Build.props owns the receiver-private package root. Match it
# rather than assuming the environment overrides that explicit project property.
export NUGET_PACKAGES="$out/complete/.nuget/packages"
dotnet restore "$out/complete/SvgFoundation/SvgFoundation.fsproj" --force-evaluate -p:RestoreLockedMode=false --configfile "$out/NuGet.Config" -p:FsGgSvgInputVersion="$version" >"$out/receiver-restore.log" 2>&1
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
output=root/'complete/SvgFoundation/output'
for relative in ('SoldierReference.js','SoldierReferenceLocal.js','SoldierReferenceExternal.js',
                 'Examples/SoldierReference/SoldierWorkload.js','Examples/SoldierReference/SoldierDocument.js'):
    assert (output/relative).is_file(), relative
assert 'from "./SoldierReference.js"' in (output/'Program.js').read_text(), 'actual entry missing reference import'
PY
python3 - "$root" "$out" "$expected_source" "$expected_manifest" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
root,out=map(Path,sys.argv[1:3])
receipt={'schema':'fsgg.soldier-reference-compile/1','disposition':'passed','templatesRevision':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'producerRevision':sys.argv[3],'inputProfile':'existing-fixture-compile-only','fixtureInput':json.loads((out/'producer-fixture-input.json').read_text()),'fixtureManifestSha256':sys.argv[4],'releaseCustody':False,'archives':json.loads((out/'producer-archives.json').read_text()),'fableLogSha256':hashlib.sha256((out/'fable-build.log').read_bytes()).hexdigest(),'browserExecuted':False,'publication':False}
(out/'compile-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
PY
dotnet new uninstall "${archives[0]}" >"$out/template-uninstall.log" 2>&1
printf 'soldier-reference-candidate: compile passed; evidence=%s/compile-qualification.json\n' "$out"
