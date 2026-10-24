#!/usr/bin/env bash
# Build the host-libraries image used by `current-composition-local.py --container` (ADR-0096).
#
# The image holds only the Ubuntu 24.04 shared libraries Playwright's stock browsers need, the same
# distribution the hosted runner uses. Node, .NET, the receiver and the Playwright browsers are
# bind-mounted at run time, so no tool version is decided here. `podman run` + `podman commit` is used
# instead of `podman build` because nested rootless overlay build contexts are unavailable in the
# development container.
#
#   usage: current-composition-local-image.sh NODE_ROOT [IMAGE]
#   NODE_ROOT is an unpacked Node distribution (for example node-v24.20.0-linux-x64).
set -euo pipefail
node_root="$(realpath "${1:?unpacked Node distribution required}")"
image="${2:-localhost/fsgg-pw-host-libs:1.63}"
playwright=1.63.0
[[ -x "$node_root/bin/npx" ]]
name="fsgg-pw-host-libs-build-$$"
trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT
podman run --name "$name" -v "$node_root:/opt/node:ro" docker.io/library/ubuntu:24.04 bash -c "
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive HOME=/tmp/home PATH=/opt/node/bin:\$PATH
  mkdir -p \$HOME
  echo 'APT::Sandbox::User \"root\";' > /etc/apt/apt.conf.d/99sandbox
  apt-get update -qq
  npx --yes playwright@$playwright install-deps chromium firefox webkit
  apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/home"
podman commit "$name" "$image" >/dev/null
echo "built $image"
