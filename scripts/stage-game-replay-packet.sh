#!/usr/bin/env bash
set -euo pipefail
game="${1:?usage: $0 <Game checkout> <empty-output-directory> <candidate-version>}"
output="${2:?usage: $0 <Game checkout> <empty-output-directory> <candidate-version>}"
version="${3:?usage: $0 <Game checkout> <empty-output-directory> <candidate-version>}"
git -C "$game" rev-parse --is-inside-work-tree >/dev/null
[[ ! -e "$output" && "$version" =~ ^0\.15\.0-svg-replay\.1\.[0-9a-f]{8}(\.[0-9A-Za-z.-]+)?$ ]]
mkdir -p "$output/packages"
dotnet pack "$game/src/Game.Core/FS.GG.Game.Core.fsproj" -c Release -o "$output/packages" -p:Version="$version" >/dev/null
python3 - "$game" "$output" "$version" <<'PY'
import hashlib,json,pathlib,subprocess,sys,zipfile
repo=pathlib.Path(sys.argv[1]).resolve(); out=pathlib.Path(sys.argv[2]).resolve(); version=sys.argv[3]
revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
package=out/'packages'/f'FS.GG.Game.Core.{version}.nupkg'
def identity(value): return {'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
required=['fable/Replay.fsi','fable/Planning.fsi','fable/Rules.fsi','fable-compatibility/fixtures/v1/expected.bin']
with zipfile.ZipFile(package) as archive:
    missing=[name for name in required if name not in archive.namelist()]
    if missing: raise SystemExit(f'missing replay interfaces: {missing}')
    interfaces={name:identity(archive.read(name)) for name in required}
(out/'manifest.json').write_text(json.dumps({'schema':'fsgg.svg-replay.game-candidate/v1','source':{'repository':'FS-GG/FS.GG.Game','commit':revision},'version':version,'package':{'file':package.name,**identity(package.read_bytes())},'interfaces':interfaces},indent=2,sort_keys=True)+'\n')
PY
