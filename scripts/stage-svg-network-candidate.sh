#!/usr/bin/env bash
set -euo pipefail
game="${1:?usage: $0 <Game checkout> <Net checkout> <empty-output-directory>}"
net="${2:?usage: $0 <Game checkout> <Net checkout> <empty-output-directory>}"
final_output="${3:?usage: $0 <Game checkout> <Net checkout> <empty-output-directory>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ! -e "$final_output" ]]
game_revision="$(git -C "$game" rev-parse HEAD)"
net_revision="$(git -C "$net" rev-parse HEAD)"
templates_revision="$(git -C "$root" rev-parse HEAD)"
game_version="0.15.0-svg-network.1.${game_revision:0:8}"
net_version="0.5.0-svg-network.1.${net_revision:0:8}"
template_version="0.12.0-svg-network.1"
output="$final_output.staging.$$"
work="$(mktemp -d "${TMPDIR:-/tmp}/svg-network-template.XXXXXX")"
cleanup() { rm -rf "$work" "$output"; }
trap cleanup EXIT
mkdir -p "$output/feed"
dotnet pack "$game/src/Game.Core/FS.GG.Game.Core.fsproj" -c Release -o "$output/feed" -p:Version="$game_version" >/dev/null
dotnet pack "$net/src/FS.GG.Net.Core/FS.GG.Net.Core.fsproj" -c Release -o "$output/feed" -p:FsGgNetVersion="$net_version" >/dev/null
git -C "$root" archive HEAD | tar -x -C "$work"
dotnet pack "$work/FS.GG.Templates.csproj" -c Release -o "$output/feed" -p:Version="$template_version" >/dev/null
python3 - "$output" "$game_revision" "$net_revision" "$templates_revision" "$game_version" "$net_version" "$template_version" <<'PY'
import hashlib,json,pathlib,sys,zipfile
out=pathlib.Path(sys.argv[1]); grev,nrev,trev,gver,nver,tver=sys.argv[2:]
def identity(path):
    data=path.read_bytes(); return {'file':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
game=out/'feed'/f'FS.GG.Game.Core.{gver}.nupkg'
net=out/'feed'/f'FS.GG.Net.Core.{nver}.nupkg'
template=out/'feed'/f'FS.GG.Workspace.Template.{tver}.nupkg'
with zipfile.ZipFile(game) as archive:
    required=['api-surface/NetworkSession.fsi','api-surface/Replay.fsi']
    missing=[name for name in required if name not in archive.namelist()]
    if missing: raise SystemExit(f'missing Game network/replay interfaces: {missing}')
with zipfile.ZipFile(net) as archive:
    if 'api-surface/Delivery.fsi' not in archive.namelist(): raise SystemExit('missing Net delivery interface')
manifest={'schema':'fsgg.svg-network.candidate/v1','publication':False,
 'game':{'repository':'FS-GG/FS.GG.Game','commit':grev,'version':gver,'package':identity(game)},
 'net':{'repository':'FS-GG/FS.GG.Net','commit':nrev,'version':nver,'package':identity(net)},
 'templates':{'repository':'FS-GG/FS.GG.Templates','commit':trev,'version':tver,'package':identity(template)}}
(out/'candidate-packet.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
PY
mv "$output" "$final_output"
output=""
