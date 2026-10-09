#!/usr/bin/env bash
# Separately admitted candidate-only generation/managed qualification. Never repack a substitute.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
output=""; game_archive=""; game_sha=""; templates_source=""; provider=false
while (($#)); do
  case "$1" in
    --output) output="$2"; shift 2 ;;
    --canonical-game-archive) game_archive="$2"; shift 2 ;;
    --canonical-game-archive-sha256) game_sha="$2"; shift 2 ;;
    --templates-source) templates_source="$2"; shift 2 ;;
    --provider) provider=true; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "${FSGG_TEMPLATES_NUPKG:-}" && -n "${FSGG_TEMPLATES_NUPKG_SHA256:-}" ]] || { echo 'supply the actual candidate archive and SHA256; no packing fallback' >&2; exit 2; }
[[ "$output" == /* && ! -e "$output" && ! -L "$output" ]] || { echo '--output must be a new absolute directory' >&2; exit 2; }
[[ "$game_archive" == /* && "$game_sha" =~ ^[0-9a-f]{64}$ && "$templates_source" =~ ^[0-9a-f]{40}$ ]] || { echo 'exact canonical archive/source pins required' >&2; exit 2; }
[[ "$(git -C "$root" rev-parse HEAD)" == "$templates_source" && -z "$(git -C "$root" status --porcelain=v1 --untracked-files=all)" ]] || { echo 'source must be clean at exact candidate revision' >&2; exit 2; }
if [[ "$provider" == true ]]; then
  [[ -f "${FSGG_PORTAL_QUALIFIED_SDD:-}" && ! -L "$FSGG_PORTAL_QUALIFIED_SDD" && "${FSGG_PORTAL_QUALIFIED_SDD_SHA256:-}" =~ ^[0-9a-f]{64}$ ]] || { echo 'provider requires a separately qualified installed SDD >=2.1.0 and its exact executable pin' >&2; exit 2; }
  [[ "$(sha256sum "$FSGG_PORTAL_QUALIFIED_SDD" | cut -d' ' -f1)" == "$FSGG_PORTAL_QUALIFIED_SDD_SHA256" ]] || { echo 'qualified SDD executable changed' >&2; exit 2; }
fi
LANE_REPO_ROOT="$root"
# shellcheck source=tests/composition/lib/lane-package.sh
. "$root/tests/composition/lib/lane-package.sh"
package="$(lane_package_path "$output")"
verify=(python3 "$root/tests/composition/fable-game/verify-portal-example.py" --canonical-game-archive "$game_archive" --canonical-game-archive-sha256 "$game_sha")
# Cheap exact input/source/archive checks precede output creation and every native effect.
"${verify[@]}" --source "$root" --archive "$package" --archive-sha256 "$FSGG_TEMPLATES_NUPKG_SHA256" --templates-source "$templates_source"
mkdir -m 700 "$output"
export DOTNET_CLI_HOME="$output/home" NUGET_PACKAGES="$output/packages" NUGET_HTTP_CACHE_PATH="$output/http-cache"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 MSBUILDDISABLENODEREUSE=1
stage() {
  local name="$1" code=0; shift
  printf '%s\tstarted\n' "$name" >>"$output/stages.tsv"
  "$@" >"$output/$name.log" 2>&1 || code=$?
  printf '%s\texit=%d\n' "$name" "$code" >>"$output/stages.tsv"
  [[ "$code" == 0 ]] || { echo "first stage failure: $name exit=$code; dependent stages stopped" >&2; exit "$code"; }
}
stage install dotnet new install "$package" --force
create() { local label="$1"; shift; stage "$label" dotnet new fs-gg-fable-game -n PortalCandidate -o "$output/$label" --lifecycle none "$@"; }
create omitted
create false --portalExample false
create player --bundle player --portalExample true
create complete-off --bundle complete --portalExample false
create complete --bundle complete --portalExample true
create legacy-true --svgFoundation true
create legacy-false --svgFoundation false
for label in omitted false complete-off legacy-true legacy-false; do
  "${verify[@]}" --generated "$output/$label" --expected false
done
"${verify[@]}" --generated "$output/false" --expected false --peer "$output/omitted"
"${verify[@]}" --generated "$output/player" --expected true --peer "$output/omitted"
"${verify[@]}" --generated "$output/complete" --expected true --peer "$output/complete-off"
refuse() {
  local label="$1"; shift
  if dotnet new fs-gg-fable-game -n RefusedPortal -o "$output/$label" --lifecycle none "$@" >"$output/$label.log" 2>&1; then
    echo "invalid selection unexpectedly generated: $label" >&2; exit 1
  fi
  [[ ! -e "$output/$label" ]] || { echo "refused selection left receiver effects: $label" >&2; exit 1; }
}
refuse invalid-bool --portalExample definitely-not-a-bool
refuse legacy-mixed --svgFoundation true --portalExample true
refuse legacy-mixed-reverse --portalExample true --svgFoundation false
cat >"$output/Public.NuGet.Config" <<'CONFIG'
<?xml version="1.0"?><configuration><packageSources><clear/><add key="nuget.org" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><clear/><packageSource key="nuget.org"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
CONFIG
runtime() {
  local label="$1" receiver="$2"
  (
    cd "$receiver/PortalExample"
    stage "$label-preflight" python3 verify-package-boundary.py --presentation --preflight
    cp packages.lock.json "$output/$label-original.lock.json"
    stage "$label-restore" dotnet restore Consumer.fsproj --configfile "$output/Public.NuGet.Config" --no-cache --locked-mode --disable-parallel
    cmp packages.lock.json "$output/$label-original.lock.json"
    stage "$label-boundary" python3 verify-package-boundary.py --presentation
    stage "$label-build" dotnet build Consumer.fsproj -c Release --no-restore -m:1 --disable-build-servers
    stage "$label-default" dotnet exec --fx-version 10.0.12 bin/Release/net10.0/Consumer.dll
    stage "$label-presentation" dotnet exec --fx-version 10.0.12 bin/Release/net10.0/Consumer.dll --presentation
    local code=0
    dotnet exec --fx-version 10.0.12 bin/Release/net10.0/Consumer.dll --invalid >"$output/$label-invalid.log" 2>&1 || code=$?
    [[ "$code" == 2 ]] && grep -qF 'Usage: Box2D.Portals [--presentation]' "$output/$label-invalid.log" || { echo 'invalid argument contract changed' >&2; exit 1; }
  )
}
runtime direct "$output/player"
if [[ "$provider" == true ]]; then
  mkdir -p "$output/provider/.fsgg"
  cp "$root/providers/fable-game.providers.yml" "$output/provider/.fsgg/providers.yml"
  lane_pin_provider_to_archive "$output/provider/.fsgg/providers.yml" "$package"
  "$FSGG_PORTAL_QUALIFIED_SDD" scaffold --root "$output/provider" --provider fable-game --param productName=Portal-Provider --param rootNamespace=PortalProvider --param portalExample=true --param lifecycle=none --no-update --json >"$output/provider.json"
  "${verify[@]}" --generated "$output/provider" --expected true --provider-json "$output/provider.json"
  runtime provider "$output/provider"
else
  printf '%s\n' 'Provider-v2 qualification PENDING: no installed SDD invocation authorized/selected.' >"$output/provider-pending.txt"
fi
printf '%s\n' 'PASS candidate-only direct template Portal generation/runtime; provider separately reported; no public installed/retained adoption or performance rerun.'
