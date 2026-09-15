#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/fs-gg-svg-bundles.XXXXXX")"
home="$work/home"
package="$work/feed/FS.GG.Workspace.Template.0.14.0.nupkg"
mkdir -p "$work/feed" "$home"

dotnet pack "$root/FS.GG.Templates.csproj" -c Release -o "$work/feed" >/dev/null
if unzip -Z1 "$package" | rg '/(dist|output|vendor|artifacts)/|/Protocol.Tests/cross-runtime/CodecProbe.Fable/Program.js$' >/dev/null; then
  echo "bundle composition: packed archive contains generated product output" >&2; exit 1
fi
[[ "$(unzip -Z1 "$package" | rg -c 'fs-gg-fable-game(-legacy)?/\.template\.config/template\.json$')" == 2 ]] || {
  echo "bundle composition: grouped new/legacy template definitions missing from archive" >&2; exit 1;
}
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
  assert_path "$work/$product/SvgFoundation/packages.lock.json"
  refute_path "$work/$product/SvgFoundation/Studio"
  refute_path "$work/$product/SvgFoundation/Examples"
  refute_path "$work/$product/SvgFoundation/TacticalCompatibility.fs"
  refute_path "$work/$product/SvgFoundation/PreviewDocument.fs"
  refute_path "$work/$product/SvgFoundation/PreviewFont.fs"
  grep -F 'Cooperative SVG arena' "$work/$product/SvgFoundation/index.html" >/dev/null
  if find "$work/$product" -type f \( -iname '*.qnt' -o -iname '*.java' \) -print -quit | grep -q .; then
    echo "bundle composition: player contains Quint or Java source" >&2; exit 1
  fi
  if rg -l -i 'babylon|fable\.react|feliz' "$work/$product" \
       -g '!README.md' -g '!packages.lock.json' -g '!package-lock.json' | grep -q .; then
    echo "bundle composition: player contains an accidental Babylon/React/Feliz closure" >&2; exit 1
  fi
done
assert_path "$work/Studio/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/Studio/SvgFoundation/Studio/packages.lock.json"
refute_path "$work/Studio/SvgFoundation/Examples"
assert_path "$work/Tactical/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/Tactical/SvgFoundation/Examples/Tactical/README.md"
assert_path "$work/Tactical/SvgFoundation/Examples/Tactical/scene.json"
assert_path "$work/Tactical/SvgFoundation/TacticalCompatibility.fs"
assert_path "$work/Tactical/SvgFoundation/Examples/Tactical/packages.lock.json"
refute_path "$work/Tactical/SvgFoundation/Examples/Arcade"
assert_path "$work/Arcade/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/Arcade/SvgFoundation/Examples/Arcade/README.md"
assert_path "$work/Arcade/SvgFoundation/Examples/Arcade/scene.json"
refute_path "$work/Arcade/SvgFoundation/Examples/Tactical"
assert_path "$work/Complete/SvgFoundation/Examples/Tactical/README.md"
assert_path "$work/Complete/SvgFoundation/Examples/Arcade/README.md"
refute_path "$work/Complete/SvgFoundation/PreviewDocument.fs"
assert_path "$work/LegacyTrue/SvgFoundation/Studio/Studio.fsproj"
assert_path "$work/LegacyTrue/SvgFoundation/Examples/Tactical/README.md"
refute_path "$work/LegacyFalse/SvgFoundation"

for lifecycle in none sdd typed-sdd spec-kit; do
  DOTNET_CLI_HOME="$home" dotnet new fs-gg-fable-game -n "Lifecycle${lifecycle//-/}" \
    -o "$work/Lifecycle${lifecycle//-/}" --bundle player --lifecycle "$lifecycle" >/dev/null
done

for pair in "player false" "studio false" "player true" "arcade true" "complete true"; do
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

# Valid response-file selection reaches the same grouped template contract.
response="$work/valid-response.rsp"
printf '%s\n' fs-gg-fable-game -n ResponseStudio -o "$work/ResponseStudio" --bundle studio --lifecycle none >"$response"
DOTNET_CLI_HOME="$home" dotnet new @"$response" >/dev/null
assert_path "$work/ResponseStudio/SvgFoundation/Studio/Studio.fsproj"

# A response file is a supported .NET host surface and can carry raw NUL even though argv cannot.
# Reproduce the superseded sentinel bypass exactly; the removed internal parameter must now be
# ordinary invalid input and the destination must remain byte-identical.
destination="$work/conflict-response-nul"
mkdir -p "$destination"
printf 'retained\n' >"$destination/sentinel"
response="$work/conflict-response-nul.rsp"
printf '%s\n' fs-gg-fable-game -n Conflict -o "$destination" --bundle player --svgFoundation false \
  --bundleCompatibilityConflict >"$response"
printf '\0\n' >>"$response"
if DOTNET_CLI_HOME="$home" dotnet new @"$response" >"$work/response-nul.log" 2>&1; then
  echo "bundle composition: raw-NUL response-file bypass was accepted" >&2; exit 1
fi
[[ "$(find "$destination" -mindepth 1 -maxdepth 1 -type f -printf '%f\n')" == sentinel ]] || {
  echo "bundle composition: raw-NUL response-file attempt wrote into $destination" >&2; exit 1;
}

destination="$work/conflict-response"
mkdir -p "$destination"
printf 'retained\n' >"$destination/sentinel"
response="$work/conflict-response.rsp"
printf '%s\n' fs-gg-fable-game -n Conflict -o "$destination" --bundle player --svgFoundation false >"$response"
if DOTNET_CLI_HOME="$home" dotnet new @"$response" >"$work/response.log" 2>&1; then
  echo "bundle composition: response-file contradiction was accepted" >&2; exit 1
