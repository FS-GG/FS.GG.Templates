#!/bin/sh
# Each closed capability owns its work/output directory, independent of gate order.
set -eu
[ "$#" -eq 1 ] || { echo 'one operation required' >&2; exit 2; }
case "$1" in build|lint|test|public-surface|package|security|evidence|release) ;; *) echo 'unknown operation' >&2; exit 2;; esac
operation=$1
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$root"
# A shim may not acquire or select a global toolchain before the first probe.
: "${RUSTUP_HOME:?selected private rustup home required}" "${CARGO_HOME:?selected private Cargo home required}"
case "$RUSTUP_HOME:$CARGO_HOME" in /*:/*) ;; *) echo 'absolute private tool homes required' >&2; exit 3;; esac
[ -d "$RUSTUP_HOME" ] && [ -d "$CARGO_HOME" ] || { echo 'selected tool homes must already exist' >&2; exit 3; }
[ "$RUSTUP_HOME" != "${HOME:?}/.rustup" ] && [ "$CARGO_HOME" != "$HOME/.cargo" ] || { echo 'global/default tool homes refused' >&2; exit 3; }
[ "$RUSTUP_HOME" != "$CARGO_HOME" ] || exit 3
export RUSTUP_TOOLCHAIN=1.98.1 RUSTUP_AUTO_INSTALL=0
case "$(rustc --version)" in 'rustc 1.98.1 '*) ;; *) exit 3;; esac
case "$(cargo --version)" in 'cargo 1.98.1 '*) ;; *) exit 3;; esac
mkdir -p artifacts
report="$root/artifacts/$operation-handoff.json"
work="$root/artifacts/$operation-work"
# These exact copied namespaces are the consumed product/test/package inputs.
source_roots='.gitignore README.md Cargo.toml Cargo.lock rust-toolchain.toml display-name.txt security-policy.json toolchain-lock.json src tests scripts'
seal_sources() {
  scope=$1
  manifest=$2
  (
    cd "$scope"
    # Refuse unsupported link/path shapes before execution; display-name CONTENT is unrestricted.
    find $source_roots -type l -print > "$manifest.links"
    [ ! -s "$manifest.links" ] || { echo 'linked execution input refused' >&2; exit 3; }
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
original_pre="$root/artifacts/$operation-original-pre.sha256"
staged_pre="$root/artifacts/$operation-staged-pre.sha256"
seal_sources "$root" "$original_pre"
[ ! -e "$report" ] || { echo 'stale operation evidence refused' >&2; exit 3; }
mkdir "$work"  # no overwrite/retry of an interrupted owned operation
cp .gitignore README.md Cargo.toml Cargo.lock rust-toolchain.toml display-name.txt security-policy.json toolchain-lock.json "$work/"
cp -R src tests scripts "$work/"
seal_sources "$work" "$staged_pre"
cmp "$original_pre" "$staged_pre" || { echo 'original/staged input mismatch before use' >&2; exit 3; }
# Reobserve the original adjacent to use; later root bytes never replace staged identity.
seal_sources "$root" "$root/artifacts/$operation-original-adjacent.sha256"
cmp "$original_pre" "$root/artifacts/$operation-original-adjacent.sha256" || exit 3
cd "$work"
export CARGO_NET_OFFLINE=true CARGO_TARGET_DIR="$work/target"
: "${CARGO_HOME:?selected private locked Cargo home required}"
build() {
  cargo build --locked --offline
}
lint() {
  cargo fmt --check
  cargo clippy --all-targets --locked --offline -- -D warnings
}
test_product() {
  cargo test --locked --offline
}
surface() {
  [ "$(target/debug/product-cli hello 'surface text')" = 'hello surface text' ]
}
package_product() {
  cargo package --locked --offline --allow-dirty
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
# No receipt on source/staged drift, including tests, display text and package metadata.
seal_sources "$work" "$root/artifacts/$operation-staged-post.sha256"
seal_sources "$root" "$root/artifacts/$operation-original-post.sha256"
cmp "$staged_pre" "$root/artifacts/$operation-staged-post.sha256" || { echo 'executed staged input changed' >&2; exit 3; }
cmp "$original_pre" "$root/artifacts/$operation-original-post.sha256" || { echo 'original input changed during operation' >&2; exit 3; }
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
