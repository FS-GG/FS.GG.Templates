#!/bin/sh
# Each closed capability owns its work/output directory, independent of gate order.
set -eu
umask 077
set -C  # no metadata/report truncation, including a refused repeat
[ "$#" -eq 1 ] || { echo 'one operation required' >&2; exit 2; }
case "$1" in build|lint|test|public-surface|package|security|evidence|release) ;; *) echo 'unknown operation' >&2; exit 2;; esac
operation=$1
FSGG_POLYGLOT_PROVIDER=typescript-cli
export FSGG_POLYGLOT_PROVIDER
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$root"
report="$root/artifacts/$operation-handoff.json"
work="$root/artifacts/$operation-work"
custody="$root/artifacts/$operation-custody"
for owned in "$report" "$work" "$custody"; do
  [ ! -e "$owned" ] && [ ! -L "$owned" ] || { echo 'existing operation custody/evidence refused before probes' >&2; exit 3; }
done
mkdir -p artifacts
mkdir "$custody"
mkdir "$work"  # exclusive operation before any probe or seal write
[ "$(node --version)" = v24.20.0 ] || exit 3
[ "$(npm --version)" = 11.19.0 ] || exit 3
# These exact copied namespaces are the consumed product/test/package inputs.
source_roots='.gitignore README.md package.json package-lock.json tsconfig.json display-name.txt security-policy.json toolchain-lock.json src tests scripts'
seal_sources() {
  scope=$1
  manifest=$2
  (
    cd "$scope"
    # Refuse unsupported link/path shapes before execution; display-name CONTENT is unrestricted.
    find $source_roots ! -type d ! -type f -print > "$manifest.unsupported"
    [ ! -s "$manifest.unsupported" ] || { echo 'non-regular execution input refused' >&2; exit 3; }
    find $source_roots -type f -exec /bin/sh -c '
      for input do
        case "$input" in *[!A-Za-z0-9_./-]*) echo "unsupported evidence input path" >&2; exit 3;; esac
        sha256sum -- "$input" || exit 3
      done
    ' sh {} + > "$manifest.unsorted"
    LC_ALL=C sort "$manifest.unsorted" > "$manifest"
    [ -s "$manifest" ] || exit 3
  )
}
original_pre="$custody/original-pre.sha256"
staged_pre="$custody/staged-pre.sha256"
seal_sources "$root" "$original_pre"
cp .gitignore README.md package.json package-lock.json tsconfig.json display-name.txt security-policy.json toolchain-lock.json "$work/"
cp -R src tests scripts "$work/"
seal_sources "$work" "$staged_pre"
cmp "$original_pre" "$staged_pre" || { echo 'original/staged input mismatch before use' >&2; exit 3; }
# Reobserve the original adjacent to use; later root bytes never replace staged identity.
seal_sources "$root" "$custody/original-adjacent.sha256"
cmp "$original_pre" "$custody/original-adjacent.sha256" || exit 3
cd "$work"
. "$work/scripts/node-build.sh"
node_prepare

build() { node_build; }
lint() { node_lint; }
test_product() { node_test; }
surface() { node_surface; }
package_product() { node_package; }
. "$work/scripts/security.sh"

case "$operation" in
  build) build ;;
  lint) lint ;;
  test) build; test_product ;;
  public-surface) build; surface ;;
  package) build; package_product ;;
  security) security ;;
  evidence|release) build; lint; test_product; surface; package_product; security ;;
esac
# No receipt on source/staged drift, including tests, display text and package metadata.
seal_sources "$work" "$custody/staged-post.sha256"
seal_sources "$root" "$custody/original-post.sha256"
cmp "$staged_pre" "$custody/staged-post.sha256" || { echo 'executed staged input changed' >&2; exit 3; }
cmp "$original_pre" "$custody/original-post.sha256" || { echo 'original input changed during operation' >&2; exit 3; }
# Cite the sealed bytes actually staged/executed; exact equality above joins their original paths.
printf '{"contractVersion":"2.0.0","schemaVersion":1,"evidence":{"nodes":[{"id":"%s:%s","state":"real"}],"dependencies":[]},"governedReferences":[],"sources":[' "$operation" "$operation" > "$report"
separator=''
while read -r digest input; do
  [ "${#digest}" -eq 64 ] || exit 3
  case "$digest" in *[!0-9a-f]*) exit 3;; esac
  printf '%s{"path":"%s","digest":"sha256:%s"}' "$separator" "$input" "$digest" >> "$report"
  separator=,
done < "$staged_pre"
printf ']}' >> "$report"
