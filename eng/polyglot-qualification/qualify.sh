#!/usr/bin/env bash
# Run the fixed once-packed four-product qualification for ONE archive inside the carrier (<=4 CPUs).
# usage: qualify.sh <carrier-root> <archive.nupkg> <absent-attempt-name>
# Writes <carrier-root>/work/<attempt>/ and prints its path; scripts/polyglot/qualify-once-packed.sh does the work.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CHECKOUT="$(cd "$HERE/../.." && pwd -P)"
ROOT="${1:?carrier root}"; ARCHIVE="$(readlink -f "${2:?archive}")"; ATTEMPT="${3:?attempt name}"
WORK="$ROOT/work"
[[ ! -e "$WORK/$ATTEMPT" ]] || { echo 'attempt directory must be absent' >&2; exit 3; }
mkdir -p "$WORK/gov-catalog"
cp -n -- "$HERE"/governance-catalog/*.yml "$WORK/gov-catalog/"
. "$HERE/pins.env"
carrier() {
  taskset -c 0-3 podman --root "$ROOT/containers" --runroot "$ROOT/runroot" --storage-driver vfs run --rm \
    --hostname q1 --workdir /w \
    -v "$CHECKOUT":/src:ro -v "$ROOT/sdd-src":/sddsrc:ro -v "$WORK":/w:rw -v "$(dirname "$ARCHIVE")":/pkg:ro -v "$ROOT/dl":/dl:ro \
    -v "$HERE":/recipe:ro -e HOME=/w/home -e LANG=C.UTF-8 \
    --rootfs "$ROOT/rootfs/arch" taskset -c 0-3 "$@"
}
mkdir -p "$WORK/home"
if [[ ! -e "$WORK/stage" ]]; then
  carrier env FSGG_SOURCE_STAGE_ROOT=/w/stage FSGG_QUALIFIED_SDK_ROOT=/opt/dotnet PATH=/opt/dotnet:/usr/bin:/bin bash /src/scripts/polyglot/build-catalog.sh > "$WORK/build-catalog.log" 2>&1
fi
cmp -- "$WORK/stage/catalog-first.json" "$CHECKOUT/providers/polyglot.catalog.json"
[[ -e "$WORK/policy.json" ]] || carrier python3 -I /recipe/make-policy.py /w/policy.json "$GO_VERSION"
if [[ ! -d "$WORK/npm-input-cache" ]]; then
  carrier bash -c 'set -e; export PATH=/opt/node/bin:/usr/bin:/bin; mkdir -p /w/npmseed; cp -R /src/templates/fs-gg-typescript-cli /w/npmseed/typescript
    cd /w/npmseed/typescript && : > .u.cfg && : > .g.cfg && npm ci --ignore-scripts --no-audit --no-fund --userconfig=$PWD/.u.cfg --globalconfig=$PWD/.g.cfg --cache /w/npm-input-cache'
fi
carrier env ATTEMPT="$ATTEMPT" ARCHIVE_NAME="$(basename "$ARCHIVE")" GO_VERSION="$GO_VERSION" bash /recipe/inner-qualify.sh
echo "$WORK/$ATTEMPT"
