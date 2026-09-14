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

speechd_root="$(mktemp -d)"
speechd_config="$speechd_root/config"
speechd_logs="$output.speechd-logs"
speechd_socket="$speechd_root/speechd.sock"
mkdir -p "$speechd_config/modules" "$speechd_logs"
cp /etc/speech-dispatcher/speechd.conf "$speechd_config/speechd.conf"
cp /etc/speech-dispatcher/modules/espeak-ng.conf "$speechd_config/modules/espeak-ng.conf"
sed -Ei 's/^([[:space:]]*(CommunicationMethod|SocketPath|AudioOutputMethod|AudioPulseDevice|AddModule|DefaultModule|DisableAutoSpawn)([[:space:]]|$))/# isolated override: \1/' "$speechd_config/speechd.conf"
cat >>"$speechd_config/speechd.conf" <<EOF
CommunicationMethod "unix_socket"
SocketPath "$speechd_socket"
AudioOutputMethod "pulse"
AudioPulseDevice "svg_orca"
AddModule "espeak-ng" "sd_espeak-ng" "espeak-ng.conf"
DefaultModule espeak-ng
DisableAutoSpawn
EOF

pulseaudio --start --exit-idle-time=-1 --log-target="file:$output.pulseaudio.log"
null_sink_module="$(pactl load-module module-null-sink sink_name=svg_orca sink_properties=device.description=SVG_Orca_Null_Sink)"
pactl set-default-sink svg_orca
speech-dispatcher -s -C "$speechd_config" -S "$speechd_socket" -P "$speechd_root/speechd.pid" -L "$speechd_logs" -t 0 \
  >"$output.speechd.log" 2>&1 & speechd_pid=$!
orca_pid=""
browser_pid=""
cleanup() {
  [[ -z "$browser_pid" ]] || kill "$browser_pid" 2>/dev/null || true
  [[ -z "$orca_pid" ]] || kill "$orca_pid" 2>/dev/null || true
  kill "$speechd_pid" 2>/dev/null || true
  pactl unload-module "$null_sink_module" 2>/dev/null || true
  rm -rf "$speechd_root"
}
trap cleanup EXIT
for _ in {1..80}; do [[ -S "$speechd_socket" ]] && break; sleep .1; done
test -S "$speechd_socket"
export SPEECHD_ADDRESS="unix_socket:$speechd_socket"
timeout --signal=TERM --kill-after=5s 30s /usr/bin/python3 "$script_dir/speech-dispatcher-preflight.py" \
  "$output.speechd-preflight.json"

/usr/bin/python3 "$script_dir/orca-faulthandler.py" --replace --debug \
  --debug-file="$output.orca-debug.log" >"$output.orca.log" 2>&1 & orca_pid=$!
sleep 3
browser_bin="${PLAYWRIGHT_EXECUTABLE_PATH:-$(command -v chromium || command -v chromium-browser)}"
browser_family="${SVG_ORCA_BROWSER_FAMILY:-chromium}"
if [[ "$browser_family" == firefox ]]; then
  browser_profile="$(mktemp -d)"
  MOZ_ENABLE_WAYLAND=0 "$browser_bin" --profile "$browser_profile" --new-instance "$address" >"$output.browser.log" 2>&1 & browser_pid=$!
  browser_class='firefox|Navigator'
elif [[ "$browser_family" == chromium ]]; then
  "$browser_bin" --no-sandbox --force-renderer-accessibility --user-data-dir="$(mktemp -d)" "$address" >"$output.browser.log" 2>&1 & browser_pid=$!
  browser_class='chromium|google-chrome'
else
  echo "unsupported Orca browser family: $browser_family" >&2
  exit 2
fi
browser_window="$(timeout --signal=TERM --kill-after=5s 45s xdotool search --sync --onlyvisible --class "$browser_class" | tail -1)"
xdotool windowfocus --sync "$browser_window"
ORCA_PID="$orca_pid" BROWSER_PID="$browser_pid" SVG_ORCA_BROWSER_FAMILY="$browser_family" \
  /usr/bin/python3 "$script_dir/svg-input-orca.py" "$output"
