#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then echo "VPS rollback must run as root" >&2; exit 1; fi
app_root="/opt/fsgg-fable-game"

if [[ -L "$app_root/rollback-target" && -f /etc/fsgg-fable-game.rollback.env \
    && -f /etc/fsgg-fable-game.rollback.service ]]; then
  previous_target="$(readlink "$app_root/rollback-target")"
  [[ "$previous_target" == "$app_root/deployments/"* && -d "$previous_target" ]] || {
    echo "refusing an invalid retained rollback target" >&2; exit 1;
  }
  systemctl stop fsgg-fable-game.service 2>/dev/null || true
  link_staging="$app_root/.rollback.$(date +%s)"
  ln -s "$previous_target" "$link_staging"
  mv -T "$link_staging" "$app_root/current"
  install -m 0600 /etc/fsgg-fable-game.rollback.env /etc/fsgg-fable-game.env
  install -m 0644 /etc/fsgg-fable-game.rollback.service /etc/systemd/system/fsgg-fable-game.service
  systemctl daemon-reload
  systemctl start fsgg-fable-game.service
  echo "restored prior production deployment: $previous_target"
elif [[ -f "$app_root/rollback-absent" ]]; then
  systemctl stop fsgg-fable-game.service 2>/dev/null || true
  systemctl disable fsgg-fable-game.service >/dev/null 2>&1 || true
  rm -f "$app_root/current" /etc/fsgg-fable-game.env /etc/systemd/system/fsgg-fable-game.service
  systemctl daemon-reload
  echo "removed failed first production activation; no prior deployment existed"
else
  echo "no pending production activation can be rolled back" >&2
  exit 1
fi
rm -f "$app_root/rollback-target" "$app_root/rollback-absent" \
  /etc/fsgg-fable-game.rollback.env /etc/fsgg-fable-game.rollback.service
