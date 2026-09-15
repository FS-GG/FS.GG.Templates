#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-${SVG_RELEASE_VERSION:-workspace-v1}}"
base="${GAME_EDGE_URL:-http://localhost:${GAME_HTTP_PORT:-8080}}"
release="$root/artifacts/releases/$version"
expected_manifest_sha="${EXPECTED_RELEASE_MANIFEST_SHA:-}"

if [[ -n "$expected_manifest_sha" ]]; then
  [[ "$expected_manifest_sha" =~ ^[0-9a-f]{64}$ ]] || {
    echo "edge verification: invalid expected release manifest SHA-256" >&2; exit 1;
  }
else
  [[ -d "$release" ]] || { echo "edge verification: missing release $release" >&2; exit 1; }
  (cd "$release" && sha256sum -c --quiet SHA256SUMS)
fi

for _ in {1..80}; do
  if curl --fail --silent --show-error "$base/healthz" >/dev/null 2>&1; then break; fi
  sleep .25
done
curl --fail --silent --show-error "$base/healthz" | grep -F '"status":"ok"' >/dev/null
[[ "$(curl --fail --silent --show-error "$base/deployment/VERSION")" == "$version" ]]
served_manifest="$(mktemp)"
trap 'rm -f "$served_manifest"' EXIT
curl --fail --silent --show-error "$base/deployment/SHA256SUMS" >"$served_manifest"
if [[ -n "$expected_manifest_sha" ]]; then
  [[ "$(sha256sum "$served_manifest" | cut -d' ' -f1)" == "$expected_manifest_sha" ]] || {
    echo "edge verification: retained release manifest does not match the expected digest" >&2; exit 1;
  }
  manifest="$served_manifest"
else
  cmp -s "$served_manifest" "$release/SHA256SUMS"
  manifest="$release/SHA256SUMS"
fi

expected_player="$(awk '$2 == "./static-player/index.html" { print $1 }' "$manifest")"
[[ -n "$expected_player" ]]
observed_player="$(curl --fail --silent --show-error "$base/" | sha256sum | cut -d' ' -f1)"
[[ "$observed_player" == "$expected_player" ]]

expected_studio="$(awk '$2 == "./static-studio/index.html" { print $1 }' "$manifest")"
if [[ -n "$expected_studio" ]]; then
  observed_studio="$(curl --fail --silent --show-error "$base/studio/" | sha256sum | cut -d' ' -f1)"
  [[ "$observed_studio" == "$expected_studio" ]]
fi

GAME_EDGE_URL="$base" node "$root/deploy/verify-edge.mjs"
rm -f "$served_manifest"
trap - EXIT
echo "edge verification passed: version=$version url=$base hashes=matched api=passed websocket=passed"
