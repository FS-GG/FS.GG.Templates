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
  SvgFoundation/Studio/SceneSchema.fs
  SvgFoundation/Studio/Program.fs
  SvgFoundation/Studio/SvgGeometryWorkerEntry.js
  SvgFoundation/Studio/Studio.fsproj
  SvgFoundation/Studio/index.html
  SvgFoundation/Studio/vite.config.js
  SvgFoundation/Studio/build.sh
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

# Preview-A payloads predate the additive Studio surface. Keep their established
# bounded transaction unchanged; once the first Studio file is present, require
# and apply the complete authoring set declared above.
if [[ ! -e "$source_payload/SvgFoundation/Studio/SceneSchema.fs" ]]; then
  preview_a_files=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/Studio/* ]] || preview_a_files+=("$path")
  done
  files=("${preview_a_files[@]}")
fi

declare -A expected
while read -r digest path; do
  [[ -n "${digest:-}" && -n "${path:-}" ]] && expected["$path"]="${expected[$path]:-} $digest"
done < "$baseline"

conflicts=()
for path in "${files[@]}"; do
  src="$source_payload/$path"
  dst="$workspace/$path"
  [[ -f "$src" ]] || fail "candidate payload missing $path"
  if [[ -e "$dst" ]]; then
    current="$(sha "$dst")"
    candidate="$(sha "$src")"
    allowed="${expected[$path]:- ABSENT}"
    if [[ "$path" == *.fs ]]; then
      normalized="$(python3 - "$dst" <<'PY'
import hashlib,re,sys
text=open(sys.argv[1]).read()
match=re.search(r'^module ([A-Za-z_][A-Za-z0-9_.]*?)(?:\.SvgFoundation|\.PreviewDocument$|\.PreviewFont$|\.TacticalCompatibility(?:Tests)?$)',text,re.M)
normalized=text if not match else text.replace(match.group(1),'FableGameWorkspaceNamespace')
print(hashlib.sha256(normalized.encode()).hexdigest())
PY
)"
    else
      normalized="$current"
    fi
    [[ "$current" == "$candidate" || " $allowed " == *" $normalized "* || " $allowed " == *" ABSENT "* && ! -e "$dst" ]] || conflicts+=("$path")
  fi
done
if (( ${#conflicts[@]} > 0 )); then
  printf 'preview adoption conflict: %s\n' "${conflicts[@]}" >&2
  exit 3
fi

if [[ -f "$workspace/SvgFoundation/Program.fs" ]]; then
  destination_namespace="$(sed -nE 's/^module ([A-Za-z_][A-Za-z0-9_.]*)\.SvgFoundation$/\1/p' "$workspace/SvgFoundation/Program.fs")"
else
  destination_namespace="$(sed -nE 's/^namespace ([A-Za-z_][A-Za-z0-9_.]*)\.Domain$/\1/p' "$workspace/Domain/Room.fs")"
fi
[[ -n "$destination_namespace" ]] || fail "destination product namespace is unreadable"
mkdir -p "$backup/files" "$backup/staged"
: > "$backup/manifest.tsv"
for path in "${files[@]}"; do
  mkdir -p "$(dirname "$backup/staged/$path")"
  if [[ "$path" == *.fs ]]; then
    python3 - "$source_payload/$path" "$backup/staged/$path" "$destination_namespace" <<'PY'
import re,sys
source,destination,target=sys.argv[1:]
text=open(source).read()
match=re.search(r'^module ([A-Za-z_][A-Za-z0-9_.]*?)(?:\.SvgFoundation|\.PreviewDocument$|\.PreviewFont$|\.TacticalCompatibility(?:Tests)?$)',text,re.M)
if not match: raise SystemExit(f'candidate F# module namespace is unreadable: {source}')
open(destination,'w').write(text.replace(match.group(1),target))
PY
  else
    cp "$source_payload/$path" "$backup/staged/$path"
  fi
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
