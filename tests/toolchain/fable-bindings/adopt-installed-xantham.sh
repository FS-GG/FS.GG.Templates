#!/usr/bin/env bash
# Apply the bounded 0.14.0 Xantham payload with a three-way collision check.
set -euo pipefail
baseline="${1:?usage: adopt-installed-xantham.sh BASELINE CANDIDATE TARGET MANIFEST}"
candidate="${2:?}"
target="${3:?}"
manifest="${4:?}"

while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  test -f "$candidate/$path" || { echo "candidate is missing managed path: $path" >&2; exit 1; }
  if [[ -e "$baseline/$path" ]]; then
    test -f "$target/$path" && cmp -s "$baseline/$path" "$target/$path" || {
      echo "adoption refused before writes: managed path changed: $path" >&2
      exit 1
    }
  elif [[ -e "$target/$path" ]]; then
    echo "adoption refused before writes: new managed path collides: $path" >&2
    exit 1
  fi
done <"$manifest"

while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  mkdir -p "$target/$(dirname "$path")"
  cp -p "$candidate/$path" "$target/$path"
done <"$manifest"

echo 'PASS retained Xantham payload adopted after collision-free inventory'
