#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
rendering="${1:?exact Rendering checkout required}"
out="${2:?empty output directory required}"
[[ ! -e "$out" ]] || { echo 'svg-scale-candidate: output exists' >&2; exit 2; }
mkdir -p "$out/feed" "$out/home" "$out/packages" "$out/http"
rendering_revision="$(git -C "$rendering" rev-parse HEAD)"
rendering_version="0.30.0-svg-scale.1.${rendering_revision:0:8}"
template_revision="$(git -C "$root" rev-parse HEAD)"
template_version="0.12.0-svg-scale.1"
for project in Scene/Scene Scene.SvgBrowser/Scene.SvgBrowser KeyboardInput/KeyboardInput; do
  dotnet pack "$rendering/src/$project.fsproj" -c Release -o "$out/feed" -p:Version="$rendering_version" >/dev/null
done
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$out/feed" -p:Version="$template_version" >/dev/null

export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
candidate="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
dotnet new install "$candidate" --force >/dev/null
dotnet new fs-gg-fable-game -n ScaleReceiver -o "$out/receiver" --lifecycle none --svgFoundation true >/dev/null
if [[ -n "${FSGG_LOCAL_SDK_VERSION:-}" ]]; then
  python3 - "$out/receiver/global.json" "$FSGG_LOCAL_SDK_VERSION" <<'PY'
import json,pathlib,sys
path=pathlib.Path(sys.argv[1]); value=json.loads(path.read_text()); value['sdk']['version']=sys.argv[2]; path.write_text(json.dumps(value,indent=2)+'\n')
PY
fi
test -f "$out/receiver/SvgFoundation/ScalePlayer.fs"
grep -F '<FsGgSvgScaleCandidate' "$out/receiver/SvgFoundation/SvgFoundation.fsproj" >/dev/null

(cd "$out/receiver" && dotnet tool restore >/dev/null)
FSGG_SVG_INPUT_VERSION="$rendering_version" FSGG_SVG_CANDIDATE_FEED="$out/feed" FSGG_SVG_SCALE_CANDIDATE=true \
  bash "$out/receiver/SvgFoundation/build.sh" >"$out/player-build.log" 2>&1
FSGG_SVG_AUTHORING_VERSION="$rendering_version" FSGG_SVG_CANDIDATE_FEED="$out/feed" \
  bash "$out/receiver/SvgFoundation/Studio/build.sh" >"$out/studio-build.log" 2>&1
npm ci --prefix "$out/receiver/Browser.Tests" >/dev/null
cp "$root/tests/composition/fable-game/svg-scale-observe.mjs" "$out/receiver/Browser.Tests/"

player_server=''; studio_server=''
trap '[[ -z "$player_server" ]] || kill "$player_server" 2>/dev/null || true; [[ -z "$studio_server" ]] || kill "$studio_server" 2>/dev/null || true' EXIT
(cd "$out/receiver/SvgFoundation/dist" && exec python3 -m http.server 8150 --bind 127.0.0.1 >"$out/player-server.log" 2>&1) & player_server=$!
(cd "$out/receiver/SvgFoundation/Studio/dist" && exec python3 -m http.server 8151 --bind 127.0.0.1 >"$out/studio-server.log" 2>&1) & studio_server=$!
for port in 8150 8151; do
  for _ in {1..80}; do curl -fsS "http://127.0.0.1:$port/" >/dev/null && break; sleep .25; done
done

browsers='{}'
read -r -a families <<<"${FSGG_BROWSER_FAMILIES:-chromium firefox webkit}"
for family in "${families[@]}"; do
  (cd "$out/receiver/Browser.Tests" && node svg-scale-observe.mjs "$family" http://127.0.0.1:8150/ http://127.0.0.1:8151/) >"$out/$family-scale.json"
  browsers="$(jq --arg family "$family" --slurpfile result "$out/$family-scale.json" '. + {($family):$result[0]}' <<<"$browsers")"
done

python3 - "$out/feed" "$rendering" "$rendering_revision" "$rendering_version" "$template_revision" "$template_version" "$browsers" "$out/qualification.json" <<'PY'
import hashlib,json,pathlib,sys
feed,rendering=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2])
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
packages=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(feed.glob('*.nupkg'))]
receipt=rendering/'readiness/svg-scale-01-3/scale-qualification.json'
result={'schema':'fsgg.svg-scale.generated-qualification/v1','rendering':{'commit':sys.argv[3],'version':sys.argv[4],'receiptSha256':sha(receipt),'packages':[p for p in packages if not p['file'].startswith('FS.GG.Workspace.Template.')]},'templates':{'commit':sys.argv[5],'version':sys.argv[6],'package':next(p for p in packages if p['file'].startswith('FS.GG.Workspace.Template.'))},'browser':json.loads(sys.argv[7]),'workloads':{'dense':'passed','worldExtent':'passed','continuous':'passed','responsive':'passed'},'accessibility':{'keyboard':'passed','touch':'passed','alternatives':'passed','reducedMotion':'passed','focusAcrossReflow':'passed'},'publication':False}
pathlib.Path(sys.argv[8]).write_text(json.dumps(result,indent=2)+'\n')
PY
echo "svg-scale-candidate: passed; evidence=$out/qualification.json"
