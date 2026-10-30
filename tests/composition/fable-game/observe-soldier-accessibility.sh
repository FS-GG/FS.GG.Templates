#!/usr/bin/env bash
# Container-qualified accessible-alternative and focus observation of the actual
# generated soldier player (SVG-COHERENCE-01.5). It consumes the staged candidate
# that verify-soldier-reference-candidate.sh already built (published generated
# Server plus the sealed webroot), serves it once on a task-owned loopback port,
# runs the accessibility-tree observer and the Orca observer, and stops only the
# server it started. It rebuilds nothing and gains no endpoint, credential or
# checkout access.
#
#   observe-soldier-accessibility.sh <staged-out> <fixture-work> <evidence-dir> [orca]
#
# Required environment: PLAYWRIGHT_MODULE_ROOT (node_modules holding @playwright/test),
# SOLDIER_AXE_JS (pinned axe-core axe.min.js). Optional: PLAYWRIGHT_EXECUTABLE_PATH,
# SOLDIER_A11Y_FAMILIES (default "chromium", e.g. "chromium firefox webkit").
# The final "orca" argument adds the Orca/AT-SPI baseline and its causal controls,
# which need the Xvfb/dbus/Orca/xdotool toolchain used by observe-soldier-orca.sh.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
staged="$(realpath "${1:?staged consumer output directory required}")"
fixture="$(realpath "${2:?fixture work directory required}")"
evidence="${3:?empty evidence directory required}"
with_orca="${4:-}"
: "${PLAYWRIGHT_MODULE_ROOT:?Playwright module root required}" "${SOLDIER_AXE_JS:?pinned axe-core path required}"
[[ ! -e "$evidence" ]] || { echo "evidence directory must be absent" >&2; exit 1; }
[[ -f "$staged/server/Server.dll" && -f "$fixture/Browser/dist/soldier-player/index.html" && -f "$SOLDIER_AXE_JS" ]]
mkdir -p "$evidence" "$evidence/server-home"
evidence="$(realpath "$evidence")"

server=''
server_start=''
origin=''
stop_server() {
  [[ -n "$server" ]] || return 0
  if [[ -r "/proc/$server/stat" ]]; then
    [[ "$(awk '{print $22}' "/proc/$server/stat")" == "$server_start" ]] || { echo 'server custody changed; refusing kill' >&2; return 1; }
    kill -TERM "$server" 2>/dev/null || true
  fi
  wait "$server" 2>/dev/null || true
  if kill -0 "$server" 2>/dev/null; then echo "server cleanup unknown: process remains $server" >&2; return 1; fi
  server=''
}
trap stop_server EXIT

# Same sealed webroot and generated server the staged functional profile used.
(cd "$staged/server" && exec timeout --signal=TERM --kill-after=5s 1800s \
  env -i PATH="$PATH" DOTNET_ROOT="${DOTNET_ROOT:-/usr/share/dotnet}" DOTNET_CLI_HOME="$evidence/server-home" \
  ASPNETCORE_ENVIRONMENT=Production dotnet "$staged/server/Server.dll" --urls http://127.0.0.1:0 --webroot "$fixture/Browser/dist") \
  >"$evidence/server.log" 2>&1 & server=$!
server_start="$(awk '{print $22}' "/proc/$server/stat")"
for _ in {1..120}; do
  origin="$(sed -nE 's@.*Now listening on: (http://127\.0\.0\.1:[0-9]+).*@\1@p' "$evidence/server.log" | head -1)"
  [[ -z "$origin" ]] || break
  kill -0 "$server" 2>/dev/null || { tail -n 80 "$evidence/server.log" >&2; exit 1; }
  sleep .25
done
[[ "$origin" =~ ^http://127\.0\.0\.1:[0-9]+$ ]]
curl -fsS "$origin/healthz" >/dev/null

executable_args=()
[[ -z "${PLAYWRIGHT_EXECUTABLE_PATH:-}" ]] || executable_args=(--executable "$PLAYWRIGHT_EXECUTABLE_PATH")
for family in ${SOLDIER_A11Y_FAMILIES:-chromium}; do
  mode=observe; [[ "$family" != chromium ]] || mode=all
  timeout --signal=TERM --kill-after=15s 20m node "$script_dir/soldier-accessibility-observe.mjs" \
    --base-url "$origin/" --out "$evidence/soldier-accessibility-$family.json" --module-root "$PLAYWRIGHT_MODULE_ROOT" \
    --axe "$SOLDIER_AXE_JS" --family "$family" --mode "$mode" --deadline-ms 1080000 "${executable_args[@]}" \
    >"$evidence/soldier-accessibility-$family.log" 2>&1 || { tail -n 20 "$evidence/soldier-accessibility-$family.log" >&2; exit 1; }
done

if [[ "$with_orca" == orca ]]; then
  player="$origin/soldier-player/index.html"
  export SVG_ORCA_BROWSER_FAMILY=chromium
  timeout --signal=TERM --kill-after=15s 6m bash "$script_dir/observe-soldier-orca.sh" "$player" "$evidence/soldier-orca-baseline.json" \
    >"$evidence/soldier-orca-baseline.log" 2>&1 || { tail -n 30 "$evidence/soldier-orca-baseline.log" >&2; exit 1; }
  for mutant in unnamed-roster-button no-focus-transfer silent-status; do
    # Each control must be refused (exit 3) by its own Orca/AT-SPI observation.
    status=0
    SOLDIER_ORCA_MUTANT="$mutant" timeout --signal=TERM --kill-after=15s 6m bash "$script_dir/observe-soldier-orca.sh" "$player" "$evidence/soldier-orca-$mutant.json" \
      >"$evidence/soldier-orca-$mutant.log" 2>&1 || status=$?
    [[ "$status" == 3 ]] || { echo "orca control $mutant was not refused (exit $status)" >&2; tail -n 30 "$evidence/soldier-orca-$mutant.log" >&2; exit 1; }
  done
fi
stop_server
trap - EXIT
python3 "$script_dir/test-soldier-accessibility.py" --verify "$evidence" ${with_orca:+--orca}
printf 'soldier-accessibility: verified; evidence=%s\n' "$evidence"
