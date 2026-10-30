#!/bin/bash
# Rebuild the committed Noble IME facility manifest from this repository. Needs: rootless podman, python3 (>=3.12),
# gpgv, network access to snapshot.ubuntu.com, and a PUBLIC CA bundle for the container's apt (the base image has no
# ca-certificates). Nothing secret is read or written. Run from a checkout, under a bounded scope, e.g.
#   systemd-run --user --scope -p CPUQuota=300% -p MemoryMax=6G bash prepare/reproduce.sh "$(mktemp -d)"
# The result must equal noble-20261024.{manifest,package-request}.json byte for byte (checked at the end).
set -euo pipefail
OUT=$(realpath "$1"); test -d "$OUT" && test -z "$(ls -A "$OUT")" || { echo "need an empty private output directory" >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd); FAC=$(dirname "$HERE"); GAME=$(dirname "$FAC")
IMAGE=docker.io/library/ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
CA=${CA_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}
chmod 700 "$OUT"; mkdir "$OUT/in" "$OUT/out"
podman pull -q "$IMAGE" >/dev/null
podman run --rm "$IMAGE" cat /usr/share/keyrings/ubuntu-archive-keyring.gpg > "$OUT/in/keyring.gpg"
echo "80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31  $OUT/in/keyring.gpg" | sha256sum --check --strict
cp "$CA" "$OUT/in/ca.crt"
# the 32 exact roots come from the committed no-install source request, not from a hand-kept list
python3 -I - "$GAME/fixtures/noble-source-prefix-request.json" > "$OUT/in/roots.txt" <<'PY'
import json, sys
for p in json.load(open(sys.argv[1]))['packages']: print(p['name'] + '=' + p['version'])
PY
cp "$HERE/install-in-container.sh" "$HERE/extract-installed.py" "$HERE/crosscheck-archives.py" "$OUT/in/"
chmod +x "$OUT/in/install-in-container.sh"
NAME=fsgg-ime-facility-$$; trap 'podman rm -f "$NAME" >/dev/null 2>&1 || true; podman rmi -f "$NAME-img" >/dev/null 2>&1 || true' EXIT
podman run --name "$NAME" -v "$OUT/in:/in:ro" -v "$OUT/out:/out" "$IMAGE" /in/install-in-container.sh >/dev/null
podman commit -q "$NAME" "$NAME-img" >/dev/null
podman run --rm -v "$OUT/in:/in:ro" -v "$OUT/out:/out" "$NAME-img" python3 /in/extract-installed.py
# signed metadata and archive-only acquisition through the maintained helper (absolute keyring path; HOME is private)
env -i PATH=/usr/sbin:/usr/bin:/bin LANG=C.UTF-8 HOME="$OUT" PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B "$GAME/current-reference-noble-acquisition.py" --metadata-only "$OUT/metadata" --keyring "$OUT/in/keyring.gpg"
python3 -I -B "$HERE/build-package-request.py" "$GAME/current-reference-noble-acquisition.py" "$OUT/metadata" "$OUT/out/draft.json" "$OUT/package-request.json"
env -i PATH=/usr/sbin:/usr/bin:/bin LANG=C.UTF-8 HOME="$OUT" PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B "$GAME/current-reference-noble-acquisition.py" --package-request "$OUT/package-request.json" --keyring "$OUT/in/keyring.gpg" "$OUT/acq"
python3 -I -B "$HERE/assemble-manifest.py" "$GAME/current-reference-native-input.py" "$OUT/out/draft.json" "$OUT/package-request.json" "$OUT/manifest.json"
podman run --rm -v "$OUT/in:/in:ro" -v "$OUT/manifest.json:/out/manifest.json:ro" -v "$OUT/acq:/acq:ro" "$NAME-img" python3 /in/crosscheck-archives.py
cmp "$OUT/package-request.json" "$FAC/noble-20261024.package-request.json"
cmp "$OUT/manifest.json" "$FAC/noble-20261024.manifest.json"
cmp "$OUT/out/installed-packages.txt" "$FAC/noble-20261024.closure.txt"
echo "REPRODUCED: manifest, package request and closure equal the committed files"
