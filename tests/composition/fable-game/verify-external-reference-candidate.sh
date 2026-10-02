#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
producer="${1:?exact Rendering source checkout required}"
producer_feed="${2:?packed Rendering source feed required}"
version="${3:?isolated Rendering candidate version required}"
out="${4:?empty qualification directory required}"
expected_source="${5:-097e228388375bf27a03ac008627e4a038686c53}"
[[ "$expected_source" =~ ^[0-9a-f]{40}$ && "$version" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ && "$version" != 0.31.0 ]]
[[ ! -e "$out" && "$(git -C "$producer" rev-parse HEAD)" == "$expected_source" ]]
[[ -z "$(git -C "$producer" status --porcelain --untracked-files=no)" ]]
mkdir -p "$out"/{feed,home,packages,http}
out="$(realpath "$out")"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
# Each CLR stage is sequential; compilation must fit the integrator's live allocation.
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1
for id in FS.GG.UI.Scene FS.GG.UI.KeyboardInput FS.GG.UI.Scene.SvgBrowser; do
  cp "$producer_feed/$id.$version.nupkg" "$out/feed/"
done
python3 - "$producer" "$out/feed" "$version" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,sys
source,feed=map(Path,sys.argv[1:3]); version=sys.argv[3]
rows=[]
source_entries=[]
for package in sorted(feed.glob('*.nupkg')):
    rows.append({'name':package.name,'sha256':hashlib.sha256(package.read_bytes()).hexdigest()})
with ZipFile(feed/f'FS.GG.UI.Scene.SvgBrowser.{version}.nupkg') as archive:
    for name in ('SvgExternalSessionHost.fs','SvgExternalSessionHost.fsi','SvgInputHost.fs','SvgInputHost.fsi'):
        raw=archive.read('fable/'+name)
        assert raw==(source/'src/Scene.SvgBrowser'/name).read_bytes(), name
        source_entries.append({'path':'fable/'+name,'sha256':hashlib.sha256(raw).hexdigest()})
    profile='fable-compatibility/compatibility-profile.v1.json'
    assert archive.read(profile)==(source/'src/Scene.SvgBrowser/Fable/compatibility-profile.v1.json').read_bytes()
    source_entries.append({'path':profile,'sha256':hashlib.sha256(archive.read(profile)).hexdigest()})
