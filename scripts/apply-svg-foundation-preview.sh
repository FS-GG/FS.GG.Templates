#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  complete-inventory|complete-apply|complete-rollback|complete-recover)
    exec python3 "$script_dir/apply-svg-complete-workspace.py" "$@"
    ;;
esac

files=(
  SvgFoundation/Program.fs
  SvgFoundation/PreviewFont.fs
  SvgFoundation/PreviewDocument.fs
  SvgFoundation/PlayerInput.fs
  SvgFoundation/ContinuousPlayer.fs
  SvgFoundation/PresentationPlayer.fs
  SvgFoundation/ScalePlayer.fs
  SvgFoundation/README.md
  SvgFoundation/THIRD-PARTY-NOTICES.md
  SvgFoundation/fonts/noto-sans-latin-400-normal.woff2
  SvgFoundation/public/movement-cue.wav
  SvgFoundation/SvgFoundation.fsproj
  SvgFoundation/packages.lock.json
  SvgFoundation/LegacyPreview.props
  SvgFoundation/AdoptedArenaContent.fs
  SvgFoundation/TacticalCompatibility.fs
  SvgFoundation/TacticalCompatibility.Tests.fs
  SvgFoundation/TacticalCompatibility.Tests.fsproj
  SvgFoundation/TacticalCompatibility.Tests.packages.lock.json
  SvgFoundation/index.html
  SvgFoundation/vite.config.js
  SvgFoundation/build.sh
  SvgFoundation/Studio/SceneSchema.fs
  SvgFoundation/Studio/WorkspaceInput.fs
  SvgFoundation/Studio/ReplayStudio.fs
  SvgFoundation/Studio/AdoptedRoom.fs
  SvgFoundation/Studio/AdoptedArenaContent.fs
  SvgFoundation/Studio/AdoptedArenaRules.fs
  SvgFoundation/Studio/Program.fs
  SvgFoundation/Studio/SvgGeometryWorkerEntry.js
  SvgFoundation/Studio/Studio.fsproj
  SvgFoundation/Studio/index.html
  SvgFoundation/Studio/vite.config.js
  SvgFoundation/Studio/build.sh
  models/svg-replay/energy-rules.md
  models/svg-replay/energy-rules.bindings.json
)

fail() { echo "preview adoption: $*" >&2; exit 2; }
sha() { sha256sum "$1" | cut -d' ' -f1; }

# The selectable tactical example keeps its tests outside the Player root. The
# adoption transaction retains the established destination paths while sourcing
# those two files from their package-owned example directory.
source_for() {
  local path="$1"
  if [[ "$path" == build.sh ]]; then
    printf '%s\n' "$workspace/build.sh"
  elif [[ -f "$source_payload/$path" ]]; then
    printf '%s\n' "$source_payload/$path"
  elif [[ "$path" == SvgFoundation/TacticalCompatibility.Tests.fs || "$path" == SvgFoundation/TacticalCompatibility.Tests.fsproj ]] \
       && [[ -f "$source_payload/SvgFoundation/Examples/Tactical/${path##*/}" ]]; then
    printf '%s\n' "$source_payload/SvgFoundation/Examples/Tactical/${path##*/}"
  elif [[ "$path" == SvgFoundation/TacticalCompatibility.Tests.packages.lock.json ]] \
       && [[ -f "$source_payload/SvgFoundation/Examples/Tactical/packages.lock.json" ]]; then
    printf '%s\n' "$source_payload/SvgFoundation/Examples/Tactical/packages.lock.json"
  elif [[ "$path" == SvgFoundation/Studio/AdoptedRoom.fs ]] && [[ -f "$source_payload/Domain/Room.fs" ]]; then
    printf '%s\n' "$source_payload/Domain/Room.fs"
  elif [[ "$path" == SvgFoundation/Studio/AdoptedArenaContent.fs ]] && [[ -f "$source_payload/Domain/ArenaContent.fs" ]]; then
    printf '%s\n' "$source_payload/Domain/ArenaContent.fs"
  elif [[ "$path" == SvgFoundation/Studio/AdoptedArenaRules.fs ]] && [[ -f "$source_payload/Domain/ArenaRules.fs" ]]; then
    printf '%s\n' "$source_payload/Domain/ArenaRules.fs"
  elif [[ "$path" == SvgFoundation/AdoptedArenaContent.fs ]] && [[ -f "$source_payload/Domain/ArenaContent.fs" ]]; then
    printf '%s\n' "$source_payload/Domain/ArenaContent.fs"
  else
    return 1
  fi
}

