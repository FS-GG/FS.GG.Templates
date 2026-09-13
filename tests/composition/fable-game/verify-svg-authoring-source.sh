#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/svg-authoring-source.XXXXXX")"
trap 'rm -rf "$work"' EXIT
dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$work" >/dev/null
package="$work/FS.GG.Workspace.Template.0.11.0.nupkg"
DOTNET_CLI_HOME="$work/home" dotnet new install "$package" --force >/dev/null
DOTNET_CLI_HOME="$work/home" dotnet new fs-gg-fable-game -n Plain -o "$work/plain" >/dev/null
DOTNET_CLI_HOME="$work/home" dotnet new fs-gg-fable-game -n Selected -o "$work/selected" --svgFoundation true >/dev/null
test ! -e "$work/plain/SvgFoundation"
for path in SceneSchema.fs Program.fs SvgGeometryWorkerEntry.js Studio.fsproj index.html vite.config.js build.sh; do test -f "$work/selected/SvgFoundation/Studio/$path"; done
grep -F '<FsGgSvgAuthoringVersion Condition=' "$work/selected/SvgFoundation/Studio/Studio.fsproj" >/dev/null
grep -F 'Version="[0.29.0]"' "$work/selected/SvgFoundation/SvgFoundation.fsproj" >/dev/null
grep -F 'import "./vendor/svg-geometry-worker.js"' "$work/selected/SvgFoundation/Studio/SvgGeometryWorkerEntry.js" >/dev/null
grep -F 'let gridAdapter' "$work/selected/SvgFoundation/Studio/SceneSchema.fs" >/dev/null
grep -F 'let continuousAdapter' "$work/selected/SvgFoundation/Studio/SceneSchema.fs" >/dev/null
! grep -RE 'SvgStudio\|SvgGeometryWorker\|polygon-clipping' "$work/selected/Client" "$work/selected/Server" "$work/selected/SvgFoundation/Program.fs"
bash -n "$root/scripts/stage-rendering-authoring-packet.sh" "$root/scripts/stage-svg-authoring-candidate.sh" "$root/scripts/apply-svg-foundation-preview.sh" "$root/tests/composition/fable-game/verify-svg-authoring-candidate.sh" "$work/selected/SvgFoundation/Studio/build.sh"
bash -n "$root/tests/composition/fable-game/observe-svg-authoring-orca.sh"
python3 - "$root/tests/composition/fable-game/svg-authoring-orca.py" <<'PY'
import ast,sys
ast.parse(open(sys.argv[1]).read())
PY
node --check "$root/tests/composition/fable-game/svg-authoring-observe.mjs"
node --check "$work/selected/SvgFoundation/Studio/SvgGeometryWorkerEntry.js"
if bash "$root/scripts/stage-svg-authoring-candidate.sh" "$work/missing.json" "$work/refused" >/dev/null 2>&1; then echo "missing packet accepted" >&2; exit 1; fi
echo "svg-authoring-source: opt-in=passed player-isolation=passed package-worker-import=passed staging-refusal=passed"
