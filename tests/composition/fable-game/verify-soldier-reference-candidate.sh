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
# Historical compile custody stays exact; staged mode has an explicit immutable producer input.
[[ "$version" == 0.32.0 && "$phase" =~ ^(compile|staged)$ ]]
[[ "$expected_source" =~ ^[0-9a-f]{40}$ && "$expected_manifest" =~ ^[0-9a-f]{64}$ ]]
if [[ "$phase" == compile ]]; then
  [[ "$expected_source" == 237f66bcce46c9e6227a266231342b34367b060c ]]
  [[ "$expected_manifest" == d496fe3f69d873d7522d19897bc4a2955f670b958133d481a805141299f2fae1 ]]
fi
[[ ! -e "$out" && "$(git -C "$producer" rev-parse HEAD)" == "$expected_source" ]]
[[ -z "$(git -C "$producer" status --porcelain --untracked-files=no)" ]]
mkdir -p "$out"/{feed,home,packages,http}
out="$(realpath "$out")"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1 DOTNET_CLI_USE_MSBUILD_SERVER=0
python3 - "$producer" "$producer_feed" "$out" "$version" "$expected_source" "$expected_manifest" "$phase" <<'PY'
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
if sys.argv[7]=='compile': assert manifest['artifactId']=='sha256:4385c3b3ef8ac9188d6b28c75582cd5eeabff3227b2bb4d8ef88c1ceacb16ef6', 'fixture artifact identity'
source_manifest=feed.parent/'source-manifest.tsv'
source_raw=source_manifest.read_bytes()
assert manifest['sourceSha256']=='sha256:'+sha(source_raw), 'source manifest digest'
if sys.argv[7]=='compile': assert manifest['sourceSha256']=='sha256:fa33c2a5f2de93d2961f9844bad35350d787978c8ba734aa8ac6dbbba8faf393', 'source manifest digest'
assert manifest['artifactId']=='sha256:'+sha(json.dumps({key:manifest[key] for key in ('files','packages','sourceSha256','workloadSha256')},separators=(',',':'),ensure_ascii=False).encode()), 'fixture artifact derivation'
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
base_args=()
[[ "$phase" != staged ]] || base_args=(--base /soldier-player/)
(cd "$out/complete" && ./Client/node_modules/.bin/vite build --config SvgFoundation/vite.config.js "${base_args[@]}") >"$out/vite-build.log" 2>&1
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
if [[ "$phase" == staged ]]; then
  templates_source="$(git -C "$root" rev-parse HEAD)"
  dotnet msbuild "$out/complete/SvgFoundation/SvgFoundation.fsproj" -nologo \
    -getProperty:FsGgExternalReferenceCandidate -getProperty:FsGgSvgRuntimeCandidate \
    -getProperty:FsGgSvgInputCandidate -getProperty:FsGgSvgNetworkCandidate -getProperty:FsGgLegacyPreview >"$out/receiver-properties.json"
  python3 - "$root" "$out" "$expected_source" "$expected_manifest" <<'PYSTAGED'
from pathlib import Path
import hashlib,json,re,subprocess,sys
root,out=map(Path,sys.argv[1:3]); complete=out/'complete'
def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
asset=complete/'SvgFoundation/Examples/SoldierReference'
provenance=json.loads((asset/'provenance.json').read_text())
entry=(complete/'SvgFoundation/dist/index.html').read_text()
modules=re.findall(r'<script[^>]+type="module"[^>]+src="([^"]+)"',entry)
assert len(modules)==1 and modules[0].startswith('/soldier-player/assets/') and '..' not in modules[0]
module=complete/'SvgFoundation/dist'/modules[0].removeprefix('/soldier-player/')
inputs={'schema':'fsgg.soldier-staged-input/v1','renderingRevision':sys.argv[3],
        'templatesRevision':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),
        'candidateVersion':'0.32.0','producerManifestSha256':'sha256:'+sys.argv[4],
        'restoreAssetsSha256':sha(complete/'SvgFoundation/obj/project.assets.json'),
        'actualProgramSha256':sha(complete/'SvgFoundation/output/Program.js'),
        'programSourceSha256':sha(complete/'SvgFoundation/Program.fs'),
        'playerEntryModule':modules[0],'playerEntryModuleSha256':sha(module),
        'referenceSha256':sha(asset/'reference.json'),'provenanceSha256':sha(asset/'provenance.json'),
        'assetSha256':'sha256:'+provenance['canonicalContentSha256'],
        'adapterSha256':sha(root/'tests/composition/fable-game/soldier-staged-journey.js'),
        'actualEntry':'soldier-player/index.html','adapterEntry':'soldier-staged-journey.js',
        'evaluatedProperties':json.loads((out/'receiver-properties.json').read_text())['Properties'],
        'packageArchives':[{'name':row['name'],'sha256':'sha256:'+row['sha256']} for row in json.loads((out/'producer-archives.json').read_text())]}
