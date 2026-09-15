#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "VPS bootstrap must run as root (normally through passwordless sudo)" >&2
  exit 1
fi

source /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:24.04|debian:12) ;;
  *)
    echo "VPS bootstrap supports Ubuntu 24.04 LTS or Debian 12; found ${PRETTY_NAME:-unknown}" >&2
    exit 1
    ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes ca-certificates curl podman podman-compose unattended-upgrades

install -d -m 0755 /opt/fsgg-fable-game/deployments
systemctl enable --now unattended-upgrades.service
if systemctl list-unit-files podman-restart.service --no-legend | grep -q '^podman-restart.service'; then
  systemctl enable podman-restart.service
fi

podman --version
podman compose version
echo "VPS bootstrap passed; ensure inbound TCP 22, 80 and 443 are allowed by the provider firewall"
