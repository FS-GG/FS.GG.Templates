#!/usr/bin/env bash
set -euo pipefail
studio="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$studio/../.." && pwd)"
version="${FSGG_SVG_AUTHORING_VERSION:-0.29.0}"
export FsGgSvgAuthoringVersion="$version"
restore_args=(dotnet restore "$studio/Studio.fsproj" -p:FsGgSvgAuthoringVersion="$version")
if [[ -n "${FSGG_SVG_CANDIDATE_FEED:-}" ]]; then
  config="$studio/NuGet.candidate.generated.config"
  cat >"$config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$FSGG_SVG_CANDIDATE_FEED"/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
CONFIG
  restore_args+=(--configfile "$config")
fi
"${restore_args[@]}"
packages="$(python3 - "$studio/obj/project.assets.json" <<'PY'
import json,sys
folders=list(json.load(open(sys.argv[1]))['packageFolders'])
if len(folders)!=1: raise SystemExit('SVG studio restore must resolve through one package folder')
print(folders[0].rstrip('/'))
PY
)"
browser_package="$packages/fs.gg.ui.scene.svgbrowser/$version"
assets="$browser_package/contentFiles/any/any"
[[ -d "$assets" ]] || { echo "SVG studio: restored SvgBrowser content is missing: $assets" >&2; exit 1; }
mkdir -p "$studio/vendor"
python3 - "$assets" "$studio/vendor" <<'PY'
import pathlib,sys
source,destination=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2])
paths=('svg-geometry-worker.js','package.json','package-lock.json','font-resource-manifest.json','noto-sans-latin-400-normal.woff2.base64')
for name in paths:
    (destination/name).write_bytes((source/name).read_bytes())
PY
cp "$browser_package/OFL-Noto-Sans.txt" "$browser_package/THIRD-PARTY-NOTICES.md" "$studio/vendor/"
(cd "$studio/vendor" && npm ci)
(cd "$workspace" && dotnet fable SvgFoundation/Studio/Studio.fsproj --outDir SvgFoundation/Studio/output --noCache)
(cd "$workspace/Client" && npm ci)
(cd "$workspace" && ./Client/node_modules/.bin/vite build --config SvgFoundation/Studio/vite.config.js)
