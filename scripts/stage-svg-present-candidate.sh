#!/usr/bin/env bash
set -euo pipefail
rendering_manifest="${1:?usage: $0 <rendering-manifest> <game-manifest> <audio-manifest> <empty-output-directory>}"
game_manifest="${2:?usage: $0 <rendering-manifest> <game-manifest> <audio-manifest> <empty-output-directory>}"
audio_manifest="${3:?usage: $0 <rendering-manifest> <game-manifest> <audio-manifest> <empty-output-directory>}"
final_output="${4:?usage: $0 <rendering-manifest> <game-manifest> <audio-manifest> <empty-output-directory>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ! -e "$final_output" ]]
output="$final_output.staging.$$"; work=''
cleanup() { [[ -z "$work" ]] || rm -rf "$work"; [[ -z "${output:-}" ]] || rm -rf "$output"; }
trap cleanup EXIT
mkdir -p "$output/feed"

readarray -t values < <(python3 - "$rendering_manifest" "$game_manifest" "$audio_manifest" "$output/feed" <<'PY'
import hashlib,json,pathlib,re,shutil,sys
paths=[pathlib.Path(v).resolve() for v in sys.argv[1:4]]; feed=pathlib.Path(sys.argv[4])
schemas=['fsgg.svg-present.rendering-candidate/v1','fsgg.svg-present.game-candidate/v1','fsgg.svg-present.audio-candidate/v1']
repos=['FS-GG/FS.GG.Rendering','FS-GG/FS.GG.Game','FS-GG/FS.GG.Audio']; versions=[]; revisions=[]
for path,schema,repo in zip(paths,schemas,repos):
    data=json.loads(path.read_text())
    if data.get('schema')!=schema or data.get('source',{}).get('repository')!=repo: raise SystemExit(f'invalid packet: {path}')
    revision=data['source'].get('commit','')
    if not re.fullmatch('[0-9a-f]{40}',revision): raise SystemExit(f'invalid revision: {path}')
    rows=data.get('packages') or [data.get('package')]
    for row in rows:
        package=path.parent/'packages'/row['file']
        if hashlib.sha256(package.read_bytes()).hexdigest()!=row['sha256']: raise SystemExit(f'package digest mismatch: {package}')
        shutil.copy2(package,feed/package.name)
    versions.append(data['version']); revisions.append(revision)
for value in revisions+versions: print(value)
PY
)
rendering_revision="${values[0]}"; game_revision="${values[1]}"; audio_revision="${values[2]}"
rendering_version="${values[3]}"; game_version="${values[4]}"; audio_version="${values[5]}"
work="$(mktemp -d "${TMPDIR:-/tmp}/svg-present-template.XXXXXX")"
git -C "$root" archive HEAD | tar -x -C "$work"
python3 - "$work/templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj" "$work/templates/fs-gg-fable-game/SvgFoundation/Studio/Studio.fsproj" "$rendering_version" "$game_version" "$audio_version" <<'PY'
from pathlib import Path
import sys
player=Path(sys.argv[1]); studio=Path(sys.argv[2]); rendering,game,audio=sys.argv[3:]
def replace(path,old,new):
    text=path.read_text()
    if text.count(old)!=1: raise SystemExit(f'candidate seam drifted in {path}: {old}')
    path.write_text(text.replace(old,new))
replace(player,'>0.29.0</FsGgSvgInputVersion>',f'>{rendering}</FsGgSvgInputVersion>')
replace(player,'>0.14.0</FsGgGameRuntimeVersion>',f'>{game}</FsGgGameRuntimeVersion>')
replace(player,'>0.5.0</FsGgAudioPresentVersion>',f'>{audio}</FsGgAudioPresentVersion>')
replace(studio,'>0.29.0</FsGgSvgAuthoringVersion>',f'>{rendering}</FsGgSvgAuthoringVersion>')
for path in (player,studio): replace(path,'>false</FsGgSvgInputCandidate>','>true</FsGgSvgInputCandidate>')
replace(player,'>false</FsGgSvgRuntimeCandidate>','>true</FsGgSvgRuntimeCandidate>')
replace(player,'>false</FsGgSvgPresentCandidate>','>true</FsGgSvgPresentCandidate>')
PY
template_version="0.12.0-svg-present.1"
dotnet pack "$work/FS.GG.Templates.csproj" -c Release -o "$output/feed" -p:Version="$template_version" >/dev/null
template_archive="$output/feed/FS.GG.Workspace.Template.$template_version.nupkg"
python3 - "$rendering_manifest" "$game_manifest" "$audio_manifest" "$template_archive" "$output/candidate-packet.json" "$rendering_revision" "$game_revision" "$audio_revision" "$(git -C "$root" rev-parse HEAD)" <<'PY'
import hashlib,json,pathlib,sys,zipfile
r,g,a,t,d=map(pathlib.Path,sys.argv[1:6]); revisions=sys.argv[6:10]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
with zipfile.ZipFile(t) as z: payload=hashlib.sha256(b''.join(z.read(n) for n in sorted(z.namelist()) if n.startswith('content/templates/fs-gg-fable-game/'))).hexdigest()
result={'schema':'fsgg.svg-present.template-candidate/v1','rendering':{'mergedRevision':revisions[0],'packetSha256':sha(r),**json.loads(r.read_text())},'game':{'mergedRevision':revisions[1],'packetSha256':sha(g),**json.loads(g.read_text())},'audio':{'mergedRevision':revisions[2],'packetSha256':sha(a),**json.loads(a.read_text())},'templates':{'sourceRevision':revisions[3],'package':{'file':t.name,'version':'0.12.0-svg-present.1','sha256':sha(t),'payloadSha256':payload}},'publicPins':{'templates':'0.11.0','rendering':'0.29.0','game':'0.14.0','audio':'0.5.0'},'publication':False}
d.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
PY
mv "$output" "$final_output"; output=''
echo "SVG presentation candidate: staged exact producer packages and Templates candidate at $final_output"
