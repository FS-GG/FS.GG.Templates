#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$root/artifacts/svg-artifact-measurements.tsv"
: > "$output"
for directory in static-player static-studio authority-server; do
  path="$root/artifacts/$directory"
  if [[ -d "$path" ]]; then
    bytes="$(du -sb "$path" | cut -f1)"
    files="$(find "$path" -type f | wc -l)"
    printf '%s\t%s\t%s\n' "$directory" "$files" "$bytes" >> "$output"
  fi
done
static_directories=()
for directory in static-player static-studio; do
  [[ -d "$root/artifacts/$directory" ]] && static_directories+=("$root/artifacts/$directory")
done
if (( ${#static_directories[@]} > 0 )); then
  find "${static_directories[@]}" -type f -name '*.js' \
    | sort \
    | while IFS= read -r file; do
      bytes="$(wc -c < "$file")"
      gzip_bytes="$(gzip -c "$file" | wc -c)"
      printf 'chunk\t%s\t%s\t%s\n' "${file#"$root/"}" "$bytes" "$gzip_bytes" >> "$output"
    done
fi
