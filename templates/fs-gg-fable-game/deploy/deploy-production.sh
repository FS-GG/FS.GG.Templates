#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${DEPLOY_TARGET:-}"
site_address="${GAME_SITE_ADDRESS:-}"
version="${1:-${SVG_RELEASE_VERSION:-}}"
upstream="${GAME_UPSTREAM:-authority:8080}"

[[ "$target" =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9._:-]+$ ]] || {
  echo "DEPLOY_TARGET must be an explicit user@host SSH target" >&2; exit 1;
}
[[ "$site_address" =~ ^([A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$ ]] || {
  echo "GAME_SITE_ADDRESS must be one public DNS host name without a scheme or path" >&2; exit 1;
}
[[ "$version" =~ ^[A-Za-z0-9._-]+$ && "$version" != "." && "$version" != ".." ]] || {
  echo "supply an immutable release version as argument or SVG_RELEASE_VERSION" >&2; exit 1;
}
[[ "$upstream" =~ ^(https?://)?[A-Za-z0-9._-]+(:[0-9]{1,5})?$ ]] || {
  echo "GAME_UPSTREAM must be a bounded host[:port] or http(s) URL without a path" >&2; exit 1;
}
for required in ssh tar gzip sha256sum curl openssl node; do command -v "$required" >/dev/null; done
ssh_options=(-o BatchMode=yes -o StrictHostKeyChecking=yes)
if [[ -n "${DEPLOY_SSH_KEY_FILE:-}" ]]; then
  [[ -f "$DEPLOY_SSH_KEY_FILE" ]] || { echo "DEPLOY_SSH_KEY_FILE does not exist" >&2; exit 1; }
  ssh_options+=(-i "$DEPLOY_SSH_KEY_FILE")
fi
if [[ -n "${DEPLOY_KNOWN_HOSTS_FILE:-}" ]]; then
  [[ -f "$DEPLOY_KNOWN_HOSTS_FILE" ]] || { echo "DEPLOY_KNOWN_HOSTS_FILE does not exist" >&2; exit 1; }
  ssh_options+=(-o "UserKnownHostsFile=$DEPLOY_KNOWN_HOSTS_FILE")
fi

release="$root/artifacts/releases/$version"
[[ -d "$release" ]] || { echo "missing immutable release: $release" >&2; exit 1; }
(cd "$release" && sha256sum --check --quiet SHA256SUMS)

if [[ "${BOOTSTRAP_VPS:-false}" == true ]]; then
  ssh "${ssh_options[@]}" "$target" \
    'sudo -n bash -s' <"$root/deploy/install-vps.sh"
fi

archive="$(mktemp --suffix=.tar.gz)"
activation_pending=false
rollback_remote() {
  ssh "${ssh_options[@]}" "$target" \
    'sudo -n bash -s' <"$root/deploy/rollback-vps.sh"
}
cleanup() {
  rm -f "$archive"
  if [[ "$activation_pending" == true ]]; then rollback_remote || true; fi
}
trap cleanup EXIT
bash "$root/deploy/package-production.sh" "$version" "$archive"
archive_sha="$(sha256sum "$archive" | cut -d' ' -f1)"
remote_archive="/tmp/fsgg-$version-${archive_sha:0:12}.tar.gz"

ssh "${ssh_options[@]}" "$target" "cat >$remote_archive" <"$archive"
ssh "${ssh_options[@]}" "$target" \
  "sudo -n bash -s -- $remote_archive $archive_sha $version $site_address $upstream" \
  <"$root/deploy/activate-vps.sh"
activation_pending=true

if ! GAME_EDGE_URL="https://$site_address" bash "$root/deploy/verify-production.sh" "$version"; then
  exit 1
fi
if [[ "${VERIFY_SERVICE_RESTART:-true}" == true ]]; then
  if ! ssh "${ssh_options[@]}" "$target" \
      'sudo -n systemctl restart fsgg-fable-game.service && sudo -n systemctl is-enabled --quiet fsgg-fable-game.service'; then
    exit 1
  fi
  if ! GAME_EDGE_URL="https://$site_address" SERVICE_RESTART_VERIFIED=true \
      bash "$root/deploy/verify-production.sh" "$version"; then
    exit 1
  fi
fi
ssh "${ssh_options[@]}" "$target" \
  'sudo -n bash -s' <"$root/deploy/finalize-vps.sh"
activation_pending=false
echo "production deployment passed: version=$version url=https://$site_address archive_sha256=$archive_sha"
