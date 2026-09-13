#!/usr/bin/env bash
set -euo pipefail
audio="${1:?usage: $0 <Audio checkout> <empty-output-directory> <candidate-version>}"
output="${2:?usage: $0 <Audio checkout> <empty-output-directory> <candidate-version>}"
version="${3:?usage: $0 <Audio checkout> <empty-output-directory> <candidate-version>}"
git -C "$audio" rev-parse --is-inside-work-tree >/dev/null
[[ ! -e "$output" && "$version" =~ ^0\.6\.0-svg-present\.1\.[0-9a-f]{8}(\.[0-9A-Za-z.-]+)?$ ]]
mkdir -p "$output/packages"
for project in src/FS.GG.Audio.Core/FS.GG.Audio.Core.fsproj src/FS.GG.Audio.WebBrowser/FS.GG.Audio.WebBrowser.fsproj; do
  dotnet pack "$audio/$project" -c Release -o "$output/packages" -p:Version="$version" >/dev/null
done
python3 - "$audio" "$output" "$version" <<'PY'
import hashlib,json,pathlib,subprocess,sys,zipfile
repo=pathlib.Path(sys.argv[1]).resolve(); out=pathlib.Path(sys.argv[2]).resolve(); version=sys.argv[3]
revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
def identity(value): return {'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
packages=[]; interfaces={}
for package_id,member in [('FS.GG.Audio.Core','fable/Audio.fsi'),('FS.GG.Audio.WebBrowser','fable/WebAudio.fsi')]:
    path=out/'packages'/f'{package_id}.{version}.nupkg'; packages.append({'file':path.name,**identity(path.read_bytes())})
    with zipfile.ZipFile(path) as archive:
        if member not in archive.namelist(): raise SystemExit(f'missing audio interface: {member}')
        interfaces[f'{path.name}:{member}']=identity(archive.read(member))
(out/'manifest.json').write_text(json.dumps({'schema':'fsgg.svg-present.audio-candidate/v1','source':{'repository':'FS-GG/FS.GG.Audio','commit':revision},'version':version,'packages':packages,'interfaces':interfaces},indent=2,sort_keys=True)+'\n')
PY
