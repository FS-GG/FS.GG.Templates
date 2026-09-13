#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
packet="${1:?usage: $0 <rendering-packet.json> <empty-output-directory>}"
final_output="${2:?usage: $0 <rendering-packet.json> <empty-output-directory>}"
[[ -f "$packet" ]] || { echo "SVG authoring candidate: packet manifest is missing" >&2; exit 2; }
[[ ! -e "$final_output" ]] || { echo "SVG authoring candidate: output identity already exists: $final_output" >&2; exit 2; }
output="$final_output.staging.$$"
mkdir -p "$output/feed"
work=''
cleanup() { [[ -z "${work:-}" ]] || rm -rf "$work"; [[ -z "${output:-}" ]] || rm -rf "$output"; }
trap cleanup EXIT

readarray -t values < <(python3 - "$packet" <<'PY'
import hashlib,json,pathlib,re,sys,zipfile
p=pathlib.Path(sys.argv[1]).resolve(); data=json.loads(p.read_text())
if data.get('schema')!='fsgg.svg-author.rendering-candidate/v1': raise SystemExit('unsupported Rendering packet schema')
source=data.get('source',{})
if source.get('repository')!='FS-GG/FS.GG.Rendering': raise SystemExit('unexpected Rendering packet repository')
revision=source.get('commit','')
if not re.fullmatch(r'[0-9a-f]{40}',revision): raise SystemExit('invalid merged Rendering revision')
version=data.get('version','')
if not re.fullmatch(r'0\.30\.0-svg-author\.1\.[0-9a-f]{8}(\.[0-9A-Za-z.-]+)?',version): raise SystemExit('invalid Rendering candidate version')
packages=data.get('packages',[])
rows=[]
expected=['FS.GG.UI.KeyboardInput','FS.GG.UI.Scene','FS.GG.UI.Scene.SvgBrowser']
for identity in expected:
    matches=[value for value in packages if value.get('file','').lower()==f'{identity}.{version}.nupkg'.lower()]
    if len(matches)!=1: raise SystemExit(f'missing or duplicate {identity} archive')
    value=matches[0]; path=(p.parent/'packages'/value['file']).resolve()
    if not path.is_file(): raise SystemExit(f'missing {identity} archive')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=value.get('sha256'): raise SystemExit(f'{identity} archive hash mismatch')
    rows.append(path)
browser=next(path for path in rows if 'SvgBrowser' in path.name)
with zipfile.ZipFile(browser) as archive:
    worker=data.get('worker',{}); worker_bytes=archive.read(worker.get('path',''))
    if hashlib.sha256(worker_bytes).hexdigest()!=worker.get('sha256') or len(worker_bytes)!=worker.get('bytes'):
        raise SystemExit('packaged geometry worker identity mismatch')
    for name,value in data.get('resources',{}).items():
        payload=archive.read(name)
        if hashlib.sha256(payload).hexdigest()!=value.get('sha256') or len(payload)!=value.get('bytes'):
            raise SystemExit(f'packaged resource identity mismatch: {name}')
    lock=data.get('npmLocks',{}).get('src/Scene.SvgBrowser/package-lock.json')
    if lock!=data.get('resources',{}).get('contentFiles/any/any/package-lock.json',{}).get('sha256'):
        raise SystemExit('packaged npm lock identity mismatch')
for entry,value in data.get('fableInterfaces',{}).items():
    archive_name,member=entry.split(':',1); archive_path=p.parent/'packages'/archive_name
    with zipfile.ZipFile(archive_path) as archive: payload=archive.read(member)
    if hashlib.sha256(payload).hexdigest()!=value.get('sha256') or len(payload)!=value.get('bytes'):
        raise SystemExit(f'curated Fable interface identity mismatch: {entry}')
print(revision)
print(version)
for path in rows: print(path)
PY
)
rendering_revision="${values[0]}"
rendering_version="${values[1]}"
for archive in "${values[@]:2}"; do cp "$archive" "$output/feed/"; done

work="$(mktemp -d "${TMPDIR:-/tmp}/svg-authoring-template.XXXXXX")"
git -C "$root" archive HEAD | tar -x -C "$work"
python3 - "$work/templates/fs-gg-fable-game/SvgFoundation/Studio/Studio.fsproj" "$rendering_version" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); version=sys.argv[2]
text=p.read_text()
old='<FsGgSvgAuthoringVersion Condition="\'$(FsGgSvgAuthoringVersion)\' == \'\'">0.29.0</FsGgSvgAuthoringVersion>'
new=f'<FsGgSvgAuthoringVersion Condition="\'$(FsGgSvgAuthoringVersion)\' == \'\'">{version}</FsGgSvgAuthoringVersion>'
if text.count(old)!=1: raise SystemExit('studio candidate version seam drifted')
p.write_text(text.replace(old,new))
PY
template_version="0.11.0-svg-author.1"
dotnet pack "$work/FS.GG.Templates.csproj" -c Release -o "$output/feed" -p:Version="$template_version" >/dev/null
template_archive="$output/feed/FS.GG.Workspace.Template.$template_version.nupkg"

python3 - "$packet" "$template_archive" "$output/candidate-packet.json" "$rendering_revision" "$(git -C "$root" rev-parse HEAD)" <<'PY'
import hashlib,json,pathlib,sys,zipfile
source=pathlib.Path(sys.argv[1]); template=pathlib.Path(sys.argv[2]); destination=pathlib.Path(sys.argv[3])
rendering=json.loads(source.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
with zipfile.ZipFile(template) as archive:
    payload=hashlib.sha256(b''.join(archive.read(n) for n in sorted(archive.namelist()) if n.startswith('content/templates/fs-gg-fable-game/'))).hexdigest()
result={'schema':'fsgg.svg-authoring-template-candidate/v1','rendering':{'mergedRevision':sys.argv[4],'packetSha256':sha(source),'version':rendering['version'],'packages':rendering['packages'],'fableInterfaces':rendering['fableInterfaces'],'worker':rendering['worker'],'resources':rendering['resources'],'npmLocks':rendering['npmLocks']},'templates':{'sourceRevision':sys.argv[5],'package':{'file':template.name,'version':'0.11.0-svg-author.1','sha256':sha(template),'payloadSha256':payload}},'publicPins':{'templates':'0.11.0','rendering':'0.29.0'},'publication':False}
destination.write_text(json.dumps(result,indent=2)+'\n')
PY
mv "$output" "$final_output"
output=''
echo "SVG authoring candidate: staged exact Rendering archives and Templates candidate at $final_output"