fi
[[ "$(find "$destination" -mindepth 1 -maxdepth 1 -type f -printf '%f\n')" == sentinel ]] || {
  echo "bundle composition: response-file contradiction wrote into $destination" >&2; exit 1;
}

# Mixed argv/response input must enforce the same mutual exclusion before writes.
destination="$work/conflict-response-mixed"
mkdir -p "$destination"
printf 'retained\n' >"$destination/sentinel"
response="$work/conflict-response-mixed.rsp"
printf '%s\n' --svgFoundation false -o "$destination" >"$response"
if DOTNET_CLI_HOME="$home" dotnet new fs-gg-fable-game -n Conflict --bundle player @"$response" \
     >"$work/response-mixed.log" 2>&1; then
  echo "bundle composition: mixed response-file contradiction was accepted" >&2; exit 1
fi
[[ "$(find "$destination" -mindepth 1 -maxdepth 1 -type f -printf '%f\n')" == sentinel ]] || {
  echo "bundle composition: mixed response-file contradiction wrote into $destination" >&2; exit 1;
}

jq -e '.dependencies["net10.0"]["FSharp.Core"].resolved == "10.1.400"' \
  "$work/Player/SvgFoundation/packages.lock.json" \
  "$work/Studio/SvgFoundation/Studio/packages.lock.json" >/dev/null
grep -F 'artifacts/static-player' "$work/Player/build.sh" >/dev/null
grep -F 'artifacts/authority-server' "$work/Player/build.sh" >/dev/null
for deployment_path in \
  .dockerignore \
  deploy/authority.Dockerfile \
  deploy/Caddyfile \
  deploy/compose.yaml \
  deploy/compose.local.yaml \
  deploy/compose.production.yaml \
  deploy/container-engine.sh \
  deploy/install-vps.sh \
  deploy/activate-vps.sh \
  deploy/rollback-vps.sh \
  deploy/finalize-vps.sh \
  deploy/package-production.sh \
  deploy/deploy-production.sh \
  deploy/run-local.sh \
  deploy/verify-edge.sh \
  deploy/verify-edge.mjs \
  deploy/verify-production.sh
do
  assert_path "$work/Player/$deployment_path"
done
grep -F 'reverse_proxy {$GAME_UPSTREAM:authority:8080}' "$work/Player/deploy/Caddyfile" >/dev/null
! grep -F 'health_uri' "$work/Player/deploy/Caddyfile" >/dev/null
grep -F 'docker.io/library/caddy:2.10.2-alpine@sha256:' "$work/Player/deploy/compose.yaml" >/dev/null
grep -F 'dotnet/aspnet:10.0@sha256:' "$work/Player/deploy/authority.Dockerfile" >/dev/null
grep -F 'USER $APP_UID' "$work/Player/deploy/authority.Dockerfile" >/dev/null
grep -F 'context: .' "$work/Player/deploy/compose.yaml" >/dev/null
grep -F './deploy/Caddyfile:/etc/caddy/Caddyfile:ro' "$work/Player/deploy/compose.yaml" >/dev/null
grep -F './artifacts/releases/${SVG_RELEASE_VERSION:-workspace-v1}:/srv/release:ro' "$work/Player/deploy/compose.yaml" >/dev/null
grep -F 'bash "$root/deploy/verify-edge.sh"' "$work/Player/deploy/run-local.sh" >/dev/null
grep -F 'StrictHostKeyChecking=yes' "$work/Player/deploy/deploy-production.sh" >/dev/null
grep -F 'rollback_remote' "$work/Player/deploy/deploy-production.sh" >/dev/null
grep -F 'systemctl enable fsgg-fable-game.service' "$work/Player/deploy/activate-vps.sh" >/dev/null
grep -F 'serviceRestartVerified' "$work/Player/deploy/verify-production.sh" >/dev/null
grep -F 'HttpTransportType.WebSockets' "$work/Player/deploy/verify-edge.mjs" >/dev/null
grep -F 'payload: { version: 3, sessionCapability }' "$work/Player/deploy/verify-edge.mjs" >/dev/null
if DEPLOY_TARGET='root@example.com;false' GAME_SITE_ADDRESS=game.example.com \
    bash "$work/Player/deploy/deploy-production.sh" workspace-v1 >/dev/null 2>&1; then
  echo "bundle composition: production deploy accepted an unsafe SSH target" >&2; exit 1
fi
mkdir -p "$work/Player/artifacts/releases/archive-test"
printf 'archive-test\n' >"$work/Player/artifacts/releases/archive-test/VERSION"
(cd "$work/Player/artifacts/releases/archive-test" && sha256sum VERSION >SHA256SUMS)
archive_one="$work/archive-one.tar.gz"
archive_two="$work/archive-two.tar.gz"
bash "$work/Player/deploy/package-production.sh" archive-test "$archive_one" >/dev/null
bash "$work/Player/deploy/package-production.sh" archive-test "$archive_two" >/dev/null
cmp -s "$archive_one" "$archive_two" || {
  echo "bundle composition: identical production inputs produced different archives" >&2; exit 1
}

grep -F 'source: FS.GG.Workspace.Template::0.14.0' "$root/providers/fable-game.providers.yml" >/dev/null
if grep -A3 -- '- key: bundle' "$root/providers/fable-game.providers.yml" | grep -F 'default:' >/dev/null; then
  echo "bundle composition: provider must preserve bundle omission for legacy callers" >&2; exit 1
fi

echo "svg-workspace-bundles: default=player matrix=passed legacy=true/false contradiction=no-write lifecycle=preserved"
