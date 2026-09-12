#!/usr/bin/env bash
set -euo pipefail

files=(
  SvgFoundation/Program.fs
  SvgFoundation/PreviewFont.fs
  SvgFoundation/PreviewDocument.fs
  SvgFoundation/README.md
  SvgFoundation/THIRD-PARTY-NOTICES.md
  SvgFoundation/fonts/noto-sans-latin-400-normal.woff2
  SvgFoundation/SvgFoundation.fsproj
  SvgFoundation/TacticalCompatibility.fs
  SvgFoundation/TacticalCompatibility.Tests.fs
  SvgFoundation/TacticalCompatibility.Tests.fsproj
  SvgFoundation/index.html
)

fail() { echo "preview adoption: $*" >&2; exit 2; }
sha() { sha256sum "$1" | cut -d' ' -f1; }

restore_backup() {
  local workspace="$1" backup="$2" manifest="$2/manifest.tsv"
  [[ -f "$manifest" ]] || fail "rollback manifest missing: $manifest"

  while IFS=$'\t' read -r state digest path; do
    [[ " ${files[*]} " == *" $path "* ]] || fail "rollback manifest contains unmanaged path: $path"
    if [[ "$state" == PRESENT ]]; then
      [[ -f "$backup/files/$path" ]] || fail "rollback object missing: $path"
      [[ "$(sha "$backup/files/$path")" == "$digest" ]] || fail "rollback object digest mismatch: $path"
    elif [[ "$state" != ABSENT || "$digest" != - ]]; then
      fail "rollback manifest row is invalid: $path"
    fi
  done < "$manifest"

  while IFS=$'\t' read -r state _ path; do
    if [[ "$state" == PRESENT ]]; then
      mkdir -p "$(dirname "$workspace/$path")"
      cp "$backup/files/$path" "$workspace/$path"
    else
      rm -f "$workspace/$path"
    fi
  done < "$manifest"
  echo "preview adoption: rolled back bounded SVG foundation package/config delta"
}

case "${1:-}" in
  rollback)
    [[ $# == 3 ]] || fail "usage: $0 rollback <workspace> <backup>"
    restore_backup "$2" "$3"
    exit 0
    ;;
  apply)
    [[ $# == 5 ]] || fail "usage: $0 apply <candidate-payload> <workspace> <baseline-manifest> <backup>"
    source_payload="$2"
    workspace="$3"
    baseline="$4"
    backup="$5"
    ;;
  *)
    fail "first argument must be apply or rollback"
    ;;
esac

[[ ! -e "$backup" ]] || fail "backup target already exists: $backup"
[[ -f "$baseline" ]] || fail "baseline manifest missing: $baseline"

declare -A expected
while read -r digest path; do
  [[ -n "${digest:-}" && -n "${path:-}" ]] && expected["$path"]="$digest"
done < "$baseline"

conflicts=()
for path in "${files[@]}"; do
  src="$source_payload/$path"
  dst="$workspace/$path"
  [[ -f "$src" ]] || fail "candidate payload missing $path"
  if [[ -e "$dst" ]]; then
    current="$(sha "$dst")"
    candidate="$(sha "$src")"
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

mkdir -p "$backup/files" "$backup/staged"
: > "$backup/manifest.tsv"
for path in "${files[@]}"; do
  mkdir -p "$(dirname "$backup/staged/$path")"
  cp "$source_payload/$path" "$backup/staged/$path"
  if [[ -f "$workspace/$path" ]]; then
    mkdir -p "$(dirname "$backup/files/$path")"
    cp "$workspace/$path" "$backup/files/$path"
    printf 'PRESENT\t%s\t%s\n' "$(sha "$workspace/$path")" "$path" >> "$backup/manifest.tsv"
  else
    printf 'ABSENT\t-\t%s\n' "$path" >> "$backup/manifest.tsv"
  fi
done

applied=0
for path in "${files[@]}"; do
  mkdir -p "$(dirname "$workspace/$path")"
  cp "$backup/staged/$path" "$workspace/$path"
  applied=$((applied + 1))
  if [[ "${FSGG_SVG_PREVIEW_FAIL_AFTER:-}" == "$applied" ]]; then
    restore_backup "$workspace" "$backup" >/dev/null
    fail "injected interruption after $applied managed files; rollback completed"
  fi
done
echo "preview adoption: applied bounded SVG foundation package/config delta; rollback=$backup"
