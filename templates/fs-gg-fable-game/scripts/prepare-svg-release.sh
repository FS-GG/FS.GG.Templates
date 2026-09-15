#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${SVG_RELEASE_VERSION:-workspace-v1}"
case "$version" in
  *[!A-Za-z0-9._-]*|''|.|..)
    echo "release preparation refused: SVG_RELEASE_VERSION must be a nonblank file-name token" >&2
    exit 1
    ;;
esac

release="$root/artifacts/releases/$version"
mkdir -p "$root/artifacts/releases"
staging="$(mktemp -d "$root/artifacts/releases/.${version}.staging.XXXXXX")"
trap 'rm -rf "$staging"' EXIT

for artifact in static-player static-studio authority-server; do
  if [[ -d "$root/artifacts/$artifact" ]]; then
    mkdir -p "$staging/$artifact"
    cp -R "$root/artifacts/$artifact/." "$staging/$artifact/"
  fi
done

mkdir -p "$staging/content"
for selected in SvgFoundation/Examples/Tactical/scene.json SvgFoundation/Examples/Arcade/scene.json; do
  if [[ -f "$root/$selected" ]]; then
    destination="$staging/content/${selected#SvgFoundation/Examples/}"
    mkdir -p "$(dirname "$destination")"
    cp "$root/$selected" "$destination"
  fi
done

printf '%s\n' "$version" > "$staging/VERSION"
(
  cd "$staging"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c --quiet SHA256SUMS
)
if [[ -d "$release" ]]; then
  existing_manifest="$(mktemp)"
  trap 'rm -rf "$staging"; rm -f "$existing_manifest"' EXIT
  (
    cd "$release"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$existing_manifest"
  )
  if ! cmp -s "$staging/SHA256SUMS" "$existing_manifest"; then
    echo "release preparation refused: immutable version '$version' already contains different bytes" >&2
    exit 1
  fi
  echo "release already prepared with identical bytes: artifacts/releases/$version"
  exit 0
fi
mv "$staging" "$release"
trap - EXIT
echo "release prepared: artifacts/releases/$version"
