#!/usr/bin/env bash
# Separate unpublished producer/receiver qualification; never public0.32.3 acceptance.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
producer="${1:?exact Rendering checkout required}"
expected="${2:?immutable Rendering commit required}"
fixture="${3:?existing producer fixture required}"
template="${4:?qualified Templates candidate archive required}"
out="${5:?absent output directory required}"
[[ "$expected" =~ ^[0-9a-f]{40}$ && "$producer" = /* && "$fixture" = /* && "$template" = /* && "$out" = /* && ! -e "$out" ]]
[[ "$(git -C "$producer" rev-parse HEAD)" == "$expected" ]]
[[ -z "$(git -C "$producer" status --porcelain --untracked-files=all)" ]]
version=0.32.0 # Existing Rendering build-fixture.sh candidate-pack identity, not publication.
mkdir -m 700 "$out"
mkdir -p "$out/home" "$out/packages" "$out/http"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
python3 - "$fixture/feed" "$expected" "$template" "$out/candidate-input.json" "$(git -C "$root" rev-parse HEAD)" <<'PY'
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import hashlib,json,sys
feed,source,template,destination=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]),Path(sys.argv[4])
rows=[]
for identity in ['FS.GG.UI.Scene','FS.GG.UI.KeyboardInput','FS.GG.UI.Scene.SvgBrowser']:
 path=feed/(identity+'.0.32.0.nupkg')
 if path.is_symlink() or not path.is_file():raise SystemExit('candidate package missing or linked: '+identity)
 with ZipFile(path) as archive:
  metadata=ET.fromstring(archive.read(identity+'.nuspec'))
  field=lambda name:[v for v in metadata.iter() if v.tag.rsplit('}',1)[-1]==name]
  if len(field('repository'))!=1 or field('repository')[0].get('commit')!=source:raise SystemExit('candidate package source differs: '+identity)
  if len(field('version'))!=1 or field('version')[0].text!='0.32.0':raise SystemExit('candidate package version differs')
 rows.append({'id':identity,'version':'0.32.0','file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
with ZipFile(template) as archive:
 metadata=ET.fromstring(archive.read('FS.GG.Workspace.Template.nuspec'))
 fields=lambda name:[v for v in metadata.iter() if v.tag.rsplit('}',1)[-1]==name]
 if len(fields('repository'))!=1 or fields('repository')[0].get('commit')!=sys.argv[5]:raise SystemExit('Templates candidate source differs')
 if len(fields('id'))!=1 or fields('id')[0].text!='FS.GG.Workspace.Template':raise SystemExit('Templates candidate identity differs')
 if len(fields('version'))!=1:raise SystemExit('Templates candidate version missing')
 template_version=fields('version')[0].text
record={'templatesSource':sys.argv[5],'templatesVersion':template_version,'schema':'fsgg.palette-candidate-input/1','renderingSource':source,'archives':rows,
        'templatesArchiveSha256':hashlib.sha256(template.read_bytes()).hexdigest(),
        'qualification':'unpublished-source-candidate','publication':False,'installedPublicAcceptance':False}
destination.write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
PY
# Install only the exact source-bound Templates candidate into this private home.
(
 cd "$fixture"
 [[ "$(dotnet --version)" == 10.0.401 ]]
 dotnet new install "$template" --force >"$out/template-install.log" 2>&1
 dotnet new fs-gg-fable-game -n PaletteCandidate -o "$out/receiver" --lifecycle none --svgFoundation true >"$out/generate.log" 2>&1
)
# The explicit restore config is outside receiver ancestry: candidate mapping
# must not leak into generated tool restore, whose public source key is nuget.org.
# The candidate profile generates its own lock; retained/public locks are unchanged.
mkdir "$out/candidate-config"
cat > "$out/candidate-config/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$fixture/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.*"/></packageSource><packageSource key="public"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
EOF
(
 cd "$out/receiver"
 [[ "$(dotnet --version)" == 10.0.401 ]]
 dotnet restore SvgFoundation/Studio/Studio.fsproj --configfile "$out/candidate-config/NuGet.Config" \
   -p:FsGgSvgAuthoringVersion="$version" -p:RestoreLockedMode=false -p:RestoreForceEvaluate=true \
   >"$out/candidate-restore.log" 2>&1
)
verify_consumer() {
 python3 - "$out" "$1" <<'PYCONSUMER'
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import hashlib,json,sys
root=Path(sys.argv[1]);stage=sys.argv[2]
if stage not in ('before','after'):raise SystemExit('unknown consumer stage')
record=json.loads((root/'candidate-input.json').read_text())
assets_path=root/'receiver/SvgFoundation/Studio/obj/project.assets.json'
assets=json.loads(assets_path.read_text());packages=(root/'receiver/.nuget/packages').resolve()
if {str(Path(p).resolve()) for p in assets['packageFolders']}!={str(packages)}:raise SystemExit('receiver package folder differs')
expected={row['id'].lower()+'/'+row['version']:row for row in record['archives']}
actual={key.lower():value for key,value in assets['libraries'].items() if key.lower().startswith('fs.gg.ui.')}
if set(actual)!=set(expected):raise SystemExit('receiver UI package closure differs')
rows=[]
for key,row in expected.items():
 library=actual[key]
 if library.get('type')!='package' or library.get('path')!=key:raise SystemExit('receiver package path differs')
 path=packages/key/(row['id'].lower()+'.'+row['version']+'.nupkg')
 if path.is_symlink() or not path.is_file():raise SystemExit('restored receiver archive missing or linked')
 if path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise SystemExit('restored receiver archive differs')
 with ZipFile(path) as archive:
  metadata=ET.fromstring(archive.read(row['id']+'.nuspec'))
  repositories=[v for v in metadata.iter() if v.tag.rsplit('}',1)[-1]=='repository']
  if len(repositories)!=1 or repositories[0].get('commit')!=record['renderingSource']:raise SystemExit('restored receiver source differs')
 rows.append({'id':row['id'],'version':row['version'],'sha256':row['sha256']})
(root/('consumer-'+stage+'.json')).write_text(json.dumps({'packageFolder':str(packages),'archives':rows,
 'assetsSha256':hashlib.sha256(assets_path.read_bytes()).hexdigest()},sort_keys=True,indent=2)+'\n')
PYCONSUMER
}
verify_consumer before
lock="$out/receiver/SvgFoundation/Studio/packages.lock.json"
lock_sha="$(sha256sum "$lock" | cut -d' ' -f1)"
(
 cd "$out/receiver"
 FSGG_SVG_AUTHORING_VERSION="$version" FSGG_SVG_CANDIDATE_FEED="$fixture/feed" \
   bash SvgFoundation/Studio/build.sh >"$out/studio-build.log" 2>&1
)
[[ "$(sha256sum "$lock" | cut -d' ' -f1)" == "$lock_sha" ]]
verify_consumer after
studio="$out/receiver/SvgFoundation/Studio/dist"
[[ -f "$studio/index.html" ]]
(cd "$studio" && exec python3 -m http.server 8144 --bind 127.0.0.1 >"$out/server.log" 2>&1) & server=$!
trap 'kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
for _ in {1..80}; do curl -fsS http://127.0.0.1:8144/ >/dev/null && break; sleep .25; done
# Same real observer and runtime as the public route, with separate evidence/identity.
orca --version >"$out/orca-version.log"
[[ "$(cat "$out/orca-version.log")" == 46.1 ]]
SVG_ORCA_BROWSER_FAMILY=chromium timeout --signal=TERM --kill-after=15s 5m \
 bash "$root/tests/composition/fable-game/observe-svg-input-orca.sh" http://127.0.0.1:8144/ "$out/orca-input.json"
jq -e '.result=="passed" and .paletteAnnouncement.name=="Command palette" and .paletteAnnouncement.role=="dialog" and .paletteAnnouncement.initialFocus=="heading" and .keyboard.escape=="passed" and .keyboard.focusRestoration=="passed"' "$out/orca-input.json" >/dev/null
# A passing speech observation is not a successful qualification until its owned
# direct server has stopped and been reaped. The failure trap remains a fallback.
kill -TERM "$server"
server_exit=0
wait "$server" || server_exit=$?
# Once reaped, this PID must never be signalled by the failure trap.
trap - EXIT
[[ "$server_exit" == 143 ]] # Direct Python server's expected SIGTERM terminal status.
python3 - "$out" "$lock_sha" "$server_exit" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);record=json.loads((root/'candidate-input.json').read_text())
record.update(schema='fsgg.palette-candidate-qualification/1',studioLockSha256=sys.argv[2],
              observerSha256=hashlib.sha256((root/'orca-input.json').read_bytes()).hexdigest(),
              orcaVersion=(root/'orca-version.log').read_text().strip(),
              consumerBeforeSha256=hashlib.sha256((root/'consumer-before.json').read_bytes()).hexdigest(),
              consumerAfterSha256=hashlib.sha256((root/'consumer-after.json').read_bytes()).hexdigest(),
              serverCleanup={'signal':'SIGTERM','expectedExit':143,'actualExit':int(sys.argv[3]),'reaped':True},disposition='passed')
(root/'qualification.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
PY
