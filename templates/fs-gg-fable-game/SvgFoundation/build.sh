#!/usr/bin/env bash
set -euo pipefail
foundation="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$foundation/.." && pwd)"
version="${FSGG_SVG_INPUT_VERSION:-0.32.1}"
export FsGgSvgInputVersion="$version"
scale_candidate="${FSGG_SVG_SCALE_CANDIDATE:-true}"
export FsGgSvgScaleCandidate="$scale_candidate"
wasm_example="${FSGG_WASM_POLICY_EXAMPLE:-${FsGgWasmPolicyExample:-false}}"
case "$wasm_example" in true|false) ;; *) echo 'WASM policy option must be true or false' >&2; exit 2 ;; esac
if [[ -n "${FSGG_WASM_POLICY_EXAMPLE:-}" && -n "${FsGgWasmPolicyExample:-}" && "$FSGG_WASM_POLICY_EXAMPLE" != "$FsGgWasmPolicyExample" ]]; then
  echo 'WASM policy option selections disagree' >&2; exit 2
fi
export FsGgWasmPolicyExample="$wasm_example" FSGG_WASM_POLICY_EXAMPLE="$wasm_example"
if [[ "$wasm_example" == true ]]; then
  [[ -f "$foundation/Examples/Wasm/WasmPolicyExample.fs" && -f "$foundation/Examples/Wasm/packages.lock.json" ]] || { echo 'WASM policy requires Complete source and qualified opt-in lock' >&2; exit 2; }
  [[ "${FsGgLegacyPreview:-false}" != true ]] || { echo 'WASM policy is unavailable for legacy preview' >&2; exit 2; }
  [[ -d "$foundation/obj/wasm-policy-guests" ]] || { echo 'Build the independently authored guest inputs first' >&2; exit 2; }
fi
restore_args=(dotnet restore "$foundation/SvgFoundation.fsproj" --locked-mode -p:FsGgSvgInputVersion="$version" -p:FsGgSvgScaleCandidate="$scale_candidate" -p:FsGgWasmPolicyExample="$wasm_example")
if [[ -n "${FSGG_SVG_CANDIDATE_FEED:-}" ]]; then
  config="$foundation/NuGet.candidate.generated.config"
  cat >"$config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$FSGG_SVG_CANDIDATE_FEED"/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
CONFIG
  restore_args+=(--configfile "$config")
fi
"${restore_args[@]}"
if [[ "$wasm_example" == true ]]; then
  python3 "$foundation/Examples/Wasm/materialize-assets.py" "$foundation"
fi
(cd "$workspace" && dotnet tool restore)
# Fable must never import stale enabled output after the selection changes.
rm -rf "$foundation/output"
(cd "$workspace" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache)
(cd "$workspace/Client" && npm ci)
(cd "$workspace" && ./Client/node_modules/.bin/vite build --config SvgFoundation/vite.config.js)
