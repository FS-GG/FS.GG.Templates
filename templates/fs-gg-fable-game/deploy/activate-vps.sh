#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "VPS activation must run as root" >&2
  exit 1
fi

archive="${1:-}"
expected_archive_sha="${2:-}"
version="${3:-}"
site_address="${4:-}"
upstream="${5:-authority:8080}"
app_root="/opt/fsgg-fable-game"

[[ -f "$archive" ]] || { echo "activation archive is missing" >&2; exit 1; }
[[ "$expected_archive_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "invalid archive SHA-256" >&2; exit 1; }
[[ "$version" =~ ^[A-Za-z0-9._-]+$ && "$version" != "." && "$version" != ".." ]] || {
  echo "invalid immutable release version" >&2; exit 1;
}
[[ "$site_address" =~ ^([A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$ ]] || {
  echo "GAME_SITE_ADDRESS must be one public DNS host name without a scheme or path" >&2; exit 1;
}
[[ "$upstream" =~ ^(https?://)?[A-Za-z0-9._-]+(:[0-9]{1,5})?$ ]] || {
  echo "GAME_UPSTREAM must be a bounded host[:port] or http(s) URL without a path" >&2; exit 1;
}
expected_archive="/tmp/fsgg-$version-${expected_archive_sha:0:12}.tar.gz"
[[ "$archive" == "$expected_archive" ]] || { echo "activation archive path is not the bounded upload path" >&2; exit 1; }
command -v podman >/dev/null
podman compose version >/dev/null
command -v systemctl >/dev/null

observed_archive_sha="$(sha256sum "$archive" | cut -d' ' -f1)"
[[ "$observed_archive_sha" == "$expected_archive_sha" ]] || {
  echo "activation archive SHA-256 mismatch" >&2; exit 1;
}

deployment_id="$version-${expected_archive_sha:0:12}"
destination="$app_root/deployments/$deployment_id"
install -d -m 0755 "$app_root/deployments"
staging="$(mktemp -d "$app_root/deployments/.incoming.XXXXXX")"
cleanup() {
  if [[ -n "$staging" ]]; then rm -rf "$staging"; fi
  rm -f "$archive"
}
trap cleanup EXIT
tar --extract --gzip --file "$archive" --directory "$staging" --no-same-owner

release="$staging/artifacts/releases/$version"
[[ -d "$release" ]] || { echo "archive does not contain release $version" >&2; exit 1; }
(cd "$release" && sha256sum --check --quiet SHA256SUMS)
[[ -f "$staging/deploy/compose.yaml" && -f "$staging/deploy/compose.production.yaml" ]] || {
  echo "archive does not contain the production Compose definition" >&2; exit 1;
}

if [[ -d "$destination" ]]; then
  diff --recursive --quiet "$staging" "$destination" >/dev/null || {
    echo "retained deployment id contains different bytes: $deployment_id" >&2; exit 1;
  }
  rm -rf "$staging"
  staging=""
else
  chmod -R go-w "$staging"
  mv "$staging" "$destination"
  staging=""
fi

env_staging="$(mktemp /etc/fsgg-fable-game.env.XXXXXX)"
unit_staging="$(mktemp /etc/fsgg-fable-game.service.XXXXXX)"
rollback_env="$(mktemp)"
previous_target=""
if [[ -L "$app_root/current" ]]; then previous_target="$(readlink "$app_root/current")"; fi
if [[ -f /etc/fsgg-fable-game.env ]]; then cp /etc/fsgg-fable-game.env "$rollback_env"; fi
rm -f "$app_root/rollback-target" "$app_root/rollback-absent" /etc/fsgg-fable-game.rollback.env
if [[ -n "$previous_target" && -s "$rollback_env" ]]; then
  ln -s "$previous_target" "$app_root/rollback-target"
  install -m 0600 "$rollback_env" /etc/fsgg-fable-game.rollback.env
else
  install -m 0600 /dev/null "$app_root/rollback-absent"
fi

cat >"$env_staging" <<EOF
SVG_RELEASE_VERSION=$version
GAME_SITE_ADDRESS=$site_address
GAME_UPSTREAM=$upstream
CONTAINER_ENGINE=podman
EOF
chmod 0600 "$env_staging"

cat >"$unit_staging" <<'EOF'
[Unit]
Description=FS.GG Fable game edge
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/fsgg-fable-game/current
EnvironmentFile=/etc/fsgg-fable-game.env
ExecStart=/usr/bin/podman compose --project-directory . -f deploy/compose.yaml -f deploy/compose.production.yaml up --detach --build --remove-orphans
ExecStop=/usr/bin/podman compose --project-directory . -f deploy/compose.yaml -f deploy/compose.production.yaml down --remove-orphans
TimeoutStartSec=900
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
EOF

if systemctl is-active --quiet fsgg-fable-game.service; then systemctl stop fsgg-fable-game.service; fi
link_staging="$app_root/.current.$deployment_id"
ln -s "$destination" "$link_staging"
mv -T "$link_staging" "$app_root/current"
install -m 0600 "$env_staging" /etc/fsgg-fable-game.env
install -m 0644 "$unit_staging" /etc/systemd/system/fsgg-fable-game.service
rm -f "$env_staging" "$unit_staging"
systemctl daemon-reload
systemctl enable fsgg-fable-game.service >/dev/null

if ! systemctl start fsgg-fable-game.service; then
  echo "activation failed; restoring the prior deployment" >&2
  systemctl stop fsgg-fable-game.service 2>/dev/null || true
  if [[ -n "$previous_target" && -s "$rollback_env" ]]; then
    link_staging="$app_root/.rollback.$deployment_id"
    ln -s "$previous_target" "$link_staging"
    mv -T "$link_staging" "$app_root/current"
    install -m 0600 "$rollback_env" /etc/fsgg-fable-game.env
    systemctl start fsgg-fable-game.service || true
  else
    rm -f "$app_root/current" /etc/fsgg-fable-game.env
  fi
  rm -f "$app_root/rollback-target" "$app_root/rollback-absent" /etc/fsgg-fable-game.rollback.env
  exit 1
fi

rm -f "$rollback_env"
trap - EXIT
rm -f "$archive"
echo "production activation passed: deployment=$deployment_id version=$version host=$site_address"
