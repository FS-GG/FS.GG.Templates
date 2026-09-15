#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-${SVG_RELEASE_VERSION:-}}"
output="${2:-}"
[[ "$version" =~ ^[A-Za-z0-9._-]+$ && "$version" != "." && "$version" != ".." ]] || {
  echo "invalid immutable release version" >&2; exit 1;
}
[[ -n "$output" ]] || { echo "production archive output path is required" >&2; exit 1; }
release="$root/artifacts/releases/$version"
[[ -d "$release" ]] || { echo "missing immutable release: $release" >&2; exit 1; }
(cd "$release" && sha256sum --check --quiet SHA256SUMS)

staging="$(mktemp "${output}.staging.XXXXXX")"
trap 'rm -f "$staging"' EXIT
tar --create --file - --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  --directory "$root" deploy "artifacts/releases/$version" | gzip -n >"$staging"
mv "$staging" "$output"
trap - EXIT
echo "production archive prepared: version=$version sha256=$(sha256sum "$output" | cut -d' ' -f1)"
