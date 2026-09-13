#!/usr/bin/env bash
set -euo pipefail
game_manifest="${1:?usage: $0 <game-manifest> <empty-output-directory>}"
final_output="${2:?usage: $0 <game-manifest> <empty-output-directory>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ! -e "$final_output" ]]
output="$final_output.staging.$$"; work=''
cleanup() { [[ -z "$work" ]] || rm -rf "$work"; [[ -z "${output:-}" ]] || rm -rf "$output"; }
trap cleanup EXIT
mkdir -p "$output/feed"
readarray -t values < <(python3 - "$game_manifest" "$output/feed" <<'PY'
import hashlib,json,pathlib,re,shutil,sys
path=pathlib.Path(sys.argv[1]).resolve(); feed=pathlib.Path(sys.argv[2]); data=json.loads(path.read_text())
if data.get('schema')!='fsgg.svg-replay.game-candidate/v1' or data.get('source',{}).get('repository')!='FS-GG/FS.GG.Game': raise SystemExit('invalid Game replay packet')
revision=data['source'].get('commit',''); package=path.parent/'packages'/data['package']['file']
if not re.fullmatch('[0-9a-f]{40}',revision) or hashlib.sha256(package.read_bytes()).hexdigest()!=data['package']['sha256']: raise SystemExit('Game replay identity mismatch')
shutil.copy2(package,feed/package.name); print(revision); print(data['version'])
PY
)
game_revision="${values[0]}"; game_version="${values[1]}"
work="$(mktemp -d "${TMPDIR:-/tmp}/svg-replay-template.XXXXXX")"
git -C "$root" archive HEAD | tar -x -C "$work"
python3 - "$work/templates/fs-gg-fable-game/SvgFoundation/Studio/Studio.fsproj" "$game_version" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text()
for old,new in [('>0.15.0</FsGgGameReplayVersion>',f'>{sys.argv[2]}</FsGgGameReplayVersion>'),('>false</FsGgSvgReplayCandidate>','>true</FsGgSvgReplayCandidate>')]:
    if text.count(old)!=1: raise SystemExit(f'replay seam drifted: {old}')
    text=text.replace(old,new)
p.write_text(text)
PY
template_version="0.12.0-svg-replay.1"
dotnet pack "$work/FS.GG.Templates.csproj" -c Release -o "$output/feed" -p:Version="$template_version" >/dev/null
template_archive="$output/feed/FS.GG.Workspace.Template.$template_version.nupkg"
python3 - "$game_manifest" "$template_archive" "$output/candidate-packet.json" "$game_revision" "$(git -C "$root" rev-parse HEAD)" <<'PY'
import hashlib,json,pathlib,sys,zipfile
g,t,d=map(pathlib.Path,sys.argv[1:4]); game_revision,templates_revision=sys.argv[4:6]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
with zipfile.ZipFile(t) as z: payload=hashlib.sha256(b''.join(z.read(n) for n in sorted(z.namelist()) if n.startswith('content/templates/fs-gg-fable-game/'))).hexdigest()
result={'schema':'fsgg.svg-replay.template-candidate/v1','game':{'mergedRevision':game_revision,'packetSha256':sha(g),**json.loads(g.read_text())},'templates':{'sourceRevision':templates_revision,'package':{'file':t.name,'version':'0.12.0-svg-replay.1','sha256':sha(t),'payloadSha256':payload}},'publicPins':{'templates':'0.12.0','rendering':'0.30.0','game':'0.15.0','audio':'0.6.0','sdd':'1.7.0'},'publication':False}
d.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
PY
mv "$output" "$final_output"; output=''
