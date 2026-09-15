#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then echo "retained VPS activation must run as root" >&2; exit 1; fi

deployment_id="${1:-}"
version="${2:-}"
expected_manifest_sha="${3:-}"
site_address="${4:-}"
upstream="${5:-authority:8080}"
app_root="/opt/fsgg-fable-game"

if [[ -L "$app_root/rollback-target" || -e "$app_root/rollback-target" || -e "$app_root/rollback-absent" \
    || -e /etc/fsgg-fable-game.rollback.env || -e /etc/fsgg-fable-game.rollback.service ]]; then
  echo "a production activation is already pending verification or rollback" >&2
  exit 1
fi

[[ "$deployment_id" =~ ^[A-Za-z0-9._-]+$ && "$deployment_id" != "." && "$deployment_id" != ".." ]] || {
  echo "invalid retained deployment id" >&2; exit 1;
}
[[ "$version" =~ ^[A-Za-z0-9._-]+$ && "$version" != "." && "$version" != ".." ]] || {
  echo "invalid retained release version" >&2; exit 1;
}
prefix="$version-"
[[ "$deployment_id" == "$prefix"* ]] || { echo "deployment id does not belong to release version" >&2; exit 1; }
archive_prefix="${deployment_id#"$prefix"}"
[[ "$archive_prefix" =~ ^[0-9a-f]{12}$ ]] || { echo "deployment id lacks its archive digest prefix" >&2; exit 1; }
[[ "$expected_manifest_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "invalid release manifest SHA-256" >&2; exit 1; }
[[ "$site_address" =~ ^([A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$ ]] || { echo "invalid public site address" >&2; exit 1; }
[[ "$upstream" =~ ^(https?://)?[A-Za-z0-9._-]+(:[0-9]{1,5})?$ ]] || { echo "invalid game upstream" >&2; exit 1; }

destination="$app_root/deployments/$deployment_id"
release="$destination/artifacts/releases/$version"
[[ -d "$release" && -f "$destination/deploy/compose.yaml" && -f "$destination/deploy/compose.production.yaml" ]] || {
  echo "retained deployment is incomplete or absent: $deployment_id" >&2; exit 1;
}
(cd "$release" && sha256sum --check --quiet SHA256SUMS)
[[ "$(sha256sum "$release/SHA256SUMS" | cut -d' ' -f1)" == "$expected_manifest_sha" ]] || {
  echo "retained deployment manifest does not match the expected digest" >&2; exit 1;
}
[[ -L "$app_root/current" && -f /etc/fsgg-fable-game.env && -f /etc/systemd/system/fsgg-fable-game.service ]] || {
  echo "retained rollback requires an active managed deployment" >&2; exit 1;
}

previous_target="$(readlink "$app_root/current")"
[[ "$previous_target" == "$app_root/deployments/"* && -d "$previous_target" ]] || {
  echo "current deployment target is invalid" >&2; exit 1;
}
rollback_env="$(mktemp)"
env_staging="$(mktemp /etc/fsgg-fable-game.env.XXXXXX)"
cleanup() { rm -f "$rollback_env" "$env_staging"; }
trap cleanup EXIT
cp /etc/fsgg-fable-game.env "$rollback_env"
ln -s "$previous_target" "$app_root/rollback-target"
install -m 0600 "$rollback_env" /etc/fsgg-fable-game.rollback.env
install -m 0644 /etc/systemd/system/fsgg-fable-game.service /etc/fsgg-fable-game.rollback.service

restore_prior() {
  trap - ERR
  systemctl stop fsgg-fable-game.service 2>/dev/null || true
  local restore_link="$app_root/.rollback.$deployment_id"
  rm -f "$restore_link"
  ln -s "$previous_target" "$restore_link"
  mv -T "$restore_link" "$app_root/current"
  install -m 0600 "$rollback_env" /etc/fsgg-fable-game.env
  install -m 0644 /etc/fsgg-fable-game.rollback.service /etc/systemd/system/fsgg-fable-game.service
  systemctl daemon-reload
  systemctl start fsgg-fable-game.service || true
  rm -f "$app_root/rollback-target" /etc/fsgg-fable-game.rollback.env \
    /etc/fsgg-fable-game.rollback.service
}
restore_on_error() {
  local status=$?
  echo "retained activation interrupted; restoring the prior deployment" >&2
  restore_prior
  exit "$status"
}
trap restore_on_error ERR

cat >"$env_staging" <<EOF
SVG_RELEASE_VERSION=$version
GAME_SITE_ADDRESS=$site_address
GAME_UPSTREAM=$upstream
CONTAINER_ENGINE=podman
EOF
chmod 0600 "$env_staging"

systemctl stop fsgg-fable-game.service
link_staging="$app_root/.retained.$deployment_id"
ln -s "$destination" "$link_staging"
mv -T "$link_staging" "$app_root/current"
install -m 0600 "$env_staging" /etc/fsgg-fable-game.env

if ! systemctl start fsgg-fable-game.service; then
  echo "retained activation failed; restoring the prior deployment" >&2
  restore_prior
  exit 1
fi

trap - ERR
echo "retained production activation passed: deployment=$deployment_id version=$version host=$site_address"
