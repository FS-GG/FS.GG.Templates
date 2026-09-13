#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/svg-authoring-source.XXXXXX")"
trap 'rm -rf "$work"' EXIT
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$work" >/dev/null
packages=("$work"/FS.GG.Workspace.Template.*.nupkg)
[[ ${#packages[@]} -eq 1 && -f "${packages[0]}" ]]
package="${packages[0]}"
DOTNET_CLI_HOME="$work/home" dotnet new install "$package" --force >/dev/null
DOTNET_CLI_HOME="$work/home" dotnet new fs-gg-fable-game -n Plain -o "$work/plain" >/dev/null
DOTNET_CLI_HOME="$work/home" dotnet new fs-gg-fable-game -n Selected -o "$work/selected" --svgFoundation true >/dev/null
test ! -e "$work/plain/SvgFoundation"
for path in SceneSchema.fs Program.fs SvgGeometryWorkerEntry.js Studio.fsproj index.html vite.config.js build.sh; do test -f "$work/selected/SvgFoundation/Studio/$path"; done
for path in PlayerInput.fs build.sh vite.config.js; do test -f "$work/selected/SvgFoundation/$path"; done
test -f "$work/selected/SvgFoundation/Studio/WorkspaceInput.fs"
grep -F '<FsGgSvgAuthoringVersion Condition=' "$work/selected/SvgFoundation/Studio/Studio.fsproj" >/dev/null
grep -F '<FsGgSvgInputCandidate Condition=' "$work/selected/SvgFoundation/Studio/Studio.fsproj" >/dev/null
grep -F '<FsGgSvgInputVersion Condition=' "$work/selected/SvgFoundation/SvgFoundation.fsproj" >/dev/null
grep -F '<Compile Include="PlayerInput.fs" Condition=' "$work/selected/SvgFoundation/SvgFoundation.fsproj" >/dev/null
grep -F '<Compile Include="WorkspaceInput.fs" Condition=' "$work/selected/SvgFoundation/Studio/Studio.fsproj" >/dev/null
grep -F 'Version="[$(FsGgSvgInputVersion)]"' "$work/selected/SvgFoundation/SvgFoundation.fsproj" >/dev/null
grep -F 'import "./vendor/svg-geometry-worker.js"' "$work/selected/SvgFoundation/Studio/SvgGeometryWorkerEntry.js" >/dev/null
grep -F 'let gridAdapter' "$work/selected/SvgFoundation/Studio/SceneSchema.fs" >/dev/null
grep -F 'let continuousAdapter' "$work/selected/SvgFoundation/Studio/SceneSchema.fs" >/dev/null
! grep -RE 'SvgStudio\|SvgGeometryWorker\|polygon-clipping' "$work/selected/Client" "$work/selected/Server" "$work/selected/SvgFoundation/Program.fs"
bash -n "$root/scripts/stage-rendering-authoring-packet.sh" "$root/scripts/stage-svg-authoring-candidate.sh" "$root/scripts/apply-svg-foundation-preview.sh" "$root/tests/composition/fable-game/verify-svg-authoring-candidate.sh" "$work/selected/SvgFoundation/Studio/build.sh"
bash -n "$root/scripts/stage-rendering-input-packet.sh" "$root/scripts/stage-svg-input-candidate.sh" "$root/tests/composition/fable-game/verify-svg-input-candidate.sh" "$work/selected/SvgFoundation/build.sh"
bash -n "$root/tests/composition/fable-game/observe-svg-authoring-orca.sh"
bash -n "$root/tests/composition/fable-game/observe-svg-input-orca.sh"
python3 - "$root/tests/composition/fable-game/svg-authoring-orca.py" <<'PY'
import ast,sys
ast.parse(open(sys.argv[1]).read())
PY
python3 - "$root/tests/composition/fable-game/svg-input-orca.py" <<'PY'
import ast,sys
ast.parse(open(sys.argv[1]).read())
PY
node --check "$root/tests/composition/fable-game/svg-authoring-observe.mjs"
node --check "$root/tests/composition/fable-game/svg-input-observe.mjs"
node --check "$root/tests/composition/fable-game/svg-player-input-observe.mjs"
node --check "$work/selected/SvgFoundation/Studio/SvgGeometryWorkerEntry.js"
if bash "$root/scripts/stage-svg-authoring-candidate.sh" "$work/missing.json" "$work/refused" >/dev/null 2>&1; then echo "missing packet accepted" >&2; exit 1; fi
if bash "$root/scripts/stage-svg-input-candidate.sh" "$work/missing.json" "$work/input-refused" >/dev/null 2>&1; then echo "missing input packet accepted" >&2; exit 1; fi
echo "svg-authoring-source: opt-in=passed player-isolation=passed package-worker-import=passed staging-refusal=passed"
