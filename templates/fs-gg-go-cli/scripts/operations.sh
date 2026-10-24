#!/bin/sh
# Each closed capability owns its work/output directory, independent of gate order.
set -eu
[ "$#" -eq 1 ] || { echo 'one operation required' >&2; exit 2; }
case "$1" in build|lint|test|public-surface|package|security|evidence|release) ;; *) echo 'unknown operation' >&2; exit 2;; esac
operation=$1
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$root"
export GOTOOLCHAIN=local GOWORK=off GOPROXY=off GOSUMDB=off
[ "$(go version)" = 'go version go1.27.1 linux/amd64' ] || exit 3
mkdir -p artifacts
report="$root/artifacts/$operation-handoff.json"
work="$root/artifacts/$operation-work"
[ ! -e "$report" ] || { echo 'stale operation evidence refused' >&2; exit 3; }
mkdir "$work"  # no overwrite/retry of an interrupted owned operation
cp go.mod main.go main_test.go display-name.txt security-policy.json toolchain-lock.json "$work/"
cd "$work"
: "${GOCACHE:?selected private Go cache required}" "${GOMODCACHE:?selected private module cache required}"
build() {
  go build -trimpath -buildvcs=false -o product-cli .
}
lint() {
  [ -z "$(gofmt -l .)" ]
  go vet ./...
}
test_product() {
  go test -count=1 ./...
}
surface() {
  [ "$(./product-cli hello 'surface text')" = 'hello surface text' ]
}
package_product() {
  tar --sort=name --mtime='UTC 1980-01-01' --owner=0 --group=0 --numeric-owner -cf product-cli.tar product-cli
}
security() {
  # Remains held until Root selects exact scanner/advisory closure and source policy.
  echo 'security closure is unselected; exact scanner/advisory qualification required' >&2
  return 3
}
case "$operation" in
  build) build ;;
  lint) lint ;;
  test) build; test_product ;;
  public-surface) build; surface ;;
  package) build; package_product ;;
  security) security ;;
  evidence|release) build; lint; test_product; surface; package_product; security ;;
esac
# The existing handoff contract cites the ORIGINAL inputs, not an invented pass summary.
cd "$root"
printf '{"contractVersion":"2.0.0","schemaVersion":1,"evidence":{"nodes":[{"id":"%s:%s","state":"real"}],"dependencies":[]},"governedReferences":[],"sources":[' "$operation" "$operation" > "$report"
separator=''
for input in go.mod main.go main_test.go scripts/operations.sh toolchain-lock.json security-policy.json; do
  digest=$(sha256sum "$input" | cut -d' ' -f1)
  [ "${#digest}" -eq 64 ] || exit 3
  case "$digest" in *[!0-9a-f]*) exit 3;; esac
  printf '%s{"path":"%s","digest":"sha256:%s"}' "$separator" "$input" "$digest" >> "$report"
  separator=,
done
printf ']}' >> "$report"