restore_backup() {
  local workspace="$1" backup="$2" manifest="$2/manifest.tsv"
  [[ -f "$manifest" ]] || fail "rollback manifest missing: $manifest"

  while IFS=$'\t' read -r state digest path; do
    [[ " ${files[*]} " == *" $path "* || "$path" == build.sh ]] || fail "rollback manifest contains unmanaged path: $path"
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

# The 0.11.1 wizard emits the current root build entry point even when it
# installs the older Preview-A payload. That payload has no root SVG lock and
# explicitly disables lock mode in its SVG project. When SVG is being added to
# a workspace that did not have it before, carry the root entry point through
# this same atomic transaction and teach its presence check about the Preview-A
# generation boundary. Existing SVG workspaces retain their root entry point.
if [[ ! -e "$workspace/SvgFoundation" && ! -e "$source_payload/SvgFoundation/packages.lock.json" ]]; then
  [[ -f "$workspace/build.sh" ]] || fail "legacy preview adopter has no root build.sh"
  files+=(build.sh)
fi

# Preview-A payloads predate the additive input and Studio surfaces. Keep their
# established bounded transaction unchanged; each later generation marker makes
# its complete managed set mandatory.
if [[ ! -e "$source_payload/SvgFoundation/Studio/SceneSchema.fs" ]]; then
  preview_a_files=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/Studio/* ]] || preview_a_files+=("$path")
  done
  files=("${preview_a_files[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/PlayerInput.fs" ]]; then
  without_player_runtime=()
  for path in "${files[@]}"; do
    case "$path" in
      SvgFoundation/PlayerInput.fs|SvgFoundation/vite.config.js|SvgFoundation/build.sh) ;;
      *) without_player_runtime+=("$path") ;;
    esac
  done
  files=("${without_player_runtime[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/LegacyPreview.props" ]]; then
  without_legacy_property=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/LegacyPreview.props ]] || without_legacy_property+=("$path")
  done
  files=("${without_legacy_property[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/public/movement-cue.wav" ]]; then
  without_audio_cue=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/public/movement-cue.wav ]] || without_audio_cue+=("$path")
  done
  files=("${without_audio_cue[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/Examples/Tactical/packages.lock.json" ]]; then
  without_tactical_lock=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/TacticalCompatibility.Tests.packages.lock.json ]] || without_tactical_lock+=("$path")
  done
  files=("${without_tactical_lock[@]}")
fi
# Existing workspaces retain their reviewed lock. A workspace that did not
# previously carry SvgFoundation (the wizard adoption path) receives the
# candidate payload's reviewed lock when that payload actually ships one.
if [[ ! -e "$source_payload/SvgFoundation/packages.lock.json" || -e "$workspace/SvgFoundation/packages.lock.json" ]]; then
  with_existing_foundation_lock=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/packages.lock.json ]] || with_existing_foundation_lock+=("$path")
  done
  files=("${with_existing_foundation_lock[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/ContinuousPlayer.fs" ]]; then
  without_continuous_runtime=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/ContinuousPlayer.fs ]] || without_continuous_runtime+=("$path")
  done
  files=("${without_continuous_runtime[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/ScalePlayer.fs" ]]; then
  without_scale=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/ScalePlayer.fs ]] || without_scale+=("$path")
  done
  files=("${without_scale[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/Studio/ReplayStudio.fs" ]]; then
  without_replay=()
  for path in "${files[@]}"; do
    case "$path" in SvgFoundation/Studio/ReplayStudio.fs|models/svg-replay/*) ;; *) without_replay+=("$path") ;; esac
  done
  files=("${without_replay[@]}")
fi
if [[ ! -e "$source_payload/Domain/ArenaRules.fs" ]]; then
  without_adopted_domain=()
  for path in "${files[@]}"; do
    case "$path" in SvgFoundation/AdoptedArenaContent.fs|SvgFoundation/Studio/AdoptedRoom.fs|SvgFoundation/Studio/AdoptedArenaContent.fs|SvgFoundation/Studio/AdoptedArenaRules.fs) ;; *) without_adopted_domain+=("$path") ;; esac
  done
  files=("${without_adopted_domain[@]}")
fi
if [[ ! -e "$source_payload/SvgFoundation/PresentationPlayer.fs" ]]; then
  without_presentation=()
  for path in "${files[@]}"; do
    [[ "$path" == SvgFoundation/PresentationPlayer.fs ]] || without_presentation+=("$path")
  done
  files=("${without_presentation[@]}")
fi

declare -A expected
while read -r digest path; do
  [[ -n "${digest:-}" && -n "${path:-}" ]] && expected["$path"]="${expected[$path]:-} $digest"
done < "$baseline"

conflicts=()
for path in "${files[@]}"; do
  src="$(source_for "$path")" || fail "candidate payload missing $path"
  dst="$workspace/$path"
  if [[ -e "$dst" ]]; then
    current="$(sha "$dst")"
    candidate="$(sha "$src")"
    allowed="${expected[$path]:- ABSENT}"
    if [[ "$path" == *.fs ]]; then
      normalized="$(python3 - "$dst" <<'PY'
import hashlib,re,sys
text=open(sys.argv[1]).read()
match=re.search(r'^module ([A-Za-z_][A-Za-z0-9_.]*?)(?:\.SvgFoundation|\.PreviewDocument$|\.PreviewFont$|\.TacticalCompatibility(?:Tests)?$|\.Domain$|\.ArenaContent$|\.ArenaRules$)',text,re.M)
if not match:
    match=re.search(r'^namespace ([A-Za-z_][A-Za-z0-9_.]*?)\.Domain$',text,re.M)
if not match and sys.argv[1].endswith('/PresentationPlayer.fs'):
    match=re.search(r'^module Player = ([A-Za-z_][A-Za-z0-9_.]*?)\.SvgFoundation\.ContinuousPlayer$',text,re.M)
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
  src="$(source_for "$path")" || fail "candidate payload missing $path"
  if [[ "$path" == *.fs ]]; then
    python3 - "$src" "$backup/staged/$path" "$destination_namespace" <<'PY'
import re,sys
source,destination,target=sys.argv[1:]
text=open(source).read()
match=re.search(r'^module ([A-Za-z_][A-Za-z0-9_.]*?)(?:\.SvgFoundation|\.PreviewDocument$|\.PreviewFont$|\.TacticalCompatibility(?:Tests)?$|\.Domain$|\.ArenaContent$|\.ArenaRules$)',text,re.M)
if not match:
    match=re.search(r'^namespace ([A-Za-z_][A-Za-z0-9_.]*?)\.Domain$',text,re.M)
if not match and source.endswith('/PresentationPlayer.fs'):
    match=re.search(r'^module Player = ([A-Za-z_][A-Za-z0-9_.]*?)\.SvgFoundation\.ContinuousPlayer$',text,re.M)
if not match: raise SystemExit(f'candidate F# module namespace is unreadable: {source}')
open(destination,'w').write(text.replace(match.group(1),target))
PY
  elif [[ "$path" == SvgFoundation/SvgFoundation.fsproj ]]; then
    python3 - "$src" "$backup/staged/$path" <<'PY'
import sys
source,destination=sys.argv[1:]
text=open(source).read().replace('../Domain/ArenaContent.fs', 'AdoptedArenaContent.fs')
open(destination,'w').write(text)
PY
  elif [[ "$path" == SvgFoundation/Studio/Studio.fsproj ]]; then
    python3 - "$src" "$backup/staged/$path" <<'PY'
import sys
source,destination=sys.argv[1:]
text=open(source).read()
text=text.replace('../../Domain/Room.fs', 'AdoptedRoom.fs')
text=text.replace('../../Domain/ArenaContent.fs', 'AdoptedArenaContent.fs')
text=text.replace('../../Domain/ArenaRules.fs', 'AdoptedArenaRules.fs')
open(destination,'w').write(text)
PY
  elif [[ "$path" == SvgFoundation/TacticalCompatibility.Tests.fsproj ]]; then
    python3 - "$src" "$backup/staged/$path" <<'PY'
import sys
source,destination=sys.argv[1:]
text=open(source).read()
text=text.replace('<TargetFramework>net10.0</TargetFramework>',
                  '<TargetFramework>net10.0</TargetFramework>\n    <NuGetLockFilePath>TacticalCompatibility.Tests.packages.lock.json</NuGetLockFilePath>')
text=text.replace('<Compile Include="../../TacticalCompatibility.fs" />',
                  '<Compile Include="TacticalCompatibility.fs" />')
open(destination,'w').write(text)
PY
  elif [[ "$path" == build.sh ]]; then
    python3 - "$src" "$backup/staged/$path" <<'PY'
import sys
source,destination=sys.argv[1:]
text=open(source).read()
old='''if [[ -d SvgFoundation ]]; then
  for locked in SvgFoundation SvgFoundation/Studio SvgFoundation/Examples/Tactical; do'''
new='''if [[ -d SvgFoundation ]]; then
  svg_lock_roots=()
  # Preview-A predates both the player runtime and the reviewed root lock. The
  # additive player generation is the boundary from which that lock is mandatory.
  if [[ -f SvgFoundation/PlayerInput.fs ]]; then
    svg_lock_roots+=(SvgFoundation)
  fi
  for locked in "${svg_lock_roots[@]}" SvgFoundation/Studio SvgFoundation/Examples/Tactical; do'''
if text.count(old) != 1:
    raise SystemExit('legacy preview adopter root build lock check is not the expected shape')
open(destination,'w').write(text.replace(old,new))
PY
  else
    cp "$src" "$backup/staged/$path"
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
