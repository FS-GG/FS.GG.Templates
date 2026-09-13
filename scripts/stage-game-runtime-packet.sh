#!/usr/bin/env bash
set -euo pipefail

game="${1:?usage: $0 <Game checkout> <empty-output-directory> <candidate-version>}"
output="${2:?usage: $0 <Game checkout> <empty-output-directory> <candidate-version>}"
version="${3:?usage: $0 <Game checkout> <empty-output-directory> <candidate-version>}"
git -C "$game" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Game checkout is missing: $game" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "Game packet output already exists: $output" >&2; exit 2; }
[[ "$version" =~ ^0\.15\.0-svg-runtime\.1\.[0-9a-f]{8}(\.[0-9A-Za-z.-]+)?$ ]] || {
  echo "Game candidate version is outside the SVG-RUNTIME-01 family: $version" >&2
  exit 2
}

mkdir -p "$output/packages"
dotnet pack "$game/src/Game.Core/FS.GG.Game.Core.fsproj" -c Release -o "$output/packages" -p:Version="$version" >/dev/null

python3 - "$game" "$output" "$version" <<'PY'
import hashlib,json,pathlib,re,subprocess,sys,zipfile
game=pathlib.Path(sys.argv[1]).resolve(); output=pathlib.Path(sys.argv[2]).resolve(); version=sys.argv[3]
revision=subprocess.check_output(['git','-C',str(game),'rev-parse','HEAD'],text=True).strip()
if not re.fullmatch(r'[0-9a-f]{40}',revision): raise SystemExit('Game revision is invalid')
package=output/'packages'/f'FS.GG.Game.Core.{version}.nupkg'
if not package.is_file(): raise SystemExit('Game.Core package is missing')
def identity(payload): return {'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
required=['fable/SessionContract.fsi','fable/SessionRuntime.fsi','fable/Geometry.fsi','fable/SpatialGrid.fsi','fable/Resolution.fsi','fable/Kinematics.fsi','fable-compatibility/compatibility-profile.v1.json','fable-compatibility/fixtures/v1/expected.bin']
with zipfile.ZipFile(package) as archive:
    missing=[name for name in required if name not in archive.namelist()]
    if missing: raise SystemExit(f'Game.Core candidate is missing: {missing}')
    interfaces={name:identity(archive.read(name)) for name in required}
manifest={'schema':'fsgg.svg-runtime.game-candidate/v1','source':{'repository':'FS-GG/FS.GG.Game','commit':revision},'version':version,'package':{'file':package.name,**identity(package.read_bytes())},'interfaces':interfaces}
(output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
PY

echo "Game runtime packet: staged $version from $(git -C "$game" rev-parse HEAD)"
