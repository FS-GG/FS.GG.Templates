#!/usr/bin/env bash
set -euo pipefail
foundation="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$foundation/.." && pwd)"
version="${FSGG_SVG_INPUT_VERSION:-0.30.0}"
export FsGgSvgInputVersion="$version"
restore_args=(dotnet restore "$foundation/SvgFoundation.fsproj" -p:FsGgSvgInputVersion="$version")
if [[ -n "${FSGG_SVG_CANDIDATE_FEED:-}" ]]; then
  config="$foundation/NuGet.candidate.generated.config"
  cat >"$config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$FSGG_SVG_CANDIDATE_FEED"/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
CONFIG
  restore_args+=(--configfile "$config")
fi
"${restore_args[@]}"
(cd "$workspace" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache)
(cd "$workspace/Client" && npm ci)
(cd "$workspace" && ./Client/node_modules/.bin/vite build --config SvgFoundation/vite.config.js)
