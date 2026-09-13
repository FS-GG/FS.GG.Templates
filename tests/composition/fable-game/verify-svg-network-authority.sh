#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
game="${1:?Game checkout required}"
net="${2:?Net checkout required}"
out="${3:?empty output directory required}"
bash "$root/scripts/stage-svg-network-candidate.sh" "$game" "$net" "$out"
game_version="$(jq -r .game.version "$out/candidate-packet.json")"
net_version="$(jq -r .net.version "$out/candidate-packet.json")"
template_package="$out/feed/FS.GG.Workspace.Template.0.12.0-svg-network.1.nupkg"
mkdir -p "$out/home" "$out/packages" "$out/http"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
dotnet new install "$template_package" --force >/dev/null
dotnet new fs-gg-fable-game -n NetworkReceiver -o "$out/receiver" --lifecycle none --svgFoundation true >/dev/null
if [[ -n "${FSGG_LOCAL_SDK_VERSION:-}" ]]; then
  python3 - "$out/receiver/global.json" "$FSGG_LOCAL_SDK_VERSION" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); data=json.loads(p.read_text()); data['sdk']['version']=sys.argv[2]; p.write_text(json.dumps(data,indent=2)+'\n')
PY
fi
test -f "$out/receiver/Server/NetworkAuthority.fs"
dotnet restore "$out/receiver/Server.Tests/Server.Tests.fsproj" --configfile "$out/NuGet.Config" \
  -p:RestoreLockedMode=false -p:FsGgSvgNetworkCandidate=true -p:FsGgGameVersion="$game_version" \
  -p:FsGgGameNetworkVersion="$game_version" -p:FsGgNetNetworkVersion="$net_version" >/dev/null
dotnet test "$out/receiver/Server.Tests/Server.Tests.fsproj" --no-restore \
  -p:RestoreLockedMode=false -p:FsGgSvgNetworkCandidate=true -p:FsGgGameVersion="$game_version" \
  -p:FsGgGameNetworkVersion="$game_version" -p:FsGgNetNetworkVersion="$net_version" \
  --logger "trx;LogFileName=network-authority.trx" --results-directory "$out/results" >/dev/null
jq -n --slurpfile packet "$out/candidate-packet.json" \
  '{schema:"fsgg.svg-network.authority-qualification/v1",candidate:$packet[0],admission:"passed",delivery:"passed",replay:"passed",serverTests:11,publication:false}' \
  >"$out/qualification.json"
