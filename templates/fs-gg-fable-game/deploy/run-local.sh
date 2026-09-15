#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$root/deploy/container-engine.sh"
select_compose_engine
version="${1:-${SVG_RELEASE_VERSION:-workspace-v1}}"
export SVG_RELEASE_VERSION="$version"
export GAME_SITE_ADDRESS="http://localhost:8080"
export GAME_HTTP_PORT="${GAME_HTTP_PORT:-8080}"

compose=("${COMPOSE_ENGINE[@]}" --project-directory "$root" -f "$root/deploy/compose.yaml" -f "$root/deploy/compose.local.yaml")
cleanup() {
  if [[ "${KEEP_EDGE_RUNNING:-false}" != true ]]; then "${compose[@]}" down --remove-orphans; fi
}
trap cleanup EXIT

(cd "$root/artifacts/releases/$version" && sha256sum -c --quiet SHA256SUMS)
"${compose[@]}" config --quiet
"${compose[@]}" up --detach --build --remove-orphans
GAME_EDGE_URL="http://localhost:$GAME_HTTP_PORT" "$root/deploy/verify-edge.sh" "$version"

if [[ "${KEEP_EDGE_RUNNING:-false}" == true ]]; then
  echo "local edge remains available at http://localhost:$GAME_HTTP_PORT"
fi
