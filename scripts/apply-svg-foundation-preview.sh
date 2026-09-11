#!/usr/bin/env bash
set -euo pipefail
source_payload="${1:?current template payload root is required}"
workspace="${2:?retained workspace root is required}"
baseline="${3:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/svg-foundation-preview-baseline.manifest}"

files=(
  SvgFoundation/Program.fs
  SvgFoundation/README.md
  SvgFoundation/SvgFoundation.fsproj
  SvgFoundation/TacticalCompatibility.fs
  SvgFoundation/TacticalCompatibility.Tests.fs
  SvgFoundation/TacticalCompatibility.Tests.fsproj
  SvgFoundation/index.html
)

declare -A expected
while read -r digest path; do
  [[ -n "${digest:-}" && -n "${path:-}" ]] && expected["$path"]="$digest"
done < "$baseline"

conflicts=()
for path in "${files[@]}"; do
  src="$source_payload/$path"; dst="$workspace/$path"
  [[ -f "$src" ]] || { echo "preview adoption: candidate payload missing $path" >&2; exit 2; }
  if [[ -e "$dst" ]]; then
    current="$(sha256sum "$dst" | cut -d' ' -f1)"
    candidate="$(sha256sum "$src" | cut -d' ' -f1)"
    allowed="${expected[$path]:-ABSENT}"
    if [[ "$path" == SvgFoundation/Program.fs ]]; then
      normalized="$(sed -E 's/^module [A-Za-z_][A-Za-z0-9_.]*\.SvgFoundation$/module FableGameWorkspaceNamespace.SvgFoundation/' "$dst" | sha256sum | cut -d' ' -f1)"
    else
      normalized="$current"
    fi
    [[ "$current" == "$candidate" || "$normalized" == "$allowed" ]] || conflicts+=("$path")
  fi
done
if (( ${#conflicts[@]} > 0 )); then
  printf 'preview adoption conflict: %s\n' "${conflicts[@]}" >&2
  exit 3
fi

for path in "${files[@]}"; do
  mkdir -p "$(dirname "$workspace/$path")"
  cp "$source_payload/$path" "$workspace/$path"
done
echo "preview adoption: applied bounded SVG foundation package/config delta"
