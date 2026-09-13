#!/usr/bin/env bash
set -euo pipefail

rendering="${1:?usage: $0 <Rendering checkout> <empty-output-directory> <candidate-version>}"
output="${2:?usage: $0 <Rendering checkout> <empty-output-directory> <candidate-version>}"
version="${3:?usage: $0 <Rendering checkout> <empty-output-directory> <candidate-version>}"
git -C "$rendering" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Rendering checkout is missing: $rendering" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "Rendering packet output already exists: $output" >&2; exit 2; }
[[ "$version" =~ ^0\.30\.0-svg-runtime\.1\.[0-9a-f]{8}(\.[0-9A-Za-z.-]+)?$ ]] || {
  echo "Rendering candidate version is outside the SVG-RUNTIME-01 family: $version" >&2
  exit 2
}

mkdir -p "$output/packages"
for project in \
  src/KeyboardInput/KeyboardInput.fsproj \
  src/Scene/Scene.fsproj \
  src/Scene.SvgBrowser/Scene.SvgBrowser.fsproj; do
  dotnet pack "$rendering/$project" -c Release -o "$output/packages" -p:Version="$version" >/dev/null
done

python3 - "$rendering" "$output" "$version" <<'PY'
import hashlib,json,pathlib,re,subprocess,sys,zipfile

rendering=pathlib.Path(sys.argv[1]).resolve()
output=pathlib.Path(sys.argv[2]).resolve()
version=sys.argv[3]
revision=subprocess.check_output(['git','-C',str(rendering),'rev-parse','HEAD'],text=True).strip()
if not re.fullmatch(r'[0-9a-f]{40}',revision): raise SystemExit('Rendering revision is invalid')

def identity(payload):
    return {'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}

ids=['FS.GG.UI.KeyboardInput','FS.GG.UI.Scene','FS.GG.UI.Scene.SvgBrowser']
packages=[]; archives={}
for package_id in ids:
    path=output/'packages'/f'{package_id}.{version}.nupkg'
    if not path.is_file(): raise SystemExit(f'expected package is missing: {path.name}')
    packages.append({'file':path.name,**identity(path.read_bytes())})
    archives[package_id]=path

interfaces={}
for path in archives.values():
    with zipfile.ZipFile(path) as archive:
        for name in sorted(n for n in archive.namelist() if n.startswith('fable/') and n.endswith('.fsi')):
            interfaces[f'{path.name}:{name}']=identity(archive.read(name))
required={
 'FS.GG.UI.KeyboardInput':['fable/CommandInput.fsi','fable/CommandResolver.fsi'],
 'FS.GG.UI.Scene':['fable/SvgWorkspace.fsi'],
 'FS.GG.UI.Scene.SvgBrowser':['fable/SvgInputHost.fsi','fable/SvgSessionHost.fsi']}
for package_id,members in required.items():
    archive=archives[package_id]
    with zipfile.ZipFile(archive) as package:
        for member in members:
            if member not in package.namelist(): raise SystemExit(f'missing required Fable interface: {package_id}:{member}')

browser=archives['FS.GG.UI.Scene.SvgBrowser']
resource_names=[
    'OFL-Noto-Sans.txt','THIRD-PARTY-NOTICES.md',
    'contentFiles/any/any/font-resource-manifest.json',
    'contentFiles/any/any/noto-sans-latin-400-normal.woff2.base64',
    'contentFiles/any/any/package-lock.json','contentFiles/any/any/package.json']
with zipfile.ZipFile(browser) as archive:
    resources={name:{'archive':browser.name,**identity(archive.read(name))} for name in resource_names}
    worker_name='contentFiles/any/any/svg-geometry-worker.js'
    worker={'archive':browser.name,'path':worker_name,**identity(archive.read(worker_name))}

manifest={
    'schema':'fsgg.svg-runtime.rendering-candidate/v1',
    'source':{'repository':'FS-GG/FS.GG.Rendering','commit':revision},
    'version':version,'packages':packages,'fableInterfaces':interfaces,'worker':worker,
    'resources':resources,
    'npmLocks':{
        'src/Scene.SvgBrowser/package-lock.json':resources['contentFiles/any/any/package-lock.json']['sha256']
    },
    'modelEvidence':{
        name:identity((rendering/name).read_bytes()) for name in [
            'models/input-command/input-command.md',
            'readiness/svg-input-01-2/typed-authority.json',
            'readiness/svg-input-01-2/quint/inputCommand.qnt',
            'readiness/svg-input-01-2/quint/receipt.json']
    }
}
(output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
PY

echo "Rendering runtime packet: staged $version from $(git -C "$rendering" rev-parse HEAD)"
