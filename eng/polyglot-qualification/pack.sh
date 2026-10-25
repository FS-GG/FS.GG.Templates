#!/usr/bin/env bash
# Pack the release archive exactly as .github/workflows/release.yml does (locked restore, CI build).
# usage: pack.sh <carrier-root> <output-directory>   (run from the Templates checkout to be packed)
set -euo pipefail
ROOT="${1:?carrier root}"; OUT="${2:?absent output directory}"
[[ ! -e "$OUT" ]] || { echo 'output directory must be absent' >&2; exit 3; }
CHECKOUT="$(git rev-parse --show-toplevel)"
export FSGG_PYTHON_COORDINATION_ROOT="$ROOT/coord-fixture" DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
cd "$CHECKOUT"
taskset -c 0-3 dotnet restore FS.GG.Templates.csproj --locked-mode
taskset -c 0-3 dotnet pack FS.GG.Templates.csproj -c Release --no-restore -p:ContinuousIntegrationBuild=true -o "$OUT"
(cd "$OUT" && sha256sum -- *.nupkg | tee SHA256SUMS)
git -C "$CHECKOUT" rev-parse HEAD > "$OUT/SOURCE_COMMIT"
