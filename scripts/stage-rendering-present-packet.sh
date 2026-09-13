#!/usr/bin/env bash
set -euo pipefail
rendering="${1:?usage: $0 <Rendering checkout> <empty-output-directory> <candidate-version>}"
output="${2:?usage: $0 <Rendering checkout> <empty-output-directory> <candidate-version>}"
version="${3:?usage: $0 <Rendering checkout> <empty-output-directory> <candidate-version>}"
git -C "$rendering" rev-parse --is-inside-work-tree >/dev/null
[[ ! -e "$output" && "$version" =~ ^0\.30\.0-svg-present\.1\.[0-9a-f]{8}(\.[0-9A-Za-z.-]+)?$ ]]
mkdir -p "$output/packages"
for project in src/KeyboardInput/KeyboardInput.fsproj src/Scene/Scene.fsproj src/Scene.SvgBrowser/Scene.SvgBrowser.fsproj; do
  dotnet pack "$rendering/$project" -c Release -o "$output/packages" -p:Version="$version" >/dev/null
done
python3 - "$rendering" "$output" "$version" <<'PY'
import hashlib,json,pathlib,re,subprocess,sys,zipfile
repo=pathlib.Path(sys.argv[1]).resolve(); out=pathlib.Path(sys.argv[2]).resolve(); version=sys.argv[3]
revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
def identity(value): return {'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
ids=['FS.GG.UI.KeyboardInput','FS.GG.UI.Scene','FS.GG.UI.Scene.SvgBrowser']; packages=[]; interfaces={}
required={'FS.GG.UI.Scene':['fable/Animation.fsi'],'FS.GG.UI.Scene.SvgBrowser':['fable/SvgAnimationHost.fsi','fable/BrowserPersistence.fsi']}
for package_id in ids:
    path=out/'packages'/f'{package_id}.{version}.nupkg'; packages.append({'file':path.name,**identity(path.read_bytes())})
    with zipfile.ZipFile(path) as archive:
        for member in required.get(package_id,[]):
            if member not in archive.namelist(): raise SystemExit(f'missing presentation interface: {package_id}:{member}')
            interfaces[f'{path.name}:{member}']=identity(archive.read(member))
(out/'manifest.json').write_text(json.dumps({'schema':'fsgg.svg-present.rendering-candidate/v1','source':{'repository':'FS-GG/FS.GG.Rendering','commit':revision},'version':version,'packages':packages,'interfaces':interfaces},indent=2,sort_keys=True)+'\n')
PY
