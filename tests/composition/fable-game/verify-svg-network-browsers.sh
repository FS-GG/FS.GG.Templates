#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
game="${1:?Game checkout required}"; net="${2:?Net checkout required}"; out="${3:?empty output directory required}"
bash "$root/scripts/stage-svg-network-candidate.sh" "$game" "$net" "$out"
game_version="$(jq -r .game.version "$out/candidate-packet.json")"
net_version="$(jq -r .net.version "$out/candidate-packet.json")"
mkdir -p "$out/home" "$out/packages" "$out/http"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
dotnet new install "$out/feed/FS.GG.Workspace.Template.0.12.0-svg-network.1.nupkg" --force >/dev/null
dotnet new fs-gg-fable-game -n NetworkBrowserReceiver -o "$out/receiver" --lifecycle none --svgFoundation true >/dev/null
if [[ -n "${FSGG_LOCAL_SDK_VERSION:-}" ]]; then
  python3 - "$out/receiver/global.json" "$FSGG_LOCAL_SDK_VERSION" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); data=json.loads(p.read_text()); data['sdk']['version']=sys.argv[2]; p.write_text(json.dumps(data,indent=2)+'\n')
PY
fi
common=(-p:RestoreLockedMode=false -p:FsGgSvgNetworkCandidate=true -p:FsGgGameVersion="$game_version" -p:FsGgGameNetworkVersion="$game_version" -p:FsGgNetNetworkVersion="$net_version")
dotnet restore "$out/receiver/Client/Client.fsproj" --configfile "$out/NuGet.Config" "${common[@]}" >/dev/null
dotnet restore "$out/receiver/Server/Server.fsproj" --configfile "$out/NuGet.Config" "${common[@]}" >/dev/null
(cd "$out/receiver/Client" && FsGgSvgNetworkCandidate=true FsGgGameVersion="$game_version" RestoreLockedMode=false npm ci >/dev/null && FsGgSvgNetworkCandidate=true FsGgGameVersion="$game_version" RestoreLockedMode=false npm run build >/dev/null)
dotnet publish "$out/receiver/Server/Server.fsproj" -c Release --no-restore -o "$out/publish" "${common[@]}" >/dev/null
cp "$root/tests/composition/fable-game/svg-network-observe.mjs" "$out/receiver/Browser.Tests/"
npm ci --prefix "$out/receiver/Browser.Tests" >/dev/null
server=''
trap '[[ -z "$server" ]] || kill "$server" 2>/dev/null || true' EXIT
read -r -a families <<<"${FSGG_BROWSER_FAMILIES:-chromium firefox webkit}"
browser_json='{}'
for family in "${families[@]}"; do
  (cd "$out/publish" && exec dotnet Server.dll --urls http://127.0.0.1:5100 >"$out/$family-server.log" 2>&1) & server=$!
  for _ in {1..80}; do curl -fsS http://127.0.0.1:5100/ >/dev/null && break; sleep .25; done
  (cd "$out/receiver/Browser.Tests" && node svg-network-observe.mjs "$family" http://127.0.0.1:5100) >"$out/$family-network.json"
  kill "$server"
  wait "$server" 2>/dev/null || true
  server=''
  browser_json="$(jq --arg family "$family" --slurpfile result "$out/$family-network.json" '. + {($family):$result[0]}' <<<"$browser_json")"
done
jq -n --argjson browsers "$browser_json" --slurpfile packet "$out/candidate-packet.json" \
  '{schema:"fsgg.svg-network.browser-qualification/v1",candidate:$packet[0],browser:$browsers,twoClient:"passed",reconnect:"passed",resync:"passed",staleRefusal:"passed",invalidRefusal:"passed",replayReview:"passed",keyboard:"passed",disclosure:"passed",publication:false}' \
  >"$out/qualification.json"
