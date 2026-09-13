#!/usr/bin/env bash
set -euo pipefail
address="${1:?studio address required}"
output="${2:?observation output required}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${SVG_ORCA_INNER:-}" != 1 ]]; then
  exec dbus-run-session -- env SVG_ORCA_INNER=1 xvfb-run -a bash "$0" "$address" "$output"
fi

export NO_AT_BRIDGE=0 GTK_MODULES="${GTK_MODULES:-gail:atk-bridge}"
gsettings set org.gnome.desktop.interface toolkit-accessibility true
gsettings set org.gnome.desktop.a11y.applications screen-reader-enabled true
orca --replace >"$output.orca.log" 2>&1 & orca_pid=$!
sleep 3
browser_bin="${PLAYWRIGHT_EXECUTABLE_PATH:-$(command -v chromium || command -v chromium-browser)}"
"$browser_bin" --no-sandbox --force-renderer-accessibility --user-data-dir="$(mktemp -d)" "$address" >"$output.browser.log" 2>&1 & browser_pid=$!
cleanup() { kill "$browser_pid" "$orca_pid" 2>/dev/null || true; }
trap cleanup EXIT
ORCA_PID="$orca_pid" BROWSER_PID="$browser_pid" python3 "$script_dir/svg-authoring-orca.py" "$output"