(out/'staged-input.json').write_text(json.dumps(inputs,indent=2)+'\n')
PYSTAGED
  fixture_work="$(realpath "$producer_feed/..")"
  node "$producer/tests/Scene.SvgBrowser.Tests/package-fixture.mjs" --work "$fixture_work" \
    --profile soldier-functional --player-dist "$out/complete/SvgFoundation/dist" \
    --adapter "$root/tests/composition/fable-game/soldier-staged-journey.js" --input-metadata "$out/staged-input.json" \
    >"$out/staging.log" 2>&1
  sealed="$fixture_work/Browser/dist"
  cp "$sealed/artifact-manifest.json" "$out/staged-artifact-manifest.json"
  manifest_sha="sha256:$(sha256sum "$out/staged-artifact-manifest.json" | cut -d' ' -f1)"
  dotnet restore "$out/complete/Server/Server.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/server-restore.log" 2>&1
  dotnet publish "$out/complete/Server/Server.fsproj" -c Release --no-restore -o "$out/server" >"$out/server-publish.log" 2>&1
  mkdir -p "$out/server-home"
  server=''
  server_start=''
  origin=''
  cleanup_server() {
    local status=0
    if [[ -n "$server" ]]; then
      if [[ -r "/proc/$server/stat" ]]; then
        [[ "$(awk '{print $22}' "/proc/$server/stat")" == "$server_start" ]] || { echo 'server custody changed; refusing kill' >&2; return 1; }
        kill -TERM "$server" 2>/dev/null || true
      fi
      wait "$server" 2>/dev/null || status=$?
      if kill -0 "$server" 2>/dev/null; then
        printf 'server cleanup unknown: process remains %s\n' "$server" >&2
        return 1
      fi
      python3 - "$out/staged-result.json" "$status" "$origin" <<'PYCLEANUP'
from pathlib import Path
import json,sys,socket,urllib.parse
origin=urllib.parse.urlparse(sys.argv[3])
if origin.port:
 with socket.socket() as probe:
  probe.settimeout(1)
  assert probe.connect_ex(('127.0.0.1',origin.port))!=0, 'owned server listener did not settle'
p=Path(sys.argv[1])
if p.exists():
 value=json.loads(p.read_text()); value['driver']['serverCleanup']={'status':'observed-exited','exitCode':int(sys.argv[2])}
 p.write_text(json.dumps(value,indent=2)+'\n')
PYCLEANUP
      server=''
    fi
  }
  trap cleanup_server EXIT
  # Existing generated app, isolated test room, sealed webroot. No checkout, token or debug endpoint.
  (cd "$out/server" && exec timeout --signal=TERM --kill-after=5s 2400s \
    env -i PATH="$PATH" DOTNET_ROOT="${DOTNET_ROOT:-/usr/share/dotnet}" DOTNET_CLI_HOME="$out/server-home" \
    ASPNETCORE_ENVIRONMENT=Production dotnet "$out/server/Server.dll" --urls http://127.0.0.1:0 --webroot "$sealed") \
    >"$out/staged-server.log" 2>&1 & server=$!
  server_start="$(awk '{print $22}' "/proc/$server/stat")"
  for _ in {1..120}; do
    origin="$(sed -nE 's@.*Now listening on: (http://127\.0\.0\.1:[0-9]+).*@\1@p' "$out/staged-server.log" | head -1)"
    [[ -z "$origin" ]] || break
    kill -0 "$server" 2>/dev/null || { tail -n 80 "$out/staged-server.log" >&2; exit 1; }
    sleep .25
  done
  [[ "$origin" =~ ^http://127\.0\.0\.1:[0-9]+$ ]]
  curl -fsS "$origin/healthz" >/dev/null
  executable_args=()
  [[ -z "${PLAYWRIGHT_EXECUTABLE_PATH:-}" ]] || executable_args=(--executable "$PLAYWRIGHT_EXECUTABLE_PATH")
  node "$fixture_work/Browser/drive-suite.mjs" --base-url "$origin/" \
    --profile soldier-functional --manifest-sha256 "$manifest_sha" --deadline-ms 750000 \
    --out "$out/staged-result.json" --exercise-resume "${executable_args[@]}" >"$out/staged-driver.log" 2>&1
  # Every adversarial driver invocation must download a failed report and refuse acceptance.
  for mutant in missing-mount wrong-entry source-hash asset-hash bundle-hash workload-hash missing-case stale-checkpoint stale-epoch-accepted incomplete-export owner-leak artifact-before-download artifact-after-download; do
    if node "$fixture_work/Browser/drive-suite.mjs" --base-url "$origin/" \
      --profile soldier-functional --manifest-sha256 "$manifest_sha" --deadline-ms 120000 \
      --out "$out/staged-negative-$mutant.json" --mutant "$mutant" "${executable_args[@]}" >"$out/staged-negative-$mutant.log" 2>&1; then
      echo "staged mutant survived: $mutant" >&2; exit 1
    fi
    python3 - "$out/staged-negative-$mutant.json" <<'PYNEGATIVE'
from pathlib import Path
import json,sys
value=json.loads(Path(sys.argv[1]).read_text())
assert value['outcome'] in ('failed','capability-check-failed') and value['driver']['downloadObserved'] is True
assert value['driver']['browserCleanup']=='observed-closed'
PYNEGATIVE
  done
  cleanup_server
  python3 "$root/tests/composition/fable-game/test-soldier-staged-fixture.py" --verify "$out/staged-result.json" \
    --manifest "$out/staged-artifact-manifest.json" --rendering "$expected_source" --templates "$templates_source" >"$out/staged-verification.log" 2>&1
  trap - EXIT
fi
dotnet new uninstall "${archives[0]}" >"$out/template-uninstall.log" 2>&1
printf 'soldier-reference-candidate: compile passed; evidence=%s/compile-qualification.json\n' "$out"
