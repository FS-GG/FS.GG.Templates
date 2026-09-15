#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then echo "VPS finalization must run as root" >&2; exit 1; fi
rm -f /opt/fsgg-fable-game/rollback-target /opt/fsgg-fable-game/rollback-absent \
  /etc/fsgg-fable-game.rollback.env /etc/fsgg-fable-game.rollback.service
systemctl is-active --quiet fsgg-fable-game.service
systemctl is-enabled --quiet fsgg-fable-game.service
echo "production activation finalized"
