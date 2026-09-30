#!/usr/bin/env bash
set -euo pipefail

version="1.27.1"
archive_name="go${version}.linux-amd64.tar.gz"
archive_url="https://go.dev/dl/${archive_name}"
expected_sha256="63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445"
destination="${1:-${TMPDIR:-/tmp}/fsgg-go-${version}}"
archive="${2:-${TMPDIR:-/tmp}/${archive_name}}"

if [[ -e "$destination" ]]; then
  echo "refusing existing toolchain destination: $destination" >&2
  exit 2
fi

if [[ ! -f "$archive" ]]; then
  curl --fail --location --proto '=https' --tlsv1.2 --output "$archive" "$archive_url"
fi

printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status

staging="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-go-stage.XXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
tar --extract --gzip --file "$archive" --directory "$staging"
mv "$staging/go" "$destination"

actual="$($destination/bin/go version)"
if [[ "$actual" != "go version go${version} linux/amd64" ]]; then
  echo "unexpected installed toolchain: $actual" >&2
  exit 3
fi

printf '%s\n' "$actual"
printf 'sha256 %s\n' "$expected_sha256"
