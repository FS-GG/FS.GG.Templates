#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
package="${1:?template package path is required}"
work="${2:-$(mktemp -d "${TMPDIR:-/tmp}/fable-game-svg-foundation.XXXXXX")}"
rendering="${FSGG_RENDERING_REPO:-$root/../FS.GG.Rendering}"
expected_rendering="c4e50dcb239ccb62453cdd47505f1a8d1095814e"

if [ ! -d "$rendering/.git" ] || [ "$(git -C "$rendering" rev-parse HEAD)" != "$expected_rendering" ]; then
  rendering="$work/FS.GG.Rendering"
  git clone --quiet https://github.com/FS-GG/FS.GG.Rendering.git "$rendering"
  git -C "$rendering" checkout --quiet "$expected_rendering"
fi

mkdir -p "$work/feed" "$work/packages" "$work/dotnet-home"
dotnet pack "$rendering/src/Scene/Scene.fsproj" -c Release -o "$work/feed" -p:Version=0.29.0-preview.1
dotnet pack "$rendering/src/KeyboardInput/KeyboardInput.fsproj" -c Release -o "$work/feed" -p:Version=0.29.0-preview.1
dotnet pack "$rendering/src/Scene.SvgBrowser/Scene.SvgBrowser.fsproj" -c Release -o "$work/feed" -p:Version=0.29.0-preview.1
DOTNET_CLI_HOME="$work/dotnet-home" dotnet new install "$package" --force >/dev/null
DOTNET_CLI_HOME="$work/dotnet-home" dotnet new fs-gg-fable-game -n FoundationFixture -o "$work/default" >/dev/null
test ! -e "$work/default/SvgFoundation"
DOTNET_CLI_HOME="$work/dotnet-home" dotnet new fs-gg-fable-game -n FoundationFixture -o "$work/selected" --svgFoundation true >/dev/null
test -f "$work/selected/SvgFoundation/Program.fs"
test -f "$work/selected/SvgFoundation/TacticalCompatibility.fs"
cat > "$work/NuGet.Config" <<CONFIG
<configuration><packageSources><clear/><add key="candidate" value="$work/feed"/><add key="nuget" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="candidate"><package pattern="FS.GG.UI.Scene*"/><package pattern="FS.GG.UI.KeyboardInput"/></packageSource><packageSource key="nuget"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
CONFIG
export NUGET_PACKAGES="$work/packages"
dotnet restore "$work/selected/SvgFoundation/SvgFoundation.fsproj" --configfile "$work/NuGet.Config"
dotnet restore "$work/selected/SvgFoundation/TacticalCompatibility.Tests.fsproj" --configfile "$work/NuGet.Config"
dotnet tool restore --tool-manifest "$work/selected/.config/dotnet-tools.json" --configfile "$work/NuGet.Config"
(cd "$work/selected" && dotnet fable SvgFoundation/SvgFoundation.fsproj --outDir "$work/fable" --noCache)
test -f "$work/fable/Program.js"
dotnet run --project "$work/selected/SvgFoundation/TacticalCompatibility.Tests.fsproj" --no-restore
if grep -En 'ProjectReference|<Link>' "$work/selected/SvgFoundation/"*.fsproj; then
  echo 'foundation fixture acquired a sibling source edge' >&2; exit 1
fi
grep -q 'foundation-grid' "$work/selected/SvgFoundation/Program.fs"
grep -q 'foundation-continuous' "$work/selected/SvgFoundation/Program.fs"
grep -q 'foundation-tactical-compatibility' "$work/selected/SvgFoundation/Program.fs"
grep -q 'preview-alpha-mask' "$work/selected/SvgFoundation/PreviewDocument.fs"
grep -q '09aee8065d25508f23a4c3d92cd777ac869c52d93fd868a88f025d888a7937d6' "$work/selected/SvgFoundation/PreviewFont.fs"
grep -q '80e1ac9328865ec8d1ee3eeea130560ef22b1b01' "$work/selected/SvgFoundation/README.md"
if grep -REn 'SIR\.' "$work/selected/SvgFoundation"; then
  echo 'neutral fixture contains S.I.R. types' >&2; exit 1
fi
grep -q 'undisclosed-contact-at-grid-9' "$work/selected/SvgFoundation/TacticalCompatibility.Tests.fs"
grep -q 'Selection = projection.Selection' "$work/selected/SvgFoundation/TacticalCompatibility.fs" && {
  echo 'tactical adapter bypasses relevant disclosed-selection filtering' >&2; exit 1
}
echo "svg-foundation-template: explicit-selection=passed package-only=passed grid=passed continuous=passed tactical-contract=passed"
