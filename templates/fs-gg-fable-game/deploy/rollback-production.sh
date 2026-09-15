#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${DEPLOY_TARGET:-}"
site_address="${GAME_SITE_ADDRESS:-}"
upstream="${GAME_UPSTREAM:-authority:8080}"
deployment_id="${1:-${RETAINED_DEPLOYMENT_ID:-}}"
version="${2:-${SVG_RELEASE_VERSION:-}}"
manifest_sha="${3:-${EXPECTED_RELEASE_MANIFEST_SHA:-}}"

[[ "$target" =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9._:-]+$ ]] || { echo "invalid DEPLOY_TARGET" >&2; exit 1; }
[[ "$site_address" =~ ^([A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$ ]] || { echo "invalid GAME_SITE_ADDRESS" >&2; exit 1; }
[[ "$deployment_id" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid retained deployment id" >&2; exit 1; }
[[ "$version" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid retained release version" >&2; exit 1; }
[[ "$manifest_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "invalid retained manifest SHA-256" >&2; exit 1; }
[[ "$upstream" =~ ^(https?://)?[A-Za-z0-9._-]+(:[0-9]{1,5})?$ ]] || { echo "invalid GAME_UPSTREAM" >&2; exit 1; }

ssh_options=(-o BatchMode=yes -o StrictHostKeyChecking=yes)
if [[ -n "${DEPLOY_SSH_KEY_FILE:-}" ]]; then
  [[ -f "$DEPLOY_SSH_KEY_FILE" ]] || { echo "DEPLOY_SSH_KEY_FILE does not exist" >&2; exit 1; }
  ssh_options+=(-i "$DEPLOY_SSH_KEY_FILE")
fi
if [[ -n "${DEPLOY_KNOWN_HOSTS_FILE:-}" ]]; then
  [[ -f "$DEPLOY_KNOWN_HOSTS_FILE" ]] || { echo "DEPLOY_KNOWN_HOSTS_FILE does not exist" >&2; exit 1; }
  ssh_options+=(-o "UserKnownHostsFile=$DEPLOY_KNOWN_HOSTS_FILE")
fi

activation_pending=false
cleanup() {
  if [[ "$activation_pending" == true ]]; then
    ssh "${ssh_options[@]}" "$target" 'sudo -n bash -s' <"$root/deploy/rollback-vps.sh" || true
  fi
}
trap cleanup EXIT

ssh "${ssh_options[@]}" "$target" \
  "sudo -n bash -s -- $deployment_id $version $manifest_sha $site_address $upstream" \
  <"$root/deploy/activate-retained-vps.sh"
activation_pending=true

verify() {
  GAME_EDGE_URL="https://$site_address" EXPECTED_RELEASE_MANIFEST_SHA="$manifest_sha" \
    DEPLOYMENT_OPERATION=rollback DEPLOYMENT_ID="$deployment_id" \
    bash "$root/deploy/verify-production.sh" "$version"
}
verify
ssh "${ssh_options[@]}" "$target" \
  'sudo -n systemctl restart fsgg-fable-game.service && sudo -n systemctl is-enabled --quiet fsgg-fable-game.service'
SERVICE_RESTART_VERIFIED=true verify
ssh "${ssh_options[@]}" "$target" 'sudo -n bash -s' <"$root/deploy/finalize-vps.sh"
activation_pending=false
echo "retained production rollback passed: deployment=$deployment_id version=$version url=https://$site_address"
