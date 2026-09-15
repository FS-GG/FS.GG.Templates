#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-${SVG_RELEASE_VERSION:-}}"
base="${GAME_EDGE_URL:-}"
evidence="${SVG_DEPLOYMENT_EVIDENCE:-$root/artifacts/deployment-evidence/$version.json}"

[[ "$version" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid production release version" >&2; exit 1; }
[[ "$base" =~ ^https://([^/:]+)(:[0-9]{1,5})?$ ]] || {
  echo "GAME_EDGE_URL must be a public https URL without a path" >&2; exit 1;
}
host="${BASH_REMATCH[1]}"
port="${BASH_REMATCH[2]#:}"
port="${port:-443}"

ready=false
for _ in {1..120}; do
  if curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$base/healthz" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || { echo "public TLS edge did not become healthy within 120 seconds" >&2; exit 1; }
bash "$root/deploy/verify-edge.sh" "$version"

certificate="$(openssl s_client -connect "$host:$port" -servername "$host" </dev/null 2>/dev/null \
  | openssl x509 -noout -fingerprint -sha256 -issuer -subject -enddate)"
cert_fingerprint="$(printf '%s\n' "$certificate" | sed -n 's/^sha256 Fingerprint=//p')"
cert_issuer="$(printf '%s\n' "$certificate" | sed -n 's/^issuer=//p')"
cert_subject="$(printf '%s\n' "$certificate" | sed -n 's/^subject=//p')"
cert_not_after="$(printf '%s\n' "$certificate" | sed -n 's/^notAfter=//p')"
[[ -n "$cert_fingerprint" && -n "$cert_not_after" ]] || { echo "trusted certificate readback failed" >&2; exit 1; }

mkdir -p "$(dirname "$evidence")"
VERSION="$version" BASE_URL="$base" EVIDENCE_PATH="$evidence" \
CERT_FINGERPRINT="$cert_fingerprint" CERT_ISSUER="$cert_issuer" CERT_SUBJECT="$cert_subject" \
CERT_NOT_AFTER="$cert_not_after" RELEASE_MANIFEST_SHA="$(sha256sum "$root/artifacts/releases/$version/SHA256SUMS" | cut -d' ' -f1)" \
SERVICE_RESTART_VERIFIED="${SERVICE_RESTART_VERIFIED:-false}" \
node --input-type=module <<'EOF'
import { writeFileSync } from "node:fs";
const evidence = {
  schema: "fsgg.svg.deployment-evidence/v1",
  observedAtUtc: new Date().toISOString(),
  result: "passed",
  releaseVersion: process.env.VERSION,
  baseUrl: process.env.BASE_URL,
  releaseManifestSha256: process.env.RELEASE_MANIFEST_SHA,
  servedIdentity: "matched",
  httpBootstrap: "passed",
  signalRWebSocket: "passed",
  twoClientV3Reconnect: "passed",
  serviceRestartVerified: process.env.SERVICE_RESTART_VERIFIED === "true",
  certificate: {
    sha256Fingerprint: process.env.CERT_FINGERPRINT,
    issuer: process.env.CERT_ISSUER,
    subject: process.env.CERT_SUBJECT,
    notAfter: process.env.CERT_NOT_AFTER
  },
  secretsRecorded: false
};
writeFileSync(process.env.EVIDENCE_PATH, `${JSON.stringify(evidence, null, 2)}\n`, { mode: 0o600 });
EOF
echo "production verification passed: version=$version url=$base evidence=$evidence"
