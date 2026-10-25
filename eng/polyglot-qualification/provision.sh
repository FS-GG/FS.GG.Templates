#!/usr/bin/env bash
# Build the dedicated qualification carrier into a FRESH root: a rootless podman container rootfs
# from a digest-pinned Arch userland (glibc 2.44, matching SDD's catalog scaffold requirement).
# Credential-free, read-only acquisition only. usage: provision.sh <absent-root-directory>
set -euo pipefail
umask 022
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$HERE/pins.env"
ROOT="${1:?absent fresh root directory required}"
[[ "$ROOT" = /* && ! -e "$ROOT" ]] || { echo 'fresh absolute root required' >&2; exit 3; }
mkdir -p "$ROOT"/{dl,rootfs,work,containers,runroot}
R="$ROOT/rootfs/arch"
podman_private() { podman --root "$ROOT/containers" --runroot "$ROOT/runroot" --storage-driver vfs "$@"; }
in_carrier() { taskset -c 0-3 podman --root "$ROOT/containers" --runroot "$ROOT/runroot" --storage-driver vfs run --rm --rootfs "$R" "$@"; }
# 1. Pinned image -> rootfs directory with mapped (container-root) ownership.
podman_private pull "$ARCH_IMAGE" >/dev/null
podman_private create --name seed "$ARCH_IMAGE" true >/dev/null
mkdir -p "$R"
podman_private export seed | podman unshare tar -x -C "$R" --numeric-owner
podman_private rm seed >/dev/null
podman_private rmi -a -f >/dev/null 2>&1 || true
# 2. Packages from a dated Arch Linux Archive snapshot (signed pacman packages).
podman unshare sh -c "printf 'Server = https://archive.archlinux.org/repos/%s/\$repo/os/\$arch\n' '$ARCH_SNAPSHOT' > '$R/etc/pacman.d/mirrorlist'"
# shellcheck disable=SC2086
in_carrier pacman -Syu --noconfirm --disable-sandbox $ARCH_PACKAGES
[[ "$(in_carrier sh -c 'ldd --version | head -1')" = 'ldd (GNU libc) 2.44' ]] || { echo 'carrier glibc is not 2.44' >&2; exit 3; }
# 3. Official archives, digest-verified before extraction.
curl -fsSL -o "$ROOT/dl/dotnet-sdk.tar.gz" "$DOTNET_SDK_URL"
echo "$DOTNET_SDK_SHA512  $ROOT/dl/dotnet-sdk.tar.gz" | sha512sum -c -
curl -fsSL -o "$ROOT/dl/go.tar.gz" "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"
echo "$GO_SHA256  $ROOT/dl/go.tar.gz" | sha256sum -c -
curl -fsSL -o "$ROOT/dl/node.tar.xz" "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz"
echo "$NODE_SHA256  $ROOT/dl/node.tar.xz" | sha256sum -c -
podman unshare sh -c "mkdir -p '$R/opt/dotnet' '$R/opt/go-$GO_VERSION' '$R/opt/node' '$R/opt/q1' \
  && tar -xzf '$ROOT/dl/dotnet-sdk.tar.gz' -C '$R/opt/dotnet' \
  && tar -xzf '$ROOT/dl/go.tar.gz' -C '$R/opt/go-$GO_VERSION' \
  && tar -xJf '$ROOT/dl/node.tar.xz' -C '$R/opt/node' --strip-components=1 \
  && chown -R 0:0 '$R/opt'"
# 4. Rust toolchain (rustup verifies its own manifests) and the TypeScript compiler probe target.
in_carrier sh -c "set -e; mkdir -p /opt/q1/rustup /opt/q1/cargo /opt/q1/ts; export RUSTUP_HOME=/opt/q1/rustup CARGO_HOME=/opt/q1/cargo PATH=/opt/node/bin:\$PATH
  rustup toolchain install $RUST_VERSION --profile minimal -c clippy -c rustfmt --no-self-update
  cd /opt/q1/ts && npm init -y >/dev/null && npm install typescript@$TYPESCRIPT_VERSION --ignore-scripts"
# 5. Advisory databases from upstream git, with the exact source commit and epoch recorded.
in_carrier sh -c "set -e; mkdir -p /opt/q1/src /opt/q1/advisory; cd /opt/q1/src
  git clone -q https://github.com/rustsec/advisory-db.git rustsec
  git clone -q https://github.com/golang/vulndb.git vulndb
  export PATH=/opt/go-$GO_VERSION/go/bin:\$PATH GOTOOLCHAIN=local GOPATH=/opt/q1/gopath GOCACHE=/opt/q1/gocache GOFLAGS=-mod=mod
  (cd vulndb && go run ./cmd/gendb -repo . -out /opt/q1/advisory/go-db)
  mkdir /opt/q1/advisory/rust-db; (cd rustsec && tar --exclude=.git -cf - .) | tar -xf - -C /opt/q1/advisory/rust-db
  (cd /opt/q1/advisory/rust-db && find . -type f | LC_ALL=C sort | xargs sha256sum) > /opt/q1/advisory/rust.manifest
  (cd /opt/q1/advisory/go-db && find . -type f | LC_ALL=C sort | xargs sha256sum) > /opt/q1/advisory/go.manifest
  { echo RUST_ADVISORY_COMMIT=\$(git -C rustsec rev-parse HEAD); echo RUST_ADVISORY_EPOCH=\$(git -C rustsec log -1 --format=%ct)
    echo GO_ADVISORY_COMMIT=\$(git -C vulndb rev-parse HEAD); echo GO_ADVISORY_EPOCH=\$(git -C vulndb log -1 --format=%ct); } > /opt/q1/advisory/sources.env"
cp "$R/opt/q1/advisory/sources.env" "$ROOT/work/advisory-sources.env"
# 6. Published CLIs from nuget.org and the immutable SDD driver source.
for pair in "fs.gg.sdd.cli:$SDD_CLI_VERSION:x-sdd:$SDD_CLI_SHA256" "fs.gg.governance.cli:$GOVERNANCE_CLI_VERSION:x-gov:$GOVERNANCE_CLI_SHA256"; do
  IFS=: read -r id version dir digest <<<"$pair"
  curl -fsSL -o "$ROOT/dl/$id.$version.nupkg" "https://api.nuget.org/v3-flatcontainer/$id/$version/$id.$version.nupkg"
  echo "$digest  $ROOT/dl/$id.$version.nupkg" | sha256sum -c -
  mkdir "$ROOT/dl/$dir"; bsdtar -xf "$ROOT/dl/$id.$version.nupkg" -C "$ROOT/dl/$dir"
done
git clone -q --no-hardlinks --no-checkout https://github.com/FS-GG/FS.GG.SDD.git "$ROOT/sdd-src"
git -C "$ROOT/sdd-src" checkout -q "$SDD_SOURCE_COMMIT"
git init -q "$ROOT/coord-fixture"
git -C "$ROOT/coord-fixture" remote add origin https://github.com/FS-GG/FS.GG.Coordination.git
git -C "$ROOT/coord-fixture" sparse-checkout set --no-cone tests/portable-workspace/image/fixture/python/app.py tests/portable-workspace/image/fixture/python/build.py tests/portable-workspace/image/fixture/python/test.py
git -C "$ROOT/coord-fixture" fetch -q --depth 1 origin "$PYTHON_FIXTURE_COMMIT"
git -C "$ROOT/coord-fixture" checkout -q FETCH_HEAD
[[ "$(git -C "$ROOT/coord-fixture" rev-parse HEAD)" = "$PYTHON_FIXTURE_COMMIT" ]]
echo "carrier ready: $ROOT"