(feed.parent/'producer-archives.json').write_text(json.dumps(rows,indent=2)+'\n')
(feed.parent/'producer-source-entries.json').write_text(json.dumps(source_entries,indent=2)+'\n')
PY
cat > "$out/NuGet.Config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.Scene"/><package pattern="FS.GG.UI.Scene.SvgBrowser"/><package pattern="FS.GG.UI.KeyboardInput"/></packageSource><packageSource key="public"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
CONFIG
# Reuse the canonical checked Python projection for a fresh complete Templates archive.
. "$root/tests/composition/fable-game/svg-source-python-fixture.sh"
prepare_svg_source_python_fixture "$root" "$out"
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/template" -m:1 -p:UseSharedCompilation=false >"$out/templates-pack.log" 2>&1
mapfile -t archives < <(find "$out/template" -maxdepth 1 -name '*.nupkg' -type f)
[[ "${#archives[@]}" == 1 ]]
dotnet new install "${archives[0]}" --force >"$out/template-install.log" 2>&1
dotnet new fs-gg-fable-game -n ExternalReference -o "$out/complete" --bundle complete --lifecycle none >"$out/complete-generate.log" 2>&1
dotnet new fs-gg-fable-game -n DefaultPlayer -o "$out/player" >"$out/player-generate.log" 2>&1
[[ -f "$out/complete/SvgFoundation/Examples/ExternalAuthority/reference.json" ]]
[[ -f "$out/complete/SvgFoundation/Examples/FourD/reference.json" ]]
[[ ! -e "$out/player/SvgFoundation/Examples/ExternalAuthority" && ! -e "$out/player/SvgFoundation/Examples/FourD" ]]
grep -F 'ExternalAuthorityReference.install ()' "$out/complete/SvgFoundation/Program.fs" >/dev/null
# Only this isolated generated receiver gets candidate resolution/locks. Public 0.31.0 and
# checked-in published lockfiles are never overwritten or inserted into an ambient cache.
cp "$out/NuGet.Config" "$out/complete/NuGet.Config"
export FsGgSvgInputVersion="$version" FsGgExternalReferenceCandidate=true
# Generated Directory.Build.props owns the receiver-private package root. Match it
# rather than assuming the environment overrides that explicit project property.
export NUGET_PACKAGES="$out/complete/.nuget/packages"
dotnet restore "$out/complete/SvgFoundation/SvgFoundation.fsproj" --force-evaluate -p:RestoreLockedMode=false --configfile "$out/NuGet.Config" -p:FsGgSvgInputVersion="$version" >"$out/receiver-restore.log" 2>&1
(cd "$out/complete" && dotnet tool restore && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache) >"$out/fable-build.log" 2>&1
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
assert str(root/'complete/.nuget/packages')+'/' in ''.join(assets['packageFolders'])
assert 'SvgExternalSessionHost' in (root/'complete/.nuget/packages/fs.gg.ui.scene.svgbrowser'/version/'fable/SvgExternalSessionHost.fs').read_text()
assert any((root/'complete/SvgFoundation/output').rglob('SvgExternalSessionHost.js')), 'external host missing from delivered Fable output'
PY
dotnet restore "$out/complete/Server/Server.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/server-restore.log" 2>&1
dotnet publish "$out/complete/Server/Server.fsproj" -c Release --no-restore -m:1 -p:UseSharedCompilation=false -o "$out/complete/artifacts/authority-server" >"$out/server-publish.log" 2>&1
(cd "$out/complete/Browser.Tests" && npm ci) >"$out/npm-browser.log" 2>&1
for family in chromium firefox webkit; do
  (cd "$out/complete/Browser.Tests" && PLAYWRIGHT_BROWSER_FAMILY="$family" npm test -- --grep 'external authority reference|FourD reference' --workers=1) >"$out/$family-browser.log" 2>&1
  cp "$out/complete/Browser.Tests/test-results/browser.json" "$out/$family-browser.json"
  python3 - "$out/$family-browser.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1])); stats=report['stats']
assert stats['expected']==4 and stats['unexpected']==0 and stats['skipped']==0 and stats['flaky']==0, stats
PY
done
python3 - "$root" "$producer" "$out" "$version" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
root,producer,out=map(Path,sys.argv[1:4]); version=sys.argv[4]
def git(path,field): return subprocess.check_output(['git','-C',str(path),'rev-parse',field],text=True).strip()
def hashes(path): return [{'path':p.relative_to(path).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(path.rglob('*')) if p.is_file() and 'node_modules' not in p.parts and 'obj' not in p.parts and 'bin' not in p.parts]
packet={'schema':'fsgg.external-reference-source-qualification/1','disposition':'passed','templates':{'revision':git(root,'HEAD'),'tree':git(root,'HEAD^{tree}')},'producer':{'revision':git(producer,'HEAD'),'tree':git(producer,'HEAD^{tree}'),'candidateVersion':version,'archives':json.loads((out/'producer-archives.json').read_text()),'sourceEntries':json.loads((out/'producer-source-entries.json').read_text())},'environment':{'dotnet':subprocess.check_output(['dotnet','--info'],text=True),'node':subprocess.check_output(['node','--version'],text=True).strip(),'npm':subprocess.check_output(['npm','--version'],text=True).strip(),'fableLoadedVersion':(out/'fable-version.log').read_text().strip(),'fableLogSha256':hashlib.sha256((out/'fable-build.log').read_bytes()).hexdigest()},'receiver':hashes(out/'complete/SvgFoundation'),'browserFamilies':['chromium','firefox','webkit'],'browserReports':hashes(out/'complete/Browser.Tests/test-results'),'browserReportSha256':{family:hashlib.sha256((out/(family+'-browser.json')).read_bytes()).hexdigest() for family in ['chromium','firefox','webkit']},'passedPerFamily':4,'skipped':0,'domAutomation':True,'actualScreenReader':'not-observed','publication':False,'installedAcceptance':False}
(out/'qualification.json').write_text(json.dumps(packet,indent=2)+'\n')
PY
printf 'external-reference-candidate: passed; evidence=%s/qualification.json\n' "$out"
