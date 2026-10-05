#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
producer="${1:?exact Rendering source checkout required}"
producer_feed="${2:?packed Rendering source feed required}"
version="${3:?isolated Rendering candidate version required}"
out="${4:?empty qualification directory required}"
expected_source="${5:?exact admitted Rendering source revision required}"
expected_custody="${6:?SHA-256 of root-admitted release-custody.json required}"
phase="${7:-all}"
[[ "$phase" == compile || "$phase" == chromium || "$phase" == all ]]
[[ "$expected_custody" =~ ^[0-9a-f]{64}$ && -f "$producer_feed/release-custody.json" && -f "$producer_feed/ROOT-CUSTODY.json" ]]
[[ "$(sha256sum "$producer_feed/release-custody.json" | cut -d ' ' -f 1)" == "$expected_custody" ]]
[[ "$expected_source" =~ ^[0-9a-f]{40}$ && "$version" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ && "$version" != 0.31.0 ]]
[[ ! -e "$out" && "$(git -C "$producer" rev-parse HEAD)" == "$expected_source" ]]
[[ -z "$(git -C "$producer" status --porcelain --untracked-files=no)" ]]
mkdir -p "$out"/{feed,home,packages,http}
out="$(realpath "$out")"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
# Each CLR stage is sequential; compilation must fit the integrator's live allocation.
export DOTNET_PROCESSOR_COUNT=1 MSBUILDDISABLENODEREUSE=1 DOTNET_CLI_USE_MSBUILD_SERVER=0
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
    for name in ('SvgExternalSessionHost.fs','SvgExternalSessionHost.fsi','SvgInputHost.fs','SvgInputHost.fsi','SvgSessionHost.fs','SvgSessionHost.fsi','SvgBrowser.fs','SvgBrowser.fsi'):
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
for name in ('SoldierReference.fs.js','SoldierReferenceLocal.fs.js','SoldierReferenceExternal.fs.js','SoldierWorkload.fs.js','SoldierDocument.fs.js'):
    assert any((root/'complete/SvgFoundation/output').rglob(name)), name
PY
if [[ "$phase" == compile ]]; then
  python3 - "$root" "$out" "$expected_source" "$expected_custody" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
root,out=map(Path,sys.argv[1:3])
receipt={'schema':'fsgg.soldier-reference-compile/1','disposition':'passed','templatesRevision':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'producerRevision':sys.argv[3],'custodySha256':sys.argv[4],'archives':json.loads((out/'producer-archives.json').read_text()),'fableLogSha256':hashlib.sha256((out/'fable-build.log').read_bytes()).hexdigest(),'browserExecuted':False,'publication':False}
(out/'compile-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
PY
  dotnet new uninstall "${archives[0]}" >"$out/template-uninstall.log" 2>&1
  printf 'soldier-reference-candidate: compile passed; evidence=%s/compile-qualification.json\n' "$out"
  exit 0
fi
dotnet restore "$out/complete/Server/Server.fsproj" --locked-mode --configfile "$out/NuGet.Config" >"$out/server-restore.log" 2>&1
dotnet publish "$out/complete/Server/Server.fsproj" -c Release --no-restore --disable-build-servers -m:1 -p:UseSharedCompilation=false -p:BuildInParallel=false -o "$out/complete/artifacts/authority-server" >"$out/server-publish.log" 2>&1
(cd "$out/complete/Browser.Tests" && npm ci) >"$out/npm-browser.log" 2>&1
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$out/browsers}"
(cd "$out/complete/Browser.Tests" && if [[ "$phase" == all ]]; then npx playwright install chromium firefox webkit; else npx playwright install chromium; fi) >"$out/browser-install.log" 2>&1
families=(chromium)
if [[ "$phase" == all ]]; then families=(chromium firefox webkit); fi
for family in "${families[@]}"; do
  (cd "$out/complete/Browser.Tests" && PLAYWRIGHT_BROWSER_FAMILY="$family" npm test -- --grep '^soldier reference ' --workers=1) >"$out/$family-browser.log" 2>&1
  cp "$out/complete/Browser.Tests/test-results/browser.json" "$out/$family-browser.json"
  python3 - "$out/$family-browser.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1])); stats=report['stats']
assert stats['expected']==3 and stats['unexpected']==0 and stats['skipped']==0 and stats['flaky']==0, stats
PY
done
python3 - "$root" "$producer" "$out" "$version" "$producer_feed" "$expected_custody" "$phase" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
root,producer,out=map(Path,sys.argv[1:4]); version=sys.argv[4]
families=['chromium','firefox','webkit'] if sys.argv[7]=='all' else ['chromium']
def git(path,field): return subprocess.check_output(['git','-C',str(path),'rev-parse',field],text=True).strip()
def hashes(path): return [{'path':p.relative_to(path).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(path.rglob('*')) if p.is_file() and 'node_modules' not in p.parts and 'obj' not in p.parts and 'bin' not in p.parts]
packet={'schema':'fsgg.soldier-reference-source-qualification/1','disposition':'passed','templates':{'revision':git(root,'HEAD'),'tree':git(root,'HEAD^{tree}')},'producer':{'admittedCustodySha256':sys.argv[6],'inputCustody':json.loads((Path(sys.argv[5])/'ROOT-CUSTODY.json').read_text()) if (Path(sys.argv[5])/'ROOT-CUSTODY.json').exists() else None,'custodyManifestSha256':hashlib.sha256((Path(sys.argv[5])/'release-custody.json').read_bytes()).hexdigest() if (Path(sys.argv[5])/'release-custody.json').exists() else None,'revision':git(producer,'HEAD'),'tree':git(producer,'HEAD^{tree}'),'candidateVersion':version,'archives':json.loads((out/'producer-archives.json').read_text()),'sourceEntries':json.loads((out/'producer-source-entries.json').read_text())},'environment':{'dotnet':subprocess.check_output(['dotnet','--info'],text=True),'node':subprocess.check_output(['node','--version'],text=True).strip(),'npm':subprocess.check_output(['npm','--version'],text=True).strip(),'fableLoadedVersion':(out/'fable-version.log').read_text().strip(),'fableLogSha256':hashlib.sha256((out/'fable-build.log').read_bytes()).hexdigest()},'receiver':hashes(out/'complete/SvgFoundation'),'browserFamilies':families,'browserReports':hashes(out/'complete/Browser.Tests/test-results'),'browserReportSha256':{family:hashlib.sha256((out/(family+'-browser.json')).read_bytes()).hexdigest() for family in families},'passedPerFamily':3,'skipped':0,'domAutomation':True,'actualScreenReader':'not-observed','publication':False,'installedAcceptance':False}
(out/'qualification.json').write_text(json.dumps(packet,indent=2)+'\n')
PY
dotnet new uninstall "${archives[0]}" >"$out/template-uninstall.log" 2>&1
printf 'soldier-reference-candidate: passed; evidence=%s/qualification.json\n' "$out"
