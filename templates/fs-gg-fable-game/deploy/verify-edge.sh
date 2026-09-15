#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-${SVG_RELEASE_VERSION:-workspace-v1}}"
base="${GAME_EDGE_URL:-http://localhost:${GAME_HTTP_PORT:-8080}}"
release="$root/artifacts/releases/$version"

[[ -d "$release" ]] || { echo "edge verification: missing release $release" >&2; exit 1; }
(cd "$release" && sha256sum -c --quiet SHA256SUMS)

for _ in {1..80}; do
  if curl --fail --silent --show-error "$base/healthz" >/dev/null 2>&1; then break; fi
  sleep .25
done
curl --fail --silent --show-error "$base/healthz" | grep -F '"status":"ok"' >/dev/null
[[ "$(curl --fail --silent --show-error "$base/deployment/VERSION")" == "$version" ]]
cmp -s <(curl --fail --silent --show-error "$base/deployment/SHA256SUMS") "$release/SHA256SUMS"

expected_player="$(awk '$2 == "./static-player/index.html" { print $1 }' "$release/SHA256SUMS")"
[[ -n "$expected_player" ]]
observed_player="$(curl --fail --silent --show-error "$base/" | sha256sum | cut -d' ' -f1)"
[[ "$observed_player" == "$expected_player" ]]

if [[ -f "$release/static-studio/index.html" ]]; then
  expected_studio="$(awk '$2 == "./static-studio/index.html" { print $1 }' "$release/SHA256SUMS")"
  observed_studio="$(curl --fail --silent --show-error "$base/studio/" | sha256sum | cut -d' ' -f1)"
  [[ "$observed_studio" == "$expected_studio" ]]
fi

GAME_EDGE_URL="$base" node "$root/deploy/verify-edge.mjs"
echo "edge verification passed: version=$version url=$base hashes=matched api=passed websocket=passed"
