#!/usr/bin/env bash
# Create a full-stack FS.GG product: SDD lifecycle + runnable Rendering app +
# Governance config, by composing the three products. This is the composition
# approach (see docs/design.md) — each product stays decoupled and independently
# owned; this script just glues them.
#
# Usage:
#   scripts/new-fullstack.sh <target-dir> <product-name> [rendering-template-source]
#
#   [rendering-template-source]  OPTIONAL. The provider descriptor is already
#                                version-pinned (FS.GG.UI.Template::<pinned>), so this
#                                arg is only needed to OVERRIDE that pin — e.g. point at
#                                a local path or a different NuGet id for `dotnet new
#                                install` of FS.GG.Rendering's `fs-gg-ui` template.
#
# The consumer only needs THIS repo: the script bootstraps the FS.GG.SDD CLI
# (`fsgg-sdd`, a global dotnet tool) on first run if it is not already on PATH.
# Override the bootstrap via env:
#   FSGG_SDD_PACKAGE   tool package id          (default: FS.GG.SDD.Cli)
#   FSGG_SDD_VERSION   pin a specific version   (default: latest from the feed)
#   FSGG_SDD_SOURCE    extra NuGet source       (e.g. a local feed or org feed)
set -euo pipefail

TARGET="${1:?target dir required}"
PRODUCT="${2:?product name required}"
RENDERING_SOURCE="${3:-}"   # optional override of the pinned provider source

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER="$REPO_ROOT/providers/rendering.providers.yml"

# 0. Ensure the FS.GG.SDD CLI is available. Global dotnet tools land in
#    ~/.dotnet/tools (or $DOTNET_CLI_HOME), which may not be on PATH in a fresh
#    shell, so put it on PATH first, then install only if still missing.
FSGG_SDD_PACKAGE="${FSGG_SDD_PACKAGE:-FS.GG.SDD.Cli}"
TOOLS_DIR="${DOTNET_CLI_HOME:-$HOME}/.dotnet/tools"
case ":$PATH:" in *":$TOOLS_DIR:"*) ;; *) export PATH="$TOOLS_DIR:$PATH" ;; esac
if ! command -v fsgg-sdd >/dev/null 2>&1; then
  echo "fsgg-sdd not found — installing $FSGG_SDD_PACKAGE as a global dotnet tool…"
  install_args=(tool install --global "$FSGG_SDD_PACKAGE")
  [[ -n "${FSGG_SDD_VERSION:-}" ]] && install_args+=(--version "$FSGG_SDD_VERSION")
  [[ -n "${FSGG_SDD_SOURCE:-}" ]]  && install_args+=(--add-source "$FSGG_SDD_SOURCE")
  dotnet "${install_args[@]}"
fi
command -v fsgg-sdd >/dev/null 2>&1 || {
  echo "ERROR: fsgg-sdd is still not on PATH after install." >&2
  echo "       Ensure '$TOOLS_DIR' is on your PATH, or set FSGG_SDD_SOURCE to a feed" >&2
  echo "       that serves $FSGG_SDD_PACKAGE, then re-run." >&2
  exit 1
}

mkdir -p "$TARGET/.fsgg"

# 1. Register the Rendering provider so `fsgg-sdd scaffold` can drive it. The provider
#    is self-pinned, so by default we copy it verbatim; an explicit override rewrites
#    only the `source:` value, leaving the rest of the descriptor (parameters, comments)
#    intact.
if [[ -n "$RENDERING_SOURCE" ]]; then
  sed -E "s|^([[:space:]]*)source:.*|\1source: ${RENDERING_SOURCE}|" \
      "$PROVIDER" > "$TARGET/.fsgg/providers.yml"
else
  cp "$PROVIDER" "$TARGET/.fsgg/providers.yml"
fi

# 2. SDD skeleton + full Rendering app, recorded in scaffold-provenance.
#    (fsgg-sdd installs/updates and runs the provider template; produced runtime
#    files are marked externally owned.) The `fs-gg-ui` template takes `--name`
#    (project names derive from it), so the product name is forwarded as `name=`.
fsgg-sdd scaffold --root "$TARGET" --provider rendering --param "name=$PRODUCT"

# 3. Activate Governance: drop policy/capabilities/tooling config into the project.
#    Done after scaffold (not via the provider) so it is not flagged as a provider
#    writing into the SDD-owned .fsgg/ tree.
dotnet new install "$REPO_ROOT/templates/fs-gg-governance" >/dev/null 2>&1 || true
dotnet new fs-gg-governance -o "$TARGET"

echo "Full-stack product created in $TARGET (SDD + Rendering + Governance)."
echo "Next: cd $TARGET && chmod +x fake.sh && ./fake.sh build -t Dev   # FAKE-backed; no root .sln"
echo "      (or compile one project directly: dotnet build src/$PRODUCT/$PRODUCT.fsproj)"
echo "      then drive the lifecycle: fsgg-sdd charter."
