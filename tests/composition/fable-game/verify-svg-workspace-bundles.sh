#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/fs-gg-svg-bundles.XXXXXX")"
home="$work/home"
package="$work/feed/FS.GG.Workspace.Template.0.14.0.nupkg"
mkdir -p "$work/feed" "$home"

dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$work/feed" >/dev/null
DOTNET_CLI_HOME="$home" dotnet new install "$package" >/dev/null

assert_path() { [[ -e "$1" ]] || { echo "bundle composition: missing $1" >&2; exit 1; }; }
refute_path() { [[ ! -e "$1" ]] || { echo "bundle composition: unexpected $1" >&2; exit 1; }; }

create() {
  local name="$1"; shift
  DOTNET_CLI_HOME="$home" dotnet new fs-gg-fable-game -n "$name" -o "$work/$name" --lifecycle none "$@" >/dev/null
}

create Omitted
create Player --bundle player
create Studio --bundle studio
create Tactical --bundle tactical
create Arcade --bundle arcade
create Complete --bundle complete
create LegacyTrue --svgFoundation true
create LegacyFalse --svgFoundation false

for product in Omitted Player; do
  assert_path "$work/$product/SvgFoundation/SvgFoundation.fsproj"
  refute_path "$work/$product/SvgFoundation/Studio"
  refute_path "$work/$product/SvgFoundation/Examples"
done
assert_path "$work/Studio/SvgFoundation/Studio/Studio.fsproj"
refute_path "$work/Studio/SvgFoundation/Examples"
assert_path "$work/Tactical/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/Tactical/SvgFoundation/Examples/Tactical/README.md"
refute_path "$work/Tactical/SvgFoundation/Examples/Arcade"
assert_path "$work/Arcade/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/Arcade/SvgFoundation/Examples/Arcade/README.md"
refute_path "$work/Arcade/SvgFoundation/Examples/Tactical"
assert_path "$work/Complete/SvgFoundation/Examples/Tactical/README.md"
assert_path "$work/Complete/SvgFoundation/Examples/Arcade/README.md"
assert_path "$work/LegacyTrue/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/LegacyTrue/SvgFoundation/Examples/Tactical/README.md"
refute_path "$work/LegacyFalse/SvgFoundation"

for lifecycle in none sdd typed-sdd spec-kit; do
  DOTNET_CLI_HOME="$home" dotnet new fs-gg-fable-game -n "Lifecycle${lifecycle//-/}" \
    -o "$work/Lifecycle${lifecycle//-/}" --bundle player --lifecycle "$lifecycle" >/dev/null
done

for pair in "player false" "studio false" "player true" "arcade true"; do
  read -r bundle legacy <<<"$pair"
  destination="$work/conflict-$bundle-$legacy"
  mkdir -p "$destination"
  printf 'retained\n' >"$destination/sentinel"
  if DOTNET_CLI_HOME="$home" dotnet new fs-gg-fable-game -n Conflict -o "$destination" \
       --bundle "$bundle" --svgFoundation "$legacy" >"$work/conflict.log" 2>&1; then
    echo "bundle composition: contradictory bundle=$bundle svgFoundation=$legacy was accepted" >&2
    exit 1
  fi
  [[ "$(find "$destination" -mindepth 1 -maxdepth 1 -type f -printf '%f\n')" == sentinel ]] || {
    echo "bundle composition: contradictory parameters wrote into $destination" >&2; exit 1;
  }
done

grep -F 'source: FS.GG.Workspace.Template::0.14.0' "$root/providers/fable-game.providers.yml" >/dev/null
grep -A3 -- '- key: bundle' "$root/providers/fable-game.providers.yml" | grep -F 'default: player' >/dev/null

echo "svg-workspace-bundles: default=player matrix=passed legacy=true/false contradiction=no-write lifecycle=preserved"
